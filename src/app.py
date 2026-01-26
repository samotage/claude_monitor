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

    # Add global error handlers
    _register_error_handlers(app)

    # Add dashboard route
    @app.route("/")
    def index():
        from flask import render_template

        return render_template(
            "index.html",
            scan_interval=config.scan_interval,
        )

    # Add logging popout route
    @app.route("/logging")
    def logging_popout():
        from flask import render_template

        return render_template(
            "logging.html",
            scan_interval=config.scan_interval,
        )

    # Add legacy compatibility routes if needed
    _add_legacy_routes(app, config)

    return app


def _register_error_handlers(app: Flask) -> None:
    """Register global error handlers for the application.

    These handlers prevent stack traces from leaking to clients and
    provide consistent error response formats.

    Args:
        app: Flask application.
    """
    from flask import jsonify, request

    @app.errorhandler(400)
    def bad_request(error):  # noqa: ARG001 - error param required by Flask
        """Handle 400 Bad Request errors."""
        return jsonify({"error": "Bad request"}), 400

    @app.errorhandler(404)
    def not_found(error):  # noqa: ARG001
        """Handle 404 Not Found errors."""
        return jsonify({"error": "Resource not found"}), 404

    @app.errorhandler(405)
    def method_not_allowed(error):  # noqa: ARG001
        """Handle 405 Method Not Allowed errors."""
        return jsonify({"error": "Method not allowed"}), 405

    @app.errorhandler(500)
    def internal_error(error):  # noqa: ARG001
        """Handle 500 Internal Server Error."""
        logger.exception("Internal server error")
        return jsonify({"error": "Internal server error"}), 500

    @app.errorhandler(Exception)
    def handle_exception(error):
        """Handle uncaught exceptions.

        Logs the full exception and returns a generic error to avoid
        leaking stack traces to clients.
        """
        logger.exception(f"Unhandled exception: {error}")
        return jsonify({"error": "Internal server error"}), 500

    @app.after_request
    def add_cors_headers(response):
        """Add CORS headers for localhost access.

        Allows cross-origin requests from localhost only.
        """
        # Only allow localhost origins
        origin = request.headers.get("Origin", "")
        if origin.startswith("http://localhost") or origin.startswith("http://127.0.0.1"):
            response.headers["Access-Control-Allow-Origin"] = origin
            response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, DELETE, OPTIONS"
            response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
        return response


