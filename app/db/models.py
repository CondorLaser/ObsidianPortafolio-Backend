from sqlalchemy import Column, String, DateTime
from sqlalchemy.dialects.postgresql import UUID

from app.db.database import Base

class Asset(Base):
    __tablename__ = "asset"

    id = Column(UUID(as_uuid=True), primary_key=True)
    symbol = Column(String, nullable=False)
    name = Column(String, nullable=False)
    kind = Column(String, nullable=False)
    currency = Column(String(3), nullable=False)
    created_at = Column(DateTime)