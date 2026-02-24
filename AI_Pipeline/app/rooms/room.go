package rooms

import "time"

type User struct {
	UserID     string
	Username   string
	SourceLang string
	TargetLang string
	JoinedAt   time.Time
	IsSpeaking bool
}

func (u User) ToMap() map[string]any {
	return map[string]any{
		"user_id":     u.UserID,
		"username":    u.Username,
		"source_lang": u.SourceLang,
		"target_lang": u.TargetLang,
		"joined_at":   u.JoinedAt.Format(time.RFC3339Nano),
		"is_speaking": u.IsSpeaking,
	}
}

type Room struct {
	RoomID         string
	MaxUsers       int
	CreatedAt      time.Time
	Users          map[string]*User
	ActiveSpeakers map[string]struct{}
}

func NewRoom(roomID string, maxUsers int) *Room {
	return &Room{
		RoomID:         roomID,
		MaxUsers:       maxUsers,
		CreatedAt:      time.Now(),
		Users:          map[string]*User{},
		ActiveSpeakers: map[string]struct{}{},
	}
}

func (r *Room) AddUser(userID, username, sourceLang, targetLang string) bool {
	if len(r.Users) >= r.MaxUsers {
		return false
	}
	r.Users[userID] = &User{
		UserID:     userID,
		Username:   username,
		SourceLang: sourceLang,
		TargetLang: targetLang,
		JoinedAt:   time.Now(),
	}
	return true
}

func (r *Room) RemoveUser(userID string) bool {
	if _, ok := r.Users[userID]; !ok {
		return false
	}
	delete(r.ActiveSpeakers, userID)
	delete(r.Users, userID)
	return true
}

func (r *Room) GetUser(userID string) *User {
	return r.Users[userID]
}

func (r *Room) GetAllUsers() []*User {
	out := make([]*User, 0, len(r.Users))
	for _, u := range r.Users {
		out = append(out, u)
	}
	return out
}

func (r *Room) IsEmpty() bool {
	return len(r.Users) == 0
}

func (r *Room) GetUserCount() int {
	return len(r.Users)
}

func (r *Room) ToMap() map[string]any {
	users := make([]map[string]any, 0, len(r.Users))
	for _, u := range r.Users {
		users = append(users, u.ToMap())
	}
	active := make([]string, 0, len(r.ActiveSpeakers))
	for id := range r.ActiveSpeakers {
		active = append(active, id)
	}
	return map[string]any{
		"room_id":         r.RoomID,
		"created_at":      r.CreatedAt.Format(time.RFC3339Nano),
		"max_users":       r.MaxUsers,
		"user_count":      len(r.Users),
		"users":           users,
		"active_speakers": active,
	}
}
