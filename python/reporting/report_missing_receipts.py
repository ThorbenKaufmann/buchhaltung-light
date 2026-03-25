#!/usr/bin/env python3
"""
report_missing_receipts.py (NEU)

Zeigt Transaktionen ohne zugeordneten Beleg (incoming/outgoing).

Features:
  --month YYYY-MM
  --non-private
  --non-internal
  --group-by counterpart|purpose
  --export csv|md
"""

import argparse
import csv
from datetime import datetime, timedelta
from pathlib import Path
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection


def safe_float(v):
    try:
        return float(v)
    except:
        return 0.0


def report_missing_receipts(month, non_private, non_internal, group_by, export):
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()

    # Zeitraum
    mdate = datetime.strptime(month, "%Y-%m")
    start = mdate.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)

    print(f"\n📅 Zeitraum: {start.date()} bis {end.date()}\n")

    # --- CORE QUERY (NEU!) ---
    sql = """
    SELECT
        t.id,
        t.booking_date,
        t.amount,
        t.counterpart_name,
        t.purpose,
        t.is_private,
        t.is_internal
    FROM transactions t
    LEFT JOIN voucher_links vl
           ON vl.transaction_id = t.id
    LEFT JOIN outgoing_links ol
           ON ol.transaction_id = t.id
    WHERE t.booking_date >= %s
      AND t.booking_date < %s
      AND vl.transaction_id IS NULL
      AND ol.transaction_id IS NULL
    """

    params = [start, end]

    if non_private:
        sql += " AND t.is_private IS NOT TRUE"

    if non_internal:
        sql += " AND t.is_internal IS NOT TRUE"

    sql += " ORDER BY ABS(t.amount) DESC, t.booking_date"

    cur.execute(sql, params)
    rows = cur.fetchall()

    if not rows:
        print("✅ Keine offenen Transaktionen.\n")
        return

    print(f"⚠️  {len(rows)} Transaktion(en) ohne Beleg:\n")

    export_rows = []

    # ---------------------------------------------------------
    # DETAIL OUTPUT
    # ---------------------------------------------------------
    for r in rows:
        amount = safe_float(r["amount"])
        priv = "P" if r["is_private"] else "-"
        internal = "I" if r["is_internal"] else "-"

        print("-" * 120)
        print(
            f"{r['booking_date']} | "
            f"{amount:10.2f} € | "
            f"{(r['counterpart_name'] or '-')[:25]:25} | "
            f"{priv}/{internal} | "
            f"{(r['purpose'] or '-')[:80]}"
        )

        export_rows.append({
            "id": r["id"],
            "date": r["booking_date"],
            "amount": amount,
            "counterpart": r["counterpart_name"],
            "purpose": r["purpose"],
            "private": r["is_private"],
            "internal": r["is_internal"],
        })

    print("-" * 120)

    # ---------------------------------------------------------
    # OPTIONAL GROUPING
    # ---------------------------------------------------------
    if group_by:
        print("\n📊 Gruppierung:\n")

        groups = {}
        key_field = "counterpart_name" if group_by == "counterpart" else "purpose"

        for r in rows:
            key = (r[key_field] or "").strip() or "<leer>"
            groups.setdefault(key, 0)
            groups[key] += abs(safe_float(r["amount"]))

        sorted_groups = sorted(groups.items(), key=lambda x: x[1], reverse=True)

        for k, v in sorted_groups:
            print(f"{v:10.2f} € | {k[:60]}")

    # ---------------------------------------------------------
    # EXPORT
    # ---------------------------------------------------------
    if export and export_rows:
        out_file = Path(f"missing_receipts_{month}.{export}")

        if export == "csv":
            with out_file.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=export_rows[0].keys())
                writer.writeheader()
                writer.writerows(export_rows)

        elif export == "md":
            with out_file.open("w", encoding="utf-8") as f:
                f.write("| " + " | ".join(export_rows[0].keys()) + " |\n")
                f.write("|" + "|".join(["---"] * len(export_rows[0])) + "|\n")
                for row in export_rows:
                    f.write("| " + " | ".join(str(v) for v in row.values()) + " |\n")

        print(f"\n💾 Export: {out_file.resolve()}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Fehlende Belege anzeigen")

    ap.add_argument("--month", required=True)
    ap.add_argument("--non-private", action="store_true")
    ap.add_argument("--non-internal", action="store_true")
    ap.add_argument("--group-by", choices=["counterpart", "purpose"])
    ap.add_argument("--export", choices=["csv", "md"])

    args = ap.parse_args()

    report_missing_receipts(
        args.month,
        args.non_private,
        args.non_internal,
        args.group_by,
        args.export
    )