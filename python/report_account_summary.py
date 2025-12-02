#!/usr/bin/env python3
"""
report_account_summary.py — Monats-Kontosummenbericht
Summiert alle booking_lines je Konto für einen Monat:

    Konto → Netto, Steuer, Brutto

Brutto = Netto + Steuer
"""

import argparse
from datetime import datetime, timedelta
from db import get_connection
from bhl_utils import row_get, safe_float


def run_account_summary(month):

    # ------------------------------------------------------------------
    # Zeitraum bestimmen
    # ------------------------------------------------------------------
    mdate = datetime.strptime(month, "%Y-%m")
    start = mdate.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)

    print(f"📆 Kontensummen {start:%Y-%m-%d} bis {end:%Y-%m-%d}\n")

    conn = get_connection()
    cur = conn.cursor()

    # ------------------------------------------------------------------
    # Buchungslinien abrufen (booking_lines ist die Wahrheit)
    # ------------------------------------------------------------------
    cur.execute("""
        SELECT account_skr, net_amount, tax_amount
          FROM booking_lines
         WHERE created_at BETWEEN %s AND %s
         ORDER BY account_skr;
    """, (start, end))

    rows = cur.fetchall()

    # ------------------------------------------------------------------
    # Summen pro Konto bilden
    # ------------------------------------------------------------------
    account_totals = {}  # konto → {'net': x, 'tax': y}

    for row in rows:
        account = row_get(row, "account_skr", 0)
        net     = safe_float(row_get(row, "net_amount", 1))
        tax     = safe_float(row_get(row, "tax_amount", 2))

        if not account:
            # Sicherheit, darf nicht passieren
            continue

        if account not in account_totals:
            account_totals[account] = {"net": 0.0, "tax": 0.0}

        account_totals[account]["net"] += net
        account_totals[account]["tax"] += tax

    # ------------------------------------------------------------------
    # Ausgabe
    # ------------------------------------------------------------------
    print("Konto      Bezeichnung                         Netto €     Steuer €     Brutto €")
    print("--------------------------------------------------------------------------------")

    # Wenn wir später ein eigenes Konten-Register haben, ergänzen wir die Namen hier.
    def konto_name(k):
        return "(SKR03 Konto)"

    total_net = 0.0
    total_tax = 0.0

    for konto in sorted(account_totals):
        net = account_totals[konto]["net"]
        tax = account_totals[konto]["tax"]
        brutto = net + tax

        total_net += net
        total_tax += tax

        print(f"{konto:<10} {konto_name(konto):30s} "
              f"{net:10.2f} {tax:12.2f} {brutto:12.2f}")

    print("--------------------------------------------------------------------------------")
    print(f"{'SUMME':<42s} {total_net:10.2f} {total_tax:12.2f} {(total_net + total_tax):12.2f}")

    cur.close()
    conn.close()


# ----------------------------------------------------------------------
# CLI
# ----------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser(description="Monatliche Summen pro SKR03-Konto.")
    ap.add_argument("--month", default=datetime.today().strftime("%Y-%m"),
                    help="Monat im Format YYYY-MM (Standard: aktueller Monat)")
    args = ap.parse_args()

    run_account_summary(args.month)


if __name__ == "__main__":
    main()
