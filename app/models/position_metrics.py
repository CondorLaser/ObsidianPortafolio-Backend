import uuid
from datetime import date as date_type
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base

if TYPE_CHECKING:
    from app.models.position import Position


class PositionDailyMetric(Base):
    __tablename__ = "position_daily_metrics"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    position_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("positions.id", ondelete="CASCADE"),
        nullable=False,
    )
    date: Mapped[date_type | None] = mapped_column(Date, nullable=True)
    pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    unrealized_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    total_pnl: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    personal_return: Mapped[Decimal | None] = mapped_column(Numeric(10, 4), nullable=True)

    position: Mapped["Position"] = relationship(back_populates="daily_metrics")
