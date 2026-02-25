#include "tts_engine.hpp"

#include <algorithm>
#include <array>
#include <atomic>
#include <chrono>
#include <condition_variable>
#include <cctype>
#include <cstddef>
#include <cmath>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <filesystem>
#include <iostream>
#include <memory>
#include <mutex>
#include <optional>
#include <sstream>
#include <string>
#include <thread>
#include <unordered_set>
#include <utility>
#include <vector>

#include <curl/curl.h>
#ifdef __linux__
#include <pthread.h>
#include <sched.h>
#include <arpa/inet.h>
#include <netinet/in.h>
#include <signal.h>
#include <sys/socket.h>
#include <sys/types.h>
#include <sys/wait.h>
#include <unistd.h>
#endif

namespace fs = std::filesystem;

namespace {

struct EngineConfig {
    std::string model_id;
    std::string llama_cpp_path;
    std::string explicit_llama_server_path;
    std::string default_voice;
    int timeout_seconds = 90;
    int queue_size = 128;
    int worker_count = 2;
    int max_input_chars = 1200;
    int llama_server_port = 8091;
    bool use_local_model = false;
    int gguf_threads = 2;
    int gguf_context_size = 1024;
    bool pin_workers = false;
};

struct Request {
    std::string id;
    std::string cmd;
    std::string language;
    std::string text;
    std::vector<std::int64_t> token_ids;
    std::vector<std::int64_t> attention_mask;
    bool has_token_tensors = false;
};
constexpr std::size_t kQueueSpinCount = 32;

struct RingSlot {
    std::atomic<bool> ready{false};
    std::optional<Request> req;
};

std::mutex g_stdout_mutex;

const std::unordered_set<std::string> kSupportedLanguages = {
    "en", "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok", "mai",
    "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta", "te", "ur",
};

bool ends_with(const std::string& text, const std::string& suffix) {
    return text.size() >= suffix.size() &&
           text.compare(text.size() - suffix.size(), suffix.size(), suffix) == 0;
}

std::string to_lower(std::string input) {
    std::transform(input.begin(), input.end(), input.begin(), [](unsigned char c) {
        return static_cast<char>(std::tolower(c));
    });
    return input;
}

std::string trim(const std::string& input) {
    std::size_t start = 0;
    while (start < input.size() && std::isspace(static_cast<unsigned char>(input[start]))) {
        ++start;
    }
    if (start == input.size()) return "";
    std::size_t end = input.size() - 1;
    while (end > start && std::isspace(static_cast<unsigned char>(input[end]))) {
        --end;
    }
    return input.substr(start, end - start + 1);
}

std::string json_escape(const std::string& input) {
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
        }
    }
    return out;
}

const char* B64_ALPHABET = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/";

std::string base64_encode_bytes(const std::string& input) {
    std::string out;
    out.reserve(((input.size() + 2) / 3) * 4);
    int val = 0;
    int valb = -6;
    for (unsigned char c : input) {
        val = (val << 8) + c;
        valb += 8;
        while (valb >= 0) {
            out.push_back(B64_ALPHABET[(val >> valb) & 0x3F]);
            valb -= 6;
        }
    }
    if (valb > -6) {
        out.push_back(B64_ALPHABET[((val << 8) >> (valb + 8)) & 0x3F]);
    }
    while (out.size() % 4) out.push_back('=');
    return out;
}

std::string base64_decode(const std::string& input) {
    static const std::array<int, 256> table = []() {
        std::array<int, 256> t{};
        t.fill(-1);
        for (int i = 0; i < 64; ++i) {
            t[static_cast<unsigned char>(B64_ALPHABET[i])] = i;
        }
        return t;
    }();

    std::string out;
    int val = 0;
    int valb = -8;
    for (unsigned char c : input) {
        if (table[c] == -1) {
            if (c == '=') break;
            continue;
        }
        val = (val << 6) + table[c];
        valb += 6;
        if (valb >= 0) {
            out.push_back(static_cast<char>((val >> valb) & 0xFF));
            valb -= 8;
        }
    }
    return out;
}

std::vector<std::int64_t> decode_i64_vector_from_b64(const std::string& b64) {
    std::vector<std::int64_t> out;
    if (b64.empty()) {
        return out;
    }
    const std::string bytes = base64_decode(b64);
    if (bytes.empty() || (bytes.size() % sizeof(std::int64_t)) != 0) {
        return out;
    }
    out.resize(bytes.size() / sizeof(std::int64_t));
    std::memcpy(out.data(), bytes.data(), bytes.size());
    return out;
}

