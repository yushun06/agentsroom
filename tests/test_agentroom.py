from __future__ import annotations

import asyncio
import tempfile
import unittest
from pathlib import Path

from agentroom.adapters.base import BaseAdapter, ConcurrencyPool, ModelCache, PromptCompiler
from agentroom.core import AgentroomStore
from agentroom.delivery.dlq import enqueue_dlq, read_dlq_entries, retry_dlq
from agentroom.delivery.poller import poll_unread
from agentroom.delivery.webhook import fan_out, get_subscribers_for_room
from agentroom.lifecycle import AgentroomLifecycle
from agentroom.observability.logger import JSONFormatter, get_logger, setup_logging
from agentroom.observability.metrics import Counter, Gauge, Histogram, Metrics, Timer
from agentroom.schemas import SchemaError, create_envelope, validate_a2a_payload


class AgentroomTests(unittest.TestCase):
    def make_lifecycle(self) -> AgentroomLifecycle:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        return AgentroomLifecycle(AgentroomStore(Path(self.tmp.name) / "agentroom", max_segment_messages=2))

    def test_create_discover_post_and_list_room_messages(self) -> None:
        lifecycle = self.make_lifecycle()
        room = lifecycle.create_room("project:demo", topic="Demo")
        self.assertEqual(room["status"], "active")
        self.assertEqual(lifecycle.discover_rooms(prefix="project:")[0]["roomId"], "project:demo")

        result = lifecycle.post_text(
            "project:demo",
            text="hello",
            agent_id="worker-a",
            role="worker",
            adapter="codex",
        )
        self.assertEqual(result["message"]["payload"]["text"], "hello")

        messages = lifecycle.store.list_messages("project:demo")
        self.assertEqual([message["payload"].get("type") for message in messages[:1]], ["room.created"])
        self.assertEqual(messages[-1]["payload"]["text"], "hello")

    def test_unread_cursor_can_mark_messages_read(self) -> None:
        lifecycle = self.make_lifecycle()
        lifecycle.create_room("project:demo")
        lifecycle.post_text("project:demo", text="one", agent_id="worker-a", role="worker", adapter="codex")
        first = lifecycle.store.list_unread("reviewer-a", "project:demo", mark_read=True)
        self.assertEqual(len(first), 2)
        self.assertEqual(lifecycle.store.list_unread("reviewer-a", "project:demo"), [])

        lifecycle.post_text("project:demo", text="two", agent_id="worker-a", role="worker", adapter="codex")
        second = lifecycle.store.list_unread("reviewer-a", "project:demo", mark_read=False)
        self.assertEqual([message["payload"].get("text") for message in second], ["two"])

    def test_segment_rotation_records_cursor_segment(self) -> None:
        lifecycle = self.make_lifecycle()
        lifecycle.create_room("project:demo")
        lifecycle.post_text("project:demo", text="one", agent_id="worker-a", role="worker", adapter="codex")
        result = lifecycle.post_text("project:demo", text="two", agent_id="worker-a", role="worker", adapter="codex")
        self.assertEqual(result["cursor"]["segment"], 2)
        self.assertEqual(len(lifecycle.store.room_segments("project:demo")), 2)

    def test_agent_register_join_heartbeat_leave(self) -> None:
        lifecycle = self.make_lifecycle()
        lifecycle.create_room("project:demo")
        agent = lifecycle.register_agent(
            "reviewer-a",
            role="reviewer",
            adapter="codex",
            capabilities=["review"],
            webhook="http://example.test/webhook",
        )
        self.assertEqual(agent["status"], "online")
        self.assertEqual(lifecycle.list_agents(role="reviewer")[0]["agentId"], "reviewer-a")

        presence = lifecycle.join_room("project:demo", "reviewer-a", role="reviewer", adapter="codex", capabilities=["review"])
        self.assertEqual(presence["rooms"], ["project:demo"])
        self.assertEqual(lifecycle.heartbeat("reviewer-a", status="busy")["status"], "busy")
        self.assertEqual(lifecycle.leave_room("project:demo", "reviewer-a", role="reviewer", adapter="codex")["rooms"], [])

    def test_archive_blocks_future_user_posts(self) -> None:
        lifecycle = self.make_lifecycle()
        lifecycle.create_room("project:demo")
        archived = lifecycle.archive_room("project:demo")
        self.assertEqual(archived["status"], "archived")
        with self.assertRaises(ValueError):
            lifecycle.post_text("project:demo", text="late", agent_id="worker-a", role="worker", adapter="codex")

    def test_a2a_schema_validation(self) -> None:
        validate_a2a_payload({"schema": "agentroom.a2a.v1", "type": "review", "intent": "request", "summary": "Review code"})
        with self.assertRaises(SchemaError):
            validate_a2a_payload({"schema": "agentroom.a2a.v1", "type": "review"})

    def test_envelope_trace_is_added(self) -> None:
        envelope = create_envelope(
            "project:demo",
            {"agentId": "worker-a", "role": "worker", "adapter": "codex"},
            {"text": "hello"},
        )
        self.assertTrue(envelope["metadata"]["traceId"].startswith("trace_"))

    def test_presence_path_safety(self) -> None:
        """Agent IDs with path separators must not escape presence_dir."""
        lifecycle = self.make_lifecycle()
        lifecycle.create_room("project:demo")
        # This agent ID contains a path traversal attempt
        agent = lifecycle.register_agent(
            "../registry", role="attacker", adapter="test",
        )
        # The presence file should be inside presence_dir, not outside
        presence_dir = lifecycle.store.presence_dir
        for path in presence_dir.iterdir():
            self.assertEqual(path.resolve().parent, presence_dir.resolve(),
                             f"presence file escaped directory: {path}")
        # Verify the agent can be looked up and presence read correctly
        presence = lifecycle.join_room("project:demo", "../registry", role="attacker", adapter="test")
        self.assertIn("project:demo", presence["rooms"])


