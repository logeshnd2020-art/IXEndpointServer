from pydantic import BaseModel


class ProductivityResponse(BaseModel):
    hostname: str
    username: str
    working_seconds: int
    idle_seconds: int
    active_seconds: int
    productivity_percent: float
    mouse_clicks: int
    keyboard_hits: int
