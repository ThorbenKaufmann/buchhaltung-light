#!/usr/bin/env python3
"""
report_transaction_overview.py
Zeigt alle Transaktionen mit zugeordneten Belegen und Konten.

Optionen:
  --month YYYY-MM      → Zeitraum eines Monats
  --year YYYY          → gesamtes Jahr
  --open-only          → nur unvollständige (fehlender Beleg oder Kontierung)
  --non-private        → blendet private Transaktionen aus
  --export csv|md      → exportiert die Ausgabe als CSV oder Markdown
"""

import argparse
import csv
from datetime import datetime, timedelta
from db import get_connection
from pathlib import Path


def report_transaction_overview(month: str | None, year: str | None, open_only: bool, non_private: bool, export: str | None):
    conn = get_connection()
    cur = conn.cursor()

    # Zeitraum bestimmen
    if year:
        start = datetime.strptime(year, "%Y")
        end = start.replace(month=12, day=31) + timedelta(days=1)
        period_label = f"{year}"
    elif month:
        mdate = datetime.strptime(month, "%Y-%m")
        start = mdate.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        period_label = month
    else:
        print("❌ Bitte --month oder --year angeben.")
        return

    print(f"📅 Zeitraum: {start.date()} bis {end.date()}\n")

    sql = """
        SELECT id, booking_date, amount, counterpart_name, purpose, is_private
          FROM transactions
         WHERE booking_date BETWEEN %s AND %s
    """
    params = [start, end]
    if non_private:
        sql += " AND is_private IS NOT TRUE"
    sql += " ORDER BY booking_date;"

    cur.execute(sql, params)
    transactions = cur.fetchall()

    if not transactions:
        print("⚠️  Keine Transaktionen im angegebenen Zeitraum gefunden.")
        return

    export_rows = []
    total, shown = len(transactions), 0

    for tid, tdate, tamount, tname, purpose, is_private in transactions:
        # Belege abrufen
        cur.execute("""
            SELECT v.id, v.voucher_number, v.partner_name, v.total_amount, v.status,
                   v.voucher_date AS doc_date
              FROM voucher_links vl
              JOIN vouchers v ON v.id = vl.voucher_id
             WHERE vl.transaction_id = %s
            UNION ALL
            SELECT o.id, o.voucher_number, o.customer_name, o.total_amount, o.status,
                   o.invoice_date AS doc_date
              FROM outgoing_links ol
              JOIN outgoing_vouchers o ON o.id = ol.outgoing_id
             WHERE ol.transaction_id = %s;
        """, (tid, tid))
        vouchers = cur.fetchall()

        # Buchungslinien abrufen
        cur.execute("""
            SELECT account_skr, tax_type, receipt_status, gross_amount
              FROM booking_lines
             WHERE description = %s OR description = CAST(%s AS text);
        """, (str(tid), tid))
        accounts = cur.fetchall()

        has_voucher = bool(vouchers)
        has_account = bool(accounts)

        if open_only and has_voucher and has_account:
            continue

        shown += 1
        priv_flag = "privat" if is_private else ""

        print("=" * 100)
        print(f"💳 TxID {tid:5d} | {tdate} | {tamount:8.2f} EUR | {tname or '-'} {priv_flag}")
        print(f"    Zweck: {purpose[:100] if purpose else '-'}")

        if not vouchers:
            print("    ⚠️  Kein Beleg verknüpft.")
        else:
            for vid, vnum, vname, vamount, vstatus, vdate in vouchers:
                print(f"    📄 Beleg {vid:5d} | {vnum or '-':<15} | {vname[:35] if vname else '-':35s} "
                      f"| {vamount:8.2f} EUR | {vdate or '-'} | Status: {vstatus}")

        if not accounts:
            print("    ⚠️  Keine Kontierung (booking_lines) gefunden.")
        else:
            for acc, tax_type, status, gross in accounts:
                print(f"    🧾 Konto {acc:<8} | {tax_type or '-':<10} | {status:<10} | {gross:8.2f} EUR")

        export_rows.append({
            "TxID": tid,
            "Datum": tdate,
            "Betrag": float(tamount),
            "Name": tname or "",
            "Zweck": (purpose or "")[:100],
            "Beleg_IDs": ", ".join(str(v[0]) for v in vouchers) if vouchers else "",
            "Konten": ", ".join(str(a[0]) for a in accounts) if accounts else "",
            "Privat": is_private,
            "Offen": not (has_voucher and has_account)
        })

    print("\n📊 Zusammenfassung")
    print(f"    Gesamt:        {total:5d}")
    print(f"    Angezeigt:     {shown:5d}")

    if export:
        out_file = Path(f"report_transaction_overview_{period_label}.{export}")
        if export == "csv":
            with out_file.open("w", newline="", encoding="utf-8") as f:
                writer = csv.DictWriter(f, fieldnames=list(export_rows[0].keys()))
                writer.writeheader()
                writer.writerows(export_rows)
        elif export == "md":
            with out_file.open("w", encoding="utf-8") as f:
                f.write("| " + " | ".join(export_rows[0].keys()) + " |\n")
                f.write("|" + "|".join(["---"] * len(export_rows[0])) + "|\n")
                for row in export_rows:
                    f.write("| " + " | ".join(str(v) for v in row.values()) + " |\n")
        print(f"💾 Exportiert nach: {out_file.resolve()}")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Transaktions-/Beleg-/Kontenübersicht mit Exportoption")
    ap.add_argument("--month", help="Monat im Format YYYY-MM")
    ap.add_argument("--year", help="Ganzes Jahr im Format YYYY")
    ap.add_argument("--open-only", action="store_true", help="Nur unvollständige Transaktionen anzeigen")
    ap.add_argument("--non-private", action="store_true", help="Private Transaktionen ausblenden")
    ap.add_argument("--export", choices=["csv", "md"], help="Exportformat (csv oder md)")
    args = ap.parse_args()
    report_transaction_overview(args.month, args.year, args.open_only, args.non_private, args.export)
