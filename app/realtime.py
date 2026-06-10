from __future__ import annotations

import asyncio
import contextlib
import json
from collections import defaultdict
from collections.abc import Callable
from typing import Any

from fastapi import WebSocket

from app.config import Settings, get_settings


class ConnectionManager:
    def __init__(
        self,
        settings_provider: Callable[[], Settings] = get_settings,
        redis_client_factory: Callable[[str], Any] | None = None,
    ) -> None:
        self._settings_provider = settings_provider
        self._redis_client_factory = redis_client_factory
        self._connections: dict[str, set[WebSocket]] = defaultdict(set)
        self._presence: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._redis: Any | None = None
        self._redis_unavailable = False
        self._pubsub: Any | None = None
        self._subscriber_task: asyncio.Task | None = None
        self._subscribed_projects: set[str] = set()

    async def connect(self, project_id: str, user_id: str, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections[project_id].add(websocket)
        self._presence[project_id][user_id] += 1
        if await self._ensure_redis():
            try:
                await self._write_redis_presence(project_id, user_id)
                await self._subscribe_project(project_id)
            except Exception:
                await self._disable_redis()

    async def disconnect(self, project_id: str, user_id: str, websocket: WebSocket) -> None:
        self._connections[project_id].discard(websocket)
        if not self._connections[project_id]:
            self._connections.pop(project_id, None)
        if user_id in self._presence[project_id]:
            self._presence[project_id][user_id] -= 1
            if self._presence[project_id][user_id] <= 0:
                self._presence[project_id].pop(user_id, None)
                if await self._ensure_redis():
                    try:
                        await self._redis.delete(self._presence_key(project_id, user_id))
                        await self._redis.srem(self._presence_set_key(project_id), user_id)
                    except Exception:
                        await self._disable_redis()
        if project_id in self._presence and not self._presence[project_id]:
            self._presence.pop(project_id, None)

    async def presence(self, project_id: str) -> list[str]:
        if await self._ensure_redis():
            try:
                users = await self._redis.smembers(self._presence_set_key(project_id))
                active: list[str] = []
                for raw_user_id in users:
                    user_id = raw_user_id.decode("utf-8") if isinstance(raw_user_id, bytes) else str(raw_user_id)
                    if await self._redis.exists(self._presence_key(project_id, user_id)):
                        active.append(user_id)
                    else:
                        await self._redis.srem(self._presence_set_key(project_id), user_id)
                return sorted(active)
            except Exception:
                await self._disable_redis()
        return sorted(self._presence.get(project_id, {}).keys())

    async def broadcast(self, project_id: str, payload: dict[str, Any]) -> None:
        if await self._ensure_redis():
            try:
                await self._redis.publish(self._channel(project_id), json.dumps(payload, separators=(",", ":")))
                return
            except Exception:
                await self._disable_redis()
        await self._broadcast_local(project_id, payload)

    async def _broadcast_local(self, project_id: str, payload: dict[str, Any]) -> None:
        stale: list[WebSocket] = []
        for websocket in list(self._connections.get(project_id, set())):
            try:
                await websocket.send_json(payload)
            except RuntimeError:
                stale.append(websocket)
        for websocket in stale:
            self._connections[project_id].discard(websocket)

    async def _ensure_redis(self) -> bool:
        if self._redis_unavailable:
            return False
        settings = self._settings_provider()
        if not settings.redis_url:
            return False
        if self._redis is not None:
            return True
        try:
            self._redis = self._create_redis_client(settings.redis_url)
            await self._redis.ping()
            self._start_subscriber()
            return True
        except Exception:
            await self._disable_redis()
            return False

    def _create_redis_client(self, redis_url: str) -> Any:
        if self._redis_client_factory:
            return self._redis_client_factory(redis_url)
        from redis import asyncio as redis_asyncio

        return redis_asyncio.from_url(redis_url, decode_responses=True)

    async def _write_redis_presence(self, project_id: str, user_id: str) -> None:
        ttl_seconds = self._settings_provider().realtime_presence_ttl_seconds
        await self._redis.set(self._presence_key(project_id, user_id), user_id, ex=ttl_seconds)
        await self._redis.sadd(self._presence_set_key(project_id), user_id)

    async def _subscribe_project(self, project_id: str) -> None:
        if project_id in self._subscribed_projects:
            return
        if self._pubsub is None:
            self._pubsub = self._redis.pubsub()
        await self._pubsub.subscribe(self._channel(project_id))
        self._subscribed_projects.add(project_id)

    def _start_subscriber(self) -> None:
        if self._subscriber_task is None or self._subscriber_task.done():
            self._subscriber_task = asyncio.create_task(self._subscriber_loop())

    async def _subscriber_loop(self) -> None:
        while True:
            try:
                if self._pubsub is None:
                    await asyncio.sleep(0.1)
                    continue
                async for message in self._pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    channel = message.get("channel", "")
                    if isinstance(channel, bytes):
                        channel = channel.decode("utf-8")
                    project_id = channel.rsplit(":", 1)[-1]
                    data = message.get("data")
                    if isinstance(data, bytes):
                        data = data.decode("utf-8")
                    await self._broadcast_local(project_id, json.loads(data))
                return
            except asyncio.CancelledError:
                raise
            except Exception:
                await self._disable_redis()
                return

    async def _disable_redis(self) -> None:
        self._redis_unavailable = True
        if self._subscriber_task and not self._subscriber_task.done():
            self._subscriber_task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self._subscriber_task
        if self._pubsub is not None:
            with contextlib.suppress(Exception):
                await self._pubsub.close()
        if self._redis is not None:
            with contextlib.suppress(Exception):
                await self._redis.aclose()
        self._redis = None
        self._pubsub = None
        self._subscriber_task = None
        self._subscribed_projects.clear()

    @staticmethod
    def _channel(project_id: str) -> str:
        return f"teamsync:realtime:{project_id}"

    @staticmethod
    def _presence_set_key(project_id: str) -> str:
        return f"teamsync:presence:{project_id}"

    @staticmethod
    def _presence_key(project_id: str, user_id: str) -> str:
        return f"teamsync:presence:{project_id}:{user_id}"


manager = ConnectionManager()
