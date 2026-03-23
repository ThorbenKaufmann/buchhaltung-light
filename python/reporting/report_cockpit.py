#!/usr/bin/env python3
"""
report_cockpit.py

Dein Finanz-Cockpit:
- Cashflow monatlich
- Kumuliert
- aktueller Stand
- einfache Risikoabschätzung
"""

import argparse
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection


def run_cockpit(year):
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()

    print(f"\n🚀 FINANZ-COCKPIT {year}\n")

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

    print("Monat    Inflow     Outflow     Netto     Kumuliert")
    print("----------------------------------------------------------")

    cumulative = 0.0
    worst = 0.0

    for r in rows:
        monat = r["monat"].strftime("%Y-%m")
        inflow = float(r["inflow"] or 0)
        outflow = float(r["outflow"] or 0)
        net = inflow + outflow

        cumulative += net
        worst = min(worst, cumulative)

        print(f"{monat}  {inflow:10.0f}  {outflow:10.0f}  {net:10.0f}  {cumulative:10.0f}")

    print("----------------------------------------------------------")

    # ------------------------------------------------------------
    # Kontostand aktuell
    # ------------------------------------------------------------
    cur.execute("""
        SELECT SUM(amount) AS balance
        FROM transactions
        WHERE is_private IS NOT TRUE
          AND is_internal IS NOT TRUE
    """)

    balance = float(cur.fetchone()["balance"] or 0)

    # ------------------------------------------------------------
    # Burn Rate (Durchschnitt negative Monate)
    # ------------------------------------------------------------
    negative_months = [float(r["inflow"] or 0) + float(r["outflow"] or 0)
                       for r in rows if (float(r["inflow"] or 0) + float(r["outflow"] or 0)) < 0]

    burn = sum(negative_months) / len(negative_months) if negative_months else 0

    print(f"\n💰 Kontostand:     {balance:10.2f} EUR")
    print(f"🔥 Burn Rate:      {burn:10.2f} EUR/Monat")

    # ------------------------------------------------------------
    # Risikoindikator
    # ------------------------------------------------------------
    if burn < 0:
        runway = balance / abs(burn) if burn != 0 else 999
        print(f"⏳ Runway:         {runway:10.1f} Monate")
    else:
        print("⏳ Runway:         ∞ (kein negativer Trend)")

    print(f"⚠️  Max Drawdown:  {worst:10.2f} EUR")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Finanz-Cockpit")
    ap.add_argument("--year", required=True, type=int)
    args = ap.parse_args()

    run_cockpit(args.year)