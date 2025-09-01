import sys
import os
from unittest.mock import MagicMock

# Add the project root to the Python path to allow for imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from server.game_logic import dice, engine
from server.core.models import Message, CampaignMeta, UserSettings

def test_dice_roll():
    print("Testing dice.roll()...")
    for sides in dice.VALID_DICE_SIDES:
        if sides == 100: continue # d100 is special
        result = dice.roll(sides)
        assert 1 <= result <= sides
    print("OK")

def test_d100_roll():
    print("Testing dice.roll_d100()...")
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

    print("OK")

def test_seeded_roll():
    print("Testing seeded dice.roll()...")
    result1 = dice.roll(20, seed=123)
    result2 = dice.roll(20, seed=123)
    assert result1 == result2
    print("OK")

def test_engine_placeholder():
    """
    This is a smoke test for the engine placeholder function.
    It doesn't do much, but it ensures the function can be called
    without errors and returns the expected structure.
    """
    print("Testing engine.process_player_action()...")

    # Mocking necessary inputs
    mock_action = Message(role="user", content="I open the door.")
    mock_meta = CampaignMeta(name="Test", host_user_code="test_user")
    mock_journal = [Message(role="assistant", content="You see a door.")]
    mock_settings = UserSettings(language="en").dict()

    result = engine.process_player_action(
        action=mock_action,
        campaign_meta=mock_meta,
        campaign_journal=mock_journal,
        user_settings=mock_settings
    )

    assert "messages" in result
    assert "context" in result
    assert len(result["messages"]) == 2 # assistant + user
    assert result["messages"][-1] == mock_action
    assert result["context"]["language"] == "en"

    print("OK")

if __name__ == "__main__":
    print("--- Running Game Logic Smoke Tests ---")
    test_dice_roll()
    test_d100_roll()
    test_seeded_roll()
    test_engine_placeholder()
    print("--- All tests passed successfully! ---")
