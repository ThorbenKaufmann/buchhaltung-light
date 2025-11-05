#!/usr/bin/env python3
"""
import_mt940.py
Liest MT940-Dateien ein und importiert sie in die Tabelle 'transactions'.

Funktionen:
- Parser für MT940-Dateien (Paket mt-940)
- JSON-Speicherung der Rohdaten
- Hash-basierte Dublettenerkennung (account_id | booking_date | amount | purpose)
- Purpose-Cleaner: entfernt MT940-Codes und Leerzeichen
"""

import sys
import os
import re
import hashlib
import mt940
from psycopg2.extras import Json
from db import get_connection


def clean_purpose(description: str, counterpart: str = "") -> str:
    """Bereinigt den Verwendungszweck aus MT940 (:86:)."""
    if not description:
        description = counterpart or ""

    # Steuerzeichen ?00, ?20 usw. und IBAN-Texte entfernen
    cleaned = re.sub(r"\?[0-9]{2}", " ", description)
    cleaned = re.sub(r"IBAN:[A-Z0-9]+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"BIC:[A-Z0-9]+", "", cleaned, flags=re.IGNORECASE)
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned.strip()


def make_hash(account_id, booking_date, amount, purpose, counterpart):
    """Erzeugt einen stabilen Hash zur Dublettenerkennung."""
    normalized_purpose = " ".join(purpose.lower().split())
    normalized_counterpart = (counterpart or "").lower().strip()
    amount_str = f"{amount:.2f}"
    key = f"{account_id}|{booking_date}|{amount_str}|{normalized_purpose}|{normalized_counterpart}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def import_mt940_file(filename: str, account_id: int):
    if not os.path.exists(filename):
        raise FileNotFoundError(f"Datei {filename} wurde nicht gefunden.")

    with open(filename, "r", encoding="utf-8") as f:
        data = f.read()

    transactions = mt940.models.Transactions(processors=dict())
    transactions.parse(data)
    print(f"{len(transactions)} Buchungen in {filename} gefunden.")

    conn = get_connection()
    cur = conn.cursor()
    inserted = 0
    skipped = 0

    for t in transactions:
        booking_date = t.data.get("date")
        value_date = t.data.get("entry_date") or booking_date
        amount = float(t.data["amount"].amount)
        currency = t.data["amount"].currency or "EUR"
        counterpart = (t.data.get("applicant_name") or "").strip()
        raw = {k: str(v) for k, v in t.data.items()}

        # purpose = clean_purpose(t.data.get("description", ""), counterpart)
        # Zweck robust zusammensetzen aus mehreren Quellen
        desc = t.data.get("description") or ""
        purpose_field = t.data.get("purpose") or ""
        add_purpose = t.data.get("additional_purpose") or ""
        applicant = t.data.get("applicant_name") or ""

        # alle zusammenführen (manche Parser-Felder überschneiden sich)
        combined_purpose = " ".join(
            p for p in [desc, purpose_field, add_purpose] if p
        ).strip()

        # Fallback: wenn nichts übrig bleibt, wenigstens Gegenpartei nehmen
        if not combined_purpose:
            combined_purpose = applicant

        purpose = clean_purpose(combined_purpose, applicant)

        tx_hash = make_hash(account_id, booking_date, amount, purpose, counterpart)

        cur.execute(
            """
            INSERT INTO transactions
                (account_id, booking_date, value_date, amount, currency,
                 counterpart_name, purpose, import_source, raw_data, tx_hash)
            VALUES (%s,%s,%s,%s,%s,%s,%s,'mt940',%s,%s)
            ON CONFLICT (tx_hash) DO NOTHING
            """,
            (
                account_id,
                booking_date,
                value_date,
                amount,
                currency,
                counterpart,
                purpose,
                Json(raw),
                tx_hash,
            ),
        )

        if cur.rowcount == 0:
            skipped += 1
            print(f"⚠️  Dublette übersprungen: {booking_date} {amount:>10.2f} {purpose[:60]}")
        else:
            inserted += 1
            print(f"✓ Buchung importiert: {booking_date} {amount:>10.2f} {currency} – {purpose[:60]}")

    conn.commit()
    cur.close()
    conn.close()
    print(f"\nImport abgeschlossen: {inserted} neu, {skipped} Dubletten übersprungen.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Verwendung: python import_mt940.py <datei> <account_id>")
        sys.exit(1)
    import_mt940_file(sys.argv[1], int(sys.argv[2]))
