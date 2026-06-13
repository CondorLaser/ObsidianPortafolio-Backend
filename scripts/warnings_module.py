import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mailer.default_mailer import inmmediate_mail


#DEVOLVER TODAS LAS WARNINGS EN FORMATO [[type, valor_trigger, valor_real, mensaje], [ ], [ ] ]
def warnings(user_id):
    conn, cur = connection_bdd()

    cur.execute("SELECT id, name FROM accounts WHERE user_id = %s", (user_id,))
    accounts = cur.fetchall()  # [(id, name), ...]

    cur.execute("""
        SELECT
            pnl_percentage_account_daily,
            pnl_percentage_asset_daily,
            max_drawdown_portfolio_daily,
            max_drawdown_account_daily,
            asset_weight_weekly
        FROM user_preferences
        WHERE user_id = %s
    """, (user_id,))

    preferences = cur.fetchone()
    if preferences is None:
        close_bdd(conn, cur)
        return []

    # Últimas 2 fechas de portfolio_snapshots: snapshot de hoy para peso max por activo
    # y snapshot de ayer (para P&L por cuenta)
    cur.execute("""
        SELECT id, date, total_value, breakdown_by_account
        FROM portfolio_snapshots
        WHERE user_id = %s
        ORDER BY date DESC
        LIMIT 2
    """, (user_id,))
    snapshots = cur.fetchall()
    snapshot_today = snapshots[0] if len(snapshots) >= 1 else None
    snapshot_yesterday = snapshots[1] if len(snapshots) >= 2 else None

    #ACCOUNT
    warnings_found = []
    for account_id, account_name in accounts:
        aux = warnings_account(account_id, account_name, cur, preferences, snapshot_yesterday)
        warnings_found = warnings_found + aux

    account_ids = [row[0] for row in accounts]
    # Diccionario account_id -> account_name, usado para los mensajes de warnings_portfolio
    account_names = {acc_id: acc_name for acc_id, acc_name in accounts}

    # PORTFOLIO
    aux = warnings_portfolio(user_id, account_ids, account_names, cur, preferences, snapshot_today)
    warnings_found = warnings_found + aux

    # Email del usuario, se obtiene antes de cerrar la conexión
    cur.execute("SELECT email FROM profiles WHERE clerk_id = %s", (user_id,))
    profile_row = cur.fetchone()

    close_bdd(conn, cur)

    if profile_row is not None and warnings_found:
        email = profile_row[0]
        send_mails(email, warnings_found)

    return warnings_found


def warnings_account(account_id, account_name, cur, preferences, snapshot_yesterday):
    warnings_found = []

    #GANANCIA/PERDIDA P&L
    preference_pnl_accout = preferences[0]
    cur.execute("""
        SELECT pnl FROM account_daily_metrics
        WHERE account_id = %s AND date = (SELECT MAX(date) FROM account_daily_metrics WHERE account_id = %s)
    """, (account_id, account_id))
    for (pnl_dollars,) in cur.fetchall():
        if snapshot_yesterday is not None:
            _, _, _, breakdown_by_account_yesterday = snapshot_yesterday
            account_value_yesterday = breakdown_by_account_yesterday.get(str(account_id)) if breakdown_by_account_yesterday else None
            if account_value_yesterday:
                pnl_pct = round(pnl_dollars / account_value_yesterday, 4) #para convertirlo en %
                if abs(pnl_pct) > preference_pnl_accout:
                    direction = "ganó" if pnl_pct > 0 else "perdió"
                    msg = f"La cuenta '{account_name}' {direction} {abs(pnl_pct):.1%} "
                    warnings_found.append(["P&L account", preference_pnl_accout, pnl_pct, msg])

    # MAX DRAWDOWN
    preference_max_drawdown_accout = preferences[3]
    cur.execute("""
        SELECT max_drawdown FROM account_daily_metrics
        WHERE account_id = %s AND date = (SELECT MAX(date) FROM account_daily_metrics WHERE account_id = %s)
    """, (account_id, account_id))
    for (max_drawdown,) in cur.fetchall():
        if abs(max_drawdown) > preference_max_drawdown_accout:
            msg = f"La cuenta '{account_name}' tiene un drawdown de {abs(max_drawdown):.1%} respecto a su máximo histórico"
            warnings_found.append(["max_drawdown", preference_max_drawdown_accout, max_drawdown, msg])

    return warnings_found


