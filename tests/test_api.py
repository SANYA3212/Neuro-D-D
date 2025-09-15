import requests
import asyncio
import websockets
import json
import time
import random

# --- Configuration ---
BASE_URL = "http://127.0.0.1:8000"
USER_1 = {"email": f"testuser_{random.randint(1000,9999)}@example.com", "password": "password123", "username": f"TestUser{random.randint(1000,9999)}"}
USER_2 = {"email": f"testuser_{random.randint(1000,9999)}@example.com", "password": "password123", "username": f"TestUser{random.randint(1000,9999)}"}

# --- State ---
user_1_code = None
user_2_code = None
campaign_id = None
room_code = None

# --- Helper Functions ---
def log_step(step_name):
    print(f"\n{'='*20}\n[STEP] {step_name}\n{'='*20}")

def log_success(message):
    print(f"[SUCCESS] {message}")

def log_error(message):
    print(f"[ERROR] {message}")

def log_info(message):
    print(f"[INFO] {message}")

def test_register_user(user_data):
    """Tests user registration."""
    log_step(f"Registering user: {user_data['username']}")
    response = requests.post(f"{BASE_URL}/api/auth/register", json=user_data)
    if response.status_code == 200:
        log_success(f"User {user_data['username']} registered successfully.")
        return response.json()["user_code"]
    else:
        log_error(f"Failed to register user. Status: {response.status_code}, Response: {response.text}")
        return None

def test_create_campaign(user_code):
    """Tests campaign creation."""
    log_step("Creating a new campaign")
    headers = {"X-User-Code": user_code}
    payload = {"name": "Test Campaign for Automated Script"}
    response = requests.post(f"{BASE_URL}/api/campaigns", json=payload, headers=headers)
    if response.status_code == 200:
        campaign = response.json()
        log_success(f"Campaign created with ID: {campaign['id']}")
        return campaign['id']
    else:
        log_error(f"Failed to create campaign. Status: {response.status_code}, Response: {response.text}")
        return None

def test_create_room(user_code, campaign_id):
    """Tests room creation."""
    log_step("Creating a new room")
    headers = {"X-User-Code": user_code}
    payload = {"name": "Test Room", "is_public": True, "campaign_id": campaign_id}
    response = requests.post(f"{BASE_URL}/api/rooms", json=payload, headers=headers)
    if response.status_code == 200:
        room = response.json()
        log_success(f"Room created with code: {room['room_code']}")
        return room['room_code']
    else:
        log_error(f"Failed to create room. Status: {response.status_code}, Response: {response.text}")
        return None

async def run_tests():
    """Main function to run all tests in sequence."""
    global user_1_code, user_2_code, campaign_id, room_code

    log_step("Starting API Tests")

    user_1_code = test_register_user(USER_1)
    if not user_1_code:
        return

    user_2_code = test_register_user(USER_2)
    if not user_2_code:
        return

    campaign_id = test_create_campaign(user_1_code)
    if not campaign_id:
        return

    room_code = test_create_room(user_1_code, campaign_id)
    if not room_code:
        return

    await test_websocket_flow()

    log_step("All Tests Completed")

