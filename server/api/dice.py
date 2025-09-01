from fastapi import APIRouter, Depends, HTTPException

from server.game_logic import dice as dice_logic
from server.core.models import RollRequest, DiceRoll
from server.api.auth import get_current_user_code

router = APIRouter(prefix="/dice", tags=["Dice"])


@router.post("/roll", response_model=DiceRoll)
async def roll_dice(
    request: RollRequest,
    user_code: str = Depends(get_current_user_code) # Protect endpoint
):
    """
    Performs a server-side dice roll.
    This can be used for actions that require server validation.
    """
    if request.sides not in dice_logic.VALID_DICE_SIDES:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid sides. Valid options are: {dice_logic.VALID_DICE_SIDES}"
        )

    if request.sides == 100:
        roll_result = dice_logic.roll_d100(seed=request.seed)
        return DiceRoll(
            sides=100,
            result=roll_result["result"],
            parts={"tens": roll_result["tens"], "ones": roll_result["ones"]}
        )
    else:
        result = dice_logic.roll(sides=request.sides, seed=request.seed)
        return DiceRoll(sides=request.sides, result=result)
