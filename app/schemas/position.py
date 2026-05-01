import uuid
from decimal import Decimal

from pydantic import BaseModel


class PositionRead(BaseModel):
    account_id: uuid.UUID
    asset_id: uuid.UUID
    symbol: str
    name: str
    quantity: Decimal
    avg_cost: Decimal | None
    last_price: Decimal | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
