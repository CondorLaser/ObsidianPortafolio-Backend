import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
from mailer.default_mailer import inmmediate_mail
from datetime import date, datetime
import uuid

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, desc, and_, or_, update, not_
from app.models.account import Account
from app.models.user_preference import UserPreference
from app.models.portfolio_snapshot import PortfolioSnapshot
from app.models.position import Position
from app.models.asset import Asset
from app.models.asset_price import AssetPrice
from app.models.account_metrics import AccountDailyMetric
from app.models.portfolio_metrics import PortfolioDailyMetric
from app.models.position_metrics import PositionDailyMetric
from app.models.alert import Alert
from app.models.user import Profile


# DEVOLVER TODAS LAS WARNINGS EN FORMATO [[type, valor_trigger, valor_real, mensaje], [ ], [ ] ]
async def warnings(db: AsyncSession, user_id: str, send_mail: bool = False):
    """Generate warnings for a user based on their preferences and portfolio state.
    
    Args:
        db: AsyncSession for database queries
        user_id: clerk_id of the user
        send_mail: Whether to send email notifications
        
    Returns:
        List of warnings in format [type, threshold, trigger_value, msg]
    """
    
    # Get accounts
    result = await db.execute(select(Account.id, Account.name).where(Account.user_id == user_id))
    accounts = result.all()  # [(id, name), (), (), ...]
    
    # Get user preferences
    result = await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
    preferences_obj = result.scalar_one_or_none()
    if preferences_obj is None:
        return []
    
    preferences = (
        preferences_obj.pnl_percentage_account_daily,
        preferences_obj.pnl_percentage_asset_daily,
        preferences_obj.max_drawdown_portfolio_daily,
        preferences_obj.max_drawdown_account_daily,
        preferences_obj.asset_weight_weekly,
    )
    
    # Get last 2 portfolio snapshots (today for asset weight, yesterday for P&L)
    result = await db.execute(
        select(PortfolioSnapshot.id, PortfolioSnapshot.date, PortfolioSnapshot.total_value, PortfolioSnapshot.breakdown_by_account)
        .where(PortfolioSnapshot.user_id == user_id)
        .order_by(desc(PortfolioSnapshot.date))
        .limit(2)
    )
    snapshots = result.all()
    snapshot_today = snapshots[0] if len(snapshots) >= 1 else None
    snapshot_yesterday = snapshots[1] if len(snapshots) >= 2 else None
    
    # ACCOUNT warnings
    warnings_found = []
    for account_id, account_name in accounts:
        aux = await warnings_account(db, account_id, account_name, preferences, snapshot_yesterday)
        warnings_found.extend(aux)
    
    account_ids = [row[0] for row in accounts]
    # Diccionario account_id -> account_name, used for portfolio warning messages
    account_names = {acc_id: acc_name for acc_id, acc_name in accounts}
    
    # PORTFOLIO warnings
    aux = await warnings_portfolio(db, user_id, account_ids, account_names, preferences, snapshot_today)
    warnings_found.extend(aux)
    
    # Get user email
    result = await db.execute(select(Profile.email).where(Profile.clerk_id == user_id))
    profile_row = result.scalar_one_or_none()
    
    if profile_row is not None and warnings_found:
        await warning_db_changes(db, user_id, warnings_found)
    
    if profile_row is not None and warnings_found and send_mail:
        await send_mails(db, profile_row, user_id)
    
    return warnings_found


async def warnings_account(db: AsyncSession, account_id: uuid.UUID, account_name: str, preferences: tuple, snapshot_yesterday: tuple):
    """Generate account-level warnings based on P&L and max drawdown."""
    warnings_found = []

    # P&L ACCOUNT
    preference_pnl_account = preferences[0]
    if preference_pnl_account is not None:
        result = await db.execute(
            select(AccountDailyMetric.pnl)
            .where(AccountDailyMetric.account_id == account_id)
            .order_by(desc(AccountDailyMetric.date))
            .limit(1)
        )
        latest_pnl = result.scalar_one_or_none()
        
        if latest_pnl is not None:
            if snapshot_yesterday is not None:
                snapshot_id, snapshot_date, total_value, breakdown_by_account = snapshot_yesterday
                account_value_yesterday = breakdown_by_account.get(str(account_id)) if breakdown_by_account else None
                if account_value_yesterday:
                    pnl_pct = round(float(latest_pnl) / float(account_value_yesterday), 4)
                    if abs(pnl_pct) > float(preference_pnl_account):
                        direction = "ganó" if pnl_pct > 0 else "perdió"
                        msg = f"La cuenta '{account_name}' {direction} {abs(pnl_pct):.1%} "
                        warnings_found.append(["P&L account", preference_pnl_account, pnl_pct, msg])

    # MAX DRAWDOWN ACCOUNT
    preference_max_drawdown_account = preferences[3]
    if preference_max_drawdown_account is not None:
        result = await db.execute(
            select(AccountDailyMetric.max_drawdown)
            .where(AccountDailyMetric.account_id == account_id)
            .order_by(desc(AccountDailyMetric.date))
            .limit(1)
        )
        max_drawdown = result.scalar_one_or_none()
        
        if max_drawdown is not None and abs(float(max_drawdown)) > float(preference_max_drawdown_account):
            msg = f"La cuenta '{account_name}' tiene un drawdown de {abs(float(max_drawdown)):.1%} respecto a su máximo histórico"
            warnings_found.append(["max_drawdown", preference_max_drawdown_account, max_drawdown, msg])

    return warnings_found


