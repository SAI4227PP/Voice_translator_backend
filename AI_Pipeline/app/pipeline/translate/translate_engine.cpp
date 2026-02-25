#include "translate_engine.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <cctype>
#include <condition_variable>
#include <cstddef>
#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <csignal>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <limits>
#include <memory>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <thread>
#include <utility>
#include <vector>

#include <curl/curl.h>
#ifdef __linux__
#include <pthread.h>
#include <sched.h>
#endif
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <netinet/in.h>
#include <arpa/inet.h>
#include <sys/prctl.h>
#include <unistd.h>

namespace fs = std::filesystem;

namespace {

#if defined(__has_cpp_attribute)
#if __has_cpp_attribute(likely)
#define TE_LIKELY_ATTR [[likely]]
#define TE_UNLIKELY_ATTR [[unlikely]]
#else
#define TE_LIKELY_ATTR
#define TE_UNLIKELY_ATTR
#endif
#else
#define TE_LIKELY_ATTR
#define TE_UNLIKELY_ATTR
#endif

#if defined(__GNUC__) || defined(__clang__)
#define TE_LIKELY(x) (__builtin_expect(!!(x), 1))
#define TE_UNLIKELY(x) (__builtin_expect(!!(x), 0))
#else
#define TE_LIKELY(x) (x)
#define TE_UNLIKELY(x) (x)
#endif

struct EngineConfig {
    std::string llama_cpp_path;
    std::string explicit_llama_cli_path;
    std::string model_path;
    int max_tokens = 256;
    int context_size = 2048;
    int threads = 4;
    int gpu_layers = 0;
    int queue_size = 256;
    int worker_count = 2;
    int max_input_chars = 4000;
    int server_port = 8089;
};

struct Request {
    std::string id;
    std::string cmd;
    std::string source;
    std::string target;
    std::string text;
    std::vector<std::string> batch_texts;
};

std::mutex g_stdout_mutex;
std::mutex g_slot_mutex;
constexpr int kMaxKvSlots = 512;
constexpr std::size_t kQueueSpinCount = 32;

constexpr std::array<const char*, 23> kSupportedIndianLanguages = {
    "en", "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok", "mai", "ml",
    "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta", "te", "ur"
};
constexpr std::size_t kLangCount = kSupportedIndianLanguages.size();
constexpr std::array<std::array<const char*, 2>, 6> kWarmupPairs = {{
    {"en", "hi"},
    {"hi", "en"},
    {"hi", "ta"},
    {"ta", "hi"},
    {"hi", "te"},
    {"te", "hi"},
}};

std::array<std::array<int, kLangCount>, kLangCount> g_slot_matrix{};
std::array<std::array<std::uint64_t, kLangCount>, kLangCount> g_slot_last_used{};
std::array<int, kMaxKvSlots> g_slot_src_idx{};
std::array<int, kMaxKvSlots> g_slot_dst_idx{};
int g_next_slot = 0;
std::uint64_t g_slot_clock = 0;

void init_slot_state_once() {
    static const bool initialized = []() {
        for (std::size_t i = 0; i < kLangCount; ++i) {
            for (std::size_t j = 0; j < kLangCount; ++j) {
                g_slot_matrix[i][j] = -1;
                g_slot_last_used[i][j] = 0;
            }
        }
        for (int i = 0; i < kMaxKvSlots; ++i) {
            g_slot_src_idx[static_cast<std::size_t>(i)] = -1;
            g_slot_dst_idx[static_cast<std::size_t>(i)] = -1;
        }
        return true;
    }();
    (void)initialized;
}

int language_index(const std::string& code) {
    for (std::size_t i = 0; i < kLangCount; ++i) {
        if (code == kSupportedIndianLanguages[i]) {
            return static_cast<int>(i);
        }
    }
    return -1;
}

bool is_supported_language_code(const std::string& code) {
    return language_index(code) >= 0;
}

bool validate_language_pair(const std::string& source, const std::string& target, std::string& error) {
    if (!is_supported_language_code(source)) {
        error = "unsupported_source_language";
        return false;
    }
    if (!is_supported_language_code(target)) {
        error = "unsupported_target_language";
        return false;
    }
    return true;
}

std::string trim(const std::string& input) {
    std::size_t start = 0;
    while (start < input.size() && std::isspace(static_cast<unsigned char>(input[start]))) {
        ++start;
    }
    if (start == input.size()) {
        return "";
    }
    std::size_t end = input.size() - 1;
    while (end > start && std::isspace(static_cast<unsigned char>(input[end]))) {
        --end;
    }
    return input.substr(start, end - start + 1);
}

std::string json_escape(const std::string& input) {
    if (input.find_first_of("\\\"\n\r\t") == std::string::npos &&
        std::none_of(input.begin(), input.end(), [](unsigned char c) { return c < 0x20; })) {
        return input;
    }

    std::string out;
    out.reserve(input.size() + 16);
    static const char* hex = "0123456789abcdef";
    for (unsigned char c : input) {
        switch (c) {
            case '\\': out += "\\\\"; break;
            case '"': out += "\\\""; break;
            case '\n': out += "\\n"; break;
            case '\r': out += "\\r"; break;
            case '\t': out += "\\t"; break;
            default:
                if (c < 0x20) {
                    out += "\\u00";
                    out.push_back(hex[(c >> 4) & 0x0F]);
                    out.push_back(hex[c & 0x0F]);
                } else {
                    out.push_back(static_cast<char>(c));
                }
                break;
        }
    }
    return out;
}

static const char* B64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

void append_json_quoted(std::string& out, const std::string& value) {
    out.push_back('"');
    out += json_escape(value);
    out.push_back('"');
}

void emit_json_line(
    const std::string& id,
    const std::string& status,
    const std::string& source,
    const std::string& target,
    const std::string& original_text,
    const std::string& translated_text,
    long long latency_ms,
    const std::string& stderr_snippet,
    const std::string& error_message = "",
    const std::vector<std::string>* translated_items = nullptr
) {
    std::string out;
    std::size_t reserve_size = 256 + id.size() + status.size() + source.size() + target.size() +
                               original_text.size() + translated_text.size() + stderr_snippet.size() +
                               error_message.size();
    reserve_size += 128;
    if (translated_items) {
        for (const auto& item : *translated_items) {
            reserve_size += item.size() + 4;
        }
    }
    out.reserve(reserve_size);

    out += "{\"id\":";
    append_json_quoted(out, id);
    out += ",\"status\":";
    append_json_quoted(out, status);
    out += ",\"source\":";
    append_json_quoted(out, source);
    out += ",\"target\":";
    append_json_quoted(out, target);
    out += ",\"original_text\":";
    append_json_quoted(out, original_text);
    out += ",\"translated_text\":";
    append_json_quoted(out, translated_text);

    if (translated_items) {
        out += ",\"translated_items\":[";
        for (std::size_t i = 0; i < translated_items->size(); ++i) {
            if (i > 0) {
                out.push_back(',');
            }
            append_json_quoted(out, (*translated_items)[i]);
        }
        out.push_back(']');
    }

    out += ",\"latency_ms\":";
    out += std::to_string(latency_ms);
    out += ",\"stderr_snippet\":";
    append_json_quoted(out, stderr_snippet);
    out += ",\"error\":";
    append_json_quoted(out, error_message);
    out.push_back('}');

    std::lock_guard<std::mutex> lock(g_stdout_mutex);
    std::cout << out << '\n';
}

std::string resolve_binary(const std::string& base, const std::vector<std::string>& rel_candidates, const std::string& explicit_path) {
    if (!explicit_path.empty() && explicit_path != "-") {
        fs::path p(explicit_path);
        if (fs::exists(p)) {
            return p.string();
        }
    }
    for (const auto& rel : rel_candidates) {
        fs::path p = fs::path(base) / rel;
        if (fs::exists(p)) {
            return p.string();
        }
    }
    return "";
}

std::string resolve_llama_server_path(const std::string& llama_cpp_path) {
    return resolve_binary(
        llama_cpp_path,
        {"bin/llama-server", "build/bin/llama-server", "llama-server", "server"},
        ""
    );
}

bool wait_for_port_ready(int port, int timeout_ms, pid_t server_pid) {
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(timeout_ms);
    while (std::chrono::steady_clock::now() < deadline) {
        // If server died early, fail fast instead of waiting full timeout.
        if (server_pid > 0) {
            int child_status = 0;
            const pid_t wait_rc = waitpid(server_pid, &child_status, WNOHANG);
            if (wait_rc == server_pid) {
                return false;
            }
        }

        int sock = socket(AF_INET, SOCK_STREAM, 0);
        if (sock < 0) {
            std::this_thread::sleep_for(std::chrono::milliseconds(50));
            continue;
        }

        sockaddr_in addr{};
        addr.sin_family = AF_INET;
        addr.sin_port = htons(static_cast<uint16_t>(port));
        inet_pton(AF_INET, "127.0.0.1", &addr.sin_addr);

        int ok = connect(sock, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
        close(sock);
        if (ok == 0) {
            return true;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    return false;
}

std::string strip_trailing_newlines(const std::string& input) {
    std::size_t end = input.size();
    while (end > 0 && (input[end - 1] == '\n' || input[end - 1] == '\r')) {
        --end;
    }
    return input.substr(0, end);
}

std::string build_prompt(const std::string& text, const std::string& source_lang, const std::string& target_lang) {
    const std::string clean_text = strip_trailing_newlines(text);
    auto lang_name = [](const std::string& code) -> const char* {
        if (code == "en") return "English";
        if (code == "hi") return "Hindi";
        if (code == "ta") return "Tamil";
        if (code == "te") return "Telugu";
        if (code == "bn") return "Bengali";
        if (code == "gu") return "Gujarati";
        if (code == "kn") return "Kannada";
        if (code == "ml") return "Malayalam";
        if (code == "mr") return "Marathi";
        if (code == "or") return "Odia";
        if (code == "pa") return "Punjabi";
        if (code == "ur") return "Urdu";
        if (code == "as") return "Assamese";
        if (code == "brx") return "Bodo";
        if (code == "doi") return "Dogri";
        if (code == "kok") return "Konkani";
        if (code == "ks") return "Kashmiri";
        if (code == "mai") return "Maithili";
        if (code == "mni") return "Manipuri";
        if (code == "ne") return "Nepali";
        if (code == "sa") return "Sanskrit";
        if (code == "sat") return "Santali";
        if (code == "sd") return "Sindhi";
        return "target language";
    };
    std::string prompt;
    prompt.reserve(clean_text.size() + 196);
    prompt += "<";
    prompt += source_lang;
    prompt += "2";
    prompt += target_lang;
    prompt += ">\nTranslate the following text from ";
    prompt += lang_name(source_lang);
    prompt += " to ";
    prompt += lang_name(target_lang);
    prompt += ". Return only translated text in ";
    prompt += lang_name(target_lang);
    prompt += ".\nText: ";
    prompt += clean_text;
    prompt += "\nTranslation:";
    return prompt;
}

int adaptive_max_tokens(const std::string& text, int max_tokens) {
    const std::size_t n = text.size();
    if (n <= 32) {
        return std::min(max_tokens, 16);
    }
    if (n <= 80) {
        return std::min(max_tokens, 32);
    }
    if (n <= 240) {
        return std::min(max_tokens, 64);
    }
    if (n <= 800) {
        return std::min(max_tokens, 128);
    }
    return max_tokens;
}

std::string take_tail_window(const std::string& text, std::size_t max_words, std::size_t max_chars) {
    if (text.empty()) {
        return text;
    }

    const std::size_t begin_by_chars = (text.size() > max_chars) ? (text.size() - max_chars) : 0;
    std::size_t start = begin_by_chars;

    std::size_t words = 0;
    bool in_word = false;
    for (std::size_t i = text.size(); i > begin_by_chars; --i) {
        const unsigned char c = static_cast<unsigned char>(text[i - 1]);
        const bool ws = std::isspace(c) != 0;
        if (!ws && !in_word) {
            in_word = true;
            ++words;
            if (words > max_words) {
                start = i;
                break;
            }
        } else if (ws) {
            in_word = false;
        }
    }

    while (start < text.size() && std::isspace(static_cast<unsigned char>(text[start]))) {
        ++start;
    }
    return text.substr(start);
}

std::string truncate_text(const std::string& text, int max_chars) {
    if (max_chars <= 0 || static_cast<int>(text.size()) <= max_chars) {
        return text;
    }
    return text.substr(0, static_cast<std::size_t>(max_chars));
}

int slot_for_pair(const std::string& source, const std::string& target) {
    const int src_idx = language_index(source);
    const int dst_idx = language_index(target);
    if (src_idx < 0 || dst_idx < 0) {
        return 0;
    }

    std::lock_guard<std::mutex> lock(g_slot_mutex);
    init_slot_state_once();
    ++g_slot_clock;

    int& assigned = g_slot_matrix[static_cast<std::size_t>(src_idx)][static_cast<std::size_t>(dst_idx)];
    if (TE_LIKELY(assigned >= 0)) TE_LIKELY_ATTR {
        g_slot_last_used[static_cast<std::size_t>(src_idx)][static_cast<std::size_t>(dst_idx)] = g_slot_clock;
        return assigned;
    }

    if (g_next_slot < kMaxKvSlots) {
        const int new_slot = g_next_slot++;
        assigned = new_slot;
        g_slot_last_used[static_cast<std::size_t>(src_idx)][static_cast<std::size_t>(dst_idx)] = g_slot_clock;
        g_slot_src_idx[static_cast<std::size_t>(new_slot)] = src_idx;
        g_slot_dst_idx[static_cast<std::size_t>(new_slot)] = dst_idx;
        return new_slot;
    }

    int victim_slot = 0;
    std::uint64_t oldest = std::numeric_limits<std::uint64_t>::max();
    for (int slot = 0; slot < kMaxKvSlots; ++slot) {
        const int old_src = g_slot_src_idx[static_cast<std::size_t>(slot)];
        const int old_dst = g_slot_dst_idx[static_cast<std::size_t>(slot)];
        if (old_src < 0 || old_dst < 0) {
            victim_slot = slot;
            oldest = 0;
            break;
        }
        const auto used = g_slot_last_used[static_cast<std::size_t>(old_src)][static_cast<std::size_t>(old_dst)];
        if (used < oldest) {
            oldest = used;
            victim_slot = slot;
        }
    }

    const int old_src = g_slot_src_idx[static_cast<std::size_t>(victim_slot)];
    const int old_dst = g_slot_dst_idx[static_cast<std::size_t>(victim_slot)];
    if (old_src >= 0 && old_dst >= 0) {
        g_slot_matrix[static_cast<std::size_t>(old_src)][static_cast<std::size_t>(old_dst)] = -1;
    }

    assigned = victim_slot;
    g_slot_last_used[static_cast<std::size_t>(src_idx)][static_cast<std::size_t>(dst_idx)] = g_slot_clock;
    g_slot_src_idx[static_cast<std::size_t>(victim_slot)] = src_idx;
    g_slot_dst_idx[static_cast<std::size_t>(victim_slot)] = dst_idx;
    return victim_slot;
}

std::string base64_decode(const std::string& input) {
    static const std::array<int, 256> T = []() {
        std::array<int, 256> table{};
        table.fill(-1);
        for (int i = 0; i < 64; ++i) {
            table[static_cast<unsigned char>(B64_ALPHABET[i])] = i;
        }
        return table;
    }();

    std::string out;
    int val = 0;
    int valb = -8;
    for (unsigned char c : input) {
        if (T[c] == -1) {
            if (c == '=') break;
            continue;
        }
        val = (val << 6) + T[c];
        valb += 6;
        if (valb >= 0) {
            out.push_back(static_cast<char>((val >> valb) & 0xFF));
            valb -= 8;
        }
    }
    return out;
}

std::string join_null_terminated(const std::vector<std::string>& items) {
    if (items.empty()) {
        return "";
    }

    std::size_t total = 0;
    for (const auto& s : items) {
        total += s.size();
    }
    total += items.size() - 1;

    std::string out;
    out.resize(total);
    char* dst = out.data();
    for (std::size_t i = 0; i < items.size(); ++i) {
        const auto& item = items[i];
        if (!item.empty()) {
            std::memcpy(dst, item.data(), item.size());
            dst += item.size();
        }
        if (i + 1 < items.size()) {
            *dst++ = '\0';
        }
    }

    return out;
}

bool parse_json_string(const char*& p, const char* end, std::string& out) {
    if (p >= end || *p != '"') {
        return false;
    }
    ++p;
    out.clear();
    while (p < end) {
        char c = *p++;
        if (c == '"') {
            return true;
        }
        if (c == '\\') {
            if (p >= end) return false;
            c = *p++;
            switch (c) {
                case 'n': out.push_back('\n'); break;
                case 'r': out.push_back('\r'); break;
                case 't': out.push_back('\t'); break;
                case '"': out.push_back('"'); break;
                case '\\': out.push_back('\\'); break;
                default: out.push_back(c); break;
            }
            continue;
        }
        out.push_back(c);
    }
    return false;
}

void skip_json_ws(const char*& p, const char* end) {
    while (p < end && std::isspace(static_cast<unsigned char>(*p))) {
        ++p;
    }
}

bool parse_request_json_fields(const std::string& line, Request& r) {
    const char* p = line.data();
    const char* end = p + line.size();
    std::string key;
    std::string value;

    while (p < end) {
        skip_json_ws(p, end);
        if (p >= end || *p != '"') {
            ++p;
            continue;
        }
        if (!parse_json_string(p, end, key)) {
            return false;
        }
        skip_json_ws(p, end);
        if (p >= end || *p != ':') {
            continue;
        }
        ++p;
        skip_json_ws(p, end);
        if (p >= end || *p != '"') {
            continue;
        }
        if (!parse_json_string(p, end, value)) {
            return false;
        }

        if (key == "id") {
            r.id = value;
        } else if (key == "cmd") {
            r.cmd = value;
        } else if (key == "source") {
            r.source = value;
        } else if (key == "target") {
            r.target = value;
        } else if (key == "text_b64") {
            r.text = base64_decode(value);
        } else if (key == "batch_b64") {
            std::string blob = base64_decode(value);
            std::string cur;
            for (char c : blob) {
                if (c == '\0') {
                    r.batch_texts.push_back(cur);
                    cur.clear();
                } else {
                    cur.push_back(c);
                }
            }
            if (!cur.empty() || (!blob.empty() && blob.back() != '\0')) {
                r.batch_texts.push_back(cur);
            }
        }
    }

    return true;
}

struct StreamResponse {
    std::string buffer;
    std::string content;
    std::string raw;
};

bool extract_content_field(const char* data, std::size_t len, std::string& out) {
    static constexpr const char* kKey = "\"content\":\"";
    const char* p = data;
    const char* end = data + len;

    while (p < end) {
        const char* key = static_cast<const char*>(std::memchr(p, '"', static_cast<std::size_t>(end - p)));
        if (!key) return false;
        const std::size_t rem = static_cast<std::size_t>(end - key);
        const std::size_t klen = std::char_traits<char>::length(kKey);
        if (rem >= klen && std::memcmp(key, kKey, klen) == 0) {
            const char* v = key + klen;
            bool escape = false;
            while (v < end) {
                const char c = *v++;
                if (escape) {
                    switch (c) {
                        case 'n': out.push_back('\n'); break;
                        case 'r': out.push_back('\r'); break;
                        case 't': out.push_back('\t'); break;
                        case '"': out.push_back('"'); break;
                        case '\\': out.push_back('\\'); break;
                        default: out.push_back(c); break;
                    }
                    escape = false;
                    continue;
                }
                if (c == '\\') {
                    escape = true;
                    continue;
                }
                if (c == '"') {
                    return true;
                }
                out.push_back(c);
            }
            return false;
        }
        p = key + 1;
    }
    return false;
}

void parse_stream_line(const char* line, std::size_t len, StreamResponse& resp) {
    while (len > 0 && std::isspace(static_cast<unsigned char>(*line))) {
        ++line;
        --len;
    }
    while (len > 0 && std::isspace(static_cast<unsigned char>(line[len - 1]))) {
        --len;
    }
    if (len == 0) {
        return;
    }

    static constexpr const char* kData = "data:";
    if (len >= 5 && std::memcmp(line, kData, 5) == 0) {
        line += 5;
        len -= 5;
        while (len > 0 && std::isspace(static_cast<unsigned char>(*line))) {
            ++line;
            --len;
        }
    }

    if (len == 6 && std::memcmp(line, "[DONE]", 6) == 0) {
        return;
    }

    if (len > 0 && line[0] == '{') {
        extract_content_field(line, len, resp.content);
    }
}

void parse_stream_buffer(std::string& buffer, StreamResponse& resp) {
    const char* begin = buffer.data();
    const char* ptr = begin;
    const char* end = begin + buffer.size();

    while (ptr < end) {
        const char* nl = static_cast<const char*>(std::memchr(ptr, '\n', static_cast<std::size_t>(end - ptr)));
        if (TE_UNLIKELY(!nl)) TE_UNLIKELY_ATTR {
            break;
        }
        parse_stream_line(ptr, static_cast<std::size_t>(nl - ptr), resp);
        ptr = nl + 1;
    }

    if (ptr > begin) {
        buffer.erase(0, static_cast<std::size_t>(ptr - begin));
    }
}

size_t curl_stream_callback(char* ptr, size_t size, size_t nmemb, void* userdata) {
    const std::size_t total = size * nmemb;
#if defined(__GNUC__) || defined(__clang__)
    __builtin_prefetch(ptr + 64, 0, 1);
#endif
    auto* resp = static_cast<StreamResponse*>(userdata);
    resp->raw.append(ptr, total);
    resp->buffer.append(ptr, total);
    parse_stream_buffer(resp->buffer, *resp);
    return total;
}

std::pair<std::string, std::string> http_post_json_streaming(const std::string& url, const std::string& payload, long timeout_seconds) {
    thread_local CURL* curl = []() {
        CURL* h = curl_easy_init();
        if (h) {
            curl_easy_setopt(h, CURLOPT_NOSIGNAL, 1L);
            curl_easy_setopt(h, CURLOPT_TCP_KEEPALIVE, 1L);
            curl_easy_setopt(h, CURLOPT_TCP_KEEPIDLE, 30L);
            curl_easy_setopt(h, CURLOPT_TCP_KEEPINTVL, 15L);
            curl_easy_setopt(h, CURLOPT_FOLLOWLOCATION, 0L);
            curl_easy_setopt(h, CURLOPT_WRITEFUNCTION, curl_stream_callback);
            curl_easy_setopt(h, CURLOPT_POST, 1L);
            curl_easy_setopt(h, CURLOPT_CONNECTTIMEOUT, 5L);
        }
        return h;
    }();

    if (!curl) {
        return {"", "curl_easy_init_failed"};
    }

    StreamResponse response;
    char errbuf[CURL_ERROR_SIZE] = {0};
    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, payload.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, static_cast<long>(payload.size()));
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, timeout_seconds);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &response);
    curl_easy_setopt(curl, CURLOPT_ERRORBUFFER, errbuf);

    const CURLcode rc = curl_easy_perform(curl);
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    
    if (rc != CURLE_OK) {
        std::string msg = errbuf[0] ? errbuf : curl_easy_strerror(rc);
        if (headers) curl_slist_free_all(headers);
        return {"", "curl_error: " + msg};
    }
    if (http_code < 200 || http_code >= 300) {
        if (headers) curl_slist_free_all(headers);
        return {"", "http_status_" + std::to_string(http_code) + ": " + trim(response.raw)};
    }
    parse_stream_buffer(response.buffer, response);
    if (!response.buffer.empty()) {
        parse_stream_line(response.buffer.data(), response.buffer.size(), response);
    }
    if (headers) curl_slist_free_all(headers);

    if (!response.content.empty()) {
        return {response.content, ""};
    }
    return {"", "empty_translation_output"};
}

struct RingSlot {
    std::atomic<bool> ready{false};
    std::optional<Request> req;
};

class TranslationDaemon {
public:
    explicit TranslationDaemon(EngineConfig cfg)
        : cfg_(std::move(cfg)) {
        queue_capacity_ = static_cast<std::size_t>(std::max(1, cfg_.queue_size));
        queue_slots_ = std::make_unique<RingSlot[]>(queue_capacity_);
    }

