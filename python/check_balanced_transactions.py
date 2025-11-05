#!/usr/bin/env python3
"""
check_balanced_transactions.py
Prüft, ob Transaktionen mit verknüpften Belegen in Summe ausgeglichen sind.
Zeigt Differenzen und Mehrfachzuordnungen an.
"""

from db import get_connection
from decimal import Decimal, ROUND_HALF_UP

def check_balanced_transactions(tolerance=Decimal("0.5")):
    conn = get_connection()
    cur = conn.cursor()

    print("🔎 Prüfe Sammelzahlungen und Transaktionsverknüpfungen …\n")

    cur.execute("""
        SELECT
            t.id AS transaction_id,
            t.booking_date,
            t.amount AS tx_amount,
            t.counterpart_name,
            COALESCE(SUM(vl.amount),0) AS linked_amount,
            COUNT(vl.voucher_id) AS voucher_count
        FROM transactions t
        LEFT JOIN voucher_links vl ON vl.transaction_id = t.id
        GROUP BY t.id, t.booking_date, t.amount, t.counterpart_name
        HAVING COUNT(vl.voucher_id) > 0
        ORDER BY t.booking_date;
    """)

    rows = cur.fetchall()
    if not rows:
        print("✅ Keine Transaktionen mit Belegverknüpfung gefunden.\n")
        return

    balanced = []
    unbalanced = []

    for tid, tdate, tx_amount, name, linked_amount, vcount in rows:
        diff = abs(abs(Decimal(tx_amount)) - abs(Decimal(linked_amount)))
        is_balanced = diff <= tolerance
        entry = (tid, tdate, tx_amount, linked_amount, diff, name, vcount)
        (balanced if is_balanced else unbalanced).append(entry)

    print(f"Gefundene Transaktionen mit Verknüpfungen: {len(rows)}\n")
    print(f"✅ Ausgeglichene Zahlungen: {len(balanced)}")
    print(f"⚠️  Unausgeglichene Zahlungen: {len(unbalanced)}\n")

    if unbalanced:
        print("───────────────────────────────────────────────────────────────")
        print("⚠️  Unausgeglichene Transaktionen (Differenz > ±{:.2f} €):\n".format(tolerance))
        for tid, tdate, tx_amount, linked_amount, diff, name, vcount in unbalanced:
            print(f"TxID {tid:6d} | {tdate} | {tx_amount:8.2f} € | Belege: {linked_amount:8.2f} € | Δ={diff:.2f} € | {vcount} Beleg(e) | {name}")
        print()

    if balanced:
        print("───────────────────────────────────────────────────────────────")
        print("✅ Ausgeglichene Sammeltransaktionen:\n")
        for tid, tdate, tx_amount, linked_amount, diff, name, vcount in balanced:
            print(f"TxID {tid:6d} | {tdate} | {tx_amount:8.2f} € | {vcount} Beleg(e) | {name}")

    cur.close()
    conn.close()
    print("\n🔚 Prüfung abgeschlossen.\n")


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Prüft Transaktionen mit mehreren Belegen auf Summenkonsistenz.")
    ap.add_argument("--tolerance", type=float, default=0.5, help="zulässige Differenz in Euro (Standard 0.5)")
    args = ap.parse_args()
    check_balanced_transactions(tolerance=Decimal(str(args.tolerance)))
