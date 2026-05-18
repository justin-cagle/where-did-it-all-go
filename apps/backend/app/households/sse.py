"""Server-Sent Events connection manager for household-level notifications.

Maintains an in-memory registry of user_id -> asyncio.Queue connections.
Connections are cleaned up on disconnect (generator exhaustion or exception).

Usage:
    mgr = get_sse_manager()
    async with mgr.connect(user_id) as queue:
        async for event in mgr.stream(queue):
            yield event

Emit from service code:
    mgr = get_sse_manager()
    await mgr.broadcast("read_only_changed", {"enabled": True})
    await mgr.send_to_user(user_id, "household_assigned", {...})
"""

from __future__ import annotations

import asyncio
import json
import uuid
from collections import defaultdict
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any


class SSEConnectionManager:
    def __init__(self) -> None:
        self._connections: dict[uuid.UUID, list[asyncio.Queue[str | None]]] = defaultdict(list)

    def _format_event(self, event: str, data: dict[str, Any]) -> str:
        return f"event: {event}\ndata: {json.dumps(data)}\n\n"

    @asynccontextmanager
    async def connect(self, user_id: uuid.UUID) -> AsyncGenerator[asyncio.Queue[str | None], None]:
        queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._connections[user_id].append(queue)
        try:
            yield queue
        finally:
            self._connections[user_id].remove(queue)
            if not self._connections[user_id]:
                del self._connections[user_id]

    async def stream(self, queue: asyncio.Queue[str | None]) -> AsyncGenerator[str, None]:
        while True:
            chunk = await queue.get()
            if chunk is None:
                break
            yield chunk

    async def send_to_user(self, user_id: uuid.UUID, event: str, data: dict[str, Any]) -> None:
        payload = self._format_event(event, data)
        for q in list(self._connections.get(user_id, [])):
            await q.put(payload)

    async def broadcast(self, event: str, data: dict[str, Any]) -> None:
        payload = self._format_event(event, data)
        for queues in list(self._connections.values()):
            for q in list(queues):
                await q.put(payload)


_manager: SSEConnectionManager | None = None


def get_sse_manager() -> SSEConnectionManager:
    global _manager
    if _manager is None:
        _manager = SSEConnectionManager()
    return _manager
