#!/usr/bin/env python3
"""
AfA Apply Tool
--------------
Erzeugt automatisch jährliche Abschreibungsbuchungen (AfA) aus `vw_afa_schedule`.

Verwendung:
    ./python/reporting/afa_apply.py --year 2025 --dry-run
    ./python/reporting/afa_apply.py --year 2025 --commit
"""

import argparse
from decimal import Decimal
import sys
from pathlib import Path


# Pfadkorrektur für Direktaufruf
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from db import get_connection

def get_afa_entries(year: int):
    """Liest alle AfA-Datensätze aus der View für das angegebene Jahr."""
    conn = get_connection()
    cur = conn.cursor()
    sql = """
        SELECT id, asset_name, account_skr, afa_jahr, jahr
        FROM vw_afa_schedule
        WHERE jahr = %s
        ORDER BY account_skr;
    """
    cur.execute(sql, (year,))
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def check_existing(year: int):
    """Prüft, ob für das Jahr bereits auto_afa-Buchungen vorhanden sind."""
    conn = get_connection()
    cur = conn.cursor()
    sql = """
        SELECT COUNT(*) 
        FROM booking_lines
        WHERE description ILIKE 'AfA%%'
          AND EXTRACT(YEAR FROM created_at) = %s
          AND receipt_status = 'complete'
          AND tax_type = 'vst0';
    """
    cur.execute(sql, (year,))
    row = cur.fetchone()
    cnt = row["count"] if row and "count" in row else 0
    cur.close()
    conn.close()
    return cnt


def apply_afa(year: int, dry_run=True):
    """Erzeugt AfA-Buchungen (Simulation oder Echtlauf) und aktualisiert Status."""
    rows = get_afa_entries(year)
    if not rows:
        print(f"Keine AfA-Einträge für {year} gefunden.")
        return

    existing = check_existing(year)
    if existing > 0:
        print(f"⚠️  Es existieren bereits {existing} auto_afa-Buchungen für {year}. Abbruch!")
        return

    print(f"\nGefundene AfA-Einträge für {year}: {len(rows)}")
    for r in rows:
        print(f"- {r['asset_name']:<35} Konto {r['account_skr']:<6} AfA: {r['afa_jahr']:>10.2f} EUR")

    if dry_run:
        print("\n--dry-run aktiviert: Es wurden keine Buchungen angelegt.")
        return

    conn = get_connection()
    cur = conn.cursor()
    try:
        for r in rows:
            # AfA-Buchung anlegen
            cur.execute("""
                INSERT INTO booking_lines (
                    direction, account_skr, description, net_amount, tax_rate,
                    tax_amount, gross_amount, created_at, receipt_status, tax_type
                ) VALUES (
                    'incoming', %s, %s, %s, 0, 0, %s, NOW(), 'complete', 'vst0'
                )
            """, (
                '4830',
                f"AfA {r['asset_name']} {r['jahr']}",
                Decimal(r['afa_jahr']),
                Decimal(r['afa_jahr'])
            ))

            # Status in depreciations aktualisieren
            cur.execute("""
                UPDATE depreciations
                   SET last_afa_year = %s,
                       last_afa_run  = NOW()
                 WHERE id = %s;
            """, (year, r['id']))

        conn.commit()
        print(f"✅ {len(rows)} AfA-Buchungen für {year} wurden erzeugt und Status aktualisiert.")
    except Exception as e:
        conn.rollback()
        print(f"❌ Fehler: {e}")
    finally:
        cur.close()
        conn.close()


def main():
    parser = argparse.ArgumentParser(description="AfA Apply Tool – automatische Abschreibungsbuchungen")
    parser.add_argument("--year", required=True, type=int, help="Jahr der Abschreibungen")
    parser.add_argument("--dry-run", action="store_true", help="Nur anzeigen, keine Inserts ausführen")
    parser.add_argument("--commit", action="store_true", help="Echte Inserts ausführen")
    args = parser.parse_args()

    dry = not args.commit  # Standard: dry-run

    apply_afa(args.year, dry_run=dry)


if __name__ == "__main__":
    main()
