from pydantic import BaseModel, Field


class CallInitiateRequest(BaseModel):
    to_number: str = Field(..., max_length=30, description="E.164 phone number")
    caller_id: str | None = Field(None, max_length=30)
    use_case: str | None = Field(None, max_length=100)
    metadata: dict | None = None


class CallStatusUpdateRequest(BaseModel):
    status: str = Field(..., description="New status: in_progress, completed, failed, cancelled")
    transcript: str | None = None


class CallResponse(BaseModel):
    call_id: str
    status: str
    estimated_connect_ms: int | None = None
    webhook_registered: bool = False


class CallSummaryResponse(BaseModel):
    call_id: str
    summary: str | None
    key_points: list[str] | None
    entities: dict | None
    sentiment: str | None
    escalation_flagged: bool | None
    duration_seconds: int | None


class CallListResponse(BaseModel):
    calls: list[CallResponse]
    total: int
    page: int
    page_size: int