class DLQTests(unittest.TestCase):
    def test_enqueue_and_read_dlq(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        message = {"id": "msg_test123", "roomId": "room1", "format": "plain_text",
                    "from": {"agentId": "a", "role": "r", "adapter": "x"}, "payload": {"text": "hi"}}
        enqueue_dlq(tmp.name, "agent-1", message, error="timeout")
        entries = read_dlq_entries(tmp.name)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]["agentId"], "agent-1")
        self.assertEqual(entries[0]["attempts"], 1)
        self.assertEqual(entries[0]["lastError"], "timeout")

    def test_dlq_retry_marks_unhealthy(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        message = {"id": "msg_retry1", "roomId": "room1", "format": "plain_text",
                    "from": {"agentId": "a", "role": "r", "adapter": "x"}, "payload": {"text": "hi"}}
        # Enqueue with max retries already reached
        from agentroom.delivery.dlq import _dlq_path, _update_dlq_entry
        path = enqueue_dlq(tmp.name, "agent-1", message, error="fail1")
        entry = {"agentId": "agent-1", "messageId": "msg_retry1", "payload": message,
                 "attempts": 3, "lastError": "fail", "updatedAt": "now",
                 "webhook": "http://127.0.0.1:1/nonexistent"}
        _update_dlq_entry(tmp.name, entry, error="fail2")
        # After 4 attempts total, retry should mark unhealthy
        marked_unhealthy = []
        async def mark_fn(agent_id: str) -> None:
            marked_unhealthy.append(agent_id)
        asyncio.run(retry_dlq(tmp.name, mark_unhealthy_fn=mark_fn, webhook_timeout=0.5))
        # The entry should be removed (exhausted)
        entries = read_dlq_entries(tmp.name)
        self.assertEqual(len(entries), 0)
        self.assertIn("agent-1", marked_unhealthy)


class WebhookTests(unittest.TestCase):
    def test_get_subscribers_for_room(self) -> None:
        registry = {
            "agents": {
                "a1": {"agentId": "a1", "webhook": "http://a1.test/hook", "status": "online"},
                "a2": {"agentId": "a2", "webhook": None, "status": "online"},
                "a3": {"agentId": "a3", "webhook": "http://a3.test/hook", "status": "offline"},
            }
        }
        subs = get_subscribers_for_room(registry, "room1")
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0]["agentId"], "a1")

    def test_get_subscribers_filters_by_room_membership(self) -> None:
        """When store is provided, only agents present in the room receive webhooks."""
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = AgentroomStore(Path(tmp.name) / "agentroom")
        lifecycle = AgentroomLifecycle(store)
        lifecycle.create_room("room:alpha")
        lifecycle.create_room("room:beta")
        lifecycle.register_agent("a1", role="worker", adapter="codex", webhook="http://a1.test/hook")
        lifecycle.register_agent("a2", role="worker", adapter="codex", webhook="http://a2.test/hook")
        lifecycle.join_room("room:alpha", "a1", role="worker", adapter="codex")
        lifecycle.join_room("room:beta", "a2", role="worker", adapter="codex")

        registry = store.read_json(store.registry_path, {"agents": {}})
        # a1 is in alpha, not beta
        alpha_subs = get_subscribers_for_room(registry, "room:alpha", store=store)
        self.assertEqual([s["agentId"] for s in alpha_subs], ["a1"])
        beta_subs = get_subscribers_for_room(registry, "room:beta", store=store)
        self.assertEqual([s["agentId"] for s in beta_subs], ["a2"])

    def test_get_subscribers_excludes_sender(self) -> None:
        registry = {
            "agents": {
                "a1": {"agentId": "a1", "webhook": "http://a1.test/hook", "status": "online"},
                "a2": {"agentId": "a2", "webhook": "http://a2.test/hook", "status": "online"},
            }
        }
        subs = get_subscribers_for_room(registry, "room1", exclude_agent="a1")
        self.assertEqual(len(subs), 1)
        self.assertEqual(subs[0]["agentId"], "a2")

    def test_fan_out_to_invalid_url(self) -> None:
        message = {"id": "msg_test", "roomId": "r1", "format": "plain_text",
                    "from": {"agentId": "a", "role": "r", "adapter": "x"}, "payload": {"text": "hi"}}
        subs = [{"agentId": "bad-agent", "webhook": "http://127.0.0.1:1/nonexistent"}]
        results = asyncio.run(fan_out(message, subs, timeout=0.5))
        self.assertEqual(len(results), 1)
        self.assertIsNotNone(results[0])