std::string json_get_string(const std::string& json, const std::string& key) {
    const std::string pattern = "\"" + key + "\"";
    std::size_t pos = json.find(pattern);
    if (pos == std::string::npos) return "";
    pos = json.find(':', pos);
    if (pos == std::string::npos) return "";
    pos = json.find('"', pos);
    if (pos == std::string::npos) return "";
    ++pos;

    std::string out;
    bool escape = false;
    while (pos < json.size()) {
        const char c = json[pos++];
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
        if (c == '"') break;
        out.push_back(c);
    }
    return out;
}

std::string truncate_text(const std::string& text, int max_chars) {
    if (max_chars <= 0 || static_cast<int>(text.size()) <= max_chars) {
        return text;
    }
    return text.substr(0, static_cast<std::size_t>(max_chars));
}

std::string resolve_binary(
    const std::string& base,
    const std::vector<std::string>& rel_candidates,
    const std::string& explicit_path
) {
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

std::string resolve_llama_server_path(const std::string& llama_cpp_path, const std::string& explicit_path) {
    return resolve_binary(
        llama_cpp_path,
        {"bin/llama-server", "build/bin/llama-server", "llama-server", "server"},
        explicit_path
    );
}

#ifdef __linux__
bool wait_for_port_ready(int port, int timeout_ms, pid_t server_pid) {
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(timeout_ms);
    while (std::chrono::steady_clock::now() < deadline) {
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
        const int ok = connect(sock, reinterpret_cast<sockaddr*>(&addr), sizeof(addr));
        close(sock);
        if (ok == 0) {
            return true;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    return false;
}
#endif

bool wait_for_http_ready(int port, int timeout_ms) {
    const std::string url = "http://127.0.0.1:" + std::to_string(port) + "/health";
    const auto deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(timeout_ms);
    while (std::chrono::steady_clock::now() < deadline) {
        CURL* curl = curl_easy_init();
        if (!curl) {
            std::this_thread::sleep_for(std::chrono::milliseconds(100));
            continue;
        }

        std::string body;
        curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
        curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);
        curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 0L);
        curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT_MS, 500L);
        curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, 1000L);
        curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, +[](char* ptr, size_t size, size_t nmemb, void* userdata) -> size_t {
            auto* out = static_cast<std::string*>(userdata);
            out->append(ptr, size * nmemb);
            return size * nmemb;
        });
        curl_easy_setopt(curl, CURLOPT_WRITEDATA, &body);

        const CURLcode rc = curl_easy_perform(curl);
        long http_code = 0;
        curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
        curl_easy_cleanup(curl);

        if (rc == CURLE_OK && http_code >= 200 && http_code < 300) {
            return true;
        }
        std::this_thread::sleep_for(std::chrono::milliseconds(100));
    }
    return false;
}

void emit_json_line(
    const std::string& id,
    const std::string& status,
    const std::string& language,
    const std::string& audio_b64,
    long long latency_ms,
    const std::string& stderr_snippet,
    const std::string& error_message = ""
) {
    std::lock_guard<std::mutex> lock(g_stdout_mutex);
    std::cout << "{"
              << "\"id\":\"" << json_escape(id) << "\","
              << "\"status\":\"" << json_escape(status) << "\","
              << "\"language\":\"" << json_escape(language) << "\","
              << "\"audio_b64\":\"" << audio_b64 << "\","
              << "\"latency_ms\":" << latency_ms << ","
              << "\"stderr_snippet\":\"" << json_escape(stderr_snippet) << "\","
              << "\"error\":\"" << json_escape(error_message) << "\""
              << "}" << std::endl;
}

void append_u16le(std::string& out, std::uint16_t v) {
    out.push_back(static_cast<char>(v & 0xFF));
    out.push_back(static_cast<char>((v >> 8) & 0xFF));
}

void append_u32le(std::string& out, std::uint32_t v) {
    out.push_back(static_cast<char>(v & 0xFF));
    out.push_back(static_cast<char>((v >> 8) & 0xFF));
    out.push_back(static_cast<char>((v >> 16) & 0xFF));
    out.push_back(static_cast<char>((v >> 24) & 0xFF));
}

