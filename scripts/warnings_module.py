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


async def warnings(db: AsyncSession, user_id: str, send_mail: bool = False):
    # Get accounts
    result = await db.execute(select(Account.id, Account.name).where(Account.user_id == user_id))
    accounts = result.all()

    # Get user preferences
    result = await db.execute(select(UserPreference).where(UserPreference.user_id == user_id))
    preferences_obj = result.scalar_one_or_none()
    
    from sqlalchemy import text
    raw = await db.execute(text("SELECT * FROM user_preferences WHERE user_id = :u"), {"u": user_id})
    print(f"  [DEBUG RAW] {raw.fetchall()}")

    if preferences_obj is None:
        print(f"  [DEBUG] user {user_id}: sin preferencias, se omite")
        return []

    preferences = (
        preferences_obj.pnl_percentage_account_daily,
        preferences_obj.pnl_percentage_asset_daily,
        preferences_obj.max_drawdown_portfolio_daily,
        preferences_obj.max_drawdown_account_daily,
        preferences_obj.asset_weight_weekly,
    )

    # Get last 2 portfolio snapshots
    result = await db.execute(
        select(PortfolioSnapshot.id, PortfolioSnapshot.date, PortfolioSnapshot.total_value, PortfolioSnapshot.breakdown_by_account)
        .where(PortfolioSnapshot.user_id == user_id)
        .order_by(desc(PortfolioSnapshot.date))
        .limit(2)
    )
    snapshots = result.all()
    snapshot_today = snapshots[0] if len(snapshots) >= 1 else None
    snapshot_yesterday = snapshots[1] if len(snapshots) >= 2 else None

    # ─── DEBUG MAIN ──────────────────────────────────────────────────────────
    print(f"\n{'='*60}")
    print(f"DEBUG warnings | user: {user_id}")
    print(f"  accounts ({len(accounts)}): {[(str(aid), aname) for aid, aname in accounts]}")
    print(f"  preferences:")
    print(f"    pnl_account    = {preferences[0]}")
    print(f"    pnl_asset      = {preferences[1]}")
    print(f"    dd_portfolio   = {preferences[2]}")
    print(f"    dd_account     = {preferences[3]}")
    print(f"    asset_weight   = {preferences[4]}")
    if snapshot_today:
        print(f"  snapshot_today:     id={snapshot_today[0]} | date={snapshot_today[1]} | total={snapshot_today[2]}")
    else:
        print(f"  snapshot_today:     None ⚠️  → warnings de peso y dd_portfolio no van a dispararse")
    if snapshot_yesterday:
        print(f"  snapshot_yesterday: id={snapshot_yesterday[0]} | date={snapshot_yesterday[1]} | total={snapshot_yesterday[2]}")
    else:
        print(f"  snapshot_yesterday: None ⚠️  → warnings de pnl_account no van a dispararse")
    print(f"{'='*60}")
    # ─────────────────────────────────────────────────────────────────────────

    warnings_found = []
    for account_id, account_name in accounts:
        aux = await warnings_account(db, account_id, account_name, preferences, snapshot_yesterday)
        warnings_found.extend(aux)

    account_ids = [row[0] for row in accounts]
    account_names = {acc_id: acc_name for acc_id, acc_name in accounts}

    aux = await warnings_portfolio(db, user_id, account_ids, account_names, preferences, snapshot_today)
    warnings_found.extend(aux)

    print(f"\n  [DEBUG] warnings_found ({len(warnings_found)}):")
    for w in warnings_found:
        print(f"    {w}")

    result = await db.execute(select(Profile.email).where(Profile.clerk_id == user_id))
    profile_row = result.scalar_one_or_none()

    if profile_row is not None and warnings_found:
        await warning_db_changes(db, user_id, warnings_found)

    if profile_row is not None and warnings_found and send_mail:
        await send_mails(db, profile_row, user_id)

    return warnings_found