async def test_websocket_flow():
    """Tests the full WebSocket lobby flow with delta updates."""
    log_step("Testing WebSocket Flow")

    # Store the local state for each client
    client_state = {"user1": None, "user2": None}

    # 1. User 2 joins the room via HTTP first
    headers = {"X-User-Code": user_2_code}
    payload = {"room_code": room_code}
    response = requests.post(f"{BASE_URL}/api/rooms/join", json=payload, headers=headers)
    if response.status_code != 200:
        log_error(f"User 2 failed to join room. Status: {response.status_code}, Response: {response.text}")
        return
    log_success("User 2 joined the room via HTTP.")

    uri1 = f"ws://127.0.0.1:8000/api/rooms/ws/{room_code}/{user_1_code}"
    uri2 = f"ws://127.0.0.1:8000/api/rooms/ws/{room_code}/{user_2_code}"

    async with websockets.connect(uri1) as ws1, websockets.connect(uri2) as ws2:
        log_success("Both users connected to WebSocket.")

        # 2. Verify initial state for both clients
        # User 1 (host) gets their welcome package
        msg1_initial = json.loads(await ws1.recv())
        client_state["user1"] = msg1_initial
        if len(client_state["user1"]['players']) == 2:
             log_success("User 1 received initial state with 2 players.")
        else:
            log_error(f"User 1 initial state incorrect. Players: {len(client_state['user1']['players'])}")
            return

        # User 2 gets their welcome package
        msg2_initial = json.loads(await ws2.recv())
        client_state["user2"] = msg2_initial
        if len(client_state["user2"]['players']) == 2:
             log_success("User 2 received initial state with 2 players.")
        else:
            log_error(f"User 2 initial state incorrect. Players: {len(client_state['user2']['players'])}")
            return

        # User 1 receives the 'player_joined' delta for User 2
        log_step("User 1 receives join notification for User 2")
        join_delta = json.loads(await ws1.recv())
        if join_delta['type'] == 'player_joined' and join_delta['player']['user_code'] == user_2_code:
            log_success("User 1 correctly received the 'player_joined' delta.")
        else:
            log_error(f"User 1 received incorrect join delta: {join_delta}")
            return

        # 3. User 2 gets ready
        log_step("User 2 sends 'player_ready'")
        await ws2.send(json.dumps({"type": "player_ready"}))

        # Both clients should receive a 'player_ready_changed' delta
        delta1 = json.loads(await ws1.recv())
        delta2 = json.loads(await ws2.recv())

        if delta1['type'] == 'player_ready_changed' and delta1['user_code'] == user_2_code and delta1['is_ready']:
            log_success("User 1 received correct 'player_ready_changed' delta for User 2.")
        else:
            log_error(f"User 1 received incorrect delta for User 2 ready: {delta1}")
            return

        # 4. User 1 gets ready
        log_step("User 1 sends 'player_ready'")
        await ws1.send(json.dumps({"type": "player_ready"}))

        # Both clients should receive another 'player_ready_changed' delta
        delta1 = json.loads(await ws1.recv())
        delta2 = json.loads(await ws2.recv())

        if delta2['type'] == 'player_ready_changed' and delta2['user_code'] == user_1_code and delta2['is_ready']:
            log_success("User 2 received correct 'player_ready_changed' delta for User 1.")
        else:
            log_error(f"User 2 received incorrect delta for User 1 ready: {delta2}")
            return

        # 5. User 1 sends a chat message
        log_step("User 1 sends a chat message")
        chat_text = "Hello from the updated test script!"
        await ws1.send(json.dumps({"type": "chat", "text": chat_text}))

        # Both clients receive the 'new_message' delta
        delta1 = json.loads(await ws1.recv())
        delta2 = json.loads(await ws2.recv())

        if delta2['type'] == 'new_message' and delta2['text'] == chat_text and delta2['sender'] == USER_1['username']:
            log_success("User 2 received the chat message delta correctly.")
        else:
            log_error(f"User 2 did not receive chat message correctly. Received: {delta2}")
            return

        # 6. Host (User 1) starts the game
        log_step("Host sends 'start_game'")
        await ws1.send(json.dumps({"type": "start_game"}))

        # Both clients should receive the 'game_starting' delta
        delta1 = json.loads(await ws1.recv())
        delta2 = json.loads(await ws2.recv())

        if delta2['type'] == 'game_starting':
            log_success("User 2 received 'game_starting' message.")
        else:
            log_error(f"User 2 did not receive 'game_starting' message. Received: {delta2}")
            return

if __name__ == "__main__":
    try:
        asyncio.run(run_tests())
    except ImportError:
        print("Please install required libraries: pip install requests websockets")
    except Exception as e:
        log_error(f"An unexpected error occurred: {e}")