std::string pcm_f32_to_wav(const std::vector<float>& pcm, int sample_rate_hz) {
    const int channels = 1;
    const int bits_per_sample = 16;
    const int block_align = channels * (bits_per_sample / 8);
    const int byte_rate = sample_rate_hz * block_align;
    const std::uint32_t data_bytes = static_cast<std::uint32_t>(pcm.size() * block_align);
    const std::uint32_t riff_size = 36u + data_bytes;

    std::string out;
    out.reserve(44 + static_cast<std::size_t>(data_bytes));

    out.append("RIFF", 4);
    append_u32le(out, riff_size);
    out.append("WAVE", 4);
    out.append("fmt ", 4);
    append_u32le(out, 16);  // PCM fmt chunk size
    append_u16le(out, 1);   // PCM format
    append_u16le(out, static_cast<std::uint16_t>(channels));
    append_u32le(out, static_cast<std::uint32_t>(sample_rate_hz));
    append_u32le(out, static_cast<std::uint32_t>(byte_rate));
    append_u16le(out, static_cast<std::uint16_t>(block_align));
    append_u16le(out, static_cast<std::uint16_t>(bits_per_sample));
    out.append("data", 4);
    append_u32le(out, data_bytes);

    float peak = 0.0f;
    for (float s : pcm) {
        peak = std::max(peak, std::fabs(s));
    }
    if (peak < 1e-5f) {
        peak = 1.0f;
    }

    for (float s : pcm) {
        const float norm = s / peak;
        const float clamped = std::max(-1.0f, std::min(1.0f, norm));
        const int sample_i = static_cast<int>(std::lrint(clamped * 32767.0f));
        const std::int16_t sample = static_cast<std::int16_t>(sample_i);
        append_u16le(out, static_cast<std::uint16_t>(sample));
    }
    return out;
}

size_t curl_write_callback(char* ptr, size_t size, size_t nmemb, void* userdata) {
    const std::size_t total = size * nmemb;
    auto* output = static_cast<std::string*>(userdata);
    output->append(ptr, total);
    return total;
}

std::pair<std::string, std::string> http_post_binary_audio(
    const std::string& url,
    const std::string& payload,
    long timeout_seconds
) {
    thread_local CURL* curl = curl_easy_init();
    if (!curl) {
        return {"", "curl_easy_init_failed"};
    }

    curl_easy_reset(curl);
    std::string out;
    char errbuf[CURL_ERROR_SIZE] = {0};

    struct curl_slist* headers = nullptr;
    headers = curl_slist_append(headers, "Content-Type: application/json");

    curl_easy_setopt(curl, CURLOPT_URL, url.c_str());
    curl_easy_setopt(curl, CURLOPT_NOSIGNAL, 1L);
    curl_easy_setopt(curl, CURLOPT_TCP_KEEPALIVE, 1L);
    curl_easy_setopt(curl, CURLOPT_TCP_KEEPIDLE, 30L);
    curl_easy_setopt(curl, CURLOPT_TCP_KEEPINTVL, 15L);
    curl_easy_setopt(curl, CURLOPT_FOLLOWLOCATION, 0L);
    curl_easy_setopt(curl, CURLOPT_HTTPHEADER, headers);
    curl_easy_setopt(curl, CURLOPT_POST, 1L);
    curl_easy_setopt(curl, CURLOPT_POSTFIELDS, payload.c_str());
    curl_easy_setopt(curl, CURLOPT_POSTFIELDSIZE, static_cast<long>(payload.size()));
    const long timeout_ms = std::max(1000L, timeout_seconds * 1000L);
    curl_easy_setopt(curl, CURLOPT_TIMEOUT_MS, timeout_ms);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT_MS, 3000L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_LIMIT, 64L);
    curl_easy_setopt(curl, CURLOPT_LOW_SPEED_TIME, 10L);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &out);
    curl_easy_setopt(curl, CURLOPT_ERRORBUFFER, errbuf);

    const CURLcode rc = curl_easy_perform(curl);
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    if (headers) curl_slist_free_all(headers);

    if (rc != CURLE_OK) {
        const std::string msg = errbuf[0] ? errbuf : curl_easy_strerror(rc);
        return {"", "curl_error: " + msg + " url=" + url};
    }
    if (http_code < 200 || http_code >= 300) {
        std::string tail = trim(out);
        if (tail.size() > 240) {
            tail = tail.substr(tail.size() - 240);
        }
        std::string err = "http_status_" + std::to_string(http_code) + " url=" + url;
        if (!tail.empty()) {
            err += " body_tail=" + tail;
        }
        return {"", err};
    }
    return {out, ""};
}

