package config

import (
	"os"
	"strconv"
	"strings"
)

type Settings struct {
	Host        string
	Port        int
	Workers     int
	Environment string
	Debug       bool
	LogLevel    string
	LogFile     string

	AudioSampleRate int
	AudioChannels   int
	AudioChunkSize  int
	AudioFormat     string

	MaxConnections       int
	MaxConnectionsPerIP  int
	MaxUsersPerRoom      int
	MaxMessageSize       int
	IdleTimeout          int
	RoomTimeout          int
	MaxMessagesPerSecond int
	MaxRequestsPerMinute int
	RateLimitPerMinute   int

	WorkerThreads      int
	QueueSize          int
	TranslationWorkers int
	TTSWorkers         int

	STTEngine         string
	TranslationEngine string
	TTSEngine         string

	VoskModelBasePath  string
	VoskModelPathEn    string
	VoskModelPathHi    string
	VoskModelPathTe    string
	VoskModelPathGu    string
	VoskModelPathBn    string
	SarvamModelPath    string
	SarvamCppBinary    string
	LlamaCppPath       string
	LlamaCliPath       string
	SarvamMaxTokens    int
	SarvamContextSize  int
	SarvamThreads      int
	SarvamTimeout      int
	SarvamMaxConcurrentProcesses int
	SarvamWorkers      int
	SarvamQueueSize    int
	SarvamMaxInputChar int
	SarvamGpuLayers    int
	LlamaServerPort    int

	TranslationRetryCount        int
	TranslationRetryBackoffMs    int
	TranslationBreakerThreshold  int
	TranslationBreakerResetSecs  int
	TranslationEnableWarmStart   bool
	TranslationWarmStartMode     string
	TranslationCommonPairs       string
	TranslationCommonPairsParsed [][2]string

	SvaraModelID          string
	SvaraAPIBaseURL       string
	SvaraAPIKey           string
	SvaraTimeoutSeconds   int
	SvaraMaxInputChars    int
	SvaraDefaultVoice     string
	SvaraCppBinaryPath    string
	SvaraDaemonWorkers    int
	SvaraDaemonQueueSize  int
	SvaraOnnxModelPath    string
	SvaraTokenizerID      string
	SvaraOnnxThreads      int
	SvaraOnnxSampleRate   int
	TTSEnableWarmStart    bool
	TTSPreloadLanguages   string
	TTSPreloadLangsParsed []string
	STTEnableWarmStart    bool
	STTPreloadLanguages   string
	STTPreloadLangsParsed []string

	EnableAuth    bool
	JWTSecretKey  string
	JWTAlgorithm  string
	JWTExpiration int
	APIKeys       []string
	EnableMetrics bool
	MetricsPort   int
	EnableGPU     bool

	CORSOrigins string
	DatabaseURL string
	RedisURL    string

	WSPingInterval int
	WSPingTimeout  int
	GRPCEnabled    bool
	GRPCPort       int
}