def _register_projects_from_config(agent_store, config: AppConfig) -> None:
    """Register projects from config into the agent store.

    Creates Project objects for each configured project and adds them
    to the store if they don't already exist. Existing projects are
    updated with config values.

    Args:
        agent_store: The AgentStore to register projects with.
        config: Application configuration containing project list.
    """
    from src.models.project import Project

    for project_config in config.projects:
        # Check if project already exists (by name)
        existing = agent_store.get_project_by_name(project_config.name)

        if existing is None:
            # Create new project from config
            import uuid

            project = Project(
                id=str(uuid.uuid4()),
                name=project_config.name,
                path=project_config.path,
                goal=project_config.goal,
                git_repo_path=project_config.git_repo_path,
            )
            agent_store.add_project(project)
            logger.info(f"Registered project: {project_config.name}")
        else:
            # Update existing project with config values
            existing.path = project_config.path
            existing.goal = project_config.goal or existing.goal
            existing.git_repo_path = project_config.git_repo_path or existing.git_repo_path
            agent_store.update_project(existing)
            logger.debug(f"Updated project: {project_config.name}")


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

    # Register projects from config
    _register_projects_from_config(agent_store, config)

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

        backend = get_wezterm_backend(
            max_cache_size=config.wezterm.max_cache_size,
            max_lines=config.wezterm.max_lines,
        )
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
        config=config,
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
    elapsed_seconds = 0
    if agent.created_at:
        delta = datetime.now() - agent.created_at
        elapsed_seconds = delta.total_seconds()
        hours = int(elapsed_seconds // 3600)
        minutes = int((elapsed_seconds % 3600) // 60)
        elapsed = f"{hours}h {minutes}m" if hours > 0 else f"{minutes}m"

    # Get task details
    task_summary = task.summary if task else None
    priority_score = task.priority_score if task else None
    priority_rationale = task.priority_rationale if task else None
    command_summary = task.command_summary if task else None

    # Terminal session ID (used as pseudo-PID for legacy compatibility)
    terminal_id = agent.terminal_session_id
    try:
        pid = int(terminal_id) if terminal_id and terminal_id.isdigit() else None
    except (ValueError, AttributeError):
        pid = None

    return {
        "uuid": agent.id,
        "uuid_short": agent.id[:8],
        "project_name": project_name,
        "activity_state": legacy_state_map.get(task_state, "idle"),
        "status": "active" if task else "completed",
        "elapsed": elapsed,
        "elapsed_seconds": elapsed_seconds,
        "started_at": agent.created_at.isoformat() if agent.created_at else None,
        "pid": pid,
        "session_type": "wezterm",
        "tmux_session": agent.session_name,
        # Additional fields for frontend compatibility
        "task_summary": task_summary,
        "last_message": "",  # TODO: Populate from turn tracking when ported
        "turn_command": command_summary or "",  # Use command_summary as turn_command
        "priority_score": priority_score,
        "rationale": priority_rationale,
        "session_id": agent.terminal_session_id,
    }


def start_background_tasks(app: Flask) -> None:
    """Start background tasks for the application.

    Starts:
    - Agent polling loop (GoverningAgent)
    - Compression service background thread
    - Session sync service background thread

    Args:
        app: Flask application.
    """
    governing_agent = app.extensions.get("governing_agent")
    config = app.extensions.get("config")
    agent_store = app.extensions.get("agent_store")

    if governing_agent and config:
        scan_interval = config.scan_interval

        def scan_loop():
            """Background scan loop."""
            import time

            while True:
                try:
                    governing_agent.poll_agents()
                except Exception as e:
                    logger.error(f"Scan error: {e}")
                time.sleep(scan_interval)

        thread = threading.Thread(target=scan_loop, daemon=True)
        thread.start()
        logger.info(f"Started background scan thread (interval: {scan_interval}s)")

    # Start compression service background thread if enabled
    if config and agent_store:
        from src.services.compression_service import get_compression_service

        compression_service = get_compression_service(
            data_dir="data",
            compression_interval=300,  # 5 minutes default
        )

        def get_project_names():
            """Get list of project names for compression processing."""
            return [p.name for p in agent_store.list_projects()]

        compression_service.start_background_thread(get_project_names)
        app.extensions["compression_service"] = compression_service

    # Start session sync service background thread if enabled
    if config and config.session_sync.enabled and agent_store:
        from src.services.session_sync_service import get_session_sync_service

        session_sync_service = get_session_sync_service(
            data_dir="data",
            sync_interval=config.session_sync.interval,
            jsonl_tail_entries=config.session_sync.jsonl_tail_entries,
        )

        def get_active_sessions():
            """Get list of active agent sessions for sync."""
            agents = agent_store.list_agents()
            return [
                {
                    "uuid": a.id,
                    "id": a.id,
                    "project_id": a.project_id,
                }
                for a in agents
            ]

        session_sync_service.start_background_thread(get_active_sessions)
        app.extensions["session_sync_service"] = session_sync_service
        logger.info("Started session sync background thread")


# Module-level app for CLI usage
def main():
    """Run the Flask application."""
    # Enable DEBUG level for our modules to trace data flow
    logging.basicConfig(
        level=logging.DEBUG,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    )
    # Reduce noise from external libraries
    logging.getLogger("werkzeug").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)

    app = create_app()
    config = app.extensions.get("config")

    # Start background tasks
    start_background_tasks(app)

    # Run the server
    port = config.port if config else 5050
    debug = config.debug if config else False

    logger.info(f"Starting Claude Headspace on port {port} (localhost only)")
    # Security: Bind to localhost only - API should not be exposed to network
    app.run(host="127.0.0.1", port=port, debug=debug, threaded=True)


if __name__ == "__main__":
    main()
