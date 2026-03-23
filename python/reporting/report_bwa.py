#!/usr/bin/env python3
"""
report_bwa.py

Einfache BWA (Betriebswirtschaftliche Auswertung)

Zeigt pro Monat:
    Umsatz | Aufwand | Ergebnis
"""

import argparse
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection


def run_bwa(year):
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()

    print(f"\n📊 BWA {year}\n")

    cur.execute("""
        SELECT
            DATE_TRUNC('month', u.voucher_date) AS monat,
            a.is_revenue,
            a.is_expense,
            SUM(bl.amount) AS summe
        FROM booking_lines_new bl
        JOIN unified_voucher_lines u
          ON u.id = bl.source_id
         AND u.type = bl.source_type
        JOIN skr03_accounts a
          ON a.id = bl.account_skr
        WHERE DATE_PART('year', u.voucher_date) = %s
        GROUP BY monat, a.is_revenue, a.is_expense
        ORDER BY monat;
    """, (year,))

    rows = cur.fetchall()

    # ------------------------------------------------------------
    # Struktur aufbauen
    # ------------------------------------------------------------
    data = {}

    for r in rows:
        monat = r["monat"].strftime("%Y-%m")

        if monat not in data:
            data[monat] = {
                "revenue": 0.0,
                "expense": 0.0
            }

        summe = float(r["summe"] or 0)

        if r["is_revenue"]:
            data[monat]["revenue"] += summe
        elif r["is_expense"]:
            data[monat]["expense"] += summe

    # ------------------------------------------------------------
    # Ausgabe
    # ------------------------------------------------------------
    print("Monat    Umsatz      Aufwand     Ergebnis")
    print("--------------------------------------------------")

    total_rev = 0.0
    total_exp = 0.0

    for monat in sorted(data.keys()):
        rev = data[monat]["revenue"]
        exp = data[monat]["expense"]
        res = rev + exp

        total_rev += rev
        total_exp += exp

        print(f"{monat}  {rev:10.2f}  {exp:10.2f}  {res:10.2f}")

    print("--------------------------------------------------")

    print(f"SUMME   {total_rev:10.2f}  {total_exp:10.2f}  {(total_rev + total_exp):10.2f}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="BWA (Monatsübersicht)")
    ap.add_argument("--year", required=True, type=int)
    args = ap.parse_args()

    run_bwa(args.year)