#!/usr/bin/env python3
"""
import_paypal_csv.py

Importiert PayPal-Kontoauszüge (CSV-Export aus paypal.com) in die
Tabelle 'transactions' mit account_id 3 (PayPal).

Verwendung:
    python3 python/import_paypal_csv.py secret/PayPal_2024.csv
    python3 python/import_paypal_csv.py secret/PayPal_2024.csv --dry-run
    python3 python/import_paypal_csv.py secret/PayPal_2024.csv --account-id 3

PayPal CSV-Export:
    paypal.com → Aktivitäten → Alle Transaktionen → Herunterladen → CSV

Übersprungen werden:
    - Bank Deposit to PP Account  (Banküberweisung an PayPal, bereits im MT940)
    - General Authorization        (Vorautorisation, kein Geldfluss)
    - Account Hold / Reversal      (Haltebeträge, kein tatsächlicher Abfluss)
    - General Currency Conversion  (interne FX-Umbuchung)
    - Status != Completed          (ausstehende oder rückgängig gemachte TXs)
    - Balance Impact == Memo       (keine Kontobewegung)
"""

import argparse
import csv
import hashlib
import sys
import os
from datetime import datetime
from decimal import Decimal, InvalidOperation
from psycopg2.extras import Json

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
from db import get_connection


SKIP_TYPES = {
    "Bank Deposit to PP Account",
    "General Authorization",
    "Account Hold for Open Authorization",
    "Reversal of General Account Hold",
    "General Currency Conversion",
}


def parse_amount(value: str) -> Decimal:
    """'−16,99' oder '16,99' → Decimal"""
    cleaned = value.strip().replace(".", "").replace(",", ".")
    try:
        return Decimal(cleaned)
    except InvalidOperation:
        raise ValueError(f"Ungültiger Betrag: {repr(value)}")


def parse_date(value: str) -> str:
    """'DD/MM/YYYY' → 'YYYY-MM-DD'"""
    return datetime.strptime(value.strip(), "%d/%m/%Y").strftime("%Y-%m-%d")


def build_purpose(row: dict) -> str:
    """Setzt den Verwendungszweck aus mehreren Feldern zusammen."""
    parts = [
        row.get("Type", "").strip(),
        row.get("Item Title", "").strip(),
        row.get("Subject", "").strip(),
        row.get("Note", "").strip(),
    ]
    return " – ".join(p for p in parts if p) or row.get("Type", "").strip()


def make_hash(account_id: int, transaction_id: str) -> str:
    """Stabiler Hash basierend auf der eindeutigen PayPal Transaction ID."""
    key = f"{account_id}|paypal|{transaction_id}"
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


def import_paypal_csv(filename: str, account_id: int, dry_run: bool = False):
    if not os.path.exists(filename):
        print(f"❌ Datei nicht gefunden: {filename}")
        sys.exit(1)

    with open(filename, encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)

    print(f"\nDatei: {filename}")
    print(f"Zeilen gesamt: {len(rows)}")
    if dry_run:
        print("⚠️  DRY-RUN — keine Datenbankänderungen\n")

    conn = get_connection() if not dry_run else None
    cur  = conn.cursor() if conn else None

    inserted    = 0
    skipped     = 0
    duplicate   = 0
    errors      = 0
    non_eur     = []

    for row in rows:
        tx_type   = row.get("Type", "").strip()
        status    = row.get("Status", "").strip()
        impact    = row.get("Balance Impact", "").strip()
        tx_id     = row.get("Transaction ID", "").strip()

        # --- Filter ---
        if tx_type in SKIP_TYPES:
            skipped += 1
            continue
        if status != "Completed":
            skipped += 1
            continue
        if impact == "Memo":
            skipped += 1
            continue

        try:
            booking_date  = parse_date(row["Date"])
            net_amount    = parse_amount(row["Net"])
            gross_amount  = parse_amount(row["Gross"])
            fee_amount    = parse_amount(row["Fee"])
            currency      = row.get("Currency", "EUR").strip()
            counterpart   = row.get("Name", "").strip() or row.get("To Email Address", "").strip()
            purpose       = build_purpose(row)
            tx_hash       = make_hash(account_id, tx_id)

            raw = {
                "transaction_id": tx_id,
                "type":           tx_type,
                "status":         status,
                "gross":          str(gross_amount),
                "fee":            str(fee_amount),
                "net":            str(net_amount),
                "from_email":     row.get("From Email Address", ""),
                "to_email":       row.get("To Email Address", ""),
                "item_title":     row.get("Item Title", ""),
                "invoice_number": row.get("Invoice Number", ""),
                "balance_impact": impact,
            }

        except (ValueError, KeyError) as e:
            print(f"  ❌ Zeile übersprungen (Parsing-Fehler): {e} — {row.get('Transaction ID','?')}")
            errors += 1
            continue

        if currency != "EUR":
            non_eur.append((booking_date, float(net_amount), currency, counterpart, tx_id))

        label = f"{booking_date}  {float(net_amount):>10.2f} {currency}  {counterpart[:35]:35}  {tx_type[:30]}"

        if dry_run:
            print(f"  → {label}")
            inserted += 1
            continue

        cur.execute(
            """
            INSERT INTO transactions
                (account_id, booking_date, amount, currency,
                 counterpart_name, purpose, import_source, raw_data, tx_hash)
            VALUES (%s, %s, %s, %s, %s, %s, 'paypal_csv', %s, %s)
            ON CONFLICT (tx_hash) DO NOTHING
            """,
            (
                account_id,
                booking_date,
                float(net_amount),
                currency,
                counterpart,
                purpose,
                Json(raw),
                tx_hash,
            ),
        )

        if cur.rowcount == 0:
            duplicate += 1
            print(f"  ⚠️  Dublette: {label}")
        else:
            inserted += 1
            print(f"  ✓  {label}")

    if not dry_run:
        conn.commit()
        cur.close()
        conn.close()

    print(f"\n{'DRY-RUN ' if dry_run else ''}Ergebnis:")
    print(f"  Importiert:   {inserted}")
    print(f"  Dubletten:    {duplicate}")
    print(f"  Übersprungen: {skipped}  (Bank Deposit, Pending, Memo, FX)")
    if errors:
        print(f"  Fehler:       {errors}")
    if non_eur:
        print(f"\n⚠️  Nicht-EUR Transaktionen ({len(non_eur)}) — Betrag in Originalwährung gespeichert:")
        for date, amt, cur_, name, txid in non_eur:
            print(f"    {date}  {amt:>10.2f} {cur_}  {name[:40]}  ({txid})")
        print("    → EUR-Äquivalent bitte manuell prüfen (Kreditkartenabrechnung / PayPal-Kontoauszug)")


def main():
    ap = argparse.ArgumentParser(description="PayPal CSV-Import in BHL transactions.")
    ap.add_argument("file",                       help="PayPal-CSV-Datei (UTF-8, paypal.com-Export)")
    ap.add_argument("--account-id", type=int, default=3, help="account_id für PayPal (Standard: 3)")
    ap.add_argument("--dry-run",    action="store_true",  help="Nur anzeigen, nichts schreiben")
    args = ap.parse_args()

    import_paypal_csv(args.file, args.account_id, args.dry_run)


if __name__ == "__main__":
    main()
