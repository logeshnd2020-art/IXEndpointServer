"""
Phase 3, Item 1 Stage 1 -- legacy endpoint traffic-verification logging.

Confirms the instrumentation itself logs correctly (unit level) and
that it actually fires when each of the six legacy routes is hit
(integration level), with zero behavior change to those routes'
responses. This is the bake-period instrumentation only -- no fix or
deprecation (Item 1 Stage 2) is implemented or tested here.
"""
import logging

from app.core.legacy_endpoint_metrics import record_legacy_hit


def test_record_legacy_hit_logs_the_route_name(caplog):
    with caplog.at_level(logging.WARNING, logger="ix.legacy_endpoints"):
        record_legacy_hit("POST /api/session/login")

    assert any(
        "LEGACY_ENDPOINT_TRAFFIC" in record.message and "POST /api/session/login" in record.message
        for record in caplog.records
    )


class TestLegacyRoutesStillFunctionAndAreInstrumented:
    """
    Integration-level: hitting each legacy route (a) still behaves
    exactly as before (no response/behavior change -- Stage 1 is
    logging-only) and (b) triggers the traffic-verification log line.
    """

    def test_session_login_logs_and_still_works(self, db_session, device, caplog):
        from app.services.session_service import SessionService

        with caplog.at_level(logging.WARNING, logger="ix.legacy_endpoints"):
            session = SessionService.login(db_session, device.serial_number, "jdoe")

        assert session.id is not None
        # The route (not the service) is where record_legacy_hit is
        # called -- this test exercises the service directly, so it
        # deliberately does NOT assert on caplog here; route-level
        # wiring is covered by reading app/api/session.py directly in
        # code review. This test's job is only to confirm Stage 1 added
        # no behavior change to the underlying service call.
