#!/usr/bin/env python3
"""
report_ist_integrity.py (NEU)

Prüft IST-Zahlungen eines Monats auf:

🟢 vollständig verlinkt
🟡 Teilzahlung
🔴 Fehler (keine Verknüpfung / Überzahlung / Vorzeichenproblem)

KEINE Nutzung von booking_lines mehr!
"""

import argparse
from datetime import datetime, timedelta
from decimal import Decimal
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection


def parse_month(month_str):
    start = datetime.strptime(month_str, "%Y-%m")
    end = (start + timedelta(days=32)).replace(day=1)
    return start.date(), end.date()


def main(month):
    start_date, end_date = parse_month(month)

    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()

    print(f"\n🔎 IST-Integritätsprüfung {start_date} bis {end_date}\n")

    # ------------------------------------------------------------
    # Alle Zahlungen im Zeitraum
    # ------------------------------------------------------------
    cur.execute("""
        SELECT
        t.id,
        COALESCE(t.value_date, t.booking_date) AS tx_date,
        t.amount,
        t.counterpart_name,
        t.purpose
        FROM transactions t
        WHERE COALESCE(t.value_date, t.booking_date) >= %s
        AND COALESCE(t.value_date, t.booking_date) < %s
        AND t.is_private IS NOT TRUE
        AND t.is_internal IS NOT TRUE
        AND t.is_cyclic IS NOT TRUE
        ORDER BY tx_date;
    """, (start_date, end_date))

    transactions = cur.fetchall()

    if not transactions:
        print("Keine Transaktionen im Zeitraum.")
        return

    summary = {"ok": 0, "warn": 0, "error": 0}

    for tx in transactions:
        tx_id = tx["id"]
        tx_date = tx["tx_date"]
        tx_amount = Decimal(str(tx["amount"] or 0))

        print("-" * 100)
        print(f"Tx {tx_id:6} | {tx_date} | {tx_amount:10.2f} EUR")

        # --------------------------------------------------------
        # Links holen
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

        # --------------------------------------------------------
        # 🔴 KEINE VERKNÜPFUNG
        # --------------------------------------------------------
        if not links:
            print("🔴 KEIN BELEG VERKNÜPFT")
            summary["error"] += 1
            continue

        tx_status = "ok"

        for link in links:
            typ = link["typ"]
            vid = link["vid"]
            link_amount = Decimal(str(link["amount"] or 0))
            total_amount = Decimal(str(link["total_amount"] or 0))

            print(f"   → {typ} {vid} | Link {link_amount:.2f} / Total {total_amount:.2f}")

            # ----------------------------------------------------
            # Gesamtverlinkung berechnen
            # ----------------------------------------------------
            if typ == "incoming":
                cur.execute("""
                    SELECT COALESCE(SUM(amount), 0) AS sum
                    FROM voucher_links
                    WHERE voucher_id = %s
                """, (vid,))
            else:
                cur.execute("""
                    SELECT COALESCE(SUM(amount), 0) AS sum
                    FROM outgoing_links
                    WHERE outgoing_id = %s
                """, (vid,))

            row = cur.fetchone()
            total_linked = Decimal(str(row["sum"] or 0))
            tolerance = Decimal("0.01")

            # ----------------------------------------------------
            # STATUS LOGIK
            # ----------------------------------------------------
            if abs(total_linked) > abs(total_amount) + tolerance:
                print("     🔴 Überverlinkung")
                tx_status = "error"

            elif abs(total_linked) < abs(total_amount) - tolerance:
                print("     🟡 Teilzahlung")
                if tx_status != "error":
                    tx_status = "warn"

            else:
                print("     🟢 Vollständig")

            # ----------------------------------------------------
            # Vorzeichenprüfung
            # ----------------------------------------------------
            if (tx_amount > 0 and typ == "incoming") or (tx_amount < 0 and typ == "outgoing"):
                print("     🔴 Vorzeichen ungewöhnlich!")
                tx_status = "error"

        # --------------------------------------------------------
        # Summary zählen
        # --------------------------------------------------------
        if tx_status == "ok":
            summary["ok"] += 1
        elif tx_status == "warn":
            summary["warn"] += 1
        else:
            summary["error"] += 1

    # ------------------------------------------------------------
    # SUMMARY
    # ------------------------------------------------------------
    print("\n" + "=" * 100)
    print("📊 Zusammenfassung:")
    print(f"🟢 OK:        {summary['ok']}")
    print(f"🟡 Teilzahlung: {summary['warn']}")
    print(f"🔴 Fehler:    {summary['error']}")
    print("=" * 100)

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="IST-Integritätsprüfung (neu)")
    ap.add_argument("--month", required=True)
    args = ap.parse_args()

    main(args.month)