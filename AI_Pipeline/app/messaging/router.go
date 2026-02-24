package messaging

import (
	"log/slog"

	"voice_translator_go_server/app/rooms"
)

type MessageRouter interface {
	RouteMessage(connectionID string, message map[string]any) error
	RouteBinary(connectionID string, data []byte) error
	HandleUserDisconnect(userID string) error
}

type ConnectionGateway interface {
	RegisterUser(userID, connectionID string)
	AddToRoom(roomID, userID string)
	RemoveFromRoom(roomID, userID string)
	SendToUser(userID string, message map[string]any) bool
	SendToRoom(roomID string, message map[string]any, excludeUser string) int
	FindUserByConnection(connectionID string) string
}

type AppRouter struct {
	roomManager       *rooms.Manager
	connectionManager ConnectionGateway
	logger            *slog.Logger
}

func NewMessageRouter(roomManager *rooms.Manager, connectionManager ConnectionGateway) *AppRouter {
	return &AppRouter{
		roomManager:       roomManager,
		connectionManager: connectionManager,
		logger:            slog.Default(),
	}
}

func (r *AppRouter) RouteMessage(connectionID string, message map[string]any) (err error) {
	messageType, _ := message["type"].(string)
	if messageType == "" {
		r.logger.Warn("message_missing_type", "connection_id", connectionID)
		return nil
	}

	payload, _ := message["payload"].(map[string]any)
	if payload == nil {
		payload = map[string]any{}
	}

	defer func() {
		if rec := recover(); rec != nil {
			r.logger.Error("message_routing_error", "connection_id", connectionID, "message_type", messageType, "error", rec)
			err = nil
		}
	}()

	switch messageType {
	case TypeJoinRoom:
		err = r.handleJoinRoom(connectionID, payload)
	case TypeLeaveRoom:
		err = r.handleLeaveRoom(payload)
	case TypeAudioStart:
		err = r.handleAudioStart(payload)
	case TypeAudioStop:
		err = r.handleAudioStop(payload)
	case TypeTextMessage:
		err = r.handleTextMessage(payload)
	case TypeGetRoomInfo:
		err = r.handleGetRoomInfo(connectionID, payload)
	case TypePing:
		err = r.handlePing(connectionID)
	default:
		r.logger.Warn("unknown_message_type", "connection_id", connectionID, "message_type", messageType)
		return nil
	}

	if err != nil {
		r.logger.Error("message_routing_error", "connection_id", connectionID, "message_type", messageType, "error", err)
		return nil
	}
	return nil
}

func (r *AppRouter) RouteBinary(connectionID string, data []byte) error {
	r.logger.Debug("binary_message_routed", "connection_id", connectionID, "size", len(data))
	return nil
}

func (r *AppRouter) HandleUserDisconnect(userID string) error {
	roomsAffected := r.roomManager.RemoveUserFromAllRooms(userID)
	for _, roomID := range roomsAffected {
		leftMsg := CreateUserLeftMessage(roomID, userID, "Unknown")
		r.connectionManager.SendToRoom(roomID, leftMsg, "")
	}
	r.logger.Info("user_disconnected", "user_id", userID, "affected_rooms", roomsAffected)
	return nil
}

func (r *AppRouter) handleJoinRoom(connectionID string, payload map[string]any) error {
	roomID, _ := payload["room_id"].(string)
	userID, _ := payload["user_id"].(string)
	username, _ := payload["username"].(string)
	sourceLang, _ := payload["source_lang"].(string)
	targetLang, _ := payload["target_lang"].(string)
	if roomID == "" || userID == "" || username == "" || sourceLang == "" || targetLang == "" {
		r.logger.Warn("join_room_missing_fields", "connection_id", connectionID)
		return nil
	}

	r.connectionManager.RegisterUser(userID, connectionID)
	if ok := r.roomManager.AddUserToRoom(roomID, userID, username, sourceLang, targetLang); !ok {
		r.connectionManager.SendToUser(userID, CreateErrorMessage("ROOM_FULL", "Room has reached maximum capacity"))
		return nil
	}
	r.connectionManager.AddToRoom(roomID, userID)

	room := r.roomManager.GetRoom(roomID)
	users := []map[string]any{}
	if room != nil {
		for _, u := range room.GetAllUsers() {
			users = append(users, u.ToMap())
		}
	}
	r.connectionManager.SendToUser(userID, CreateRoomJoinedMessage(roomID, userID, users))
	r.connectionManager.SendToRoom(roomID, CreateUserJoinedMessage(roomID, map[string]any{
		"user_id":     userID,
		"username":    username,
		"source_lang": sourceLang,
		"target_lang": targetLang,
	}), userID)

	r.logger.Info("user_joined_room", "room_id", roomID, "user_id", userID, "username", username)
	return nil
}

