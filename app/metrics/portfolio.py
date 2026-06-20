from decimal import Decimal
from statistics import stdev
from datetime import timedelta


def calculate_portfolio_daily_metrics(snapshots: list[dict]) -> dict:
    if not snapshots:
        return {
            "date": None,
            "pnl": {},
            "max_drawdown": {},
            "volatility": {},
        }
    return {
        "date": snapshots[-1]["date"],
        "pnl": calculate_pnl(snapshots),
        "max_drawdown": calculate_max_drawdown(snapshots),
        "volatility": calculate_volatility(snapshots),
    }

def calculate_portfolio_monthly_metrics(snapshots: list) -> dict:
    if not snapshots:
        return {
            "date": None,
            "twr": {},
            "var": {},
        }
    end_date = snapshots[-1].date
    # Filtrar periodo de tiempo aprovechando timedelta
    start_date = end_date - timedelta(days=30)
    filtered_snapshots = [s for s in snapshots if s.date >= start_date]
    return {
        "date": filtered_snapshots[-1].date if filtered_snapshots else None,
        "twr": calculate_twr(filtered_snapshots),
        "var": calculate_var(filtered_snapshots),
    } 

def calculate_pnl(snapshots: list[dict]) -> dict:
    if len(snapshots) < 2:
        return {}
    today_snapshot = snapshots[-1]
    yesterday_snapshot = snapshots[-2]

    # Extraer los diccionarios, usando dicts vacíos si son None
    today_realized = today_snapshot.get("realized_pnl") or {}
    today_unrealized = today_snapshot.get("unrealized_pnl") or {}
    yesterday_realized = yesterday_snapshot.get("realized_pnl") or {}
    yesterday_unrealized = yesterday_snapshot.get("unrealized_pnl") or {}

    # Consolidar todas las monedas existentes
    all_currencies = set(today_realized.keys()) | set(today_unrealized.keys()) | \
                     set(yesterday_realized.keys()) | set(yesterday_unrealized.keys())
    # Calcular Pnl
    pnl_by_currency = {}
    for curr in all_currencies:
        today_r = Decimal(str(today_realized.get(curr, "0")))
        today_u = Decimal(str(today_unrealized.get(curr, "0")))
        yesterday_r = Decimal(str(yesterday_realized.get(curr, "0")))
        yesterday_u = Decimal(str(yesterday_unrealized.get(curr, "0")))

        today_total = today_r + today_u
        yesterday_total = yesterday_r + yesterday_u
        
        pnl_by_currency[curr] = str(today_total - yesterday_total)
    
    return pnl_by_currency


def calculate_max_drawdown(snapshots: list[dict]) -> dict:
    if not snapshots:
        return {}
    peaks = {}
    max_drawdowns = {}
    # Iteración por todas las snapshots para obtener max_drawdown
    for snapshot in snapshots:
        total_values = snapshot.get("total_value") or {}
        
        for curr, val_str in total_values.items():
            value = Decimal(str(val_str))
            # Inicializar variables para una moneda nueva
            if curr not in peaks:
                peaks[curr] = value
                max_drawdowns[curr] = Decimal("0")
                
            if value > peaks[curr]:
                peaks[curr] = value
                
            if peaks[curr] > Decimal("0"):
                drawdown = (value - peaks[curr]) / peaks[curr]
                if drawdown < max_drawdowns[curr]:
                    max_drawdowns[curr] = drawdown

    # Retornar diccionarios formateados a String para guardarlos en BD
    return {curr: str(md) for curr, md in max_drawdowns.items()}


