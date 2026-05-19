import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal
from pydantic import BaseModel, ConfigDict

from app.models.transaction import TransactionKind


class RiskProfileUpdate(BaseModel):
    risk_profile: Literal[
        "conservador",
        "moderado",
        "agresivo",
    ]