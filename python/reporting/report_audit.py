#!/usr/bin/env python3

import argparse
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection


def parse_year(year: int):
    start = datetime(year, 1, 1).date()
    end = datetime(year + 1, 1, 1).date()
    return start, end


def print_section(title):
    print("\n" + "=" * 72)
    print(title)
    print("=" * 72)

def get_sort_clause(sort_mode):
    if sort_mode == "amount":
        return "t.amount DESC"
    elif sort_mode == "abs_amount":
        return "ABS(t.amount) DESC"
    else:
        return "t.booking_date ASC"


def run_audit(year: int, order_clause):
    start_date, end_date = parse_year(year)

    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()

    print(f"\n📊 Audit für Jahr {year}")
    print(f"Zeitraum: {start_date} bis {end_date}")

    # ------------------------------------------------------------
    # 1. Unkontierte Eingangsbelege
    # ------------------------------------------------------------
    print_section("❗ Unkontierte Eingangsbelege (keine voucher_lines)")

    cur.execute("""
        SELECT v.id, v.voucher_date, v.partner_name, v.total_amount
        FROM vouchers v
        LEFT JOIN voucher_lines vl ON vl.voucher_id = v.id
        WHERE vl.id IS NULL
          AND v.voucher_date >= %s
          AND v.voucher_date < %s
        ORDER BY v.voucher_date;
    """, (start_date, end_date))

    rows = cur.fetchall()
    for r in rows:
        print(f"{r['voucher_date']} | {r['id']:>5} | {r['total_amount']:>10.2f} | {r['partner_name'] or '-':<25}")
    print(f"→ {len(rows)} Belege ohne Kontierung")

    # ------------------------------------------------------------
    # 2. Unkontierte Ausgangsbelege
    # ------------------------------------------------------------
    print_section("❗ Unkontierte Ausgangsbelege (keine outgoing_lines)")

    cur.execute("""
        SELECT ov.id, ov.voucher_date, ov.partner_name, ov.total_amount
        FROM outgoing_vouchers ov
        LEFT JOIN outgoing_lines ol ON ol.outgoing_id = ov.id
        WHERE ol.id IS NULL
          AND ov.voucher_date >= %s
          AND ov.voucher_date < %s
        ORDER BY ov.voucher_date;
    """, (start_date, end_date))

    rows = cur.fetchall()
    for r in rows:
        print(f"{r['voucher_date']} | {r['id']:>5} | {r['partner_name'] or '-':<25} | {r['total_amount']:>10.2f}")
    print(f"→ {len(rows)} Belege ohne Kontierung")

    # ------------------------------------------------------------
    # 3. Zahlungen ohne Beleg
    # ------------------------------------------------------------
    print_section("💰 Zahlungen ohne Beleg (kein voucher_link)")

    

    query = f"""
        SELECT t.id, t.booking_date, t.amount, t.purpose
        FROM transactions t
        LEFT JOIN voucher_links vl ON vl.transaction_id = t.id
        WHERE vl.id IS NULL
        AND NOT t.is_private
        AND NOT t.is_internal
        AND COALESCE(t.booking_date, t.value_date) >= %s
        AND COALESCE(t.booking_date, t.value_date) < %s
        ORDER BY {order_clause};
    """

    cur.execute(query, (start_date, end_date))

    rows = cur.fetchall()
    for r in rows:
        print(f"{r['booking_date']} | {r['id']:>5} | {r['amount']:>10.2f} | {r['purpose'][:180] if r['purpose'] else '-'}")
    print(f"→ {len(rows)} unzugeordnete Zahlungen")

    # ------------------------------------------------------------
    # 4. Zahlungsabweichungen
    # ------------------------------------------------------------
    print_section("⚠️  Zahlungsabweichungen (Beleg ≠ Zahlung)")

    cur.execute("""
        SELECT v.id,
        v.voucher_date,
        v.total_amount,
        SUM(ABS(t.amount)) AS paid
        FROM vouchers v
        JOIN voucher_links vl ON vl.voucher_id = v.id
        JOIN transactions t ON t.id = vl.transaction_id
        WHERE v.voucher_date >= %s
        AND v.voucher_date < %s
        GROUP BY v.id, v.voucher_date, v.total_amount
        HAVING ABS(v.total_amount - SUM(ABS(t.amount))) > 1.00
        ORDER BY v.voucher_date;
    """, (start_date, end_date))

    rows = cur.fetchall()
    for r in rows:
        diff = r["total_amount"] - (r["paid"] or 0)
        print(f"{r['voucher_date']} | {r['id']:>5} | Soll: {r['total_amount']:>10.2f} | Ist: {r['paid']:>10.2f} | Δ {diff:>8.2f}")
    print(f"→ {len(rows)} Abweichungen")

    cur.close()
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="Audit-Report zur Identifikation fehlender Buchungen")
    ap.add_argument("--year", type=int, required=True, help="Jahr (z.B. 2024)")
    ap.add_argument(
        "--sort",
        choices=["date", "amount", "abs_amount"],
        default="date",
        help="Sortierung der Zahlungen"
    )

    args = ap.parse_args()
    order_clause = get_sort_clause(args.sort)

    run_audit(args.year, order_clause)


if __name__ == "__main__":
    main()