async def warnings_account(db: AsyncSession, account_id: uuid.UUID, account_name: str, preferences: tuple, snapshot_yesterday: tuple):
    warnings_found = []

    # ─── DEBUG ACCOUNT ───────────────────────────────────────────────────────
    print(f"\n  [DEBUG account: '{account_name}' | id={account_id}]")
    # ─────────────────────────────────────────────────────────────────────────

    # P&L ACCOUNT
    preference_pnl_account = preferences[0]
    if preference_pnl_account is not None:
        result = await db.execute(
            select(AccountDailyMetric.pnl, AccountDailyMetric.date)
            .where(AccountDailyMetric.account_id == account_id)
            .order_by(desc(AccountDailyMetric.date))
            .limit(1)
        )
        row = result.first()
        latest_pnl = row[0] if row else None
        latest_pnl_date = row[1] if row else None

        # ─── DEBUG ───────────────────────────────────────────────────────────
        print(f"    pnl_account | AccountDailyMetric más reciente: pnl={latest_pnl}, date={latest_pnl_date}")
        # ─────────────────────────────────────────────────────────────────────

        if latest_pnl is not None:
            if snapshot_yesterday is not None:
                snapshot_id, snapshot_date, total_value, breakdown_by_account = snapshot_yesterday
                account_value_yesterday = breakdown_by_account.get(str(account_id)) if breakdown_by_account else None

                # ─── DEBUG ───────────────────────────────────────────────────
                print(f"    pnl_account | snapshot_yesterday date={snapshot_date}, account_value_yesterday={account_value_yesterday}")
                # ─────────────────────────────────────────────────────────────

                if account_value_yesterday:
                    pnl_pct = round(float(latest_pnl) / float(account_value_yesterday), 4)
                    supera = abs(pnl_pct) > float(preference_pnl_account)
                    print(f"    pnl_account | pnl_pct={pnl_pct:.4f}, threshold={preference_pnl_account}, supera={supera}")
                    if supera:
                        direction = "ganó" if pnl_pct > 0 else "perdió"
                        msg = f"La cuenta '{account_name}' {direction} {abs(pnl_pct):.1%} "
                        warnings_found.append(["P&L account", preference_pnl_account, pnl_pct, msg])
                else:
                    print(f"    pnl_account | ⚠️  account_value_yesterday es None o vacío, no se calcula pnl_pct")
            else:
                print(f"    pnl_account | ⚠️  snapshot_yesterday es None, no se calcula pnl_pct")
        else:
            print(f"    pnl_account | ⚠️  sin registros en AccountDailyMetric para esta cuenta")
    else:
        print(f"    pnl_account | preferencia no configurada, se omite")

    # MAX DRAWDOWN ACCOUNT
    preference_max_drawdown_account = preferences[3]
    if preference_max_drawdown_account is not None:
        result = await db.execute(
            select(AccountDailyMetric.max_drawdown, AccountDailyMetric.date)
            .where(AccountDailyMetric.account_id == account_id)
            .order_by(desc(AccountDailyMetric.date))
            .limit(1)
        )
        row = result.first()
        max_drawdown = row[0] if row else None
        max_drawdown_date = row[1] if row else None
        supera = max_drawdown is not None and abs(float(max_drawdown)) > float(preference_max_drawdown_account)

        # ─── DEBUG ───────────────────────────────────────────────────────────
        print(f"    dd_account  | AccountDailyMetric más reciente: max_drawdown={max_drawdown}, date={max_drawdown_date}, threshold={preference_max_drawdown_account}, supera={supera}")
        # ─────────────────────────────────────────────────────────────────────

        if supera:
            msg = f"La cuenta '{account_name}' tiene un drawdown de {abs(float(max_drawdown)):.1%} respecto a su máximo histórico"
            warnings_found.append(["max_drawdown", preference_max_drawdown_account, max_drawdown, msg])
    else:
        print(f"    dd_account  | preferencia no configurada, se omite")

    return warnings_found


