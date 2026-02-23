"""
Tests for WebSocket functionality.
"""
import pytest
import json
from fastapi.testclient import TestClient
from app.main import app


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


def test_health_endpoint(client):
    """Test health check endpoint."""
    response = client.get("/health")
    assert response.status_code == 200
    
    data = response.json()
    assert data["status"] == "healthy"
    assert "connections" in data
    assert "rooms" in data


def test_root_endpoint(client):
    """Test root endpoint."""
    response = client.get("/")
    assert response.status_code == 200
    
    data = response.json()
    assert data["service"] == "Voice-to-Voice Translator"
    assert data["status"] == "running"


def test_websocket_connection(client):
    """Test basic WebSocket connection."""
    with client.websocket_connect("/ws") as websocket:
        # Connection should be established
        assert websocket is not None


def test_websocket_join_room(client):
    """Test joining a room via WebSocket."""
    with client.websocket_connect("/ws") as websocket:
        # Send join room message
        join_message = {
            "type": "join_room",
            "payload": {
                "room_id": "test_room",
                "user_id": "test_user",
                "username": "Test User",
                "source_lang": "en",
                "target_lang": "hi"
            }
        }
        websocket.send_json(join_message)
        
        # Receive response
        response = websocket.receive_json()
        
        # Should receive room_joined message
        assert response["type"] == "room_joined"
        assert response["payload"]["room_id"] == "test_room"
        assert response["payload"]["user_id"] == "test_user"


def test_websocket_ping_pong(client):
    """Test ping/pong mechanism."""
    with client.websocket_connect("/ws") as websocket:
        # Send ping
        ping_message = {
            "type": "ping",
            "payload": {}
        }
        websocket.send_json(ping_message)
        
        # Should receive pong
        response = websocket.receive_json()
        assert response["type"] == "pong"


def test_websocket_leave_room(client):
    """Test leaving a room."""
    with client.websocket_connect("/ws") as websocket:
        # First join a room
        join_message = {
            "type": "join_room",
            "payload": {
                "room_id": "test_room",
                "user_id": "test_user",
                "username": "Test User",
                "source_lang": "en",
                "target_lang": "hi"
            }
        }
        websocket.send_json(join_message)
        websocket.receive_json()  # room_joined
        
        # Now leave
        leave_message = {
            "type": "leave_room",
            "payload": {
                "room_id": "test_room",
                "user_id": "test_user"
            }
        }
        websocket.send_json(leave_message)
        
        # Connection should still be active
        # (actual implementation may vary)


@pytest.mark.asyncio
async def test_multiple_users_same_room():
    """Test multiple users in the same room."""
    # This would require async WebSocket testing
    # Implementation depends on your testing strategy
    pass


@pytest.mark.asyncio
async def test_audio_streaming():
    """Test audio data streaming."""
    # This would test binary WebSocket messages
    # Implementation depends on audio pipeline
    pass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
