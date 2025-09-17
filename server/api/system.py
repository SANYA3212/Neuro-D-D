import logging
from fastapi import APIRouter, Body
from pydantic import BaseModel

router = APIRouter(prefix="/system", tags=["System"])
logger = logging.getLogger(__name__)

class ClientLog(BaseModel):
    level: str = "INFO"
    message: str
    context: dict = {}

@router.post("/log")
async def client_log(log: ClientLog = Body(...)):
    """Receives a log message from the client and prints it on the server."""
    level_map = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
    }
    log_level = level_map.get(log.level.upper(), logging.INFO)

    log_message = f"[CLIENT LOG - {log.level.upper()}] {log.message}"
    if log.context:
        log_message += f" | Context: {log.context}"

    logger.log(log_level, log_message)
    return {"status": "logged"}
