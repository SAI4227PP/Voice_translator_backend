package messaging

import (
	"time"

	"github.com/google/uuid"
)

const (
	TypeJoinRoom      = "join_room"
	TypeLeaveRoom     = "leave_room"
	TypeAudioStart    = "audio_start"
	TypeAudioStop     = "audio_stop"
	TypeTextMessage   = "text_message"
	TypePing          = "ping"
	TypeGetRoomInfo   = "get_room_info"
	TypeRoomJoined    = "room_joined"
	TypeRoomLeft      = "room_left"
	TypeUserJoined    = "user_joined"
	TypeUserLeft      = "user_left"
	TypeTranscription = "transcription"
	TypeTranslation   = "translation"
	TypeAudioStartAck = "audio_start_ack"
	TypeAudioStopAck  = "audio_stop_ack"
	TypePong          = "pong"
	TypeRoomInfo      = "room_info"
	TypeError         = "error"
)

func CreateMessage(messageType string, payload map[string]any, messageID string) map[string]any {
	id := messageID
	if id == "" {
		id = uuid.NewString()
	}
	return map[string]any{
		"type":       messageType,
		"payload":    payload,
		"timestamp":  time.Now().Format(time.RFC3339Nano),
		"message_id": id,
	}
}

func CreateErrorMessage(errorCode, message string, opts ...any) map[string]any {
	details := any(nil)
	recoverable := true
	if len(opts) >= 1 {
		details = opts[0]
	}
	if len(opts) >= 2 {
		if v, ok := opts[1].(bool); ok {
			recoverable = v
		}
	}
	return CreateMessage(
		TypeError,
		map[string]any{
			"code":        errorCode,
			"message":     message,
			"details":     details,
			"recoverable": recoverable,
		},
		"",
	)
}

func CreateRoomJoinedMessage(roomID, userID string, users []map[string]any) map[string]any {
	return CreateMessage(TypeRoomJoined, map[string]any{
		"room_id": roomID,
		"user_id": userID,
		"users":   users,
	}, "")
}

func CreateUserJoinedMessage(roomID string, user map[string]any) map[string]any {
	return CreateMessage(TypeUserJoined, map[string]any{
		"room_id": roomID,
		"user":    user,
	}, "")
}

func CreateUserLeftMessage(roomID, userID, username string) map[string]any {
	return CreateMessage(TypeUserLeft, map[string]any{
		"room_id":  roomID,
		"user_id":  userID,
		"username": username,
	}, "")
}

func CreateTranscriptionMessage(roomID, userID, text, lang string, isFinal bool, confidence any) map[string]any {
	return CreateMessage(TypeTranscription, map[string]any{
		"room_id":    roomID,
		"user_id":    userID,
		"text":       text,
		"lang":       lang,
		"is_final":   isFinal,
		"confidence": confidence,
	}, "")
}

func CreateTranslationMessage(roomID, sourceUserID, targetUserID, originalText, translatedText, sourceLang, targetLang string, confidence any) map[string]any {
	return CreateMessage(TypeTranslation, map[string]any{
		"room_id":         roomID,
		"source_user_id":  sourceUserID,
		"target_user_id":  targetUserID,
		"original_text":   originalText,
		"translated_text": translatedText,
		"source_lang":     sourceLang,
		"target_lang":     targetLang,
		"confidence":      confidence,
	}, "")
}

func CreatePongMessage() map[string]any {
	return CreateMessage(TypePong, map[string]any{
		"timestamp": time.Now().Format(time.RFC3339Nano),
	}, "")
}
