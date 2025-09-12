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
    """Tests the full WebSocket lobby flow."""
    log_step("Testing WebSocket Flow")

    # 1. User 2 joins the room
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

        # 2. Verify initial state broadcast
        msg1 = await ws1.recv()
        msg2 = await ws2.recv()
        state1 = json.loads(msg1)
        state2 = json.loads(msg2)

        if len(state1['players']) == 2 and len(state2['players']) == 2:
            log_success("Initial state broadcast received by both users with 2 players.")
        else:
            log_error(f"Initial state incorrect. User1 players: {len(state1['players'])}, User2 players: {len(state2['players'])}")
            return

        # 3. User 2 gets ready
        log_step("User 2 sends 'player_ready'")
        await ws2.send(json.dumps({"type": "player_ready"}))

        msg1 = await ws1.recv()
        msg2 = await ws2.recv()
        state1 = json.loads(msg1)

        if user_2_code in state1['ready_players']:
            log_success("User 1 received update with User 2 ready.")
        else:
            log_error("User 1 did not see User 2 as ready.")
            return

        # 4. User 1 gets ready
        log_step("User 1 sends 'player_ready'")
        await ws1.send(json.dumps({"type": "player_ready"}))

        msg1 = await ws1.recv()
        msg2 = await ws2.recv()
        state2 = json.loads(msg2)

        if len(state2['ready_players']) == 2:
            log_success("User 2 received update with both players ready.")
        else:
            log_error(f"User 2 did not see both players as ready. Ready count: {len(state2['ready_players'])}")
            return

        # 5. User 1 sends a chat message
        log_step("User 1 sends a chat message")
        chat_text = "Hello from the test script!"
        await ws1.send(json.dumps({"type": "chat", "text": chat_text}))

        msg1 = await ws1.recv()
        msg2 = await ws2.recv()
        chat_msg = json.loads(msg2)

        if chat_msg['type'] == 'new_message' and chat_msg['text'] == chat_text:
            log_success("User 2 received the chat message correctly.")
        else:
            log_error(f"User 2 did not receive chat message correctly. Received: {chat_msg}")
            return

        # 6. Host (User 1) starts the game
        log_step("Host sends 'start_game'")
        await ws1.send(json.dumps({"type": "start_game"}))

        msg1 = await ws1.recv()
        msg2 = await ws2.recv()
        start_msg = json.loads(msg2)

        if start_msg['type'] == 'game_starting':
            log_success("User 2 received 'game_starting' message.")
        else:
            log_error(f"User 2 did not receive 'game_starting' message. Received: {start_msg}")
            return

if __name__ == "__main__":
    try:
        asyncio.run(run_tests())
    except ImportError:
        print("Please install required libraries: pip install requests websockets")
    except Exception as e:
        log_error(f"An unexpected error occurred: {e}")
