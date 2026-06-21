"""DTOs para GET /portfolio/dashboard. Shape derivado del mock del frontend
(portfolio_snapshot.json + handlers.js)."""
import uuid
from datetime import date as date_type
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.position import PositionDerived


class PortfolioSnapshotRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    date: date_type | None
    total_value: dict | None
    total_invested: dict | None
    unrealized_pnl: dict | None
    realized_pnl: dict | None
    breakdown_by_currency: dict | None
    breakdown_by_account: dict | None


class TrendPoint(BaseModel):
    date: date_type
    value: Decimal


class AccountDistributionItem(BaseModel):
    account_id: uuid.UUID
    name: str
    amount: Decimal
    percentage: Decimal  # 0..1
    currency: str


class PortfolioSummary(BaseModel):
    # Escalares: poblados sólo si el user tiene 1 sola currency. Null si tiene
    # múltiples — sumar CLP + USD sin FX engañaría. Frontend cae a *_by_currency.
    total_value: Decimal | None
    total_invested: Decimal | None
    unrealized_pnl: Decimal | None
    total_value_by_currency: dict[str, Decimal]
    total_invested_by_currency: dict[str, Decimal]
    unrealized_pnl_by_currency: dict[str, Decimal]
    realized_pnl_by_currency: dict[str, Decimal]
    total_return_pct: Decimal | None
    total_return_pct_by_currency: dict[str, Decimal]
    active_positions: int
    linked_accounts: int
    last_snapshot_date: date_type | None


class PortfolioDashboard(BaseModel):
    summary: PortfolioSummary
    trend: list[TrendPoint]
    account_distribution: list[AccountDistributionItem]
    positions: list[PositionDerived]

# Para versión simplificada de /dashboard = /portfolio/summary
class PortfolioSummaryResponse(BaseModel):
    summary: PortfolioSummary
    account_distribution: list[AccountDistributionItem]
