#!/usr/bin/env python3
"""
add_all_outgoing_vouchers.py
Batch-Importer für Ausgangsrechnungen.

Liest alle PDF-Dateien in einem angegebenen Verzeichnis
und übergibt sie nacheinander an add_outgoing_voucher.py.
"""

import os
import sys
import traceback
from add_outgoing_voucher import add_outgoing_voucher

def add_all_outgoing_vouchers(source_dir: str, base_dir: str):
    """Verarbeitet alle PDF-Dateien im Verzeichnis."""
    if not os.path.isdir(source_dir):
        print(f"❌ Quellverzeichnis nicht gefunden: {source_dir}")
        sys.exit(1)

    pdfs = [
        os.path.join(source_dir, f)
        for f in sorted(os.listdir(source_dir))
        if f.lower().endswith(".pdf")
    ]

    print(f"{len(pdfs)} Datei(en) gefunden – Starte Stapelverarbeitung.\n")

    for idx, path in enumerate(pdfs, 1):
        print("=" * 70)
        print(f"[{idx}/{len(pdfs)}] Beleg: {os.path.basename(path)}")
        print("=" * 70)
        try:
            add_outgoing_voucher(path, base_dir)
        except KeyboardInterrupt:
            print("\n⏹  Vom Benutzer abgebrochen.")
            sys.exit(0)
        except Exception as e:
            print(f"⚠️  Fehler bei {os.path.basename(path)}: {e}")
            traceback.print_exc()
            print("\n--- Nächster Beleg ---\n")

    print("\n✅ Stapelverarbeitung abgeschlossen.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Verwendung: python add_all_outgoing_vouchers.py <quellverzeichnis> <basisverzeichnis>")
        sys.exit(1)

    add_all_outgoing_vouchers(sys.argv[1], sys.argv[2])