class TTSDaemon {
public:
    explicit TTSDaemon(EngineConfig cfg) : cfg_(std::move(cfg)) {
        queue_capacity_ = static_cast<std::size_t>(std::max(1, cfg_.queue_size));
        queue_slots_ = std::make_unique<RingSlot[]>(queue_capacity_);
    }

    int run() {
        curl_global_init(CURL_GLOBAL_DEFAULT);

        if (cfg_.use_local_model) {
            std::string init_err;
            if (!init_local_gguf(init_err)) {
                std::cerr << "local_gguf_init_failed: " << init_err << "\n";
                curl_global_cleanup();
                return 8;
            }
        }

        for (int i = 0; i < std::max(1, cfg_.worker_count); ++i) {
            workers_.emplace_back(&TTSDaemon::worker_loop, this, i);
        }

        std::string line;
        while (std::getline(std::cin, line)) {
            if (trim(line).empty()) continue;
            Request req = parse_request(line);
            if (req.id.empty()) {
                emit_json_line("", "error", "", "", 0, "", "invalid_request_id");
                continue;
            }
            if (req.cmd == "shutdown") {
                emit_json_line(req.id, "ok", req.language, "", 0, "", "");
                break;
            }
            if (!enqueue(std::move(req))) {
                emit_json_line(req.id, "error", "", "", 0, "queue_full", "queue_full");
            }
        }

        stop_.store(true);
        cv_.notify_all();
        for (auto& w : workers_) {
            if (w.joinable()) w.join();
        }
        stop_local_gguf();
        curl_global_cleanup();
        return 0;
    }

private:
    void bind_worker_affinity(int worker_index) {
#ifdef __linux__
        if (!cfg_.pin_workers) return;
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

    bool init_local_gguf(std::string& err) {
#ifdef __linux__
        const std::string llama_server =
            resolve_llama_server_path(cfg_.llama_cpp_path, cfg_.explicit_llama_server_path);
        if (llama_server.empty()) {
            err = "llama_server_not_found_in_llama_cpp_path";
            return false;
        }
        if (!fs::exists(cfg_.model_id)) {
            err = "local_model_not_found";
            return false;
        }

        pid_t pid = fork();
        if (pid < 0) {
            err = "fork_failed";
            return false;
        }
        if (pid == 0) {
            const std::string port_s = std::to_string(cfg_.llama_server_port);
            const std::string threads_s = std::to_string(std::max(1, cfg_.gguf_threads));
            const std::string context_s = std::to_string(std::max(256, cfg_.gguf_context_size));
            std::vector<char*> args;
            args.push_back(const_cast<char*>(llama_server.c_str()));
            args.push_back(const_cast<char*>("-m"));
            args.push_back(const_cast<char*>(cfg_.model_id.c_str()));
            args.push_back(const_cast<char*>("-t"));
            args.push_back(const_cast<char*>(threads_s.c_str()));
            args.push_back(const_cast<char*>("-c"));
            args.push_back(const_cast<char*>(context_s.c_str()));
            args.push_back(const_cast<char*>("--host"));
            args.push_back(const_cast<char*>("127.0.0.1"));
            args.push_back(const_cast<char*>("--port"));
            args.push_back(const_cast<char*>(port_s.c_str()));
            args.push_back(nullptr);
            execv(llama_server.c_str(), args.data());
            _exit(127);
        }

        llama_server_pid_ = pid;
        if (!wait_for_port_ready(cfg_.llama_server_port, 30000, llama_server_pid_)) {
            stop_local_gguf();
            err = "llama_server_start_failed_or_timed_out";
            return false;
        }
        if (!wait_for_http_ready(cfg_.llama_server_port, 30000)) {
            stop_local_gguf();
            err = "llama_server_http_not_ready";
            return false;
        }
        local_llama_raw_base_ = "http://127.0.0.1:" + std::to_string(cfg_.llama_server_port);
        local_llama_base_ = local_llama_raw_base_ + "/v1";
        return true;
#else
        err = "local_gguf_mode_is_supported_only_on_linux";
        return false;
#endif
    }

    void stop_local_gguf() {
#ifdef __linux__
        if (llama_server_pid_ > 0) {
            kill(llama_server_pid_, SIGTERM);
            int status = 0;
            waitpid(llama_server_pid_, &status, 0);
            llama_server_pid_ = -1;
        }
#endif
    }

    Request parse_request(const std::string& line) {
        Request r;
        r.id = json_get_string(line, "id");
        r.cmd = json_get_string(line, "cmd");
        r.language = json_get_string(line, "language");
        const std::string b64 = json_get_string(line, "text_b64");
        if (!b64.empty()) r.text = base64_decode(b64);
        const std::string token_ids_b64 = json_get_string(line, "token_ids_i64_b64");
        const std::string attention_b64 = json_get_string(line, "attention_mask_i64_b64");
        if (!token_ids_b64.empty() && !attention_b64.empty()) {
            r.token_ids = decode_i64_vector_from_b64(token_ids_b64);
            r.attention_mask = decode_i64_vector_from_b64(attention_b64);
            r.has_token_tensors = !r.token_ids.empty() && (r.token_ids.size() == r.attention_mask.size());
        }
        return r;
    }

    bool enqueue(Request req) {
        const std::uint64_t qsize_now = queue_size_.load(std::memory_order_acquire);
        const std::uint64_t high_water =
            queue_capacity_ > 1 ? (queue_capacity_ - std::max<std::size_t>(1, queue_capacity_ / 10)) : 1;
        if (qsize_now >= high_water) {
            return false;
        }
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
            auto ready_deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(2);
            std::size_t spins = 0;
            while (!slot.ready.load(std::memory_order_acquire)) {
                if (stop_.load(std::memory_order_relaxed)) {
                    return false;
                }
                if (++spins >= kQueueSpinCount) {
                    spins = 0;
                    if (std::chrono::steady_clock::now() >= ready_deadline) {
                        std::this_thread::sleep_for(std::chrono::microseconds(50));
                        ready_deadline = std::chrono::steady_clock::now() + std::chrono::milliseconds(2);
                    } else {
                        std::this_thread::yield();
                    }
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

    std::pair<std::string, std::string> synthesize_local_gguf(const std::string& text, const std::string& language) {
        const std::string clean_text = truncate_text(trim(text), cfg_.max_input_chars);
        if (clean_text.empty()) {
            return {"", "empty_text"};
        }
        if (local_llama_base_.empty()) {
            return {"", "local_gguf_runtime_not_initialized"};
        }

        thread_local std::string payload;
        payload.clear();
        payload.reserve(256 + clean_text.size());
        payload += "{";
        payload += "\"model\":\"" + json_escape(cfg_.model_id) + "\",";
        payload += "\"input\":\"" + json_escape(clean_text) + "\",";
        payload += "\"voice\":\"" + json_escape(cfg_.default_voice) + "\",";
        payload += "\"language\":\"" + json_escape(language) + "\",";
        payload += "\"response_format\":\"wav\"";
        payload += "}";

        // Some llama-server builds expose /audio/speech, others /v1/audio/speech.
        auto result = http_post_binary_audio(local_llama_base_ + "/audio/speech", payload, cfg_.timeout_seconds);
        if (result.second.find("http_status_404") != std::string::npos) {
            return http_post_binary_audio(local_llama_raw_base_ + "/audio/speech", payload, cfg_.timeout_seconds);
        }
        return result;
    }

    std::pair<std::string, std::string> synthesize(
        const std::string& text,
        const std::string& language,
        const std::vector<std::int64_t>& token_ids,
        const std::vector<std::int64_t>& attention_mask,
        bool has_token_tensors
    ) {
        (void)token_ids;
        (void)attention_mask;
        (void)has_token_tensors;
        if (kSupportedLanguages.find(language) == kSupportedLanguages.end()) {
            return {"", "unsupported_language"};
        }
        if (cfg_.use_local_model) {
            return synthesize_local_gguf(text, language);
        }
        return {"", "local_model_required"};
    }

    void process_request(const Request& req) {
        const auto start = std::chrono::steady_clock::now();

        if (req.cmd == "warm_up") {
            const std::string warm_text = req.text.empty() ? "नमस्ते" : req.text;
            auto result = synthesize(warm_text, "hi", req.token_ids, req.attention_mask, req.has_token_tensors);
            const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - start).count();
            if (!result.second.empty()) {
                emit_json_line(req.id, "error", "hi", "", ms, result.second.substr(0, 256), "warm_up_failed");
            } else {
                emit_json_line(req.id, "ok", "hi", base64_encode_bytes(result.first), ms, "", "");
            }
            return;
        }

        if (req.cmd == "synthesize") {
            auto result = synthesize(req.text, req.language, req.token_ids, req.attention_mask, req.has_token_tensors);
            const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - start).count();
            if (!result.second.empty()) {
                const std::string detail = result.second.substr(0, 256);
                emit_json_line(req.id, "error", req.language, "", ms, detail, detail);
            } else {
                emit_json_line(req.id, "ok", req.language, base64_encode_bytes(result.first), ms, "", "");
            }
            return;
        }

        if (req.cmd == "validate") {
            const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                std::chrono::steady_clock::now() - start).count();
            emit_json_line(req.id, "ok", req.language, "", ms, "", "");
            return;
        }

        const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
            std::chrono::steady_clock::now() - start).count();
        emit_json_line(req.id, "error", req.language, "", ms, "", "unknown_command");
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
    std::string local_llama_base_;
    std::string local_llama_raw_base_;
#ifdef __linux__
    pid_t llama_server_pid_ = -1;
#endif
};

EngineConfig parse_daemon_config(int argc, char* argv[]) {
    EngineConfig cfg;
    // daemon model voice timeout queue workers max_input llama_cpp_path llama_server_port explicit_llama_server_path gguf_threads gguf_context_size pin_workers
    cfg.model_id = (argc > 2) ? argv[2] : "";
    cfg.default_voice = (argc > 3) ? argv[3] : "anushka";
    cfg.timeout_seconds = (argc > 4) ? std::atoi(argv[4]) : 90;
    cfg.queue_size = (argc > 5) ? std::atoi(argv[5]) : 128;
    cfg.worker_count = (argc > 6) ? std::atoi(argv[6]) : 2;
    cfg.max_input_chars = (argc > 7) ? std::atoi(argv[7]) : 600;
    cfg.llama_cpp_path = (argc > 8) ? argv[8] : "/app/llama.cpp";
    cfg.llama_server_port = (argc > 9) ? std::max(1, std::atoi(argv[9])) : 8091;
    cfg.explicit_llama_server_path = (argc > 10) ? argv[10] : "-";
    cfg.gguf_threads = (argc > 11) ? std::max(1, std::atoi(argv[11])) : 2;
    cfg.gguf_context_size = (argc > 12) ? std::max(256, std::atoi(argv[12])) : 1024;
    cfg.pin_workers = (argc > 13) ? (to_lower(trim(argv[13])) == "true" || trim(argv[13]) == "1") : false;
    cfg.use_local_model = fs::exists(cfg.model_id);
    return cfg;
}

}  // namespace

