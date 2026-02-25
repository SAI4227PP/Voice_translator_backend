package workers

type Settings struct {
	SarvamCppBinary   string
	LlamaCppPath      string
	LlamaCliPath      string
	SarvamModelPath   string
	SarvamMaxTokens   int
	SarvamContextSize int
	SarvamThreads     int
	SarvamGpuLayers   int
	SarvamQueueSize   int
	SarvamWorkers     int
	SarvamMaxInputChar int
	LlamaServerPort    int
	SarvamTimeout      int

	TranslationRetryCount      int
	TranslationRetryBackoffMs  int
	TranslationBreakerThreshold int
	TranslationBreakerResetSecs int

	SvaraCppBinaryPath   string
	SvaraModelID         string
	SvaraDefaultVoice    string
	SvaraTimeoutSeconds  int
	SvaraDaemonQueueSize int
	SvaraDaemonWorkers   int
	SvaraMaxInputChars   int
	SvaraThreads         int
	SvaraContextSize     int
	SvaraPinWorkers      bool
	SvaraEndpointPath    string
	SvaraVocoderModel    string
}
