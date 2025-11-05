#!/usr/bin/env python3
"""
report_missing_receipts.py
Zeigt Transaktionen ohne zugeordneten Beleg (incoming/outgoing).
Optionen:
  --month YYYY-MM      → Zeitraum
  --non-private        → blendet private Transaktionen aus
  --export csv|md      → Exportiert als CSV oder Markdown
"""

import argparse
import csv
from datetime import datetime, timedelta
from pathlib import Path
from db import get_connection


def report_missing_receipts(month: str, non_private: bool, export: str | None):
    conn = get_connection()
    cur = conn.cursor()

    # Zeitraum bestimmen
    mdate = datetime.strptime(month, "%Y-%m")
    start = mdate.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)

    print(f"📅 Zeitraum: {start.date()} bis {end.date()}\n")

    # Basis-Query für Transaktionen
    sql = """
        SELECT t.id, t.booking_date, t.amount, t.counterpart_name, t.purpose, t.is_private
          FROM transactions t
         WHERE t.booking_date BETWEEN %s AND %s
           AND t.id NOT IN (
               SELECT transaction_id FROM voucher_links
               UNION ALL
               SELECT transaction_id FROM outgoing_links
           )
    """
    params = [start, end]
    if non_private:
        sql += " AND t.is_private IS NOT TRUE"
    sql += " ORDER BY t.booking_date;"

    cur.execute(sql, params)
    txs = cur.fetchall()

    if not txs:
        print("✅ Keine Transaktionen ohne Beleg im angegebenen Zeitraum.\n")
        return

    export_rows = []
    print(f"⚠️  {len(txs)} Transaktion(en) ohne Beleg gefunden:\n")

    for tid, tdate, tamount, tname, purpose, is_private in txs:
        priv = " (privat)" if is_private else ""
        print("=" * 90)
        print(f"💳 TxID {tid:5d} | {tdate} | {tamount:8.2f} EUR | {tname or '-'}{priv}")
        print(f"    Zweck: {purpose[:100] if purpose else '-'}")

        # Hat schon eine Buchungslinie?
        cur.execute("""
            SELECT account_skr, gross_amount, receipt_status
              FROM booking_lines
             WHERE description = %s OR description = CAST(%s AS text);
        """, (str(tid), tid))
        lines = cur.fetchall()

        if lines:
            for acc, gross, status in lines:
                print(f"    🧾 Konto {acc:<8} | {status:<10} | {gross:8.2f} EUR")
        else:
            print("    ⚠️  Keine Buchungslinie (booking_lines) vorhanden.")

        export_rows.append({
            "TxID": tid,
            "Datum": tdate,
            "Betrag": float(tamount),
            "Name": tname or "",
            "Zweck": (purpose or "")[:100],
            "Privat": is_private,
            "Hat_BookingLine": bool(lines)
        })

    # Export
    if export and export_rows:
        out_file = Path(f"report_missing_receipts_{month}.{export}")
        if export == "csv":
            with out_file.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(export_rows[0].keys()))
                writer.writeheader()
                writer.writerows(export_rows)
        elif export == "md":
            with out_file.open("w", encoding="utf-8") as f:
                f.write("| " + " | ".join(export_rows[0].keys()) + " |\n")
                f.write("|" + "|".join(["---"] * len(export_rows[0])) + "|\n")
                for row in export_rows:
                    f.write("| " + " | ".join(str(v) for v in row.values()) + " |\n")
        print(f"\n💾 Exportiert nach: {out_file.resolve()}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Transaktionen ohne Beleg auflisten")
    ap.add_argument("--month", required=True, help="Monat im Format YYYY-MM")
    ap.add_argument("--non-private", action="store_true", help="Private Transaktionen ausblenden")
    ap.add_argument("--export", choices=["csv", "md"], help="Exportformat (csv oder md)")
    args = ap.parse_args()
    report_missing_receipts(args.month, args.non_private, args.export)
