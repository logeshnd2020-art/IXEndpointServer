from sqlalchemy.orm import Session

from app.models.application import Application
from app.models.device import Device
from app.repositories.application_repository import ApplicationRepository
from app.repositories.session_repository import SessionRepository
from app.schemas.agent_application import (
    AgentApplicationSyncRequest,
    AgentApplicationSyncResponse,
)


class AgentApplicationService:

    @staticmethod
    def sync(
        db: Session,
        request: AgentApplicationSyncRequest,
        device: Device,
    ) -> AgentApplicationSyncResponse:

        #########################################
        # Validate Local IDs
        #########################################

        if request.local_application_id <= 0:
            raise ValueError(
                "local_application_id must be greater than zero"
            )

        if request.local_session_id <= 0:
            raise ValueError(
                "local_session_id must be greater than zero"
            )

        #########################################
        # Resolve Local Session -> Server Session
        #########################################

        server_session = SessionRepository.get_by_local_session_id(
            db=db,
            device_id=device.id,
            local_session_id=request.local_session_id,
        )

        if server_session is None:
            raise ValueError(
                f"Server session not found for "
                f"local_session_id={request.local_session_id}"
            )

        #########################################
        # Check Existing Application
        #########################################

        existing = ApplicationRepository.get_by_local_application_id(
            db=db,
            device_id=device.id,
            local_application_id=request.local_application_id,
        )

        created = False

        #########################################
        # Create Application
        #########################################

        if existing is None:

            application = Application(
                device_id=device.id,
                session_id=server_session.id,
                local_application_id=request.local_application_id,
                application_name=request.application_name,
                window_title=request.window_title,
                start_time=request.start_time,
                end_time=request.end_time,
                duration_seconds=request.duration_seconds,
            )

            application = ApplicationRepository.create(
                db,
                application,
            )

            created = True

        #########################################
        # Update Existing Application
        #########################################

        else:

            existing.session_id = server_session.id
            existing.application_name = request.application_name
            existing.window_title = request.window_title
            existing.start_time = request.start_time
            existing.end_time = request.end_time
            existing.duration_seconds = request.duration_seconds

            application = ApplicationRepository.update(
                db,
                existing,
            )

        return AgentApplicationSyncResponse(
            status="success",
            server_application_id=application.id,
            local_application_id=request.local_application_id,
            server_session_id=server_session.id,
            local_session_id=request.local_session_id,
            created=created,
        )
