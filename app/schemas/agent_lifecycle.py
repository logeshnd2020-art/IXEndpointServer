from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field

# The nine raw client-observed event types the approved 7.8.0
# specification defines. Every management-facing reason (Sleep, Confirmed
# Restart, Confirmed Shutdown, Agent Restarted, Unexpected Agent Recovery,
# Network Unavailable, Server Unavailable) is DERIVED server-side from
# sequences of these -- none of those derived labels is ever sent by the
# client or stored as its own event_type.
AgentLifecycleEventType = Literal[
    "SLEEP",
    "WAKE",
    "SHUTDOWN_OR_RESTART_IMMINENT",
    "AGENT_STARTED",
    "AGENT_STOPPED",
    "NETWORK_UNAVAILABLE",
    "NETWORK_RECOVERED",
    "SERVER_UNAVAILABLE",
    "SERVER_RECOVERED",
]

WakeReason = Literal["UserWake", "DarkWake", "Unknown"]
ReachabilityTarget = Literal["default_route", "server_endpoint"]


class AgentLifecycleEventIn(BaseModel):
    event_uid: str = Field(min_length=1, max_length=36)
    event_type: AgentLifecycleEventType

    event_time: datetime
    collected_at: datetime

    agent_version: Optional[str] = None
    boottime: Optional[datetime] = None
    pid: Optional[int] = None
    wake_reason: Optional[WakeReason] = None
    reachability_target: Optional[ReachabilityTarget] = None
    detail: Optional[str] = Field(default=None, max_length=255)


class AgentLifecycleSyncRequest(BaseModel):
    # Bounded batch size -- see agent_lifecycle_service for the exact
    # cap and why (production-safety consideration: an unbounded payload
    # from a malfunctioning or malicious client must never be accepted).
    events: List[AgentLifecycleEventIn]


class AgentLifecycleSyncResponse(BaseModel):
    status: str
    # Every event_uid the server now has durably stored for this device --
    # a duplicate/retried event_uid is included here too (already-stored,
    # not re-inserted), so the client can safely prune ANY event_uid in
    # this list from its local queue, whether this was its first
    # successful delivery or a retry of one already accepted earlier.
    accepted_event_uids: List[str]
