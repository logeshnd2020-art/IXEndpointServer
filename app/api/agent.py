from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.auth import get_current_device
from app.core.database import get_db
from app.exceptions.device import DeviceAlreadyExists
from app.schemas.device import AgentRegisterRequest, AgentRegisterResponse
from app.schemas.heartbeat import AgentHeartbeatRequest, AgentHeartbeatResponse
from app.services.agent_service import AgentService

router = APIRouter(
    prefix="/api/agent",
    tags=["Agent"],
)


@router.post(
    "/register",
    response_model=AgentRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"description": "Bad request"},
        403: {"description": "Invalid or unauthorized enrollment key"},
        409: {"description": "Device conflict or duplicate registration"},
        422: {"description": "Validation error"},
    },
)
def register_agent(
    request: AgentRegisterRequest,
    db: Session = Depends(get_db),
):
    try:
        return AgentService.register_agent(db, request)
    except PermissionError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    except DeviceAlreadyExists as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc))


@router.post(
    "/heartbeat",
    response_model=AgentHeartbeatResponse,
    status_code=status.HTTP_200_OK,
    responses={
        400: {"description": "Bad request"},
        401: {"description": "Invalid device token or authentication failed"},
        404: {"description": "Device not found"},
        422: {"description": "Validation error"},
    },
)
async def heartbeat(
    request: Request,
    heartbeat: AgentHeartbeatRequest,
    current_device=Depends(get_current_device),
    db: Session = Depends(get_db),
):
    body = await request.body()
    print('=== AGENT HEARTBEAT RECEIVED ===')
    print('headers:', dict(request.headers))
    print('raw body:', body.decode('utf-8', errors='replace'))
    return AgentService.heartbeat(db, heartbeat, current_device)
