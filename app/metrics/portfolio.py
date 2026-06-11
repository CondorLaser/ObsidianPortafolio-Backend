from decimal import Decimal
from statistics import stdev

from app.schemas.portfolio import PortfolioSnapshotRead


def calculate_portfolio_daily_metrics(snapshots: list[PortfolioSnapshotRead]) -> dict:
    if not snapshots:
        return {
            "portfolio_id": snapshots[-1].id if snapshots else None,
            "date": None,
            "pnl": Decimal("0"),
            "max_drawdown": Decimal("0"),
            "volatility": Decimal("0"),
        }
    
    return {
        "portfolio_id": snapshots[-1].id,
        "date": snapshots[-1].date,
        "pnl": calculate_pnl(snapshots),
        "max_drawdown": calculate_max_drawdown(snapshots),
        "volatility": calculate_volatility(snapshots),
    }


def calculate_pnl(snapshots: list[PortfolioSnapshotRead]) -> Decimal:
    if len(snapshots) < 2:
        return Decimal("0")

    today_total = snapshots[-1].realized_pnl + snapshots[-1].unrealized_pnl
    yesterday_total = snapshots[-2].realized_pnl + snapshots[-2].unrealized_pnl
    return today_total - yesterday_total


def calculate_max_drawdown(snapshots: list[PortfolioSnapshotRead]) -> Decimal:
    if not snapshots:
        return Decimal("0")

    peak = snapshots[0].total_value
    max_drawdown = Decimal("0")

    for snapshot in snapshots:
        value = snapshot.total_value

        if value > peak:
            peak = value

        drawdown = (value - peak) / peak

        if drawdown < max_drawdown:
            max_drawdown = drawdown

    return max_drawdown


def calculate_volatility(snapshots: list[PortfolioSnapshotRead]) -> Decimal:
    if len(snapshots) < 2:
        return Decimal("0")
    
    returns = []
    for i in range(1, len(snapshots)):
        prev = snapshots[i - 1].total_value
        curr = snapshots[i].total_value

        if prev == 0:
            continue

        returns.append((curr - prev) / prev)

    if len(returns) < 2:
        return 0
        
    return stdev(returns)


def calculate_twr():
    pass