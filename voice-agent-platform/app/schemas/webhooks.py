from pydantic import BaseModel, Field


class WebhookRegisterRequest(BaseModel):
    url: str = Field(..., max_length=500)
    events: str = Field(default="call.completed", max_length=500)


class WebhookResponse(BaseModel):
    id: str
    url: str
    events: str
    is_active: bool
    webhook_secret: str | None = None
