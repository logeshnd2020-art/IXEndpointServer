from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.idle import IdleEvent
from app.repositories.idle_repository import IdleRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.agent_idle import (
    AgentIdleSyncRequest,
    AgentIdleSyncResponse,
)


class AgentIdleService:

    @staticmethod
    def sync(
        db: Session,
        request: AgentIdleSyncRequest,
        device: Device,
    ) -> AgentIdleSyncResponse:

        server_session = SessionRepository.get_by_local_session_id(
            db=db,
            device_id=device.id,
            local_session_id=request.local_session_id,
        )

        if server_session is None:
            raise ValueError(
                f"Session mapping not found: "
                f"local_session_id={request.local_session_id}"
            )

        existing = IdleRepository.get_by_local_idle_id(
            db=db,
            device_id=device.id,
            local_idle_id=request.local_idle_id,
        )

        created = False

        if existing is None:

            idle = IdleEvent(
                device_id=device.id,
                session_id=server_session.id,
                local_idle_id=request.local_idle_id,
                idle_start=request.idle_start,
                idle_end=request.idle_end,
                idle_seconds=request.idle_seconds,
            )

            idle = IdleRepository.create(db, idle)
            created = True

        else:

            existing.session_id = server_session.id
            existing.idle_start = request.idle_start
            existing.idle_end = request.idle_end
            existing.idle_seconds = request.idle_seconds

            idle = IdleRepository.update(db, existing)

        return AgentIdleSyncResponse(
            status="success",
            server_idle_id=idle.id,
            local_idle_id=request.local_idle_id,
            server_session_id=server_session.id,
            local_session_id=request.local_session_id,
            created=created,
        )
