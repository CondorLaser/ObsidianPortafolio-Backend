import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.asset import Asset
    from app.models.position_metrics import PositionDailyMetric


class Position(Base):
    """Posición materializada — cantidad neta + costo promedio + acumulados de
    PnL/dividends/fees para un par (account, asset). Diseñada por Eduardo, NO
    se computa automáticamente todavía. Sin TimestampMixin (Neon develop no
    tiene `created_at`)."""

    __tablename__ = "positions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="CASCADE"),
        nullable=False,
    )
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    avg_cost: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    realized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    total_dividends: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    total_fees: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    last_transaction_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    account: Mapped["Account"] = relationship(back_populates="positions")
    asset: Mapped["Asset"] = relationship()
    daily_metrics: Mapped[list["PositionDailyMetric"]] = relationship(
        back_populates="position",
        cascade="all, delete-orphan",
    )
