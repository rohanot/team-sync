import pytest

from app.realtime import ConnectionManager


class DummySettings:
    redis_url = "redis://redis:6379/0"
    realtime_presence_ttl_seconds = 45


class FakePubSub:
    def __init__(self) -> None:
        self.subscribed: list[str] = []

    async def subscribe(self, channel: str) -> None:
        self.subscribed.append(channel)

    async def listen(self):
        if False:
            yield {}

    async def close(self) -> None:
        pass


class FakeRedis:
    def __init__(self) -> None:
        self.pinged = False
        self.keys: dict[str, str] = {}
        self.expirations: dict[str, int] = {}
        self.sets: dict[str, set[str]] = {}
        self.published: list[tuple[str, str]] = []
        self.pubsub_instance = FakePubSub()

    async def ping(self) -> None:
        self.pinged = True

    async def set(self, key: str, value: str, ex: int) -> None:
        self.keys[key] = value
        self.expirations[key] = ex

    async def delete(self, key: str) -> None:
        self.keys.pop(key, None)
        self.expirations.pop(key, None)

    async def sadd(self, key: str, value: str) -> None:
        self.sets.setdefault(key, set()).add(value)

    async def smembers(self, key: str) -> set[str]:
        return self.sets.get(key, set())

    async def exists(self, key: str) -> bool:
        return key in self.keys

    async def srem(self, key: str, value: str) -> None:
        self.sets.get(key, set()).discard(value)

    async def publish(self, channel: str, message: str) -> None:
        self.published.append((channel, message))

    def pubsub(self) -> FakePubSub:
        return self.pubsub_instance

    async def aclose(self) -> None:
        pass


class ExplodingRedis(FakeRedis):
    async def ping(self) -> None:
        raise OSError("redis unavailable")


class FakeWebSocket:
    def __init__(self) -> None:
        self.accepted = False
        self.sent: list[dict] = []

    async def accept(self) -> None:
        self.accepted = True

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


@pytest.mark.asyncio
async def test_redis_manager_uses_ttl_presence_and_pubsub_publish() -> None:
    redis = FakeRedis()
    manager = ConnectionManager(settings_provider=lambda: DummySettings(), redis_client_factory=lambda _: redis)
    websocket = FakeWebSocket()

    await manager.connect("project-1", "jane", websocket)
    users = await manager.presence("project-1")
    await manager.broadcast("project-1", {"type": "issue_updated"})

    assert websocket.accepted is True
    assert redis.pinged is True
    assert redis.keys["teamsync:presence:project-1:jane"] == "jane"
    assert redis.expirations["teamsync:presence:project-1:jane"] == 45
    assert users == ["jane"]
    assert redis.published == [('teamsync:realtime:project-1', '{"type":"issue_updated"}')]


@pytest.mark.asyncio
async def test_redis_manager_falls_back_to_in_memory_when_redis_unreachable() -> None:
    redis = ExplodingRedis()
    manager = ConnectionManager(settings_provider=lambda: DummySettings(), redis_client_factory=lambda _: redis)
    websocket = FakeWebSocket()

    await manager.connect("project-1", "jane", websocket)
    users = await manager.presence("project-1")
    await manager.broadcast("project-1", {"type": "issue_updated"})

    assert websocket.accepted is True
    assert users == ["jane"]
    assert websocket.sent == [{"type": "issue_updated"}]
