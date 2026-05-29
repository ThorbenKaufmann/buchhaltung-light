#!/usr/bin/env python3
"""
import_commerzbank_csv.py
Importiert Commerzbank CSV-Kontoauszüge in die Tabelle 'transactions'.

Format: Semikolon-getrennt, DD.MM.YYYY, deutsches Zahlenformat.
Export unter: Commerzbank Online-Banking → Umsätze → Herunterladen → CSV

Verwendung:
    python3 python/import_commerzbank_csv.py <datei.csv> <account_id>
    python3 python/import_commerzbank_csv.py <datei.csv> <account_id> --dry-run
"""

import argparse
import csv
import hashlib
import re
import sys
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from psycopg2.extras import Json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db import get_connection


_BIC_RE  = re.compile(r'\b[A-Z]{4}[A-Z]{2}[A-Z0-9]{2}(?:[A-Z0-9]{3})?\b')
_IBAN_RE = re.compile(r'\b[A-Z]{2}[0-9]{2}[A-Z0-9]{10,30}\b')
_ETE_RE  = re.compile(r'End-to-End-Ref', re.IGNORECASE)

# Umsatzarten ohne externen Gegenpart
_NO_COUNTERPART = {"Zinsen/Entgelte", "Kontoführungsgebühren", "Kontoabschluss"}


def parse_amount(value: str) -> Decimal:
    """'1.728,49' oder '-180,26' oder '2000' → Decimal"""
    cleaned = value.strip().replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"Ungültiger Betrag: {repr(value)}")


def parse_date(value: str) -> str:
    """'DD.MM.YYYY' → 'YYYY-MM-DD'"""
    return datetime.strptime(value.strip(), "%d.%m.%Y").strftime("%Y-%m-%d")


def extract_counterpart(buchungstext: str, umsatzart: str) -> str:
    """Extrahiert den Gegenparteinamen aus dem Buchungstext."""
    if umsatzart in _NO_COUNTERPART:
        return ""

    text = buchungstext.strip()
    cutoff = len(text)

    for pattern in (_BIC_RE, _IBAN_RE, _ETE_RE):
        m = pattern.search(text)
        if m:
            cutoff = min(cutoff, m.start())

    counterpart = text[:cutoff].strip().rstrip(",;")
    return counterpart if len(counterpart) <= 120 else ""


def make_hash(account_id: int, booking_date: str, amount: Decimal, buchungstext: str) -> str:
    key = f"{account_id}|{booking_date}|{amount:.2f}|{buchungstext.strip()}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def read_csv(filename: str) -> tuple[list[dict], str]:
    for enc in ("utf-8-sig", "utf-8", "latin-1"):
        try:
            with open(filename, encoding=enc, newline="") as f:
                content = f.read()
            reader = csv.DictReader(content.splitlines(), delimiter=";")
            return list(reader), enc
        except UnicodeDecodeError:
            continue
    raise ValueError(f"Konnte {filename} nicht lesen (kein UTF-8 oder Latin-1).")


def import_commerzbank_csv(filename: str, account_id: int, dry_run: bool = False):
    if not os.path.exists(filename):
        print(f"Datei nicht gefunden: {filename}")
        sys.exit(1)

    rows, enc = read_csv(filename)
    print(f"\nDatei: {filename}  (Encoding: {enc})")
    print(f"Zeilen gesamt: {len(rows)}")
    if dry_run:
        print("DRY-RUN — keine Datenbankänderungen\n")

    conn = get_connection() if not dry_run else None
    cur  = conn.cursor() if conn else None

    inserted = skipped = duplicate = errors = 0

    for row in rows:
        buchungstext = (row.get("Buchungstext") or "").strip()
        umsatzart    = (row.get("Umsatzart") or "").strip()

        if not buchungstext and not (row.get("Betrag") or "").strip():
            skipped += 1
            continue

        try:
            booking_date = parse_date(row["Buchungstag"])
            value_date   = parse_date(row["Wertstellung"])
            amount       = parse_amount(row["Betrag"])
            currency     = (row.get("Währung") or "EUR").strip()
            counterpart  = extract_counterpart(buchungstext, umsatzart)
            tx_hash      = make_hash(account_id, booking_date, amount, buchungstext)

            raw = {
                "buchungstag":  row.get("Buchungstag", ""),
                "wertstellung": row.get("Wertstellung", ""),
                "umsatzart":    umsatzart,
                "buchungstext": buchungstext,
                "betrag":       row.get("Betrag", ""),
                "waehrung":     currency,
                "iban":         row.get("IBAN Kontoinhaber", ""),
                "kategorie":    row.get("Kategorie", ""),
            }
        except (ValueError, KeyError) as e:
            print(f"  Zeile übersprungen (Parsing-Fehler): {e}")
            errors += 1
            continue

        label = (f"{booking_date}  {float(amount):>10.2f} {currency}  "
                 f"{counterpart[:30]:30}  {umsatzart[:25]}")

        if dry_run:
            print(f"  -> {label}")
            print(f"       {buchungstext[:100]}")
            inserted += 1
            continue

        cur.execute(
            """
            INSERT INTO transactions
                (account_id, booking_date, value_date, amount, currency,
                 counterpart_name, purpose, import_source, raw_data, tx_hash)
            VALUES (%s, %s, %s, %s, %s, %s, %s, 'commerzbank_csv', %s, %s)
            ON CONFLICT (tx_hash) DO NOTHING
            """,
            (
                account_id,
                booking_date,
                value_date,
                float(amount),
                currency,
                counterpart,
                buchungstext,
                Json(raw),
                tx_hash,
            ),
        )

        if cur.rowcount == 0:
            duplicate += 1
            print(f"  Dublette: {label}")
        else:
            inserted += 1
            print(f"  OK  {label}")

    if not dry_run:
        conn.commit()
        cur.close()
        conn.close()

    print(f"\n{'DRY-RUN ' if dry_run else ''}Ergebnis:")
    print(f"  Importiert:   {inserted}")
    print(f"  Dubletten:    {duplicate}")
    print(f"  Übersprungen: {skipped}")
    if errors:
        print(f"  Fehler:       {errors}")


def main():
    ap = argparse.ArgumentParser(description="Commerzbank CSV-Import in BHL transactions.")
    ap.add_argument("file",                        help="Commerzbank CSV-Datei")
    ap.add_argument("account_id", type=int,        help="account_id des Bankkontos in der Datenbank")
    ap.add_argument("--dry-run",  action="store_true", help="Nur anzeigen, nichts schreiben")
    args = ap.parse_args()

    import_commerzbank_csv(args.file, args.account_id, args.dry_run)


if __name__ == "__main__":
    main()