    int run() {
        curl_global_init(CURL_GLOBAL_DEFAULT);
        const std::string llama_server = resolve_llama_server_path(cfg_.llama_cpp_path);
        if (llama_server.empty()) {
            std::cerr << "llama-server not found in " << cfg_.llama_cpp_path << "\n";
            curl_global_cleanup();
            return 5;
        }
        if (!fs::exists(cfg_.model_path)) {
            std::cerr << "model not found: " << cfg_.model_path << "\n";
            curl_global_cleanup();
            return 4;
        }

        if (!start_llama_server(llama_server)) {
            std::cerr << "failed to start llama-server\n";
            curl_global_cleanup();
            return 6;
        }

        for (int i = 0; i < std::max(1, cfg_.worker_count); ++i) {
            workers_.emplace_back(&TranslationDaemon::worker_loop, this, i);
        }

        std::string line;
        while (std::getline(std::cin, line)) {
            if (trim(line).empty()) continue;
            Request req = parse_request(line);
            if (req.id.empty()) {
                emit_json_line("", "error", "", "", "", "", 0, "", "invalid_request_id");
                continue;
            }

            if (req.cmd == "shutdown") {
                emit_json_line(req.id, "ok", "", "", "", "", 0, "", "");
                break;
            }

            if (!enqueue(std::move(req))) {
                emit_json_line(req.id, "error", req.source, req.target, "", "", 0, "queue_full", "queue_full");
            }
        }

        stop_.store(true);
        cv_.notify_all();
        for (auto& w : workers_) {
            if (w.joinable()) w.join();
        }
        stop_llama_server();
        curl_global_cleanup();
        return 0;
    }

private:
    Request parse_request(const std::string& line) {
        Request r;
        parse_request_json_fields(line, r);
        return r;
    }

