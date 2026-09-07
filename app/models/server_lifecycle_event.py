from sqlalchemy import Column, DateTime, Integer, String
from sqlalchemy.sql import func

from app.core.database import Base


class ServerLifecycleEvent(Base):
    """
    Phase 3, Item 2 -- durable record of this server process's own
    startup/shutdown lifecycle.

    This is EVIDENCE, not absolute truth. A clean shutdown reliably
    writes a "shutdown" row (the ASGI lifespan shutdown handler gets a
    chance to run). A crash, hard reboot, power loss, or forced
    termination (SIGKILL) does NOT -- there is no code running at that
    moment to write anything. Consequently:

      - The ABSENCE of a "shutdown" row before the next "startup" row
        does NOT prove the server was continuously available in
        between -- it proves only that the previous run ended
        ungracefully, with the precise moment of unavailability
        unknown.
      - The ABSENCE of any row at all for a given time window (e.g.
        before this table existed, or a write failure at the exact
        moment of a transition) must NEVER be treated as evidence the
        server was up -- it means no evidence exists, nothing more.

    See app.services.server_lifecycle_service.get_outage_evidence() for
    the exact, conservative derivation built on top of these raw rows
    (CONFIRMED_OUTAGE_INTERVAL vs. UNCERTAIN_AVAILABILITY_INTERVAL).

    This table intentionally does NOT and cannot capture network-level
    unavailability -- the process staying up while unreachable from
    clients, or unable to reach its own database, leaves no trace here.
    That is a distinct kind of evidence this table has no way to
    observe, and no code should ever infer it from this table.
    """

    __tablename__ = "server_lifecycle_events"

    id = Column(Integer, primary_key=True, index=True)

    # "startup" or "shutdown" -- enforced at the service layer, not a
    # DB enum, to keep this migration simple and additive.
    event_type = Column(String(20), nullable=False)

    occurred_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
    )

    # Debugging/correlation aid only -- never read by evidence
    # derivation.
    pid = Column(Integer, nullable=True)
