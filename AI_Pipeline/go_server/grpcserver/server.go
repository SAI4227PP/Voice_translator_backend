package grpcserver

import (
	"context"
	"encoding/binary"
	"io"
	"log"
	"net"
	"strings"
	"time"

	"google.golang.org/grpc"
	"google.golang.org/grpc/codes"
	"google.golang.org/grpc/status"

	"voice_translator_go_server/app/config"
	utils "voice_translator_go_server/app/utils"
	workers "voice_translator_go_server/app/workers"
	pb "voice_translator_go_server/proto"
)

type Dependencies struct {
	Settings   config.Settings
	Scanner    utils.Scanner
	Translator *workers.SarvamTranslator
	TTS        *workers.SvaraTTS
	STT        *workers.PythonSTTBridge
}

type Service struct {
	pb.UnimplementedSTTServiceServer
	pb.UnimplementedTranslationServiceServer
	pb.UnimplementedTTSServiceServer
	deps      Dependencies
	startedAt time.Time
}

func Start(address string, deps Dependencies) (func(), error) {
	lis, err := net.Listen("tcp", address)
	if err != nil {
		return nil, err
	}

	grpcSrv := grpc.NewServer()
	svc := &Service{
		deps:      deps,
		startedAt: time.Now(),
	}

	pb.RegisterSTTServiceServer(grpcSrv, svc)
	pb.RegisterTranslationServiceServer(grpcSrv, svc)
	pb.RegisterTTSServiceServer(grpcSrv, svc)

	go func() {
		log.Printf("grpc_server_started addr=%s", address)
		if serveErr := grpcSrv.Serve(lis); serveErr != nil {
			log.Printf("grpc_server_stopped error=%v", serveErr)
		}
	}()

	stopFn := func() {
		grpcSrv.GracefulStop()
		_ = lis.Close()
	}
	return stopFn, nil
}

func (s *Service) RecognizeAudio(_ context.Context, req *pb.AudioRequest) (*pb.RecognitionResponse, error) {
	if req == nil {
		return nil, status.Error(codes.InvalidArgument, "request is required")
	}
	if len(req.GetAudioData()) == 0 {
		return nil, status.Error(codes.InvalidArgument, "audio_data is required")
	}
	lang := strings.TrimSpace(req.GetLanguage())
	if lang == "" {
		return nil, status.Error(codes.InvalidArgument, "language is required")
	}
	if _, ok := s.deps.Scanner.GetAvailableSTTLanguages()[lang]; !ok {
		return nil, status.Errorf(codes.InvalidArgument, "unsupported STT language: %s", lang)
	}

	start := time.Now()
	result, err := s.deps.STT.Transcribe(req.GetAudioData(), lang)
	if err != nil {
		return nil, mapWorkerError(err)
	}
	processingMs := time.Since(start).Milliseconds()

	conf := float32(0)
	if v, ok := result.Confidence.(float64); ok {
		conf = float32(v)
	}

	return &pb.RecognitionResponse{
		Text:             result.Text,
		Confidence:       conf,
		Language:         lang,
		ProcessingTimeMs: processingMs,
	}, nil
}

func (s *Service) RecognizeStream(stream pb.STTService_RecognizeStreamServer) error {
	var buffer []byte
	var language string
	var userID string

	for {
		chunk, err := stream.Recv()
		if err == io.EOF {
			return nil
		}
		if err != nil {
			return err
		}

		language = chunk.GetLanguage()
		if strings.TrimSpace(language) == "" {
			return status.Error(codes.InvalidArgument, "language is required")
		}
		userID = chunk.GetUserId()
		buffer = append(buffer, chunk.GetAudioData()...)

		if !chunk.GetIsFinal() {
			// Best-effort rolling partial by transcribing current accumulated audio.
			partial := ""
			if len(buffer) > 0 {
				if pResult, pErr := s.deps.STT.Transcribe(buffer, language); pErr == nil {
					partial = pResult.Text
				}
			}
			if err = stream.Send(&pb.RecognitionResult{
				Text:       partial,
				IsPartial:  true,
				Confidence: 0,
				Language:   language,
				UserId:     userID,
			}); err != nil {
				return err
			}
			continue
		}

		result, tErr := s.deps.STT.Transcribe(buffer, language)
		if tErr != nil {
			return mapWorkerError(tErr)
		}
		buffer = buffer[:0]

		conf := float32(0)
		if v, ok := result.Confidence.(float64); ok {
			conf = float32(v)
		}

		if err = stream.Send(&pb.RecognitionResult{
			Text:       result.Text,
			IsPartial:  false,
			Confidence: conf,
			Language:   language,
			UserId:     userID,
		}); err != nil {
			return err
		}
	}
}