    bool enqueue(Request req) {
        for (;;) {
            std::uint64_t tail = queue_tail_.load(std::memory_order_relaxed);
            const std::uint64_t head = queue_head_.load(std::memory_order_acquire);
            if (tail - head >= queue_capacity_) {
                return false;
            }

            if (!queue_tail_.compare_exchange_weak(
                    tail,
                    tail + 1,
                    std::memory_order_acq_rel,
                    std::memory_order_relaxed)) {
                continue;
            }

            RingSlot& slot = queue_slots_[static_cast<std::size_t>(tail % queue_capacity_)];
            std::size_t spins = 0;
            while (slot.ready.load(std::memory_order_acquire)) {
                if (++spins >= kQueueSpinCount) {
                    std::this_thread::yield();
                    spins = 0;
                }
            }

            slot.req.emplace(std::move(req));
            slot.ready.store(true, std::memory_order_release);
            queue_size_.fetch_add(1, std::memory_order_release);
            cv_.notify_one();
            return true;
        }
    }

    bool try_dequeue(Request& req) {
        for (;;) {
            std::uint64_t head = queue_head_.load(std::memory_order_relaxed);
            const std::uint64_t tail = queue_tail_.load(std::memory_order_acquire);
            if (head >= tail) {
                return false;
            }
            if (!queue_head_.compare_exchange_weak(
                    head,
                    head + 1,
                    std::memory_order_acq_rel,
                    std::memory_order_relaxed)) {
                continue;
            }

            RingSlot& slot = queue_slots_[static_cast<std::size_t>(head % queue_capacity_)];
            std::size_t spins = 0;
            while (!slot.ready.load(std::memory_order_acquire)) {
                if (stop_.load()) return false;
                if (++spins >= kQueueSpinCount) {
                    std::this_thread::yield();
                    spins = 0;
                }
            }

            req = std::move(*slot.req);
            slot.req.reset();
            slot.ready.store(false, std::memory_order_release);
            queue_size_.fetch_sub(1, std::memory_order_release);
            return true;
        }
    }

