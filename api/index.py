"""Vercel Python entrypoint.

Vercel's Python runtime imports this module and serves the `app` WSGI
callable. vercel.json rewrites all traffic here, so every route of the
Flask control plane (pages, /api/cron/daily-run, /api/worker/*,
/billing/webhook) is handled by the one function.

On Vercel the SQLite database lives in /tmp (see webapp._default_database)
— ephemeral across cold starts until a hosted database is wired in.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from webapp import create_app  # noqa: E402

app = create_app()
