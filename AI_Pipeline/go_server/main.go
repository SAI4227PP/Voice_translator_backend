package main

import (
	"encoding/base64"
	"encoding/json"
	"io"
	"log"
	"mime/multipart"
	"net/http"
	"strconv"
	"strings"
	"sync"
	"time"

	"voice_translator_go_server/app/config"
	"voice_translator_go_server/app/messaging"
	"voice_translator_go_server/app/rooms"
	utils "voice_translator_go_server/app/utils"
	workers "voice_translator_go_server/app/workers"
	"voice_translator_go_server/grpcserver"
	"voice_translator_go_server/server"

	"github.com/gorilla/websocket"
)

type TranslateRequest struct {
	Text           string `json:"text"`
	SourceLanguage string `json:"source_language"`
	TargetLanguage string `json:"target_language"`
}

type BatchTranslateRequest struct {
	Texts          []string `json:"texts"`
	SourceLanguage string   `json:"source_language"`
	TargetLanguage string   `json:"target_language"`
}

type TTSRequest struct {
	Text     string `json:"text"`
	Language string `json:"language"`
	Format   string `json:"format"`
}

type TranslateTTSRequest struct {
	Text           string `json:"text"`
	SourceLanguage string `json:"source_language"`
	TargetLanguage string `json:"target_language"`
	Mode           string `json:"mode"`
	StreamID       string `json:"stream_id"`
	Format         string `json:"format"`
}

type STTRequest struct {
	AudioData        string `json:"audio_data"`
	Language         string `json:"language"`
	SampleRate       int    `json:"sample_rate"`
	ReturnConfidence bool   `json:"return_confidence"`
}

type BatchSTTRequest struct {
	AudioFiles       []string `json:"audio_files"`
	Language         string   `json:"language"`
	SampleRate       int      `json:"sample_rate"`
	ReturnConfidence bool     `json:"return_confidence"`
}

type appState struct {
	settings   config.Settings
	scanner    utils.Scanner
	roomMgr    *rooms.Manager
	translator *workers.SarvamTranslator
	tts        *workers.SvaraTTS
	stt        *workers.PythonSTTBridge
	chunkBuf   map[string]string
	chunkMu    sync.Mutex
}

var upgrader = websocket.Upgrader{
	CheckOrigin: func(r *http.Request) bool { return true },
}

func main() {
	settings := config.LoadSettings()
	config.SetupLogging(settings)
	workerSettings := toWorkerSettings(settings)
	server.ConfigureHeartbeat(settings.WSPingInterval, settings.WSPingTimeout)

	state := &appState{
		settings:   settings,
		scanner:    utils.NewScanner(settings),
		roomMgr:    rooms.NewManager(settings.MaxUsersPerRoom),
		translator: workers.NewSarvamTranslator(workerSettings),
		tts:        workers.NewSvaraTTS(workerSettings),
		stt:        workers.NewPythonSTTBridge(),
		chunkBuf:   map[string]string{},
	}
	server.SetMessageRouter(messaging.NewMessageRouter(state.roomMgr, server.GetConnectionManager()))

	warmStart(state)
	defer state.translator.Close()
	defer state.tts.Close()

	if settings.GRPCEnabled {
		grpcAddr := settings.Host + ":" + strconv.Itoa(settings.GRPCPort)
		stopGRPC, err := grpcserver.Start(grpcAddr, grpcserver.Dependencies{
			Settings:   settings,
			Scanner:    state.scanner,
			Translator: state.translator,
			TTS:        state.tts,
			STT:        state.stt,
		})
		if err != nil {
			log.Printf("grpc_server_start_failed addr=%s error=%v", grpcAddr, err)
		} else {
			defer stopGRPC()
		}
	}

	mux := http.NewServeMux()
	mux.HandleFunc("/", state.rootHandler)
	mux.HandleFunc("/health", state.healthHandler)
	mux.HandleFunc("/stats", state.statsHandler)
	mux.HandleFunc("/config", state.configHandler)
	mux.HandleFunc("/languages/supported", state.supportedLanguagesHandler)
	mux.HandleFunc("/languages/pairs", state.translationPairsHandler)
	mux.HandleFunc("/translate", state.translateHandler)
	mux.HandleFunc("/translate/batch", state.batchTranslateHandler)
	mux.HandleFunc("/tts/generate", state.ttsGenerateHandler)
	mux.HandleFunc("/translate-tts", state.translateTTSHandler)
	mux.HandleFunc("/stt/transcribe", state.sttTranscribeHandler)
	mux.HandleFunc("/stt/transcribe-file", state.sttTranscribeFileHandler)
	mux.HandleFunc("/stt/transcribe-batch", state.sttTranscribeBatchHandler)
	mux.HandleFunc("/ws", wsHandler)

	addr := settings.Host + ":" + strconv.Itoa(settings.Port)
	log.Printf("starting_go_server host=%s port=%d env=%s", settings.Host, settings.Port, settings.Environment)
	if err := http.ListenAndServe(addr, withCORS(settings, mux)); err != nil {
		log.Fatal(err)
	}
}