async def warnings_portfolio(db: AsyncSession, user_id: str, account_ids: list, account_names: dict, preferences: tuple, snapshot_today: tuple):
    """Generate portfolio-level warnings based on positions, weights, and drawdown."""
    warnings_found = []

    portfolio_id = None
    total_value = None
    if snapshot_today is not None:
        portfolio_id, _, total_value, _ = snapshot_today

        # MAX DRAWDOWN PORTFOLIO
        preference_max_drawdown_portfolio = preferences[2]
        if preference_max_drawdown_portfolio is not None and portfolio_id:
            result = await db.execute(
                select(PortfolioDailyMetric.max_drawdown)
                .where(PortfolioDailyMetric.portfolio_id == portfolio_id)
                .order_by(desc(PortfolioDailyMetric.date))
                .limit(1)
            )
            max_drawdown = result.scalar_one_or_none()
            
            if max_drawdown is not None and abs(float(max_drawdown)) > float(preference_max_drawdown_portfolio):
                msg = f"Tu portafolio tiene un max drawdown de {abs(float(max_drawdown)):.1%} respecto a su máximo histórico"
                warnings_found.append(["max_drawdown", preference_max_drawdown_portfolio, max_drawdown, msg])

    if account_ids:
        # Get all positions for these accounts
        result = await db.execute(
            select(Position.id, Position.quantity, Position.asset_id, Position.account_id,
                   Asset.symbol, Asset.name)
            .join(Asset, Position.asset_id == Asset.id)
            .where(Position.account_id.in_(account_ids))
        )
        positions_rows = result.all()
    else:
        positions_rows = []

    if positions_rows:
        position_ids = [row[0] for row in positions_rows]

        position_info = {
            row[0]: {
                "asset_id": row[2],
                "account_id": row[3],
                "symbol": row[4],
                "name": row[5],
                "quantity": row[1],
            }
            for row in positions_rows
        }

        # Get latest 2 asset prices for each position
        asset_ids = list({row[2] for row in positions_rows})
        asset_closes = {}
        for asset_id in asset_ids:
            result = await db.execute(
                select(AssetPrice.close)
                .where(AssetPrice.asset_id == asset_id)
                .order_by(desc(AssetPrice.date))
                .limit(2)
            )
            asset_closes[asset_id] = [row[0] for row in result.all()]

        position_data = {
            row[0]: {
                "asset_id": row[2],
                "quantity": row[1],
                "closes": asset_closes.get(row[2], []),
            }
            for row in positions_rows
        }

        # P&L ASSET
        preference_pnl_position = preferences[1]
        if preference_pnl_position is not None:
            today = date.today()
            result = await db.execute(
                select(PositionDailyMetric.position_id, PositionDailyMetric.pnl)
                .where(
                    PositionDailyMetric.position_id.in_(position_ids),
                    PositionDailyMetric.date == today
                )
            )
            pnl_by_position = {row[0]: row[1] for row in result.all()}

            for position_id, data in position_data.items():
                closes = data["closes"]
                pnl_dollars = pnl_by_position.get(position_id)
                if pnl_dollars is None or len(closes) < 2:
                    continue
                close_ayer = closes[1]
                quantity = data["quantity"]
                if not close_ayer or not quantity:
                    continue
                valor_posicion_ayer = float(quantity) * float(close_ayer)
                if not valor_posicion_ayer:
                    continue
                pnl_pct = round(float(pnl_dollars) / valor_posicion_ayer, 4)
                if abs(pnl_pct) > float(preference_pnl_position):
                    info = position_info.get(position_id, {})
                    asset_label = f"{info.get('name', 'Activo')} ({info.get('symbol', '')})"
                    acc_name = account_names.get(info.get("account_id"), "")
                    direction = "ganó" if pnl_pct > 0 else "perdió"
                    msg = f"{asset_label} {direction} {abs(pnl_pct):.1%} hoy en tu cuenta '{acc_name}'"
                    warnings_found.append(["P&L asset", preference_pnl_position, pnl_pct, msg])

        # PESO MAX
        preference_max_weight = preferences[4]
        if preference_max_weight is not None and total_value:
            asset_totals = {}
            for position_id, data in position_data.items():
                info = position_info.get(position_id, {})
                symbol = info.get("symbol", str(position_id))
                closes = data["closes"]
                close_hoy = closes[0] if closes else None
                quantity = data["quantity"]
                
                if close_hoy and quantity:
                    position_value = float(quantity) * float(close_hoy)
                    if symbol not in asset_totals:
                        asset_totals[symbol] = {
                            "total_value": 0,
                            "name": info.get("name", "Activo"),
                            "symbol": symbol
                        }
                    asset_totals[symbol]["total_value"] += position_value

            for symbol, asset_data in asset_totals.items():
                weight = round(asset_data["total_value"] / float(total_value), 4)
                if abs(weight) > float(preference_max_weight):
                    asset_label = f"{asset_data['name']} ({symbol})"
                    msg = f"{asset_label} representa {weight:.1%} de tu portafolio total"
                    warnings_found.append(["asset_weight", preference_max_weight, weight, msg])

    return warnings_found


