#!/usr/bin/env python3
"""
add_voucher.py
Erzeugt einen neuen Belegeintrag in der Datenbank und verschiebt die zugehörige PDF-Datei
in ein Zielverzeichnis mit Jahres-/Monatsstruktur und standardisiertem Namensschema.

Verwendung:
    python add_voucher.py <quelldatei.pdf> <zielverzeichnis>
"""

import os
import sys
import shutil
import subprocess
import hashlib
from datetime import datetime
from db import get_connection


# ------------------------------------------------------------
# Hilfsfunktionen
# ------------------------------------------------------------

def open_in_brave(filepath: str):
    """Öffnet die PDF-Datei im Brave-Browser zur Sichtprüfung."""
    try:
        subprocess.Popen(["brave-browser", filepath])
    except FileNotFoundError:
        print("⚠️  Brave-Browser nicht gefunden – Datei wird nicht angezeigt.")


def prompt(msg, default=None):
    val = input(f"{msg} [{'Enter' if default else ''}]: ").strip()
    return val or default


def sha256sum(filename: str) -> str:
    """Berechnet den SHA256-Hash einer Datei."""
    h = hashlib.sha256()
    with open(filename, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def ensure_target_dir(base_dir: str, date_str: str) -> str:
    """Erstellt automatisch Unterverzeichnis nach Jahr/Monat."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        year_dir = os.path.join(base_dir, str(date_obj.year))
        month_dir = os.path.join(year_dir, f"{date_obj.month:02d}")
        os.makedirs(month_dir, exist_ok=True)
        return month_dir
    except Exception:
        os.makedirs(base_dir, exist_ok=True)
        return base_dir


# ------------------------------------------------------------
# Hauptfunktion
# ------------------------------------------------------------

def add_voucher(pdf_path: str, base_dir: str):
    if not os.path.exists(pdf_path):
        print(f"❌ Quelldatei nicht gefunden: {pdf_path}")
        sys.exit(1)

    # Datei im Browser zeigen
    print(f"Öffne {pdf_path} im Brave-Browser zur Kontrolle …")
    open_in_brave(pdf_path)

    print("\nBitte Belegdaten eingeben:")
    supplier = prompt("Lieferant / Aussteller")
    voucher_number = prompt("Rechnungs-/Belegnummer")
    voucher_date = prompt("Rechnungsdatum (YYYY-MM-DD)")
    if not voucher_date:
        voucher_date = datetime.today().strftime("%Y-%m-%d")
    description = prompt("Kurzbeschreibung")
    total_amount = float(prompt("Gesamtbetrag (brutto, EUR)", "0").replace(",", "."))
    document_type = prompt("Typ (invoice/receipt/self_issued/other)", "invoice")

    # Zielverzeichnis (Jahr/Monat) automatisch erzeugen
    target_dir = ensure_target_dir(base_dir, voucher_date)

    # Vorschau des neuen Dateinamens
    safe_supplier = supplier.replace(" ", "_").replace("/", "-")
    new_filename = f"{voucher_date}_{voucher_number}_{safe_supplier}.pdf"
    target_path = os.path.join(target_dir, new_filename)

    print(f"\nVorschau:")
    print(f"  Lieferant:      {supplier}")
    print(f"  Belegnummer:    {voucher_number}")
    print(f"  Datum:          {voucher_date}")
    print(f"  Betrag:         {total_amount:.2f} EUR")
    print(f"  Typ:            {document_type}")
    print(f"  Neuer Dateiname: {new_filename}")
    print(f"  Zielverzeichnis: {target_dir}")
    confirm = input("\nAnlegen [Y/n]? ").strip().lower()

    if confirm not in ("y", ""):
        print("Abgebrochen.")
        sys.exit(0)

    # Datei-Hash berechnen (vor dem Verschieben)
    file_hash = sha256sum(pdf_path)

    # --- DB-Eintrag: Hauptbeleg ---
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO vouchers
            (voucher_number, voucher_date, partner_name, description,
             total_amount, currency, document_type, source, status)
        VALUES (%s,%s,%s,%s,%s,'EUR',%s,'manual','draft')
        RETURNING id;
        """,
        (voucher_number, voucher_date, supplier, description, total_amount, document_type),
    )
    voucher_id = cur.fetchone()[0]
    conn.commit()

    # --- Datei verschieben ---
    shutil.move(pdf_path, target_path)

    # --- DB-Eintrag: Dokument ---
    cur.execute(
        """
        INSERT INTO voucher_documents
            (voucher_id, file_name, file_path, mime_type, file_hash)
        VALUES (%s,%s,%s,%s,%s);
        """,
        (voucher_id, new_filename, target_dir, "application/pdf", file_hash),
    )
    conn.commit()
    cur.close()
    conn.close()

    print(f"\n✅ Beleg {voucher_number} angelegt (ID {voucher_id})")
    print(f"📁 Datei verschoben nach: {target_path}")
    print(f"🔒 SHA256: {file_hash}")


# ------------------------------------------------------------
# Einstiegspunkt
# ------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Verwendung: python add_voucher.py <quelldatei.pdf> <zielverzeichnis>")
        sys.exit(1)

    pdf_path = sys.argv[1]
    base_dir = sys.argv[2]
    add_voucher(pdf_path, base_dir)
