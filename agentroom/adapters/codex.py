"""Codex adapter — runs OpenAI Codex CLI as a subprocess."""

from __future__ import annotations

import asyncio
import json
import shutil
from typing import Any

from ..observability.logger import get_logger
from ..observability.metrics import Timer, metrics
from .base import BaseAdapter, ConcurrencyPool, ModelCache

logger = get_logger("adapter.codex")


class CodexAdapter(BaseAdapter):
    """Adapter that spawns Codex CLI subprocess for each processing round.

    The Codex CLI is expected to be available on PATH as ``codex``.
    Each invocation receives the compiled prompt via stdin and returns
    the response on stdout as JSON.
    """

    def __init__(
        self,
        agent_id: str,
        role: str,
        cache: ModelCache | None = None,
        pool: ConcurrencyPool | None = None,
        *,
        codex_bin: str = "codex",
        model: str = "o4-mini",
        timeout: float = 300.0,
    ) -> None:
        cache = cache or ModelCache()
        pool = pool or ConcurrencyPool()
        super().__init__(agent_id, role, cache, pool)
        self.codex_bin = codex_bin
        self.model = model
        self.timeout = timeout

    async def process(self, room_id: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Process messages through Codex CLI and return response envelopes."""
        compiled = self.compiler.compile(
            {"agentId": self.agent_id, "role": self.role},
            messages,
        )
        prompt = compiled["system"] + "\n\n" + "\n".join(
            msg.get("payload", {}).get("text", json.dumps(msg.get("payload", {})))
            for msg in compiled["messages"]
        )

        with Timer(metrics.adapter_llm_duration):
            result = await self.pool.execute(self._run_codex, prompt)

        if not result:
            return []

        response_envelope = {
            "id": f"msg_codex_{asyncio.get_event_loop().time():.0f}",
            "text": result,
            "source": "codex",
        }
        return [response_envelope]

    async def _run_codex(self, prompt: str) -> str | None:
        """Run Codex CLI as a subprocess and return its output."""
        if not shutil.which(self.codex_bin):
            logger.error(f"Codex binary not found: {self.codex_bin}")
            return None

        try:
            proc = await asyncio.create_subprocess_exec(
                self.codex_bin,
                "--model", self.model,
                "--quiet",
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(prompt.encode()), timeout=self.timeout)
            if proc.returncode != 0:
                logger.error(f"Codex exited with code {proc.returncode}: {stderr.decode()[:200]}")
                return None
            return stdout.decode().strip() or None
        except asyncio.TimeoutError:
            logger.error(f"Codex timed out after {self.timeout}s")
            proc.kill()
            return None
        except Exception as exc:
            logger.error(f"Codex error: {exc}")
            return None
