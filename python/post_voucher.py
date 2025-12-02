#!/usr/bin/env python3
"""post_voucher.py
Bucht die Buchungszeilen eines einzelnen Belegs aus vouchers/voucher_lines
bzw. outgoing_vouchers/outgoing_lines in die booking_lines-Tabelle.

Verwendung:
  ./python/post_voucher.py --direction incoming --voucher-id 7
  ./python/post_voucher.py --direction outgoing --voucher-id 12
  ./python/post_voucher.py --direction incoming --voucher-id 7 --dry-run
"""

import argparse
from db import get_connection


def post_single_voucher(direction: str, voucher_id: int, dry_run: bool = False):
    if direction not in ("incoming", "outgoing"):
        raise ValueError("direction muss 'incoming' oder 'outgoing' sein.")

    conn = get_connection()
    cur = conn.cursor()

    if direction == "incoming":
        cur.execute(
            """SELECT id, voucher_number, partner_name, voucher_date
                 FROM vouchers
                WHERE id = %s""",
            (voucher_id,),
        )
        row = cur.fetchone()
        if not row:
            print(f"❌ Eingangsbeleg mit ID {voucher_id} nicht gefunden.")
            cur.close()
            conn.close()
            return

        vid, vnum, partner, vdate = row

        # Prüfen, ob bereits Buchungen existieren
        cur.execute(
            """SELECT COUNT(*) FROM booking_lines
                   WHERE direction = 'incoming' AND voucher_id = %s""",
            (vid,),
        )
        already, = cur.fetchone()
        if already:
            print(f"⚠ Beleg {vnum or vid} hat bereits {already} Buchungszeile(n) in booking_lines.")
            if dry_run:
                print("   (Dry-Run: es werden keine weiteren Buchungen simuliert.)")
            else:
                print("   Vorgang wird abgebrochen, um Doppelbuchungen zu vermeiden.")
            cur.close()
            conn.close()
            return

        print(f"📄 Eingangsbeleg {vnum or vid} ({partner or 'unbekannt'}), {vdate}")
        cur.execute(
            """SELECT id, account_skr, description, net_amount, tax_rate, tax_amount
                 FROM voucher_lines
                WHERE voucher_id = %s
                ORDER BY id""",
            (vid,),
        )
        lines = cur.fetchall()
        if not lines:
            print("⚠ Keine Zeilen in voucher_lines gefunden – nichts zu buchen.")
        for lid, acc, desc, net, rate, tax in lines:
            net = net or 0
            tax = tax or 0
            gross = net + tax
            print(f"   → incoming  {acc:<8}  {gross:10.2f} EUR  ({desc or ''})")
            if not dry_run:
                cur.execute(
                    """INSERT INTO booking_lines
                               (direction, voucher_id, outgoing_id,
                                account_skr, description,
                                net_amount, tax_rate, tax_amount, gross_amount)
                        VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s)""",
                    ("incoming", vid, acc, desc, net, rate, tax, gross),
                )

    else:  # outgoing
        cur.execute(
            """SELECT id, voucher_number, customer_name, invoice_date
                 FROM outgoing_vouchers
                WHERE id = %s""",
            (voucher_id,),
        )
        row = cur.fetchone()
        if not row:
            print(f"❌ Ausgangsbeleg mit ID {voucher_id} nicht gefunden.")
            cur.close()
            conn.close()
            return

        oid, onum, customer, odate = row

        cur.execute(
            """SELECT COUNT(*) FROM booking_lines
                   WHERE direction = 'outgoing' AND outgoing_id = %s""",
            (oid,),
        )
        already, = cur.fetchone()
        if already:
            print(f"⚠ Beleg {onum or oid} hat bereits {already} Buchungszeile(n) in booking_lines.")
            if dry_run:
                print("   (Dry-Run: es werden keine weiteren Buchungen simuliert.)")
            else:
                print("   Vorgang wird abgebrochen, um Doppelbuchungen zu vermeiden.")
            cur.close()
            conn.close()
            return

        print(f"📄 Ausgangsbeleg {onum or oid} ({customer or 'unbekannt'}), {odate}")
        cur.execute(
            """SELECT id, account_skr, description, net_amount, tax_rate, tax_amount
                 FROM outgoing_lines
                WHERE outgoing_id = %s
                ORDER BY id""",
            (oid,),
        )
        lines = cur.fetchall()
        if not lines:
            print("⚠ Keine Zeilen in outgoing_lines gefunden – nichts zu buchen.")
        for lid, acc, desc, net, rate, tax in lines:
            net = net or 0
            tax = tax or 0
            gross = net + tax
            print(f"   → outgoing  {acc:<8}  {gross:10.2f} EUR  ({desc or ''})")
            if not dry_run:
                cur.execute(
                    """INSERT INTO booking_lines
                               (direction, voucher_id, outgoing_id,
                                account_skr, description,
                                net_amount, tax_rate, tax_amount, gross_amount)
                        VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, %s)""",
                    ("outgoing", oid, acc, desc, net, rate, tax, gross),
                )

    if dry_run:
        print("\n🧪 Dry-Run aktiviert – es wurden keine Buchungen geschrieben.")
        conn.rollback()
    else:
        conn.commit()
        print("\n✅ Beleg wurde in booking_lines gebucht.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Einen Beleg in booking_lines buchen.")
    ap.add_argument(
        "--direction",
        required=True,
        choices=["incoming", "outgoing"],
        help="Richtung des Belegs",
    )
    ap.add_argument(
        "--voucher-id",
        required=True,
        type=int,
        help="ID des Belegs in vouchers/outgoing_vouchers",
    )
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur anzeigen, keine Buchungen schreiben.",
    )
    args = ap.parse_args()

    post_single_voucher(
        direction=args.direction,
        voucher_id=args.voucher_id,
        dry_run=args.dry_run,
    )
