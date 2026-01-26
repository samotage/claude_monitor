"""Tests for EventBus."""

import threading
import time

import pytest

from src.services.event_bus import Event, EventBus, get_event_bus, reset_event_bus


@pytest.fixture
def event_bus():
    """Create an EventBus instance."""
    return EventBus(buffer_size=10)


@pytest.fixture(autouse=True)
def reset_global_bus():
    """Reset the global event bus before and after each test."""
    reset_event_bus()
    yield
    reset_event_bus()


class TestEvent:
    """Tests for Event dataclass."""

    def test_create_event(self):
        """Test basic Event creation."""
        event = Event(event_type="test", data={"key": "value"})
        assert event.event_type == "test"
        assert event.data == {"key": "value"}
        assert event.timestamp is not None

    def test_to_sse_basic(self):
        """Test SSE formatting."""
        event = Event(event_type="test", data={"key": "value"}, id="123")
        sse = event.to_sse()

        assert "event: test" in sse
        assert 'data: {"key": "value"}' in sse
        assert "id: 123" in sse
        assert sse.endswith("\n\n")

    def test_to_sse_without_id(self):
        """Test SSE formatting without ID."""
        event = Event(event_type="test", data={"key": "value"})
        sse = event.to_sse()

        assert "event: test" in sse
        assert "id:" not in sse


class TestEventBusSubscription:
    """Tests for EventBus subscription."""

    def test_subscribe_and_receive(self, event_bus):
        """Events are delivered to subscribers."""
        events = []
        event_bus.subscribe("test", lambda e: events.append(e))
        event_bus.emit("test", {"key": "value"})

        assert len(events) == 1
        assert events[0].event_type == "test"
        assert events[0].data == {"key": "value"}

    def test_subscribe_to_specific_type(self, event_bus):
        """Subscribers only receive events of subscribed type."""
        events = []
        event_bus.subscribe("type_a", lambda e: events.append(e))

        event_bus.emit("type_a", {"a": 1})
        event_bus.emit("type_b", {"b": 2})

        assert len(events) == 1
        assert events[0].data == {"a": 1}

    def test_wildcard_subscriber(self, event_bus):
        """Wildcard subscribers receive all events."""
        events = []
        event_bus.subscribe("*", lambda e: events.append(e))

        event_bus.emit("type_a", {"a": 1})
        event_bus.emit("type_b", {"b": 2})

        assert len(events) == 2

    def test_unsubscribe(self, event_bus):
        """Unsubscribe removes a listener."""
        events = []

        def callback(e):
            events.append(e)

        event_bus.subscribe("test", callback)
        event_bus.unsubscribe("test", callback)
        event_bus.emit("test", {"key": "value"})

        assert len(events) == 0

    def test_multiple_subscribers(self, event_bus):
        """Multiple subscribers receive the same event."""
        events_a = []
        events_b = []
        event_bus.subscribe("test", lambda e: events_a.append(e))
        event_bus.subscribe("test", lambda e: events_b.append(e))
        event_bus.emit("test", {"key": "value"})

        assert len(events_a) == 1
        assert len(events_b) == 1

    def test_subscriber_error_doesnt_break_others(self, event_bus):
        """Errors in one subscriber don't affect others."""
        events = []

        def bad_callback(e):
            raise RuntimeError("Callback error")

        event_bus.subscribe("test", bad_callback)
        event_bus.subscribe("test", lambda e: events.append(e))
        event_bus.emit("test", {"key": "value"})

        assert len(events) == 1


class TestEventBusEmit:
    """Tests for EventBus emit."""

    def test_emit_returns_event(self, event_bus):
        """emit() returns the created Event."""
        event = event_bus.emit("test", {"key": "value"})

        assert isinstance(event, Event)
        assert event.event_type == "test"
        assert event.id is not None

    def test_emit_assigns_sequential_ids(self, event_bus):
        """Events get sequential IDs."""
        e1 = event_bus.emit("test", {"n": 1})
        e2 = event_bus.emit("test", {"n": 2})
        e3 = event_bus.emit("test", {"n": 3})

        assert int(e1.id) < int(e2.id) < int(e3.id)


