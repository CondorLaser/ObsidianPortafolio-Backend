import enum
import uuid
from typing import TYPE_CHECKING

from sqlalchemy import Enum, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.account import Account


class RiskProfileKind(str, enum.Enum):
    conservative = "conservative"
    moderate = "moderate"
    agressive = "agressive"


class User(Base, TimestampMixin):
    __tablename__ = "profiles"

    # id: Mapped[uuid.UUID] = mapped_column(
    #     UUID(as_uuid=True),
    #     primary_key=True,
    #     default=uuid.uuid4,
    # )
    clerk_id: Mapped[str] = mapped_column(
        String, unique=True, nullable=False, index=True, primary_key=True
    )
    email: Mapped[str | None] = mapped_column(String, nullable=True)

    accounts: Mapped[list["Account"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )

    risk_profile: Mapped[RiskProfileKind | None] = mapped_column(
        Enum(RiskProfileKind, name="risk_profile_kind"), nullable=True
    )
