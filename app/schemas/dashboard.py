from pydantic import BaseModel

class DashboardSummaryResponse(BaseModel):
    devices: int
    active_sessions: int
    applications: int
    idle_events: int
    activity_events: int
