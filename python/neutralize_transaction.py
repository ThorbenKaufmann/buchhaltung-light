#!/usr/bin/env python3
"""
neutralize_transaction.py
Entfernt alle Verknüpfungen, Buchungslinien und Belegstatus
zu einer gegebenen Transaktions-ID (TxID).

Optionen:
  --txid NNNN        → Transaktions-ID
  --dry-run          → Nur anzeigen, nichts löschen
"""

import argparse
from db import get_connection


def neutralize_transaction(txid: int, dry_run: bool):
    conn = get_connection()
    cur = conn.cursor()

    print(f"🔄 Neutralisiere Transaktion TxID {txid} {'(Trockentest)' if dry_run else ''}\n")

    # --- 1️⃣ Zugehörige Buchungslinien ---
    cur.execute("""
        SELECT id, account_skr, gross_amount, receipt_status
          FROM booking_lines
         WHERE description = %s;
    """, (str(txid),))
    lines = cur.fetchall()
    if lines:
        print(f"📘 {len(lines)} Buchungslinie(n) gefunden:")
        for lid, acc, gross, status in lines:
            print(f"    🧾 ID {lid} | Konto {acc} | Betrag {gross:.2f} | Status {status}")
        if not dry_run:
            cur.execute("DELETE FROM booking_lines WHERE description = %s;", (str(txid),))
    else:
        print("🟡 Keine Buchungslinien zu dieser TxID gefunden.")

    # --- 2️⃣ Verknüpfte Belege (incoming) ---
    cur.execute("""
        SELECT v.id, v.voucher_number, v.partner_name
          FROM voucher_links vl
          JOIN vouchers v ON v.id = vl.voucher_id
         WHERE vl.transaction_id = %s;
    """, (txid,))
    vouchers = cur.fetchall()
    if vouchers:
        print(f"📄 {len(vouchers)} verknüpfte Eingangsbelege:")
        for vid, vnum, vname in vouchers:
            print(f"    Beleg {vid} | {vnum or '-'} | {vname}")
        if not dry_run:
            cur.execute("DELETE FROM voucher_links WHERE transaction_id = %s;", (txid,))
            cur.execute("UPDATE vouchers SET status='draft' WHERE id = ANY(%s);",
                        ([v[0] for v in vouchers],))
    else:
        print("🟡 Keine Eingangsbelege verknüpft.")

    # --- 3️⃣ Verknüpfte Ausgangsbelege ---
    cur.execute("""
        SELECT o.id, o.voucher_number, o.customer_name
          FROM outgoing_links ol
          JOIN outgoing_vouchers o ON o.id = ol.outgoing_id
         WHERE ol.transaction_id = %s;
    """, (txid,))
    outgoing = cur.fetchall()
    if outgoing:
        print(f"📄 {len(outgoing)} verknüpfte Ausgangsbelege:")
        for oid, vnum, cname in outgoing:
            print(f"    Beleg {oid} | {vnum or '-'} | {cname}")
        if not dry_run:
            cur.execute("DELETE FROM outgoing_links WHERE transaction_id = %s;", (txid,))
            cur.execute("UPDATE outgoing_vouchers SET status='draft' WHERE id = ANY(%s);",
                        ([o[0] for o in outgoing],))
    else:
        print("🟡 Keine Ausgangsbelege verknüpft.")

    # --- 4️⃣ Optional: Transaktionskategorie zurücksetzen ---
    if not dry_run:
        cur.execute("""
            UPDATE transactions
               SET category = NULL,
                   is_private = FALSE,
                   is_internal = FALSE
             WHERE id = %s;
        """, (txid,))

    if not dry_run:
        conn.commit()
        print("\n✅ Neutralisierung abgeschlossen.")
    else:
        print("\n🔍 (Dry-Run) Es wurden keine Änderungen vorgenommen.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Transaktion vollständig neutralisieren")
    ap.add_argument("--txid", type=int, required=True, help="Transaktions-ID")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts löschen")
    args = ap.parse_args()
    neutralize_transaction(args.txid, args.dry_run)
