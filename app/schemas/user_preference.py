import uuid
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class UserPreferenceFields(BaseModel):
    """Umbrales que configura el usuario para alertas. Todos opcionales."""

    pnl_percentage_account_daily: Decimal | None = None
    pnl_percentage_asset_daily: Decimal | None = None
    max_drawdown_portfolio_daily: Decimal | None = None
    max_drawdown_account_daily: Decimal | None = None
    asset_weight_weekly: Decimal | None = None
    currency_exposure_weekly: Decimal | None = None


class UserPreferenceUpdate(UserPreferenceFields):
    """Body para PUT /preferences (upsert): cualquier subset de los umbrales."""


class UserPreferenceRead(UserPreferenceFields):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    user_id: str
