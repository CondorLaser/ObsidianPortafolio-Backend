"""Genera docs/API_CONTRACT.md desde el OpenAPI vivo de la app.

Como lee el spec REAL (no escribe a mano), el contrato nunca queda desfasado:
basta re-correr el script tras cambiar rutas y commitear el .md.

Uso:
    docker compose up -d   # tener la API corriendo
    ./venv/bin/python -m scripts.generate_api_contract
"""
import json
import sys
from collections import defaultdict
from pathlib import Path

import httpx


OUTPUT = Path(__file__).parent.parent / "docs" / "API_CONTRACT.md"


def fmt_schema_ref(ref: str) -> str:
    return ref.split("/")[-1]


def fmt_schema(schema: dict, components: dict, indent: int = 0) -> str:
    """Pretty-print de un schema Pydantic recursivo (lista campos + tipos)."""
    pad = "  " * indent
    if "$ref" in schema:
        name = fmt_schema_ref(schema["$ref"])
        ref = components.get(name, {})
        return f"`{name}` " + fmt_schema(ref, components, indent)
    t = schema.get("type")
    if t == "array":
        items = schema.get("items", {})
        return "array of " + fmt_schema(items, components, indent)
    if t == "object" or "properties" in schema:
        props = schema.get("properties", {})
        required = set(schema.get("required", []))
        lines = ["{"]
        for name, prop in props.items():
            req = "" if name in required else "?"
            type_str = _scalar_type(prop, components)
            lines.append(f"{pad}    {name}{req}: {type_str}")
        lines.append(f"{pad}  }}")
        return "\n".join(lines)
    return _scalar_type(schema, components)


def _scalar_type(prop: dict, components: dict) -> str:
    if "$ref" in prop:
        return f"`{fmt_schema_ref(prop['$ref'])}`"
    if "anyOf" in prop:
        # nullable common pattern: anyOf [type, {"type": "null"}]
        non_null = [a for a in prop["anyOf"] if a.get("type") != "null"]
        nullable = any(a.get("type") == "null" for a in prop["anyOf"])
        if len(non_null) == 1:
            inner = _scalar_type(non_null[0], components)
            return f"{inner} | null" if nullable else inner
        return " | ".join(_scalar_type(a, components) for a in prop["anyOf"])
    t = prop.get("type", "any")
    if t == "array":
        return "array of " + _scalar_type(prop.get("items", {}), components)
    if prop.get("format"):
        return f"{t} ({prop['format']})"
    if prop.get("enum"):
        return "enum [" + ", ".join(f'"{v}"' for v in prop["enum"]) + "]"
    return t


def main():
    spec = httpx.get("http://127.0.0.1:8000/openapi.json").json()
    paths = spec["paths"]
    components = spec.get("components", {}).get("schemas", {})

    # Agrupar por tag
    by_tag = defaultdict(list)
    for path, methods in paths.items():
        for method, op in methods.items():
            tags = op.get("tags") or ["misc"]
            by_tag[tags[0]].append((method.upper(), path, op))

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    out = []
    out.append("# API Contract — Orion Portafolio Backend\n")
    out.append("> ⚙️ Generado automáticamente desde `/openapi.json`. **NO editar a mano** — re-correr `scripts/generate_api_contract.py`.\n")
    out.append(f"**Total endpoints**: {sum(len(v) for v in by_tag.values())}  ")
    out.append(f"**Base URL local**: `http://localhost:8000` (sin `/api/v1`)  ")
    out.append("**Auth**: Bearer JWT Clerk en header `Authorization` (excepto rutas públicas)\n")

    # Tabla resumen
    out.append("## Resumen\n")
    out.append("| Tag | Endpoints |")
    out.append("|---|---|")
    for tag, ops in sorted(by_tag.items()):
        paths_in_tag = sorted({p for _, p, _ in ops})
        out.append(f"| **{tag}** | {len(ops)} ({', '.join(f'`{p}`' for p in paths_in_tag)}) |")
    out.append("")

    # Detalle por tag
    for tag, ops in sorted(by_tag.items()):
        out.append(f"\n## {tag}\n")
        for method, path, op in sorted(ops, key=lambda x: (x[1], x[0])):
            summary = op.get("summary") or op.get("description") or ""
            summary = summary.split("\n")[0].strip()
            out.append(f"### `{method}` `{path}`\n")
            if summary:
                out.append(f"{summary}\n")

            # Params
            params = op.get("parameters", [])
            path_params = [p for p in params if p.get("in") == "path"]
            query_params = [p for p in params if p.get("in") == "query"]
            if path_params:
                out.append("**Path params**:\n")
                for p in path_params:
                    t = _scalar_type(p.get("schema", {}), components)
                    out.append(f"- `{p['name']}`: {t}")
                out.append("")
            if query_params:
                out.append("**Query params**:\n")
                for p in query_params:
                    t = _scalar_type(p.get("schema", {}), components)
                    req = "**required**" if p.get("required") else "optional"
                    desc = p.get("description", "")
                    line = f"- `{p['name']}` ({t}, {req})"
                    if desc:
                        line += f" — {desc}"
                    out.append(line)
                out.append("")

            # Request body
            req_body = op.get("requestBody")
            if req_body:
                content = req_body.get("content", {})
                json_schema = content.get("application/json", {}).get("schema", {})
                if json_schema:
                    out.append("**Request body** (application/json):\n")
                    out.append("```")
                    if "$ref" in json_schema:
                        name = fmt_schema_ref(json_schema["$ref"])
                        out.append(f"{name}: {fmt_schema(components.get(name, {}), components)}")
                    else:
                        out.append(fmt_schema(json_schema, components))
                    out.append("```\n")
                multipart = content.get("multipart/form-data", {}).get("schema", {})
                if multipart:
                    out.append("**Request body** (multipart/form-data):\n")
                    out.append("```")
                    out.append(fmt_schema(multipart, components))
                    out.append("```\n")

            # Responses
            responses = op.get("responses", {})
            for code, resp in sorted(responses.items()):
                desc = resp.get("description", "")
                content = resp.get("content", {})
                json_schema = content.get("application/json", {}).get("schema", {})
                if json_schema:
                    out.append(f"**Response {code}** — {desc}:\n")
                    out.append("```")
                    if "$ref" in json_schema:
                        name = fmt_schema_ref(json_schema["$ref"])
                        out.append(f"{name}: {fmt_schema(components.get(name, {}), components)}")
                    elif json_schema.get("type") == "array" and "$ref" in json_schema.get("items", {}):
                        name = fmt_schema_ref(json_schema["items"]["$ref"])
                        out.append(f"array of {name}:")
                        out.append(fmt_schema(components.get(name, {}), components))
                    else:
                        out.append(fmt_schema(json_schema, components))
                    out.append("```\n")
                elif desc and code != "200":
                    out.append(f"**Response {code}** — {desc}\n")

            out.append("---\n")

    OUTPUT.write_text("\n".join(out))
    print(f"✅ API contract generado: {OUTPUT} ({OUTPUT.stat().st_size:,} bytes)")
    print(f"   Total endpoints: {sum(len(v) for v in by_tag.values())}")


if __name__ == "__main__":
    sys.exit(main())
