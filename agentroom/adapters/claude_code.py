"""Claude Code adapter — runs Claude Code CLI as a subprocess."""

from __future__ import annotations

import asyncio
import json
import shutil
from typing import Any

from ..observability.logger import get_logger
from ..observability.metrics import Timer, metrics
from .base import BaseAdapter, ConcurrencyPool, ModelCache

logger = get_logger("adapter.claude_code")


class ClaudeCodeAdapter(BaseAdapter):
    """Adapter that spawns Claude Code CLI subprocess for each processing round.

    The Claude Code CLI is expected to be available on PATH as ``claude``.
    Each invocation receives the compiled prompt as a --prompt argument
    and returns the response on stdout.
    """

    def __init__(
        self,
        agent_id: str,
        role: str,
        cache: ModelCache | None = None,
        pool: ConcurrencyPool | None = None,
        *,
        claude_bin: str = "claude",
        model: str = "claude-sonnet-4-20250514",
        timeout: float = 300.0,
    ) -> None:
        cache = cache or ModelCache()
        pool = pool or ConcurrencyPool()
        super().__init__(agent_id, role, cache, pool)
        self.claude_bin = claude_bin
        self.model = model
        self.timeout = timeout

    async def process(self, room_id: str, messages: list[dict[str, Any]]) -> list[dict[str, Any]]:  # noqa: ARG002
        """Process messages through Claude Code CLI and return response envelopes."""
        compiled = self.compiler.compile(
            {"agentId": self.agent_id, "role": self.role},
            messages,
        )
        prompt = (
            compiled["system"]
            + "\n\n"
            + "\n".join(
                msg.get("payload", {}).get("text", json.dumps(msg.get("payload", {}))) for msg in compiled["messages"]
            )
        )

        with Timer(metrics.adapter_llm_duration):
            result = await self.pool.execute(self._run_claude, prompt)

        if not result:
            return []

        response_envelope = {
            "id": f"msg_claude_{asyncio.get_event_loop().time():.0f}",
            "text": result,
            "source": "claude_code",
        }
        return [response_envelope]

    async def _run_claude(self, prompt: str) -> str | None:
        """Run Claude Code CLI as a subprocess and return its output."""
        if not shutil.which(self.claude_bin):
            logger.error(f"Claude binary not found: {self.claude_bin}")
            return None

        try:
            proc = await asyncio.create_subprocess_exec(
                self.claude_bin,
                "--model",
                self.model,
                "--print",
                prompt,
                stdin=asyncio.subprocess.DEVNULL,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=self.timeout)
            if proc.returncode != 0:
                logger.error(f"Claude exited with code {proc.returncode}: {stderr.decode()[:200]}")
                return None
            return stdout.decode().strip() or None
        except TimeoutError:
            logger.error(f"Claude timed out after {self.timeout}s")
            proc.kill()
            return None
        except Exception as exc:
            logger.error(f"Claude error: {exc}")
            return None
