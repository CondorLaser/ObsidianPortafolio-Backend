"""Genera un ERD del MVP (las 5 tablas implementadas) en formato DOT y PNG.

Lee Base.metadata de SQLAlchemy y produce un .dot que se renderiza con
graphviz (binary `dot`). No requiere pygraphviz (que no compila en Py 3.14).

Usage:
    python -m scripts.generate_erd_mvp
"""
import subprocess
import sys
from pathlib import Path

from sqlalchemy import ForeignKey

from app.models import Base

DOCS = Path(__file__).resolve().parent.parent / "docs"
DOT_PATH = DOCS / "erd-mvp.dot"
PNG_PATH = DOCS / "erd-mvp.png"


def col_label(col) -> str:
    parts = [col.name]
    type_str = str(col.type).lower()
    if col.primary_key:
        parts.append("PK")
    if any(isinstance(fk, ForeignKey) for fk in col.foreign_keys):
        parts.append("FK")
    if col.unique:
        parts.append("UK")
    if not col.nullable:
        parts.append("NN")
    badge = " ".join(parts[1:]) or "&nbsp;"
    return (
        f"<TR><TD ALIGN='LEFT'><B>{col.name}</B></TD>"
        f"<TD ALIGN='LEFT'>{type_str}</TD>"
        f"<TD ALIGN='LEFT'><FONT COLOR='#666'>{badge}</FONT></TD></TR>"
    )


def table_node(table) -> str:
    rows = "\n".join(col_label(c) for c in table.columns)
    return (
        f'    "{table.name}" [shape=plaintext, label=<\n'
        f'      <TABLE BORDER="1" CELLBORDER="0" CELLSPACING="0" CELLPADDING="6" BGCOLOR="white">\n'
        f'        <TR><TD COLSPAN="3" BGCOLOR="#2E7D32"><FONT COLOR="white"><B>{table.name}</B></FONT></TD></TR>\n'
        f'        {rows}\n'
        f'      </TABLE>>];'
    )


def edges(metadata) -> list[str]:
    out = []
    for table in metadata.sorted_tables:
        for col in table.columns:
            for fk in col.foreign_keys:
                target = fk.column.table.name
                out.append(f'    "{target}" -> "{table.name}" [arrowhead=crow, arrowtail=none, dir=both, color="#555"];')
    return out


def main() -> int:
    DOCS.mkdir(parents=True, exist_ok=True)
    md = Base.metadata

    nodes = "\n".join(table_node(t) for t in md.sorted_tables)
    rels = "\n".join(edges(md))

    dot = (
        'digraph orion_mvp {\n'
        '  graph [rankdir=LR, splines=ortho, nodesep=0.6, ranksep=0.9, '
        'label="Orion Portafolio — ERD del MVP (implementado)", '
        'labelloc=t, fontsize=18, fontname="Helvetica"];\n'
        '  node  [fontname="Helvetica", fontsize=11];\n'
        '  edge  [fontname="Helvetica", fontsize=10];\n'
        f'{nodes}\n\n'
        f'{rels}\n'
        '}\n'
    )
    DOT_PATH.write_text(dot, encoding="utf-8")
    print(f"wrote {DOT_PATH}")

    res = subprocess.run(
        ["dot", "-Tpng", str(DOT_PATH), "-o", str(PNG_PATH)],
        capture_output=True,
        text=True,
    )
    if res.returncode != 0:
        print(res.stderr, file=sys.stderr)
        return res.returncode
    print(f"wrote {PNG_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