func (s *Service) Translate(_ context.Context, req *pb.TranslationRequest) (*pb.TranslationResponse, error) {
	if err := s.validateTranslationRequest(req); err != nil {
		return nil, err
	}

	source := strings.TrimSpace(req.GetSourceLang())
	target := strings.TrimSpace(req.GetTargetLang())
	if strings.EqualFold(source, target) {
		return &pb.TranslationResponse{
			OriginalText:     req.GetText(),
			TranslatedText:   req.GetText(),
			SourceLang:       source,
			TargetLang:       target,
			Confidence:       1,
			ProcessingTimeMs: 0,
			TaskId:           req.GetTaskId(),
		}, nil
	}

	start := time.Now()
	translated, err := s.deps.Translator.Translate(req.GetText(), source, target)
	if err != nil {
		return nil, mapWorkerError(err)
	}
	return &pb.TranslationResponse{
		OriginalText:     req.GetText(),
		TranslatedText:   translated,
		SourceLang:       source,
		TargetLang:       target,
		Confidence:       0,
		ProcessingTimeMs: time.Since(start).Milliseconds(),
		TaskId:           req.GetTaskId(),
	}, nil
}

func (s *Service) TranslateStream(stream pb.TranslationService_TranslateStreamServer) error {
	for {
		req, err := stream.Recv()
		if err == io.EOF {
			return nil
		}
		if err != nil {
			return err
		}

		resp, tErr := s.Translate(nil, req)
		if tErr != nil {
			return tErr
		}
		if err = stream.Send(resp); err != nil {
			return err
		}
	}
}

func (s *Service) GetSupportedLanguages(_ context.Context, _ *pb.LanguageRequest) (*pb.LanguageResponse, error) {
	pairs := s.deps.Scanner.GetTranslationPairs()
	out := make([]*pb.LanguagePair, 0, len(pairs))
	for _, p := range pairs {
		out = append(out, &pb.LanguagePair{
			SourceLang: p["from"],
			TargetLang: p["to"],
		})
	}
	return &pb.LanguageResponse{SupportedPairs: out}, nil
}

func (s *Service) Synthesize(_ context.Context, req *pb.TTSRequest) (*pb.TTSResponse, error) {
	if err := s.validateTTSRequest(req); err != nil {
		return nil, err
	}

	start := time.Now()
	audio, err := s.deps.TTS.Synthesize(req.GetLanguage(), req.GetText())
	if err != nil {
		return nil, mapWorkerError(err)
	}

	sampleRate := req.GetSampleRate()
	audioLenMs := int32(0)
	if wavRate, wavLenMs, ok := parseWAVMetadata(audio); ok {
		sampleRate = wavRate
		audioLenMs = wavLenMs
	}

	if sampleRate <= 0 {
		sampleRate = int32(s.deps.Settings.AudioSampleRate)
	}
	if audioLenMs <= 0 && sampleRate > 0 {
		// Approximate duration for PCM16 mono bytes.
		audioLenMs = int32((len(audio) * 1000) / (2 * int(sampleRate)))
	}

	return &pb.TTSResponse{
		AudioData:         audio,
		Language:          req.GetLanguage(),
		ProcessingTimeMs:  time.Since(start).Milliseconds(),
		TaskId:            req.GetTaskId(),
		SampleRate:        sampleRate,
		AudioLengthMs:     audioLenMs,
	}, nil
}

