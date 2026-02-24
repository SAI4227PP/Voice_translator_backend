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
#ifdef TTS_ENGINE_ENABLE_ONNX
#include <onnxruntime_cxx_api.h>
#endif
#ifdef __linux__
#include <pthread.h>
#include <sched.h>
#endif

namespace fs = std::filesystem;

namespace {

struct EngineConfig {
    std::string api_base_url;
    std::string model_id;
    std::string default_voice;
    std::string api_key;
    int timeout_seconds = 90;
    int queue_size = 128;
    int worker_count = 2;
    int max_input_chars = 1200;
    bool use_onnx = false;
    bool use_local_model = false;
    int onnx_sample_rate = 24000;
    int onnx_threads = 1;
};
constexpr std::size_t kMaxOnnxTokenLength = 4096;
constexpr std::size_t kOnnxTokenWindow = 256;

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
    const std::string& api_key,
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
    if (!api_key.empty() && api_key != "-") {
        const std::string auth = "Authorization: Bearer " + api_key;
        headers = curl_slist_append(headers, auth.c_str());
    }

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
    curl_easy_setopt(curl, CURLOPT_TIMEOUT, timeout_seconds);
    curl_easy_setopt(curl, CURLOPT_CONNECTTIMEOUT, 5L);
    curl_easy_setopt(curl, CURLOPT_WRITEFUNCTION, curl_write_callback);
    curl_easy_setopt(curl, CURLOPT_WRITEDATA, &out);
    curl_easy_setopt(curl, CURLOPT_ERRORBUFFER, errbuf);

    const CURLcode rc = curl_easy_perform(curl);
    long http_code = 0;
    curl_easy_getinfo(curl, CURLINFO_RESPONSE_CODE, &http_code);
    if (headers) curl_slist_free_all(headers);

