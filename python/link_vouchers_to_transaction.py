#!/usr/bin/env python3
"""
link_vouchers_to_transaction.py
Verknüpft mehrere Eingangs- oder Ausgangsbelege mit einer Banktransaktion.

Beispiel:
    python3 ./python/link_vouchers_to_transaction.py --txid 6072 --vouchers 10,11,12,13
    python3 ./python/link_vouchers_to_transaction.py --txid 6072 --direction outgoing --vouchers 3,4
"""

import argparse
import sys
from decimal import Decimal
from db import get_connection


def link_vouchers_to_transaction(txid: int, voucher_ids: list[int], direction: str):
    conn = get_connection()
    cur = conn.cursor()

    # Tabelle wählen
    if direction == "outgoing":
        voucher_table = "outgoing_vouchers"
        link_table = "outgoing_links"
        id_field = "outgoing_id"
    else:
        voucher_table = "vouchers"
        link_table = "voucher_links"
        id_field = "voucher_id"

    # Transaktion abrufen
    cur.execute(
        """
        SELECT id, booking_date, amount, counterpart_name, purpose
          FROM transactions
         WHERE id=%s;
        """,
        (txid,),
    )
    tx = cur.fetchone()
    if not tx:
        print(f"❌ Transaktion {txid} nicht gefunden.")
        sys.exit(1)
    tid, tdate, tamount, tname, tpurpose = tx

    print(f"\n💳 Transaktion {tid}: {tdate} | {tamount:.2f} EUR | {tname or '-'}")
    print(f"    Zweck: {tpurpose[:100] if tpurpose else '-'}\n")

    # Summierung der Belege
    cur.execute(
        f"""
        SELECT id, voucher_number, partner_name, total_amount, voucher_date
          FROM {voucher_table}
         WHERE id = ANY(%s);
        """,
        (voucher_ids,),
    )
    vouchers = cur.fetchall()

    if not vouchers:
        print("❌ Keine der angegebenen Beleg-IDs gefunden.")
        return

    total_sum = Decimal("0.00")
    print("📄 Zugeordnete Belege:")
    for vid, vnum, vname, vamount, vdate in vouchers:
        print(f"    {vid:4d} | {vnum or '-':15s} | {vname[:30]:30s} | {vamount:8.2f} EUR | {vdate}")
        total_sum += vamount or Decimal("0.00")

    diff = abs(total_sum - abs(tamount))
    print(f"\n💰 Summe Belege: {total_sum:.2f} EUR")
    print(f"💳 Transaktionsbetrag: {abs(tamount):.2f} EUR")
    print(f"➡️  Differenz: {diff:.2f} EUR")

    if diff > Decimal("1.00"):
        print("⚠️  Differenz größer als 1.00 EUR – bitte prüfen!")
    else:
        print("✅ Betrag plausibel.")

    confirm = input("\nVerknüpfung speichern [Y/n]? ").strip().lower()
    if confirm not in ("y", ""):
        print("❎ Abgebrochen.")
        return

    # Links anlegen
    for vid, vnum, vname, vamount, vdate in vouchers:
        cur.execute(
            f"""
            INSERT INTO {link_table} ({id_field}, transaction_id, link_type, amount)
            VALUES (%s, %s, 'payment', %s)
            ON CONFLICT DO NOTHING;
            """,
            (vid, tid, vamount),
        )
        cur.execute(f"UPDATE {voucher_table} SET status='paid' WHERE id=%s;", (vid,))

    conn.commit()
    print(f"\n✅ {len(vouchers)} Beleg(e) mit Transaktion {tid} verknüpft und als 'paid' markiert.\n")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Verknüpft mehrere Belege mit einer Transaktion.")
    ap.add_argument("--txid", required=True, type=int, help="ID der Transaktion")
    ap.add_argument("--vouchers", required=True, help="Kommaseparierte Liste von Beleg-IDs")
    ap.add_argument("--direction", choices=["incoming", "outgoing"], default="incoming", help="Richtung (incoming|outgoing)")
    args = ap.parse_args()

    ids = [int(x.strip()) for x in args.vouchers.split(",") if x.strip()]
    link_vouchers_to_transaction(args.txid, ids, args.direction)