func warmStart(state *appState) {
	if state.settings.TranslationEnableWarmStart {
		if strings.EqualFold(state.settings.TranslationWarmStartMode, "all") {
			state.translator.WarmUp()
		} else {
			state.translator.WarmUpCommonPairs(state.settings.TranslationCommonPairsParsed)
		}
	}
	if state.settings.TTSEnableWarmStart {
		state.tts.WarmUp(state.settings.TTSPreloadLangsParsed)
	}
	if state.settings.STTEnableWarmStart {
		state.stt.WarmUp(state.settings.STTPreloadLangsParsed)
	}
}

func withCORS(settings config.Settings, next http.Handler) http.Handler {
	origins := strings.TrimSpace(settings.CORSOrigins)
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if origins == "" || origins == "*" {
			w.Header().Set("Access-Control-Allow-Origin", "*")
		} else {
			w.Header().Set("Access-Control-Allow-Origin", origins)
		}
		w.Header().Set("Access-Control-Allow-Credentials", "true")
		w.Header().Set("Access-Control-Allow-Methods", "*")
		w.Header().Set("Access-Control-Allow-Headers", "*")
		if r.Method == http.MethodOptions {
			w.WriteHeader(http.StatusNoContent)
			return
		}
		next.ServeHTTP(w, r)
	})
}

func wsHandler(w http.ResponseWriter, r *http.Request) {
	conn, err := upgrader.Upgrade(w, r, nil)
	if err != nil {
		http.Error(w, "websocket upgrade failed", http.StatusBadRequest)
		return
	}
	server.GetWebSocketServer().HandleConnection(conn)
}

func (a *appState) rootHandler(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"service": "Voice-to-Voice Translator",
		"version": "1.0.0",
		"status":  "running",
	})
}

func (a *appState) healthHandler(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	conn := server.GetConnectionManager()
	writeJSON(w, http.StatusOK, map[string]any{
		"status":      "healthy",
		"connections": conn.GetConnectionCount(),
		"rooms":       a.roomMgr.GetRoomCount(),
		"total_users": a.roomMgr.GetTotalUsers(),
	})
}

func (a *appState) statsHandler(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	conn := server.GetConnectionManager()
	writeJSON(w, http.StatusOK, map[string]any{
		"server": map[string]any{
			"version":     "1.0.0",
			"environment": a.settings.Environment,
		},
		"connections": map[string]any{
			"total":  conn.GetConnectionCount(),
			"active": conn.GetConnectionCount(),
		},
		"rooms": map[string]any{
			"total":  a.roomMgr.GetRoomCount(),
			"active": a.roomMgr.GetRoomCount(),
		},
		"workers": map[string]any{
			"translation": map[string]any{"total": a.settings.TranslationWorkers, "busy": 0, "queue_size": 0},
			"tts":         map[string]any{"total": a.settings.TTSWorkers, "busy": 0, "queue_size": 0},
		},
	})
}

