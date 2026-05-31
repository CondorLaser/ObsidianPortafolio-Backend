import uuid
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.account_metrics import (
        AccountDailyMetric,
        AccountMonthlyMetric,
    )
    from app.models.dividend import Dividend
    from app.models.position import Position
    from app.models.transaction import Transaction
    from app.models.user import Profile


class Account(Base, TimestampMixin):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[str] = mapped_column(
        String,
        ForeignKey("profiles.clerk_id"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    broker: Mapped[str | None] = mapped_column(String, nullable=True)
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="USD"
    )

    user: Mapped["Profile"] = relationship(back_populates="accounts")
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    dividends: Mapped[list["Dividend"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    positions: Mapped[list["Position"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    daily_metrics: Mapped[list["AccountDailyMetric"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
    monthly_metrics: Mapped[list["AccountMonthlyMetric"]] = relationship(
        back_populates="account",
        cascade="all, delete-orphan",
    )
