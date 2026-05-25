import uuid
from datetime import date as date_type
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import Date, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.asset import Asset


class Dividend(Base, TimestampMixin):
    """Dividendo recibido en una cuenta para un asset. Cargado desde PDF (Fintual)
    o registrado manualmente. Inmutable como `Transaction`."""

    __tablename__ = "dividends"
    __table_args__ = (
        Index("ix_dividend_account_date", "account_id", "date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("assets.id", ondelete="RESTRICT"),
        nullable=False,
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    gross_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)

    account: Mapped["Account"] = relationship(back_populates="dividends")
    asset: Mapped["Asset"] = relationship()