    bool dequeue_or_wait(Request& req) {
        for (std::size_t i = 0; i < kQueueSpinCount; ++i) {
            if (try_dequeue(req)) {
                return true;
            }
            if (stop_.load()) {
                return false;
            }
            std::this_thread::yield();
        }

        std::unique_lock<std::mutex> lock(cv_mu_);
        cv_.wait_for(lock, std::chrono::milliseconds(2), [&]() {
            return stop_.load() || queue_size_.load(std::memory_order_acquire) > 0;
        });
        if (stop_.load() && queue_size_.load(std::memory_order_acquire) == 0) {
            return false;
        }
        return try_dequeue(req);
    }

    void bind_worker_affinity(int worker_index) {
#ifdef __linux__
        const unsigned int hw = std::thread::hardware_concurrency();
        if (hw == 0) return;
        cpu_set_t cpuset;
        CPU_ZERO(&cpuset);
        CPU_SET(static_cast<unsigned int>(worker_index) % hw, &cpuset);
        pthread_setaffinity_np(pthread_self(), sizeof(cpu_set_t), &cpuset);
#else
        (void)worker_index;
#endif
    }

    void worker_loop(int worker_index) {
        bind_worker_affinity(worker_index);
        for (;;) {
            Request req;
            if (!dequeue_or_wait(req)) {
                if (stop_.load()) {
                    return;
                }
                continue;
            }
            process_request(req);
        }
    }

