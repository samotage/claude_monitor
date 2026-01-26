"""Flask application factory for Claude Headspace.

This module creates and configures the Flask application, wiring together
all the services from the new src/ architecture:

- AgentStore: Single source of truth for agents and tasks
- ConfigService: Configuration loading and migration
- EventBus: Real-time SSE event broadcasting
- NotificationService: macOS notifications
- InferenceService: OpenRouter API integration
- StateInterpreter: LLM-based state detection
- GoverningAgent: Agent orchestration

Usage:
    from src.app import create_app
    app = create_app()
    app.run(port=5050)
"""

import logging
import os
import threading
from pathlib import Path

from flask import Flask

from src.models import AppConfig
from src.routes import register_blueprints
from src.services import (
    AgentStore,
    GoverningAgent,
    HookReceiver,
    InferenceService,
    StateInterpreter,
    get_config_service,
    get_event_bus,
    get_notification_service,
)

logger = logging.getLogger(__name__)


def _load_dotenv() -> None:
    """Load environment variables from .env file if it exists."""
    env_file = Path(".env")
    if env_file.exists():
        with open(env_file) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    key = key.strip()
                    value = value.strip().strip('"').strip("'")
                    if key and key not in os.environ:
                        os.environ[key] = value


# Load environment variables from .env file
_load_dotenv()


