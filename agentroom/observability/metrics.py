"""Prometheus-compatible metrics for Agentroom.

Uses a simple text-based collector that does not require the prometheus_client
library.  Exposes metrics via GET /metrics in the standard exposition format.
"""

from __future__ import annotations

import threading
import time
from typing import Any


class Counter:
    """A monotonically increasing counter."""

    def __init__(self, name: str, help_text: str, labels: tuple[str, ...] = ()) -> None:
        self.name = name
        self.help_text = help_text
        self.labels = labels
        self._value: float = 0
        self._label_values: dict[tuple[str, ...], float] = {}
        self._lock = threading.Lock()

    def inc(self, amount: float = 1, *, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            if labels and self.labels:
                key = tuple(labels.get(l, "") for l in self.labels)
                self._label_values[key] = self._label_values.get(key, 0) + amount
            else:
                self._value += amount

    def collect(self) -> str:
        lines = [f"# HELP {self.name} {self.help_text}", f"# TYPE {self.name} counter"]
        if self.labels and self._label_values:
            for key, value in sorted(self._label_values.items()):
                label_str = ",".join(f'{l}="{v}"' for l, v in zip(self.labels, key))
                lines.append(f"{self.name}{{{label_str}}} {value:.0f}")
        else:
            lines.append(f"{self.name} {self._value:.0f}")
        return "\n".join(lines) + "\n"


class Gauge:
    """A value that can go up or down."""

    def __init__(self, name: str, help_text: str, labels: tuple[str, ...] = ()) -> None:
        self.name = name
        self.help_text = help_text
        self.labels = labels
        self._value: float = 0
        self._label_values: dict[tuple[str, ...], float] = {}
        self._lock = threading.Lock()

    def set(self, value: float, *, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            if labels and self.labels:
                key = tuple(labels.get(l, "") for l in self.labels)
                self._label_values[key] = value
            else:
                self._value = value

    def inc(self, amount: float = 1, *, labels: dict[str, str] | None = None) -> None:
        with self._lock:
            if labels and self.labels:
                key = tuple(labels.get(l, "") for l in self.labels)
                self._label_values[key] = self._label_values.get(key, 0) + amount
            else:
                self._value += amount

    def dec(self, amount: float = 1, *, labels: dict[str, str] | None = None) -> None:
        self.inc(-amount, labels=labels)

    def collect(self) -> str:
        lines = [f"# HELP {self.name} {self.help_text}", f"# TYPE {self.name} gauge"]
        if self.labels and self._label_values:
            for key, value in sorted(self._label_values.items()):
                label_str = ",".join(f'{l}="{v}"' for l, v in zip(self.labels, key))
                lines.append(f"{self.name}{{{label_str}}} {value:.0f}")
        else:
            lines.append(f"{self.name} {self._value:.0f}")
        return "\n".join(lines) + "\n"


class Histogram:
    """A histogram for observing value distributions."""

    DEFAULT_BUCKETS = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0, 30.0, 60.0)

    def __init__(self, name: str, help_text: str, buckets: tuple[float, ...] = DEFAULT_BUCKETS) -> None:
        self.name = name
        self.help_text = help_text
        self.buckets = sorted(buckets)
        self._counts: dict[float, int] = {b: 0 for b in self.buckets}
        self._counts[float("inf")] = 0
        self._sum: float = 0
        self._total: int = 0
        self._lock = threading.Lock()

    def observe(self, value: float) -> None:
        with self._lock:
            self._sum += value
            self._total += 1
            # Increment only the tightest bucket the value falls into
            for b in self.buckets:
                if value <= b:
                    self._counts[b] += 1
                    break
            else:
                # Value exceeds all explicit buckets; only +Inf catches it
                pass

    def collect(self) -> str:
        lines = [f"# HELP {self.name} {self.help_text}", f"# TYPE {self.name} histogram"]
        cumulative = 0
        for b in self.buckets:
            cumulative += self._counts.get(b, 0)
            lines.append(f'{self.name}_bucket{{le="{b}"}} {cumulative}')
        lines.append(f'{self.name}_bucket{{le="+Inf"}} {self._total}')
        lines.append(f"{self.name}_count {self._total}")
        lines.append(f"{self.name}_sum {self._sum:.6f}")
        return "\n".join(lines) + "\n"


class Timer:
    """Context manager that records elapsed time into a Histogram."""

    def __init__(self, histogram: Histogram) -> None:
        self.histogram = histogram
        self._start: float = 0

    def __enter__(self) -> "Timer":
        self._start = time.monotonic()
        return self

    def __exit__(self, *args: Any) -> None:
        self.histogram.observe(time.monotonic() - self._start)


class Metrics:
    """Central registry of all Agentroom metrics."""

    def __init__(self) -> None:
        # Central node metrics
        self.messages_total = Counter("agentroom_messages_total", "Total messages appended")
        self.webhook_deliveries_total = Counter(
            "agentroom_webhook_deliveries_total",
            "Total webhook delivery attempts",
            labels=("status",),
        )
        self.dlq_retries_total = Counter("agentroom_dlq_retries_total", "Total DLQ retry attempts")
        self.active_rooms = Gauge("agentroom_active_rooms", "Number of active rooms")
        self.registered_agents = Gauge("agentroom_registered_agents", "Number of registered agents")
        self.healthy_agents = Gauge("agentroom_healthy_agents", "Number of healthy agents")
        self.dlq_depth = Gauge("agentroom_dlq_depth", "DLQ entries per agent", labels=("agent",))
        self.message_append_duration = Histogram("agentroom_message_append_duration_seconds", "Message append duration")
        self.webhook_delivery_duration = Histogram("agentroom_webhook_delivery_duration_seconds", "Webhook delivery duration")
        self.segment_size_bytes = Gauge("agentroom_segment_size_bytes", "Current active segment size")

        # Agent node metrics
        self.adapter_llm_duration = Histogram("agentroom_adapter_llm_duration_seconds", "LLM call duration")
        self.adapter_prompt_tokens = Counter("agentroom_adapter_prompt_tokens_total", "Total prompt tokens sent")
        self.adapter_cache_hits = Counter("agentroom_adapter_cache_hits_total", "Model cache hits")
        self.adapter_cache_misses = Counter("agentroom_adapter_cache_misses_total", "Model cache misses")
        self.adapter_pool_waiting = Gauge("agentroom_adapter_concurrency_pool_waiting", "Threads waiting in pool")

    def collect(self) -> str:
        """Collect all metrics in Prometheus exposition format."""
        parts = [
            self.messages_total,
            self.webhook_deliveries_total,
            self.dlq_retries_total,
            self.active_rooms,
            self.registered_agents,
            self.healthy_agents,
            self.dlq_depth,
            self.message_append_duration,
            self.webhook_delivery_duration,
            self.segment_size_bytes,
            self.adapter_llm_duration,
            self.adapter_prompt_tokens,
            self.adapter_cache_hits,
            self.adapter_cache_misses,
            self.adapter_pool_waiting,
        ]
        return "".join(m.collect() for m in parts)


# Global singleton
metrics = Metrics()
