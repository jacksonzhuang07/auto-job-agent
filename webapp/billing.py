"""Billing: subscriptions, usage metering, and Stripe state.

Model (see webapp/pricing.py for the pure math):
- A user needs an active subscription for runs to execute in hosted mode.
- Every application recorded as DELIVERED is metered exactly once into
  usage_ledger (UNIQUE(application_id) makes metering idempotent):
  the first INCLUDED_APPLICATIONS in a billing month are kind='included'
  (amount 0); the rest are kind='overage' at OVERAGE_PRICE_CENTS each.
- Delivery-failed (or otherwise non-delivered) applications never meter.

Stripe is optional: checkout/webhook activate only when the STRIPE_*
environment variables are set; the SDK import is guarded so the app runs
(and reports "payments not configured") without it. Nothing here ever
fakes a charge.
"""
from __future__ import annotations

import os
from datetime import date

from . import db
from .pricing import (  # re-exported for callers/tests
    BASE_PRICE_CENTS,
    INCLUDED_APPLICATIONS,
    OVERAGE_PRICE_CENTS,
    PLAN_NAME,
    compute_usage,
    currency,
    pricing_summary,
)

ACTIVE_STATUSES = ("active", "trialing")


def hosted_mode() -> bool:
    """Hosted mode = running on Vercel or explicitly flagged. Hosted runs
    require an active subscription; local dev runs do not."""
    return bool(os.environ.get("VERCEL") or os.environ.get("HOSTED_MODE"))


def current_period(when: date | None = None) -> str:
    """Billing periods are calendar months, keyed 'YYYY-MM'."""
    when = when or date.today()
    return when.strftime("%Y-%m")


def period_bounds(period: str) -> tuple[str, str]:
    year, month = (int(p) for p in period.split("-"))
    start = date(year, month, 1)
    end = date(year + (1 if month == 12 else 0), 1 if month == 12 else month + 1, 1)
    return start.isoformat(), end.isoformat()


# --------------------------------------------------------------------------
# Subscriptions
# --------------------------------------------------------------------------

def get_subscription(db_path: str, user_id: int) -> dict | None:
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT * FROM subscriptions WHERE user_id = ?", (user_id,)
        ).fetchone()
    return dict(row) if row else None


def has_active_subscription(db_path: str, user_id: int) -> bool:
    sub = get_subscription(db_path, user_id)
    return bool(sub) and sub["status"] in ACTIVE_STATUSES


def subscribed_user_ids(db_path: str) -> list[int]:
    with db.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT user_id FROM subscriptions WHERE status IN ('active', 'trialing') ORDER BY user_id"
        ).fetchall()
    return [r["user_id"] for r in rows]


def update_subscription(db_path: str, user_id: int, **fields) -> None:
    allowed = {"plan", "status", "is_comped", "current_period_start",
               "current_period_end", "stripe_customer_id", "stripe_subscription_id"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    cols = ", ".join(f"{k} = ?" for k in updates)
    with db.connect(db_path) as conn:
        conn.execute(
            f"UPDATE subscriptions SET {cols} WHERE user_id = ?",
            (*updates.values(), user_id),
        )
        conn.commit()


def find_user_by_stripe_customer(db_path: str, customer_id: str) -> int | None:
    with db.connect(db_path) as conn:
        row = conn.execute(
            "SELECT user_id FROM subscriptions WHERE stripe_customer_id = ?", (customer_id,)
        ).fetchone()
    return row["user_id"] if row else None


# --------------------------------------------------------------------------
# Metering
# --------------------------------------------------------------------------

def meter_application(db_path: str, user_id: int, application_id: int,
                      delivery_status: str, app_date=None) -> bool | None:
    """Meter one recorded application. THE metering entry point — the
    simulated runner and the worker report path both call this.

    Returns True when a new usage row was written, False when the
    application was already metered (idempotent — never double-bills),
    and None when the application is not billable (not delivered).
    """
    if delivery_status != "delivered":
        return None
    if app_date is None:
        app_date = date.today()
    period = app_date[:7] if isinstance(app_date, str) else app_date.strftime("%Y-%m")
    with db.connect(db_path) as conn:
        existing = conn.execute(
            "SELECT id FROM usage_ledger WHERE application_id = ?", (application_id,)
        ).fetchone()
        if existing:
            return False
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM usage_ledger WHERE user_id = ? AND period = ?",
            (user_id, period),
        ).fetchone()["c"]
        if count < INCLUDED_APPLICATIONS:
            kind, amount = "included", 0
        else:
            kind, amount = "overage", OVERAGE_PRICE_CENTS
        conn.execute(
            """INSERT INTO usage_ledger (user_id, application_id, amount_cents, currency, period, kind)
               VALUES (?, ?, ?, ?, ?, ?)""",
            (user_id, application_id, amount, currency(), period, kind),
        )
        conn.commit()
    return True


def period_usage(db_path: str, user_id: int, period: str | None = None) -> dict:
    """Usage totals for one billing period, consistent with compute_usage."""
    period = period or current_period()
    with db.connect(db_path) as conn:
        row = conn.execute(
            """SELECT COUNT(*) AS delivered,
                      SUM(CASE WHEN kind = 'included' THEN 1 ELSE 0 END) AS included_used,
                      SUM(CASE WHEN kind = 'overage' THEN 1 ELSE 0 END) AS overage_count,
                      COALESCE(SUM(amount_cents), 0) AS overage_cents
               FROM usage_ledger WHERE user_id = ? AND period = ?""",
            (user_id, period),
        ).fetchone()
    usage = compute_usage(row["delivered"] or 0)
    usage["period"] = period
    return usage


def usage_rows(db_path: str, user_id: int, period: str | None = None, limit: int = 50) -> list:
    period = period or current_period()
    with db.connect(db_path) as conn:
        return conn.execute(
            """SELECT u.*, a.company, a.role, a.source, a.date AS application_date
               FROM usage_ledger u JOIN applications a ON a.id = u.application_id
               WHERE u.user_id = ? AND u.period = ? ORDER BY u.id DESC LIMIT ?""",
            (user_id, period, limit),
        ).fetchall()


# --------------------------------------------------------------------------
# Stripe (optional, guarded)
# --------------------------------------------------------------------------

def stripe_configured() -> bool:
    return bool(os.environ.get("STRIPE_SECRET_KEY") and os.environ.get("STRIPE_PRICE_ID"))


def _stripe():
    """Import and configure the Stripe SDK, or None when unavailable."""
    try:
        import stripe
    except ImportError:
        return None
    key = os.environ.get("STRIPE_SECRET_KEY")
    if not key:
        return None
    stripe.api_key = key
    return stripe


def create_checkout_session(db_path: str, user_id: int, base_url: str):
    """Create a Stripe Checkout session (subscription mode) for the plan's
    base price. Returns the session URL, or None when Stripe is not
    configured. The $1/application overage is metered in usage_ledger and
    reconciled against the subscription (see README)."""
    stripe = _stripe()
    price_id = os.environ.get("STRIPE_PRICE_ID")
    if stripe is None or not price_id:
        return None
    base = base_url.rstrip("/")
    session = stripe.checkout.Session.create(
        mode="subscription",
        line_items=[{"price": price_id, "quantity": 1}],
        success_url=f"{base}/billing?checkout=success",
        cancel_url=f"{base}/billing?checkout=cancelled",
        client_reference_id=str(user_id),
        metadata={"user_id": str(user_id)},
    )
    return session.url
