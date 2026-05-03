"""Gemini adapter — runs Gemini CLI as a subprocess."""

from __future__ import annotations

import asyncio
import json
import shutil
from typing import Any

from ..observability.logger import get_logger
from ..observability.metrics import Timer, metrics
from .base import BaseAdapter, ConcurrencyPool, ModelCache

logger = get_logger("adapter.gemini")


class GeminiAdapter(BaseAdapter):
    """Adapter that spawns Gemini CLI subprocess for each processing round.

    The Gemini CLI is expected to be available on PATH as ``gemini``.
    Each invocation receives the compiled prompt via stdin and returns
    the response on stdout.
    """

    def __init__(
        self,
        agent_id: str,
        role: str,
        cache: ModelCache | None = None,
        pool: ConcurrencyPool | None = None,
        *,
        gemini_bin: str = "gemini",
        model: str = "gemini-2.5-pro",
        timeout: float = 300.0,
    ) -> None:
        cache = cache or ModelCache()
        pool = pool or ConcurrencyPool()
        super().__init__(agent_id, role, cache, pool)
        self.gemini_bin = gemini_bin
        self.model = model
        self.timeout = timeout

    async def process(self, room_id: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process messages through Gemini CLI and return response envelopes."""
        compiled = self.compiler.compile(
            {"agentId": self.agent_id, "role": self.role},
            messages,
        )
        prompt = compiled["system"] + "\n\n" + "\n".join(
            msg.get("payload", {}).get("text", json.dumps(msg.get("payload", {})))
            for msg in compiled["messages"]
        )

        with Timer(metrics.adapter_llm_duration):
            result = await self.pool.execute(self._run_gemini, prompt)

        if not result:
            return []

        response_envelope = {
            "id": f"msg_gemini_{asyncio.get_event_loop().time():.0f}",
            "text": result,
            "source": "gemini",
        }
        return [response_envelope]

    async def _run_gemini(self, prompt: str) -> str | None:
        """Run Gemini CLI as a subprocess and return its output."""
        if not shutil.which(self.gemini_bin):
            logger.error(f"Gemini binary not found: {self.gemini_bin}")
            return None

        try:
            proc = await asyncio.create_subprocess_exec(
                self.gemini_bin,
                "--model", self.model,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(prompt.encode()), timeout=self.timeout)
            if proc.returncode != 0:
                logger.error(f"Gemini exited with code {proc.returncode}: {stderr.decode()[:200]}")
                return None
            return stdout.decode().strip() or None
        except asyncio.TimeoutError:
            logger.error(f"Gemini timed out after {self.timeout}s")
            proc.kill()
            return None
        except Exception as exc:
            logger.error(f"Gemini error: {exc}")
            return None
