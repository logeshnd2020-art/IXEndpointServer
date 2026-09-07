from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.core.database import Base


class AgentLifecycleEvent(Base):
    """
    7.8.0 client-supplied evidence -- one of nine raw event types (see the
    approved 7.8.0 specification): SLEEP, WAKE, SHUTDOWN_OR_RESTART_IMMINENT,
    AGENT_STARTED, AGENT_STOPPED, NETWORK_UNAVAILABLE, NETWORK_RECOVERED,
    SERVER_UNAVAILABLE, SERVER_RECOVERED.

    This table only STORES raw client evidence. It never itself decides a
    management-facing reason -- that derivation lives entirely in
    app.services.agent_evidence_service, kept deliberately separate from
    storage so the evidence-tiering rules can be tested and changed without
    touching how events are persisted.

    Idempotency: (device_id, event_uid) is unique -- a retried/duplicate
    upload of the same locally-generated event_uid is a no-op, never a
    second row. event_uid is client-generated (a UUID), immutable from the
    moment of capture through however many retries it takes to deliver.

    Three distinct timestamps are kept, on purpose, and none is ever
    derived from another:
      - event_time: when the OS/agent actually observed this (client-
        authoritative -- e.g. the instant NSWorkspaceWillSleepNotification
        fired).
      - collected_at: when the agent process serialized it into its local
        durable queue (client-authoritative, normally ~identical to
        event_time for synchronous OS-notification callbacks).
      - upload_time: when THIS server actually received the batch
        containing it (server-authoritative -- set here, never trusted
        from the client). A device offline for days uploads a backlog
        whose event_time values are far in the past relative to
        upload_time; that gap is expected and preserved, never collapsed.
    """

    __tablename__ = "agent_lifecycle_events"

    id = Column(Integer, primary_key=True, index=True)

    device_id = Column(Integer, ForeignKey("devices.id"), nullable=False, index=True)

    event_uid = Column(String(36), nullable=False)

    # One of the nine raw types (see app.schemas.agent_lifecycle for the
    # authoritative Literal) -- stored as a plain string, not a DB enum,
    # matching the same convention already used for
    # server_lifecycle_events.event_type.
    event_type = Column(String(40), nullable=False)

    event_time = Column(DateTime(timezone=True), nullable=False)
    collected_at = Column(DateTime(timezone=True), nullable=False)
    upload_time = Column(DateTime(timezone=True), nullable=False, server_default=func.now())

    agent_version = Column(String(20), nullable=True)

    # Only meaningful on AGENT_STARTED -- sysctl kern.boottime, read fresh
    # by the client at emission time. See agent_evidence_service for why
    # this is authoritative for "did the kernel restart" and for the
    # tolerance applied when comparing it across events.
    boottime = Column(DateTime(timezone=True), nullable=True)

    # Debugging/correlation aid only -- never read by evidence derivation.
    pid = Column(Integer, nullable=True)

    # Only meaningful on WAKE -- "UserWake" / "DarkWake" / "Unknown".
    wake_reason = Column(String(20), nullable=True)

    # Only meaningful on NETWORK_UNAVAILABLE / SERVER_UNAVAILABLE --
    # "default_route" / "server_endpoint".
    reachability_target = Column(String(20), nullable=True)

    # Free-text diagnostic context. Never load-bearing for classification.
    detail = Column(String(255), nullable=True)

    device = relationship("Device")

    __table_args__ = (
        UniqueConstraint(
            "device_id",
            "event_uid",
            name="uq_agent_lifecycle_events_device_event_uid",
        ),
    )