class MetricsTests(unittest.TestCase):
    def test_counter(self) -> None:
        c = Counter("test_counter", "A test counter")
        c.inc()
        c.inc(2)
        output = c.collect()
        self.assertIn("test_counter 3", output)
        self.assertIn("# TYPE test_counter counter", output)

    def test_counter_with_labels(self) -> None:
        c = Counter("test_labeled", "Labeled", labels=("status",))
        c.inc(labels={"status": "ok"})
        c.inc(2, labels={"status": "ok"})
        c.inc(labels={"status": "err"})
        output = c.collect()
        self.assertIn('status="ok"} 3', output)
        self.assertIn('status="err"} 1', output)

    def test_gauge(self) -> None:
        g = Gauge("test_gauge", "A test gauge")
        g.set(42)
        output = g.collect()
        self.assertIn("test_gauge 42", output)
        g.inc(8)
        self.assertIn("test_gauge 50", g.collect())

    def test_histogram(self) -> None:
        h = Histogram("test_hist", "A test hist", buckets=(0.1, 0.5, 1.0))
        h.observe(0.3)
        h.observe(0.7)
        output = h.collect()
        self.assertIn("# TYPE test_hist histogram", output)
        self.assertIn("test_hist_count 2", output)

    def test_histogram_buckets_are_valid_cumulative(self) -> None:
        """Cumulative bucket values must be monotonically non-decreasing and <= _count."""
        h = Histogram("test_bucket_h", "Bucket test", buckets=(0.1, 0.5, 1.0))
        h.observe(0.05)   # falls in 0.1
        h.observe(0.3)    # falls in 0.5
        h.observe(0.7)    # falls in 1.0
        h.observe(5.0)    # exceeds all, only +Inf
        output = h.collect()
        # Parse bucket lines
        import re
        buckets = {}
        for match in re.finditer(r'_bucket\{le="([^"]+)"\} (\d+)', output):
            le, count = match.group(1), int(match.group(2))
            buckets[le] = count
        # +Inf must equal total count
        self.assertEqual(buckets.get("+Inf"), 4)
        # Cumulative: each le >= previous
        prev = 0
        for le_val in ["0.1", "0.5", "1.0", "+Inf"]:
            self.assertGreaterEqual(buckets[le_val], prev,
                                    f"le={le_val}={buckets[le_val]} < prev={prev}")
            prev = buckets[le_val]
        # No bucket exceeds total
        for le_val, count in buckets.items():
            self.assertLessEqual(count, 4, f"le={le_val}={count} > total=4")

    def test_timer(self) -> None:
        h = Histogram("test_timer_h", "Timer test")
        import time
        with Timer(h):
            time.sleep(0.01)
        self.assertEqual(h._total, 1)
        self.assertGreater(h._sum, 0)

    def test_metrics_collect(self) -> None:
        m = Metrics()
        m.messages_total.inc()
        output = m.collect()
        self.assertIn("agentroom_messages_total", output)
        self.assertIn("agentroom_active_rooms", output)


