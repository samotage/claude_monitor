"""EventBus for SSE (Server-Sent Events) broadcasting.

Provides real-time dashboard updates without polling.
Events: agent_updated, priorities_changed, task_state_changed, headspace_changed
"""

import contextlib
import json
import queue
import threading
from collections.abc import Callable, Generator
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Event:
    """An event to be broadcast via SSE."""

    event_type: str
    data: dict
    timestamp: datetime = field(default_factory=datetime.now)
    id: str | None = None

    def to_sse(self) -> str:
        """Format the event as an SSE message.

        SSE format:
        event: <event_type>
        data: <json_data>
        id: <optional_id>

        """
        lines = []
        if self.event_type:
            lines.append(f"event: {self.event_type}")
        lines.append(f"data: {json.dumps(self.data)}")
        if self.id:
            lines.append(f"id: {self.id}")
        lines.append("")  # Empty line to end the event
        return "\n".join(lines) + "\n"


class EventBus:
    """Central event bus for broadcasting events to SSE clients.

    Features:
    - Subscribe/unsubscribe to specific event types
    - SSE stream generator for Flask routes
    - Event buffering for new subscribers
    - Thread-safe operation
    """

    def __init__(self, buffer_size: int = 100):
        """Initialize the EventBus.

        Args:
            buffer_size: Number of recent events to buffer for new subscribers.
        """
        self._buffer_size = buffer_size
        self._event_buffer: list[Event] = []
        self._subscribers: dict[str, list[Callable[[Event], None]]] = {}
        self._sse_queues: list[queue.Queue] = []
        self._lock = threading.Lock()
        self._event_counter = 0

    def subscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """Subscribe to an event type.

        Args:
            event_type: The event type to subscribe to, or "*" for all events.
            callback: Function to call when event occurs.
        """
        with self._lock:
            if event_type not in self._subscribers:
                self._subscribers[event_type] = []
            self._subscribers[event_type].append(callback)

    def unsubscribe(self, event_type: str, callback: Callable[[Event], None]) -> None:
        """Unsubscribe from an event type.

        Args:
            event_type: The event type to unsubscribe from.
            callback: The callback to remove.
        """
        with self._lock:
            if event_type in self._subscribers:
                self._subscribers[event_type] = [
                    cb for cb in self._subscribers[event_type] if cb != callback
                ]

    def emit(self, event_type: str, data: dict) -> Event:
        """Emit an event to all subscribers and SSE clients.

        Args:
            event_type: The type of event (e.g., "agent_updated").
            data: The event data.

        Returns:
            The created Event object.
        """
        with self._lock:
            self._event_counter += 1
            event = Event(
                event_type=event_type,
                data=data,
                id=str(self._event_counter),
            )

            # Add to buffer
            self._event_buffer.append(event)
            if len(self._event_buffer) > self._buffer_size:
                self._event_buffer = self._event_buffer[-self._buffer_size :]

            # Notify direct subscribers
            for callback in self._subscribers.get(event_type, []):
                with contextlib.suppress(Exception):
                    callback(event)

            # Notify wildcard subscribers
            for callback in self._subscribers.get("*", []):
                with contextlib.suppress(Exception):
                    callback(event)

            # Push to SSE queues
            dead_queues = []
            for q in self._sse_queues:
                try:
                    q.put_nowait(event)
                except queue.Full:
                    dead_queues.append(q)

            # Clean up dead queues
            for q in dead_queues:
                self._sse_queues.remove(q)

        return event

    def get_sse_stream(
        self,
        include_buffer: bool = True,
        timeout: float = 30.0,
    ) -> Generator[str, None, None]:
        """Get an SSE event stream generator.

        This generator yields SSE-formatted events as they occur.
        Use this with Flask's streaming response.

        Args:
            include_buffer: Whether to send buffered events first.
            timeout: Seconds to wait for events before sending a keep-alive.

        Yields:
            SSE-formatted event strings.
        """
        # Create a queue for this subscriber
        event_queue: queue.Queue = queue.Queue(maxsize=100)

        with self._lock:
            self._sse_queues.append(event_queue)

            # Send buffered events if requested
            if include_buffer:
                for event in self._event_buffer:
                    yield event.to_sse()

        try:
            while True:
                try:
                    event = event_queue.get(timeout=timeout)
                    yield event.to_sse()
                except queue.Empty:
                    # Send keep-alive comment to prevent timeout
                    yield ": keep-alive\n\n"
        finally:
            # Clean up when generator is closed
            with self._lock:
                if event_queue in self._sse_queues:
                    self._sse_queues.remove(event_queue)

    def get_buffered_events(
        self, since_id: str | None = None, event_type: str | None = None
    ) -> list[Event]:
        """Get buffered events, optionally filtered.

        Args:
            since_id: Only return events after this ID.
            event_type: Only return events of this type.

        Returns:
            List of matching events.
        """
        with self._lock:
            events = self._event_buffer.copy()

        # Filter by ID
        if since_id:
            try:
                since_num = int(since_id)
                events = [e for e in events if e.id and int(e.id) > since_num]
            except ValueError:
                pass

        # Filter by type
        if event_type:
            events = [e for e in events if e.event_type == event_type]

        return events

    def clear_buffer(self) -> None:
        """Clear the event buffer."""
        with self._lock:
            self._event_buffer.clear()

    @property
    def subscriber_count(self) -> int:
        """Get the number of active SSE subscribers."""
        with self._lock:
            return len(self._sse_queues)


# Singleton instance for the application
_event_bus: EventBus | None = None


def get_event_bus() -> EventBus:
    """Get the global EventBus instance."""
    global _event_bus
    if _event_bus is None:
        _event_bus = EventBus()
    return _event_bus


def reset_event_bus() -> None:
    """Reset the global EventBus (for testing)."""
    global _event_bus
    _event_bus = None
