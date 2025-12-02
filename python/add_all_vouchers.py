#!/usr/bin/env python3
"""
add_all_vouchers.py
Batch-Importer für Belege (Eingang oder Ausgang).

Verarbeitet alle PDF-Dateien in einem Quellverzeichnis und ruft
bhl_voucher_base.process_voucher() für jede Datei auf.

Beispiel:
    python add_all_vouchers.py ./backlog/in ./belege --direction incoming
    python add_all_vouchers.py ./backlog/out ./belege/ausgang --direction outgoing
    python add_all_vouchers.py ./backlog/mixed ./belege --direction auto
"""

import os
import sys
import argparse
import traceback
from bhl_voucher_base import process_voucher


def add_all_vouchers(source_dir: str, base_dir: str, direction: str):
    """Verarbeitet alle PDF-Dateien in einem Verzeichnis."""
    if not os.path.isdir(source_dir):
        print(f"❌ Quellverzeichnis nicht gefunden: {source_dir}")
        sys.exit(1)

    pdfs = [
        os.path.join(source_dir, f)
        for f in sorted(os.listdir(source_dir))
        if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(source_dir, f))
    ]

    if not pdfs:
        print(f"Keine PDF-Dateien im Verzeichnis {source_dir} gefunden.")
        return

    print(f"{len(pdfs)} Datei(en) gefunden – Starte Stapelverarbeitung ({direction}).\n")

    for idx, path in enumerate(pdfs, 1):
        print("=" * 70)
        print(f"[{idx}/{len(pdfs)}] Beleg: {os.path.basename(path)}")
        print("=" * 70)
        try:
            process_voucher(path, base_dir, mode=direction)
        except KeyboardInterrupt:
            print("\n⏹  Vom Benutzer abgebrochen.")
            sys.exit(0)
        except Exception as e:
            print(f"⚠️  Fehler bei {os.path.basename(path)}: {e}")
            traceback.print_exc()
            print("\n--- Nächster Beleg ---\n")

    print("\n✅ Stapelverarbeitung abgeschlossen.")


def main():
    ap = argparse.ArgumentParser(
        description="Batch-Importer für Eingangs- oder Ausgangsbelege (ZUGFeRD/XRechnung-fähig)."
    )
    ap.add_argument("source_dir", help="Quellverzeichnis mit PDF-Dateien")
    ap.add_argument("base_dir", help="Zielbasis (z. B. ./belege oder ./belege/ausgang)")
    ap.add_argument(
        "--direction",
        choices=["incoming", "outgoing", "auto"],
        default="incoming",
        help="Richtung der Belege: incoming, outgoing oder auto (Standard: incoming)",
    )

    args = ap.parse_args()
    add_all_vouchers(args.source_dir, args.base_dir, args.direction)


if __name__ == "__main__":
    main()
