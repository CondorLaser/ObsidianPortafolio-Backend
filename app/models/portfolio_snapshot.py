import uuid
from datetime import date as date_type
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.portfolio_metrics import (
        PortfolioDailyMetric,
        PortfolioMonthlyMetric,
    )
    from app.models.user import Profile


class PortfolioSnapshot(Base):
    """Foto diaria del patrimonio del usuario. Diseñada por Eduardo, sin código
    que la llene todavía. Sin TimestampMixin (Neon develop no tiene `created_at`).
    """

    __tablename__ = "portfolio_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("profiles.clerk_id"),
        nullable=False,
        index=True,
    )
    date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    total_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    total_invested: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    unrealized_pnl: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    realized_pnl: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    breakdown_by_currency: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    breakdown_by_account: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    user: Mapped["Profile"] = relationship("Profile", back_populates="portfolio_snapshots")

