from datetime import datetime
from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.agent_lifecycle_event import AgentLifecycleEvent


class AgentLifecycleRepository:

    @staticmethod
    def get_by_event_uid(
        db: Session,
        device_id: int,
        event_uid: str,
    ) -> Optional[AgentLifecycleEvent]:
        return (
            db.query(AgentLifecycleEvent)
            .filter(
                AgentLifecycleEvent.device_id == device_id,
                AgentLifecycleEvent.event_uid == event_uid,
            )
            .first()
        )

    @staticmethod
    def create(db: Session, event: AgentLifecycleEvent) -> AgentLifecycleEvent:
        db.add(event)
        db.commit()
        db.refresh(event)
        return event

    @staticmethod
    def get_events_in_window(
        db: Session,
        device_id: int,
        window_start: datetime,
        window_end: datetime,
    ) -> List[AgentLifecycleEvent]:
        """
        All events for this device whose event_time falls in
        [window_start, window_end], ordered chronologically by event_time
        (never by upload_time/arrival order -- a backlog uploaded after an
        extended outage must still be interpreted in the order things
        actually happened).
        """
        return (
            db.query(AgentLifecycleEvent)
            .filter(
                AgentLifecycleEvent.device_id == device_id,
                AgentLifecycleEvent.event_time >= window_start,
                AgentLifecycleEvent.event_time <= window_end,
            )
            .order_by(AgentLifecycleEvent.event_time.asc(), AgentLifecycleEvent.id.asc())
            .all()
        )

    @staticmethod
    def get_last_event_before(
        db: Session,
        device_id: int,
        event_type: str,
        before: datetime,
    ) -> Optional[AgentLifecycleEvent]:
        """Most recent event of `event_type` with event_time < `before`."""
        return (
            db.query(AgentLifecycleEvent)
            .filter(
                AgentLifecycleEvent.device_id == device_id,
                AgentLifecycleEvent.event_type == event_type,
                AgentLifecycleEvent.event_time < before,
            )
            .order_by(AgentLifecycleEvent.event_time.desc(), AgentLifecycleEvent.id.desc())
            .first()
        )
