import uuid
from datetime import date, datetime
from decimal import Decimal

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin


class Alert(Base, TimestampMixin):
    __tablename__ = "alerts"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        primary_key=True,
        default=uuid.uuid4,
    )
    user_id: Mapped[str] = mapped_column(
    String,
    ForeignKey("profiles.clerk_id"),
    nullable=False,
    index=True,
    )
    type: Mapped[str] = mapped_column(String, nullable=False)
    trigger_field: Mapped[str] = mapped_column(String, nullable=False)
    trigger_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    threshold_value: Mapped[Decimal] = mapped_column(Numeric(20, 8), nullable=False)
    msg: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    notified_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=False),
        nullable=True,
    )
    last_triggered: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
