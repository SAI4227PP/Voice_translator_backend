package server

import (
	"log/slog"
	"os"
	"strconv"
	"time"

	"voice_translator_go_server/app/messaging"
)

var (
	wsPingIntervalSeconds = getEnvInt("WS_PING_INTERVAL", 20)
	wsPingTimeoutSeconds  = getEnvInt("WS_PING_TIMEOUT", 10)
	connectionManager = NewConnectionManager(slog.Default())
	heartbeatManager  = NewHeartbeatManager(time.Duration(wsPingIntervalSeconds)*time.Second, time.Duration(wsPingTimeoutSeconds)*time.Second, slog.Default())
	messageRouter     messaging.MessageRouter = &messaging.NoopRouter{}
	websocketServer                        = NewWebSocketServer(connectionManager, heartbeatManager, messageRouter, slog.Default())
)

func ConfigureHeartbeat(pingIntervalSeconds int, pingTimeoutSeconds int) {
	if pingIntervalSeconds <= 0 {
		pingIntervalSeconds = wsPingIntervalSeconds
	}
	if pingTimeoutSeconds <= 0 {
		pingTimeoutSeconds = wsPingTimeoutSeconds
	}
	heartbeatManager = NewHeartbeatManager(time.Duration(pingIntervalSeconds)*time.Second, time.Duration(pingTimeoutSeconds)*time.Second, slog.Default())
	websocketServer = NewWebSocketServer(connectionManager, heartbeatManager, messageRouter, slog.Default())
}

func GetConnectionManager() *ConnectionManager {
	return connectionManager
}

func GetHeartbeatManager() *HeartbeatManager {
	return heartbeatManager
}

func GetWebSocketServer() *WebSocketServer {
	return websocketServer
}

func SetMessageRouter(r messaging.MessageRouter) {
	if r == nil {
		return
	}
	messageRouter = r
	websocketServer = NewWebSocketServer(connectionManager, heartbeatManager, messageRouter, slog.Default())
}

func getEnvInt(key string, defaultValue int) int {
	val := os.Getenv(key)
	if val == "" {
		return defaultValue
	}
	n, err := strconv.Atoi(val)
	if err != nil || n <= 0 {
		return defaultValue
	}
	return n
}
