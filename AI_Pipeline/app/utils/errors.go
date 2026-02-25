package utils

import "fmt"

type VoiceTranslatorError struct {
	Kind string
	Msg  string
	Err  error
}

func (e *VoiceTranslatorError) Error() string {
	if e == nil {
		return ""
	}
	if e.Msg != "" {
		return e.Msg
	}
	if e.Err != nil {
		return e.Err.Error()
	}
	return e.Kind
}

func (e *VoiceTranslatorError) Unwrap() error {
	if e == nil {
		return nil
	}
	return e.Err
}

func NewError(kind, msg string, err error) error {
	return &VoiceTranslatorError{
		Kind: kind,
		Msg:  msg,
		Err:  err,
	}
}

func wrap(kind, msg string, err error) error {
	if err == nil {
		return NewError(kind, msg, nil)
	}
	if msg == "" {
		return NewError(kind, "", err)
	}
	return NewError(kind, fmt.Sprintf("%s: %v", msg, err), err)
}

func NewConfigurationError(msg string, err error) error      { return wrap("ConfigurationError", msg, err) }
func NewModelLoadError(msg string, err error) error          { return wrap("ModelLoadError", msg, err) }
func NewSTTError(msg string, err error) error                { return wrap("STTError", msg, err) }
func NewTranslationError(msg string, err error) error        { return wrap("TranslationError", msg, err) }
func NewTTSError(msg string, err error) error                { return wrap("TTSError", msg, err) }
func NewAudioProcessingError(msg string, err error) error    { return wrap("AudioProcessingError", msg, err) }
func NewRoomError(msg string, err error) error               { return wrap("RoomError", msg, err) }
func NewRoomFullError(msg string, err error) error           { return wrap("RoomFullError", msg, err) }
func NewRoomNotFoundError(msg string, err error) error       { return wrap("RoomNotFoundError", msg, err) }
func NewUserNotFoundError(msg string, err error) error       { return wrap("UserNotFoundError", msg, err) }
func NewConnectionError(msg string, err error) error         { return wrap("ConnectionError", msg, err) }
func NewAuthenticationError(msg string, err error) error     { return wrap("AuthenticationError", msg, err) }
func NewRateLimitError(msg string, err error) error          { return wrap("RateLimitError", msg, err) }
func NewValidationError(msg string, err error) error         { return wrap("ValidationError", msg, err) }
func NewUnsupportedLanguageError(msg string, err error) error { return wrap("UnsupportedLanguageError", msg, err) }
func NewPipelineError(msg string, err error) error           { return wrap("PipelineError", msg, err) }
func NewWorkerError(msg string, err error) error             { return wrap("WorkerError", msg, err) }

