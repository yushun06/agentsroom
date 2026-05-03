"""Base adapter primitives described by the Agentroom architecture."""

from __future__ import annotations

import asyncio
import time
from collections.abc import Awaitable, Callable
from dataclasses import dataclass, field
from typing import Any


@dataclass
class CachedSession:
    session: Any
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    ttl_seconds: int = 3600

    def touch(self) -> None:
        self.last_used = time.time()

    def is_expired(self) -> bool:
        return time.time() - self.created_at > self.ttl_seconds


class ModelCache:
    def __init__(self, max_sessions: int = 20, session_ttl_seconds: int = 3600) -> None:
        self.max_sessions = max_sessions
        self.session_ttl_seconds = session_ttl_seconds
        self._cache: dict[tuple[str, str], CachedSession] = {}

    def get_or_create(self, agent_id: str, room_id: str, backend_factory: Callable[[], Any]) -> Any:
        key = (agent_id, room_id)
        cached = self._cache.get(key)
        if cached and not cached.is_expired():
            cached.touch()
            return cached.session
        if len(self._cache) >= self.max_sessions:
            self._evict_lru()
        session = backend_factory()
        self._cache[key] = CachedSession(session=session, ttl_seconds=self.session_ttl_seconds)
        return session

    def _evict_lru(self) -> None:
        oldest = min(self._cache, key=lambda key: self._cache[key].last_used)
        del self._cache[oldest]


class ConcurrencyPool:
    def __init__(self, max_concurrent: int = 3) -> None:
        self._semaphore = asyncio.Semaphore(max_concurrent)

    async def execute(self, adapter_fn: Callable[..., Awaitable[Any]], *args: Any, **kwargs: Any) -> Any:
        async with self._semaphore:
            return await adapter_fn(*args, **kwargs)


class PromptCompiler:
    def compile(
        self, agent_identity: dict[str, Any], messages: list[dict[str, Any]], max_tokens: int = 8000
    ) -> dict[str, Any]:
        system = (
            f"You are {agent_identity.get('agentId')} with role {agent_identity.get('role')}. "
            "Respond using Agentroom coordination conventions."
        )
        budget = max(max_tokens - len(system.split()), 0)
        trimmed = messages[-budget:] if budget else []
        return {"system": system, "messages": trimmed}


class BaseAdapter:
    def __init__(self, agent_id: str, role: str, cache: ModelCache, pool: ConcurrencyPool) -> None:
        self.agent_id = agent_id
        self.role = role
        self.cache = cache
        self.pool = pool
        self.compiler = PromptCompiler()

    async def process(self, room_id: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        raise NotImplementedError
