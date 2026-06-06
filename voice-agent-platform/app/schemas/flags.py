from typing import Any

from pydantic import BaseModel


class FlagResponse(BaseModel):
    flag_key: str
    flag_value: Any
    is_default: bool


class FlagUpdateRequest(BaseModel):
    value: Any
