#!/usr/bin/env python3
"""
report_open_vouchers.py
Zeigt alle offenen Belege (incoming/outgoing) – optional gefiltert nach Monat.
"""

import argparse
from datetime import datetime, timedelta
from db import get_connection

def report_open_vouchers(month=None):
    conn = get_connection()
    cur = conn.cursor()

    if month:
        mdate = datetime.strptime(month, "%Y-%m")
        start = mdate.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        print(f"📅 Zeitraum: {start:%Y-%m-%d} bis {end:%Y-%m-%d}\n")
    else:
        start = datetime(1970, 1, 1)
        end = datetime(2100, 1, 1)

    print("📄 Offene Eingangsbelege:\n")
    cur.execute("""
        SELECT v.voucher_number, v.partner_name, v.total_amount,
               v.voucher_date, v.payment_due_date
          FROM vouchers v
          LEFT JOIN voucher_links l ON v.id = l.voucher_id
         WHERE l.id IS NULL
           AND (v.status IS NULL OR v.status != 'paid')
           AND v.voucher_date BETWEEN %s AND %s
         ORDER BY v.voucher_date;
    """, (start, end))

    rows = cur.fetchall()
    if not rows:
        print("  (keine offenen Eingangsbelege)\n")
    else:
        for num, name, amount, vdate, due in rows:
            due_str = due.strftime("%Y-%m-%d") if due else "-"
            print(f"  {num or '(kein Nr.)':15s} | {name[:35]:35s} | {vdate:%Y-%m-%d} | Fälligkeit: {due_str} | {amount:8.2f} EUR")

    print("\n📄 Offene Ausgangsbelege:\n")
    cur.execute("""
        SELECT o.invoice_number, o.customer_name, o.total_amount,
               o.invoice_date, o.payment_due_date
          FROM outgoing_vouchers o
          LEFT JOIN outgoing_links l ON o.id = l.outgoing_id
         WHERE l.id IS NULL
           AND (o.status IS NULL OR o.status != 'paid')
           AND o.invoice_date BETWEEN %s AND %s
         ORDER BY o.invoice_date;
    """, (start, end))

    rows = cur.fetchall()
    if not rows:
        print("  (keine offenen Ausgangsbelege)\n")
    else:
        for num, name, amount, vdate, due in rows:
            due_str = due.strftime("%Y-%m-%d") if due else "-"
            print(f"  {num or '(kein Nr.)':15s} | {name[:35]:35s} | {vdate:%Y-%m-%d} | Fälligkeit: {due_str} | {amount:8.2f} EUR")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Listet offene Belege eines Monats auf.")
    ap.add_argument("--month", help="YYYY-MM (optional)")
    args = ap.parse_args()
    report_open_vouchers(args.month)
