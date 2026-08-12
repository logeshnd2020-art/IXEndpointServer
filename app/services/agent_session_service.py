from sqlalchemy.orm import Session

from app.models.device import Device
from app.models.session import Session as UserSession
from app.repositories.session_repository import SessionRepository
from app.schemas.agent_session import (
    AgentSessionSyncRequest,
    AgentSessionSyncResponse,
)


class AgentSessionService:

    @staticmethod
    def sync(
        db: Session,
        request: AgentSessionSyncRequest,
        device: Device,
    ) -> AgentSessionSyncResponse:

        if request.local_session_id <= 0:
            raise ValueError(
                "local_session_id must be greater than zero"
            )

        existing = SessionRepository.get_by_local_session_id(
            db=db,
            device_id=device.id,
            local_session_id=request.local_session_id,
        )

        created = False

        #########################################
        # Determine session state
        #########################################

        if request.logout_time is None:
            session_status = "ACTIVE"
        else:
            session_status = "LOGOUT"

        #########################################
        # Create Session
        #########################################

        if existing is None:

            session = UserSession(
                device_id=device.id,
                local_session_id=request.local_session_id,
                username=request.username,
                login_time=request.login_time,
                logout_time=request.logout_time,
                status=session_status,
            )

            session = SessionRepository.create(
                db,
                session,
            )

            created = True

        #########################################
        # Update Existing Session
        #########################################

        else:

            existing.username = request.username
            existing.login_time = request.login_time
            existing.logout_time = request.logout_time
            existing.status = session_status

            session = SessionRepository.update(
                db,
                existing,
            )

        return AgentSessionSyncResponse(
            status="success",
            server_session_id=session.id,
            local_session_id=request.local_session_id,
            session_status=session.status,
            created=created,
        )
