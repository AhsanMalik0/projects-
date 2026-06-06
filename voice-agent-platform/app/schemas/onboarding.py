from pydantic import BaseModel, Field


class TenantRegisterRequest(BaseModel):
    name: str = Field(..., max_length=255, description="Business display name")
    industry: str | None = Field(None, max_length=100)
    use_case: str | None = Field(None, max_length=100)
    webhook_url: str | None = Field(None, max_length=500)


class TenantRegisterResponse(BaseModel):
    tenant_id: str
    api_key: str
    status: str
    message: str


class TenantConfigureRequest(BaseModel):
    use_case: str | None = Field(None, max_length=100)
    persona_prompt: str | None = None
    webhook_url: str | None = Field(None, max_length=500)
    industry: str | None = Field(None, max_length=100)


class TenantStatusResponse(BaseModel):
    tenant_id: str
    name: str
    status: str
    use_case: str | None
    webhook_url: str | None
    created_at: str | None
