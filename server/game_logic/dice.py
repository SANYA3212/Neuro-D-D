import random
from typing import Optional, Dict, Tuple

VALID_DICE_SIDES = {4, 6, 8, 10, 12, 20, 100}

def roll(sides: int, seed: Optional[int] = None) -> int:
    """
    Rolls a single die with a given number of sides.
    Can be seeded for deterministic results.
    """
    if sides not in VALID_DICE_SIDES and sides != 10: # Allow d10 for d100
         raise ValueError(f"Invalid number of sides: {sides}. Must be one of {VALID_DICE_SIDES}")

    if seed is not None:
        rng = random.Random(seed)
        return rng.randint(1, sides)
    return random.randint(1, sides)

def roll_d100(seed: Optional[int] = None) -> Dict[str, int]:
    """
    Rolls a D100 by rolling two D10s.
    One for tens (00-90) and one for ones (0-9).
    A roll of 00 and 0 is treated as 100.
    """
    if seed is not None:
        # Create two distinct seeds from the original seed for reproducible but different rolls
        rng_tens = random.Random(seed)
        rng_ones = random.Random(seed + 1)

        tens_roll = rng_tens.randint(0, 9)
        ones_roll = rng_ones.randint(0, 9)
    else:
        tens_roll = random.randint(0, 9)
        ones_roll = random.randint(0, 9)

    tens = tens_roll * 10
    ones = ones_roll

    result = tens + ones
    if result == 0:
        result = 100

    return {
        "tens": tens_roll, # The die face for tens (0-9)
        "ones": ones_roll, # The die face for ones (0-9)
        "result": result
    }
