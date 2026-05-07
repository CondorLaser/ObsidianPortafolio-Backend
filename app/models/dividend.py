import uuid
from sqlalchemy import Date, ForeignKey, Numeric
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin


class Dividend(Base):
    __tablename__ = "dividend"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("account.id"),
        nullable=False,
    )
    asset_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("asset.id"),
        nullable=False,
    )
    date: Mapped[Date] = mapped_column(Date, nullable=False)
    gross_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=True)
    tax_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=True)
    net_amount: Mapped[float] = mapped_column(Numeric(18, 2), nullable=True)