    if (rc != CURLE_OK) {
        const std::string msg = errbuf[0] ? errbuf : curl_easy_strerror(rc);
        return {"", "curl_error: " + msg};
    }
    if (http_code < 200 || http_code >= 300) {
        return {"", "http_status_" + std::to_string(http_code)};
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

        if (cfg_.use_onnx) {
            std::string init_err;
            if (!init_onnx(init_err)) {
                std::cerr << "onnx_init_failed: " << init_err << "\n";
                curl_global_cleanup();
                return 7;
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
        curl_global_cleanup();
        return 0;
    }

private:
#ifdef TTS_ENGINE_ENABLE_ONNX
    struct OnnxRuntimeState {
        Ort::Env env{ORT_LOGGING_LEVEL_WARNING, "svara-tts"};
        Ort::SessionOptions opts{};
        std::unique_ptr<Ort::Session> session;
        std::string output_name{"audio"};
    };
#endif

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

    bool init_onnx(std::string& err) {
#ifdef TTS_ENGINE_ENABLE_ONNX
        try {
            onnx_.reset(new OnnxRuntimeState());
            onnx_->opts.SetIntraOpNumThreads(std::max(1, cfg_.onnx_threads));
            onnx_->opts.SetInterOpNumThreads(1);
            onnx_->opts.SetGraphOptimizationLevel(GraphOptimizationLevel::ORT_ENABLE_ALL);
            onnx_->opts.EnableCpuMemArena();
            onnx_->opts.SetExecutionMode(ExecutionMode::ORT_SEQUENTIAL);
            onnx_->session.reset(new Ort::Session(onnx_->env, cfg_.model_id.c_str(), onnx_->opts));
            Ort::AllocatorWithDefaultOptions allocator;
            auto output_name = onnx_->session->GetOutputNameAllocated(0, allocator);
            if (output_name && output_name.get()[0] != '\0') {
                onnx_->output_name = output_name.get();
            }
            return true;
        } catch (const std::exception& e) {
            err = e.what();
            return false;
        }
#else
        err = "compiled_without_onnxruntime";
        return false;
#endif
    }

#ifdef TTS_ENGINE_ENABLE_ONNX
    std::pair<std::string, std::string> synthesize_onnx(
        const std::vector<std::int64_t>& input_ids,
        const std::vector<std::int64_t>& attention_mask
    ) {
        if (!onnx_ || !onnx_->session) {
            return {"", "onnx_session_not_initialized"};
        }
        if (input_ids.empty() || attention_mask.empty()) {
            return {"", "missing_token_tensors"};
        }
        if (input_ids.size() != attention_mask.size()) {
            return {"", "token_tensor_size_mismatch"};
        }
        const std::array<std::int64_t, 2> shape = {1, static_cast<std::int64_t>(input_ids.size())};
        const char* input_names[] = {"input_ids", "attention_mask"};
        const char* output_names[] = {onnx_->output_name.c_str()};

        try {
            thread_local Ort::MemoryInfo mem_info = Ort::MemoryInfo::CreateCpu(OrtArenaAllocator, OrtMemTypeDefault);
            Ort::Value input_ids_tensor = Ort::Value::CreateTensor<std::int64_t>(
                mem_info,
                const_cast<std::int64_t*>(input_ids.data()),
                input_ids.size(),
                shape.data(),
                shape.size()
            );
            Ort::Value mask_tensor = Ort::Value::CreateTensor<std::int64_t>(
                mem_info,
                attention_mask.data(),
                attention_mask.size(),
                shape.data(),
                shape.size()
            );

            std::array<Ort::Value, 2> ort_inputs = {
                std::move(input_ids_tensor),
                std::move(mask_tensor),
            };
            Ort::IoBinding binding(*onnx_->session);
            binding.BindInput(input_names[0], ort_inputs[0]);
            binding.BindInput(input_names[1], ort_inputs[1]);
            binding.BindOutput(output_names[0], mem_info);
            onnx_->session->Run(Ort::RunOptions{nullptr}, binding);
            binding.SynchronizeOutputs();
            auto outputs = binding.GetOutputValues();

            if (outputs.empty() || !outputs[0].IsTensor()) {
                return {"", "onnx_invalid_output"};
            }

            Ort::TypeInfo type_info = outputs[0].GetTypeInfo();
            auto tensor_info = type_info.GetTensorTypeAndShapeInfo();
            if (tensor_info.GetElementType() != ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT) {
                return {"", "onnx_output_not_float32"};
            }

            const float* audio = outputs[0].GetTensorData<float>();
            const std::size_t count = tensor_info.GetElementCount();
            if (!audio || count == 0) {
                return {"", "onnx_empty_audio"};
            }

            std::vector<float> pcm(audio, audio + count);
            return {pcm_f32_to_wav(pcm, cfg_.onnx_sample_rate), ""};
        } catch (const std::exception& e) {
            return {"", std::string("onnx_inference_error: ") + e.what()};
        }
    }
#endif

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

    std::pair<std::string, std::string> synthesize(
        const std::string& text,
        const std::string& language,
        const std::vector<std::int64_t>& token_ids,
        const std::vector<std::int64_t>& attention_mask,
        bool has_token_tensors
    ) {
        if (kSupportedLanguages.find(language) == kSupportedLanguages.end()) {
            return {"", "unsupported_language"};
        }

        if (cfg_.use_onnx) {
#ifdef TTS_ENGINE_ENABLE_ONNX
            if (!has_token_tensors) {
                return {"", "missing_hf_tokenizer_inputs"};
            }
            if (token_ids.size() > kMaxOnnxTokenLength) {
                return {"", "input_too_long"};
            }
            std::size_t start = 0;
            if (token_ids.size() > kOnnxTokenWindow) {
                start = token_ids.size() - kOnnxTokenWindow;
            }
            std::vector<std::int64_t> window_ids(token_ids.begin() + static_cast<std::ptrdiff_t>(start), token_ids.end());
            std::vector<std::int64_t> window_mask(attention_mask.begin() + static_cast<std::ptrdiff_t>(start), attention_mask.end());
            return synthesize_onnx(window_ids, window_mask);
#else
            return {"", "onnx_backend_not_compiled"};
#endif
        }
        if (cfg_.use_local_model) {
            return {"", "local_non_onnx_tts_not_implemented"};
        }

        const std::string clean_text = truncate_text(trim(text), cfg_.max_input_chars);
        if (clean_text.empty()) {
            return {"", "empty_text"};
        }

        std::string payload;
        payload.reserve(256 + clean_text.size());
        payload += "{";
        payload += "\"model\":\"" + json_escape(cfg_.model_id) + "\",";
        payload += "\"input\":\"" + json_escape(clean_text) + "\",";
        payload += "\"voice\":\"" + json_escape(cfg_.default_voice) + "\",";
        payload += "\"language\":\"" + json_escape(language) + "\",";
        payload += "\"response_format\":\"wav\"";
        payload += "}";

        const std::string url = cfg_.api_base_url + "/audio/speech";
        return http_post_binary_audio(url, payload, cfg_.api_key, cfg_.timeout_seconds);
    }

    void process_request(const Request& req) {
        const auto start = std::chrono::steady_clock::now();

        if (req.cmd == "warm_up") {
            if (cfg_.use_onnx && !req.has_token_tensors) {
                #ifdef TTS_ENGINE_ENABLE_ONNX
                static const std::vector<std::int64_t> warm_ids = {1, 2, 3};
                static const std::vector<std::int64_t> warm_mask = {1, 1, 1};
                auto warm = synthesize_onnx(warm_ids, warm_mask);
                const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                    std::chrono::steady_clock::now() - start).count();
                if (!warm.second.empty()) {
                    emit_json_line(req.id, "error", "hi", "", ms, warm.second.substr(0, 256), "warm_up_failed");
                } else {
                    emit_json_line(req.id, "ok", "hi", base64_encode_bytes(warm.first), ms, "", "");
                }
                return;
                #else
                const auto ms = std::chrono::duration_cast<std::chrono::milliseconds>(
                    std::chrono::steady_clock::now() - start).count();
                emit_json_line(req.id, "ok", "hi", "", ms, "", "");
                return;
                #endif
            }
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
                emit_json_line(req.id, "error", req.language, "", ms, result.second.substr(0, 256), "synthesis_failed");
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
#ifdef TTS_ENGINE_ENABLE_ONNX
    std::unique_ptr<OnnxRuntimeState> onnx_;
#endif
};

EngineConfig parse_daemon_config(int argc, char* argv[]) {
    EngineConfig cfg;
    // daemon api_base model voice timeout queue workers max_input api_key_or_dash [onnx_threads] [onnx_sample_rate]
    cfg.api_base_url = (argc > 2) ? argv[2] : "";
    cfg.model_id = (argc > 3) ? argv[3] : "";
    cfg.default_voice = (argc > 4) ? argv[4] : "anushka";
    cfg.timeout_seconds = (argc > 5) ? std::atoi(argv[5]) : 90;
    cfg.queue_size = (argc > 6) ? std::atoi(argv[6]) : 128;
    cfg.worker_count = (argc > 7) ? std::atoi(argv[7]) : 2;
    cfg.max_input_chars = (argc > 8) ? std::atoi(argv[8]) : 1200;
    cfg.api_key = (argc > 9) ? argv[9] : "-";
    cfg.onnx_threads = (argc > 10) ? std::max(1, std::atoi(argv[10])) : 1;
    cfg.onnx_sample_rate = (argc > 11) ? std::max(8000, std::atoi(argv[11])) : 24000;
    cfg.use_local_model = fs::exists(cfg.model_id);
    cfg.use_onnx = cfg.use_local_model && ends_with(to_lower(trim(cfg.model_id)), ".onnx");
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
        if (!cfg.use_onnx && !cfg.use_local_model && cfg.api_base_url.empty()) {
            std::cerr << "missing_api_url_for_http_mode\n";
            return 2;
        }
        TTSDaemon daemon(std::move(cfg));
        return daemon.run();
    }
    if (mode == "validate") {
        if (argc < 4) {
            std::cerr << "Usage: tts_engine validate <api_base_url_or_dash> <model_id_or_onnx_path>\n";
            return 2;
        }
        const std::string api_base = argv[2];
        const std::string model_id = argv[3];
        if (trim(model_id).empty()) {
            std::cerr << "invalid_configuration\n";
            return 2;
        }
        const bool is_local_model = fs::exists(model_id);
        const bool is_local_onnx = is_local_model && ends_with(to_lower(trim(model_id)), ".onnx");
        if (is_local_model) {
            if (is_local_onnx) {
                if (!fs::exists(model_id)) {
                    std::cerr << "onnx_model_not_found\n";
                    return 2;
                }
            }
        } else if (trim(api_base).empty() || api_base == "-") {
            std::cerr << "invalid_api_base_for_http_mode\n";
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
