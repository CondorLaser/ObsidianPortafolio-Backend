import uuid
from datetime import date as date_type
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class AccountDailyMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    date: date_type | None
    pnl: Decimal | None
    max_drawdown: Decimal | None
    volatility: Decimal | None


class AccountMonthlyMetricRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    account_id: uuid.UUID
    date: date_type | None
    twr: Decimal | None
    dietz: Decimal | None
    sharpe_ratio: Decimal | None
    var: Decimal | None
    sortino: Decimal | None
    assets_correlation: Decimal | None


class AccountMetricsRead(BaseModel):
    """Combinado: daily + monthly para un account. Eduardo no implementó la
    lógica de cómputo; las arrays vienen vacías hasta que se popule."""

    daily: list[AccountDailyMetricRead] = []
    monthly: list[AccountMonthlyMetricRead] = []
