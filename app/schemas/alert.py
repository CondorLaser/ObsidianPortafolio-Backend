import uuid
from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AlertRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    type: str
    trigger_field: str
    trigger_value: Decimal
    threshold_value: Decimal
    msg: str
    is_read: bool
    created_at: datetime
    notified_at: datetime | None
    last_triggered: date | None
    is_active: bool


class AlertUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_read: bool | None = None
    is_active: bool | None = None
