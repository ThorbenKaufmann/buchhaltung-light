#!/usr/bin/env python3
"""
report_account_summary.py

Kontensummen pro Monat basierend auf booking_lines_legacy + vouchers.

Zeigt:
    Konto → Summe (Netto)
"""

import argparse
from datetime import datetime, timedelta
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection


def run_account_summary(month):
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()

    # Zeitraum
    mdate = datetime.strptime(month, "%Y-%m")
    start = mdate.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)

    print(f"\n📆 Kontensummen {start:%Y-%m-%d} bis {end:%Y-%m-%d}\n")

    # ------------------------------------------------------------
    # Daten holen
    # ------------------------------------------------------------
    cur.execute("""
        SELECT
            bl.account_skr,
            a.name,
            a.is_expense,
            a.is_revenue,
            SUM(bl.net_amount) AS summe
        FROM booking_lines_legacy bl
        LEFT JOIN vouchers v ON v.id = bl.voucher_id
        LEFT JOIN outgoing_vouchers ov ON ov.id = bl.outgoing_id
        JOIN skr03_accounts a ON a.id = bl.account_skr
        WHERE COALESCE(v.voucher_date, ov.voucher_date) >= %s
          AND COALESCE(v.voucher_date, ov.voucher_date) < %s
        GROUP BY bl.account_skr, a.name, a.is_expense, a.is_revenue
        ORDER BY bl.account_skr;
    """, (start, end))

    rows = cur.fetchall()

    if not rows:
        print("Keine Daten.")
        return

    # ------------------------------------------------------------
    # Ausgabe Tabelle
    # ------------------------------------------------------------
    print("Konto      Bezeichnung                         Summe €    Typ")
    print("----------------------------------------------------------------")

    total_revenue = 0.0
    total_expense = 0.0
    total_ust = 0.0
    total_vorsteuer = 0.0

    for r in rows:
        konto = r["account_skr"]
        name = r["name"]
        summe = float(r["summe"] or 0)

        is_rev = r["is_revenue"]
        is_exp = r["is_expense"]

        # Typ bestimmen
        if is_rev:
            typ = "REV"
            total_revenue += summe
        elif is_exp:
            typ = "EXP"
            total_expense += summe
        elif konto.startswith("17"):
            typ = "USt"
            total_ust += summe
        elif konto.startswith("15"):
            typ = "VSt"
            total_vorsteuer += summe
        else:
            typ = "—"

        print(f"{konto:<10} {name[:30]:30} {summe:10.2f}    {typ}")

    print("----------------------------------------------------------------")

    # ------------------------------------------------------------
    # GuV
    # ------------------------------------------------------------
    print("\n📊 GuV:")
    print(f"Erlöse:   {total_revenue:10.2f}")
    print(f"Aufwand:  {total_expense:10.2f}")
    print(f"Ergebnis: {(total_revenue + total_expense):10.2f}")

    # ------------------------------------------------------------
    # Umsatzsteuer
    # ------------------------------------------------------------
    print("\n🧾 Umsatzsteuer:")
    print(f"USt:        {total_ust:10.2f}")
    print(f"Vorsteuer:  {total_vorsteuer:10.2f}")
    print(f"Zahllast:   {(total_ust + total_vorsteuer):10.2f}")

    cur.close()
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="Kontensummen pro Monat")
    ap.add_argument("--month", required=True)
    args = ap.parse_args()

    run_account_summary(args.month)


if __name__ == "__main__":
    main()