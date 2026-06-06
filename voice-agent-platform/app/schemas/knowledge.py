from pydantic import BaseModel


class KnowledgeUploadResponse(BaseModel):
    doc_id: str
    filename: str
    status: str
    message: str


class KnowledgeListResponse(BaseModel):
    documents: list[KnowledgeUploadResponse]
    total: int
    page: int
    page_size: int
