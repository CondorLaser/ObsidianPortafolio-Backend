from pydantic import BaseModel
from uuid import UUID
from datetime import datetime
from datetime import datetime, date
from decimal import Decimal


class AssetResponse(BaseModel):
    id: UUID
    symbol: str
    name: str
    kind: str
    currency: str
    created_at: datetime

    class Config:
        from_attributes = True


class AssetPriceResponse(BaseModel):
    asset_id: UUID
    date: date
    close: Decimal
    currency: str
    source: str | None

    class Config:
        from_attributes = True


class DividendResponse(BaseModel):
    id: UUID
    account_id: UUID
    asset_id: UUID
    date: date
    gross_amount: Decimal
    tax_amount: Decimal
    net_amount: Decimal

    class Config:
        from_attributes = True


class TransactionResponse(BaseModel):
    id: UUID
    account_id: UUID
    asset_id: UUID
    kind: str
    quantity: Decimal
    price: Decimal
    fee: Decimal
    executed_at: datetime
    created_at: datetime
    date: date | None

    class Config:
        from_attributes = True


class AssetDetailResponse(BaseModel):
    id: UUID
    symbol: str
    name: str
    kind: str
    currency: str
    created_at: datetime
    prices: list[AssetPriceResponse]
    dividends: list[DividendResponse]
    transactions: list[TransactionResponse]

    class Config:
        from_attributes = True


class UserResponse(BaseModel):
    id: UUID
    clerk_id: str
    email: str | None
    created_at: datetime
    risk_profile: str | None

    class Config:
        from_attributes = True