int tts_engine::run_tts_engine(int argc, char* argv[]) {
    if (argc < 2) {
        std::cerr << "Usage: tts_engine <daemon|validate> ...\n";
        return 2;
    }
    const std::string mode = argv[1];
    if (mode == "daemon") {
        EngineConfig cfg = parse_daemon_config(argc, argv);
        if (cfg.model_id.empty()) {
            std::cerr << "missing_model\n";
            return 2;
        }
        if (cfg.use_local_model &&
            !ends_with(to_lower(trim(cfg.model_id)), ".gguf")) {
            std::cerr << "invalid_local_model_extension_expected_gguf\n";
            return 2;
        }
        if (!cfg.use_local_model) {
            std::cerr << "local_model_required\n";
            return 2;
        }
        TTSDaemon daemon(std::move(cfg));
        return daemon.run();
    }
    if (mode == "validate") {
        if (argc < 3) {
            std::cerr << "Usage: tts_engine validate <model_id_or_gguf_path> [llama_cpp_path] [explicit_llama_server_path]\n";
            return 2;
        }
        const std::string model_id = argv[2];
        const std::string llama_cpp_path = (argc > 3) ? argv[3] : "/app/llama.cpp";
        const std::string explicit_llama_server_path = (argc > 4) ? argv[4] : "-";
        if (trim(model_id).empty()) {
            std::cerr << "invalid_configuration\n";
            return 2;
        }
        const bool is_local_model = fs::exists(model_id);
        if (is_local_model) {
            if (!ends_with(to_lower(trim(model_id)), ".gguf")) {
                std::cerr << "invalid_local_model_extension_expected_gguf\n";
                return 2;
            }
            const std::string server = resolve_llama_server_path(llama_cpp_path, explicit_llama_server_path);
            if (server.empty()) {
                std::cerr << "llama_server_not_found_for_local_gguf_mode\n";
                return 2;
            }
        } else {
            std::cerr << "local_model_required\n";
            return 2;
        }
        std::cout << "ok";
        return 0;
    }
    std::cerr << "Unknown mode: " << mode << "\n";
    return 2;
}

int main(int argc, char* argv[]) {
    return tts_engine::run_tts_engine(argc, argv);
}

