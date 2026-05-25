import uuid
from datetime import date as date_type
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.account import Account


class AccountDailyMetric(Base):
    __tablename__ = "account_daily_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    pnl: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    max_drawdown: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    volatility: Mapped[Decimal | None] = mapped_column(Numeric(8, 6), nullable=True)

    account: Mapped["Account"] = relationship(back_populates="daily_metrics")


class AccountMonthlyMetric(Base):
    __tablename__ = "account_monthly_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    twr: Mapped[Decimal | None] = mapped_column(Numeric(10, 8), nullable=True)
    dietz: Mapped[Decimal | None] = mapped_column(Numeric(10, 8), nullable=True)
    sharpe_ratio: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    var: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    sortino: Mapped[Decimal | None] = mapped_column(Numeric(6, 4), nullable=True)
    assets_correlation: Mapped[Decimal | None] = mapped_column(Numeric(5, 4), nullable=True)

    account: Mapped["Account"] = relationship(back_populates="monthly_metrics")
