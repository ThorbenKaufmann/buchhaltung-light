#!/usr/bin/env python3
"""
remove_voucher.py
Entfernt einen Beleg (incoming oder outgoing) aus der Datenbank und verschiebt die PDF-Dateien
an einen Zielpfad (z. B. ./removed/ oder ./backlog/recheck/).

Beispiel:
    python3 python/remove_voucher.py --id 42 --direction incoming --target ./removed
"""

import argparse
import os
import shutil
from datetime import datetime
from db import get_connection

def get_voucher_info(cur, voucher_id, direction):
    """Liefert Beleginformationen inkl. Dateipfade."""
    if direction == "outgoing":
        table = "outgoing_vouchers"
        doc_table = "outgoing_voucher_documents"
        id_field = "outgoing_id"
    else:
        table = "vouchers"
        doc_table = "voucher_documents"
        id_field = "voucher_id"

    cur.execute(f"""
        SELECT v.id, v.voucher_number, v.partner_name, v.voucher_date, d.file_path, d.file_name
          FROM {table} v
          LEFT JOIN {doc_table} d ON v.id = d.{id_field}
         WHERE v.id=%s;
    """, (voucher_id,))
    return cur.fetchall()

def remove_voucher(voucher_id, direction, target_dir):
    conn = get_connection()
    cur = conn.cursor()

    info = get_voucher_info(cur, voucher_id, direction)
    if not info:
        print(f"❌ Kein Beleg mit ID {voucher_id} gefunden.")
        conn.close()
        return

    # Anzeigen
    print("\nBeleginformationen:")
    for vid, number, name, vdate, path, fname in info:
        print(f"  ID: {vid} | Nr: {number or '-'} | {name or '-'} | {vdate or '-'}")
        if path and fname:
            print(f"  Datei: {os.path.join(path, fname)}")

    confirm = input("\nBeleg wirklich entfernen? [y/N]: ").strip().lower()
    if confirm != "y":
        print("❎ Abgebrochen.")
        conn.close()
        return

    # Zielverzeichnis vorbereiten
    os.makedirs(target_dir, exist_ok=True)

    # Dateien verschieben
    for _, _, _, _, fpath, fname in info:
        if not fpath or not fname:
            continue
        src = os.path.join(fpath, fname)
        if not os.path.exists(src):
            print(f"⚠️  Datei nicht gefunden: {src}")
            continue
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        dst = os.path.join(target_dir, f"{ts}_{fname}")
        shutil.move(src, dst)
        print(f"📦 Verschoben: {src} → {dst}")

    # DB-Einträge löschen
    if direction == "outgoing":
        table = "outgoing_vouchers"
        doc_table = "outgoing_voucher_documents"
        link_table = "outgoing_links"
        id_field = "outgoing_id"
    else:
        table = "vouchers"
        doc_table = "voucher_documents"
        link_table = "voucher_links"
        id_field = "voucher_id"

    cur.execute(f"DELETE FROM {link_table} WHERE {id_field}=%s;", (voucher_id,))
    cur.execute(f"DELETE FROM {doc_table} WHERE {id_field}=%s;", (voucher_id,))
    cur.execute(f"DELETE FROM {table} WHERE id=%s;", (voucher_id,))
    conn.commit()
    conn.close()

    print(f"✅ Beleg {voucher_id} und zugehörige Dateien erfolgreich entfernt.\n")


def main():
    ap = argparse.ArgumentParser(description="Entfernt einen Beleg aus Datenbank und Dateisystem.")
    ap.add_argument("--id", type=int, required=True, help="Beleg-ID")
    ap.add_argument("--direction", choices=["incoming", "outgoing"], default="incoming",
                    help="Belegrichtung (incoming oder outgoing)")
    ap.add_argument("--target", required=True, help="Zielverzeichnis für entfernte Dateien (z. B. ./removed)")
    args = ap.parse_args()

    remove_voucher(args.id, args.direction, args.target)


if __name__ == "__main__":
    main()
