#!/usr/bin/env python3
"""
report_tax_summary.py
Erzeugt eine zusammenfassende Steuerübersicht (USt / Vorsteuer) für einen Zeitraum.

Funktioniert sowohl mit booking_lines als auch mit vouchers/outgoing_vouchers.
"""
#!/usr/bin/env python3

import argparse
from datetime import datetime, timedelta
from decimal import Decimal
from db import get_connection


def parse_month(month_str: str):
    start = datetime.strptime(month_str, "%Y-%m")
    end = (start + timedelta(days=32)).replace(day=1)
    return start.date(), end.date()


def run_tax_summary(month: str):
    start_date, end_date = parse_month(month)
    conn = get_connection()
    cur = conn.cursor()

    print(f"📆 Steuer-Summen {start_date} bis {end_date}")
    print()

    # --- Vorsteuer ---
    cur.execute("""
        SELECT COALESCE(SUM(bl.amount), 0)
        FROM booking_lines_new bl
        JOIN voucher_lines vl ON bl.source_type = 'incoming' AND bl.source_id = vl.id
        JOIN vouchers v ON vl.voucher_id = v.id
        WHERE bl.account_skr = '1576'
          AND v.voucher_date >= %s
          AND v.voucher_date < %s
    """, (start_date, end_date))

    vorsteuer = Decimal(cur.fetchone()[0] or 0)

    # --- Umsatzsteuer ---
    cur.execute("""
        SELECT COALESCE(SUM(bl.amount), 0)
        FROM booking_lines_new bl
        JOIN outgoing_lines ol ON bl.source_type = 'outgoing' AND bl.source_id = ol.id
        JOIN outgoing_vouchers ov ON ol.outgoing_id = ov.id
        WHERE bl.account_skr = '1776'
          AND ov.voucher_date >= %s
          AND ov.voucher_date < %s
    """, (start_date, end_date))

    ust_raw = Decimal(cur.fetchone()[0] or 0)

    # Achtung: USt ist negativ gebucht → drehen
    umsatzsteuer = -ust_raw

    # --- Ausgabe ---
    print(f"{'Typ':<20} {'Betrag €':>12}")
    print("-" * 34)
    print(f"{'Vorsteuer (1576)':<20} {vorsteuer:>12.2f}")
    print(f"{'Umsatzsteuer (1776)':<20} {umsatzsteuer:>12.2f}")
    print("-" * 34)

    zahllast = umsatzsteuer - vorsteuer

    print(f"{'Zahllast':<20} {zahllast:>12.2f}")
    print()

    if zahllast < 0:
        print("➡️  Erstattung durch Finanzamt erwartet.")
    else:
        print("➡️  Zahllast an Finanzamt zu entrichten.")

    cur.close()
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="Steuerübersicht basierend auf booking_lines_new")
    ap.add_argument(
        "--month",
        required=False,
        default=datetime.today().strftime("%Y-%m"),
        help="Monat im Format YYYY-MM",
    )
    args = ap.parse_args()

    run_tax_summary(args.month)


if __name__ == "__main__":
    main()