#!/usr/bin/env python3
"""
report_unlinked_transactions.py
Zeigt Transaktionen ohne zugehörigen Beleg-Link – optional gefiltert nach Monat.

Berücksichtigt Flags:
  - is_private
  - is_internal
  - is_cyclic

Standardverhalten:
  • private, interne und zyklische Transaktionen werden ausgeblendet.
Optionen:
  --include-private   → auch private Transaktionen anzeigen
  --include-internal  → auch interne Umbuchungen anzeigen
  --include-cyclic    → auch zyklische Transaktionen (Daueraufträge) anzeigen
"""

import argparse
from datetime import datetime, timedelta
from db import get_connection


def report_unlinked_transactions(month=None,
                                 include_private=False,
                                 include_internal=False,
                                 include_cyclic=False):
    conn = get_connection()
    cur = conn.cursor()

    if month:
        mdate = datetime.strptime(month, "%Y-%m")
        start = mdate.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        print(f"📅 Zeitraum: {start:%Y-%m-%d} bis {end:%Y-%m-%d}\n")
    else:
        start = datetime(1970, 1, 1)
        end = datetime(2100, 1, 1)

    sql = """
        SELECT t.id, t.booking_date, t.amount,
               t.counterpart_name, t.purpose,
               t.is_private, t.is_internal, t.is_cyclic
          FROM transactions t
          LEFT JOIN voucher_links v ON v.transaction_id = t.id
          LEFT JOIN outgoing_links o ON o.transaction_id = t.id
         WHERE v.id IS NULL
           AND o.id IS NULL
           AND t.booking_date BETWEEN %s AND %s
    """
    params = [start, end]

    # Flags berücksichtigen
    if not include_private:
        sql += " AND (t.is_private IS FALSE OR t.is_private IS NULL)"
    if not include_internal:
        sql += " AND (t.is_internal IS FALSE OR t.is_internal IS NULL)"
    if not include_cyclic:
        sql += " AND (t.is_cyclic IS FALSE OR t.is_cyclic IS NULL)"

    sql += " ORDER BY t.booking_date;"

    cur.execute(sql, params)
    rows = cur.fetchall()

    if not rows:
        print("✅ Keine unverknüpften (relevanten) Transaktionen im angegebenen Zeitraum.\n")
    else:
        print("💶 Unverknüpfte Transaktionen:\n")
        for tid, bdate, amount, name, purpose, is_priv, is_int, is_cyc in rows:
            amt = f"{amount:8.2f} EUR"
            cname = (name or "-")[:35]
            snippet = (purpose or "").replace("\n", " ")[:70]

            flags = []
            if is_priv:
                flags.append("PRIV")
            if is_int:
                flags.append("INT")
            if is_cyc:
                flags.append("CYC")

            flag_str = f" [{' '.join(flags)}]" if flags else ""
            print(f"  TxID {tid:6d} | {bdate:%Y-%m-%d} | {amt:>12s} | "
                  f"{cname:35s} | {snippet}{flag_str}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Listet Transaktionen ohne Beleg auf.")
    ap.add_argument("--month", help="YYYY-MM (optional)")
    ap.add_argument("--include-private", action="store_true",
                    help="Auch private Transaktionen ausgeben")
    ap.add_argument("--include-internal", action="store_true",
                    help="Auch interne Umbuchungen ausgeben")
    ap.add_argument("--include-cyclic", action="store_true",
                    help="Auch zyklische Transaktionen (Daueraufträge) ausgeben")

    args = ap.parse_args()
    report_unlinked_transactions(
        args.month,
        include_private=args.include_private,
        include_internal=args.include_internal,
        include_cyclic=args.include_cyclic,
    )
