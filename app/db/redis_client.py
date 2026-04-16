from __future__ import annotations

from typing import Any, Dict, Optional

from app.config import settings

try:
    import redis.asyncio as redis
except ModuleNotFoundError:  # pragma: no cover - optional local fallback
    redis = None


class InMemoryRedis:
    def __init__(self) -> None:
        self._store: Dict[str, str] = {}

    async def get(self, key: str) -> Optional[str]:
        return self._store.get(key)

    async def set(self, key: str, value: Any, ex: Optional[int] = None) -> bool:
        del ex  # TTL is ignored in simple in-memory fallback.
        self._store[key] = str(value)
        return True

    async def delete(self, *keys: str) -> int:
        deleted = 0
        for key in keys:
            if key in self._store:
                deleted += 1
                del self._store[key]
        return deleted

    async def ping(self) -> bool:
        return True

    async def close(self) -> None:
        return None


_redis_instance: Optional[Any] = None


async def get_redis() -> Any:
    global _redis_instance
    if _redis_instance is not None:
        return _redis_instance

    if redis is not None:
        _redis_instance = redis.from_url(
            settings.redis_url, encoding="utf-8", decode_responses=True
        )
        return _redis_instance

    _redis_instance = InMemoryRedis()
    return _redis_instance
