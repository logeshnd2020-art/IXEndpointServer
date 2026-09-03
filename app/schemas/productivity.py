from typing import List

from pydantic import BaseModel


class ApplicationUsageResponse(BaseModel):

    application: str

    elapsed_seconds: int

    idle_seconds: int

    active_seconds: int


class ProductivityResponse(BaseModel):

    hostname: str

    username: str

    working_seconds: int

    idle_seconds: int

    active_seconds: int

    # wall_clock_seconds - working_seconds: time excluded from monitored
    # time (confirmed sleep and/or unobserved monitoring gaps -- the two
    # cannot be distinguished with current agent telemetry, so both are
    # reported together, honestly, as one figure).
    sleep_seconds: int

    productivity_percent: float

    mouse_clicks: int

    keyboard_hits: int

    applications: List[ApplicationUsageResponse]
