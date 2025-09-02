from typing import Dict, List
from fastapi import WebSocket

class ConnectionManager:
    def __init__(self):
        # Maps room_code to a list of active WebSocket connections
        self.active_connections: Dict[str, List[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, room_code: str):
        """Accepts a new WebSocket connection and adds it to the room's list."""
        await websocket.accept()
        if room_code not in self.active_connections:
            self.active_connections[room_code] = []
        self.active_connections[room_code].append(websocket)

    def disconnect(self, websocket: WebSocket, room_code: str):
        """Removes a WebSocket connection from a room's list."""
        if room_code in self.active_connections:
            self.active_connections[room_code].remove(websocket)
            # If the room is now empty, remove the room key
            if not self.active_connections[room_code]:
                del self.active_connections[room_code]

    async def broadcast(self, message: dict, room_code: str):
        """Broadcasts a JSON message to all clients in a specific room."""
        if room_code in self.active_connections:
            for connection in self.active_connections[room_code]:
                await connection.send_json(message)

# Create a single, shared instance of the manager
manager = ConnectionManager()
