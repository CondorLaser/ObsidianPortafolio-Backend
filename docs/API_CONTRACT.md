# API Contract — Orion Portafolio Backend

> ⚙️ Generado automáticamente desde `/openapi.json`. **NO editar a mano** — re-correr `scripts/generate_api_contract.py`.

**Total endpoints**: 30  
**Base URL local**: `http://localhost:8001` (sin `/api/v1`)  
**Auth**: Bearer JWT Clerk en header `Authorization` (excepto rutas públicas)

## Resumen

| Tag | Endpoints |
|---|---|
| **accounts** | 7 (`/accounts`, `/accounts/dividends/{account_id}`, `/accounts/metrics/{account_id}`, `/accounts/positions/{account_id}`, `/accounts/transactions/{account_id}`, `/accounts/{account_id}`) |
| **assets** | 3 (`/assets`, `/assets/{asset_id}`) |
| **dividends** | 1 (`/dividends`) |
| **health** | 1 (`/health`) |
| **misc** | 2 (`/`, `/protected`) |
| **onboarding** | 1 (`/risk_profile`) |
| **pdf** | 3 (`/pdf/extract_mutual_funds`, `/pdf/extract_stocks_etf_1`, `/pdf/extract_stocks_etf_2`) |
| **portfolio** | 2 (`/portfolio/dashboard`, `/portfolio/rebuild`) |
| **positions** | 1 (`/positions`) |
| **preferences** | 2 (`/preferences`) |
| **prices** | 2 (`/assets/{asset_id}/prices`) |
| **profile** | 2 (`/profile`) |
| **transactions** | 2 (`/transactions`) |
| **webhooks** | 1 (`/webhooks/clerk`) |
| **metrics** | (`/assets/{asset_id}/metrics`, `/accounts/{account_id}/metrics`, `/portfolio/{portfolio_id}/metrics`, `/position/{position_id}/metrics`) |


## accounts

### `GET` `/accounts`

List Accounts

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
    daily?: array of `AccountDailyMetricRead`
    monthly?: array of `AccountMonthlyMetricRead`
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
AccountDetailRead: {
    id: string (uuid)
    name: string
    broker?: string | null
    currency?: string
    created_at: string (date-time)
    user_id: string
    dividends?: array of `DividendRead`
    positions?: array of `PositionRead`
    transactions?: array of `TransactionRead`
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

- `symbol` (string | null, optional) — exact match (Eduardo)
- `kind` (`AssetKind` | null, optional)
- `currency` (string | null, optional)
- `search` (string | null, optional) — ilike sobre symbol o name
- `limit` (integer, optional)
- `offset` (integer, optional)

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


## positions

### `GET` `/positions`

List Positions

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
  }
```

**Response 422** — Validation Error:

```
HTTPValidationError: {
    detail?: array of `ValidationError`
  }
```

## Metrics

Las rutas retornan las métricas daily y/o monthly ordenadas por fecha (de la más reciente a la más antigua)

### `GET` `/assets/{asset_id}/metrics`

```
"daily": [
  {
    "id": uuid
    "asset_id": uuid
    "date": date
    "absolute_return": numeric(10, 4)
    "volatility": numeric(10, 4)
    "max_drawdown": numeric(10, 4)
  }
],
"monthly": [
  {
    "id": uuid
    "asset_id": uuid
    "date": date
    "beta": numeric(10, 4)
  }
]
```

### `GET` `/accounts/{account_id}/metrics`

```
"daily": [
  {
    "id": uuid
    "account_id": uuid
    "date": date
    "pnl": numeric(18, 2)
    "max_drawdown": numeric(18, 2)
    "volatility": numeric(8, 6)
  }
],
"monthly": [
  {
    "id": uuid
    "account_id": uuid
    "twr": numeric(10, 8)
    "dietz": numeric(10, 8)
    "sharpe_ratio": numeric(6, 4)
    "var": numeric(18, 2)
    "sortino": numeric(6, 4)
    "assets_correlation": numeric(5, 4)
  }
]
```

### `GET` `/portfolio/{portfolio_id}/metrics`

```
"daily": [
  {
    "id": uuid
    "portfolio_id": uuid
    "date": date
    "pnl": numeric(18, 2)
    "max_drawdown": numeric(18, 2)
    "volatility": numeric(8, 6)
    "fx_decomposition": jsonb
  }
],
"monthly": [
  {
    "id": uuid
    "portfolio": uuid
    "date": date
    "twr": numeric(10, 8)
    "dietz": numeric(10, 8)
    "var": numeric(18, 2)
    "accounts_correlation": numeric(5, 4)
  }
]
```

### `GET` `/positions/{position_id}/metrics`

```
"daily": [
  {
    "id": uuid
    "position_id": uuid
    "date": date
    "pnl": numeric(20, 8)
    "unrealized_pnl": numeric(20, 8)
    "total_pnl": numeric(20, 8)
    "personal_return": numeric(10, 4)
  }
]
```


## webhooks

### `POST` `/webhooks/clerk`

Clerk Webhook

---
