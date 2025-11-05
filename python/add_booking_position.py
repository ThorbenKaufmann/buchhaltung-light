#!/usr/bin/env python3
"""
add_booking_position.py
Ermöglicht das Hinzufügen, Anzeigen und optionale Summen-Validieren
von Buchungspositionen (Teilbeträgen) zu einem Beleg.

Beispiel:
    python3 python/add_booking_position.py --direction incoming --voucher-id 42 \
        --account 4950 --net 950 --tax 19 --desc "Werkzeuglieferung"

    python3 python/add_booking_position.py --direction incoming --list --voucher-id 42
"""

import argparse
from decimal import Decimal, ROUND_HALF_UP
from db import get_connection


def list_positions(voucher_id, direction):
    """Zeigt alle vorhandenen Positionen eines Belegs an."""
    conn = get_connection()
    cur = conn.cursor()
    id_field = "voucher_id" if direction == "incoming" else "outgoing_id"

    cur.execute(f"""
        SELECT id, account_skr, description, net_amount, tax_rate, tax_amount, gross_amount, receipt_status
          FROM booking_lines
         WHERE {id_field} = %s AND direction = %s
         ORDER BY id;
    """, (voucher_id, direction))
    rows = cur.fetchall()

    if not rows:
        print(f"ℹ️  Keine Positionen für Beleg {voucher_id} ({direction}) gefunden.")
    else:
        print(f"📄 Positionen für Beleg {voucher_id} ({direction}):\n")
        print(f"{'ID':>4s} {'Konto':>6s} {'Netto':>10s} {'MwSt%':>6s} {'MwSt€':>10s} {'Brutto':>10s}   Beschreibung")
        print("-" * 72)
        for r in rows:
            rid, acc, desc, net, rate, tax, gross, status = r
            print(f"{rid:4d} {acc:6} {net:10.2f} {rate:6.2f} {tax:10.2f} {gross:10.2f}   {desc or ''} [{status}]")
        print("-" * 72)
    cur.close()
    conn.close()


def add_position(direction, voucher_id, account, net, tax_rate, desc):
    """Fügt eine neue Buchungsposition hinzu."""
    conn = get_connection()
    cur = conn.cursor()

    id_field = "voucher_id" if direction == "incoming" else "outgoing_id"

    net_dec = Decimal(str(net))
    tax_rate_dec = Decimal(str(tax_rate)) / Decimal("100")
    tax_amount = (net_dec * tax_rate_dec).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    gross_amount = (net_dec + tax_amount).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    cur.execute(f"""
        INSERT INTO booking_lines
            (direction, {id_field}, account_skr, description,
             net_amount, tax_rate, tax_amount, gross_amount, receipt_status)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,'complete')
        RETURNING id;
    """, (direction, voucher_id, account, desc, net_dec, tax_rate_dec * 100, tax_amount, gross_amount))
    bid = cur.fetchone()[0]
    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Position #{bid} hinzugefügt → Konto {account}, {gross_amount:.2f} € brutto.")


def validate_sum(direction, voucher_id):
    """Prüft, ob Summe der Positionen zur Belegsumme passt."""
    conn = get_connection()
    cur = conn.cursor()
    id_field = "voucher_id" if direction == "incoming" else "outgoing_id"
    v_table = "vouchers" if direction == "incoming" else "outgoing_vouchers"

    cur.execute(f"SELECT total_amount FROM {v_table} WHERE id=%s;", (voucher_id,))
    row = cur.fetchone()
    if not row:
        print(f"❌ Beleg {voucher_id} nicht gefunden.")
        conn.close()
        return
    total = Decimal(row[0] or 0)

    cur.execute(f"SELECT COALESCE(SUM(gross_amount),0) FROM booking_lines WHERE {id_field}=%s;", (voucher_id,))
    subtotal = cur.fetchone()[0] or Decimal(0)

    diff = subtotal - total
    print(f"💰 Belegsumme: {total:.2f} € | Positionen: {subtotal:.2f} € | Differenz: {diff:.2f} €")
    if abs(diff) < Decimal("0.02"):
        print("✅ Summen stimmen überein.")
    else:
        print("⚠️  Abweichung! Bitte prüfen.")
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="Verwaltet Buchungspositionen pro Beleg.")
    ap.add_argument("--direction", choices=["incoming", "outgoing"], required=True, help="incoming|outgoing")
    ap.add_argument("--voucher-id", type=int, required=True, help="Beleg-ID")

    group = ap.add_mutually_exclusive_group(required=True)
    group.add_argument("--list", action="store_true", help="Listet vorhandene Positionen auf")
    group.add_argument("--add", action="store_true", help="Fügt eine neue Position hinzu")
    group.add_argument("--validate", action="store_true", help="Prüft Summengleichheit")

    ap.add_argument("--account", type=int, help="SKR03-Konto (z. B. 4950)")
    ap.add_argument("--net", type=float, help="Nettobetrag der Position")
    ap.add_argument("--tax", type=float, default=19.0, help="Steuersatz in Prozent")
    ap.add_argument("--desc", default="", help="Beschreibung der Position")

    args = ap.parse_args()

    if args.list:
        list_positions(args.voucher_id, args.direction)
    elif args.add:
        if not (args.account and args.net):
            print("❌ Für --add sind --account und --net erforderlich.")
            return
        add_position(args.direction, args.voucher_id, args.account, args.net, args.tax, args.desc)
    elif args.validate:
        validate_sum(args.direction, args.voucher_id)


if __name__ == "__main__":
    main()
