from typing import Dict

# --- Difficulty Classes (DC) ---
# These represent the target number a player must beat in a skill check.
DIFFICULTY_CLASSES: Dict[str, int] = {
    "trivial": 5,
    "easy": 10,
    "medium": 15,
    "hard": 20,
    "very_hard": 25,
    "nearly_impossible": 30,
}

def check_success(roll: int, modifier: int, dc: int) -> bool:
    """
    Performs a basic success check for an action.
    This is a common mechanic in D&D style games.

    Args:
        roll: The result of a d20 roll.
        modifier: The character's skill modifier (e.g., +2 for strength).
        dc: The difficulty class of the task.

    Returns:
        True if the check is successful, False otherwise.
    """
    return (roll + modifier) >= dc

# Future enhancements could include rules for advantage/disadvantage, critical success/failure, etc.
