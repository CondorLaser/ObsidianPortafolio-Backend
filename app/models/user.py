import enum
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.portfolio_snapshot import PortfolioSnapshot
    from app.models.user_preference import UserPreference


class RiskProfile(str, enum.Enum):
    """Enum nombre: 'risk_profile_kind' en Postgres. Valores matchean exactamente
    los que están en Neon develop (incluye el typo 'agressive' — preservado para
    no romper la data existente; se puede normalizar a 'aggressive' en una
    migración aparte si el equipo lo decide).
    """

    moderate = "moderate"
    agressive = "agressive"
    conservative = "conservative"


class Profile(Base, TimestampMixin):
    """Espejo del usuario Clerk. PK es `clerk_id` directamente (no hay UUID
    interno) — schema importado de Neon develop, decisión arquitectónica de
    Eduardo: acoplar el modelo al identificador del proveedor de auth.
    """

    __tablename__ = "profiles"

    clerk_id: Mapped[str] = mapped_column(String, primary_key=True)
    email: Mapped[str | None] = mapped_column(String, nullable=True)
    risk_profile: Mapped[RiskProfile | None] = mapped_column(
        Enum(RiskProfile, name="risk_profile_kind"), nullable=True
    )

    accounts: Mapped[list["Account"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    portfolio_snapshots: Mapped[list["PortfolioSnapshot"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )
    preferences: Mapped[list["UserPreference"]] = relationship(
        back_populates="user",
        cascade="all, delete-orphan",
    )


# Alias retrocompatible para imports antiguos. Quitar en sprint siguiente.
User = Profile
