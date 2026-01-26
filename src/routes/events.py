"""Event routes for Claude Headspace.

Provides Server-Sent Events (SSE) endpoint for real-time updates.
"""

from flask import Blueprint, Response

from src.services.event_bus import get_event_bus

events_bp = Blueprint("events", __name__)


@events_bp.route("/events")
def sse_events():
    """Server-Sent Events endpoint for real-time updates.

    Clients can subscribe to receive events such as:
    - agent_updated: When an agent's state changes
    - task_state_changed: When a task transitions to a new state
    - priorities_computed: When priorities are recalculated
    - priorities_invalidated: When priorities need recalculation

    Returns:
        SSE stream with events in format:
        event: <event_type>
        data: <json_payload>
    """
    event_bus = get_event_bus()

    def generate():
        """Generate SSE events from the event bus."""
        yield from event_bus.get_sse_stream()

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@events_bp.route("/events/test", methods=["POST"])
def test_event():
    """Emit a test event to verify SSE is working.

    Returns:
        JSON confirmation that the event was emitted.
    """
    from flask import jsonify

    event_bus = get_event_bus()
    event_bus.emit("test", {"message": "Test event from API"})

    return jsonify({"status": "emitted", "event_type": "test"})


@events_bp.route("/events/hook", methods=["POST"])
def hook_event():
    """Receive events from WezTerm Lua hooks.

    This endpoint allows WezTerm Lua hooks to push events to Claude Headspace
    for event-driven state detection.

    Expected JSON payload:
        {
            "event_type": "state_changed" | "pane_focused" | "user_var_changed" | "bell",
            "data": {
                "pane_id": <int>,
                "session_id": <str>,
                ...event-specific data...
            },
            "timestamp": <unix_timestamp>
        }

    Supported event types:
        - state_changed: Terminal content indicates a state change
        - pane_focused: User focused a Claude session pane
        - user_var_changed: A Claude-related user variable changed
        - bell: Terminal bell was triggered
        - user_input: User pressed Enter in a Claude session

    Returns:
        JSON confirmation that the event was received.
    """
    import logging

    from flask import current_app, jsonify, request

    logger = logging.getLogger(__name__)

    data = request.get_json()
    if not data:
        return jsonify({"error": "No JSON payload"}), 400

    event_type = data.get("event_type")
    event_data = data.get("data", {})

    if not event_type:
        return jsonify({"error": "Missing event_type"}), 400

    logger.info(f"Hook event received: {event_type} - {event_data}")

    # Emit the event to the event bus
    event_bus = get_event_bus()
    event_bus.emit(f"hook_{event_type}", event_data)

    # Handle specific event types
    if event_type == "state_changed":
        # Map detected state to task state machine triggers
        current_state = event_data.get("current_state")
        session_id = event_data.get("session_id")

        if current_state and session_id:
            # Get agent store from app
            agent_store = current_app.extensions.get("agent_store")
            if agent_store:
                # Find agent by session name
                agents = agent_store.list_agents()
                for agent in agents:
                    if agent.session_name == session_id:
                        # Emit state hint event for GoverningAgent to process
                        event_bus.emit(
                            "state_hint",
                            {
                                "agent_id": agent.id,
                                "detected_state": current_state,
                                "source": "wezterm_hook",
                            },
                        )
                        break

    return jsonify(
        {
            "status": "received",
            "event_type": event_type,
        }
    )
