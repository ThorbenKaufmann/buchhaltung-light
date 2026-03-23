#!/usr/bin/env python3

import argparse
from datetime import datetime, timedelta
from db import get_connection


def parse_month(month_str: str):
    start = datetime.strptime(month_str, "%Y-%m")
    end = (start + timedelta(days=32)).replace(day=1)
    return start.date(), end.date()


def generate_from_voucher_line(line):
    net = line["net_amount"] or 0
    tax = line["tax_amount"] or 0
    gross = net + tax

    return [
        ("incoming", line["id"], line["account_skr"], net),
        ("incoming", line["id"], "1576", tax),
        ("incoming", line["id"], "1600", -gross),
    ]


def generate_from_outgoing_line(line):
    net = line["net_amount"] or 0
    tax = line["tax_amount"] or 0
    gross = net + tax

    return [
        ("outgoing", line["id"], "1200", gross),
        ("outgoing", line["id"], line["account_skr"], -net),
        ("outgoing", line["id"], "1776", -tax),
    ]


def rebuild(month: str, dry_run: bool):
    start_date, end_date = parse_month(month)

    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()

    print(f"🔧 Rebuild booking_lines_new for {start_date} → {end_date}")
    if dry_run:
        print("🧪 DRY RUN MODE (no changes will be written)")
    print()

    # --- Incoming löschen ---
    delete_incoming = """
        DELETE FROM booking_lines_new
        WHERE source_type = 'incoming'
          AND source_id IN (
            SELECT vl.id
            FROM voucher_lines vl
            JOIN vouchers v ON vl.voucher_id = v.id
            WHERE v.voucher_date >= %s
              AND v.voucher_date < %s
        )
    """

    # --- Outgoing löschen ---
    delete_outgoing = """
        DELETE FROM booking_lines_new
        WHERE source_type = 'outgoing'
          AND source_id IN (
            SELECT ol.id
            FROM outgoing_lines ol
            JOIN outgoing_vouchers ov ON ol.outgoing_id = ov.id
            WHERE ov.voucher_date >= %s
              AND ov.voucher_date < %s
        )
    """

    if not dry_run:
        cur.execute(delete_incoming, (start_date, end_date))
        cur.execute(delete_outgoing, (start_date, end_date))
        conn.commit()

    # --- Incoming laden ---
    cur.execute("""
        SELECT vl.*
        FROM voucher_lines vl
        JOIN vouchers v ON vl.voucher_id = v.id
        WHERE v.voucher_date >= %s
          AND v.voucher_date < %s
        ORDER BY vl.id
    """, (start_date, end_date))

    incoming_lines = cur.fetchall()

    # --- Outgoing laden ---
    cur.execute("""
        SELECT ol.*
        FROM outgoing_lines ol
        JOIN outgoing_vouchers ov ON ol.outgoing_id = ov.id
        WHERE ov.voucher_date >= %s
          AND ov.voucher_date < %s
        ORDER BY ol.id
    """, (start_date, end_date))

    outgoing_lines = cur.fetchall()

    insert_sql = """
        INSERT INTO booking_lines_new (source_type, source_id, account_skr, amount)
        VALUES (%s, %s, %s, %s)
    """

    total = 0

    # --- Incoming verarbeiten ---
    for line in incoming_lines:
        bookings = generate_from_voucher_line(line)
        for b in bookings:
            if dry_run:
                print("IN ", b)
            else:
                cur.execute(insert_sql, b)
            total += 1

    # --- Outgoing verarbeiten ---
    for line in outgoing_lines:
        bookings = generate_from_outgoing_line(line)
        for b in bookings:
            if dry_run:
                print("OUT", b)
            else:
                cur.execute(insert_sql, b)
            total += 1

    if not dry_run:
        conn.commit()

    print(f"\n✅ Done. Generated {total} booking lines.")

    cur.close()
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="Rebuild booking_lines_new from voucher_lines")
    ap.add_argument("--month", required=True, help="Monat YYYY-MM")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts schreiben")

    args = ap.parse_args()

    rebuild(args.month, args.dry_run)


if __name__ == "__main__":
    main()