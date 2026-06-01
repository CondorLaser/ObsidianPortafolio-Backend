"""DTOs para el dashboard de portafolio.

Shape compatible con el mock del frontend (src/mocks/data/portfolio_snapshot.json
y handlers.js `getPortfolioSummary/Trend`). Devolvemos data CRUDA (Decimal/ISO
date); el frontend formatea con Intl.
"""
import uuid
from datetime import date as date_type
from decimal import Decimal

from pydantic import BaseModel, ConfigDict

from app.schemas.position import PositionDerived


class PortfolioSnapshotRead(BaseModel):
    """Una foto diaria del patrimonio del usuario (lectura 1:1 de la tabla)."""

    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
    date: date_type | None
    total_value: Decimal | None
    total_invested: Decimal | None
    unrealized_pnl: Decimal | None
    realized_pnl: Decimal | None
    breakdown_by_currency: dict | None
    breakdown_by_account: dict | None


class TrendPoint(BaseModel):
    """Un punto de la serie de evolución del portafolio."""

    date: date_type
    value: Decimal


class AccountDistributionItem(BaseModel):
    """Peso de una cuenta sobre el total del portafolio en el último snapshot."""

    account_id: uuid.UUID
    name: str
    amount: Decimal
    percentage: Decimal  # 0..1 (frontend lo multiplica x100)
    currency: str


class PortfolioSummary(BaseModel):
    """Métricas agregadas del último snapshot disponible.

    Si el user tiene 1 sola currency, total_value/total_invested/unrealized_pnl
    son la suma honesta en esa moneda. Si tiene múltiples (USD + CLP), esos
    3 campos vienen en NULL (sumar sin FX engañaría) y el frontend debe
    iterar los *_by_currency para mostrar 1 card por moneda.
    """

    total_value: Decimal | None
    total_invested: Decimal | None
    unrealized_pnl: Decimal | None
    total_value_by_currency: dict[str, Decimal]
    total_invested_by_currency: dict[str, Decimal]
    unrealized_pnl_by_currency: dict[str, Decimal]
    total_return_pct: Decimal | None  # variación vs snapshot anterior (0..1)
    active_positions: int
    linked_accounts: int
    last_snapshot_date: date_type | None


class PortfolioDashboard(BaseModel):
    """Response de GET /portfolio/dashboard — agrega summary + trend +
    distribución por cuenta + posiciones derivadas en un solo response."""

    summary: PortfolioSummary
    trend: list[TrendPoint]
    account_distribution: list[AccountDistributionItem]
    positions: list[PositionDerived]
