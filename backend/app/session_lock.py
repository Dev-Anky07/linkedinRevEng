import secrets
import time
from contextlib import contextmanager
from typing import Iterator

import redis

RELEASE_IF_OWNER = """
if redis.call('get', KEYS[1]) == ARGV[1] then
  return redis.call('del', KEYS[1])
end
return 0
"""

class SessionBusyError(RuntimeError):
    pass

class RedisSessionLock:
    """A short-lived Redis lock protecting one mutable browser session."""
    def __init__(self, redis_url: str, session_id: str, ttl_seconds: int = 90):
        self._redis = redis.Redis.from_url(redis_url, decode_responses=True, socket_connect_timeout=10, socket_timeout=10)
        self._key = f"profilely:linkedin:lock:{session_id}"
        self._ttl_ms = ttl_seconds * 1000

    @contextmanager
    def hold(self, wait_seconds: float = 2.0) -> Iterator[None]:
        token = secrets.token_urlsafe(24)
        deadline = time.monotonic() + wait_seconds
        while time.monotonic() < deadline:
            if self._redis.set(self._key, token, nx=True, px=self._ttl_ms):
                break
            time.sleep(0.1)
        else:
            raise SessionBusyError("The shared LinkedIn session is busy. Try again shortly.")
        try:
            yield
        finally:
            self._redis.eval(RELEASE_IF_OWNER, 1, self._key, token)
