from datetime import datetime
from pydantic import BaseModel


class CurrentApplicationResponse(BaseModel):
    hostname: str
    username: str
    application: str
    window_title: str
    started_at: datetime
    # True when the agent has not yet reported this application as closed
    # (end_time IS NULL) -- i.e. it is genuinely still in the foreground.
    # False means this is the most recently reported application usage
    # interval for the session, already closed, shown as a best-effort
    # "last used" value because the agent (v7.7.8) reports app-switch
    # events as already-closed intervals rather than leaving one open.
    is_currently_open: bool
