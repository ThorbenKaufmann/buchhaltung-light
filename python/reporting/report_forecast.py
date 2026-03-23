#!/usr/bin/env python3
"""
report_forecast.py

Forecast auf Basis:
- historischem Cashflow
- Burn Rate
- einfache lineare Projektion
"""

import argparse
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection


def run_forecast(year, months=6):
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()

    print(f"\n🔮 FORECAST ab Ende {year}\n")

    # ------------------------------------------------------------
    # Cashflow holen
    # ------------------------------------------------------------
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

    # Monatsnetto berechnen
    monthly_net = []
    for r in rows:
        net = float(r["inflow"] or 0) + float(r["outflow"] or 0)
        monthly_net.append(net)

    if not monthly_net:
        print("Keine Daten.")
        return

    # ------------------------------------------------------------
    # Durchschnitt (wichtig!)
    # ------------------------------------------------------------
    avg = sum(monthly_net) / len(monthly_net)

    # konservativer: nur negative Monate
    negatives = [x for x in monthly_net if x < 0]
    burn = sum(negatives) / len(negatives) if negatives else 0

    # ------------------------------------------------------------
    # Kontostand aktuell
    # ------------------------------------------------------------
    
    cur.execute("""
        SELECT SUM(amount) AS balance
        FROM transactions
        WHERE COALESCE(value_date, booking_date) <= %s
        AND is_private IS NOT TRUE
        AND is_internal IS NOT TRUE
    """, (f"{year}-12-31",))
    

    balance = float(cur.fetchone()["balance"] or 0)

    print(f"💰 Startkontostand: {balance:10.2f}")
    print(f"📊 Durchschnitt:    {avg:10.2f} / Monat")
    print(f"🔥 Burn (negativ):  {burn:10.2f} / Monat\n")

    # ------------------------------------------------------------
    # Forecast berechnen
    # ------------------------------------------------------------
    print("Monat        konservativ     neutral")

    current = datetime(year, 12, 1)

    bal_conservative = balance
    bal_neutral = balance

    for i in range(1, months + 1):
        current = (current + timedelta(days=32)).replace(day=1)

        # konservativ: nur negative Monate
        bal_conservative += burn

        # neutral: Durchschnitt
        bal_neutral += avg

        print(
            f"{current.strftime('%Y-%m')}   "
            f"{bal_conservative:12.2f}   "
            f"{bal_neutral:12.2f}"
        )

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Cashflow Forecast")
    ap.add_argument("--year", required=True, type=int)
    ap.add_argument("--months", type=int, default=6)
    args = ap.parse_args()

    run_forecast(args.year, args.months)