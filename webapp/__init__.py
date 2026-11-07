"""SaaS control plane for the auto-job-agent workflow.

The web app is a control plane only: profile/screening facts, ledger,
pacing/ramp state, stumps, outreach drafts and reports. Live browser
submission stays in the existing CLI agent (applier.py / main.py).
"""
import os

from flask import Flask


def _default_database() -> str:
    """Database location, environment-aware.

    - AUTO_JOB_WEBAPP_DB always wins.
    - On Vercel (VERCEL env var set) the only writable path is /tmp, which
      is EPHEMERAL: data resets when the function instance is recycled.
      Until a hosted database is wired in, AUTO_JOB_WEBAPP_DB is the single
      config point to swap (the db layer only ever receives a path).
    - Locally, keep the historical webapp/webapp.db file.
    """
    env = os.environ.get("AUTO_JOB_WEBAPP_DB")
    if env:
        return env
    if os.environ.get("VERCEL"):
        return "/tmp/auto-job-agent-webapp.db"
    return os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp.db")


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("WEBAPP_SECRET_KEY", "dev-only-change-me"),
        DATABASE=_default_database(),
    )
    if config:
        app.config.update(config)

    from . import db

    with app.app_context():
        db.init_db(app.config["DATABASE"])
        db.seed(app.config["DATABASE"])

    from .api_routes import api_bp
    from .routes import bp

    app.register_blueprint(bp)
    app.register_blueprint(api_bp)
    return app