    std::pair<std::string, std::string> translate_text(const std::string& text, const std::string& source, const std::string& target) {
        const std::string limited = truncate_text(text, cfg_.max_input_chars);
        const std::string compact = strip_trailing_newlines(limited);
        const int n_predict = adaptive_max_tokens(compact, cfg_.max_tokens);
        const std::string prompt = build_prompt(compact, source, target);
        const int slot = slot_for_pair(source, target);

        const std::string escaped_prompt = json_escape(prompt);
        thread_local std::string payload;
        payload.clear();
        payload.reserve(512 + prompt.size());
        payload.append("{\"prompt\":\"");
        payload.append(escaped_prompt);
        payload.append("\",\"n_predict\":");
        payload.append(std::to_string(n_predict));
        payload.append(",\"temperature\":0.01,\"top_p\":0.9,\"repeat_penalty\":1.1,\"cache_prompt\":true,\"stream\":true,\"id_slot\":");
        payload.append(std::to_string(slot));
        payload.push_back('}');

        const std::string url = "http://127.0.0.1:" + std::to_string(cfg_.server_port) + "/completion";
        auto [out, err] = http_post_json_streaming(url, payload, 120L);
        if (!err.empty()) {
            return {"", err};
        }

        std::string content = trim(out);
        if (content.empty()) {
            return {"", "empty_translation_output"};
        }
        return {content, ""};
    }

