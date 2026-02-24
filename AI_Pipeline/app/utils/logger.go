package utils

import "log/slog"

func LogFunctionCall(logger *slog.Logger, funcName string, params map[string]any) {
	if logger == nil {
		logger = slog.Default()
	}

	attrs := make([]any, 0, len(params)+1)
	attrs = append(attrs, "function", funcName)
	for k, v := range params {
		attrs = append(attrs, k, v)
	}
	logger.Debug("function_called", attrs...)
}

func LogErrorWithContext(logger *slog.Logger, err error, context map[string]any, message string) {
	if logger == nil {
		logger = slog.Default()
	}
	if message == "" {
		message = "error_occurred"
	}

	attrs := make([]any, 0, len(context)+1)
	attrs = append(attrs, "error_message", errString(err))
	for k, v := range context {
		attrs = append(attrs, k, v)
	}
	logger.Error(message, attrs...)
}

func CreateComponentLogger(componentName string) *slog.Logger {
	return slog.Default().With("component", componentName)
}

func errString(err error) string {
	if err == nil {
		return ""
	}
	return err.Error()
}

