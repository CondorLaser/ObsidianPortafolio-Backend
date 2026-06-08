import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.models.transaction import TransactionKind
from app.schemas.asset import AssetRead 


class TransactionBase(BaseModel):
    account_id: uuid.UUID
    asset_id: uuid.UUID
    kind: TransactionKind
    quantity: Decimal
    price: Decimal | None = None
    fee: Decimal = Decimal("0")
    executed_at: datetime


class TransactionCreate(TransactionBase):
    pass


class TransactionRead(TransactionBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    created_at: datetime
    asset: AssetRead
