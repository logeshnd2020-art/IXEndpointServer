"""
Phase 3, Item 1 Stage 1 -- traffic-verification instrumentation only.

Purely additive: records that a legacy (pre-`/api/agent/*/sync`)
endpoint was hit, so a defined bake period (recommended 14 days, per
the Phase 3 design spec) can confirm whether these routes still receive
live traffic from any deployed agent before any behavior change (a fix
or a deprecation) is ever applied to them.

This module makes NO decisions and changes NO behavior -- it only logs.
The transition choice for those endpoints (Item 1 Stage 2) is decided
by the observed traffic once the bake period completes, not assumed in
advance and not implemented here.
"""
import logging

logger = logging.getLogger("ix.legacy_endpoints")


def record_legacy_hit(route_name: str) -> None:
    """
    Record that a legacy (pre-sync) endpoint was called.

    Intentionally the simplest possible instrumentation: one log line
    per hit, at WARNING level so it is visible under any reasonable
    logging configuration without needing DEBUG/INFO enabled, prefixed
    for easy grep. No counter, no DB write, no side effect beyond the
    log line -- Item 1 Stage 1 is verification only.
    """
    logger.warning("LEGACY_ENDPOINT_TRAFFIC route=%s", route_name)
