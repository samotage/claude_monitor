"""Flask routes for Claude Headspace."""

from src.routes.agents import agents_bp
from src.routes.events import events_bp
from src.routes.headspace import headspace_bp
from src.routes.hooks import hooks_bp
from src.routes.notifications import notifications_bp
from src.routes.priorities import priorities_bp
from src.routes.projects import projects_bp

__all__ = [
    "agents_bp",
    "events_bp",
    "headspace_bp",
    "hooks_bp",
    "notifications_bp",
    "priorities_bp",
    "projects_bp",
]


def register_blueprints(app):
    """Register all blueprints with the Flask app.

    Args:
        app: The Flask application instance.
    """
    app.register_blueprint(agents_bp, url_prefix="/api")
    app.register_blueprint(events_bp, url_prefix="/api")
    app.register_blueprint(headspace_bp, url_prefix="/api")
    app.register_blueprint(hooks_bp, url_prefix="/hook")
    app.register_blueprint(notifications_bp, url_prefix="/api")
    app.register_blueprint(priorities_bp, url_prefix="/api")
    app.register_blueprint(projects_bp, url_prefix="/api")
