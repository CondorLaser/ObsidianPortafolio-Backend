import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.user import RiskProfile


class RiskProfileUpdate(BaseModel):
    risk_profile: RiskProfile


class UserRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    clerk_id: str
    email: str | None
    risk_profile: RiskProfile | None
    created_at: datetime
