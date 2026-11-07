"""Run the SaaS control plane:  python -m webapp  (port 5050 by default)."""
import os

from . import create_app

if __name__ == "__main__":
    app = create_app()
    app.run(host="127.0.0.1", port=int(os.environ.get("WEBAPP_PORT", "5050")))