class TestEventBuffer:
    """Tests for event buffering."""

    def test_events_buffered(self, event_bus):
        """Events are added to buffer."""
        event_bus.emit("test", {"n": 1})
        event_bus.emit("test", {"n": 2})

        events = event_bus.get_buffered_events()
        assert len(events) == 2

    def test_buffer_size_limit(self, event_bus):
        """Buffer respects size limit."""
        # Buffer size is 10
        for i in range(15):
            event_bus.emit("test", {"n": i})

        events = event_bus.get_buffered_events()
        assert len(events) == 10
        # Should have the last 10 events
        assert events[0].data["n"] == 5

    def test_get_buffered_events_since_id(self, event_bus):
        """get_buffered_events filters by since_id."""
        event_bus.emit("test", {"n": 1})
        event_bus.emit("test", {"n": 2})
        e3 = event_bus.emit("test", {"n": 3})

        events = event_bus.get_buffered_events(since_id=e3.id)
        assert len(events) == 0

        events = event_bus.get_buffered_events(since_id="1")
        assert len(events) == 2

    def test_get_buffered_events_by_type(self, event_bus):
        """get_buffered_events filters by event_type."""
        event_bus.emit("type_a", {"a": 1})
        event_bus.emit("type_b", {"b": 2})
        event_bus.emit("type_a", {"a": 3})

        events = event_bus.get_buffered_events(event_type="type_a")
        assert len(events) == 2

    def test_clear_buffer(self, event_bus):
        """clear_buffer removes all buffered events."""
        event_bus.emit("test", {"n": 1})
        event_bus.clear_buffer()

        assert event_bus.get_buffered_events() == []


class TestSSEStream:
    """Tests for SSE streaming."""

    def test_sse_stream_receives_events(self, event_bus):
        """SSE stream receives emitted events."""
        stream = event_bus.get_sse_stream(include_buffer=False, timeout=0.1)

        # Emit in a separate thread
        def emit_events():
            time.sleep(0.05)
            event_bus.emit("test", {"key": "value"})

        thread = threading.Thread(target=emit_events)
        thread.start()

        # Get first real event (skip keep-alive)
        for sse_msg in stream:
            if not sse_msg.startswith(":"):
                assert "event: test" in sse_msg
                break

        thread.join()

    def test_sse_stream_includes_buffer(self, event_bus):
        """SSE stream includes buffered events."""
        event_bus.emit("test", {"n": 1})
        event_bus.emit("test", {"n": 2})

        stream = event_bus.get_sse_stream(include_buffer=True, timeout=0.1)

        # First two messages should be buffered events
        msg1 = next(stream)
        msg2 = next(stream)

        assert '"n": 1' in msg1
        assert '"n": 2' in msg2

    def test_sse_stream_keep_alive(self, event_bus):
        """SSE stream sends keep-alive on timeout."""
        stream = event_bus.get_sse_stream(include_buffer=False, timeout=0.1)

        # First message should be keep-alive (no events)
        msg = next(stream)
        assert msg == ": keep-alive\n\n"

    def test_subscriber_count(self, event_bus):
        """subscriber_count tracks active SSE streams."""
        assert event_bus.subscriber_count == 0

        stream1 = event_bus.get_sse_stream(include_buffer=False, timeout=0.1)
        next(stream1)  # Start the generator
        assert event_bus.subscriber_count == 1

        stream2 = event_bus.get_sse_stream(include_buffer=False, timeout=0.1)
        next(stream2)
        assert event_bus.subscriber_count == 2


class TestGlobalEventBus:
    """Tests for global EventBus singleton."""

    def test_get_event_bus_returns_singleton(self):
        """get_event_bus returns the same instance."""
        bus1 = get_event_bus()
        bus2 = get_event_bus()
        assert bus1 is bus2

    def test_reset_event_bus(self):
        """reset_event_bus creates a new instance."""
        bus1 = get_event_bus()
        bus1.emit("test", {})
        reset_event_bus()
        bus2 = get_event_bus()

        assert bus1 is not bus2
        assert bus2.get_buffered_events() == []


class TestThreadSafety:
    """Tests for thread-safe operation."""

    def test_concurrent_emit(self, event_bus):
        """Concurrent emits don't cause issues."""
        events_received = []
        event_bus.subscribe("*", lambda e: events_received.append(e))

        def emit_many():
            for i in range(100):
                event_bus.emit("test", {"n": i})

        threads = [threading.Thread(target=emit_many) for _ in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Should have received all 500 events
        assert len(events_received) == 500

    def test_concurrent_subscribe_emit(self, event_bus):
        """Concurrent subscribes and emits don't cause issues."""
        events = []

        def subscribe_and_receive():
            event_bus.subscribe("test", lambda e: events.append(e))

        def emit_many():
            for i in range(50):
                event_bus.emit("test", {"n": i})
                time.sleep(0.001)

        t1 = threading.Thread(target=subscribe_and_receive)
        t2 = threading.Thread(target=emit_many)

        t1.start()
        t2.start()
        t1.join()
        t2.join()

        # Should have received at least some events
        assert len(events) > 0
