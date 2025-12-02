#!/usr/bin/env python3
"""
add_booking_position.py
-----------------------
Fügt eine neue Buchungsposition zu einem Beleg hinzu (nicht direkt ins Hauptbuch).

Beispiel:
  ./python/add_booking_position.py --direction incoming --voucher-id 314 \
      --account 4909 --gross 1117.28 --tax 19 --desc "Apple Cloud 2024"
"""

from decimal import Decimal, ROUND_HALF_UP
from db import get_connection
import argparse
import sys


def add_position(direction, voucher_id, account, net, gross, tax_rate, desc):
    """Fügt eine Position zu voucher_lines / outgoing_lines hinzu, mit Brutto-/Netto-Option."""
    conn = get_connection()
    cur = conn.cursor()

    # Tabelle je nach Richtung bestimmen
    if direction == "incoming":
        table = "voucher_lines"
        id_field = "voucher_id"
        voucher_table = "vouchers"
    elif direction == "outgoing":
        table = "outgoing_lines"
        id_field = "outgoing_id"
        voucher_table = "outgoing_vouchers"
    else:
        raise ValueError("direction muss 'incoming' oder 'outgoing' sein")

    # Steuerberechnung
    tax_rate_dec = Decimal(str(tax_rate)) / Decimal("100")

    if gross is not None and gross > 0:
        gross_dec = Decimal(str(gross))
        net_dec = (gross_dec / (Decimal("1") + tax_rate_dec)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax_amount = (gross_dec - net_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        net_dec = Decimal(str(net))
        tax_amount = (net_dec * tax_rate_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        gross_dec = net_dec + tax_amount

    # Plausibilitätsprüfung gegen Belegsumme
    cur.execute(f"SELECT total_amount FROM {voucher_table} WHERE id=%s;", (voucher_id,))
    row = cur.fetchone()
    if row:
        voucher_total = Decimal(str(row[0]))
        diff = abs(voucher_total - gross_dec)
        if diff > Decimal("1.00"):
            print(f"⚠️  Warnung: Belegsumme {voucher_total:.2f} EUR weicht um {diff:.2f} EUR vom Positionsbetrag ab.")
    else:
        print(f"⚠️  Beleg-ID {voucher_id} nicht gefunden.")
        conn.close()
        sys.exit(1)

    # Einfügen der Position
    cur.execute(
        f"""
        INSERT INTO {table}
            ({id_field}, account_skr, description, net_amount, tax_rate, tax_amount)
        VALUES (%s, %s, %s, %s, %s, %s)
        RETURNING id;
        """,
        (voucher_id, account, desc, net_dec, tax_rate, tax_amount),
    )

    pid = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()

    print(f"✅ Position #{pid} in {table} hinzugefügt → Konto {account}, {gross_dec:.2f} € brutto "
          f"({net_dec:.2f} € netto, {tax_amount:.2f} € Steuer).")


def main():
    ap = argparse.ArgumentParser(description="Fügt eine Buchungsposition zu einem Beleg hinzu (nicht direkt ins Hauptbuch).")
    ap.add_argument("--direction", required=True, choices=["incoming", "outgoing"], help="Richtung des Belegs")
    ap.add_argument("--voucher-id", required=True, type=int, help="Beleg-ID")
    ap.add_argument("--account", required=True, type=str, help="SKR03-Konto")
    ap.add_argument("--net", type=float, default=0.0, help="Nettobetrag in EUR (optional, wenn --gross angegeben ist)")
    ap.add_argument("--gross", type=float, default=0.0, help="Bruttobetrag in EUR (automatische Umrechnung in Netto)")
    ap.add_argument("--tax", type=float, default=19.0, help="Steuersatz in Prozent (z. B. 19 oder 0)")
    ap.add_argument("--desc", type=str, default="", help="Beschreibung / Buchungstext")
    args = ap.parse_args()

    add_position(args.direction, args.voucher_id, args.account, args.net, args.gross, args.tax, args.desc)


if __name__ == "__main__":
    main()