def warnings_portfolio(user_id, account_ids, account_names, cur, preferences, snapshot_today):
    warnings_found = []

    portfolio_id = None
    total_value = None
    if snapshot_today is not None:
        portfolio_id, _, total_value, _ = snapshot_today

        # MAX DRAWDOWN (portfolio_daily_metrics.portfolio_id -> portfolio_snapshots.id)
        preference_max_drawdown_portfolio = preferences[2]
        cur.execute("""
            SELECT max_drawdown FROM portfolio_daily_metrics
            WHERE portfolio_id = %s
        """, (portfolio_id,))
        for (max_drawdown,) in cur.fetchall():
            if abs(max_drawdown) > preference_max_drawdown_portfolio:
                msg = f"Tu portafolio tiene un max drawdown de {abs(max_drawdown):.1%} respecto a su máximo histórico"
                warnings_found.append(["max_drawdown", preference_max_drawdown_portfolio, max_drawdown, msg])

    if account_ids:
        # JOIN con assets para obtener symbol, name y account_id 
        cur.execute("""
            SELECT p.id, p.quantity, p.asset_id, p.account_id, a.symbol, a.name
            FROM positions p
            JOIN assets a ON a.id = p.asset_id
            WHERE p.account_id = ANY(%s)
        """, (account_ids,))
        positions_rows = cur.fetchall()
    else:
        positions_rows = []

    if positions_rows:
        position_ids = [row[0] for row in positions_rows]
        # para cpmstruir el mensaje
        position_info = {row[0]: {"asset_id": row[2], "account_id": row[3], "symbol": row[4], "name": row[5]} for row in positions_rows}

        cur.execute("""
            SELECT p.id, p.quantity, ap.date, ap.close
            FROM positions p
            JOIN asset_prices ap ON ap.asset_id = p.asset_id
            WHERE p.id = ANY(%s)
              AND ap.date IN (
                  SELECT date FROM asset_prices
                  WHERE asset_id = p.asset_id
                  ORDER BY date DESC
                  LIMIT 2
              )
            ORDER BY p.id, ap.date DESC
        """, (position_ids,))
        rows = cur.fetchall()

        position_data = {}
        for position_id, quantity, date, close in rows:
            position_data.setdefault(position_id, {"quantity": quantity, "closes": []})
            position_data[position_id]["closes"].append(close)

        # P&L ACTIVO: pnl ($, de position_daily_metrics) / valor de la posición ayer (quantity * close_ayer)
        # Se trae en batch el pnl más reciente de todas las posiciones.
        cur.execute("""
            SELECT pdm.position_id, pdm.pnl
            FROM position_daily_metrics pdm
            WHERE pdm.position_id = ANY(%s)
              AND pdm.date = (
                  SELECT MAX(date) FROM position_daily_metrics
                  WHERE position_id = pdm.position_id
              )
        """, (position_ids,))
        pnl_by_position = {position_id: pnl for position_id, pnl in cur.fetchall()}

        preference_pnl_position = preferences[1]
        for position_id, data in position_data.items():
            closes = data["closes"]
            pnl_dollars = pnl_by_position.get(position_id)
            if pnl_dollars is None or len(closes) < 2:
                continue

            close_ayer = closes[1]
            quantity = data["quantity"]
            if not close_ayer or not quantity:
                continue

            valor_posicion_ayer = quantity * close_ayer
            if not valor_posicion_ayer:
                continue

            pnl_pct = round(pnl_dollars / valor_posicion_ayer, 4) # para convertirlo en porcentaje
            if abs(pnl_pct) > preference_pnl_position:
                info = position_info.get(position_id, {})
                asset_label = f"{info.get('name', 'Activo')} ({info.get('symbol', '')})"
                acc_name = account_names.get(info.get("account_id"), "")
                direction = "ganó" if pnl_pct > 0 else "perdió"
                msg = f"{asset_label} {direction} {abs(pnl_pct):.1%} hoy en tu cuenta '{acc_name}'"
                warnings_found.append(["P&L asset", preference_pnl_position, pnl_pct, msg])

        # PESO MAX
        preference_max_weight = preferences[4]
        if total_value:
            # Agrupar por asset (symbol) sumando valores de todas las cuentas
            asset_totals = {}  # symbol -> {total_value, name, symbol}
            for position_id, data in position_data.items():
                info = position_info.get(position_id, {})
                symbol = info.get("symbol", position_id)  # fallback al id si no hay symbol
                
                close_hoy = data["closes"][0]
                quantity = data["quantity"]
                position_value = quantity * close_hoy
                
                if symbol not in asset_totals:
                    asset_totals[symbol] = {
                        "total_value": 0,
                        "name": info.get("name", "Activo"),
                        "symbol": symbol,
                    }
                asset_totals[symbol]["total_value"] += position_value

            # Evaluar peso por asset consolidado
            for symbol, asset_data in asset_totals.items():
                weight = round(asset_data["total_value"] / total_value, 4) #convertir a %
                if abs(weight) > preference_max_weight:
                    asset_label = f"{asset_data['name']} ({symbol})"
                    msg = f"{asset_label} representa {weight:.1%} de tu portafolio total"
                    warnings_found.append(["asset_weight", preference_max_weight, weight, msg])

    return warnings_found


def send_mails(email, warnings_found):
    alerts_for_mail = [[w[0], w[2], w[1], w[3]] for w in warnings_found]
    return inmmediate_mail(email, alerts_for_mail)