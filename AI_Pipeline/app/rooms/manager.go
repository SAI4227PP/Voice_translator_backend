package rooms

import "sync"

type Manager struct {
	mu       sync.RWMutex
	maxUsers int
	rooms    map[string]*Room
}

func NewManager(maxUsers int) *Manager {
	return &Manager{
		maxUsers: maxUsers,
		rooms:    map[string]*Room{},
	}
}

func (m *Manager) GetOrCreateRoom(roomID string) *Room {
	m.mu.Lock()
	defer m.mu.Unlock()
	if r, ok := m.rooms[roomID]; ok {
		return r
	}
	r := NewRoom(roomID, m.maxUsers)
	m.rooms[roomID] = r
	return r
}

func (m *Manager) GetRoom(roomID string) *Room {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return m.rooms[roomID]
}

func (m *Manager) AddUserToRoom(roomID, userID, username, sourceLang, targetLang string) bool {
	room := m.GetOrCreateRoom(roomID)
	m.mu.Lock()
	defer m.mu.Unlock()
	return room.AddUser(userID, username, sourceLang, targetLang)
}

func (m *Manager) RemoveUserFromRoom(roomID, userID string) bool {
	m.mu.Lock()
	defer m.mu.Unlock()
	room := m.rooms[roomID]
	if room == nil {
		return false
	}
	ok := room.RemoveUser(userID)
	if room.IsEmpty() {
		delete(m.rooms, roomID)
	}
	return ok
}

func (m *Manager) RemoveUserFromAllRooms(userID string) []string {
	m.mu.Lock()
	defer m.mu.Unlock()
	affected := []string{}
	for roomID, room := range m.rooms {
		if _, ok := room.Users[userID]; ok {
			room.RemoveUser(userID)
			affected = append(affected, roomID)
			if room.IsEmpty() {
				delete(m.rooms, roomID)
			}
		}
	}
	return affected
}

func (m *Manager) GetRoomInfo(roomID string) map[string]any {
	m.mu.RLock()
	defer m.mu.RUnlock()
	room := m.rooms[roomID]
	if room == nil {
		return nil
	}
	return room.ToMap()
}

func (m *Manager) GetRoomCount() int {
	m.mu.RLock()
	defer m.mu.RUnlock()
	return len(m.rooms)
}

func (m *Manager) GetTotalUsers() int {
	m.mu.RLock()
	defer m.mu.RUnlock()
	total := 0
	for _, room := range m.rooms {
		total += room.GetUserCount()
	}
	return total
}