async def warnings_portfolio(db: AsyncSession, user_id: str, account_ids: list, account_names: dict, preferences: tuple, snapshot_today: tuple):
    warnings_found = []

    print(f"\n  [DEBUG portfolio]")

    portfolio_id = None
    total_value = None
    if snapshot_today is not None:
        portfolio_id, _, total_value, _ = snapshot_today

        # MAX DRAWDOWN PORTFOLIO
        preference_max_drawdown_portfolio = preferences[2]
        if preference_max_drawdown_portfolio is not None and portfolio_id:
            result = await db.execute(
                select(PortfolioDailyMetric.max_drawdown, PortfolioDailyMetric.date)
                .where(PortfolioDailyMetric.user_id == user_id)
                .order_by(desc(PortfolioDailyMetric.date))
                .limit(1)
            )
            row = result.first()
            max_drawdown = row[0] if row else None
            max_drawdown_date = row[1] if row else None
            supera = max_drawdown is not None and abs(float(max_drawdown)) > float(preference_max_drawdown_portfolio)

            # ─── DEBUG ───────────────────────────────────────────────────────
            print(f"    dd_portfolio | PortfolioDailyMetric más reciente: max_drawdown={max_drawdown}, date={max_drawdown_date}, threshold={preference_max_drawdown_portfolio}, supera={supera}")
            # ─────────────────────────────────────────────────────────────────

            if supera:
                msg = f"Tu portafolio tiene un max drawdown de {abs(float(max_drawdown)):.1%} respecto a su máximo histórico"
                warnings_found.append(["max_drawdown", preference_max_drawdown_portfolio, max_drawdown, msg])
        else:
            print(f"    dd_portfolio | preferencia no configurada o sin portfolio_id, se omite")
    else:
        print(f"    dd_portfolio | ⚠️  snapshot_today es None, se omite dd_portfolio y asset_weight")

    if account_ids:
        result = await db.execute(
            select(Position.id, Position.quantity, Position.asset_id, Position.account_id,
                   Asset.symbol, Asset.name)
            .join(Asset, Position.asset_id == Asset.id)
            .where(Position.account_id.in_(account_ids))
        )
        positions_rows = result.all()
    else:
        positions_rows = []

    print(f"    posiciones encontradas: {len(positions_rows)}")

    if positions_rows:
        position_ids = [row[0] for row in positions_rows]
        position_info = {
            row[0]: {"asset_id": row[2], "account_id": row[3], "symbol": row[4], "name": row[5], "quantity": row[1]}
            for row in positions_rows
        }

        asset_ids = list({row[2] for row in positions_rows})
        asset_closes = {}
        for asset_id in asset_ids:
            result = await db.execute(
                select(AssetPrice.close, AssetPrice.date)
                .where(AssetPrice.asset_id == asset_id)
                .order_by(desc(AssetPrice.date))
                .limit(2)
            )
            rows = result.all()
            asset_closes[asset_id] = [r[0] for r in rows]
            closes_dates = [r[1] for r in rows]
            print(f"    asset_id={asset_id} | closes={asset_closes[asset_id]} | dates={closes_dates}")

        position_data = {
            row[0]: {"asset_id": row[2], "quantity": row[1], "closes": asset_closes.get(row[2], [])}
            for row in positions_rows
        }

        # P&L ASSET
        preference_pnl_position = preferences[1]
        if preference_pnl_position is not None:
            today = date.today()
            result = await db.execute(
                select(PositionDailyMetric.position_id, PositionDailyMetric.total_pnl)
                .where(
                    PositionDailyMetric.position_id.in_(position_ids),
                    PositionDailyMetric.date == today
                )
            )
            pnl_by_position = {row[0]: row[1] for row in result.all()}
            print(f"    pnl_asset | PositionDailyMetric de hoy ({today}): {len(pnl_by_position)} registros encontrados de {len(position_ids)} posiciones")
            if len(pnl_by_position) < len(position_ids):
                missing = [str(pid) for pid in position_ids if pid not in pnl_by_position]
                print(f"    pnl_asset | ⚠️  posiciones SIN métrica hoy: {missing}")

            for position_id, data in position_data.items():
                closes = data["closes"]
                pnl_dollars = pnl_by_position.get(position_id)
                info = position_info.get(position_id, {})
                symbol = info.get("symbol", str(position_id))

                if pnl_dollars is None:
                    print(f"    pnl_asset | {symbol}: sin pnl hoy, se omite")
                    continue
                if len(closes) < 2:
                    print(f"    pnl_asset | {symbol}: solo {len(closes)} precio(s), se necesitan 2, se omite")
                    continue

                close_ayer = closes[1]
                quantity = data["quantity"]
                valor_posicion_ayer = float(quantity) * float(close_ayer)
                if not valor_posicion_ayer:
                    print(f"    pnl_asset | {symbol}: valor_posicion_ayer=0, se omite")
                    continue

                pnl_pct = round(float(pnl_dollars) / valor_posicion_ayer, 4)
                supera = abs(pnl_pct) > float(preference_pnl_position)
                print(f"    pnl_asset | {symbol}: pnl_dollars={pnl_dollars}, close_ayer={close_ayer}, qty={quantity}, valor_ayer={valor_posicion_ayer:.2f}, pnl_pct={pnl_pct:.4f}, threshold={preference_pnl_position}, supera={supera}")

                if supera:
                    acc_name = account_names.get(info.get("account_id"), "")
                    asset_label = f"{info.get('name', 'Activo')} ({symbol})"
                    direction = "ganó" if pnl_pct > 0 else "perdió"
                    msg = f"{asset_label} {direction} {abs(pnl_pct):.1%} hoy en tu cuenta '{acc_name}'"
                    warnings_found.append(["P&L asset", preference_pnl_position, pnl_pct, msg])
        else:
            print(f"    pnl_asset | preferencia no configurada, se omite")

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
                        asset_totals[symbol] = {"total_value": 0, "name": info.get("name", "Activo"), "symbol": symbol}
                    asset_totals[symbol]["total_value"] += position_value
                else:
                    print(f"    asset_weight | {symbol}: sin close_hoy o quantity, se omite")

            for symbol, asset_data in asset_totals.items():
                weight = round(asset_data["total_value"] / float(total_value), 4)
                supera = abs(weight) > float(preference_max_weight)
                print(f"    asset_weight | {symbol}: value={asset_data['total_value']:.2f}, total_portfolio={total_value}, weight={weight:.4f}, threshold={preference_max_weight}, supera={supera}")
                if supera:
                    asset_label = f"{asset_data['name']} ({symbol})"
                    msg = f"{asset_label} representa {weight:.1%} de tu portafolio total"
                    warnings_found.append(["asset_weight", preference_max_weight, weight, msg])
        else:
            print(f"    asset_weight | preferencia no configurada o total_value=None, se omite")

    return warnings_found


async def send_mails(db: AsyncSession, email: str, user_id: str):
    ON_CHANGE = {"max_drawdown", "asset_weight"}
    today = date.today()

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
    today = date.today()
    now = datetime.utcnow()
    ON_CHANGE = {"max_drawdown", "asset_weight"}

    for w_type, threshold, trigger_val, msg in warnings_found:
        if w_type not in ON_CHANGE:
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
                    update(Alert).where(Alert.id == existing).values(last_triggered=today)
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