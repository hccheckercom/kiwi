"""WebSocket connection manager for real-time events."""

import asyncio
import json
import time
from typing import Optional

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self):
        self._connections: list[WebSocket] = []
        self._subscriptions: dict[WebSocket, set[str]] = {}

    async def connect(self, ws: WebSocket):
        await ws.accept()
        self._connections.append(ws)
        self._subscriptions[ws] = {"scan", "violation", "check", "fix", "file"}

    def disconnect(self, ws: WebSocket):
        if ws in self._connections:
            self._connections.remove(ws)
        self._subscriptions.pop(ws, None)

    def subscribe(self, ws: WebSocket, channels: list[str]):
        if ws in self._subscriptions:
            self._subscriptions[ws].update(channels)

    def unsubscribe(self, ws: WebSocket, channels: list[str]):
        if ws in self._subscriptions:
            self._subscriptions[ws] -= set(channels)

    async def broadcast(self, event: str, data: dict):
        channel = event.split(".")[0]
        message = json.dumps({
            "event": event,
            "data": data,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })

        disconnected = []
        for ws in self._connections:
            if channel in self._subscriptions.get(ws, set()):
                try:
                    await ws.send_text(message)
                except Exception:
                    disconnected.append(ws)

        for ws in disconnected:
            self.disconnect(ws)

    @property
    def active_count(self) -> int:
        return len(self._connections)


manager = ConnectionManager()