func LoadSettings() Settings {
	s := Settings{
		Host:        env("HOST", "0.0.0.0"),
		Port:        envInt("PORT", 8000),
		Workers:     envInt("WORKERS", 4),
		Environment: env("ENVIRONMENT", "development"),
		Debug:       envBool("DEBUG", false),
		LogLevel:    env("LOG_LEVEL", "INFO"),
		LogFile:     env("LOG_FILE", "logs/app.log"),

		AudioSampleRate: envInt("AUDIO_SAMPLE_RATE", 16000),
		AudioChannels:   envInt("AUDIO_CHANNELS", 1),
		AudioChunkSize:  envInt("AUDIO_CHUNK_SIZE", 4096),
		AudioFormat:     env("AUDIO_FORMAT", "PCM16"),

		MaxConnections:       envInt("MAX_CONNECTIONS", 100),
		MaxConnectionsPerIP:  envInt("MAX_CONNECTIONS_PER_IP", 10),
		MaxUsersPerRoom:      envInt("MAX_USERS_PER_ROOM", 10),
		MaxMessageSize:       envInt("MAX_MESSAGE_SIZE", 10485760),
		IdleTimeout:          envInt("IDLE_TIMEOUT", 300),
		RoomTimeout:          envInt("ROOM_TIMEOUT", 3600),
		MaxMessagesPerSecond: envInt("MAX_MESSAGES_PER_SECOND", 10),
		MaxRequestsPerMinute: envInt("MAX_REQUESTS_PER_MINUTE", 100),
		RateLimitPerMinute:   envInt("RATE_LIMIT_PER_MINUTE", 60),

		WorkerThreads:      envInt("WORKER_THREADS", 2),
		QueueSize:          envInt("QUEUE_SIZE", 100),
		TranslationWorkers: envInt("TRANSLATION_WORKERS", 4),
		TTSWorkers:         envInt("TTS_WORKERS", 2),

		STTEngine:         env("STT_ENGINE", "vosk"),
		TranslationEngine: env("TRANSLATION_ENGINE", "sarvam"),
		TTSEngine:         env("TTS_ENGINE", "svara"),

		VoskModelBasePath: env("VOSK_MODEL_BASE_PATH", "models/stt"),
		VoskModelPathEn:   env("VOSK_MODEL_PATH_EN", "models/stt/vosk-en"),
		VoskModelPathHi:   env("VOSK_MODEL_PATH_HI", "models/stt/vosk-hi"),
		VoskModelPathTe:   env("VOSK_MODEL_PATH_TE", "models/stt/vosk-te"),
		VoskModelPathGu:   env("VOSK_MODEL_PATH_GU", "models/stt/vosk-gu"),
		VoskModelPathBn:   env("VOSK_MODEL_PATH_BN", "models/stt/vosk-bn"),
		SarvamModelPath:   env("SARVAM_MODEL_PATH", "/app/llm-models/sarvam-1-q4.gguf"),
		SarvamCppBinary:   env("SARVAM_CPP_BINARY_PATH", "/app/app/pipeline/translate/translate_engine"),
		LlamaCppPath:      env("LLAMA_CPP_PATH", "/app/llama.cpp"),
		LlamaCliPath:      env("LLAMA_CLI_PATH", ""),
		SarvamMaxTokens:   envInt("SARVAM_MAX_TOKENS", 256),
		SarvamContextSize: envInt("SARVAM_CONTEXT_SIZE", 2048),
		SarvamThreads:     envInt("SARVAM_THREADS", 4),
		SarvamTimeout:     envInt("SARVAM_TIMEOUT_SECONDS", 120),
		SarvamMaxConcurrentProcesses: envInt("SARVAM_MAX_CONCURRENT_PROCESSES", 1),
		SarvamWorkers:     envInt("SARVAM_DAEMON_WORKERS", 2),
		SarvamQueueSize:   envInt("SARVAM_DAEMON_QUEUE_SIZE", 256),
		SarvamMaxInputChar: envInt("SARVAM_MAX_INPUT_CHARS", 4000),
		SarvamGpuLayers:    envInt("SARVAM_GPU_LAYERS", 0),
		LlamaServerPort:    envInt("LLAMA_SERVER_PORT", 8089),

		TranslationRetryCount:       envInt("TRANSLATION_RETRY_COUNT", 2),
		TranslationRetryBackoffMs:   envInt("TRANSLATION_RETRY_BACKOFF_MS", 250),
		TranslationBreakerThreshold: envInt("TRANSLATION_CIRCUIT_BREAKER_THRESHOLD", 5),
		TranslationBreakerResetSecs: envInt("TRANSLATION_CIRCUIT_BREAKER_RESET_SECONDS", 30),
		TranslationEnableWarmStart:  envBool("TRANSLATION_ENABLE_WARM_START", true),
		TranslationWarmStartMode:    env("TRANSLATION_WARM_START_MODE", "common"),
		TranslationCommonPairs:      env("TRANSLATION_COMMON_PAIRS", "en-hi,hi-en,en-bn,bn-en"),

		SvaraModelID:         env("SVARA_TTS_MODEL_ID", "kenpath/svara-tts-v1"),
		SvaraAPIBaseURL:      env("SVARA_TTS_API_BASE_URL", ""),
		SvaraAPIKey:          env("SVARA_TTS_API_KEY", ""),
		SvaraTimeoutSeconds:  envInt("SVARA_TTS_TIMEOUT_SECONDS", 90),
		SvaraMaxInputChars:   envInt("SVARA_TTS_MAX_INPUT_CHARS", 1200),
		SvaraDefaultVoice:    env("SVARA_TTS_DEFAULT_VOICE", "anushka"),
		SvaraCppBinaryPath:   env("SVARA_TTS_CPP_BINARY_PATH", "/app/app/pipeline/tts/tts_engine"),
		SvaraDaemonWorkers:   envInt("SVARA_TTS_DAEMON_WORKERS", envInt("TTS_DAEMON_WORKERS", 2)),
		SvaraDaemonQueueSize: envInt("SVARA_TTS_DAEMON_QUEUE_SIZE", 128),
		SvaraOnnxModelPath:   env("SVARA_TTS_ONNX_MODEL_PATH", "models/tts/svara/svara_tts.onnx"),
		SvaraTokenizerID:     env("SVARA_TTS_TOKENIZER_ID", "kenpath/svara-tts-v1"),
		SvaraOnnxThreads:     envInt("SVARA_TTS_ONNX_THREADS", envInt("ONNX_THREADS", 1)),
		SvaraOnnxSampleRate:  envInt("SVARA_TTS_ONNX_SAMPLE_RATE", envInt("ONNX_SAMPLE_RATE", 24000)),
		TTSEnableWarmStart:   envBool("TTS_ENABLE_WARM_START", true),
		TTSPreloadLanguages:  env("TTS_PRELOAD_LANGUAGES", "en,hi,ta,bn"),
		STTEnableWarmStart:   envBool("STT_ENABLE_WARM_START", true),
		STTPreloadLanguages:  env("STT_PRELOAD_LANGUAGES", "en,hi"),

		EnableAuth:    envBool("ENABLE_AUTH", false),
		JWTSecretKey:  env("JWT_SECRET_KEY", "your-secret-key-change-in-production"),
		JWTAlgorithm:  env("JWT_ALGORITHM", "HS256"),
		JWTExpiration: envInt("JWT_EXPIRATION", 3600),
		APIKeys:       splitCSV(env("API_KEYS", "")),
		EnableMetrics: envBool("ENABLE_METRICS", true),
		MetricsPort:   envInt("METRICS_PORT", 9090),
		EnableGPU:     envBool("ENABLE_GPU", false),
		CORSOrigins:   env("CORS_ORIGINS", "*"),
		DatabaseURL:   env("DATABASE_URL", ""),
		RedisURL:      env("REDIS_URL", ""),

		WSPingInterval: envInt("WS_PING_INTERVAL", 30),
		WSPingTimeout:  envInt("WS_PING_TIMEOUT", 10),
		GRPCEnabled:    envBool("GRPC_ENABLED", false),
		GRPCPort:       envInt("GRPC_PORT", 50051),
	}

	s.TTSPreloadLangsParsed = splitCSV(s.TTSPreloadLanguages)
	s.STTPreloadLangsParsed = splitCSV(s.STTPreloadLanguages)
	s.TranslationCommonPairsParsed = parsePairs(s.TranslationCommonPairs)
	return s
}

