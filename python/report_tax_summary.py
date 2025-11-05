#!/usr/bin/env python3
"""
report_tax_summary.py
Summiert Netto- und Steuerbeträge je Steuersatz / Kategorie (tax_type)
→ Grundlage für USt-Voranmeldung.
"""

from datetime import datetime, timedelta
import argparse
from db import get_connection


def report_tax_summary(month):
    conn = get_connection()
    cur = conn.cursor()

    mdate = datetime.strptime(month, "%Y-%m")
    start = mdate.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)

    cur.execute("""
        SELECT COALESCE(tax_type, 'unknown') AS tax_type,
               direction,
               ROUND(SUM(net_amount),2) AS net_sum,
               ROUND(SUM(tax_amount),2) AS tax_sum,
               COUNT(*) AS cnt
          FROM booking_lines
         WHERE created_at BETWEEN %s AND %s
         GROUP BY tax_type, direction
         ORDER BY direction, tax_type;
    """, (start, end))

    rows = cur.fetchall()

    print(f"📆 Steuer-Summen {start.date()} bis {end.date()}\n")
    print(f"{'Typ':<15} {'Richtung':<10} {'Netto €':>12} {'Steuer €':>12} {'#':>4}")
    print("-"*60)

    for tax_type, direction, net, tax, cnt in rows:
        print(f"{tax_type:<15} {direction:<10} {net:>12.2f} {tax:>12.2f} {cnt:>4}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Umsatzsteuer-Summenbericht")
    ap.add_argument("--month", required=True, help="YYYY-MM")
    args = ap.parse_args()
    report_tax_summary(args.month)
