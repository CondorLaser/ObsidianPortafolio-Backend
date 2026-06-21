from decimal import Decimal
from statistics import stdev
from datetime import timedelta

from app.schemas.position import PositionRead

def calculate_position_daily_metrics(position: PositionRead, current_price: Decimal) -> dict:
    unrealized_pnl = calculate_unrealized_pnl(position, current_price)
    total_pnl = calculate_total_pnl(position, current_price)

    return {
        "position_id": position.id,
        "date": position.updated_at.date(),
        "unrealized_pnl": unrealized_pnl,
        "total_pnl": total_pnl,
    }


def calculate_unrealized_pnl(position: PositionRead, current_price: Decimal) -> Decimal:
    quantity = position.quantity or Decimal("0")
    avg_cost = position.avg_cost or Decimal("0")
    return (current_price - avg_cost) * quantity


def calculate_total_pnl(position: PositionRead, current_price: Decimal) -> Decimal:
    realized = position.realized_pnl or Decimal("0")
    unrealized = calculate_unrealized_pnl(position, current_price)
    return realized + unrealized
