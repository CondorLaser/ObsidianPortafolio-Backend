import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.asset_metrics import AssetDailyMetric, AssetMonthlyMetric
    from app.models.asset_price import AssetPrice
    from app.models.transaction import Transaction


class AssetKind(str, enum.Enum):
    stock = "stock"
    etf = "etf"
    fund = "fund"
    crypto = "crypto"
    other = "other"


class Asset(Base, TimestampMixin):
    __tablename__ = "assets"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    # NO unique: Neon develop permite mismo symbol para asset_kind distintos
    # (ej. "A" es tanto stock Agilent como fondo Fintual). Disambiguación en
    # consultas se hace por (symbol, kind).
    symbol: Mapped[str] = mapped_column(String, nullable=False, index=True)
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
        order_by="AssetPrice.date.desc()",  # 1:1 con contrato Eduardo
    )
    transactions: Mapped[list["Transaction"]] = relationship(
        back_populates="asset"
    )
    daily_metrics: Mapped[list["AssetDailyMetric"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )
    monthly_metrics: Mapped[list["AssetMonthlyMetric"]] = relationship(
        back_populates="asset",
        cascade="all, delete-orphan",
    )
