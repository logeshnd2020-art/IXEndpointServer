from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.agent_lifecycle_event import AgentLifecycleEvent
from app.models.device import Device
from app.repositories.agent_lifecycle_repository import AgentLifecycleRepository
from app.schemas.agent_lifecycle import (
    AgentLifecycleSyncRequest,
    AgentLifecycleSyncResponse,
)

# Bounded batch size -- prevents a malfunctioning or malicious client from
# submitting an unbounded payload in one request. A device offline long
# enough to accumulate more than this in its local queue simply takes
# multiple sync calls to fully drain, which the client's own retry loop
# already handles naturally (unsent rows stay queued until acknowledged).
MAX_EVENTS_PER_BATCH = 500


class AgentLifecycleService:

    @staticmethod
    def sync(
        db: Session,
        request: AgentLifecycleSyncRequest,
        device: Device,
    ) -> AgentLifecycleSyncResponse:

        if len(request.events) > MAX_EVENTS_PER_BATCH:
            raise ValueError(
                f"Batch too large: {len(request.events)} events "
                f"(max {MAX_EVENTS_PER_BATCH} per request)"
            )

        accepted_event_uids = []
        upload_time = datetime.now(timezone.utc)

        for item in request.events:
            existing = AgentLifecycleRepository.get_by_event_uid(
                db=db,
                device_id=device.id,
                event_uid=item.event_uid,
            )

            if existing is None:
                event = AgentLifecycleEvent(
                    device_id=device.id,
                    event_uid=item.event_uid,
                    event_type=item.event_type,
                    event_time=item.event_time,
                    collected_at=item.collected_at,
                    upload_time=upload_time,
                    agent_version=item.agent_version,
                    boottime=item.boottime,
                    pid=item.pid,
                    wake_reason=item.wake_reason,
                    reachability_target=item.reachability_target,
                    detail=item.detail,
                )
                AgentLifecycleRepository.create(db, event)

            # Whether newly inserted or already present, this event_uid is
            # now durably stored -- the client may safely prune it from
            # its local queue either way. A duplicate/retried delivery is
            # a silent no-op, never a second row (idempotency requirement).
            accepted_event_uids.append(item.event_uid)

        return AgentLifecycleSyncResponse(
            status="success",
            accepted_event_uids=accepted_event_uids,
        )
