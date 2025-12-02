#!/usr/bin/env python3
"""
link_transactions_to_voucher.py
-------------------------------
Verknüpft mehrere Banktransaktionen mit einem einzelnen Eingangs- oder Ausgangsbeleg.

Beispiele:
    ./python/link_transactions_to_voucher.py --voucher-id 42 --tx 6011,6012,6013
    ./python/link_transactions_to_voucher.py --voucher-id 37 --direction outgoing --tx 7021,7022
"""

import argparse
import sys
from decimal import Decimal
from db import get_connection
from bhl_utils import (
    row_get,
    safe_decimal,
    safe_float,
    format_date,
    unwrap_amount,
    unwrap_date,
    unwrap_text,
)


def link_transactions_to_voucher(voucher_id: int, tx_ids: list[int], direction: str):
    conn = get_connection()
    cur = conn.cursor()

    # Tabelle je nach Richtung wählen
    if direction == "outgoing":
        voucher_table = "outgoing_vouchers"
        link_table = "outgoing_links"
        id_field = "outgoing_id"
    else:
        voucher_table = "vouchers"
        link_table = "voucher_links"
        id_field = "voucher_id"

    # Beleg abrufen
    cur.execute(
        f"""
        SELECT id, voucher_number, partner_name, total_amount, voucher_date
          FROM {voucher_table}
         WHERE id = %s;
        """,
        (voucher_id,),
    )
    row = cur.fetchone()
    if not row:
        print(f"❌ Beleg {voucher_id} nicht gefunden.")
        sys.exit(1)

    vid = row_get(row, "id", 0)
    vnum = row_get(row, "voucher_number", 1)
    vname = row_get(row, "partner_name", 2)
    vamount = row_get(row, "total_amount", 3)
    vdate = row_get(row, "voucher_date", 4)

    vamount_dec = safe_decimal(vamount)
    vamount_float = safe_float(vamount)

    print(
        f"\n📄 Beleg {vid}: {vnum or '-'} | {vname} | "
        f"{format_date(vdate)} | {vamount_float:.2f} EUR\n"
    )

    # Transaktionen abrufen
    cur.execute(
        """
        SELECT id, booking_date, amount, counterpart_name, purpose
          FROM transactions
         WHERE id = ANY(%s)
         ORDER BY booking_date;
        """,
        (tx_ids,),
    )
    tx_rows = cur.fetchall()

    if not tx_rows:
        print("❌ Keine der angegebenen Transaktions-IDs gefunden.")
        conn.close()
        return

    # Transaktionen anzeigen und Summe bilden
    print("💳 Zugeordnete Transaktionen:")
    total_sum = Decimal("0.00")

    for row in tx_rows:
        tid = row_get(row, "id", 0)
        tdate = row_get(row, "booking_date", 1)
        tamount = row_get(row, "amount", 2)
        tname = row_get(row, "counterpart_name", 3)
        purpose = row_get(row, "purpose", 4)

        amount_dec = safe_decimal(tamount)
        total_sum += amount_dec

        # Darstellung für Ausgabe
        try:
            tid_int = int(tid)
        except (TypeError, ValueError):
            tid_int = tid

        date_str = format_date(tdate)
        amount_float = safe_float(tamount)

        print(f"    {tid_int:4} | {date_str} | {amount_float:10.2f} EUR | {tname or '-'}")
        if purpose:
            print(f"         Zweck: {str(purpose)[:100]}")

    diff = abs(abs(vamount_dec) - abs(total_sum))

    print(f"\n📄 Belegbetrag:     {vamount_float:.2f} EUR")
    print(f"💰 Zahlungen Summe: {safe_float(total_sum):.2f} EUR")
    print(f"➡  Differenz:        {safe_float(diff):.2f} EUR")

    if diff > Decimal("1.00"):
        print("⚠️  Differenz größer als 1.00 EUR – bitte prüfen!")
    else:
        print("✅ Betrag plausibel.")

    confirm = input("\nVerknüpfung speichern [Y/n]? ").strip().lower()
    if confirm not in ("y", ""):
        print("❎ Abgebrochen.")
        conn.close()
        return

    # Links anlegen
    for row in tx_rows:
        tid = row_get(row, "id", 0)
        tamount = row_get(row, "amount", 2)
        amount_dec = safe_decimal(tamount)

        cur.execute(
            f"""
            INSERT INTO {link_table} ({id_field}, transaction_id, link_type, amount)
            VALUES (%s, %s, 'payment', %s)
            ON CONFLICT DO NOTHING;
            """,
            (vid, tid, amount_dec),
        )

    # Status aktualisieren
    cur.execute(f"UPDATE {voucher_table} SET status='paid' WHERE id = %s;", (vid,))

    conn.commit()
    print(f"\n✅ {len(tx_rows)} Transaktion(en) mit Beleg {vid} verknüpft und als 'paid' markiert.\n")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Verknüpft mehrere Transaktionen mit einem Beleg.")
    ap.add_argument("--voucher-id", required=True, type=int, help="ID des Belegs")
    ap.add_argument(
        "--tx",
        required=True,
        help="Kommaseparierte Liste von Transaktions-IDs (z.B. 5958,6020,6076)",
    )
    ap.add_argument(
        "--direction",
        choices=["incoming", "outgoing"],
        default="incoming",
        help="Richtung (incoming|outgoing)",
    )
    args = ap.parse_args()

    tx_ids = [int(x.strip()) for x in args.tx.split(",") if x.strip()]
    link_transactions_to_voucher(args.voucher_id, tx_ids, args.direction)
