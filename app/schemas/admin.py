from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class EmployeeResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    name: str
    role: str
    rating: float
    is_available: bool


class RatingUpdate(BaseModel):
    delta: float = Field(..., description="Amount to add to current rating")


class KnowledgeAddRequest(BaseModel):
    question: str
    answer: str
    expert_id: UUID
    role: str
