#!/usr/bin/env python3
"""
unmatch_transaction.py
Zeigt oder löst Verknüpfungen zwischen einer Transaktion und Belegen auf.
"""

import argparse
from db import get_connection

def show_links(cur, tx_id):
    """Zeigt alle mit der Transaktion verknüpften Belege und Buchungen"""
    print(f"🔎 Transaktion {tx_id} – verbundene Einträge:\n")

    # Transaktionsdetails
    cur.execute("""
        SELECT booking_date, amount, counterpart_name, purpose
          FROM transactions
         WHERE id=%s;
    """, (tx_id,))
    row = cur.fetchone()
    if not row:
        print("❌ Keine Transaktion gefunden.\n")
        return False
    tdate, amount, name, purpose = row
    print(f"📅 Datum: {tdate} | 💶 Betrag: {amount:.2f} EUR | {name or '(kein Name)'}")
    print(f"📝 {purpose[:100] if purpose else ''}\n")

    # Eingangsbelege
    cur.execute("""
        SELECT v.id, v.voucher_number, v.partner_name, v.voucher_date,
               v.total_amount, v.status, b.account_skr
          FROM voucher_links l
          JOIN vouchers v ON v.id = l.voucher_id
          LEFT JOIN booking_lines b ON b.voucher_id = v.id
         WHERE l.transaction_id=%s;
    """, (tx_id,))
    incoming = cur.fetchall()
    if incoming:
        print("📥 Eingangsbelege:")
        for vid, num, partner, vdate, val, status, konto in incoming:
            print(f"  ID {vid:4d} | {num or '-':15s} | {partner[:30]:30s} | "
                  f"{vdate:%Y-%m-%d} | {val:8.2f} € | {status:8s} | {konto or '-'}")
    else:
        print("📥 Keine Eingangsbelege verknüpft.")

    # Ausgangsbelege
    cur.execute("""
        SELECT o.id, o.voucher_number, o.customer_name, o.invoice_date,
               o.total_amount, o.status, b.account_skr
          FROM outgoing_links l
          JOIN outgoing_vouchers o ON o.id = l.outgoing_id
          LEFT JOIN booking_lines b ON b.outgoing_id = o.id
         WHERE l.transaction_id=%s;
    """, (tx_id,))
    outgoing = cur.fetchall()
    if outgoing:
        print("\n📤 Ausgangsbelege:")
        for oid, num, cust, idate, val, status, konto in outgoing:
            print(f"  ID {oid:4d} | {num or '-':15s} | {cust[:30]:30s} | "
                  f"{idate:%Y-%m-%d} | {val:8.2f} € | {status:8s} | {konto or '-'}")
    else:
        print("\n📤 Keine Ausgangsbelege verknüpft.")

    return bool(incoming or outgoing)

def unmatch_transaction(tx_id):
    """Löst Verknüpfungen und setzt Status zurück"""
    conn = get_connection()
    cur = conn.cursor()

    if not show_links(cur, tx_id):
        conn.close()
        return

    confirm = input("\n⚠️  Wirklich alle Verknüpfungen dieser Transaktion löschen? [y/N] ").strip().lower()
    if confirm != "y":
        print("🚫 Abgebrochen.")
        conn.close()
        return

    # Eingangsbelege lösen
    cur.execute("SELECT voucher_id FROM voucher_links WHERE transaction_id=%s;", (tx_id,))
    vids = [r[0] for r in cur.fetchall()]
    cur.execute("DELETE FROM voucher_links WHERE transaction_id=%s;", (tx_id,))
    for vid in vids:
        cur.execute("UPDATE vouchers SET status='draft' WHERE id=%s;", (vid,))

    # Ausgangsbelege lösen
    cur.execute("SELECT outgoing_id FROM outgoing_links WHERE transaction_id=%s;", (tx_id,))
    oids = [r[0] for r in cur.fetchall()]
    cur.execute("DELETE FROM outgoing_links WHERE transaction_id=%s;", (tx_id,))
    for oid in oids:
        cur.execute("UPDATE outgoing_vouchers SET status='draft' WHERE id=%s;", (oid,))

    conn.commit()
    cur.close()
    conn.close()

    print("\n✅ Verknüpfungen gelöscht und Belege auf 'draft' gesetzt.")

def main():
    ap = argparse.ArgumentParser(description="Zeigt oder entfernt Belegverknüpfungen zu einer Transaktion.")
    ap.add_argument("--tx-id", type=int, required=True, help="Transaktions-ID")
    ap.add_argument("--unmatch", action="store_true", help="Löst alle Verknüpfungen dieser Transaktion auf")
    args = ap.parse_args()

    conn = get_connection()
    cur = conn.cursor()

    if args.unmatch:
        conn.close()
        unmatch_transaction(args.tx_id)
    else:
        show_links(cur, args.tx_id)
        cur.close()
        conn.close()

if __name__ == "__main__":
    main()
