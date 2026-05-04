# Relaciones del modelo de datos — Orion Portafolio

Tabla de relaciones con cardinalidades explícitas. Útil para acompañar el ERD.

| # | Origen | Cardinalidad | Destino | Significado |
|---|---|---|---|---|
| 1 | `user` | **1 : 1** | `user_profile` | Cada usuario tiene un perfil extendido (nombre, país, perfil de riesgo) |
| 2 | `user` | **1 : N** | `account` | Un usuario puede tener varias cuentas (Fintual USD, Fintual CLP, IBKR, etc.) |
| 3 | `user` | **1 : N** | `transaction_import` | Un usuario carga varios certificados/CSV a lo largo del tiempo |
| 4 | `user` | **1 : N** | `portfolio_snapshot` | Un usuario tiene una foto diaria del patrimonio (1 fila por día) |
| 5 | `user` | **1 : N** | `alert_rule` | Un usuario configura múltiples reglas de alerta |
| 6 | `user` | **1 : N** | `alert` | Un usuario recibe múltiples alertas en el tiempo |
| 7 | `user` | **1 : N** | `recommendation` | Un usuario recibe múltiples recomendaciones |
| 8 | `account` | **1 : N** | `transaction` | Una cuenta acumula muchas transacciones (compra, venta, dividendo, fee) |
| 9 | `account` | **1 : N** | `position` | Una cuenta mantiene posiciones netas en varios activos |
| 10 | `account` | **1 : N** | `alert_rule` | Una cuenta puede ser objetivo de varias reglas (opcional) |
| 11 | `asset` | **1 : N** | `asset_price` | Un activo tiene serie histórica de precios diarios |
| 12 | `asset` | **1 : N** | `transaction` | Un activo es operado en muchas transacciones |
| 13 | `asset` | **1 : N** | `position` | Un activo aparece en múltiples posiciones (cuentas distintas) |
| 14 | `asset` | **1 : N** | `alert_rule` | Un activo puede ser objetivo de varias reglas (opcional) |
| 15 | `asset` | **1 : N** | `recommendation` | Un activo puede ser sugerido a múltiples usuarios |
| 16 | `transaction_import` | **1 : N** | `transaction` | Un certificado/CSV genera varias transacciones |
| 17 | `alert_rule` | **1 : N** | `alert` | Una regla dispara múltiples alertas en el tiempo |
| 18 | `recommendation_run` | **1 : N** | `recommendation` | Cada corrida del motor produce muchas recomendaciones |

## Notas

- `position` y `asset_price` usan **PK compuesta** (no FK simple): `(account_id, asset_id)` y `(asset_id, date)` respectivamente. Garantiza unicidad sin tabla intermedia.
- `fx_rate` usa **PK compuesta** `(date, base, quote)` y no tiene FK a otras tablas — es tabla de referencia global.
- Todas las relaciones donde `user` es origen están **aisladas por usuario** en la capa de aplicación: cada query filtra por `user_id` para que un cliente solo vea sus propios datos.
- Las relaciones marcadas "opcional" usan FK nullable (la regla puede aplicar a un asset O a una account, no necesariamente ambos).
- No hay relaciones N:M directas — todas son 1:1 o 1:N. Los pares como "muchos usuarios sobre muchos activos" se resuelven a través de `transaction` o `position`, que actúan como tablas asociativas.
