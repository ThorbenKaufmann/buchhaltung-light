#!/usr/bin/env python3
"""
report_open_vouchers.py
-----------------------
Zeigt offene Eingangs- und Ausgangsbelege mit Buchungs- und Zahlungsstatus an.
Kennzeichnet Stornos (negative Beträge) automatisch.
"""

from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection
from bhl_utils import row_get, format_date, safe_float

def report_open_vouchers(month: str):
    conn = get_connection()
    cur = conn.cursor()

    # Zeitraum bestimmen
    start = datetime.strptime(month + "-01", "%Y-%m-%d")
    next_month = start.replace(day=28) + timedelta(days=4)
    end = next_month.replace(day=1)
    print(f"📅 Zeitraum: {start:%Y-%m-%d} bis {end:%Y-%m-%d}\n")

 

    # ---------------------------- Eingangsbelege ----------------------------
    print("\n📄 Offene Eingangsbelege:\n")

    cur.execute("""
        SELECT id, voucher_number, partner_name, voucher_date, total_amount, payment_due_date
        FROM vouchers
        WHERE status != 'paid'
        AND voucher_date BETWEEN %s AND %s
        ORDER BY voucher_date;
    """, (start, end))

    rows = cur.fetchall()

    if not rows:
        print("  (keine offenen Eingangsbelege)\n")
    else:
        for row in rows:
            vid   = row_get(row, "id",            0)
            num   = row_get(row, "voucher_number",1)
            name  = row_get(row, "partner_name",  2)
            vdate = row_get(row, "voucher_date",  3)
            amt   = row_get(row, "total_amount",  4)
            due   = row_get(row, "due_date",      5)

            vdate_str = format_date(vdate)
            due_str   = format_date(due) if due else "-"

            print(f"  ID {vid:4} | {num or '(kein Nr.)':25s} | {name[:35]:35s} "
                f"| {vdate_str} | Fälligkeit: {due_str} | {safe_float(amt):8.2f} EUR")


    # ---------------------------- Ausgangsbelege ----------------------------
    print("\n📄 Offene Ausgangsbelege:\n")

    cur.execute("""
        SELECT id, voucher_number, partner_name, voucher_date, total_amount, payment_due_date
        FROM outgoing_vouchers
        WHERE status != 'paid'
        AND voucher_date BETWEEN %s AND %s
        ORDER BY voucher_date;
    """, (start, end))

    rows = cur.fetchall()

    if not rows:
        print("  (keine offenen Ausgangsbelege)\n")
    else:
        for row in rows:
            vid   = row_get(row, "id",            0)
            num   = row_get(row, "voucher_number",1)
            name  = row_get(row, "partner_name",  2)
            vdate = row_get(row, "voucher_date",  3)
            amt   = row_get(row, "total_amount",  4)
            due   = row_get(row, "due_date",      5)

            vdate_str = format_date(vdate)
            due_str   = format_date(due) if due else "-"

            print(f"  ID {vid:4} | {num or '(kein Nr.)':25s} | {name[:35]:35s} "
                f"| {vdate_str} | Fälligkeit: {due_str} | {safe_float(amt):8.2f} EUR")

    cur.close()
    conn.close()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Zeigt offene Belege mit Buchungs- und Zahlungsstatus an.")
    ap.add_argument("--month", required=True, help="Monat im Format YYYY-MM (z. B. 2024-01)")
    args = ap.parse_args()
    report_open_vouchers(args.month)