func (s *Service) SynthesizeStream(req *pb.TTSRequest, stream pb.TTSService_SynthesizeStreamServer) error {
	resp, err := s.Synthesize(nil, req)
	if err != nil {
		return err
	}
	audio := resp.GetAudioData()
	// Use low-latency audio shards (~50ms) for smoother real-time playback.
	// PCM16 mono: bytes_per_sample = 2.
	chunkSize := 1600 // default for 16kHz, 50ms
	if sr := int(resp.GetSampleRate()); sr > 0 {
		derived := (sr * 2 * 50) / 1000
		if derived > 0 {
			chunkSize = derived
		}
	}

	for i := 0; i < len(audio); i += chunkSize {
		end := i + chunkSize
		if end > len(audio) {
			end = len(audio)
		}
		isFinal := end == len(audio)
		if sendErr := stream.Send(&pb.AudioChunk{
			AudioData:  audio[i:end],
			UserId:     req.GetUserId(),
			Language:   req.GetLanguage(),
			IsFinal:    isFinal,
			SampleRate: resp.GetSampleRate(),
		}); sendErr != nil {
			return sendErr
		}
	}
	return nil
}

func (s *Service) GetVoices(_ context.Context, req *pb.VoiceRequest) (*pb.VoiceResponse, error) {
	ttsLangs := s.deps.Scanner.GetAvailableTTSLanguages()
	out := make([]*pb.Voice, 0)

	for lang, raw := range ttsLangs {
		if req.GetLanguage() != "" && req.GetLanguage() != lang {
			continue
		}
		voicesRaw := make([]string, 0)
		switch vv := raw["voices"].(type) {
		case []string:
			voicesRaw = append(voicesRaw, vv...)
		case []interface{}:
			for _, x := range vv {
				if v, ok := x.(string); ok && v != "" {
					voicesRaw = append(voicesRaw, v)
				}
			}
		}
		if len(voicesRaw) == 0 {
			voicesRaw = []string{"anushka"}
		}
		for _, v := range voicesRaw {
			out = append(out, &pb.Voice{
				VoiceId:  v,
				Name:     v,
				Language: lang,
				Gender:   "unknown",
			})
		}
	}
	return &pb.VoiceResponse{Voices: out}, nil
}

func (s *Service) HealthCheck(_ context.Context, req *pb.HealthCheckRequest) (*pb.HealthCheckResponse, error) {
	uptime := int64(time.Since(s.startedAt).Seconds())
	requested := ""
	if req != nil {
		requested = strings.ToLower(strings.TrimSpace(req.GetService()))
	}
	services := []string{"stt", "translation", "tts"}
	if requested != "" {
		if requested != "stt" && requested != "translation" && requested != "tts" {
			return nil, status.Errorf(codes.InvalidArgument, "unknown service: %s", requested)
		}
		services = []string{requested}
	}

	loadedModels := make([]string, 0, len(services))
	failures := make([]string, 0)
	for _, svcName := range services {
		var err error
		switch svcName {
		case "stt":
			err = s.deps.STT.HealthCheck("en")
		case "translation":
			err = s.deps.Translator.HealthCheck()
		case "tts":
			err = s.deps.TTS.HealthCheck()
		}
		if err != nil {
			failures = append(failures, svcName+" unavailable: "+err.Error())
			continue
		}
		loadedModels = append(loadedModels, svcName)
	}

	respStatus := "ok"
	healthy := true
	message := "all requested services available"
	if len(loadedModels) == 0 {
		respStatus = "unhealthy"
		healthy = false
		message = strings.Join(failures, "; ")
	} else if len(loadedModels) < len(services) {
		respStatus = "degraded"
		message = strings.Join(failures, "; ")
	}

	return &pb.HealthCheckResponse{
		Healthy:       healthy,
		Status:        respStatus,
		Message:       message,
		UptimeSeconds: uptime,
		LoadedModels:  loadedModels,
	}, nil
}

