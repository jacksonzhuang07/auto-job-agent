"""SaaS control plane for the auto-job-agent workflow.

The web app is a control plane only: profile/screening facts, ledger,
pacing/ramp state, stumps, outreach drafts and reports. Live browser
submission stays in the existing CLI agent (applier.py / main.py).
"""
import os

from flask import Flask


def create_app(config: dict | None = None) -> Flask:
    app = Flask(__name__)
    app.config.update(
        SECRET_KEY=os.environ.get("WEBAPP_SECRET_KEY", "dev-only-change-me"),
        DATABASE=os.environ.get(
            "AUTO_JOB_WEBAPP_DB",
            os.path.join(os.path.dirname(os.path.abspath(__file__)), "webapp.db"),
        ),
    )
    if config:
        app.config.update(config)

    from . import db

    with app.app_context():
        db.init_db(app.config["DATABASE"])
        db.seed(app.config["DATABASE"])

    from .routes import bp

    app.register_blueprint(bp)
    return app