func (a *appState) configHandler(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	sttLangs := a.scanner.GetAvailableSTTLanguages()
	translationLangs := a.scanner.GetAvailableTranslationLanguages()
	ttsLangs := a.scanner.GetAvailableTTSLanguages()

	supported := map[string]string{}
	for code, info := range sttLangs {
		supported[code] = info["name"]
	}
	for code, info := range translationLangs {
		if _, ok := supported[code]; !ok {
			supported[code] = info["name"]
		}
	}
	for code, raw := range ttsLangs {
		if code == "multilingual" {
			continue
		}
		if _, ok := supported[code]; ok {
			continue
		}
		if name, ok := raw["name"].(string); ok {
			supported[code] = name
		}
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"audio": map[string]any{
			"sample_rate": a.settings.AudioSampleRate,
			"channels":    a.settings.AudioChannels,
			"chunk_size":  a.settings.AudioChunkSize,
			"format":      a.settings.AudioFormat,
		},
		"limits": map[string]any{
			"max_connections":        a.settings.MaxConnections,
			"max_connections_per_ip": a.settings.MaxConnectionsPerIP,
			"max_users_per_room":     a.settings.MaxUsersPerRoom,
			"max_message_size":       a.settings.MaxMessageSize,
			"idle_timeout":           a.settings.IdleTimeout,
			"room_timeout":           a.settings.RoomTimeout,
		},
		"rate_limits": map[string]any{
			"messages_per_second":   a.settings.MaxMessagesPerSecond,
			"requests_per_minute":   a.settings.MaxRequestsPerMinute,
			"rate_limit_per_minute": a.settings.RateLimitPerMinute,
		},
		"workers": map[string]any{
			"translation_workers": a.settings.TranslationWorkers,
			"tts_workers":         a.settings.TTSWorkers,
			"worker_threads":      a.settings.WorkerThreads,
			"queue_size":          a.settings.QueueSize,
		},
		"models": map[string]any{
			"stt_engine":            a.settings.STTEngine,
			"translation_engine":    a.settings.TranslationEngine,
			"tts_engine":            a.settings.TTSEngine,
			"vosk_model_base_path":  a.settings.VoskModelBasePath,
			"svara_tts_model_id":    a.settings.SvaraModelID,
			"svara_tts_api_base_url": a.settings.SvaraAPIBaseURL,
			"available_models": map[string]any{
				"stt":         sttLangs,
				"translation": translationLangs,
				"tts":         ttsLangs,
			},
			"supported_languages": supported,
		},
		"features": map[string]any{
			"authentication_enabled": a.settings.EnableAuth,
			"rate_limiting_enabled":  true,
			"metrics_enabled":        a.settings.EnableMetrics,
			"gpu_enabled":            a.settings.EnableGPU,
		},
		"websocket": map[string]any{
			"ping_interval": a.settings.WSPingInterval,
			"ping_timeout":  a.settings.WSPingTimeout,
		},
		"environment": map[string]any{
			"env":          a.settings.Environment,
			"debug":        a.settings.Debug,
			"host":         a.settings.Host,
			"port":         a.settings.Port,
			"cors_origins": a.settings.CORSOrigins,
		},
	})
}

func (a *appState) supportedLanguagesHandler(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"stt":         a.scanner.GetAvailableSTTLanguages(),
		"translation": a.scanner.GetAvailableTranslationLanguages(),
		"tts":         a.scanner.GetAvailableTTSLanguages(),
	})
}

func (a *appState) translationPairsHandler(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodGet) {
		return
	}
	pairs := a.scanner.GetTranslationPairs()
	writeJSON(w, http.StatusOK, map[string]any{
		"pairs": pairs,
		"count": len(pairs),
	})
}

func (a *appState) translateHandler(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) {
		return
	}
	var req TranslateRequest
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	langs := a.scanner.GetAvailableTranslationLanguages()
	if _, ok := langs[req.SourceLanguage]; !ok {
		writeLangError(w, http.StatusUnprocessableEntity, "Source language '"+req.SourceLanguage+"' is not supported", keysStringMap(langs), "Check /languages/supported for available languages")
		return
	}
	if _, ok := langs[req.TargetLanguage]; !ok {
		writeLangError(w, http.StatusUnprocessableEntity, "Target language '"+req.TargetLanguage+"' is not supported", keysStringMap(langs), "Check /languages/supported for available languages")
		return
	}

	start := time.Now()
	out, err := a.translator.Translate(req.Text, req.SourceLanguage, req.TargetLanguage)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Translation failed: "+err.Error())
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"original_text":      req.Text,
		"translated_text":    out,
		"source_language":    req.SourceLanguage,
		"target_language":    req.TargetLanguage,
		"processing_time_ms": roundMs(start),
	})
}