    void process_request(const Request& req) {
        const auto start = std::chrono::steady_clock::now();

        if (req.cmd == "warm_up") {
            auto result = translate_text("test", "en", "hi");
            const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count();
            if (!result.second.empty()) {
                emit_json_line(req.id, "error", "en", "hi", "test", "", ms, result.second.substr(0, 256), "warm_up_failed");
            } else {
                emit_json_line(req.id, "ok", "en", "hi", "test", "", ms, "", "");
            }
            return;
        }

        if (req.cmd == "translate") {
            std::string lang_error;
            if (!validate_language_pair(req.source, req.target, lang_error)) {
                const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count();
                emit_json_line(req.id, "error", req.source, req.target, req.text, "", ms, "", lang_error);
                return;
            }
            auto result = translate_text(req.text, req.source, req.target);
            const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count();
            if (!result.second.empty()) {
                emit_json_line(req.id, "error", req.source, req.target, req.text, "", ms, result.second.substr(0, 256), "translate_failed");
            } else {
                emit_json_line(req.id, "ok", req.source, req.target, req.text, result.first, ms, "", "");
            }
            return;
        }

        if (req.cmd == "batch_translate") {
            std::string lang_error;
            if (!validate_language_pair(req.source, req.target, lang_error)) {
                const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count();
                emit_json_line(req.id, "error", req.source, req.target, "", "", ms, "", lang_error);
                return;
            }
            std::vector<std::string> out_items;
            out_items.reserve(req.batch_texts.size());
            std::string err;
            for (const auto& t : req.batch_texts) {
                auto result = translate_text(t, req.source, req.target);
                if (!result.second.empty()) {
                    err = result.second;
                    break;
                }
                out_items.push_back(result.first);
            }
            const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count();
            if (!err.empty()) {
                emit_json_line(req.id, "error", req.source, req.target, "", "", ms, err.substr(0, 256), "batch_translate_failed");
            } else {
                emit_json_line(req.id, "ok", req.source, req.target, "", "", ms, "", "", &out_items);
            }
            return;
        }

        if (req.cmd == "validate") {
            const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count();
            emit_json_line(req.id, "ok", req.source, req.target, req.text, "", ms, "", "");
            return;
        }

        const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(std::chrono::steady_clock::now() - start).count();
        emit_json_line(req.id, "error", req.source, req.target, req.text, "", ms, "", "unknown_command");
    }

