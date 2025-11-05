#!/usr/bin/env python3
"""
mark_private.py
Markiert Transaktionen als privat (oder zeigt sie nur an mit --dryrun).

Verwendung:
    python3 python/mark_private.py --month 2024-01 --purpose "Amazon" --dryrun
    python3 python/mark_private.py --id 6123
"""

import argparse
from datetime import datetime, timedelta
from db import get_connection


def mark_private(month=None, purpose=None, counterpart=None, tx_id=None, dryrun=False):
    conn = get_connection()
    cur = conn.cursor()

    # Zeitraum bestimmen
    if month:
        mdate = datetime.strptime(month, "%Y-%m")
        start = mdate.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        print(f"📅 Zeitraum: {start:%Y-%m-%d} bis {end:%Y-%m-%d}")
    else:
        start = datetime(1970, 1, 1)
        end = datetime(2100, 1, 1)

    # Filter aufbauen
    conds = ["booking_date BETWEEN %s AND %s"]
    params = [start, end]

    if purpose:
        conds.append("purpose ILIKE %s")
        params.append(f"%{purpose}%")
    if counterpart:
        conds.append("counterpart_name ILIKE %s")
        params.append(f"%{counterpart}%")
    if tx_id:
        conds.append("id = %s")
        params.append(tx_id)

    where_clause = " AND ".join(conds)

    cur.execute(
        f"""
        SELECT id, booking_date, amount, counterpart_name, purpose, is_private, category
          FROM transactions
         WHERE {where_clause}
         ORDER BY booking_date;
        """,
        params,
    )
    rows = cur.fetchall()

    if not rows:
        print("ℹ️  Keine passenden Transaktionen gefunden.")
        conn.close()
        return

    print(f"\n{len(rows)} Treffer:\n")
    for row in rows:
        tid, bdate, amount, name, purpose, is_private, category = row
        print(f"  TxID {tid:6d} | {bdate:%Y-%m-%d} | {amount:8.2f} EUR | {(name or '-')[:35]:35s} | {category or '-'}")
        if purpose:
            print(f"      {purpose[:80]}")

    if dryrun:
        print("\n🚫  Dryrun-Modus: keine Änderungen vorgenommen.")
    else:
        confirm = input("\nDiese Transaktionen als privat markieren? [y/N] ").strip().lower()
        if confirm != "y":
            print("Abgebrochen.")
            conn.close()
            return

        for row in rows:
            tid = row[0]
            cur.execute(
                """
                UPDATE transactions
                   SET is_private = TRUE,
                       category = 'privat'
                 WHERE id = %s;
                """,
                (tid,),
            )

        conn.commit()
        print(f"\n✅  {len(rows)} Transaktion(en) als privat markiert.")

    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Markiert Transaktionen als privat.")
    ap.add_argument("--month", help="YYYY-MM (optional)")
    ap.add_argument("--purpose", help="Textsuche im Verwendungszweck (case-insensitive)")
    ap.add_argument("--counterpart", help="Textsuche im Gegenparteinamen (case-insensitive)")
    ap.add_argument("--id", type=int, help="Transaktions-ID")
    ap.add_argument("--dryrun", action="store_true", help="Nur anzeigen, keine Änderung vornehmen")
    args = ap.parse_args()

    mark_private(
        month=args.month,
        purpose=args.purpose,
        counterpart=args.counterpart,
        tx_id=args.id,
        dryrun=args.dryrun,
    )
