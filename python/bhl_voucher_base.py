#!/usr/bin/env python3
"""
bhl_voucher_base.py – Gemeinsame Logik für Ein- und Ausgangsbelege
(Teil von Buchhaltung-Light)
"""

import os, re, sys, hashlib, shutil, unicodedata, subprocess
from datetime import datetime
from db import get_connection
from bhl_config import MY_NAMES
from bhl_zugferd import detect_and_parse_invoice

from bhl_config import OPEN_PDF_IN_BROWSER, BROWSER_CMD
from bhl_utils import row_get

# ------------------------------------------------------------
# Utility-Funktionen
# ------------------------------------------------------------


# ------------------------------------------------------------
#  Neue Konfigurations- und Erkennungslogik
# ------------------------------------------------------------

def detect_direction_from_xml(auto_info: dict, name_aliases: list[str]) -> str:
    """
    Bestimmt Richtung anhand von 'seller' und 'buyer' aus dem ZUGFeRD/XRechnung-XML.
    Gibt 'incoming', 'outgoing', 'self_issued' oder 'unknown' zurück.
    """
    if not auto_info:
        return "unknown"

    seller = (auto_info.get("seller") or "").lower()
    buyer = (auto_info.get("buyer") or "").lower()

    def matches_any(target: str) -> bool:
        return any(alias in target for alias in name_aliases if alias.strip())

    buyer_match = matches_any(buyer)
    seller_match = matches_any(seller)

    if buyer_match and not seller_match:
        return "incoming"
    elif seller_match and not buyer_match:
        return "outgoing"
    elif buyer_match and seller_match:
        return "self_issued"
    else:
        return "unknown"


def sanitize_filename_component(text: str) -> str:
    if not text:
        return "Unassigned"
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    text = text.replace("ß", "ss").replace("Ä", "Ae").replace("Ö", "Oe").replace("Ü", "Ue")
    text = text.replace("ä", "ae").replace("ö", "oe").replace("ü", "ue")
    text = re.sub(r"[^A-Za-z0-9_.-]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_")
    return text[:120]


def normalize_date(date_str: str) -> str:
    if not date_str:
        return datetime.today().strftime("%Y-%m-%d")
    if re.match(r"^\d{8}$", date_str):
        return f"{date_str[:4]}-{date_str[4:6]}-{date_str[6:8]}"
    try:
        return datetime.fromisoformat(date_str).strftime("%Y-%m-%d")
    except Exception:
        return datetime.today().strftime("%Y-%m-%d")


def parse_amount(raw: str) -> float | None:
    """Sichere Betragseingabe."""
    if not raw:
        return 0.0
    raw = raw.strip().replace("€", "").replace("EUR", "").strip().replace(",", ".")
    raw = re.sub(r"[^0-9.]", "", raw)
    parts = raw.split(".")
    if len(parts) > 2:
        raw = parts[0] + "." + "".join(parts[1:])
    try:
        return float(raw)
    except ValueError:
        return None


def sha256sum(filename: str) -> str:
    h = hashlib.sha256()
    with open(filename, "rb") as f:
        for block in iter(lambda: f.read(65536), b""):
            h.update(block)
    return h.hexdigest()


def ensure_target_dir(base_dir: str, date_str: str, mode: str) -> str:
    """Erstellt ./belege/(ausgang/)Jahr/Monat"""
    date_obj = datetime.strptime(normalize_date(date_str), "%Y-%m-%d")
    subdir = "ausgang" if mode == "outgoing" else ""
    path = os.path.join(base_dir, "belege", subdir, str(date_obj.year), f"{date_obj.month:02d}")
    os.makedirs(path, exist_ok=True)
    return path



def open_in_brave(pdf_path):
    if not OPEN_PDF_IN_BROWSER:
        return
    subprocess.Popen(BROWSER_CMD + [pdf_path],
                     stdout=subprocess.DEVNULL,
                     stderr=subprocess.DEVNULL)



# ------------------------------------------------------------
# Hauptlogik
# ------------------------------------------------------------

def process_voucher(pdf_path: str, base_dir: str, mode: str):
    if not os.path.exists(pdf_path):
        print(f"❌ Datei nicht gefunden: {pdf_path}")
        sys.exit(1)

    # --------------------------------------------------------
    #  Automatische Richtungserkennung via XML (falls gewünscht)
    # --------------------------------------------------------
    if mode == "auto":
        print("🔍 Automatische Richtungserkennung aktiviert …")
        info = detect_and_parse_invoice(pdf_path)
        mode = detect_direction_from_xml(info, MY_NAMES)
        if mode == "unknown":
            print("⚠️  Richtung nicht automatisch erkennbar.")
            mode = input("Bitte Richtung eingeben (incoming/outgoing) [incoming]: ").strip().lower() or "incoming"
        elif mode == "self_issued":
            print("ℹ️  Eigenbeleg erkannt (self_issued) – verwende 'outgoing'.")
            mode = "outgoing"
        else:
            print(f"✅ Richtung automatisch erkannt: {mode}")

    """
    Einheitliche Routine für Ein- und Ausgangsbelege.
    mode = 'incoming' oder 'outgoing'
    """
    if not os.path.exists(pdf_path):
        print(f"❌ Datei nicht gefunden: {pdf_path}")
        sys.exit(1)

    conn = get_connection()
    cur = conn.cursor()

    # Tabellenkontext
    if mode == "incoming":
        table_voucher, table_docs, link_field = "vouchers", "voucher_documents", "voucher_id"
        role = "seller"
    elif mode == "outgoing":
        table_voucher, table_docs, link_field = "outgoing_vouchers", "outgoing_documents", "outgoing_id"
        role = "buyer"
    else:
        raise ValueError("mode must be 'incoming' or 'outgoing'")

    # Erkennung elektronischer Rechnung
