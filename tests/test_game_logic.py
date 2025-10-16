import sys
import os
import asyncio
import uuid
from unittest.mock import patch, MagicMock
import pytest

# Add the project root to the Python path to allow for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from server.game_logic import dice, engine
from server.core.models import RoomDetailsResponse, UserProfile, PlayerState

def test_dice_roll():
    for sides in dice.VALID_DICE_SIDES:
        if sides == 100: continue # d100 is special
        result = dice.roll(sides)
        assert 1 <= result <= sides

def test_d100_roll():
    result_dict = dice.roll_d100()
    assert "tens" in result_dict
    assert "ones" in result_dict
    assert "result" in result_dict
    assert 0 <= result_dict["tens"] <= 9
    assert 0 <= result_dict["ones"] <= 9

    # Check for 100 case
    if result_dict["tens"] == 0 and result_dict["ones"] == 0:
        assert result_dict["result"] == 100
    else:
        assert result_dict["result"] == result_dict["tens"] * 10 + result_dict["ones"]

def test_seeded_roll():
    result1 = dice.roll(20, seed=123)
    result2 = dice.roll(20, seed=123)
    assert result1 == result2

def test_dice_roll_invalid_sides():
    with pytest.raises(ValueError):
        dice.roll(1)
    with pytest.raises(ValueError):
        dice.roll(7)
    with pytest.raises(ValueError):
        dice.roll(25)

def test_seeded_d100_roll():
    result1 = dice.roll_d100(seed=42)
    result2 = dice.roll_d100(seed=42)
    assert result1 == result2

@pytest.mark.asyncio
@patch('server.game_logic.engine.storage.get_player_state')
@patch('server.game_logic.engine.storage.get_user_profile_by_code')
@patch('server.game_logic.engine.storage.read_json')
@patch('server.game_logic.engine.storage.get_campaign_journal_file')
@patch('server.game_logic.engine.storage.get_campaign_meta_file')
@patch('server.game_logic.engine.storage.get_all_rooms')
async def test_get_room_details_logic_smoke_test(
    mock_get_all_rooms,
    mock_get_campaign_meta_file,
    mock_get_campaign_journal_file,
    mock_read_json,
        mock_get_user_profile_by_code,
        mock_get_player_state
):
    """
    Smoke test for get_room_details_logic to ensure it runs without errors
    and returns the correct data structure, restoring coverage for the engine module.
    """
    # --- Mock Setup ---
    room_code = "TEST"
    host_code = "user_host"
    player_code = "user_player"
    campaign_id = str(uuid.uuid4())

    mock_get_all_rooms.return_value = [{
        "room_code": room_code,
        "host_user_code": host_code,
        "players": [host_code, player_code],
        "campaign_id": campaign_id
    }]

    mock_get_campaign_meta_file.return_value = "path/to/meta.json"
    mock_get_campaign_journal_file.return_value = "path/to/journal.json"

    def read_json_side_effect(path):
        if "meta" in path:
                return {"id": campaign_id, "name": "Test Campaign", "host_user_code": host_code}
        if "journal" in path:
            return {"entries": []}
        return None
    mock_read_json.side_effect = read_json_side_effect

    def get_profile_side_effect(code):
        if code == host_code:
            return UserProfile(user_code=host_code, username="Host", email="host@test.com", hashed_password="pw")
        if code == player_code:
            return UserProfile(user_code=player_code, username="Player", email="player@test.com", hashed_password="pw")
        return None
    mock_get_user_profile_by_code.side_effect = get_profile_side_effect

    def get_player_state_side_effect(host_code_arg, campaign_id_arg, player_code_arg):
        if player_code_arg == host_code:
            return PlayerState(hp=15, max_hp=20, inventory=[])
        if player_code_arg == player_code:
            return PlayerState(hp=18, max_hp=20, inventory=[])
        return None
    mock_get_player_state.side_effect = get_player_state_side_effect

    # --- Test Execution ---
    result = await engine.get_room_details_logic(room_code)

    # --- Assertions ---
    assert result is not None
    assert isinstance(result, RoomDetailsResponse)
    assert result.room_code == room_code
    assert len(result.players) == 2
    assert result.players[0].username == "Host"
    assert result.players[1].username == "Player"
    assert result.players[0].hp == 15
    assert result.campaign_meta.name == "Test Campaign"
