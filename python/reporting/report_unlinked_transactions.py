#!/usr/bin/env python3
"""
report_unlinked_transactions.py – Version 3
Robuste Ausgabe aller Transaktionen im Zeitraum inkl. Belegstatus,
mit Filterung:
  --include-private
  --include-internal
  --include-cyclic
"""

import argparse
from datetime import datetime, timedelta
from db import get_connection
from bhl_utils import row_get, safe_float, format_date


def report_unlinked_transactions(month,
                                 include_private,
                                 include_internal,
                                 include_cyclic,
                                 include_linked):


    conn = get_connection()
    cur = conn.cursor()

    # Zeitraum bestimmen
    mdate = datetime.strptime(month, "%Y-%m")
    start = mdate.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)

    print(f"📅 Zeitraum: {start:%Y-%m-%d} bis {end:%Y-%m-%d}\n")

    # ------------------------------------------------------------------
    # EINHEITLICHES SELECT mit allen Flags
    # ------------------------------------------------------------------
    sql = """
        SELECT t.id, t.booking_date, t.amount, t.counterpart_name, t.purpose,
               t.is_private, t.is_internal, t.is_cyclic,
               COALESCE(vl.voucher_id, ol.outgoing_id) AS linked_id
          FROM transactions t
          LEFT JOIN voucher_links vl   ON vl.transaction_id  = t.id
          LEFT JOIN outgoing_links ol  ON ol.transaction_id = t.id
         WHERE t.booking_date BETWEEN %s AND %s
    """

    params = [start, end]

    # Filter anwenden
    if not include_private:
        sql += " AND (t.is_private IS FALSE OR t.is_private IS NULL)"
    if not include_internal:
        sql += " AND (t.is_internal IS FALSE OR t.is_internal IS NULL)"
    if not include_cyclic:
        sql += " AND (t.is_cyclic IS FALSE OR t.is_cyclic IS NULL)"
    if not include_linked:
        sql += " AND (vl.voucher_id IS NULL AND ol.outgoing_id IS NULL)"


    sql += " ORDER BY t.booking_date;"

    cur.execute(sql, params)
    rows = cur.fetchall()

    if not rows:
        print("✅ Keine Transaktionen nach Filterung.\n")
        return

    print("💶 Transaktionen mit Belegstatus:\n")

    for row in rows:
        tid     = row_get(row, "id",              0)
        tdate   = row_get(row, "booking_date",    1)
        amount  = row_get(row, "amount",          2)
        tname   = row_get(row, "counterpart_name",3)
        purpose = row_get(row, "purpose",         4)
        is_pr   = row_get(row, "is_private",      5)
        is_in   = row_get(row, "is_internal",     6)
        is_cy   = row_get(row, "is_cyclic",       7)
        linked  = row_get(row, "linked_id",       8)

        # Formate robust
        amount_f = safe_float(amount)
        tdate_s  = format_date(tdate)

        flags = ""
        if is_pr:
            flags += " (privat)"
        if is_in:
            flags += " (intern)"
        if is_cy:
            flags += " (zykl.)"

        status = "✅ LINKED" if linked else "⚠️ UNLINKED"

        print("-" * 180)
        print(
            f"TxID {tid:5} | {tdate_s} | {amount_f:10.2f} EUR | "
            f"{(tname or '-')[:35]:<35} | {(purpose or '-')[:80]:<80} | "
            f"{status}{flags}"
        )

        # ----------------------------------------------------------
        # Verknüpften Beleg anzeigen
        # ----------------------------------------------------------
        if linked:
            cur.execute(
                "SELECT voucher_number, partner_name, total_amount, voucher_date "
                "FROM vouchers WHERE id=%s", (linked,)
            )
            v = cur.fetchone()

            if not v:
                # Versuch in outgoing_vouchers
                cur.execute(
                    "SELECT voucher_number, partner_name, total_amount, voucher_date "
                    "FROM outgoing_vouchers WHERE id=%s", (linked,)
                )
                v = cur.fetchone()

            if v:
                vnum = row_get(v, "voucher_number", 0)
                vnam = row_get(v, "partner_name",   1)
                vamt = safe_float(row_get(v, "total_amount", 2))
                vdat = format_date(row_get(v, "voucher_date", 3))

                print(
                    " " * 80 +
                    f"📄 Beleg #{linked}: {vnum} ({vnam}) {vamt:.2f} EUR am {vdat}"
                )
            else:
                print(" " * 80 + f"❌ Beleg {linked} nicht gefunden!")

    print("-" * 180)

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Listet Transaktionen und Belegstatus (linked/unlinked) auf.")

    ap.add_argument("--month", required=True, help="Monat YYYY-MM")
    ap.add_argument("--include-private", action="store_true", help="Private Transaktionen anzeigen")
    ap.add_argument("--include-internal", action="store_true", help="Interne Transaktionen anzeigen")
    ap.add_argument("--include-cyclic", action="store_true", help="Zyklische Transaktionen anzeigen")
    ap.add_argument("--include-linked", action="store_true", help="Auch Transaktionen mit verknüpften Belegen anzeigen")


    args = ap.parse_args()

    report_unlinked_transactions(
    args.month,
    include_private=args.include_private,
    include_internal=args.include_internal,
    include_cyclic=args.include_cyclic,
    include_linked=args.include_linked,
)

