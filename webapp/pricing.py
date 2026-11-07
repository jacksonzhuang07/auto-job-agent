"""Pricing constants and pure billing math for the SaaS plan.

Single source of truth for pricing (Work Item 3):
- Plan "Autopilot": a monthly base subscription that includes a number of
  DELIVERED applications per billing month.
- Each additional delivered application costs a fixed per-application fee.
- Submitted-but-delivery-failed applications are NEVER billed.

All amounts are integer cents. Currency is configurable via the
BILLING_CURRENCY environment variable (default USD).
"""
from __future__ import annotations

import os

PLAN_NAME = "Autopilot"
BASE_PRICE_CENTS = 2000            # $20.00 / month base subscription
INCLUDED_APPLICATIONS = 20         # delivered applications included per month
OVERAGE_PRICE_CENTS = 100          # $1.00 per additional delivered application


def currency() -> str:
    return os.environ.get("BILLING_CURRENCY", "USD")


def compute_usage(delivered_count: int) -> dict:
    """Pure billing math for one billing period.

    Given the number of DELIVERED applications in the period, returns the
    included allowance used, the overage count, and the amount due
    (base subscription + overage), all in cents.
    """
    delivered = max(0, int(delivered_count))
    included_used = min(delivered, INCLUDED_APPLICATIONS)
    overage_count = max(0, delivered - INCLUDED_APPLICATIONS)
    overage_cents = overage_count * OVERAGE_PRICE_CENTS
    return {
        "delivered": delivered,
        "included_used": included_used,
        "included_total": INCLUDED_APPLICATIONS,
        "overage_count": overage_count,
        "overage_cents": overage_cents,
        "base_cents": BASE_PRICE_CENTS,
        "total_due_cents": BASE_PRICE_CENTS + overage_cents,
    }


def pricing_summary() -> dict:
    """Display-ready pricing facts for templates."""
    return {
        "plan": PLAN_NAME,
        "base_price": BASE_PRICE_CENTS / 100,
        "included_applications": INCLUDED_APPLICATIONS,
        "overage_price": OVERAGE_PRICE_CENTS / 100,
        "currency": currency(),
    }