    bool start_llama_server(const std::string& llama_server_path) {
        pid_t pid = fork();
        if (pid < 0) {
            return false;
        }

        if (pid == 0) {
            // Ensure child dies if parent daemon dies unexpectedly.
            prctl(PR_SET_PDEATHSIG, SIGTERM);

            std::string port_s = std::to_string(cfg_.server_port);
            std::string ctx_s = std::to_string(cfg_.context_size);
            std::string threads_s = std::to_string(cfg_.threads);
            std::string ngl_s = std::to_string(std::max(0, cfg_.gpu_layers));

            std::vector<char*> args;
            args.push_back(const_cast<char*>(llama_server_path.c_str()));
            args.push_back(const_cast<char*>("-m"));
            args.push_back(const_cast<char*>(cfg_.model_path.c_str()));
            args.push_back(const_cast<char*>("-c"));
            args.push_back(const_cast<char*>(ctx_s.c_str()));
            args.push_back(const_cast<char*>("-t"));
            args.push_back(const_cast<char*>(threads_s.c_str()));
            args.push_back(const_cast<char*>("--host"));
            args.push_back(const_cast<char*>("127.0.0.1"));
            args.push_back(const_cast<char*>("--port"));
            args.push_back(const_cast<char*>(port_s.c_str()));
            args.push_back(const_cast<char*>("-ngl"));
            args.push_back(const_cast<char*>(ngl_s.c_str()));
            args.push_back(nullptr);

            execv(llama_server_path.c_str(), args.data());
            _exit(127);
        }

        llama_server_pid_ = pid;
        return wait_for_port_ready(cfg_.server_port, 30000, llama_server_pid_);
    }

