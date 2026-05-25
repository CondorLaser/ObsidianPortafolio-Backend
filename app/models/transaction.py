import enum
import uuid
from datetime import date as date_type, datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.asset import Asset


class TransactionKind(str, enum.Enum):
    buy = "buy"
    sell = "sell"
    dividend = "dividend"
    fee = "fee"
    deposit = "deposit"
    withdrawal = "withdrawal"


class Transaction(Base, TimestampMixin):
    __tablename__ = "transaction"
    __table_args__ = (
        Index("ix_transaction_account_executed", "account_id", "executed_at"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("asset.id", ondelete="RESTRICT"),
        nullable=False,
    )
    kind: Mapped[TransactionKind] = mapped_column(
        Enum(TransactionKind, name="transaction_kind"), nullable=False
    )
    quantity: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    price: Mapped[Decimal | None] = mapped_column(Numeric(20, 8), nullable=True)
    fee: Mapped[Decimal] = mapped_column(
        Numeric(20, 8), nullable=False, server_default="0"
    )
    executed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    # `date` (sin tz) usado por la ingesta de PDF cuando solo se conoce el día,
    # no la hora exacta. Nullable: los registros existentes y los creados vía
    # API mantienen el `executed_at` como fuente canónica.
    date_: Mapped[date_type | None] = mapped_column("date", Date, nullable=True)

    account: Mapped["Account"] = relationship(back_populates="transactions")
    asset: Mapped["Asset"] = relationship(back_populates="transactions")
