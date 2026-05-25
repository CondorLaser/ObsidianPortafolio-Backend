from datetime import datetime

from pydantic import BaseModel, ConfigDict

from app.models.user import RiskProfile


class RiskProfileUpdate(BaseModel):
    risk_profile: RiskProfile


class UserRead(BaseModel):
    """Profile expuesto vía API. No hay `id` UUID — el identificador estable
    es `clerk_id` directamente (decisión arquitectónica del schema)."""

    model_config = ConfigDict(from_attributes=True)

    clerk_id: str
    email: str | None
    risk_profile: RiskProfile | None
    created_at: datetime