def create_app(config_path: str = "config.yaml") -> Flask:
    """Create and configure the Flask application.

    Args:
        config_path: Path to the configuration file.

    Returns:
        Configured Flask application.
    """
    # Load configuration
    config_service = get_config_service(config_path)
    config = config_service.get_config()

    # Create Flask app
    app = Flask(
        __name__,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config["TESTING"] = False

    # Store services on app for access in routes
    app.extensions["config"] = config
    app.extensions["config_service"] = config_service

    # Initialize core services
    _init_services(app, config)

    # Register route blueprints
    register_blueprints(app)

    # Add dashboard route
    @app.route("/")
    def index():
        from flask import render_template

        return render_template(
            "index.html",
            scan_interval=config.scan_interval,
        )

    # Add legacy compatibility routes if needed
    _add_legacy_routes(app, config)

    return app


def _init_services(app: Flask, config: AppConfig) -> None:
    """Initialize all services and wire them together.

    Args:
        app: Flask application.
        config: Application configuration.
    """
    # Get API key from environment
    api_key = os.environ.get("OPENROUTER_API_KEY")

    # Data directory for persistence
    data_dir = Path("data")
    data_dir.mkdir(exist_ok=True)

    # Create AgentStore
    agent_store = AgentStore(data_dir=str(data_dir))
    app.extensions["agent_store"] = agent_store

    # Create EventBus
    event_bus = get_event_bus()
    app.extensions["event_bus"] = event_bus

    # Create InferenceService
    inference_service = InferenceService(
        api_key=api_key,
        config=config.inference,
    )
    app.extensions["inference_service"] = inference_service

    # Create StateInterpreter
    state_interpreter = StateInterpreter(
        inference_service=inference_service,
    )
    app.extensions["state_interpreter"] = state_interpreter

    # Create NotificationService
    notification_service = get_notification_service()
    notification_service.enabled = config.notifications.enabled
    app.extensions["notification_service"] = notification_service

    # Create WezTerm backend
    if config.terminal_backend == "wezterm":
        from src.backends.wezterm import get_wezterm_backend

        backend = get_wezterm_backend()
        app.extensions["terminal_backend"] = backend
    else:
        from src.backends.tmux import get_tmux_backend

        backend = get_tmux_backend()
        app.extensions["terminal_backend"] = backend

    # Create GoverningAgent (main orchestrator)
    governing_agent = GoverningAgent(
        agent_store=agent_store,
        backend=backend,
        state_interpreter=state_interpreter,
        inference_service=inference_service,
        event_bus=event_bus,
    )
    app.extensions["governing_agent"] = governing_agent

    # Create HookReceiver for Claude Code lifecycle hooks
    hook_receiver = HookReceiver(
        agent_store=agent_store,
        event_bus=event_bus,
        governing_agent=governing_agent,
    )
    app.extensions["hook_receiver"] = hook_receiver

    logger.info("Services initialized")


def _add_legacy_routes(app: Flask, config: AppConfig) -> None:
    """Add legacy routes for backward compatibility.

    These routes map old API endpoints to the new architecture.
    They will be deprecated in a future release.

    Args:
        app: Flask application.
        config: Application configuration.
    """
    from flask import jsonify

    @app.route("/api/sessions")
    def legacy_sessions():
        """Legacy sessions endpoint - redirects to agents."""
        agent_store = app.extensions.get("agent_store")
        if not agent_store:
            return jsonify({"sessions": [], "projects": []})

        agents = agent_store.list_agents()
        sessions = []
        for agent in agents:
            task = agent_store.get_current_task(agent.id)
            sessions.append(_agent_to_session(agent, task, agent_store))

        projects = [{"name": p.name, "path": p.path} for p in config.projects]

        return jsonify({"sessions": sessions, "projects": projects})

    @app.route("/api/focus/<pid>", methods=["POST"])
    def legacy_focus_pid(pid):  # noqa: ARG001 - pid required for URL route
        """Legacy focus by PID - maps to terminal backend.

        Note: PID-based focus is deprecated. Use session name instead.
        """
        backend = app.extensions.get("terminal_backend")
        if not backend or not backend.is_available():
            return jsonify({"success": False, "error": "Backend unavailable"})

        return jsonify({"success": False, "error": "PID-based focus deprecated, use session name"})

    @app.route("/api/focus/session/<session_name>", methods=["POST"])
    def legacy_focus_session(session_name):
        """Legacy focus by session name - maps to terminal backend."""
        backend = app.extensions.get("terminal_backend")
        if not backend or not backend.is_available():
            return jsonify({"success": False, "error": "Backend unavailable"})

        if hasattr(backend, "focus_by_name"):
            success = backend.focus_by_name(session_name)
        else:
            success = backend.focus_pane(session_name)

        return jsonify({"success": success})


def _agent_to_session(agent, task, agent_store) -> dict:
    """Convert agent to legacy session format.

    Args:
        agent: Agent object.
        task: Current task (may be None).
        agent_store: AgentStore for lookups.

    Returns:
        Session dictionary in legacy format.
    """
    from datetime import datetime

    task_state = task.state.value if task else "idle"

    # Map 5-state to legacy 3-state
    legacy_state_map = {
        "idle": "idle",
        "commanded": "processing",
        "processing": "processing",
        "awaiting_input": "input_needed",
        "complete": "idle",
    }

    # Get project info
    project = agent_store.get_project(agent.project_id) if agent.project_id else None
    project_name = project.name if project else "Unknown"

    # Calculate elapsed time
    elapsed = ""
    if agent.created_at:
        delta = datetime.now() - agent.created_at
        hours = int(delta.total_seconds() // 3600)
        minutes = int((delta.total_seconds() % 3600) // 60)
        elapsed = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

    return {
        "uuid": agent.id,
        "uuid_short": agent.id[:8],
        "project_name": project_name,
        "activity_state": legacy_state_map.get(task_state, "idle"),
        "status": "active" if task else "completed",
        "elapsed": elapsed,
        "started_at": agent.created_at.isoformat() if agent.created_at else None,
        "pid": None,  # Deprecated
        "session_type": "wezterm",
        "tmux_session": agent.session_name,
    }


def start_background_tasks(app: Flask) -> None:
    """Start background tasks for the application.

    Args:
        app: Flask application.
    """
    governing_agent = app.extensions.get("governing_agent")
    config = app.extensions.get("config")

    if governing_agent and config:
        scan_interval = config.scan_interval

        def scan_loop():
            """Background scan loop."""
            import time

            while True:
                try:
                    governing_agent.scan_once()
                except Exception as e:
                    logger.error(f"Scan error: {e}")
                time.sleep(scan_interval)

        thread = threading.Thread(target=scan_loop, daemon=True)
        thread.start()
        logger.info(f"Started background scan thread (interval: {scan_interval}s)")


# Module-level app for CLI usage
def main():
    """Run the Flask application."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )

    app = create_app()
    config = app.extensions.get("config")

    # Start background tasks
    start_background_tasks(app)

    # Run the server
    port = config.port if config else 5050
    debug = config.debug if config else False

    logger.info(f"Starting Claude Headspace on port {port}")
    app.run(host="0.0.0.0", port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    main()