class LoggingTests(unittest.TestCase):
    def test_json_formatter(self) -> None:
        import logging
        formatter = JSONFormatter()
        record = logging.LogRecord("agentroom.core", logging.INFO, "", 0, "append message", (), None)
        record.roomId = "room1"
        output = formatter.format(record)
        import json
        data = json.loads(output)
        self.assertEqual(data["component"], "agentroom.core")
        self.assertEqual(data["event"], "append message")
        self.assertEqual(data["roomId"], "room1")
        self.assertIn("ts", data)

    def test_setup_and_get_logger(self) -> None:
        logger = setup_logging("WARNING")
        self.assertEqual(logger.level, 30)  # WARNING
        child = get_logger("dlq")
        self.assertEqual(child.name, "agentroom.dlq")


class AdapterBaseTests(unittest.TestCase):
    def test_model_cache_eviction(self) -> None:
        cache = ModelCache(max_sessions=2)
        cache.get_or_create("a1", "r1", lambda: "s1")
        cache.get_or_create("a2", "r2", lambda: "s2")
        cache.get_or_create("a3", "r3", lambda: "s3")  # should evict a1
        self.assertEqual(len(cache._cache), 2)
        self.assertNotIn(("a1", "r1"), cache._cache)

    def test_prompt_compiler(self) -> None:
        compiler = PromptCompiler()
        result = compiler.compile(
            {"agentId": "test-bot", "role": "tester"},
            [{"payload": {"text": "hello"}}],
        )
        self.assertIn("test-bot", result["system"])
        self.assertEqual(len(result["messages"]), 1)

    def test_concurrency_pool(self) -> None:
        pool = ConcurrencyPool(max_concurrent=2)
        results = []

        async def task(n: int) -> int:
            return n * 2

        async def run() -> None:
            r = await pool.execute(task, 5)
            results.append(r)

        asyncio.run(run())
        self.assertEqual(results, [10])

    def test_base_adapter_raises_not_implemented(self) -> None:
        adapter = BaseAdapter("test", "agent", ModelCache(), ConcurrencyPool())
        with self.assertRaises(NotImplementedError):
            asyncio.run(adapter.process("room1", []))


class PollerTests(unittest.TestCase):
    def test_poll_unread(self) -> None:
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        store = AgentroomStore(Path(tmp.name) / "agentroom")
        lifecycle = AgentroomLifecycle(store)
        lifecycle.create_room("poll:room")
        lifecycle.post_text("poll:room", text="msg1", agent_id="w", role="worker", adapter="codex")
        result = poll_unread(store, "reader-1", "poll:room", mark_read=True)
        self.assertEqual(len(result), 2)  # room.created + text


if __name__ == "__main__":
    unittest.main()