    void stop_llama_server() {
        if (llama_server_pid_ > 0) {
            kill(llama_server_pid_, SIGTERM);
            int status = 0;
            waitpid(llama_server_pid_, &status, 0);
            llama_server_pid_ = -1;
        }
    }

private:
    EngineConfig cfg_;
    std::atomic<bool> stop_{false};
    std::size_t queue_capacity_ = 0;
    std::unique_ptr<RingSlot[]> queue_slots_;
    std::atomic<std::uint64_t> queue_head_{0};
    std::atomic<std::uint64_t> queue_tail_{0};
    std::atomic<std::uint64_t> queue_size_{0};
    std::mutex cv_mu_;
    std::condition_variable cv_;
    std::vector<std::thread> workers_;
    pid_t llama_server_pid_ = -1;
};

EngineConfig parse_daemon_config(int argc, char* argv[]) {
    EngineConfig cfg;
    // Expected:
    // daemon llama_cpp_path llama_cli_path_or_dash model max_tokens ctx threads gpu_layers queue workers max_input port
    cfg.llama_cpp_path = (argc > 2) ? argv[2] : "";
    cfg.explicit_llama_cli_path = (argc > 3) ? argv[3] : "-";
    cfg.model_path = (argc > 4) ? argv[4] : "";
    cfg.max_tokens = (argc > 5) ? std::atoi(argv[5]) : 256;
    cfg.context_size = (argc > 6) ? std::atoi(argv[6]) : 2048;
    cfg.threads = (argc > 7) ? std::atoi(argv[7]) : 4;
    cfg.gpu_layers = (argc > 8) ? std::atoi(argv[8]) : 0;
    cfg.queue_size = (argc > 9) ? std::atoi(argv[9]) : 256;
    cfg.worker_count = (argc > 10) ? std::atoi(argv[10]) : 2;
    cfg.max_input_chars = (argc > 11) ? std::atoi(argv[11]) : 4000;
    cfg.server_port = (argc > 12) ? std::atoi(argv[12]) : 8089;
    return cfg;
}

}  // namespace

int translate_engine::run_translate_engine(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: translate_engine <daemon|validate> ...\n";
        return 2;
    }

    const std::string mode = argv[1];

    if (mode == "daemon") {
        EngineConfig cfg = parse_daemon_config(argc, argv);
        TranslationDaemon daemon(std::move(cfg));
        return daemon.run();
    }

    if (mode == "validate") {
        if (argc < 5) {
            std::cerr << "Usage: translate_engine validate <llama_cpp_path> <llama_cli_path_or_dash> <model_path>\n";
            return 2;
        }
        const std::string llama_cpp_path = argv[2];
        const std::string explicit_cli = argv[3];
        const std::string model_path = argv[4];

        const std::string llama_server = resolve_llama_server_path(llama_cpp_path);
        if (llama_server.empty()) {
            std::cerr << "llama-server not found\n";
            return 5;
        }
        if (!fs::exists(model_path)) {
            std::cerr << "model not found\n";
            return 4;
        }
        if (!explicit_cli.empty() && explicit_cli != "-" && !fs::exists(explicit_cli)) {
            std::cerr << "explicit llama-cli path not found\n";
            return 5;
        }
        std::cout << "ok";
        return 0;
    }

    std::cerr << "Unknown mode: " << mode << "\n";
    return 2;
}

int main(int argc, char* argv[]) {
    std::ios::sync_with_stdio(false);
    return translate_engine::run_translate_engine(argc, argv);
}
