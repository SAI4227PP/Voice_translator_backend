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
	SvaraAPIBaseURL      string
	SvaraModelID         string
	SvaraOnnxModelPath   string
	SvaraDefaultVoice    string
	SvaraTimeoutSeconds  int
	SvaraDaemonQueueSize int
	SvaraDaemonWorkers   int
	SvaraMaxInputChars   int
	SvaraAPIKey          string
	SvaraOnnxThreads     int
	SvaraOnnxSampleRate  int
	SvaraThreads         int
	SvaraContextSize     int
	SvaraPinWorkers      bool
}