func (a *appState) batchTranslateHandler(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) {
		return
	}
	var req BatchTranslateRequest
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	langs := a.scanner.GetAvailableTranslationLanguages()
	if _, ok := langs[req.SourceLanguage]; !ok {
		writeLangError(w, http.StatusUnprocessableEntity, "Source language '"+req.SourceLanguage+"' is not available", keysStringMap(langs), "Check /languages/supported for available languages")
		return
	}
	if _, ok := langs[req.TargetLanguage]; !ok {
		writeLangError(w, http.StatusUnprocessableEntity, "Target language '"+req.TargetLanguage+"' is not supported", keysStringMap(langs), "Check /languages/supported for available languages")
		return
	}

	start := time.Now()
	translations, err := a.translator.BatchTranslate(req.Texts, req.SourceLanguage, req.TargetLanguage)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Batch translation failed: "+err.Error())
		return
	}
	out := make([]map[string]string, 0, len(req.Texts))
	for i, src := range req.Texts {
		tr := ""
		if i < len(translations) {
			tr = translations[i]
		}
		out = append(out, map[string]string{"original": src, "translated": tr})
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"translations":       out,
		"source_language":    req.SourceLanguage,
		"target_language":    req.TargetLanguage,
		"total":              len(out),
		"processing_time_ms": roundMs(start),
	})
}

func (a *appState) ttsGenerateHandler(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) {
		return
	}
	var req TTSRequest
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if req.Format == "" {
		req.Format = "wav"
	}
	if req.Format != "wav" {
		writeError(w, http.StatusBadRequest, "Invalid format '"+req.Format+"'. Supported format: 'wav'")
		return
	}
	ttsLangs := a.scanner.GetAvailableTTSLanguages()
	if _, ok := ttsLangs[req.Language]; !ok {
		writeLangError(w, http.StatusUnprocessableEntity, "Language '"+req.Language+"' is not supported for TTS", keysAnyMap(ttsLangs), "Check /languages/supported for available TTS languages")
		return
	}

	start := time.Now()
	audio, err := a.tts.Synthesize(req.Language, req.Text)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "TTS generation failed: "+err.Error())
		return
	}

	w.Header().Set("Content-Type", "audio/wav")
	w.Header().Set("Content-Disposition", `attachment; filename="tts_output.wav"`)
	w.Header().Set("X-Processing-Time-Ms", strconv.FormatFloat(roundMs(start), 'f', 2, 64))
	_, _ = w.Write(audio)
}

func (a *appState) translateTTSHandler(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) {
		return
	}
	var req TranslateTTSRequest
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if req.Format == "" {
		req.Format = "wav"
	}
	if req.Mode == "" {
		req.Mode = "full_sentence"
	}
	if req.Format != "wav" {
		writeError(w, http.StatusBadRequest, "Invalid format '"+req.Format+"'. Supported format: 'wav'")
		return
	}
	mode := strings.ToLower(strings.TrimSpace(req.Mode))
	if mode != "chunk" && mode != "full_sentence" {
		writeError(w, http.StatusBadRequest, "Invalid mode. Supported values: 'chunk', 'full_sentence'")
		return
	}
	if mode == "chunk" && strings.TrimSpace(req.StreamID) == "" {
		writeError(w, http.StatusBadRequest, "stream_id is required when mode='chunk'")
		return
	}

	translationLangs := a.scanner.GetAvailableTranslationLanguages()
	ttsLangs := a.scanner.GetAvailableTTSLanguages()
	if _, ok := translationLangs[req.SourceLanguage]; !ok {
		writeLangError(w, http.StatusUnprocessableEntity, "Source language '"+req.SourceLanguage+"' is not available for translation", keysStringMap(translationLangs), "")
		return
	}
	if _, ok := translationLangs[req.TargetLanguage]; !ok {
		writeLangError(w, http.StatusUnprocessableEntity, "Target language '"+req.TargetLanguage+"' is not available for translation", keysStringMap(translationLangs), "")
		return
	}
	if _, ok := ttsLangs[req.TargetLanguage]; !ok {
		writeLangError(w, http.StatusUnprocessableEntity, "Target language '"+req.TargetLanguage+"' is not available for TTS", keysAnyMap(ttsLangs), "")
		return
	}

	start := time.Now()
	inputText := req.Text
	if mode == "chunk" {
		inputText = a.mergeChunkContext(req.StreamID, req.Text)
	} else if strings.TrimSpace(req.StreamID) != "" {
		a.chunkMu.Lock()
		delete(a.chunkBuf, req.StreamID)
		a.chunkMu.Unlock()
	}
	translated, err := a.translator.Translate(inputText, req.SourceLanguage, req.TargetLanguage)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Translate-TTS pipeline failed: "+err.Error())
		return
	}
	audio, err := a.tts.Synthesize(req.TargetLanguage, translated)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "Translate-TTS pipeline failed: "+err.Error())
		return
	}
	if len(audio) == 0 {
		writeError(w, http.StatusUnprocessableEntity, "No audio generated for input text")
		return
	}

	w.Header().Set("Content-Type", "audio/wav")
	w.Header().Set("Content-Disposition", `attachment; filename="translate_tts_output.wav"`)
	w.Header().Set("X-Processing-Time-Ms", strconv.FormatFloat(roundMs(start), 'f', 2, 64))
	w.Header().Set("X-Pipeline-Mode", mode)
	_, _ = w.Write(audio)
}

