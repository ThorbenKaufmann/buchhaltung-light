#!/usr/bin/env python3
"""
report_ist_integrity.py

Prüft IST-relevante Zahlungen eines Monats auf:
- Unverknüpfte Zahlungen
- Fehlende booking_lines
- Über-/Unterverlinkung
"""

import argparse
from datetime import datetime, timedelta
from decimal import Decimal
from db import get_connection


def parse_month(month_str):
    start = datetime.strptime(month_str, "%Y-%m")
    end = (start + timedelta(days=32)).replace(day=1)
    return start.date(), end.date()


def main(month):
    start_date, end_date = parse_month(month)

    conn = get_connection()
    cur = conn.cursor()

    print(f"\n🔎 IST-Integritätsprüfung {start_date} bis {end_date}\n")

    # ------------------------------------------------------------
    # 1. Alle Zahlungen im Zeitraum
    # ------------------------------------------------------------
    cur.execute("""
        SELECT t.id,
               COALESCE(t.value_date, t.booking_date) AS tx_date,
               t.amount
        FROM transactions t
        WHERE COALESCE(t.value_date, t.booking_date) >= %s
          AND COALESCE(t.value_date, t.booking_date) < %s
        ORDER BY tx_date;
    """, (start_date, end_date))

    transactions = cur.fetchall()

    if not transactions:
        print("Keine Transaktionen im Zeitraum.")
        return

    for tx_id, tx_date, tx_amount in transactions:
        print("-" * 80)
        print(f"Tx {tx_id} | {tx_date} | {tx_amount:.2f} EUR")

        # --------------------------------------------------------
        # Prüfe Link
        # --------------------------------------------------------
        cur.execute("""
            SELECT 'incoming' AS typ,
                   vl.voucher_id AS vid,
                   vl.amount,
                   v.total_amount
            FROM voucher_links vl
            JOIN vouchers v ON v.id = vl.voucher_id
            WHERE vl.transaction_id = %s

            UNION ALL

            SELECT 'outgoing' AS typ,
                   ol.outgoing_id AS vid,
                   ol.amount,
                   ov.total_amount
            FROM outgoing_links ol
            JOIN outgoing_vouchers ov ON ov.id = ol.outgoing_id
            WHERE ol.transaction_id = %s
        """, (tx_id, tx_id))

        links = cur.fetchall()

        if not links:
            print("⚠️  Keine Verknüpfung zu Beleg!")
            continue

        for typ, vid, link_amount, total_amount in links:
            print(f"   → {typ} Beleg {vid} | Link {link_amount:.2f} / Total {total_amount:.2f}")

            # ----------------------------------------------------
            # Prüfe booking_lines
            # ----------------------------------------------------
            if typ == "incoming":
                cur.execute("SELECT COUNT(*) FROM booking_lines WHERE voucher_id=%s", (vid,))
            else:
                cur.execute("SELECT COUNT(*) FROM booking_lines WHERE outgoing_id=%s", (vid,))

            bl_count = cur.fetchone()[0]

            if bl_count == 0:
                print("     ❌ Keine booking_lines vorhanden!")
            else:
                print(f"     ✔ {bl_count} booking_lines gefunden")

            # ----------------------------------------------------
            # Prüfe Überzahlung
            # ----------------------------------------------------
            if typ == "incoming":
                cur.execute("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM voucher_links
                    WHERE voucher_id = %s
                """, (vid,))
            else:
                cur.execute("""
                    SELECT COALESCE(SUM(amount), 0)
                    FROM outgoing_links
                    WHERE outgoing_id = %s
                """, (vid,))

            total_linked = cur.fetchone()[0] or Decimal("0.00")

            tolerance = Decimal("0.01")

            if abs(total_linked) > abs(total_amount) + tolerance:
                print("     ❌ Überverlinkung!")
            elif abs(total_linked) < abs(total_amount) - tolerance:
                print("     ⚠️ Unterverlinkung (Teilzahlung?)")
            else:
                print("     ✔ Verlinkung plausibel")

    print("\n✔ IST-Integritätsprüfung abgeschlossen.\n")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="IST-Integritätsprüfung")
    ap.add_argument("--month", required=True)
    args = ap.parse_args()

    main(args.month)