func (r *AppRouter) handleLeaveRoom(payload map[string]any) error {
	roomID, _ := payload["room_id"].(string)
	userID, _ := payload["user_id"].(string)
	if roomID == "" || userID == "" {
		return nil
	}
	room := r.roomManager.GetRoom(roomID)
	if room == nil {
		return nil
	}
	username := "Unknown"
	if u := room.GetUser(userID); u != nil {
		username = u.Username
	}
	
	r.roomManager.RemoveUserFromRoom(roomID, userID)
	r.connectionManager.RemoveFromRoom(roomID, userID)
	r.connectionManager.SendToRoom(roomID, CreateUserLeftMessage(roomID, userID, username), "")
	r.logger.Info("user_left_room", "room_id", roomID, "user_id", userID)
	return nil
}

func (r *AppRouter) handleAudioStart(payload map[string]any) error {
	roomID, _ := payload["room_id"].(string)
	userID, _ := payload["user_id"].(string)
	if userID == "" {
		return nil
	}
	r.logger.Info("audio_started", "room_id", roomID, "user_id", userID)
	r.connectionManager.SendToUser(userID, map[string]any{
		"type": TypeAudioStartAck,
		"payload": map[string]any{
			"room_id": roomID,
			"user_id": userID,
			"ready":   true,
		},
	})
	return nil
}

func (r *AppRouter) handleAudioStop(payload map[string]any) error {
	roomID, _ := payload["room_id"].(string)
	userID, _ := payload["user_id"].(string)
	if userID == "" {
		return nil
	}
	r.logger.Info("audio_stopped", "room_id", roomID, "user_id", userID)
	r.connectionManager.SendToUser(userID, map[string]any{
		"type": TypeAudioStopAck,
		"payload": map[string]any{
			"room_id": roomID,
			"user_id": userID,
		},
	})
	return nil
}

func (r *AppRouter) handleTextMessage(payload map[string]any) error {
	roomID, _ := payload["room_id"].(string)
	userID, _ := payload["user_id"].(string)
	r.logger.Debug("text_message", "room_id", roomID, "user_id", userID)
	r.connectionManager.SendToRoom(roomID, map[string]any{
		"type":    TypeTextMessage,
		"payload": payload,
	}, "")
	return nil
}

func (r *AppRouter) handleGetRoomInfo(connectionID string, payload map[string]any) error {
	roomID, _ := payload["room_id"].(string)
	userID := r.connectionManager.FindUserByConnection(connectionID)
	if userID == "" {
		return nil
	}
	info := r.roomManager.GetRoomInfo(roomID)
	if info != nil {
		r.connectionManager.SendToUser(userID, map[string]any{
			"type":    TypeRoomInfo,
			"payload": info,
		})
		return nil
	}
	r.connectionManager.SendToUser(userID, CreateErrorMessage("ROOM_NOT_FOUND", "Room '"+roomID+"' does not exist"))
	return nil
}

func (r *AppRouter) handlePing(connectionID string) error {
	userID := r.connectionManager.FindUserByConnection(connectionID)
	if userID == "" {
		return nil
	}
	r.connectionManager.SendToUser(userID, CreatePongMessage())
	return nil
}

type NoopRouter struct{}

func (n *NoopRouter) RouteMessage(connectionID string, message map[string]any) error {
	return nil
}

func (n *NoopRouter) RouteBinary(connectionID string, data []byte) error {
	return nil
}

func (n *NoopRouter) HandleUserDisconnect(userID string) error {
	return nil
}