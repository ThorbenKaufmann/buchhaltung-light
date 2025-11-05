#!/usr/bin/env python3
"""
add_all_vouchers.py
Stapelerfassung für Belege.

Liest alle PDF-Dateien in einem Quellverzeichnis und ruft für jede Datei das
add_voucher.py-Modul auf, um den Beleg interaktiv zu erfassen und in die DB einzutragen.

Verwendung:
    python add_all_vouchers.py <source_dir> <target_dir>
"""

import os
import sys
import traceback
from add_voucher import add_voucher


def add_all_vouchers(source_dir: str, target_dir: str):
    if not os.path.isdir(source_dir):
        print(f"❌ Quellverzeichnis nicht gefunden: {source_dir}")
        sys.exit(1)

    pdf_files = sorted(
        f for f in os.listdir(source_dir)
        if f.lower().endswith(".pdf") and os.path.isfile(os.path.join(source_dir, f))
    )

    if not pdf_files:
        print(f"Keine PDF-Dateien im Verzeichnis {source_dir} gefunden.")
        return

    print(f"{len(pdf_files)} Datei(en) gefunden – Starte Stapelverarbeitung.\n")

    for filename in pdf_files:
        full_path = os.path.join(source_dir, filename)
        print("=" * 70)
        print(f"Beleg: {filename}")
        print("=" * 70)
        try:
            add_voucher(full_path, target_dir)
        except KeyboardInterrupt:
            print("\nAbgebrochen durch Benutzer.")
            sys.exit(0)
        except Exception as e:
            print(f"⚠️  Fehler bei {filename}: {e}")
            traceback.print_exc()
        print("\n--- Nächster Beleg ---\n")

    print("✅ Stapelverarbeitung abgeschlossen.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Verwendung: python add_all_vouchers.py <source_dir> <target_dir>")
        sys.exit(1)

    source_dir = sys.argv[1]
    target_dir = sys.argv[2]
    add_all_vouchers(source_dir, target_dir)