async def send_mails(db: AsyncSession, email: str, user_id: str):
    """Send email notifications based on stored alerts."""
    
    ON_CHANGE = {"max_drawdown", "asset_weight"}
    today = date.today()

    # P&L alerts: send all active ones notified today
    result = await db.execute(
        select(Alert.type, Alert.trigger_value, Alert.threshold_value, Alert.msg)
        .where(
            Alert.user_id == user_id,
            Alert.type.notin_(ON_CHANGE),
            Alert.is_active == True,
            Alert.notified_at >= datetime.combine(today, datetime.min.time())
        )
    )
    always = result.all()

    # ON_CHANGE alerts: only new or reactivated (notified today)
    result = await db.execute(
        select(Alert.type, Alert.trigger_value, Alert.threshold_value, Alert.msg)
        .where(
            Alert.user_id == user_id,
            Alert.type.in_(ON_CHANGE),
            Alert.is_active == True,
            Alert.notified_at >= datetime.combine(today, datetime.min.time())
        )
    )
    on_change_new = result.all()

    to_notify = always + on_change_new
    if to_notify:
        alerts_for_mail = [[w[0], w[1], w[2], w[3]] for w in to_notify]
        return inmmediate_mail(email, alerts_for_mail)


async def warning_db_changes(db: AsyncSession, user_id: str, warnings_found: list):
    """Store warnings in the alerts table."""
    
    today = date.today()
    now = datetime.utcnow()
    ON_CHANGE = {"max_drawdown", "asset_weight"}

    for w_type, threshold, trigger_val, msg in warnings_found:
        if w_type not in ON_CHANGE:
            # P&L: insert always
            new_alert = Alert(
                id=uuid.uuid4(),
                user_id=user_id,
                type=w_type,
                trigger_field="",
                trigger_value=trigger_val,
                threshold_value=threshold,
                msg=msg,
                notified_at=now,
                last_triggered=today,
                is_active=True
            )
            db.add(new_alert)
        else:
            # ON_CHANGE: insert only if not already active, else update date
            result = await db.execute(
                select(Alert.id)
                .where(
                    Alert.user_id == user_id,
                    Alert.type == w_type,
                    Alert.msg == msg,
                    Alert.is_active == True
                )
            )
            existing = result.scalar_one_or_none()
            if existing:
                await db.execute(
                    update(Alert)
                    .where(Alert.id == existing)
                    .values(last_triggered=today)
                )
            else:
                new_alert = Alert(
                    id=uuid.uuid4(),
                    user_id=user_id,
                    type=w_type,
                    trigger_field="",
                    trigger_value=trigger_val,
                    threshold_value=threshold,
                    msg=msg,
                    notified_at=now,
                    last_triggered=today,
                    is_active=True
                )
                db.add(new_alert)

    # Deactivate ON_CHANGE alerts that are no longer in warnings_found
    active_msgs = [w[3] for w in warnings_found if w[0] in ON_CHANGE]
    
    if ON_CHANGE:
        await db.execute(
            update(Alert)
            .where(
                Alert.user_id == user_id,
                Alert.type.in_(ON_CHANGE),
                Alert.is_active == True,
                not_(Alert.msg.in_(active_msgs))
            )
            .values(is_active=False)
        )

    await db.commit()