func (a *appState) sttTranscribeHandler(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) {
		return
	}
	var req STTRequest
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	sttLangs := a.scanner.GetAvailableSTTLanguages()
	if _, ok := sttLangs[req.Language]; !ok {
		writeLangError(w, http.StatusUnprocessableEntity, "Language '"+req.Language+"' is not supported for STT", keysStringMap(sttLangs), "Check /languages/supported for available STT languages")
		return
	}
	audio, err := base64Decode(req.AudioData)
	if err != nil {
		writeError(w, http.StatusBadRequest, "Invalid base64 audio data: "+err.Error())
		return
	}
	start := time.Now()
	result, err := a.stt.Transcribe(audio, req.Language)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "STT transcription failed: "+err.Error())
		return
	}
	resp := map[string]any{
		"text":               result.Text,
		"language":           req.Language,
		"processing_time_ms": roundMs(start),
	}
	if req.ReturnConfidence {
		resp["confidence"] = result.Confidence
	}
	writeJSON(w, http.StatusOK, resp)
}

func (a *appState) sttTranscribeFileHandler(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) {
		return
	}
	file, header, err := r.FormFile("file")
	if err != nil {
		writeError(w, http.StatusBadRequest, "file is required")
		return
	}
	defer file.Close()
	language := r.FormValue("language")
	if strings.TrimSpace(language) == "" {
		language = "en"
	}
	returnConfidence := strings.EqualFold(strings.TrimSpace(r.FormValue("return_confidence")), "true")
	sttLangs := a.scanner.GetAvailableSTTLanguages()
	if _, ok := sttLangs[language]; !ok {
		writeLangError(w, http.StatusUnprocessableEntity, "Language '"+language+"' is not supported for STT", keysStringMap(sttLangs), "Check /languages/supported for available STT languages")
		return
	}
	audio, err := readAllLimited(file, 10*1024*1024+1)
	if err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	if len(audio) > 10*1024*1024 {
		writeError(w, http.StatusRequestEntityTooLarge, "File too large. Maximum size: 10485760 bytes")
		return
	}
	start := time.Now()
	result, err := a.stt.Transcribe(audio, language)
	if err != nil {
		writeError(w, http.StatusInternalServerError, "STT file transcription failed: "+err.Error())
		return
	}
	resp := map[string]any{
		"text":               result.Text,
		"language":           language,
		"file_size":          len(audio),
		"filename":           header.Filename,
		"processing_time_ms": roundMs(start),
	}
	if returnConfidence {
		resp["confidence"] = result.Confidence
	}
	writeJSON(w, http.StatusOK, resp)
}

func (a *appState) sttTranscribeBatchHandler(w http.ResponseWriter, r *http.Request) {
	if !allowMethod(w, r, http.MethodPost) {
		return
	}
	var req BatchSTTRequest
	if err := decodeJSON(r, &req); err != nil {
		writeError(w, http.StatusBadRequest, err.Error())
		return
	}
	sttLangs := a.scanner.GetAvailableSTTLanguages()
	if _, ok := sttLangs[req.Language]; !ok {
		writeLangError(w, http.StatusUnprocessableEntity, "Language '"+req.Language+"' is not supported for STT", keysStringMap(sttLangs), "Check /languages/supported for available STT languages")
		return
	}
	start := time.Now()
	items := make([]map[string]any, 0, len(req.AudioFiles))
	for idx, item := range req.AudioFiles {
		audio, err := base64Decode(item)
		if err != nil {
			items = append(items, map[string]any{"text": "", "index": idx, "error": err.Error()})
			continue
		}
		result, err := a.stt.Transcribe(audio, req.Language)
		if err != nil {
			items = append(items, map[string]any{"text": "", "index": idx, "error": err.Error()})
			continue
		}
		row := map[string]any{"text": result.Text, "index": idx}
		if req.ReturnConfidence {
			row["confidence"] = result.Confidence
		}
		items = append(items, row)
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"transcriptions":     items,
		"language":           req.Language,
		"total":              len(items),
		"processing_time_ms": roundMs(start),
	})
}

