#!/usr/bin/env python3
"""
add_outgoing_voucher.py
Erfasst eine Ausgangsrechnung (Verkauf) in der Datenbank und verschiebt
die zugehörige PDF-Datei in ./belege/ausgang/Jahr/Monat.

Struktur und Logik analog zu add_voucher.py.
"""

import os
import sys
import shutil
import subprocess
import hashlib
from datetime import datetime
from db import get_connection
from bhl_zugferd import detect_and_parse_invoice
import re
import unicodedata


# ------------------------------------------------------------
# Hilfsfunktionen
# ------------------------------------------------------------

def sanitize_filename_component(text: str) -> str:
    """Macht einen Text sicher für Dateinamen (ASCII, kein Slash, keine Sonderzeichen)."""
    if not text:
        return "Unassigned"
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")
    text = text.replace("ß", "ss").replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:120]


def open_in_brave(filepath: str):
    """Öffnet die PDF-Datei im Brave-Browser zur Sichtprüfung (falls nicht deaktiviert)."""
    if os.environ.get("BHL_NO_BROWSER"):
        return
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
    """Erstellt Unterverzeichnis ./belege/ausgang/Jahr/Monat relativ zum Basisverzeichnis."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        year_dir = os.path.join(base_dir, "belege", "ausgang", str(date_obj.year))
        month_dir = os.path.join(year_dir, f"{date_obj.month:02d}")
        os.makedirs(month_dir, exist_ok=True)
        return month_dir
    except Exception:
        os.makedirs(os.path.join(base_dir, "belege", "ausgang"), exist_ok=True)
        return os.path.join(base_dir, "belege", "ausgang")


# ------------------------------------------------------------
# Hauptfunktion
# ------------------------------------------------------------

def add_outgoing_voucher(pdf_path: str, base_dir: str):
    if not os.path.exists(pdf_path):
        print(f"❌ Quelldatei nicht gefunden: {pdf_path}")
        sys.exit(1)

    # Prüfen, ob elektronische Rechnung (ZugFeRD/XRechnung)
    auto_info = detect_and_parse_invoice(pdf_path)
    if auto_info:
        print("\n⚙️  Elektronische Rechnung erkannt:")
        for k, v in auto_info.items():
            if k not in ("xml_filename", "source_pdf"):
                print(f"  {k:>10}: {v}")
        if input("Automatisch erkannte Werte übernehmen [Y/n]? ").strip().lower() in ("y", ""):
            customer = auto_info.get("buyer") or ""
            invoice_number = auto_info.get("number") or ""
            invoice_date = auto_info.get("date") or datetime.today().strftime("%Y-%m-%d")
            total_amount = auto_info.get("amount") or 0.0
            description = f"{auto_info.get('xml_type','invoice')} erkannt"
            document_type = "invoice"
        else:
            auto_info = None
    else:
        auto_info = None

    # Datei im Browser zeigen
    print(f"\nÖffne {pdf_path} im Brave-Browser zur Kontrolle …")
    open_in_brave(pdf_path)

    print("\nBitte Rechnungsdaten eingeben:")
    customer = prompt("Kunde / Empfänger", customer if auto_info else None)
    invoice_number = prompt("Rechnungsnummer", invoice_number if auto_info else None)
    invoice_date = prompt("Rechnungsdatum (YYYY-MM-DD)", invoice_date if auto_info else None)
    if not invoice_date:
        invoice_date = datetime.today().strftime("%Y-%m-%d")
    description = prompt("Kurzbeschreibung", description if auto_info else None)
    total_amount = float(prompt("Gesamtbetrag (brutto, EUR)", str(total_amount) if auto_info else "0").replace(",", "."))
    document_type = prompt("Typ (invoice/credit_note/self_issued)", document_type if auto_info else "invoice")

    # Zielverzeichnis erzeugen
    target_dir = ensure_target_dir(base_dir, invoice_date)

    safe_customer = sanitize_filename_component(customer)
    safe_number = sanitize_filename_component(invoice_number)
    new_filename = f"{invoice_date}_{safe_number}_{safe_customer}.pdf"
    target_path = os.path.join(target_dir, new_filename)

    print(f"\nVorschau:")
    print(f"  Kunde:          {customer}")
    print(f"  Rechnungsnummer:{invoice_number}")
    print(f"  Datum:          {invoice_date}")
    print(f"  Betrag:         {total_amount:.2f} EUR")
    print(f"  Typ:            {document_type}")
    print(f"  Neuer Dateiname:{new_filename}")
    print(f"  Zielverzeichnis:{target_dir}")
    confirm = input("\nAnlegen [Y/n]? ").strip().lower()
    if confirm not in ("y", ""):
        print("Abgebrochen.")
        sys.exit(0)

    file_hash = sha256sum(pdf_path)
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        INSERT INTO outgoing_vouchers
            (invoice_number, invoice_date, customer_name, description,
             total_amount, currency, document_type, source, status)
        VALUES (%s,%s,%s,%s,%s,'EUR',%s,'manual','draft')
        RETURNING id;
        """,
        (invoice_number, invoice_date, customer, description, total_amount, document_type),
    )
    outgoing_id = cur.fetchone()[0]
    conn.commit()

    shutil.move(pdf_path, target_path)

    cur.execute(
        """
        INSERT INTO outgoing_documents
            (outgoing_id, file_name, file_path, mime_type, file_hash)
        VALUES (%s,%s,%s,%s,%s);
        """,
        (outgoing_id, new_filename, target_dir, "application/pdf", file_hash),
    )
    conn.commit()
    cur.close()
    conn.close()

    print(f"\n✅ Ausgangsrechnung {invoice_number} angelegt (ID {outgoing_id})")
    print(f"📁 Datei verschoben nach: {target_path}")
    print(f"🔒 SHA256: {file_hash}")


# ------------------------------------------------------------
# Einstiegspunkt
# ------------------------------------------------------------

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Verwendung: python add_outgoing_voucher.py <quelldatei.pdf> <basisverzeichnis>")
        sys.exit(1)
    pdf_path = sys.argv[1]
    base_dir = sys.argv[2]
    add_outgoing_voucher(pdf_path, base_dir)
