import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict
from app.schemas.asset import AssetRead


class PositionDerived(BaseModel):
    """Posición DERIVADA en runtime desde transactions + asset_prices.
    Usado en GET /positions (cálculo on-the-fly, NO lee tabla `positions`)."""

    account_id: uuid.UUID
    asset_id: uuid.UUID
    symbol: str
    name: str
    quantity: Decimal
    avg_cost: Decimal | None
    last_price: Decimal | None
    market_value: Decimal | None
    unrealized_pnl: Decimal | None
    asset: AssetRead


class PositionRead(BaseModel):
    """Posición MATERIALIZADA — lee de la tabla `positions` (1:1 con columnas
    en Neon). Embebida en GET /accounts/{id} matcheando el contrato de Eduardo."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    asset_id: uuid.UUID
    quantity: Decimal | None
    avg_cost: Decimal | None
    realized_pnl: Decimal | None
    total_dividends: Decimal | None
    total_fees: Decimal | None
    last_transaction_at: datetime | None
    updated_at: datetime | None
    asset: AssetRead

class PositionWrite(BaseModel):
    """Para poder crear una Posición Materializada, no incluye asset"""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    asset_id: uuid.UUID
    quantity: Decimal | None
    avg_cost: Decimal | None
    realized_pnl: Decimal | None
    total_dividends: Decimal | None
    total_fees: Decimal | None
    last_transaction_at: datetime | None
    updated_at: datetime | None
