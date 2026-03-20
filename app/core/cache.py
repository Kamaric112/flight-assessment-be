from __future__ import annotations

from collections.abc import Callable
from threading import RLock
from typing import Generic, TypeVar

from cachetools import TTLCache

T = TypeVar("T")


class InMemoryTTLStore(Generic[T]):
    def __init__(self, ttl_seconds: int, maxsize: int = 1024) -> None:
        self._cache: TTLCache[str, T] = TTLCache(maxsize=maxsize, ttl=ttl_seconds)
        self._lock = RLock()

    def get(self, key: str) -> T | None:
        with self._lock:
            return self._cache.get(key)

    def set(self, key: str, value: T) -> None:
        with self._lock:
            self._cache[key] = value

    def delete(self, key: str) -> None:
        with self._lock:
            self._cache.pop(key, None)

    def get_or_set(self, key: str, factory: Callable[[], T]) -> T:
        with self._lock:
            if key in self._cache:
                return self._cache[key]

        value = factory()
        self.set(key, value)
        return value

