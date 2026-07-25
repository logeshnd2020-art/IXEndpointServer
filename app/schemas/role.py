from typing import Optional

from pydantic import BaseModel


class RoleResponse(BaseModel):
    id: int
    name: str
    description: Optional[str]

    model_config = {
        "from_attributes": True,
    }
