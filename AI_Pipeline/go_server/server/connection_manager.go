package server

import (
	"log/slog"
	"sync"

	"github.com/gorilla/websocket"
)

type ManagedConn struct {
	Conn *websocket.Conn
	mu   sync.Mutex
}

func (mc *ManagedConn) SendJSON(message map[string]any) error {
	mc.mu.Lock()
	defer mc.mu.Unlock()
	return mc.Conn.WriteJSON(message)
}

func (mc *ManagedConn) SendBinary(data []byte) error {
	mc.mu.Lock()
	defer mc.mu.Unlock()
	return mc.Conn.WriteMessage(websocket.BinaryMessage, data)
}

type ConnectionManager struct {
	logger *slog.Logger

	mu sync.RWMutex
	// {connection_id: websocket}
	activeConnections map[string]*ManagedConn
	// {user_id: connection_id}
	userConnections map[string]string
	// {room_id: set(user_id)}
	roomMembers map[string]map[string]struct{}
}

func NewConnectionManager(logger *slog.Logger) *ConnectionManager {
	return &ConnectionManager{
		logger:            logger,
		activeConnections: map[string]*ManagedConn{},
		userConnections:   map[string]string{},
		roomMembers:       map[string]map[string]struct{}{},
	}
}

func (cm *ConnectionManager) Connect(conn *websocket.Conn, connectionID string) {
	cm.mu.Lock()
	cm.activeConnections[connectionID] = &ManagedConn{Conn: conn}
	total := len(cm.activeConnections)
	cm.mu.Unlock()

	cm.logger.Info("connection_accepted", "connection_id", connectionID, "total_connections", total)
}

func (cm *ConnectionManager) Disconnect(connectionID string) string {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	delete(cm.activeConnections, connectionID)

	var userID string
	for uid, connID := range cm.userConnections {
		if connID == connectionID {
			userID = uid
			delete(cm.userConnections, uid)
			break
		}
	}

	if userID != "" {
		for _, members := range cm.roomMembers {
			delete(members, userID)
		}
	}

	cm.logger.Info(
		"connection_disconnected",
		"connection_id", connectionID,
		"user_id", userID,
		"remaining_connections", len(cm.activeConnections),
	)

	return userID
}

func (cm *ConnectionManager) RegisterUser(userID string, connectionID string) {
	cm.mu.Lock()
	cm.userConnections[userID] = connectionID
	cm.mu.Unlock()
	cm.logger.Info("user_registered", "user_id", userID, "connection_id", connectionID)
}

func (cm *ConnectionManager) AddToRoom(roomID string, userID string) {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	if _, ok := cm.roomMembers[roomID]; !ok {
		cm.roomMembers[roomID] = map[string]struct{}{}
	}
	cm.roomMembers[roomID][userID] = struct{}{}
	cm.logger.Info(
		"user_added_to_room",
		"room_id", roomID,
		"user_id", userID,
		"room_size", len(cm.roomMembers[roomID]),
	)
}

func (cm *ConnectionManager) RemoveFromRoom(roomID string, userID string) {
	cm.mu.Lock()
	defer cm.mu.Unlock()

	members, ok := cm.roomMembers[roomID]
	if !ok {
		return
	}

	if _, exists := members[userID]; !exists {
		return
	}

	delete(members, userID)
	if len(members) == 0 {
		delete(cm.roomMembers, roomID)
	}

	cm.logger.Info("user_removed_from_room", "room_id", roomID, "user_id", userID)
}

func (cm *ConnectionManager) GetRoomMembers(roomID string) []string {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	members := cm.roomMembers[roomID]
	result := make([]string, 0, len(members))
	for userID := range members {
		result = append(result, userID)
	}
	return result
}

func (cm *ConnectionManager) GetUserConnection(userID string) *ManagedConn {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	connectionID, ok := cm.userConnections[userID]
	if !ok {
		return nil
	}
	return cm.activeConnections[connectionID]
}

func (cm *ConnectionManager) GetConnectionByID(connectionID string) *ManagedConn {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	return cm.activeConnections[connectionID]
}

func (cm *ConnectionManager) FindUserByConnection(connectionID string) string {
	cm.mu.RLock()
	defer cm.mu.RUnlock()

	for userID, connID := range cm.userConnections {
		if connID == connectionID {
			return userID
		}
	}
	return ""
}

func (cm *ConnectionManager) SendToUser(userID string, message map[string]any) bool {
	conn := cm.GetUserConnection(userID)
	if conn == nil {
		return false
	}

	if err := conn.SendJSON(message); err != nil {
		cm.logger.Error("send_to_user_failed", "user_id", userID, "error", err.Error())
		return false
	}
	return true
}

func (cm *ConnectionManager) SendToRoom(roomID string, message map[string]any, excludeUser string) int {
	members := cm.GetRoomMembers(roomID)
	sentCount := 0

	for _, userID := range members {
		if excludeUser != "" && userID == excludeUser {
			continue
		}
		if cm.SendToUser(userID, message) {
			sentCount++
		}
	}

	cm.logger.Debug(
		"message_broadcast_to_room",
		"room_id", roomID,
		"recipients", sentCount,
		"total_members", len(members),
	)
	return sentCount
}

func (cm *ConnectionManager) SendBinaryToUser(userID string, data []byte) bool {
	conn := cm.GetUserConnection(userID)
	if conn == nil {
		return false
	}

	if err := conn.SendBinary(data); err != nil {
		cm.logger.Error("send_binary_to_user_failed", "user_id", userID, "error", err.Error())
		return false
	}
	return true
}

func (cm *ConnectionManager) GetConnectionCount() int {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	return len(cm.activeConnections)
}

func (cm *ConnectionManager) GetRoomCount() int {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	return len(cm.roomMembers)
}

func (cm *ConnectionManager) GetUserCount() int {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	return len(cm.userConnections)
}

func (cm *ConnectionManager) IsUserConnected(userID string) bool {
	cm.mu.RLock()
	defer cm.mu.RUnlock()
	_, ok := cm.userConnections[userID]
	return ok
}
