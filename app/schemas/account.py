import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.dividend import DividendRead
from app.schemas.transaction import TransactionRead


class AccountBase(BaseModel):
    name: str
    broker: str | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)


class AccountCreate(AccountBase):
    pass


class AccountRead(AccountBase):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str  # clerk_id (varchar), no UUID interno
    created_at: datetime


class AccountDetailRead(AccountRead):
    transactions: list[TransactionRead] = []
    dividends: list[DividendRead] = []
