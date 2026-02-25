package server

import (
	"encoding/json"
	"fmt"
	"log/slog"

	"voice_translator_go_server/app/messaging"

	"github.com/google/uuid"
	"github.com/gorilla/websocket"
)

type WebSocketServer struct {
	connectionManager *ConnectionManager
	heartbeatManager  *HeartbeatManager
	messageRouter     messaging.MessageRouter
	logger            *slog.Logger
}

func NewWebSocketServer(
	connectionManager *ConnectionManager,
	heartbeatManager *HeartbeatManager,
	messageRouter messaging.MessageRouter,
	logger *slog.Logger,
) *WebSocketServer {
	return &WebSocketServer{
		connectionManager: connectionManager,
		heartbeatManager:  heartbeatManager,
		messageRouter:     messageRouter,
		logger:            logger,
	}
}

func (s *WebSocketServer) HandleConnection(websocketConn *websocket.Conn) {
	connectionID := uuid.NewString()

	defer func() {
		if r := recover(); r != nil {
			s.logger.Error("websocket_error", "connection_id", connectionID, "error", fmt.Sprintf("panic: %v", r))
		}
		s.cleanupConnection(connectionID)
	}()

	s.connectionManager.Connect(websocketConn, connectionID)
	managedConn := s.connectionManager.GetConnectionByID(connectionID)
	if managedConn == nil {
		s.logger.Error("websocket_error", "connection_id", connectionID, "error", "managed connection not found")
		return
	}
	s.heartbeatManager.StartHeartbeat(connectionID, managedConn, s.handleTimeout)

	s.logger.Info("websocket_connection_established", "connection_id", connectionID)
	s.messageLoop(websocketConn, connectionID)
}

func (s *WebSocketServer) messageLoop(websocketConn *websocket.Conn, connectionID string) {
	for {
		messageType, payload, err := websocketConn.ReadMessage()
		if err != nil {
			if websocket.IsCloseError(err, websocket.CloseNormalClosure, websocket.CloseGoingAway, websocket.CloseAbnormalClosure) {
				s.logger.Info("websocket_client_disconnect", "connection_id", connectionID)
			}
			s.logger.Info("websocket_disconnect", "connection_id", connectionID, "error", err.Error())
			return
		}

		switch messageType {
		case websocket.TextMessage:
			s.handleTextMessage(connectionID, payload)
		case websocket.BinaryMessage:
			s.handleBinaryMessage(connectionID, payload)
		}
	}
}

func (s *WebSocketServer) handleTextMessage(connectionID string, payload []byte) {
	defer func() {
		if r := recover(); r != nil {
			s.logger.Error("text_message_error", "connection_id", connectionID, "error", fmt.Sprintf("panic: %v", r))
			s.sendError(connectionID, "INTERNAL_ERROR", "Failed to process message")
		}
	}()

	var message map[string]any
	if err := json.Unmarshal(payload, &message); err != nil {
		s.logger.Error("invalid_json_message", "connection_id", connectionID, "error", err.Error())
		s.sendError(connectionID, "INVALID_MESSAGE", "Invalid JSON format")
		return
	}

	msgType, _ := message["type"].(string)
	s.logger.Debug("text_message_received", "connection_id", connectionID, "message_type", msgType)

	if msgType == messaging.TypePong {
		s.heartbeatManager.RecordPong(connectionID)
		return
	}

	if err := s.messageRouter.RouteMessage(connectionID, message); err != nil {
		s.logger.Error("text_message_error", "connection_id", connectionID, "error", err.Error())
		s.sendError(connectionID, "INTERNAL_ERROR", "Failed to process message")
	}
}

func (s *WebSocketServer) handleBinaryMessage(connectionID string, data []byte) {
	defer func() {
		if r := recover(); r != nil {
			s.logger.Error("binary_message_error", "connection_id", connectionID, "error", fmt.Sprintf("panic: %v", r))
		}
	}()

	s.logger.Debug("binary_message_received", "connection_id", connectionID, "size", len(data))
	if err := s.messageRouter.RouteBinary(connectionID, data); err != nil {
		s.logger.Error("binary_message_error", "connection_id", connectionID, "error", err.Error())
	}
}

func (s *WebSocketServer) handleTimeout(connectionID string) error {
	s.logger.Warn("connection_timeout", "connection_id", connectionID)
	userID := s.connectionManager.Disconnect(connectionID)
	if userID != "" {
		if err := s.messageRouter.HandleUserDisconnect(userID); err != nil {
			return err
		}
	}
	return nil
}

func (s *WebSocketServer) sendError(connectionID string, errorCode string, message string) {
	errorMsg := messaging.CreateErrorMessage(errorCode, message, nil, true)
	userID := s.connectionManager.FindUserByConnection(connectionID)
	if userID == "" {
		return
	}
	s.connectionManager.SendToUser(userID, errorMsg)
}

func (s *WebSocketServer) cleanupConnection(connectionID string) {
	s.logger.Info("cleaning_up_connection", "connection_id", connectionID)
	s.heartbeatManager.StopHeartbeat(connectionID)

	userID := s.connectionManager.Disconnect(connectionID)
	if userID != "" {
		_ = s.messageRouter.HandleUserDisconnect(userID)
	}

	s.logger.Info("connection_cleanup_complete", "connection_id", connectionID, "user_id", userID)
}
