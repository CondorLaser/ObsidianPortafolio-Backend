import uuid
from datetime import date as date_type
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import UniqueConstraint
from app.models.base import Base

if TYPE_CHECKING:
    from app.models.portfolio_snapshot import PortfolioSnapshot

class PortfolioDailyMetric(Base):
    __tablename__ = "portfolio_daily_metrics"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_portfolio_daily_metrics_user_date"),
    )
    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("profiles.clerk_id"), nullable=False)
    date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    pnl: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    max_drawdown: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    volatility: Mapped[dict | None] = mapped_column(JSONB, nullable=True)


class PortfolioMonthlyMetric(Base):
    __tablename__ = "portfolio_monthly_metrics"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_portfolio_monthly_metrics_user_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[str] = mapped_column(String, ForeignKey("profiles.clerk_id"), nullable=False)
    date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    twr: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    var: Mapped[dict | None] = mapped_column(JSONB, nullable=True)