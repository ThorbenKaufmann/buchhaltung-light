#!/usr/bin/env python3
"""
assign_accounts.py – Version 4
Kontiert Belege auf SKR03-Konten (verknüpft mit skr03_accounts, PDF-Vorschau aus DB, optional Auto-Modus).
"""

import argparse
import os
import subprocess
from glob import glob
from datetime import datetime, timedelta
from db import get_connection


# ------------------------------------------------------------
# Hilfsfunktionen
# ------------------------------------------------------------
def find_rule(cur, name, direction):
    cur.execute("""
        SELECT default_account, default_tax, note
          FROM booking_rules
         WHERE direction = %s
           AND position(lower(pattern) in lower(%s)) > 0
         ORDER BY LENGTH(pattern) DESC
         LIMIT 1;
    """, (direction, name))
    return cur.fetchone()


def get_account_info(cur, account_id):
    cur.execute("""
        SELECT id, name, default_tax
          FROM skr03_accounts
         WHERE id = %s;
    """, (account_id,))
    return cur.fetchone()


def list_accounts(cur):
    cur.execute("""
        SELECT id, name, default_tax
          FROM skr03_accounts
         WHERE is_active = TRUE
         ORDER BY id;
    """)
    return cur.fetchall()


def open_voucher_from_db(cur, voucher_id):
    """
    Öffnet den PDF-Beleg anhand voucher_documents.voucher_id.
    """
    cur.execute("""
        SELECT file_path, file_name
          FROM voucher_documents
         WHERE voucher_id = %s
         ORDER BY id DESC
         LIMIT 1;
    """, (voucher_id,))
    row = cur.fetchone()

    if not row:
        return False

    rel_path = os.path.join(row[0], row[1]) if row[1] else row[0]
    pdf_path = os.path.normpath(rel_path)
    if not os.path.isfile(pdf_path):
        print(f"  ⚠️  Datei {pdf_path} existiert nicht.")
        return False

    print(f"  📄 Öffne Beleg: {pdf_path}")
    try:
        if os.name == "posix":
            subprocess.Popen(["xdg-open", pdf_path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif os.name == "nt":
            os.startfile(pdf_path)
        else:
            subprocess.Popen(["open", pdf_path])
        return True
    except Exception as e:
        print(f"  ⚠️  Konnte PDF nicht öffnen: {e}")
        return False


def open_voucher_fallback(voucher_date, voucher_number=None, partner_name=None):
    """Fallback-Suche im belege/<Jahr>/<Monat>/"""
    year = voucher_date.strftime("%Y")
    month = voucher_date.strftime("%m")
    base_path = os.path.join("belege", year, month)
    if not os.path.isdir(base_path):
        return False
    pattern = "*.pdf"
    if voucher_number:
        pattern = f"*{voucher_number}*.pdf"
    elif partner_name:
        pattern = f"*{partner_name.split()[0]}*.pdf"
    matches = glob(os.path.join(base_path, pattern))
    if not matches:
        return False
    pdf_path = matches[0]
    print(f"  📄 Öffne Beleg (Fallback): {pdf_path}")
    try:
        if os.name == "posix":
            subprocess.Popen(["xdg-open", pdf_path],
                             stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        elif os.name == "nt":
            os.startfile(pdf_path)
        else:
            subprocess.Popen(["open", pdf_path])
        return True
    except Exception:
        return False


# ------------------------------------------------------------
# Hauptfunktion
# ------------------------------------------------------------
def assign_accounts(direction, month=None, show_pdf=False, auto=False):
    conn = get_connection()
    cur = conn.cursor()

    if direction == "incoming":
        table, id_field, name_field, date_field = "vouchers", "id", "partner_name", "voucher_date"
    else:
        table, id_field, name_field, date_field = "outgoing_vouchers", "id", "customer_name", "invoice_date"

    # Zeitraum
    if month:
        mdate = datetime.strptime(month, "%Y-%m")
        start = mdate.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        print(f"📅 Zeitraum: {start:%Y-%m-%d} bis {end:%Y-%m-%d}")
    else:
        start = datetime(1970, 1, 1)
        end = datetime(2100, 1, 1)

    # Belege ohne Kontierung
    cur.execute(f"""
        SELECT {id_field}, {name_field}, total_amount, {date_field}
          FROM {table}
         WHERE {date_field} BETWEEN %s AND %s
           AND id NOT IN (
                SELECT COALESCE(voucher_id, outgoing_id)
                  FROM booking_lines
                  WHERE direction = %s
           )
         ORDER BY {date_field};
    """, (start, end, direction))
    vouchers = cur.fetchall()
    if not vouchers:
        print("✅ Keine unkontierten Belege gefunden.")
        return

    print(f"\n{len(vouchers)} Beleg(e) ohne Kontierung gefunden.\n")

    for vid, name, total, vdate in vouchers:
        print("=" * 70)
        print(f"Beleg-ID {vid} | {name or '(kein Name)'} | {total:.2f} EUR | {vdate}")

        if show_pdf:
            if not open_voucher_from_db(cur, vid):
                open_voucher_fallback(vdate, voucher_number=str(vid), partner_name=name)

        # Regelvorschlag
        rule = find_rule(cur, name or "", direction)
        if not rule:
            if auto:
                print("  ⚙️  Keine Regel gefunden → übersprungen (Auto-Modus).")
                continue
            print("  ⚙️  Keine Regel gefunden.")
            acc_list = list_accounts(cur)[:10]
            for acc in acc_list:
                print(f"     {acc[0]:6s} | {acc[1]:40s} | {acc[2]}%")
            account = input("  Konto (SKR03): ").strip()
            acc_info = get_account_info(cur, account)
            if not acc_info:
                print(f"  ⚠️  Konto {account} existiert nicht. Übersprungen.\n")
                continue
            tax = acc_info[2]
        else:
            account, tax, note = rule
            acc_info = get_account_info(cur, account)
            if not acc_info:
                print(f"  ⚠️  Regel verweist auf unbekanntes Konto {account}.")
                continue
            acc_name = acc_info[1]
            print(f"  → Vorschlag: Konto {account} ({acc_name}), Steuer {tax}% ({note})")

        try:
            tax = float(tax)
        except ValueError:
            tax = acc_info[2] if acc_info else 19.0

        net = round(float(total) / (1 + tax / 100), 2)
        tax_amount = round(float(total) - net, 2)
        acc_name = acc_info[1] if acc_info else ""

        if not auto:
            confirm = input(f"  Verbuchen als {account} ({acc_name}) {tax}% [y/N]? ").strip().lower()
            if confirm != "y":
                print("  ➜ Übersprungen.\n")
                continue
        else:
            print(f"  ⚡ Auto-Kontierung: {account} ({acc_name}) {tax}%")

        cur.execute("""
            INSERT INTO booking_lines (direction, voucher_id, outgoing_id,
                                       account_skr, description,
                                       net_amount, tax_rate, tax_amount, gross_amount)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s);
        """, (
            direction,
            vid if direction == "incoming" else None,
            vid if direction == "outgoing" else None,
            account, name,
            net, tax, tax_amount, total
        ))
        conn.commit()
        print(f"  ✅ Kontierung gespeichert: {account} ({acc_name}), Netto {net:.2f} €, Steuer {tax_amount:.2f} €.\n")

    cur.close()
    conn.close()
    print("\n✅ Alle Belege bearbeitet.\n")


# ------------------------------------------------------------
# CLI
# ------------------------------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Kontiert Belege auf SKR03-Konten (mit PDF-Vorschau aus DB).")
    ap.add_argument("--direction", required=True, choices=["incoming", "outgoing"])
    ap.add_argument("--month", help="YYYY-MM (optional)")
    ap.add_argument("--show-pdf", action="store_true", help="Zeigt den Beleg im PDF-Viewer an (falls vorhanden)")
    ap.add_argument("--auto", action="store_true", help="Automatische Kontierung bei eindeutiger Regel (ohne Nachfrage)")
    args = ap.parse_args()

    assign_accounts(args.direction, args.month, args.show_pdf, args.auto)
