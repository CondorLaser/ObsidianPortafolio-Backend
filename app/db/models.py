from sqlalchemy import Column, String, DateTime, Date, Numeric, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.db.database import Base

class Asset(Base):
    __tablename__ = "asset"

    id = Column(UUID(as_uuid=True), primary_key=True)
    symbol = Column(String, nullable=False)
    name = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    currency = Column(String(3), nullable=False)
    created_at = Column(DateTime)

    prices = relationship("AssetPrice", back_populates="asset")
    dividends = relationship("Dividend", back_populates="asset")
    transactions = relationship("Transaction", back_populates="asset")


class AssetPrice(Base):
    __tablename__ = "asset_price"

    asset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("asset.id"),
        primary_key=True
    )
    date = Column(Date, primary_key=True)
    close = Column(Numeric(20, 8), nullable=False)
    currency = Column(String(3), nullable=False)
    source = Column(String)
    asset = relationship(
        "Asset",
        back_populates="prices"
    )


class Dividend(Base):
    __tablename__ = "dividend"

    id = Column(UUID(as_uuid=True), primary_key=True)
    account_id = Column(UUID(as_uuid=True))
    asset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("asset.id")
    )
    date = Column(Date, nullable=False)
    gross_amount = Column(Numeric(18, 2))
    tax_amount = Column(Numeric(18, 2))
    net_amount = Column(Numeric(18, 2))
    asset = relationship(
        "Asset",
        back_populates="dividends"
    )


class Transaction(Base):
    __tablename__ = "transaction"

    id = Column(UUID(as_uuid=True), primary_key=True)
    account_id = Column(UUID(as_uuid=True))
    asset_id = Column(
        UUID(as_uuid=True),
        ForeignKey("asset.id")
    )
    kind = Column(String)
    quantity = Column(Numeric(20, 8))
    price = Column(Numeric(20, 8))
    fee = Column(Numeric(20, 8))
    executed_at = Column(DateTime(timezone=True))
    created_at = Column(DateTime(timezone=True))
    date = Column(Date)
    asset = relationship(
        "Asset",
        back_populates="transactions"
    )


