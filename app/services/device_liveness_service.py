"""
Phase 3, Item 3 -- Device.is_online / staleness, computed at read time
(Correction 3 / Rule 3).

This module answers exactly one question: "has the server received
monitoring evidence (a heartbeat, sync call, or registration) from this
device recently?" That is the ENTIRE meaning of "stale" / "not stale"
here.

It must NEVER be read as, or used to populate, any of:

  DEVICE STATE (SLEEP, SHUTDOWN, RESTART, AGENT_STOPPED) -- staleness
  alone cannot distinguish any of these from each other, or from a live
  device on a flaky network.

  INFRASTRUCTURE/MONITORING STATE beyond the generic staleness fact
  itself -- it must never be elevated to SERVER_UNAVAILABLE or
  NETWORK_UNAVAILABLE without separate, corroborating evidence (see
  app.services.server_lifecycle_service for the one source of evidence
  this project has for server-side unavailability).

It is a dashboard/device-list liveness badge only, entirely separate
from the canonical per-segment timeline classification pipeline
(MonitoringWindowService / WorkSessionClassifier / TimelineService),
which this module is never called by and must never call into.
"""
from datetime import datetime, timezone

from app.models.device import Device
from app.services.agent_service import AgentService

# Conservative: tolerate one missed heartbeat cycle before calling a
# device stale, to avoid flapping ONLINE/OFFLINE on ordinary heartbeat
# jitter.
STALE_THRESHOLD_SECONDS = 2 * AgentService.HEARTBEAT_INTERVAL


def is_stale(device: Device, now: datetime = None) -> bool:
    """
    True if the server has not received monitoring evidence from this
    device within STALE_THRESHOLD_SECONDS.

    Fails toward "stale" (i.e. OFFLINE) whenever last_seen is missing --
    absence of evidence is never treated as evidence of liveness, per
    this project's general evidence-based-only design rule.
    """
    if now is None:
        now = datetime.now(timezone.utc)

    if device.last_seen is None:
        return True

    last_seen = device.last_seen
    if last_seen.tzinfo is None:
        # device.last_seen is always written as aware UTC by
        # AgentService (datetime.now(timezone.utc)); a naive value here
        # can only be SQLite's storage layer stripping tzinfo on
        # round-trip, so re-tagging as UTC (not local time) is correct
        # for this specific column -- unlike device_heartbeats.timestamp,
        # which has the opposite, naive-IST convention.
        last_seen = last_seen.replace(tzinfo=timezone.utc)

    return (now - last_seen).total_seconds() > STALE_THRESHOLD_SECONDS


def online_status_label(device: Device, now: datetime = None) -> str:
    """
    "ONLINE" or "OFFLINE" -- the only two values this ever returns.

    Liveness/visibility only, per this module's docstring -- never a
    device-state or infrastructure-state claim.
    """
    return "OFFLINE" if is_stale(device, now) else "ONLINE"
