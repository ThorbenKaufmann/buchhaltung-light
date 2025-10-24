#!/usr/bin/env python3
"""
report_unlinked_transactions.py
Zeigt Transaktionen ohne zugehörigen Beleg-Link – optional gefiltert nach Monat.
"""

import argparse
from datetime import datetime, timedelta
from db import get_connection

def report_unlinked_transactions(month=None):
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

    cur.execute("""
        SELECT t.id, t.booking_date, t.amount, t.counterpart_name, t.purpose
        FROM transactions t
        LEFT JOIN voucher_links v ON v.transaction_id = t.id
        LEFT JOIN outgoing_links o ON o.transaction_id = t.id
        WHERE v.id IS NULL
        AND o.id IS NULL
        AND (t.is_private IS FALSE OR t.is_private IS NULL)
        AND t.booking_date BETWEEN %s AND %s
        ORDER BY t.booking_date;
    """, (start, end))


    rows = cur.fetchall()
    if not rows:
        print("✅ Keine unverknüpften Transaktionen im angegebenen Zeitraum.\n")
    else:
        print("💶 Unverknüpfte Transaktionen:\n")
        for tid, bdate, amount, name, purpose in rows:
            amt = f"{amount:8.2f} EUR"
            cname = (name or "-")[:35]
            snippet = (purpose or "").replace("\n", " ")[:70]
            print(f"  TxID {tid:6d} | {bdate:%Y-%m-%d} | {amt:>12s} | {cname:35s} | {snippet}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Listet Transaktionen ohne Beleg auf.")
    ap.add_argument("--month", help="YYYY-MM (optional)")
    args = ap.parse_args()
    report_unlinked_transactions(args.month)
