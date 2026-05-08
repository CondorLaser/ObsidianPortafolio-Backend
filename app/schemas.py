from pydantic import BaseModel
from uuid import UUID
from datetime import datetime


class AssetResponse(BaseModel):

    id: UUID
    symbol: str
    name: str
    kind: str
    currency: str
    created_at: datetime

    class Config:
        from_attributes = True

