#!/usr/bin/env python3
"""
assign_accounts.py
Interaktive oder regelbasierte Zuordnung von Belegen (incoming/outgoing)
zu SKR03-Konten inklusive automatischer USt-/VSt-Klassifikation (tax_type).

Beispiel:
    python3 python/assign_accounts.py --direction incoming --month 2024-01
    python3 python/assign_accounts.py --direction outgoing --month 2024-12 --show-pdf
"""

import argparse
import subprocess
from decimal import Decimal, ROUND_HALF_UP
from datetime import datetime, timedelta
from db import get_connection

# ------------------------------------------------------------
# Steuerlogik für SKR03 / USt-Klassifikation
# ------------------------------------------------------------
def determine_tax_type(direction: str, tax_rate: Decimal, note: str | None = None) -> str:
    """Leitet die steuerliche Kategorie (tax_type) ab."""
    if note and "reverse" in note.lower():
        return "reverse_charge"
    if note and "ig" in note.lower():
        return "ig_erwerb"

    if direction == "incoming":
        if tax_rate == 19:
            return "vst19"
        elif tax_rate == 7:
            return "vst7"
        else:
            return "vst0"
    elif direction == "outgoing":
        if tax_rate == 19:
            return "ust19"
        elif tax_rate == 7:
            return "ust7"
        else:
            return "ust0"
    return None


def find_rule(cur, name: str, direction: str):
    """Versucht, eine passende Buchungsregel aus booking_rules zu finden."""
    cur.execute("""
        SELECT pattern, default_account, default_tax, direction, note
          FROM booking_rules
         WHERE direction = %s
      ORDER BY LENGTH(pattern) DESC;
    """, (direction,))
    rules = cur.fetchall()

    for pattern, account, tax, dirn, note in rules:
        if pattern.lower() in name.lower():
            return (account, Decimal(tax), note)
    return None


def get_account_info(cur, account_id):
    """Lädt Kontoinformationen aus SKR03-Tabelle."""
    cur.execute("SELECT id, name, tax_rate FROM skr03_accounts WHERE id = %s;", (account_id,))
    return cur.fetchone()


def list_accounts(cur):
    """Zeigt gängige Konten an (nur Auszug, zur Orientierung)."""
    cur.execute("""
        SELECT id, name, default_tax
          FROM skr03_accounts
         ORDER BY id
         LIMIT 15;
    """)
    print("  Verfügbare Konten (Auszug):")
    for acc_id, name, default_tax in cur.fetchall():
        print(f"     {acc_id:6} | {name:40s} | {default_tax:.2f}%")


def _insert_booking_lines_new(cur, source_type: str, source_id: int,
                               account_skr: str, net: Decimal, tax: Decimal):
    """Erzeugt die drei Doppelbuchungs-Zeilen in booking_lines_new."""
    gross = net + tax
    if source_type == "incoming":
        lines = [
            (source_type, source_id, account_skr, net),   # Aufwand
            (source_type, source_id, "1576",       tax),   # Vorsteuer
            (source_type, source_id, "1600",      -gross), # Verbindlichkeit
        ]
    else:
        lines = [
            (source_type, source_id, "1200",       gross), # Forderung
            (source_type, source_id, account_skr, -net),   # Erlös
            (source_type, source_id, "1776",      -tax),   # Umsatzsteuer
        ]
    for line in lines:
        cur.execute("""
            INSERT INTO booking_lines_new (source_type, source_id, account_skr, amount)
            VALUES (%s, %s, %s, %s)
        """, line)


def assign_accounts(direction: str, month: str, show_pdf=False, auto=False):
    """Weist Belegen Konten zu."""
    conn = get_connection()
    cur = conn.cursor()

    mdate = datetime.strptime(month, "%Y-%m")
    start = mdate.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)
    vtable   = "vouchers"      if direction == "incoming" else "outgoing_vouchers"
    ltable   = "voucher_lines" if direction == "incoming" else "outgoing_lines"
    id_field = "voucher_id"    if direction == "incoming" else "outgoing_id"

    # Belege ohne Kontierung holen
    cur.execute(f"""
        SELECT id, partner_name, total_amount, voucher_date
          FROM {vtable}
         WHERE status != 'cancelled'
           AND voucher_date BETWEEN %s AND %s
           AND id NOT IN (
               SELECT {id_field} FROM {ltable} WHERE {id_field} IS NOT NULL
           )
         ORDER BY voucher_date;
    """, (start, end))
    vouchers = cur.fetchall()

    print(f"📅 Zeitraum: {start.date()} bis {end.date()}")
    print(f"\n{len(vouchers)} Beleg(e) ohne Kontierung gefunden.\n")

    for vid, name, amount, vdate in vouchers:
        print("=" * 70)
        print(f"Beleg-ID {vid} | {name} | {amount:.2f} EUR | {vdate}")

        # zugehörigen Beleg anzeigen (optional)
        if show_pdf:
            cur.execute("SELECT file_path, file_name FROM voucher_documents WHERE voucher_id = %s;", (vid,))
            doc = cur.fetchone()
            if doc:
                path, fname = doc
                pdf_path = f"{path}/{fname}"
                print(f"  📄 Öffne Beleg: {pdf_path}")
                try:
                    subprocess.Popen(["brave-browser", pdf_path])
                except Exception as e:
                    print(f"  ⚠️  PDF konnte nicht geöffnet werden: {e}")

        # Regel prüfen
        rule = find_rule(cur, name or "", direction)
        if rule:
            account, tax_rate, note = rule
            print(f"  ⚙  Regel gefunden: Konto {account} ({note or 'keine Notiz'}) | {tax_rate:.2f}%")
        else:
            print("  ⚙  Keine Regel gefunden.")
            if auto:
                print("  ➜ übersprungen (--auto Modus).\n")
                continue
            list_accounts(cur)
            account = input("  Konto (SKR03): ").strip()
            if not account:
                print("  ➜ übersprungen.\n")
                continue
            tax_rate = Decimal(input("  Steuersatz (z. B. 19, 7, 0): ") or "19")
            note = None

        # Buchungsdaten berechnen
        gross = Decimal(amount)
        net = (gross / (Decimal(1) + tax_rate / 100)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax_amount = (net * tax_rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        tax_type = determine_tax_type(direction, tax_rate, note)

        # In voucher_lines / outgoing_lines schreiben
        cur.execute(f"""
            INSERT INTO {ltable}
                ({id_field}, account_skr, description,
                 net_amount, tax_rate, tax_amount, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, NOW())
            RETURNING id;
        """, (vid, account, note or "", net, tax_rate, tax_amount))
        line_id = cur.fetchone()[0]

        # Doppelbuchung in booking_lines_new erzeugen
        _insert_booking_lines_new(cur, direction, line_id, account, net, tax_amount)

        conn.commit()
        print(f"  ✅ Beleg {vid} → Konto {account} ({tax_type}) verbucht.\n")

    cur.close()
    conn.close()
    print("✅ Zuordnung abgeschlossen.")


def main():
    ap = argparse.ArgumentParser(description="Weist Belegen Konten (SKR03) zu.")
    ap.add_argument("--direction", choices=["incoming", "outgoing"], required=True)
    ap.add_argument("--month", required=True, help="Monat (YYYY-MM)")
    ap.add_argument("--show-pdf", action="store_true", help="Beleg im PDF-Viewer öffnen")
    ap.add_argument("--auto", action="store_true", help="Nur bestehende Regeln verwenden (keine manuelle Eingabe)")
    args = ap.parse_args()
    assign_accounts(args.direction, args.month, args.show_pdf, args.auto)


if __name__ == "__main__":
    main()
