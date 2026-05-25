import uuid
from datetime import date as date_type
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Index, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Dividend(Base, TimestampMixin):
    """Dividendo recibido en una cuenta para un asset. Cargado desde PDF (Fintual)
    o registrado manualmente. Inmutable como `Transaction`."""

    __tablename__ = "dividend"
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
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("asset.id", ondelete="RESTRICT"),
        nullable=False,
    )
    date: Mapped[date_type] = mapped_column(Date, nullable=False)
    gross_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    tax_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
    net_amount: Mapped[Decimal | None] = mapped_column(Numeric(18, 2), nullable=True)