func splitCSV(v string) []string {
	if strings.TrimSpace(v) == "" {
		return []string{}
	}
	parts := strings.Split(v, ",")
	out := make([]string, 0, len(parts))
	for _, p := range parts {
		item := strings.TrimSpace(p)
		if item != "" {
			out = append(out, item)
		}
	}
	return out
}

func (s Settings) IsDevelopment() bool {
	env := strings.ToLower(strings.TrimSpace(s.Environment))
	return env == "development" || env == "dev"
}

func (s Settings) IsProduction() bool {
	env := strings.ToLower(strings.TrimSpace(s.Environment))
	return env == "production" || env == "prod"
}

func (s Settings) CORSOriginsList() []string {
	if strings.TrimSpace(s.CORSOrigins) == "*" {
		return []string{"*"}
	}
	return splitCSV(s.CORSOrigins)
}

func (s Settings) GetVoskModelPath(language string) string {
	switch strings.ToLower(strings.TrimSpace(language)) {
	case "en":
		return s.VoskModelPathEn
	case "hi":
		return s.VoskModelPathHi
	case "te":
		return s.VoskModelPathTe
	case "gu":
		return s.VoskModelPathGu
	case "bn":
		return s.VoskModelPathBn
	default:
		return s.VoskModelPathEn
	}
}

func parsePairs(v string) [][2]string {
	parts := splitCSV(v)
	out := make([][2]string, 0, len(parts))
	for _, p := range parts {
		tokens := strings.SplitN(p, "-", 2)
		if len(tokens) != 2 {
			continue
		}
		src := strings.TrimSpace(tokens[0])
		tgt := strings.TrimSpace(tokens[1])
		if src != "" && tgt != "" {
			out = append(out, [2]string{src, tgt})
		}
	}
	return out
}

func env(key, fallback string) string {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	return v
}

func envInt(key string, fallback int) int {
	v := strings.TrimSpace(os.Getenv(key))
	if v == "" {
		return fallback
	}
	n, err := strconv.Atoi(v)
	if err != nil {
		return fallback
	}
	return n
}

func envBool(key string, fallback bool) bool {
	v := strings.TrimSpace(strings.ToLower(os.Getenv(key)))
	if v == "" {
		return fallback
	}
	switch v {
	case "1", "true", "yes", "on":
		return true
	case "0", "false", "no", "off":
		return false
	default:
		return fallback
	}
}