def calculate_volatility(snapshots: list) -> dict:
    if len(snapshots) < 2:
        return {}
    
    returns_by_currency = {}
    
    for i in range(1, len(snapshots)):
        prev_snapshot = snapshots[i - 1]
        curr_snapshot = snapshots[i]
        
        prev_values = prev_snapshot.get("total_value") or {}
        curr_values = curr_snapshot.get("total_value") or {}
        
        today_realized = curr_snapshot.get("realized_pnl") or {}
        today_unrealized = curr_snapshot.get("unrealized_pnl") or {}
        yesterday_realized = prev_snapshot.get("realized_pnl") or {}
        yesterday_unrealized = prev_snapshot.get("unrealized_pnl") or {}
        
        all_currencies = set(prev_values.keys()) | set(curr_values.keys()) | set(today_realized.keys()) | set(today_unrealized.keys())
        
        for curr in all_currencies:
            prev_val = Decimal(str(prev_values.get(curr, "0")))
            today_val = Decimal(str(curr_values.get(curr, "0")))
            
            # 1. Calcular PnL neto del día (Numerador)
            today_total_pnl = Decimal(str(today_realized.get(curr, "0"))) + Decimal(str(today_unrealized.get(curr, "0")))
            yesterday_total_pnl = Decimal(str(yesterday_realized.get(curr, "0"))) + Decimal(str(yesterday_unrealized.get(curr, "0")))
            
            daily_pnl = today_total_pnl - yesterday_total_pnl
            
            # 2. Calcular la Base de Capital (Denominador Dinámico)
            # Esto resuelve los depósitos iniciales gigantescos y retiros masivos.
            capital_basis = max(prev_val, today_val - daily_pnl)
            
            # 3. Filtro Anti-Polvo sobre la base de capital real
            threshold = Decimal("1") if curr == "USD" else Decimal("1000")
            if capital_basis < threshold:
                continue
            
            # 4. Retorno real de mercado aislado de flujos de caja
            period_return = daily_pnl / capital_basis
            
            if curr not in returns_by_currency:
                returns_by_currency[curr] = []
                
            returns_by_currency[curr].append(float(period_return))

    volatility_by_currency = {}
    for curr, returns in returns_by_currency.items():
        if len(returns) < 2:
            volatility_by_currency[curr] = "0"
        else:
            volatility_by_currency[curr] = str(stdev(returns))
            
    return volatility_by_currency

def calculate_twr(snapshots: list) -> dict:
    if len(snapshots) < 2:
        return {}
    
    multipliers = {}
    
    for i in range(1, len(snapshots)):
        prev_snapshot = snapshots[i - 1]
        curr_snapshot = snapshots[i]
        
        prev_values = prev_snapshot.get("total_value") or {}
        curr_values = curr_snapshot.get("total_value") or {}
        
        today_realized = curr_snapshot.get("realized_pnl") or {}
        today_unrealized = curr_snapshot.get("unrealized_pnl") or {}
        yesterday_realized = prev_snapshot.get("realized_pnl") or {}
        yesterday_unrealized = prev_snapshot.get("unrealized_pnl") or {}
        
        all_currencies = set(prev_values.keys()) | set(curr_values.keys()) | set(today_realized.keys()) | set(today_unrealized.keys())
        
        for curr in all_currencies:
            prev_val = Decimal(str(prev_values.get(curr, "0")))
            today_val = Decimal(str(curr_values.get(curr, "0")))
            
            today_total_pnl = Decimal(str(today_realized.get(curr, "0"))) + Decimal(str(today_unrealized.get(curr, "0")))
            yesterday_total_pnl = Decimal(str(yesterday_realized.get(curr, "0"))) + Decimal(str(yesterday_unrealized.get(curr, "0")))
            
            daily_pnl = today_total_pnl - yesterday_total_pnl
            
            # Aplicamos la misma Base de Capital al Time-Weighted Return
            capital_basis = max(prev_val, today_val - daily_pnl)
            
            threshold = Decimal("1") if curr == "USD" else Decimal("1000")
            if capital_basis < threshold:
                continue
            
            period_return = daily_pnl / capital_basis
            
            if curr not in multipliers:
                multipliers[curr] = Decimal("1")
                
            multipliers[curr] *= (Decimal("1") + period_return)
            
    return {curr: str(mult - Decimal("1")) for curr, mult in multipliers.items()}


def calculate_var(snapshots: list) -> dict:
    if len(snapshots) < 2:
        return {}
    
    returns_by_currency = {}
    
    for i in range(1, len(snapshots)):
        prev_vals = snapshots[i - 1].total_value or {}
        curr_vals = snapshots[i].total_value or {}

        all_currencies = set(prev_vals.keys()) | set(curr_vals.keys())

        for curr in all_currencies:
            prev = Decimal(str(prev_vals.get(curr, "0")))
            curr_val = Decimal(str(curr_vals.get(curr, "0")))

            if prev == Decimal("0"):
                continue

            if curr not in returns_by_currency:
                returns_by_currency[curr] = []

            # Calculamos el retorno del periodo para la moneda
            returns_by_currency[curr].append((curr_val - prev) / prev)

    var_by_currency = {}
    confidence = 0.95

    for curr, returns in returns_by_currency.items():
        if len(returns) < 2:
            var_by_currency[curr] = "0"
            continue

        # Ordenar rendimientos de peor a mejor
        returns.sort()

        # Calcular el índice del percentil
        percentile_index = int((1 - confidence) * len(returns))
        percentile_index = max(0, min(percentile_index, len(returns) - 1))

        # El VaR se suele expresar en valor absoluto y positivo.
        # Lo pasamos a string para la columna JSONB
        var_by_currency[curr] = str(abs(returns[percentile_index]))

    return var_by_currency
