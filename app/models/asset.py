import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.asset_price import AssetPrice
    from app.models.transaction import Transaction


class AssetKind(str, enum.Enum):
    stock = "stock"
    etf = "etf"
    fund = "fund"
    crypto = "crypto"
    other = "other"


class Asset(Base, TimestampMixin):
    __tablename__ = "asset"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    symbol: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    kind: Mapped[AssetKind] = mapped_column(
        Enum(AssetKind, name="asset_kind"), nullable=False
    )
    currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="USD"
    )

    prices: Mapped[list["AssetPrice"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="asset"
    )
