#!/usr/bin/env python3
"""
report_tax_summary.py
Erzeugt eine zusammenfassende Steuerübersicht (USt / Vorsteuer) für einen Zeitraum.

Funktioniert sowohl mit booking_lines als auch mit vouchers/outgoing_vouchers.
"""

import sys
import argparse
from datetime import datetime, timedelta
from db import get_connection

def safe_sum(rows, direction):
    return sum((r[3] or 0) for r in rows if r[1] == direction)


def parse_month(month_str: str):
    """Wandelt 'YYYY-MM' in Monatsanfang und Monatsende um."""
    start = datetime.strptime(month_str, "%Y-%m")
    end = (start + timedelta(days=32)).replace(day=1)
    return start.date(), end.date()


def run_tax_summary(month: str):
    start_date, end_date = parse_month(month)
    conn = get_connection()
    cur = conn.cursor()

    print(f"📆 Steuer-Summen {start_date} bis {end_date}")
    print()
    print(f"{'Typ':<15} {'Richtung':<15} {'Netto €':>12} {'Steuer €':>12} {'#':>4}")
    print("-" * 64)

    # 1️⃣ Versuch: booking_lines (bestehende Buchungen)
    cur.execute("""
        SELECT tax_type, direction,
               ROUND(SUM(net_amount)::numeric, 2) AS net_sum,
               ROUND(SUM(tax_amount)::numeric, 2) AS tax_sum,
               COUNT(*) AS cnt
        FROM booking_lines
        WHERE created_at >= %s AND created_at < %s
        GROUP BY tax_type, direction
        ORDER BY direction, tax_type;
    """, (start_date, end_date))
    rows = cur.fetchall()

    # 2️⃣ Fallback: vouchers + outgoing_vouchers
    if not rows:
        cur.execute("""
            SELECT 'vorsteuer19' AS tax_type,
                   'incoming' AS direction,
                   ROUND(SUM(CASE WHEN document_type='credit_note' THEN -total_amount ELSE total_amount END / 1.19)::numeric, 2) AS net_sum,
                   ROUND(SUM(CASE WHEN document_type='credit_note' THEN -total_amount ELSE total_amount END - (CASE WHEN document_type='credit_note' THEN -total_amount ELSE total_amount END / 1.19))::numeric, 2) AS tax_sum,
                   COUNT(*) AS cnt
            FROM vouchers
            WHERE voucher_date >= %s AND voucher_date < %s
            UNION ALL
            SELECT 'ust19' AS tax_type,
                   'outgoing' AS direction,
                   ROUND(SUM(CASE WHEN document_type='credit_note' THEN -total_amount ELSE total_amount END / 1.19)::numeric, 2) AS net_sum,
                   ROUND(SUM(CASE WHEN document_type='credit_note' THEN -total_amount ELSE total_amount END - (CASE WHEN document_type='credit_note' THEN -total_amount ELSE total_amount END / 1.19))::numeric, 2) AS tax_sum,
                   COUNT(*) AS cnt
            FROM outgoing_vouchers
            WHERE voucher_date >= %s AND voucher_date < %s
            ORDER BY direction;
        """, (start_date, end_date, start_date, end_date))
        rows = cur.fetchall()

    total_net = total_tax = total_count = 0
    for tax_type, direction, net_sum, tax_sum, cnt in rows:
        net_sum = net_sum or 0
        tax_sum = tax_sum or 0
        total_net += net_sum
        total_tax += tax_sum
        total_count += cnt
        print(f"{tax_type:<15} {direction:<15} {net_sum:>12.2f} {tax_sum:>12.2f} {cnt:>4}")

    print("-" * 64)
    print(f"{'Gesamt':<30} {total_net:>12.2f} {total_tax:>12.2f} {total_count:>4}")


    #ust_sum = sum(r[3] for r in rows if r[1] == "outgoing")
    #vor_sum = sum(r[3] for r in rows if r[1] == "incoming")

    ust_sum = safe_sum(rows, "outgoing")
    vor_sum = safe_sum(rows, "incoming")

    zahllast = ust_sum - vor_sum
    print(f"\nUSt-Zahllast (Umsatzsteuer - Vorsteuer): {zahllast:>10.2f} €")
    if zahllast < 0:
        print("➡️  Erstattung durch Finanzamt erwartet.")
    else:
        print("➡️  Zahllast an Finanzamt zu entrichten.")


    cur.close()
    conn.close()


def main():
    ap = argparse.ArgumentParser(
        description="Erzeugt eine Steuer-Summenübersicht (USt / Vorsteuer) für einen Monat."
    )
    ap.add_argument(
        "--month",
        required=False,
        default=datetime.today().strftime("%Y-%m"),
        help="Monat im Format YYYY-MM (Standard: aktueller Monat)",
    )
    args = ap.parse_args()

    run_tax_summary(args.month)


if __name__ == "__main__":
    main()
