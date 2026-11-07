"""Pacing/ramp engine tests — the core limit logic of the live workflow."""
from datetime import date, datetime, timedelta

import pytest

from webapp.pacing import LADDERS, PacingEngine, PlatformRamp

T0 = datetime(2026, 11, 6, 9, 0, 0)
DAY = date(2026, 11, 6)


def submit_n(engine, platform, n, start=T0, step_minutes=31):
    """Submit n times, spaced far enough apart to isolate count rules."""
    t = start
    for _ in range(n):
        engine.record_submission(platform, t)
        t += timedelta(minutes=step_minutes)
    return t


def test_burst_window_enforcement_linkedin():
    e = PacingEngine()
    t = T0
    # Under-6 cap: 5 submissions inside 30 minutes is the maximum.
    for _ in range(5):
        e.record_submission("linkedin", t)
        t += timedelta(minutes=2)
    ok, reason = e.can_submit("linkedin", t)
    assert not ok and "burst" in reason
    with pytest.raises(ValueError):
        e.record_submission("linkedin", t)
    # After the window slides past the first submission, it frees up.
    ok, _ = e.can_submit("linkedin", T0 + timedelta(minutes=31))
    assert ok


def test_burst_window_enforcement_indeed_is_stricter():
    e = PacingEngine()
    e.record_submission("indeed", T0)
    e.record_submission("indeed", T0 + timedelta(minutes=2))
    ok, reason = e.can_submit("indeed", T0 + timedelta(minutes=4))
    assert not ok and "burst" in reason  # under-3 cap -> max 2 per window


def test_spacing_two_minutes():
    e = PacingEngine()
    e.record_submission("indeed", T0)
    ok, reason = e.can_submit("indeed", T0 + timedelta(seconds=60))
    assert not ok and "spacing" in reason
    ok, _ = e.can_submit("indeed", T0 + timedelta(minutes=2))
    assert ok


def test_daily_target_blocks_beyond_ladder_step():
    e = PacingEngine()
    submit_n(e, "indeed", LADDERS["indeed"][0])  # step 1 target = 8
    ok, reason = e.can_submit("indeed", T0 + timedelta(hours=5))
    assert not ok and "target" in reason


def test_ladder_advances_on_clean_day():
    e = PacingEngine()
    assert e.ramps["linkedin"].ladder_index == 0
    assert e.close_day("linkedin", DAY, target_reached_or_pool_exhausted=True)
    assert e.ramps["linkedin"].ladder_index == 1
    assert e.target_for("linkedin", DAY) == 25


def test_no_advance_when_pool_not_exhausted_and_target_not_reached():
    e = PacingEngine()
    assert not e.close_day("indeed", DAY, target_reached_or_pool_exhausted=False)
    assert e.ramps["indeed"].ladder_index == 0


def test_limit_stop_holds_step_and_records_cap():
    e = PacingEngine()
    submit_n(e, "indeed", 6)
    cap = e.record_daily_limit("indeed", T0 + timedelta(hours=4))
    assert cap == 6
    ok, reason = e.can_submit("indeed", T0 + timedelta(hours=5))
    assert not ok and "stopped" in reason
    assert not e.close_day("indeed", DAY, target_reached_or_pool_exhausted=True)
    assert e.ramps["indeed"].ladder_index == 0  # held, not advanced
    assert e.ramps["indeed"].established_cap is None  # only seen once


def test_same_cap_twice_becomes_established():
    e = PacingEngine()
    submit_n(e, "linkedin", 11, start=T0)
    e.record_daily_limit("linkedin", T0 + timedelta(hours=6))
    day2 = datetime(2026, 11, 7, 9, 0, 0)
    submit_n(e, "linkedin", 11, start=day2)
    e.record_daily_limit("linkedin", day2 + timedelta(hours=6))
    assert e.ramps["linkedin"].established_cap == 11
    assert e.target_for("linkedin", day2.date()) == 11


def test_second_captcha_stops_platform_for_the_day():
    e = PacingEngine()
    assert e.record_captcha("indeed", T0) is False
    ok, _ = e.can_submit("indeed", T0 + timedelta(minutes=5))
    assert ok
    assert e.record_captcha("indeed", T0 + timedelta(minutes=6)) is True
    ok, reason = e.can_submit("indeed", T0 + timedelta(minutes=10))
    assert not ok and "stopped" in reason


def test_warning_stops_all_and_pauses_48h_and_drops_step():
    e = PacingEngine()
    e.ramps["linkedin"].ladder_index = 2
    e.record_warning("linkedin", T0)
    # All platforms stopped that day.
    for platform in ("linkedin", "indeed"):
        ok, _ = e.can_submit(platform, T0 + timedelta(hours=1))
        assert not ok
    # Warned platform dropped a step and is paused for 48h...
    assert e.ramps["linkedin"].ladder_index == 1
    assert e.is_paused("linkedin", T0 + timedelta(hours=47))
    ok, reason = e.can_submit("linkedin", T0 + timedelta(hours=47))
    assert not ok and "paused" in reason
    # ...but the other platform is free the next day, and LinkedIn after 48h.
    ok, _ = e.can_submit("indeed", T0 + timedelta(days=1))
    assert ok
    ok, _ = e.can_submit("linkedin", T0 + timedelta(hours=49))
    assert ok
    # A warning day is never clean.
    assert not e.close_day("indeed", DAY, target_reached_or_pool_exhausted=True)


def test_override_suspends_count_target_but_not_burst_and_no_advance():
    e = PacingEngine()
    e.set_override(DAY)
    assert e.target_for("indeed", DAY) is None
    # Count target gone: 8 (old target) + more submissions are allowed,
    # spaced outside burst windows.
    submit_n(e, "indeed", 12)
    assert e.count_on("indeed", DAY) == 12
    # Burst cap still binding under override.
    t = datetime(2026, 11, 6, 20, 0, 0)
    e.record_submission("indeed", t)
    e.record_submission("indeed", t + timedelta(minutes=2))
    ok, reason = e.can_submit("indeed", t + timedelta(minutes=4))
    assert not ok and "burst" in reason
    # Override day does not advance the ramp.
    assert not e.close_day("indeed", DAY, target_reached_or_pool_exhausted=True)
    assert e.ramps["indeed"].ladder_index == 0
    # Override expires with the date: next day the target is back.
    assert e.target_for("indeed", date(2026, 11, 7)) == 8


def test_platform_ramp_persistence_shape():
    ramp = PlatformRamp(platform="linkedin", ladder_index=1)
    assert ramp.target() == 25
    ramp.established_cap = 20
    assert ramp.target() == 20