func decodeJSON(r *http.Request, out any) error {
	body, err := io.ReadAll(io.LimitReader(r.Body, 2*1024*1024))
	if err != nil {
		return err
	}
	if len(strings.TrimSpace(string(body))) == 0 {
		return io.EOF
	}
	return json.Unmarshal(body, out)
}

func allowMethod(w http.ResponseWriter, r *http.Request, method string) bool {
	if r.Method == method {
		return true
	}
	w.Header().Set("Allow", method)
	writeJSON(w, http.StatusMethodNotAllowed, map[string]any{"detail": "Method Not Allowed"})
	return false
}

func writeJSON(w http.ResponseWriter, code int, payload any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(code)
	_ = json.NewEncoder(w).Encode(payload)
}

func writeError(w http.ResponseWriter, code int, message string) {
	writeJSON(w, code, map[string]any{"detail": message})
}

func writeLangError(w http.ResponseWriter, code int, errMsg string, available []string, message string) {
	detail := map[string]any{
		"error":               errMsg,
		"available_languages": available,
	}
	if strings.TrimSpace(message) != "" {
		detail["message"] = message
	}
	writeJSON(w, code, map[string]any{"detail": detail})
}

func keysStringMap(m map[string]map[string]string) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	return out
}

func keysAnyMap(m map[string]map[string]any) []string {
	out := make([]string, 0, len(m))
	for k := range m {
		out = append(out, k)
	}
	return out
}

func roundMs(start time.Time) float64 {
	ms := float64(time.Since(start).Microseconds()) / 1000.0
	return float64(int(ms*100)) / 100
}

func (a *appState) mergeChunkContext(streamID string, rawChunk string) string {
	const maxContextChars = 600

	chunk := strings.TrimSpace(rawChunk)
	if chunk == "" {
		return ""
	}

	a.chunkMu.Lock()
	defer a.chunkMu.Unlock()

	prev := strings.TrimSpace(a.chunkBuf[streamID])
	merged := chunk
	if prev != "" {
		merged = strings.TrimSpace(prev + " " + chunk)
	}
	if len(merged) > maxContextChars {
		merged = merged[len(merged)-maxContextChars:]
	}
	a.chunkBuf[streamID] = merged
	return merged
}

func base64Decode(data string) ([]byte, error) {
	return base64.StdEncoding.DecodeString(data)
}

func readAllLimited(file multipart.File, max int64) ([]byte, error) {
	return io.ReadAll(io.LimitReader(file, max))
}

func toWorkerSettings(s config.Settings) workers.Settings {
	return workers.Settings{
		SarvamCppBinary:    s.SarvamCppBinary,
		LlamaCppPath:       s.LlamaCppPath,
		LlamaCliPath:       s.LlamaCliPath,
		SarvamModelPath:    s.SarvamModelPath,
		SarvamMaxTokens:    s.SarvamMaxTokens,
		SarvamContextSize:  s.SarvamContextSize,
		SarvamThreads:      s.SarvamThreads,
		SarvamGpuLayers:    s.SarvamGpuLayers,
		SarvamQueueSize:    s.SarvamQueueSize,
		SarvamWorkers:      s.SarvamWorkers,
		SarvamMaxInputChar: s.SarvamMaxInputChar,
		LlamaServerPort:    s.LlamaServerPort,
		SarvamTimeout:      s.SarvamTimeout,

		TranslationRetryCount:       s.TranslationRetryCount,
		TranslationRetryBackoffMs:   s.TranslationRetryBackoffMs,
		TranslationBreakerThreshold: s.TranslationBreakerThreshold,
		TranslationBreakerResetSecs: s.TranslationBreakerResetSecs,

		SvaraCppBinaryPath:   s.SvaraCppBinaryPath,
		SvaraAPIBaseURL:      s.SvaraAPIBaseURL,
		SvaraModelID:         s.SvaraModelID,
		SvaraOnnxModelPath:   s.SvaraOnnxModelPath,
		SvaraDefaultVoice:    s.SvaraDefaultVoice,
		SvaraTimeoutSeconds:  s.SvaraTimeoutSeconds,
		SvaraDaemonQueueSize: s.SvaraDaemonQueueSize,
		SvaraDaemonWorkers:   s.SvaraDaemonWorkers,
		SvaraMaxInputChars:   s.SvaraMaxInputChars,
		SvaraAPIKey:          s.SvaraAPIKey,
		SvaraOnnxThreads:     s.SvaraOnnxThreads,
		SvaraOnnxSampleRate:  s.SvaraOnnxSampleRate,
	}
}
