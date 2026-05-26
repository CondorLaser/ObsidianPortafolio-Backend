from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.user import RiskProfile


class RiskProfileUpdate(BaseModel):
    risk_profile: RiskProfile


class UserRead(BaseModel):
    """1:1 con ProfileResponse de Eduardo (mismo orden de campos)."""

    model_config = ConfigDict(from_attributes=True)

    clerk_id: str
    email: str | None
    created_at: datetime
    risk_profile: RiskProfile | None
