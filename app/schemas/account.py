import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.schemas.dividend import DividendRead
from app.schemas.position import PositionRead
from app.schemas.transaction import TransactionRead


class AccountBase(BaseModel):
    name: str
    broker: str | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)


class AccountCreate(AccountBase):
    pass


class AccountRead(BaseModel):
    """Orden de campos matchea SELECT * FROM accounts (Eduardo)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    broker: str | None = None
    currency: str = Field(default="USD", min_length=3, max_length=3)
    created_at: datetime
    user_id: str  # clerk_id (varchar)

class AccountWithCountersRead(BaseModel):
    account: AccountRead
    stock_positions: int = 0
    fund_positions: int = 0
    etf_positions: int = 0

class AccountDetailRead(AccountRead):
    """1:1 con contrato Eduardo: account + dividends + positions + transactions."""

    dividends: list[DividendRead] = []
    positions: list[PositionRead] = []
    transactions: list[TransactionRead] = []
