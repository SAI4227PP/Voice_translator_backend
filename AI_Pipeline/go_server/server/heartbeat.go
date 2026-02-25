package server

import (
	"context"
	"log/slog"
	"sync"
	"time"
)

type TimeoutHandler func(connectionID string) error

type HeartbeatManager struct {
	logger *slog.Logger

	pingInterval time.Duration
	pingTimeout  time.Duration

	mu            sync.RWMutex
	lastPong      map[string]time.Time
	heartbeatStop map[string]context.CancelFunc
}

func NewHeartbeatManager(pingInterval time.Duration, pingTimeout time.Duration, logger *slog.Logger) *HeartbeatManager {
	return &HeartbeatManager{
		logger:        logger,
		pingInterval:  pingInterval,
		pingTimeout:   pingTimeout,
		lastPong:      map[string]time.Time{},
		heartbeatStop: map[string]context.CancelFunc{},
	}
}

func (hm *HeartbeatManager) StartHeartbeat(connectionID string, websocket *ManagedConn, onTimeout TimeoutHandler) {
	hm.StopHeartbeat(connectionID)

	hm.mu.Lock()
	hm.lastPong[connectionID] = time.Now()
	ctx, cancel := context.WithCancel(context.Background())
	hm.heartbeatStop[connectionID] = cancel
	hm.mu.Unlock()

	go hm.heartbeatLoop(ctx, connectionID, websocket, onTimeout)
	hm.logger.Debug("heartbeat_started", "connection_id", connectionID)
}

func (hm *HeartbeatManager) StopHeartbeat(connectionID string) {
	hm.mu.Lock()
	defer hm.mu.Unlock()

	if cancel, ok := hm.heartbeatStop[connectionID]; ok {
		cancel()
		delete(hm.heartbeatStop, connectionID)
	}
	delete(hm.lastPong, connectionID)

	hm.logger.Debug("heartbeat_stopped", "connection_id", connectionID)
}

func (hm *HeartbeatManager) RecordPong(connectionID string) {
	hm.mu.Lock()
	hm.lastPong[connectionID] = time.Now()
	hm.mu.Unlock()
	hm.logger.Debug("pong_received", "connection_id", connectionID)
}

func (hm *HeartbeatManager) IsAlive(connectionID string) bool {
	hm.mu.RLock()
	last, ok := hm.lastPong[connectionID]
	hm.mu.RUnlock()
	if !ok {
		return false
	}

	elapsed := time.Since(last)
	return elapsed < (hm.pingInterval + hm.pingTimeout)
}

func (hm *HeartbeatManager) heartbeatLoop(ctx context.Context, connectionID string, websocket *ManagedConn, onTimeout TimeoutHandler) {
	ticker := time.NewTicker(hm.pingInterval)
	defer ticker.Stop()
	defer hm.removeTask(connectionID)

	for {
		select {
		case <-ctx.Done():
			hm.logger.Debug("heartbeat_cancelled", "connection_id", connectionID)
			return
		case <-ticker.C:
			elapsed, timedOut := hm.timeoutElapsed(connectionID)
			if timedOut {
				hm.logger.Warn("heartbeat_timeout", "connection_id", connectionID, "elapsed_seconds", elapsed)
				if onTimeout != nil {
					if err := onTimeout(connectionID); err != nil {
						hm.logger.Error("heartbeat_timeout_callback_failed", "connection_id", connectionID, "error", err.Error())
					}
				}
				return
			}

			if err := websocket.SendJSON(map[string]any{
				"type":      "ping",
				"timestamp": time.Now().Format(time.RFC3339Nano),
			}); err != nil {
				hm.logger.Error("ping_send_failed", "connection_id", connectionID, "error", err.Error())
				return
			}
			hm.logger.Debug("ping_sent", "connection_id", connectionID)
		}
	}
}

func (hm *HeartbeatManager) timeoutElapsed(connectionID string) (float64, bool) {
	hm.mu.RLock()
	last, ok := hm.lastPong[connectionID]
	hm.mu.RUnlock()
	if !ok {
		return 0, false
	}
	elapsedDur := time.Since(last)
	return elapsedDur.Seconds(), elapsedDur > (hm.pingInterval + hm.pingTimeout)
}

func (hm *HeartbeatManager) removeTask(connectionID string) {
	hm.mu.Lock()
	delete(hm.heartbeatStop, connectionID)
	hm.mu.Unlock()
}

func (hm *HeartbeatManager) GetActiveHeartbeats() int {
	hm.mu.RLock()
	defer hm.mu.RUnlock()
	return len(hm.heartbeatStop)
}

func (hm *HeartbeatManager) Shutdown() {
	hm.mu.Lock()
	ids := make([]string, 0, len(hm.heartbeatStop))
	for id := range hm.heartbeatStop {
		ids = append(ids, id)
	}
	hm.mu.Unlock()

	hm.logger.Info("shutting_down_heartbeats", "count", len(ids))
	for _, id := range ids {
		hm.StopHeartbeat(id)
	}
	time.Sleep(100 * time.Millisecond)
	hm.logger.Info("heartbeat_shutdown_complete")
}
