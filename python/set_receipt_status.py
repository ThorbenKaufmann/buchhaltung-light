#!/usr/bin/env python3
"""
set_receipt_status.py
Ändert den Belegstatus ('complete','pending','missing','incomplete')
für Eingangs-, Ausgangsbelege oder Buchungen.
"""

import argparse
from db import get_connection

def set_status(kind, record_id, status):
    conn = get_connection()
    cur = conn.cursor()

    if kind == "voucher":
        table = "vouchers"
    elif kind == "outgoing":
        table = "outgoing_vouchers"
    elif kind == "booking":
        table = "booking_lines"
    else:
        print("❌ Ungültiger Typ. Erlaubt: voucher, outgoing, booking")
        return

    cur.execute(f"UPDATE {table} SET receipt_status=%s WHERE id=%s;", (status, record_id))
    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Status für {kind} #{record_id} → {status}")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Ändert den receipt_status eines Belegs oder einer Buchung.")
    ap.add_argument("kind", choices=["voucher","outgoing","booking"], help="Art des Eintrags")
    ap.add_argument("id", type=int, help="ID des Datensatzes")
    ap.add_argument("status", choices=["complete","pending","missing","incomplete"], help="Neuer Status")
    args = ap.parse_args()

    set_status(args.kind, args.id, args.status)
