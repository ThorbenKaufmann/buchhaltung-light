#!/usr/bin/env python3
"""
batch_import_mt940.py
Batch-Importer für MT940-Dateien.

- Liest alle *.mt940 Dateien aus einem angegebenen Verzeichnis
- Führt import_mt940_file() für jede Datei aus
- Verschiebt importierte Dateien nach imported/
- Überspringt leere oder bereits verschobene Dateien
"""

import os
import sys
import shutil
from import_mt940 import import_mt940_file


def batch_import_mt940(import_dir: str, account_id: int):
    if not os.path.isdir(import_dir):
        raise FileNotFoundError(f"Verzeichnis {import_dir} existiert nicht.")

    imported_dir = os.path.join(import_dir, "imported")
    os.makedirs(imported_dir, exist_ok=True)

    # Dateien auflisten
    files = sorted(
        f for f in os.listdir(import_dir)
        if f.lower().endswith(".mta") and os.path.isfile(os.path.join(import_dir, f))
    )

    if not files:
        print(f"Keine MT940-Dateien im Verzeichnis {import_dir} gefunden.")
        return

    print(f"{len(files)} Datei(en) gefunden – Import startet …\n")

    for filename in files:
        full_path = os.path.join(import_dir, filename)
        try:
            print(f"==> Importiere {filename}")
            import_mt940_file(full_path, account_id)

            target_path = os.path.join(imported_dir, filename)
            shutil.move(full_path, target_path)
            print(f"   ✓ Verschoben nach {target_path}\n")

        except Exception as e:
            print(f"   ⚠️  Fehler bei {filename}: {e}\n")
            # Du kannst fehlerhafte Dateien auch in ein error/-Verzeichnis verschieben:
            # error_dir = os.path.join(import_dir, "error")
            # os.makedirs(error_dir, exist_ok=True)
            # shutil.move(full_path, os.path.join(error_dir, filename))

    print("\nBatch-Import abgeschlossen.")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Verwendung: python batch_import_mt940.py <verzeichnis> <account_id>")
        sys.exit(1)

    batch_import_mt940(sys.argv[1], int(sys.argv[2]))
