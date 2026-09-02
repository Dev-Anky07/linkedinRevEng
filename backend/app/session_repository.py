import json
from datetime import datetime, timezone
from typing import Any

import redis

from app.security import SessionCipher


class SessionNotFoundError(RuntimeError):
    pass


class RedisSessionRepository:
    def __init__(self, redis_url: str, cipher: SessionCipher, session_id: str):
        self._redis = redis.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=10, socket_timeout=10)
        self._cipher = cipher
        self._key = f"profilely:linkedin:session:{session_id}"

    @property
    def key(self) -> str:
        return self._key

    def ping(self) -> bool:
        return bool(self._redis.ping())

    def load(self) -> dict[str, Any]:
        raw_record = self._redis.get(self._key)
        if raw_record is None:
            raise SessionNotFoundError(f"No session is stored at {self._key}.")
        return self._cipher.decrypt(json.loads(raw_record))

    def save(self, payload: dict[str, Any]) -> None:
        payload["updatedAt"] = datetime.now(timezone.utc).isoformat()
        # No TTL: auth expiry is controlled by cookie metadata/upstream responses.
        self._redis.set(self._key, json.dumps(self._cipher.encrypt(payload), separators=(",", ":")))

    def exists(self) -> bool:
        return bool(self._redis.exists(self._key))