# --------------------------------------------------------
#  Prüfung auf elektronische Rechnung / optionale Quarantäne
# --------------------------------------------------------
    info = detect_and_parse_invoice(pdf_path)

    open_in_brave(pdf_path)

    if not info:
        print("⚠️  Kein ZUGFeRD/XRechnung-XML erkannt.")
        print("Öffne Beleg im Browser zur manuellen Prüfung …")
        
        choice = input("Beleg aufnehmen [Y]/N? ").strip().lower()
        if choice == "n":
            quarantine_dir = os.path.join(os.path.dirname(pdf_path), "quarantine")
            os.makedirs(quarantine_dir, exist_ok=True)
            target_quarantine = os.path.join(quarantine_dir, os.path.basename(pdf_path))
            shutil.move(pdf_path, target_quarantine)
            print(f"🚫 Beleg übersprungen und in Quarantäne verschoben:\n   {target_quarantine}")
            return
        else:
            print("✅ Beleg wird aufgenommen (keine E-Rechnung).")

    partner = voucher_number = voucher_date = description = ""
    total_amount = 0.0
    document_type = "invoice"

    if info:
        print("\n⚙️  Elektronische Rechnung erkannt:")
        for k, v in info.items():
            if k not in ("xml_filename", "source_pdf"):
                print(f"  {k:>14}: {v}")
        if input("Automatisch erkannte Werte übernehmen [Y/n]? ").strip().lower() in ("y", ""):
            partner = info.get(role) or ""
            voucher_number = info.get("number") or ""
            voucher_date = normalize_date(info.get("date"))
            total_amount = info.get("amount") or 0.0
            document_type = info.get("document_type", "invoice")
            description = f"{info.get('xml_type','invoice')} erkannt"

            # ➕ Automatische Betrags-Umkehr bei Gutschriften
            if document_type == "credit_note" and total_amount > 0:
                print("💡 Gutschrift erkannt – Betrag wird automatisch negativ gebucht.")
                total_amount *= -1


    # Benutzerinteraktion
    partner = input(f"{'Kunde' if mode=='outgoing' else 'Lieferant'}: ") or partner
    voucher_number = input("Rechnungs-/Belegnummer: ") or voucher_number
    voucher_date = normalize_date(input("Rechnungsdatum (YYYY-MM-DD): ") or voucher_date)
    description = input("Kurzbeschreibung: ") or description

    while True:
        val = input(f"Gesamtbetrag (brutto, EUR) [{total_amount:.2f}]: ").strip() or f"{total_amount:.2f}"
        amt = parse_amount(val)
        if amt is not None:
            total_amount = amt
            break

    document_type = input("Typ (invoice/credit_note/self_issued): ") or document_type

    # Dateiverwaltung
    target_dir = ensure_target_dir(base_dir, voucher_date, mode)
    safe_partner = sanitize_filename_component(partner)
    safe_number = sanitize_filename_component(voucher_number)
    new_filename = f"{voucher_date}_{safe_number}_{safe_partner}.pdf"
    target_path = os.path.join(target_dir, new_filename)
    file_hash = sha256sum(pdf_path)

    # Duplikatprüfung
    cur.execute(f"SELECT id FROM {table_voucher} WHERE voucher_number=%s AND partner_name=%s;", (voucher_number, partner))
    existing = cur.fetchone()
    if existing:
        existing_id = row_get(existing, "id", 0)
        print(f"⚠  Beleg {voucher_number} ({partner}) existiert bereits (ID {existing_id}).")
        act = input("Überspringen [S] oder Ersetzen [E]? ").strip().lower()
        if not act.startswith("e"):
            return
        cur.execute(f"DELETE FROM {table_voucher} WHERE id=%s;", (existing[0],))
        conn.commit()

    receipt_status = 'complete' if os.path.isfile(pdf_path) else 'pending'

    # Insert Hauptdatensatz
    cur.execute(
        f"""
        INSERT INTO {table_voucher}
            (voucher_number, voucher_date, partner_name, description,
             total_amount, currency, document_type, source, status, receipt_status)
        VALUES (%s,%s,%s,%s,%s,'EUR',%s,'manual','draft',%s)
        RETURNING id;
        """,
        (voucher_number, voucher_date, partner, description, total_amount, document_type, receipt_status),
    )
    row = cur.fetchone()
    if not row:
        raise RuntimeError("Fehler: kein Datensatz beim Einfügen zurückgegeben.")

    if isinstance(row, dict):
        vid = row.get("id")
    else:
        vid = row[0]

    conn.commit()

    shutil.move(pdf_path, target_path)

    # Dokumenteintrag
    cur.execute(
        f"""
        INSERT INTO {table_docs}
            ({link_field}, file_name, file_path, mime_type, file_hash)
        VALUES (%s,%s,%s,%s,%s);
        """,
        (vid, new_filename, target_dir, "application/pdf", file_hash),
    )
    conn.commit()
    cur.close()
    conn.close()

    print(f"\n✅ {mode.title()}-Beleg {voucher_number} gespeichert (ID {vid})")
    print(f"📁 {target_path}\n🔒 SHA256: {file_hash}")
