# API Contract — Orion Portafolio Backend

> ⚙️ Generado automáticamente desde `/openapi.json`. **NO editar a mano** — re-correr `scripts/generate_api_contract.py`.

**Total endpoints**: 46  
**Base URL local**: `http://localhost:8000` (sin `/api/v1`)  
**Auth**: Bearer JWT Clerk en header `Authorization` (excepto rutas públicas)

## Resumen

| Tag | Endpoints |
|---|---|
| **accounts** | 8 (`/accounts`, `/accounts/dividends/{account_id}`, `/accounts/metrics/{account_id}`, `/accounts/positions/{account_id}`, `/accounts/transactions/{account_id}`, `/accounts/with-counters`, `/accounts/{account_id}`) |
| **assets** | 5 (`/assets`, `/assets/metrics/daily/{asset_id}`, `/assets/metrics/monthly/{asset_id}`, `/assets/{asset_id}`) |
| **dividends** | 1 (`/dividends`) |
| **health** | 1 (`/health`) |
| **misc** | 2 (`/`, `/protected`) |
| **onboarding** | 1 (`/risk_profile`) |
| **pdf** | 3 (`/pdf/extract_mutual_funds`, `/pdf/extract_stocks_etf_1`, `/pdf/extract_stocks_etf_2`) |
| **portfolio** | 10 (`/portfolio/dashboard`, `/portfolio/metrics/daily`, `/portfolio/metrics/daily/all`, `/portfolio/metrics/monthly`, `/portfolio/metrics/monthly/all`, `/portfolio/rebuild`, `/portfolio/summary`, `/portfolio/trend`) |
| **positions** | 6 (`/positions`, `/positions/asset/{asset_id}`, `/positions/metrics/daily/{position_id}`, `/positions/metrics/daily/{position_id}/all`, `/positions/portfolio`) |
| **preferences** | 2 (`/preferences`) |
| **prices** | 2 (`/assets/{asset_id}/prices`) |
| **profile** | 2 (`/profile`) |
| **transactions** | 2 (`/transactions`) |
| **warnings** | 2 (`/warnings`, `/warnings/{alert_id}`) |
| **webhooks** | 1 (`/webhooks/clerk`) |


## accounts

### `GET` `/accounts`

List Accounts

**Query params**:

- `skip` (integer, optional) — Registros a saltar
- `limit` (integer, optional) — Máx. registros retornar

**Response 200** — Successful Response:

```
array of AccountRead:
{
    id: string (uuid)
    name: string
    broker?: string | null
    currency?: string
    created_at: string (date-time)
    user_id: string
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `POST` `/accounts`

Create Account

**Request body** (application/json):

```
AccountCreate: {
    name: string
    broker?: string | null
    currency?: string
  }
