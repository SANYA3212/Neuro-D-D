import pytest
import requests
import asyncio
import websockets
import json
import random
import time

# Give the server a moment to start up
time.sleep(3)

BASE_URL = "http://127.0.0.1:8000"

@pytest.fixture(scope="module")
def session_users():
    """Fixture to create two unique users for the entire test session."""
    user1_email = f"testuser_{random.randint(1000, 9999)}@example.com"
    user2_email = f"testuser_{random.randint(1000, 9999)}@example.com"
    user1 = {"email": user1_email, "password": "password123", "username": "UserOne"}
    user2 = {"email": user2_email, "password": "password123", "username": "UserTwo"}

    # Register User 1
    response1 = requests.post(f"{BASE_URL}/api/auth/register", json=user1)
    assert response1.status_code == 200
    user1_code = response1.json()["user_code"]

    # Register User 2
    response2 = requests.post(f"{BASE_URL}/api/auth/register", json=user2)
    assert response2.status_code == 200
    user2_code = response2.json()["user_code"]

    return (user1_code, user2_code)

@pytest.fixture
def test_campaign(session_users):
    """Fixture to create a campaign owned by user 1."""
    user1_code, _ = session_users
    headers = {"X-User-Code": user1_code}
    payload = {"name": "E2E Test Campaign", "tone": "epic_fantasy", "difficulty": "medium"}
    response = requests.post(f"{BASE_URL}/api/campaigns", json=payload, headers=headers)
    assert response.status_code == 200
    return response.json()["id"]

@pytest.fixture
def test_room(session_users, test_campaign):
    """Fixture to create a room for the campaign, hosted by user 1."""
    user1_code, _ = session_users
    headers = {"X-User-Code": user1_code}
    payload = {"name": "E2E Test Room", "is_public": True, "campaign_id": test_campaign}
    response = requests.post(f"{BASE_URL}/api/rooms", json=payload, headers=headers)
    assert response.status_code == 200
    return response.json()["room_code"]


async def drain_websockets(*sockets):
    """Reads and discards all pending messages from a list of websockets."""
    for ws in sockets:
        while True:
            try:
                await asyncio.wait_for(ws.recv(), timeout=0.1)
            except asyncio.TimeoutError:
                break

@pytest.mark.asyncio
async def test_full_lobby_synchronization(session_users, test_campaign, test_room):
    """
    Tests the full lobby flow, ensuring that every action results in a
    full state broadcast that is consistent for all clients.
    """
    user1_code, user2_code = session_users
    room_code = test_room
    campaign_id = test_campaign

    uri1 = f"ws://127.0.0.1:8000/api/rooms/ws/{room_code}/{user1_code}"
    uri2 = f"ws://127.0.0.1:8000/api/rooms/ws/{room_code}/{user2_code}"

    async with websockets.connect(uri1) as ws1, websockets.connect(uri2) as ws2:
        # We expect two messages on connect: one direct, one broadcast. Drain them.
        await asyncio.sleep(0.1) # give time for broadcasts to arrive
        await drain_websockets(ws1, ws2)

        # 1. User 2 joins the room via HTTP
        headers = {"X-User-Code": user2_code}
        payload = {"room_code": room_code}
        response = requests.post(f"{BASE_URL}/api/rooms/join", json=payload, headers=headers)
        assert response.status_code == 200

        # Now, a broadcast should be sent. Both clients should receive the *same* new state.
        state1_after_join = json.loads(await ws1.recv())
        state2_after_join = json.loads(await ws2.recv())

        assert len(state1_after_join['players']) == 2
        assert state1_after_join == state2_after_join

        # 2. User 2 gets ready
        await drain_websockets(ws1, ws2) # Clean up any lingering messages
        await ws2.send(json.dumps({"type": "player_ready"}))

        # Both should receive the exact same update
        state1_after_ready = json.loads(await ws1.recv())
        state2_after_ready = json.loads(await ws2.recv())

        assert user2_code in state1_after_ready['ready_players']
        assert state1_after_ready == state2_after_ready, "States should be identical after User 2 readies up."
