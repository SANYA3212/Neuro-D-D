from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pathlib import Path

from server.api import auth, users, rooms, campaigns, dice, ai
from server.core.config import ROOT_DIR

# --- App Initialization ---
app = FastAPI(
    title="Neuro D&D API",
    description="The backend server for the Neuro D&D project.",
    version="1.0.a",
)

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


# --- Health Check Endpoint ---
@app.get("/api/health", tags=["System"])
async def health_check():
    """A simple endpoint to check if the server is running."""
    return {"status": "ok"}


# --- Static Files Mounting ---
# This must be placed last, as it will catch all other routes.
# It serves the frontend application (index.html, css, js).
frontend_path = ROOT_DIR / "frontend"
app.mount("/", StaticFiles(directory=frontend_path, html=True), name="static")