func (s *Service) validateTranslationRequest(req *pb.TranslationRequest) error {
	if req == nil {
		return status.Error(codes.InvalidArgument, "request is required")
	}
	if strings.TrimSpace(req.GetText()) == "" {
		return status.Error(codes.InvalidArgument, "text is required")
	}
	source := strings.TrimSpace(req.GetSourceLang())
	target := strings.TrimSpace(req.GetTargetLang())
	if source == "" || target == "" {
		return status.Error(codes.InvalidArgument, "source_lang and target_lang are required")
	}
	langs := s.deps.Scanner.GetAvailableTranslationLanguages()
	if _, ok := langs[source]; !ok {
		return status.Errorf(codes.InvalidArgument, "unsupported source_lang: %s", source)
	}
	if _, ok := langs[target]; !ok {
		return status.Errorf(codes.InvalidArgument, "unsupported target_lang: %s", target)
	}
	return nil
}

func (s *Service) validateTTSRequest(req *pb.TTSRequest) error {
	if req == nil {
		return status.Error(codes.InvalidArgument, "request is required")
	}
	if strings.TrimSpace(req.GetText()) == "" {
		return status.Error(codes.InvalidArgument, "text is required")
	}
	lang := strings.TrimSpace(req.GetLanguage())
	if lang == "" {
		return status.Error(codes.InvalidArgument, "language is required")
	}
	langs := s.deps.Scanner.GetAvailableTTSLanguages()
	if _, ok := langs[lang]; !ok {
		return status.Errorf(codes.InvalidArgument, "unsupported TTS language: %s", lang)
	}
	format := strings.ToLower(strings.TrimSpace(req.GetFormat()))
	if format == "" {
		format = "wav"
	}
	if format != "wav" {
		return status.Errorf(codes.InvalidArgument, "unsupported format: %s", format)
	}
	return nil
}

func mapWorkerError(err error) error {
	if err == nil {
		return nil
	}
	msg := strings.ToLower(err.Error())
	switch {
	case strings.Contains(msg, "unsupported_"),
		strings.Contains(msg, "unsupported "),
		strings.Contains(msg, "invalid"),
		strings.Contains(msg, "missing_"),
		strings.Contains(msg, "missing "):
		return status.Error(codes.InvalidArgument, err.Error())
	case strings.Contains(msg, "timeout"):
		return status.Error(codes.DeadlineExceeded, err.Error())
	case strings.Contains(msg, "circuit breaker"):
		return status.Error(codes.Unavailable, err.Error())
	default:
		return status.Error(codes.Internal, err.Error())
	}
}

func parseWAVMetadata(audio []byte) (int32, int32, bool) {
	if len(audio) < 44 {
		return 0, 0, false
	}
	if string(audio[0:4]) != "RIFF" || string(audio[8:12]) != "WAVE" {
		return 0, 0, false
	}

	var (
		offset     = 12
		sampleRate uint32
		channels   uint16
		bits       uint16
		dataBytes  uint32
		foundFmt   bool
	)

	for offset+8 <= len(audio) {
		chunkID := string(audio[offset : offset+4])
		chunkSize := int(binary.LittleEndian.Uint32(audio[offset+4 : offset+8]))
		chunkStart := offset + 8
		chunkEnd := chunkStart + chunkSize
		if chunkEnd > len(audio) || chunkSize < 0 {
			return 0, 0, false
		}

		switch chunkID {
		case "fmt ":
			if chunkSize < 16 {
				return 0, 0, false
			}
			channels = binary.LittleEndian.Uint16(audio[chunkStart+2 : chunkStart+4])
			sampleRate = binary.LittleEndian.Uint32(audio[chunkStart+4 : chunkStart+8])
			bits = binary.LittleEndian.Uint16(audio[chunkStart+14 : chunkStart+16])
			foundFmt = true
		case "data":
			dataBytes = uint32(chunkSize)
		}

		offset = chunkEnd
		if chunkSize%2 == 1 {
			offset++
		}
	}

	if !foundFmt || sampleRate == 0 || channels == 0 || bits == 0 || dataBytes == 0 {
		return 0, 0, false
	}
	bytesPerSec := int64(sampleRate) * int64(channels) * int64(bits) / 8
	if bytesPerSec <= 0 {
		return 0, 0, false
	}
	durationMs := int32((int64(dataBytes) * 1000) / bytesPerSec)
	return int32(sampleRate), durationMs, true
}
