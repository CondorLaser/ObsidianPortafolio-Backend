import uuid
from datetime import date as date_type, datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class DividendRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    asset_id: uuid.UUID
    date: date_type
    gross_amount: Decimal | None
    tax_amount: Decimal | None
    net_amount: Decimal | None
    created_at: datetime
