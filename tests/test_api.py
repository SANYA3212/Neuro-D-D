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


@pytest.mark.asyncio
async def test_start_game_synchronization(session_users, test_room):
    """
    Tests that when the host starts the game, all clients receive the
    'game_starting' message AND a subsequent full state update.
    """
    user1_code, user2_code = session_users
    room_code = test_room

    uri1 = f"ws://127.0.0.1:8000/api/rooms/ws/{room_code}/{user1_code}"
    # For this test, we need a fresh join for user2 to ensure the state is clean
    uri2 = f"ws://127.0.0.1:8000/api/rooms/ws/{room_code}/{user2_code}"

    headers_user2 = {"X-User-Code": user2_code}
    join_payload = {"room_code": room_code}
    join_response = requests.post(f"{BASE_URL}/api/rooms/join", json=join_payload, headers=headers_user2)
    assert join_response.status_code == 200


    async with websockets.connect(uri1) as ws1, websockets.connect(uri2) as ws2:
        # Drain initial connection and join messages for both users
        await asyncio.sleep(0.2)
        await drain_websockets(ws1, ws2)

        # Both players get ready
        await ws1.send(json.dumps({"type": "player_ready"}))
        # Wait for the broadcast from the first ready message before sending the second
        await asyncio.sleep(0.1)
        await drain_websockets(ws1, ws2)
        await ws2.send(json.dumps({"type": "player_ready"}))

        # Drain the ready confirmation broadcasts
        await asyncio.sleep(0.2)
        await drain_websockets(ws1, ws2)

        # Host starts the game
        await ws1.send(json.dumps({"type": "start_game"}))

        # 1. Check for 'game_starting' message for both clients
        # We need a loop here because the order of messages isn't guaranteed.
        # One client might get the 'game_starting' and the state update before the other.

        # Client 1 checks
        msg1_start = json.loads(await asyncio.wait_for(ws1.recv(), timeout=1))
        assert msg1_start == {"type": "game_starting"}
        state1_after_start = json.loads(await asyncio.wait_for(ws1.recv(), timeout=1))
        assert "room_code" in state1_after_start

        # Client 2 checks
        msg2_start = json.loads(await asyncio.wait_for(ws2.recv(), timeout=1))
        assert msg2_start == {"type": "game_starting"}
        state2_after_start = json.loads(await asyncio.wait_for(ws2.recv(), timeout=1))
        assert "room_code" in state2_after_start

        # Finally, assert the states are identical
        assert state1_after_start == state2_after_start


@pytest.mark.asyncio
async def test_non_host_cannot_start_game(session_users, test_room):
    """Tests that a non-host user cannot start the game."""
    user1_code, user2_code = session_users
    room_code = test_room

    uri1 = f"ws://127.0.0.1:8000/api/rooms/ws/{room_code}/{user1_code}"
    uri2 = f"ws://127.0.0.1:8000/api/rooms/ws/{room_code}/{user2_code}"

    # User 2 needs to join properly first
    headers_user2 = {"X-User-Code": user2_code}
    join_payload = {"room_code": room_code}
    requests.post(f"{BASE_URL}/api/rooms/join", json=join_payload, headers=headers_user2)

    async with websockets.connect(uri1) as ws1, websockets.connect(uri2) as ws2:
        await asyncio.sleep(0.2)
        await drain_websockets(ws1, ws2)

        # Both players get ready
        await ws1.send(json.dumps({"type": "player_ready"}))
        await asyncio.sleep(0.1)
        await drain_websockets(ws1, ws2)
        await ws2.send(json.dumps({"type": "player_ready"}))
        await asyncio.sleep(0.2)
        await drain_websockets(ws1, ws2)

        # Non-host (user2) tries to start the game
        await ws2.send(json.dumps({"type": "start_game"}))

        # Assert that the non-host (user2) receives an error message
        error_message = json.loads(await asyncio.wait_for(ws2.recv(), timeout=1))
        assert error_message['type'] == 'error'
        assert error_message['detail'] == 'Only the host can start the game.'

        # Assert that the host (ws1) receives nothing.
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws1.recv(), timeout=0.5)


@pytest.mark.asyncio
async def test_host_cannot_start_game_if_not_all_players_ready(session_users, test_room):
    """Tests that the host cannot start the game if not all players are ready."""
    user1_code, user2_code = session_users
    room_code = test_room

    uri1 = f"ws://127.0.0.1:8000/api/rooms/ws/{room_code}/{user1_code}"
    uri2 = f"ws://127.0.0.1:8000/api/rooms/ws/{room_code}/{user2_code}"

    headers_user2 = {"X-User-Code": user2_code}
    join_payload = {"room_code": room_code}
    requests.post(f"{BASE_URL}/api/rooms/join", json=join_payload, headers=headers_user2)

    async with websockets.connect(uri1) as ws1, websockets.connect(uri2) as ws2:
        await asyncio.sleep(0.2)
        await drain_websockets(ws1, ws2)

        # Only host gets ready
        await ws1.send(json.dumps({"type": "player_ready"}))
        await asyncio.sleep(0.2)
        await drain_websockets(ws1, ws2)

        # Host tries to start the game
        await ws1.send(json.dumps({"type": "start_game"}))

        # Assert that the host receives an error message and no 'game_starting' message is received by the other client
        error_message = json.loads(await asyncio.wait_for(ws1.recv(), timeout=1))
        assert error_message['type'] == 'error'
        assert error_message['detail'] == 'Not all players are ready.'
        with pytest.raises(asyncio.TimeoutError):
            await asyncio.wait_for(ws2.recv(), timeout=0.5)

@pytest.mark.asyncio
async def test_player_disconnect_updates_state(session_users, test_room):
    """Tests that when a player disconnects, the room state is updated for remaining players."""
    user1_code, user2_code = session_users
    room_code = test_room

    uri1 = f"ws://127.0.0.1:8000/api/rooms/ws/{room_code}/{user1_code}"
    uri2 = f"ws://127.0.0.1:8000/api/rooms/ws/{room_code}/{user2_code}"

    async with websockets.connect(uri1) as ws1:
        async with websockets.connect(uri2) as ws2:
            await asyncio.sleep(0.2)
            await drain_websockets(ws1, ws2)

            # User 2 disconnects
            await ws2.close()

        # Assert that user 1 receives a state update where user 2 is no longer in the player list
        state_after_disconnect = json.loads(await asyncio.wait_for(ws1.recv(), timeout=1))
        assert len(state_after_disconnect['players']) == 1
        assert state_after_disconnect['players'][0]['user_code'] == user1_code
