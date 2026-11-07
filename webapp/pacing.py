"""Pacing / ramp engine — the rate-limit logic of the live workflow.

Pure module: no I/O, no sleeping, all times are passed in explicitly so the
logic is fully unit-testable. The simulated runner and (future) live
executors must go through this module — never re-implement these rules.

Rules (from the live Muse workflow, adopted Nov 5, 2026):
- Daily ladders: LinkedIn [15, 25, 35, 50], Indeed [8, 12, 20, 30, 50].
- One step up per CLEAN day: target reached OR pool exhausted, with no
  limit stop, warning, or repeated CAPTCHA that day.
- Rolling 30-minute burst caps: fewer than 6 submissions per window on
  LinkedIn, fewer than 3 on Indeed (so 5 and 2 are the maxima).
- Minimum spacing: ~2 minutes between submissions on the same platform.
- Stop rules:
  * daily-limit message / verification block -> platform done for the day;
    the successful count is logged as an observed cap. The same cap
    observed twice becomes the ESTABLISHED cap (the daily target).
  * 2nd CAPTCHA on a platform in a day -> platform done for the day.
  * account warning / security checkpoint -> stop ALL platforms; the
    warned platform drops one ladder step and is paused for 48 hours.
- OVERRIDE: a dated override suspends the COUNT target for that date only.
  Burst caps, spacing and stop rules stay binding, and an override day is
  never a clean day (the ramp does not advance because of it).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta

PLATFORMS = ("indeed", "linkedin")
LADDERS: dict[str, list[int]] = {
    "linkedin": [15, 25, 35, 50],
    "indeed": [8, 12, 20, 30, 50],
}
# "Under N per rolling 30 minutes" -> at most N-1 submissions in a window.
BURST_CAPS: dict[str, int] = {"linkedin": 6, "indeed": 3}
MIN_SPACING = timedelta(minutes=2)
BURST_WINDOW = timedelta(minutes=30)
WARNING_PAUSE = timedelta(hours=48)


def _day(when: datetime | date) -> date:
    return when.date() if isinstance(when, datetime) else when


@dataclass
class PlatformRamp:
    """Durable per-platform ramp state (persisted by the web layer)."""

    platform: str
    ladder_index: int = 0
    established_cap: int | None = None
    paused_until: datetime | None = None

    @property
    def ladder(self) -> list[int]:
        return LADDERS[self.platform]

    def target(self) -> int:
        if self.established_cap is not None:
            return self.established_cap
        return self.ladder[min(self.ladder_index, len(self.ladder) - 1)]


@dataclass
class _DayLedger:
    submissions: list[datetime] = field(default_factory=list)
    captchas: int = 0
    stopped: bool = False
    stop_reason: str | None = None


class PacingEngine:
    """Tracks submissions and platform responses for the ramp protocol."""

    def __init__(self, ramps: dict[str, PlatformRamp] | None = None):
        self.ramps: dict[str, PlatformRamp] = ramps or {
            p: PlatformRamp(platform=p) for p in PLATFORMS
        }
        self._days: dict[tuple[str, date], _DayLedger] = {}
        self._observed_caps: dict[str, list[int]] = {p: [] for p in PLATFORMS}
        self._all_stop_day: date | None = None
        self._override_date: date | None = None

    # -- override ---------------------------------------------------------
    def set_override(self, on: date | None) -> None:
        """Suspend count targets for one date only (pacing/stops stay)."""
        self._override_date = on

    def override_active(self, when: datetime | date) -> bool:
        return self._override_date is not None and self._override_date == _day(when)

    # -- targets ----------------------------------------------------------
    def target_for(self, platform: str, when: datetime | date) -> int | None:
        """Daily count target, or None when an override suspends it."""
        if self.override_active(when):
            return None
        return self.ramps[platform].target()

    # -- submission gate ----------------------------------------------------
    def _ledger(self, platform: str, when: datetime) -> _DayLedger:
        return self._days.setdefault((platform, _day(when)), _DayLedger())

    def count_on(self, platform: str, when: datetime | date) -> int:
        ledger = self._days.get((platform, _day(when)))
        return len(ledger.submissions) if ledger else 0

    def burst_count(self, platform: str, when: datetime) -> int:
        """Submissions in the rolling window (when-30min, when]."""
        ledger = self._days.get((platform, _day(when)))
        if not ledger:
            return 0
        start = when - BURST_WINDOW
        return sum(1 for t in ledger.submissions if start < t <= when)

    def can_submit(self, platform: str, when: datetime) -> tuple[bool, str]:
        ramp = self.ramps[platform]
        if ramp.paused_until is not None and when < ramp.paused_until:
            return False, f"{platform} paused until {ramp.paused_until.isoformat()} (account warning)"
        if self._all_stop_day == _day(when):
            return False, "all platforms stopped for the day (account warning / security checkpoint)"
        ledger = self._ledger(platform, when)
        if ledger.stopped:
            return False, f"{platform} stopped for the day: {ledger.stop_reason}"
        target = self.target_for(platform, when)
        if target is not None and len(ledger.submissions) >= target:
            return False, f"{platform} daily target reached ({target})"
        if ledger.submissions:
            last = ledger.submissions[-1]
            if when - last < MIN_SPACING:
                return False, f"spacing: last {platform} submission {(when - last).seconds}s ago (< 2 min)"
        if self.burst_count(platform, when) >= BURST_CAPS[platform] - 1:
            return False, f"burst cap: {BURST_CAPS[platform] - 1} {platform} submissions already in the last 30 min"
        return True, "ok"

    def next_allowed_time(self, platform: str, when: datetime) -> datetime:
        """Earliest time a submission could pass spacing + burst checks."""
        ledger = self._days.get((platform, _day(when)))
        candidate = when
        if ledger and ledger.submissions:
            candidate = max(candidate, ledger.submissions[-1] + MIN_SPACING)
            in_window = [t for t in ledger.submissions if t > candidate - BURST_WINDOW]
            cap = BURST_CAPS[platform] - 1
            while len(in_window) >= cap:
                candidate = in_window[0] + BURST_WINDOW
                if ledger.submissions:
                    candidate = max(candidate, ledger.submissions[-1] + MIN_SPACING)
                in_window = [t for t in ledger.submissions if t > candidate - BURST_WINDOW]
        return candidate

    def record_submission(self, platform: str, when: datetime) -> None:
        ok, reason = self.can_submit(platform, when)
        if not ok:
            raise ValueError(f"submission refused by pacing engine: {reason}")
        self._ledger(platform, when).submissions.append(when)

    # -- platform responses -------------------------------------------------
    def record_daily_limit(self, platform: str, when: datetime) -> int:
        """Daily-limit message / verification block: platform done today.

        Returns the observed cap (successful submissions today). Observing
        the same cap a second time establishes it as the daily target.
        """
        ledger = self._ledger(platform, when)
        ledger.stopped = True
        ledger.stop_reason = "daily limit / verification block"
        cap = len(ledger.submissions)
        caps = self._observed_caps[platform]
        caps.append(cap)
        if caps.count(cap) >= 2:
            self.ramps[platform].established_cap = cap
        return cap

    def record_captcha(self, platform: str, when: datetime) -> bool:
        """Record a CAPTCHA. Returns True when the platform must stop
        (2nd CAPTCHA on the same platform the same day)."""
        ledger = self._ledger(platform, when)
        ledger.captchas += 1
        if ledger.captchas >= 2:
            ledger.stopped = True
            ledger.stop_reason = "second CAPTCHA"
            return True
        return False

    def record_warning(self, platform: str, when: datetime) -> None:
        """Account warning / security checkpoint: stop ALL platforms, drop
        the warned platform one ladder step, pause it for 48 hours."""
        self._all_stop_day = _day(when)
        for p in PLATFORMS:
            self._ledger(p, when).stopped = True
            self._ledger(p, when).stop_reason = "account warning / security checkpoint"
        ramp = self.ramps[platform]
        ramp.ladder_index = max(0, ramp.ladder_index - 1)
        ramp.paused_until = when + WARNING_PAUSE

    def is_paused(self, platform: str, when: datetime) -> bool:
        paused_until = self.ramps[platform].paused_until
        return paused_until is not None and when < paused_until

    # -- end of day -----------------------------------------------------------
    def close_day(
        self,
        platform: str,
        when: datetime | date,
        *,
        target_reached_or_pool_exhausted: bool,
    ) -> bool:
        """Advance the ladder one step on a CLEAN day. Returns True if the
        platform advanced. An override day, a limit stop, a warning or a
        repeated CAPTCHA all make the day not clean."""
        day = _day(when)
        if self.override_active(day):
            return False
        if self._all_stop_day == day:
            return False
        ledger = self._days.get((platform, day))
        if ledger and ledger.stopped:
            return False
        if not target_reached_or_pool_exhausted:
            return False
        ramp = self.ramps[platform]
        if ramp.established_cap is not None:
            return False  # target is the established cap; ladder no longer moves
        if ramp.ladder_index < len(ramp.ladder) - 1:
            ramp.ladder_index += 1
            return True
        return False
