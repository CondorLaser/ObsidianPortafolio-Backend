import uuid
from datetime import date as date_type
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from sqlalchemy import UniqueConstraint

if TYPE_CHECKING:
    from app.models.asset import Asset


class AssetDailyMetric(Base):
    __tablename__ = "asset_daily_metrics"
    __table_args__ = (
        UniqueConstraint("asset_id", "date", name="asset_daily_metrics_asset_id_date_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    absolute_return: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    volatility: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)
    max_drawdown: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    asset: Mapped["Asset"] = relationship(back_populates="daily_metrics")


class AssetMonthlyMetric(Base):
    __tablename__ = "asset_monthly_metrics"
    __table_args__ = (
        UniqueConstraint("asset_id", "date", name="asset_monthly_metrics_asset_id_date_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    beta: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    asset: Mapped["Asset"] = relationship(back_populates="monthly_metrics")
