#!/usr/bin/env python3
"""
add_voucher.py
Erzeugt einen neuen Belegeintrag in der Datenbank und verschiebt die zugehörige PDF-Datei
in ein Zielverzeichnis mit Jahres-/Monatsstruktur und standardisiertem Namensschema.

Neu: Automatische Erkennung elektronischer Rechnungen (ZugFeRD / XRechnung).
"""

import os
import sys
if sys.stdin.encoding.lower() != "utf-8":
    sys.stdin.reconfigure(encoding="utf-8", errors="ignore")

import shutil
import subprocess
import hashlib
from datetime import datetime
from db import get_connection
from bhl_zugferd import detect_and_parse_invoice


# ------------------------------------------------------------
# Hilfsfunktionen
# ------------------------------------------------------------

import re
import unicodedata

def sanitize_filename_component(text: str) -> str:
    """Macht einen Text sicher für Dateinamen (ASCII, kein Slash, keine Sonderzeichen)."""
    if not text:
        return "Unassigned"

    # Unicode normalisieren (z. B. é -> e, ö -> o)
    text = unicodedata.normalize("NFKD", text)
    text = text.encode("ascii", "ignore").decode("ascii")

    # typische deutsche Ersetzungen (optional, bevor ASCII-Fallback)
    text = text.replace("ß", "ss").replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")

    # unerlaubte Zeichen entfernen oder durch _ ersetzen
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)

    # mehrfach unterstriche reduzieren
    text = re.sub(r"_+", "_", text).strip("_")

    # Länge begrenzen (Dateisysteme!)
    return text[:120]


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
    """Erstellt Unterverzeichnis ./belege/Jahr/Monat relativ zum Skriptpfad."""
    try:
        date_obj = datetime.strptime(date_str, "%Y-%m-%d")
        year_dir = os.path.join(base_dir, "belege", str(date_obj.year))
        month_dir = os.path.join(year_dir, f"{date_obj.month:02d}")
        os.makedirs(month_dir, exist_ok=True)
        return month_dir
    except Exception:
        os.makedirs(os.path.join(base_dir, "belege"), exist_ok=True)
        return os.path.join(base_dir, "belege")



# ------------------------------------------------------------
# Hauptfunktion
# ------------------------------------------------------------

def add_voucher(pdf_path: str, base_dir: str):
    if not os.path.exists(pdf_path):
        print(f"❌ Quelldatei nicht gefunden: {pdf_path}")
        sys.exit(1)

    # Prüfen, ob elektronische Rechnung eingebettet ist
    auto_info = detect_and_parse_invoice(pdf_path)
    if auto_info:
        print("\n⚙️  Elektronische Rechnung erkannt:")
        for k, v in auto_info.items():
            if k not in ("xml_filename", "source_pdf"):
                print(f"  {k:>10}: {v}")
        if input("Automatisch erkannte Werte übernehmen [Y/n]? ").strip().lower() in ("y", ""):
            supplier = auto_info.get("seller") or ""
            voucher_number = auto_info.get("number") or ""
            voucher_date = auto_info.get("date") or datetime.today().strftime("%Y-%m-%d")
            total_amount = auto_info.get("amount") or 0.0
            document_type = "invoice"
            description = f"{auto_info.get('xml_type','invoice')} erkannt"
        else:
            auto_info = None
    else:
        auto_info = None

    # Datei im Browser zeigen
    print(f"\nÖffne {pdf_path} im Brave-Browser zur Kontrolle …")
    open_in_brave(pdf_path)

    print("\nBitte Belegdaten eingeben:")

    supplier = prompt("Lieferant / Aussteller", supplier if auto_info else None)
    voucher_number = prompt("Rechnungs-/Belegnummer", voucher_number if auto_info else None)
    voucher_date = prompt("Rechnungsdatum (YYYY-MM-DD)", voucher_date if auto_info else None)
    if not voucher_date:
        voucher_date = datetime.today().strftime("%Y-%m-%d")
    description = prompt("Kurzbeschreibung", description if auto_info else None)
    total_amount = float(prompt("Gesamtbetrag (brutto, EUR)", str(total_amount) if auto_info else "0").replace(",", "."))
    document_type = prompt("Typ ([invoice]/receipt/self_issued/other)", document_type if auto_info else "invoice")

    # Zielverzeichnis (Jahr/Monat) automatisch erzeugen
    target_dir = ensure_target_dir(base_dir, voucher_date)

    # Vorschau des neuen Dateinamens
    safe_supplier = sanitize_filename_component(supplier)
    safe_number = sanitize_filename_component(voucher_number)
    new_filename = f"{voucher_date}_{safe_number}_{safe_supplier}.pdf"

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

    try:
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
    except Exception as e:
        conn.rollback()
        # Prüfen, ob es ein UniqueViolation ist
        if "duplicate key value" in str(e):
            print(f"⚠️  Belegnummer {voucher_number} existiert bereits in der Datenbank.")
            # Beleg-ID nachschlagen
            cur.execute("SELECT id FROM vouchers WHERE voucher_number = %s AND partner_name = %s;", (voucher_number, supplier),)

            res = cur.fetchone()
            if res:
                voucher_id = res[0]
                action = input("Vorhandenen Beleg (ID %s) überspringen [S] oder ersetzen [E]? " % voucher_id).strip().lower()
                if action in ("e", "ers", "ersetzen"):
                    cur.execute("DELETE FROM vouchers WHERE id = %s;", (voucher_id,))
                    conn.commit()
                    print("➡️  Alter Eintrag entfernt, bitte erneut ausführen.")
                    sys.exit(0)
                else:
                    print("➡️  Beleg wird übersprungen.")
                    cur.close()
                    conn.close()
                    sys.exit(0)
            else:
                print("⚠️  Fehler: Konnte bestehende Beleg-ID nicht abrufen.")
                sys.exit(1)
        else:
            raise


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
