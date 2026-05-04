# Diagramas — Orion Portafolio

## Archivos

| Archivo | Qué es | Cómo se regenera |
|---|---|---|
| `data-model.dbml` | Fuente de verdad del **modelo objetivo** (13 tablas) en sintaxis DBML | Se edita a mano. Pegar en https://dbdiagram.io para visualizar drag-and-drop |
| `erd-target.mmd` | Mismo modelo objetivo en sintaxis Mermaid | Se edita a mano |
| `erd-target.png` | PNG renderizado del ERD objetivo | `npx @mermaid-js/mermaid-cli mmdc -i erd-target.mmd -o erd-target.png -b white --width 2400` |
| `erd-cardinalities.mmd` / `.png` | Mismo ERD pero con etiquetas explícitas **1:1** / **1:N** en cada relación (para profe/comité) | `npx @mermaid-js/mermaid-cli mmdc -i erd-cardinalities.mmd -o erd-cardinalities.png -b white --width 2600` |
| `relationships.md` | Tabla resumen de las 18 relaciones con cardinalidad y significado | Editable a mano |
| `domain-model.mmd` | **Modelo de dominio** (conceptual, sin tipos) en Mermaid | Se edita a mano |
| `domain-model.png` | PNG renderizado del modelo de dominio | `npx @mermaid-js/mermaid-cli mmdc -i domain-model.mmd -o domain-model.png -b white --width 2200` |
| `erd-mvp.dot` | DOT auto-generado del **MVP implementado** (5 tablas) | `python -m scripts.generate_erd_mvp` |
| `erd-mvp.png` | PNG del ERD MVP | igual al anterior (mismo script) |

## Diferencia entre los tres diagramas

- **`domain-model`**: vista de negocio. Conceptos (Inversionista, Patrimonio, Recomendación), reglas, fuentes externas (TwelveData, Fintual, Clerk). Sin tipos ni FKs. Cambia cuando el dominio cambia.
- **`erd-target`** (= `data-model.dbml`): modelo de datos completo, end-state. 13 tablas (5 implementadas + 8 diseñadas). Con tipos, PKs, FKs, índices.
- **`erd-mvp`**: foto del schema actual en `develop`. Auto-generado desde `app/models/` vía SQLAlchemy.

## Convenciones del modelo objetivo

- `🟢 [implemented]` (verde) — ya en `develop`, migrado en Neon: `user`, `account`, `asset`, `asset_price`, `transaction`.
- `🟡 [designed]` (amarillo) — diseñadas, no implementadas: `user_profile`, `transaction_import`, `position` (materializada), `portfolio_snapshot`, `fx_rate`, `alert_rule`, `alert`, `recommendation_run`, `recommendation`.
- `🔵 derivadas` — viven en capa de aplicación (no son tablas): patrimonio, rentabilidad, volatilidad, Sharpe, distribución por activo/moneda/cuenta, P&L no realizado, etc.

## Renderizar todo desde cero

```bash
# desde la raíz del backend
source venv/bin/activate

# 1. ERD MVP (auto-generado desde modelos SQLAlchemy)
python -m scripts.generate_erd_mvp

# 2. ERD objetivo y modelo de dominio (Mermaid → PNG)
cd docs
NODE_EXTRA_CA_CERTS=/etc/ssl/cert.pem \
  npx @mermaid-js/mermaid-cli mmdc -i erd-target.mmd -o erd-target.png -b white --width 2400
NODE_EXTRA_CA_CERTS=/etc/ssl/cert.pem \
  npx @mermaid-js/mermaid-cli mmdc -i domain-model.mmd -o domain-model.png -b white --width 2200
```

Para editar el modelo objetivo de forma visual: pega `data-model.dbml` en https://dbdiagram.io, mueve cajas, exporta PNG/SQL/PDF. Cualquier cambio: copia el DBML editado de vuelta al archivo.
