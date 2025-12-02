#!/usr/bin/env python3
"""post_all_unbooked_vouchers.py
Überträgt alle vorhandenen Buchungszeilen aus vouchers/voucher_lines
bzw. outgoing_vouchers/outgoing_lines in die booking_lines-Tabelle,
sofern sie dort noch nicht vorhanden sind.

Variante B: booking_lines ist das führende „Hauptbuch“, die *_lines
sind die Belegzeilen.

Verwendung:
  ./python/post_all_unbooked_vouchers.py                    # alles buchen
  ./python/post_all_unbooked_vouchers.py --month 2025-09    # nur einen Monat
  ./python/post_all_unbooked_vouchers.py --dry-run          # nur anzeigen
"""

from datetime import datetime, timedelta
import argparse
from db import get_connection


def parse_month(month_str):
    """Wandelt 'YYYY-MM' in (start_date, end_date) um."""
    mdate = datetime.strptime(month_str, "%Y-%m")
    start = mdate.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)
    return start.date(), end.date()


def post_all_unbooked_vouchers(month=None, dry_run=False):
    conn = get_connection()
    cur = conn.cursor()

    if month:
        start_date, end_date = parse_month(month)
        print(f"📅 Zeitraum: {start_date} bis {end_date}")
        date_filter_in = "AND v.voucher_date >= %s AND v.voucher_date < %s"
        date_filter_out = "AND o.voucher_date >= %s AND o.voucher_date < %s"
        date_params = (start_date, end_date)
    else:
        date_filter_in = ""
        date_filter_out = ""
        date_params = None

    # ----------------- Eingangsbelege -----------------
    print("\n📥 Suche ungebuchte Eingangsbelege…")

    query_in = f"""
        SELECT v.id, v.voucher_number, v.partner_name, v.voucher_date
          FROM vouchers v
         WHERE EXISTS (SELECT 1 FROM voucher_lines l WHERE l.voucher_id = v.id)
           AND NOT EXISTS (
                 SELECT 1 FROM booking_lines b
                  WHERE b.direction = 'incoming'
                    AND b.voucher_id = v.id
           )
           {date_filter_in}
         ORDER BY v.voucher_date, v.id
    """
    if date_params:
        cur.execute(query_in, date_params)
    else:
        cur.execute(query_in)
    incoming_vouchers = cur.fetchall()

    # ----------------- Ausgangsbelege -----------------
    print("\n📤 Suche ungebuchte Ausgangsbelege…")

    query_out = f"""
        SELECT o.id, o.voucher_number, o.partner_name, o.voucher_date
          FROM outgoing_vouchers o
         WHERE EXISTS (SELECT 1 FROM outgoing_lines l WHERE l.outgoing_id = o.id)
           AND NOT EXISTS (
                 SELECT 1 FROM booking_lines b
                  WHERE b.direction = 'outgoing'
                    AND b.outgoing_id = o.id
           )
           {date_filter_out}
         ORDER BY o.voucher_date, o.id
    """
    if date_params:
        cur.execute(query_out, date_params)
    else:
        cur.execute(query_out)
    outgoing_vouchers = cur.fetchall()

    if not incoming_vouchers and not outgoing_vouchers:
        print("✅ Keine ungebuchten Belege gefunden.")
        cur.close()
        conn.close()
        return

    # ----------------- Eingangsbelege buchen -----------------
    for vid, vnum, partner, vdate in incoming_vouchers:
        header = f"📄 Eingangsbeleg {vnum or vid} ({partner or 'unbekannt'}), {vdate}"
        print("\n" + header)

        cur.execute(
            """
            SELECT id, account_skr, description, net_amount, tax_rate, tax_amount
              FROM voucher_lines
             WHERE voucher_id = %s
             ORDER BY id
            """,
            (vid,),
        )
        lines = cur.fetchall()
        for lid, acc, desc, net, rate, tax in lines:
            net = net or 0
            tax = tax or 0
            gross = net + tax
            print(f"   → incoming  {acc:<8}  {gross:10.2f} EUR  ({desc or ''})")
            if not dry_run:
                cur.execute(
                    """
                    INSERT INTO booking_lines
                        (direction, voucher_id, outgoing_id,
                         account_skr, description,
                         net_amount, tax_rate, tax_amount, gross_amount)
                    VALUES (%s, %s, NULL, %s, %s, %s, %s, %s, %s)
                    """,
                    ("incoming", vid, acc, desc, net, rate, tax, gross),
                )

    # ----------------- Ausgangsbelege buchen -----------------
    for oid, onum, customer, odate in outgoing_vouchers:
        header = f"📄 Ausgangsbeleg {onum or oid} ({customer or 'unbekannt'}), {odate}"
        print("\n" + header)

        cur.execute(
            """
            SELECT id, account_skr, description, net_amount, tax_rate, tax_amount
              FROM outgoing_lines
             WHERE outgoing_id = %s
             ORDER BY id
            """,
            (oid,),
        )
        lines = cur.fetchall()
        for lid, acc, desc, net, rate, tax in lines:
            net = net or 0
            tax = tax or 0
            gross = net + tax
            print(f"   → outgoing  {acc:<8}  {gross:10.2f} EUR  ({desc or ''})")
            if not dry_run:
                cur.execute(
                    """
                    INSERT INTO booking_lines
                        (direction, voucher_id, outgoing_id,
                         account_skr, description,
                         net_amount, tax_rate, tax_amount, gross_amount)
                    VALUES (%s, NULL, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    ("outgoing", oid, acc, desc, net, rate, tax, gross),
                )

    if dry_run:
        print("\n🧪 Dry-Run aktiviert – es wurden keine Buchungen geschrieben.")
        conn.rollback()
    else:
        conn.commit()
        print("\n✅ Alle ungebuchten Belege wurden in booking_lines übertragen.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(
        description="Belegzeilen aus vouchers/outgoing_vouchers in booking_lines buchen."
    )
    ap.add_argument("--month", help="Optional: nur Belege eines Monats (YYYY-MM) buchen.")
    ap.add_argument(
        "--dry-run",
        action="store_true",
        help="Nur anzeigen, keine Buchungen schreiben.",
    )
    args = ap.parse_args()

    post_all_unbooked_vouchers(month=args.month, dry_run=args.dry_run)
