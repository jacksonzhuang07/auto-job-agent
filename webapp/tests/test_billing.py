"""Billing: pure pricing math, metering rules, billing page, Stripe states."""
from datetime import date

import pytest

from webapp import billing, create_app, db
from webapp.pricing import compute_usage


@pytest.fixture()
def app(tmp_path):
    return create_app({"TESTING": True, "DATABASE": str(tmp_path / "test.db")})


@pytest.fixture()
def client(app):
    return app.test_client()


# ---------------------------------------------------------------------------
# Pure billing math: $20 base incl. 20 delivered, then $1.00 per delivered.
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("delivered,included,overage,overage_cents,total", [
    (0, 0, 0, 0, 2000),
    (20, 20, 0, 0, 2000),
    (21, 20, 1, 100, 2100),
    (45, 20, 25, 2500, 4500),
])
def test_compute_usage_math(delivered, included, overage, overage_cents, total):
    usage = compute_usage(delivered)
    assert usage["delivered"] == delivered
    assert usage["included_used"] == included
    assert usage["overage_count"] == overage
    assert usage["overage_cents"] == overage_cents
    assert usage["base_cents"] == 2000
    assert usage["total_due_cents"] == total


# ---------------------------------------------------------------------------
# Metering rules
# ---------------------------------------------------------------------------

def _add_application(db_path, user_id, company, delivery, app_date="2026-11-06"):
    with db.connect(db_path) as conn:
        cur = conn.execute(
            """INSERT INTO applications (user_id, dedupe_key, date, company, role, source,
               proof, status, delivery_status)
               VALUES (?, ?, ?, ?, 'Program Manager', 'indeed', 'proof', 'submitted', ?)""",
            (user_id, f"{company.lower()}::program manager", app_date, company, delivery),
        )
        conn.commit()
        return cur.lastrowid


def test_seeded_demo_user_has_comped_active_subscription(app):
    db_path = app.config["DATABASE"]
    user_id = db.current_user_id(db_path)
    sub = billing.get_subscription(db_path, user_id)
    assert sub is not None
    assert sub["plan"] == "Autopilot"
    assert sub["status"] == "active"
    assert sub["is_comped"] == 1
    assert billing.has_active_subscription(db_path, user_id)


def test_delivery_failed_is_never_metered(app):
    db_path = app.config["DATABASE"]
    user_id = db.current_user_id(db_path)
    app_id = _add_application(db_path, user_id, "FailMeter Co", "failed")
    assert billing.meter_application(db_path, user_id, app_id, "failed") is None
    with db.connect(db_path) as conn:
        count = conn.execute(
            "SELECT COUNT(*) AS c FROM usage_ledger WHERE application_id = ?", (app_id,)
        ).fetchone()["c"]
    assert count == 0


def test_metering_included_then_overage_and_idempotent(app):
    db_path = app.config["DATABASE"]
    user_id = db.current_user_id(db_path)
    period = date.today().strftime("%Y-%m")
    today = date.today().isoformat()
    # The seed may already have metered delivered applications in this
    # period; start from whatever baseline exists and fill the rest of
    # the included allowance, then one more.
    baseline = billing.period_usage(db_path, user_id, period)["delivered"]
    fill = billing.INCLUDED_APPLICATIONS - baseline
    assert fill >= 0
    for i in range(fill):
        app_id = _add_application(db_path, user_id, f"Meter Co {i}", "delivered", app_date=today)
        assert billing.meter_application(db_path, user_id, app_id, "delivered", app_date=today) is True
    over_id = _add_application(db_path, user_id, "Meter Co Over", "delivered", app_date=today)
    assert billing.meter_application(db_path, user_id, over_id, "delivered", app_date=today) is True
    # Re-metering the same application is a no-op (never double-billed).
    assert billing.meter_application(db_path, user_id, over_id, "delivered", app_date=today) is False
    with db.connect(db_path) as conn:
        rows = conn.execute(
            "SELECT kind, amount_cents FROM usage_ledger WHERE user_id = ? AND period = ? ORDER BY id",
            (user_id, period),
        ).fetchall()
        over_row = conn.execute(
            "SELECT kind, amount_cents FROM usage_ledger WHERE application_id = ?", (over_id,)
        ).fetchone()
    assert len(rows) == billing.INCLUDED_APPLICATIONS + 1
    assert sum(1 for r in rows if r["kind"] == "included") == billing.INCLUDED_APPLICATIONS
    assert over_row["kind"] == "overage" and over_row["amount_cents"] == 100
    usage = billing.period_usage(db_path, user_id, period)
    assert usage["delivered"] == billing.INCLUDED_APPLICATIONS + 1
    assert usage["overage_count"] == 1
    assert usage["total_due_cents"] == 2100


# ---------------------------------------------------------------------------
# Pages / Stripe state
# ---------------------------------------------------------------------------

def test_billing_page_200_not_configured_state(client, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    monkeypatch.delenv("STRIPE_PRICE_ID", raising=False)
    resp = client.get("/billing")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Autopilot" in body
    assert "Comped" in body                      # seeded demo subscription, clearly marked
    assert "not configured" in body.lower()      # Stripe panel, keys absent
    assert "$1.00" in body                       # per-delivered-application price


def test_billing_page_shows_live_state_when_stripe_configured(client, monkeypatch):
    monkeypatch.setenv("STRIPE_SECRET_KEY", "sk_test_dummy")
    monkeypatch.setenv("STRIPE_PRICE_ID", "price_dummy")
    body = client.get("/billing").get_data(as_text=True)
    assert "Live" in body
    assert "Subscribe / Manage" in body


def test_dashboard_has_pricing_section(client):
    body = client.get("/").get_data(as_text=True)
    assert "Pricing" in body
    assert "$20" in body
    assert "$1.00" in body
    assert "never" in body.lower()  # never charged for failed deliveries


def test_webhook_not_configured_returns_503(client, monkeypatch):
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET", raising=False)
    monkeypatch.delenv("STRIPE_SECRET_KEY", raising=False)
    resp = client.post("/billing/webhook", data="{}",
                       content_type="application/json")
    assert resp.status_code == 503
