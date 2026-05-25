import uuid
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.user import Profile


class UserPreference(Base):
    """Umbrales que configura el usuario para alertas (PnL, drawdown, weights,
    currency exposure). Diseñada por Eduardo. Sin TimestampMixin (Neon develop
    no lo tiene).
    """

    __tablename__ = "user_preferences"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("profiles.clerk_id"),
        nullable=False,
        index=True,
    )
    pnl_percentage_account_daily: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    pnl_percentage_asset_daily: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    max_drawdown_portfolio_daily: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    max_drawdown_account_daily: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    asset_weight_weekly: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )
    currency_exposure_weekly: Mapped[Decimal | None] = mapped_column(
        Numeric(5, 4), nullable=True
    )

    user: Mapped["Profile"] = relationship(back_populates="preferences")