```

**Response 201** — Successful Response:

```
AccountRead: {
    id: string (uuid)
    name: string
    broker?: string | null
    currency?: string
    created_at: string (date-time)
    user_id: string
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `GET` `/accounts/dividends/{account_id}`

Get Account Dividends

**Path params**:

- `account_id`: string (uuid)

**Query params**:

- `skip` (integer, optional) — Registros a saltar
- `limit` (integer, optional) — Máx. registros retornar

**Response 200** — Successful Response:

```
array of DividendRead:
{
    id: string (uuid)
    account_id: string (uuid)
    asset_id: string (uuid)
    date: string (date)
    gross_amount: string | null
    tax_amount: string | null
    net_amount: string | null
    asset: `AssetRead`
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `GET` `/accounts/metrics/{account_id}`

Get Account Metrics

**Path params**:

- `account_id`: string (uuid)

**Response 200** — Successful Response:

```
AccountMetricsRead: {
    daily?: `AccountDailyMetricRead` | null
    monthly?: `AccountMonthlyMetricRead` | null
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `GET` `/accounts/positions/{account_id}`

Get Account Positions

**Path params**:

- `account_id`: string (uuid)

**Query params**:

- `skip` (integer, optional) — Registros a saltar
- `limit` (integer, optional) — Máx. registros retornar

**Response 200** — Successful Response:

```
array of PositionRead:
{
    id: string (uuid)
    account_id: string (uuid)
    asset_id: string (uuid)
    quantity: string | null
    avg_cost: string | null
    realized_pnl: string | null
    total_dividends: string | null
    total_fees: string | null
    last_transaction_at: string (date-time) | null
    updated_at: string (date-time) | null
    asset: `AssetRead`
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `GET` `/accounts/transactions/{account_id}`

Get Account Transactions

**Path params**:

- `account_id`: string (uuid)

**Query params**:

- `skip` (integer, optional) — Registros a saltar
- `limit` (integer, optional) — Máx. registros retornar

**Response 200** — Successful Response:

```
array of TransactionRead:
{
    account_id: string (uuid)
    asset_id: string (uuid)
    kind: `TransactionKind`
    quantity: string
    price?: string | null
    fee?: string
    executed_at: string (date-time)
    id: string (uuid)
    created_at: string (date-time)
    asset: `AssetRead`
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `GET` `/accounts/with-counters`

List Accounts

**Query params**:

- `skip` (integer, optional) — Registros a saltar
- `limit` (integer, optional) — Máx. registros retornar

**Response 200** — Successful Response:

```
array of AccountWithCountersRead:
{
    account: `AccountRead`
    stock_positions?: integer
    fund_positions?: integer
    etf_positions?: integer
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `GET` `/accounts/{account_id}`

Get Account

**Path params**:

- `account_id`: string (uuid)

**Response 200** — Successful Response:

```
AccountRead: {
    id: string (uuid)
    name: string
    broker?: string | null
    currency?: string
    created_at: string (date-time)
    user_id: string
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---


## assets

### `GET` `/assets`

List Assets

**Query params**:

- `symbol` (string | null, optional) — exact match
- `kind` (`AssetKind` | null, optional)
- `currency` (string | null, optional)
- `search` (string | null, optional) — ilike sobre symbol o name
- `limit` (integer, optional)
- `skip` (integer, optional)

**Response 200** — Successful Response:

```
array of AssetRead:
{
    id: string (uuid)
    symbol: string
    name: string
    kind: `AssetKind`
    currency?: string | null
    created_at: string (date-time)
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `POST` `/assets`

Create Asset

**Request body** (application/json):

```
AssetCreate: {
    symbol: string
    name: string
    kind: `AssetKind`
    currency?: string
  }
```

**Response 201** — Successful Response:

```
AssetRead: {
    id: string (uuid)
    symbol: string
    name: string
    kind: `AssetKind`
    currency?: string | null
    created_at: string (date-time)
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `GET` `/assets/metrics/daily/{asset_id}`

Get Asset Daily Metrics

**Path params**:

- `asset_id`: string (uuid)

**Response 200** — Successful Response:

```
AssetDailyMetricRead: {
    id: string (uuid)
    asset_id: string (uuid)
    date: string (date) | null
    absolute_return: string | null
    volatility: string | null
    max_drawdown: string | null
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `GET` `/assets/metrics/monthly/{asset_id}`

Get Asset Monthly Metrics

**Path params**:

- `asset_id`: string (uuid)

**Response 200** — Successful Response:

```
AssetMonthlyMetricRead: {
    id: string (uuid)
    asset_id: string (uuid)
    date: string (date) | null
    beta: string | null
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `GET` `/assets/{asset_id}`

Get Asset

**Path params**:

- `asset_id`: string (uuid)

**Response 200** — Successful Response:

```
AssetDetailRead: {
    id: string (uuid)
    symbol: string
    name: string
    kind: `AssetKind`
    currency?: string | null
    created_at: string (date-time)
    prices?: array of `AssetPriceRead`
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---


## dividends

### `GET` `/dividends`

List Dividends

**Query params**:

- `skip` (integer, optional) — Registros a saltar
- `limit` (integer, optional) — Máx. registros retornar

**Response 200** — Successful Response:

```
array of DividendRead:
{
    id: string (uuid)
    account_id: string (uuid)
    asset_id: string (uuid)
    date: string (date)
    gross_amount: string | null
    tax_amount: string | null
    net_amount: string | null
    asset: `AssetRead`
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---


## health

### `GET` `/health`

Health

---


## misc

### `GET` `/`

Read Root

---

### `GET` `/protected`

Protected

---


## onboarding

### `POST` `/risk_profile`

Post Risk Profile

**Request body** (application/json):

```
RiskProfileUpdate: {
    risk_profile: `RiskProfile`
  }
```

**Response 200** — Successful Response:

```
{
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---


## pdf

### `POST` `/pdf/extract_mutual_funds`

Upload Pdf Mutual Funds

**Request body** (multipart/form-data):

```
`Body_upload_pdf_mutual_funds_pdf_extract_mutual_funds_post` {
    file: string
    account_id: string (uuid)
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `POST` `/pdf/extract_stocks_etf_1`

Upload Pdf Stocks Etf 1

**Request body** (multipart/form-data):

```
`Body_upload_pdf_stocks_etf_1_pdf_extract_stocks_etf_1_post` {
    file: string
    account_id: string (uuid)
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `POST` `/pdf/extract_stocks_etf_2`

Upload Pdf Stocks Etf 2

**Request body** (multipart/form-data):

```
`Body_upload_pdf_stocks_etf_2_pdf_extract_stocks_etf_2_post` {
    file: string
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---


## portfolio

### `GET` `/portfolio/dashboard`

Get Dashboard

**Query params**:

- `trend_from` (string (date) | null, optional) — Filtra el trend desde esta fecha inclusive (YYYY-MM-DD).
- `trend_to` (string (date) | null, optional) — Filtra el trend hasta esta fecha inclusive (YYYY-MM-DD).

**Response 200** — Successful Response:

```
PortfolioDashboard: {
    summary: `PortfolioSummary`
    trend: array of `TrendPoint`
    account_distribution: array of `AccountDistributionItem`
    positions: array of `PositionDerived`
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `GET` `/portfolio/metrics/daily`

Get Latest Daily Metric

**Response 200** — Successful Response:

```
PortfolioDailyMetricRead: {
    id: string (uuid)
    portfolio_id: string (uuid)
    date: string (date) | null
    pnl: string | null
    max_drawdown: string | null
    volatility: string | null
    fx_decomposition?: object | null
  }
```

---

### `POST` `/portfolio/metrics/daily`

Post Daily Metrics

---

### `GET` `/portfolio/metrics/daily/all`

Get Daily Metrics

**Query params**:

- `trend_from` (string (date) | null, optional)
- `trend_to` (string (date) | null, optional)

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `GET` `/portfolio/metrics/monthly`

Get Latest Monthly Metric

**Response 200** — Successful Response:

```
PortfolioMonthlyMetricRead: {
    id: string (uuid)
    portfolio_id: string (uuid)
    date: string (date) | null
    twr: string | null
    dietz: string | null
    var: string | null
    accounts_correlation?: string | null
  }
```

---

### `POST` `/portfolio/metrics/monthly`

Post Monthly Metrics

---

### `GET` `/portfolio/metrics/monthly/all`

Get Monthly Metrics

**Query params**:

- `trend_from` (string (date) | null, optional)
- `trend_to` (string (date) | null, optional)

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `POST` `/portfolio/rebuild`

Rebuild Portfolio

**Response 200** — Successful Response:

```
RebuildResult: {
    snapshots_persisted: integer
    positions_persisted: integer
  }
```

---

### `GET` `/portfolio/summary`

Get Portfolio Summary

**Response 200** — Successful Response:

```
PortfolioSummaryResponse: {
    summary: `PortfolioSummary`
    account_distribution: array of `AccountDistributionItem`
  }
```

---

### `GET` `/portfolio/trend`

Get Portfolio Trend

**Query params**:

- `trend_from` (string (date) | null, optional) — Filtra desde esta fecha inclusive (YYYY-MM-DD).
- `trend_to` (string (date) | null, optional) — Filtra hasta esta fecha inclusive (YYYY-MM-DD).

**Response 200** — Successful Response:

```
array of TrendPoint:
{
    date: string (date)
    value: string
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---


## positions

### `GET` `/positions`

List Positions

**Query params**:

- `skip` (integer, optional) — Registros a saltar
- `limit` (integer, optional) — Máx. registros retornar

**Response 200** — Successful Response:

```
array of PositionRead:
{
    id: string (uuid)
    account_id: string (uuid)
    asset_id: string (uuid)
    quantity: string | null
    avg_cost: string | null
    realized_pnl: string | null
    total_dividends: string | null
    total_fees: string | null
    last_transaction_at: string (date-time) | null
    updated_at: string (date-time) | null
    asset: `AssetRead`
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `GET` `/positions/asset/{asset_id}`

Get Position By Asset
Get Position By Asset

**Path params**:

- `asset_id`: string (uuid)

**Response 200** — Successful Response:

```
`PositionRead` | null
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `GET` `/positions/metrics/daily/{position_id}`

Get Latest Daily Positions Metrics

**Path params**:

- `position_id`: string (uuid)

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `POST` `/positions/metrics/daily/{position_id}`

Post Daily Positions Metrics

**Path params**:

- `position_id`: string (uuid)

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `GET` `/positions/metrics/daily/{position_id}/all`

Get Daily Positions Metrics

**Path params**:

- `position_id`: string (uuid)

**Query params**:

- `trend_from` (string (date) | null, optional)
- `trend_to` (string (date) | null, optional)

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `GET` `/positions/portfolio`

List Positions Portfolio
List Positions Portfolio

**Query params**:

- `skip` (integer, optional) — Registros a saltar
- `limit` (integer, optional) — Máx. registros retornar

**Response 200** — Successful Response:

```
array of PositionDerived:
{
    account_id: string (uuid)
    asset_id: string (uuid)
    symbol: string
    name: string
    quantity: string
    avg_cost: string | null
    last_price: string | null
    market_value: string | null
    unrealized_pnl: string | null
    asset: `AssetRead`
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---


## preferences

### `GET` `/preferences`

Get Preferences

**Response 200** — Successful Response:

```
UserPreferenceRead: {
    pnl_percentage_account_daily?: string | null
    pnl_percentage_asset_daily?: string | null
    max_drawdown_portfolio_daily?: string | null
    max_drawdown_account_daily?: string | null
    asset_weight_weekly?: string | null
    currency_exposure_weekly?: string | null
    id: string (uuid)
    user_id: string
  }
```

---

### `PUT` `/preferences`

Upsert Preferences

**Request body** (application/json):

```
UserPreferenceUpdate: {
    pnl_percentage_account_daily?: number | string | null
    pnl_percentage_asset_daily?: number | string | null
    max_drawdown_portfolio_daily?: number | string | null
    max_drawdown_account_daily?: number | string | null
    asset_weight_weekly?: number | string | null
    currency_exposure_weekly?: number | string | null
  }
```

**Response 200** — Successful Response:

```
UserPreferenceRead: {
    pnl_percentage_account_daily?: string | null
    pnl_percentage_asset_daily?: string | null
    max_drawdown_portfolio_daily?: string | null
    max_drawdown_account_daily?: string | null
    asset_weight_weekly?: string | null
    currency_exposure_weekly?: string | null
    id: string (uuid)
    user_id: string
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---


## prices

### `GET` `/assets/{asset_id}/prices`

List Prices

**Path params**:

- `asset_id`: string (uuid)

**Query params**:

- `from` (string (date) | null, optional)
- `to` (string (date) | null, optional)

**Response 200** — Successful Response:

```
array of AssetPriceRead:
{
    date: string (date)
    close: string
    currency: string
    source?: string | null
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `POST` `/assets/{asset_id}/prices`

Upsert Price

**Path params**:

- `asset_id`: string (uuid)

**Request body** (application/json):

```
AssetPriceCreate: {
    date: string (date)
    close: number | string
    currency: string
    source?: string | null
  }
```

**Response 201** — Successful Response:

```
AssetPriceRead: {
    date: string (date)
    close: string
    currency: string
    source?: string | null
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---


## profile

### `GET` `/profile`

Get Profile

**Response 200** — Successful Response:

```
UserRead: {
    clerk_id: string
    email: string | null
    created_at: string (date-time)
    risk_profile: `RiskProfile` | null
  }
```

---

### `PUT` `/profile`

Update Profile

**Request body** (application/json):

```
RiskProfileUpdate: {
    risk_profile: `RiskProfile`
  }
```

**Response 200** — Successful Response:

```
UserRead: {
    clerk_id: string
    email: string | null
    created_at: string (date-time)
    risk_profile: `RiskProfile` | null
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---


## transactions

### `GET` `/transactions`

List Transactions

**Query params**:

- `skip` (integer, optional) — Registros a saltar
- `limit` (integer, optional) — Máx. registros retornar

**Response 200** — Successful Response:

```
array of TransactionRead:
{
    account_id: string (uuid)
    asset_id: string (uuid)
    kind: `TransactionKind`
    quantity: string
    price?: string | null
    fee?: string
    executed_at: string (date-time)
    id: string (uuid)
    created_at: string (date-time)
    asset: `AssetRead`
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `POST` `/transactions`

Create Transaction

**Request body** (application/json):

```
TransactionCreate: {
    account_id: string (uuid)
    asset_id: string (uuid)
    kind: `TransactionKind`
    quantity: number | string
    price?: number | string | null
    fee?: number | string
    executed_at: string (date-time)
  }
```

**Response 201** — Successful Response:

```
TransactionRead: {
    account_id: string (uuid)
    asset_id: string (uuid)
    kind: `TransactionKind`
    quantity: string
    price?: string | null
    fee?: string
    executed_at: string (date-time)
    id: string (uuid)
    created_at: string (date-time)
    asset: `AssetRead`
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---


## warnings

### `GET` `/warnings`

List Warnings

**Query params**:

- `is_read` (boolean | null, optional) — Filtrar por avisos leídos
- `is_active` (boolean | null, optional) — Filtrar por avisos activos

**Response 200** — Successful Response:

```
array of AlertRead:
{
    id: string (uuid)
    user_id: string
    type: string
    trigger_field: string
    trigger_value: string
    threshold_value: string
    msg: string
    is_read: boolean
    created_at: string (date-time)
    notified_at: string (date-time) | null
    last_triggered: string (date) | null
    is_active: boolean
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---

### `PATCH` `/warnings/{alert_id}`

Update Warning

**Path params**:

- `alert_id`: string (uuid)

**Request body** (application/json):

```
AlertUpdate: {
    is_read?: boolean | null
    is_active?: boolean | null
  }
```

**Response 200** — Successful Response:

```
AlertRead: {
    id: string (uuid)
    user_id: string
    type: string
    trigger_field: string
    trigger_value: string
    threshold_value: string
    msg: string
    is_read: boolean
    created_at: string (date-time)
    notified_at: string (date-time) | null
    last_triggered: string (date) | null
    is_active: boolean
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

---


## webhooks

### `POST` `/webhooks/clerk`

Clerk Webhook

---
