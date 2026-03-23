#!/usr/bin/env python3
"""
report_cashflow.py

Cashflow-Auswertung (IST-basiert)

Zeigt:
    Einzahlungen | Auszahlungen | Netto
"""

import argparse
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection


def run_cashflow(year):
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()

    print(f"\n💰 Cashflow {year}\n")

    cur.execute("""
        SELECT
            DATE_TRUNC('month', COALESCE(value_date, booking_date)) AS monat,
            SUM(CASE WHEN amount > 0 THEN amount ELSE 0 END) AS inflow,
            SUM(CASE WHEN amount < 0 THEN amount ELSE 0 END) AS outflow
        FROM transactions
        WHERE DATE_PART('year', COALESCE(value_date, booking_date)) = %s
          AND is_private IS NOT TRUE
          AND is_internal IS NOT TRUE
        GROUP BY monat
        ORDER BY monat;
    """, (year,))

    rows = cur.fetchall()

    print("Monat    Einzahlungen   Auszahlungen   Netto")
    print("--------------------------------------------------")

    total_in = 0.0
    total_out = 0.0

    for r in rows:
        monat = r["monat"].strftime("%Y-%m")
        inflow = float(r["inflow"] or 0)
        outflow = float(r["outflow"] or 0)
        net = inflow + outflow

        total_in += inflow
        total_out += outflow

        print(f"{monat}  {inflow:12.2f}  {outflow:12.2f}  {net:10.2f}")

    print("--------------------------------------------------")
    print(f"SUMME   {total_in:12.2f}  {total_out:12.2f}  {(total_in + total_out):10.2f}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Cashflow-Report")
    ap.add_argument("--year", required=True, type=int)
    args = ap.parse_args()

    run_cashflow(args.year)