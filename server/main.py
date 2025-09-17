import time
import logging
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from server.api import auth, users, rooms, campaigns, dice, ai, system
from server.core.config import ROOT_DIR

# --- Logging Middleware ---
class LoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        start_time = time.time()
        req_logger = logging.getLogger("api.request")
        user_code = request.headers.get('x-user-code', 'anonymous')

        req_logger.info(f"--> {request.method} {request.url.path} [user:{user_code}, ip:{request.client.host}]")

        response = await call_next(request)

        process_time = (time.time() - start_time) * 1000
        formatted_process_time = '{0:.2f}'.format(process_time)

        req_logger.info(f"<-- {response.status_code} for {request.url.path} (took {formatted_process_time}ms)")

        return response

# --- App Initialization ---
# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Neuro D&D API",
    description="The backend server for the Neuro D&D project.",
    version="1.0.a",
)

# Add middlewares
app.add_middleware(LoggingMiddleware)

# --- CORS Middleware ---
# This allows the frontend (even when opened from file://) to communicate with the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins
    allow_credentials=True,
    allow_methods=["*"],   # Allow all methods
    allow_headers=["*"],   # Allow all headers
)

# --- API Routers ---
# Include all the API endpoints from the /api directory
app.include_router(auth.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(rooms.router, prefix="/api")
app.include_router(campaigns.router, prefix="/api")
app.include_router(dice.router, prefix="/api")
app.include_router(ai.router, prefix="/api")
app.include_router(system.router, prefix="/api")


# --- Health Check Endpoint ---
@app.get("/api/health", tags=["System"])
async def health_check():
    """A simple endpoint to check if the server is running."""
    return {"status": "ok"}


# --- Static Files Mounting ---
# This must be placed last, as it will catch all other routes.
# It serves the frontend application (index.html, css, js).
assets_path = ROOT_DIR / "frontend/assets"
assets_path.mkdir(exist_ok=True) # Ensure the assets directory exists
(assets_path / "avatars").mkdir(exist_ok=True) # Ensure the avatars subdirectory exists
app.mount("/assets", StaticFiles(directory=assets_path), name="assets")

frontend_path = ROOT_DIR / "frontend"
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")
