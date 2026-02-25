package config

import (
	"context"
	"log/slog"
	"os"
	"strings"
)

var globalLogger = slog.Default()

func SetupLogging(settings Settings) *slog.Logger {
	level := parseLevel(settings.LogLevel)
	opts := &slog.HandlerOptions{Level: level}

	var handler slog.Handler
	if strings.EqualFold(settings.Environment, "development") || strings.EqualFold(settings.Environment, "dev") {
		handler = slog.NewTextHandler(os.Stdout, opts)
	} else {
		handler = slog.NewJSONHandler(os.Stdout, opts)
	}

	base := slog.New(handler)

	if strings.TrimSpace(settings.LogFile) != "" {
		f, err := os.OpenFile(settings.LogFile, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0o644)
		if err == nil {
			fileHandler := slog.NewJSONHandler(f, opts)
			multi := slog.New(multiHandler{handlers: []slog.Handler{handler, fileHandler}})
			base = multi
		}
	}

	slog.SetDefault(base)
	globalLogger = base
	globalLogger.Info("logging_configured", "level", strings.ToUpper(settings.LogLevel), "environment", settings.Environment, "file", settings.LogFile)
	return globalLogger
}

func GetLogger() *slog.Logger {
	return globalLogger
}

func parseLevel(v string) slog.Level {
	switch strings.ToUpper(strings.TrimSpace(v)) {
	case "DEBUG":
		return slog.LevelDebug
	case "WARNING", "WARN":
		return slog.LevelWarn
	case "ERROR":
		return slog.LevelError
	default:
		return slog.LevelInfo
	}
}

type multiHandler struct {
	handlers []slog.Handler
}

func (m multiHandler) Enabled(ctx context.Context, level slog.Level) bool {
	for _, h := range m.handlers {
		if h.Enabled(ctx, level) {
			return true
		}
	}
	return false
}

func (m multiHandler) Handle(ctx context.Context, record slog.Record) error {
	for _, h := range m.handlers {
		_ = h.Handle(ctx, record)
	}
	return nil
}

func (m multiHandler) WithAttrs(attrs []slog.Attr) slog.Handler {
	next := make([]slog.Handler, 0, len(m.handlers))
	for _, h := range m.handlers {
		next = append(next, h.WithAttrs(attrs))
	}
	return multiHandler{handlers: next}
}

func (m multiHandler) WithGroup(name string) slog.Handler {
	next := make([]slog.Handler, 0, len(m.handlers))
	for _, h := range m.handlers {
		next = append(next, h.WithGroup(name))
	}
	return multiHandler{handlers: next}
}
