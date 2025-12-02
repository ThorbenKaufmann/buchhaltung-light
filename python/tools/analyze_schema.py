#!/usr/bin/env python3
import re
from pathlib import Path
from collections import defaultdict

schema_file = Path("schema_backup.sql")
sql = schema_file.read_text(encoding="utf-8", errors="ignore")


def split_columns(body: str):
    """
    Spaltet den Inhalt der Klammern eines CREATE TABLE in einzelne
    Spalten-/Constraint-Definitionen, ohne an Kommas innerhalb von
    Klammern (z.B. numeric(12,2)) zu zerschneiden.
    """
    parts = []
    buf = []
    depth = 0
    for ch in body:
        if ch == '(':
            depth += 1
        elif ch == ')':
            if depth > 0:
                depth -= 1

        if ch == ',' and depth == 0:
            part = ''.join(buf).strip()
            if part:
                parts.append(part)
            buf = []
        else:
            buf.append(ch)

    last = ''.join(buf).strip()
    if last:
        parts.append(last)
    return parts


# --- Table extraction pattern (handles schema-qualified names) ---
table_pattern = re.compile(
    r"CREATE TABLE\s+(?:\w+\.)?\"?(\w+)\"?\s*\((.*?)\);",
    re.S | re.I,
)

# FK-Pattern wird pro Tabelle auf deren Body angewandt
fk_pattern = re.compile(
    r"CONSTRAINT\s+(\w+)\s+FOREIGN KEY\s*\((.*?)\)\s+REFERENCES\s+(?:\w+\.)?\"?(\w+)\"?\s*\((.*?)\)",
    re.I | re.S,
)

tables = {}
fkeys = []  # (local_table, constraint_name, local_cols, ref_table, ref_cols)

for table, body in table_pattern.findall(sql):
    cols = []

    # Spalten-/Constraint-Definitionen robust splitten
    for item in split_columns(body):
        upper = item.upper()
        if upper.startswith(("CONSTRAINT ", "PRIMARY KEY", "FOREIGN KEY", "UNIQUE ")):
            # FKs direkt hier herausziehen
            for cname, col, ref_table, ref_col in fk_pattern.findall(item):
                fkeys.append(
                    (table, cname, col.strip(), ref_table.strip(), ref_col.strip())
                )
            continue

        # Spalte: "name" type ...
        m = re.match(r"\"?(\w+)\"?\s+([A-Za-z0-9_\(\),]+)", item)
        if m:
            col_name = m.group(1)
            col_type = m.group(2)
            cols.append((col_name, col_type))

    tables[table] = cols

# --- Markdown summary ---
md = ["# Database Schema Overview\n"]
for t, cols in sorted(tables.items()):
    md.append(f"## {t}\n")
    md.append("| Column | Type |")
    md.append("|---------|------|")
    for c, typ in cols:
        md.append(f"| {c} | {typ} |")
    md.append("")

if fkeys:
    md.append("\n# Foreign Keys\n")
    for local_table, cname, col, ref_table, ref_col in fkeys:
        md.append(
            f"- `{cname}` in `{local_table}`: {col} → {ref_table}({ref_col})"
        )

# --- Redundancy detection ---
all_cols = [c for tbl in tables.values() for c, _ in tbl]
dupes = {c for c in all_cols if all_cols.count(c) > 1}
if dupes:
    md.append("\n# Potentially Redundant Columns\n")
    for d in sorted(dupes):
        md.append(f"- `{d}`")

Path("schema_report.md").write_text("\n".join(md), encoding="utf-8")

# --- Mermaid ER Diagram ---
mermaid = ["erDiagram"]
for t, cols in sorted(tables.items()):
    mermaid.append(f"  {t} {{")
    for c, typ in cols:
        safe_typ = re.sub(r"[^A-Za-z0-9_]", "_", typ)  # ersetzt ( , ) durch _
        mermaid.append(f"    {safe_typ} {c}")
    mermaid.append("  }")


for local_table, cname, col, ref_table, ref_col in fkeys:
    # sehr einfache Darstellung, 1:1 Beziehung angenommen
    mermaid.append(
        f"  {local_table} ||--|| {ref_table} : {col}->{ref_col}"
    )

Path("schema_erd.mmd").write_text("\n".join(mermaid), encoding="utf-8")

print("✅ Schema analysis complete:")
print(" - schema_report.md (Markdown summary)")
print(" - schema_erd.mmd (Mermaid ER diagram)")
