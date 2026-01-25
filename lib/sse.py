"""Server-Sent Events broadcasting for real-time dashboard updates.

This module provides a simple SSE broadcasting infrastructure for pushing
events to connected dashboard clients. Used for:
- Immediate session updates when Enter is pressed in WezTerm
- Priority invalidation notifications when turns complete
"""

import json
import queue
import threading
from typing import Generator

# Thread-safe list of connected client queues
_clients: list[queue.Queue] = []
_clients_lock = threading.Lock()


def add_client() -> queue.Queue:
    """Register a new SSE client.

    Returns:
        A queue to receive events from. The caller should iterate over
        this queue to get SSE formatted events.
    """
    q: queue.Queue = queue.Queue()
    with _clients_lock:
        _clients.append(q)
    return q


def remove_client(q: queue.Queue) -> None:
    """Unregister an SSE client.

    Args:
        q: The client's queue to remove
    """
    with _clients_lock:
        if q in _clients:
            _clients.remove(q)


def broadcast(event_type: str, data: dict) -> None:
    """Broadcast an event to all connected clients.

    Args:
        event_type: The event type (e.g., "session_update", "priorities_invalidated")
        data: Event payload as a dict
    """
    message = {"type": event_type, "data": data}
    with _clients_lock:
        for q in _clients:
            try:
                q.put_nowait(message)
            except queue.Full:
                pass  # Client queue full, skip this event


def event_stream(client_queue: queue.Queue) -> Generator[str, None, None]:
    """Generate SSE formatted events for a client.

    Yields SSE-formatted strings ready for HTTP response.
    Sends keepalive comments every 30 seconds to maintain connection.

    Args:
        client_queue: The client's event queue

    Yields:
        SSE formatted event strings
    """
    # Send initial keepalive immediately to establish the stream
    # This allows the browser's EventSource to transition to OPEN state
    yield ": connected\n\n"

    while True:
        try:
            message = client_queue.get(timeout=30)  # 30s keepalive interval
            yield f"data: {json.dumps(message)}\n\n"
        except queue.Empty:
            # Send SSE comment as keepalive (prevents connection timeout)
            yield ": keepalive\n\n"


def get_client_count() -> int:
    """Get the number of connected SSE clients.

    Returns:
        Number of active client connections
    """
    with _clients_lock:
        return len(_clients)
