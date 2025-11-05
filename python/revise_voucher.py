#!/usr/bin/env python3
"""
revise_voucher.py
Revision, Anzeige und Kontrolle von Belegen:
• Änderungen, Storno, Historie
• revisionssichere Protokollierung
• Anzeige (--show) inkl. Öffnen der PDF-Datei (falls vorhanden)
"""

import argparse
import os
import subprocess
from datetime import datetime
from db import get_connection


def log_revision(cur, entity, entity_id, action, field=None, old_value=None, new_value=None, reason=None):
    cur.execute("""
        INSERT INTO audit_log (entity, entity_id, action, field, old_value, new_value, reason, changed_at)
        VALUES (%s,%s,%s,%s,%s,%s,%s,NOW());
    """, (entity, entity_id, action, field, old_value, new_value, reason))


def open_pdf(voucher_id, outgoing=False):
    """Versucht, das PDF des Belegs zu öffnen."""
    conn = get_connection()
    cur = conn.cursor()
    table = "outgoing_documents" if outgoing else "voucher_documents"
    cur.execute(f"""
        SELECT file_path, file_name
          FROM {table}
         WHERE { 'outgoing_id' if outgoing else 'voucher_id' } = %s
         ORDER BY id DESC LIMIT 1;
    """, (voucher_id,))
    row = cur.fetchone()
    conn.close()

    if not row:
        print("📄 Kein zugehöriges PDF-Dokument gefunden.")
        return

    file_path, file_name = row
    pdf_path = os.path.join(file_path or "", file_name or "")
    if not os.path.exists(pdf_path):
        print(f"⚠️  PDF-Datei nicht gefunden: {pdf_path}")
        return

    print(f"📂 Öffne PDF: {pdf_path}")
    try:
        subprocess.Popen(["xdg-open", pdf_path])
    except Exception as e:
        print(f"⚠️  Konnte PDF nicht öffnen: {e}")


def show_voucher(voucher_id, outgoing=False):
    """Zeigt den vollständigen Belegdatensatz und öffnet ggf. das PDF."""
    table = "outgoing_vouchers" if outgoing else "vouchers"
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(f"SELECT * FROM {table} WHERE id=%s;", (voucher_id,))
    row = cur.fetchone()
    if not row:
        print(f"❌ Beleg {voucher_id} nicht gefunden in {table}.")
        conn.close()
        return

    colnames = [desc[0] for desc in cur.description]
    print(f"📄 Aktueller Stand von Beleg {voucher_id} ({table}):\n")
    for col, val in zip(colnames, row):
        if isinstance(val, datetime):
            val = val.strftime("%Y-%m-%d %H:%M")
        print(f"  {col:20s}: {val}")
    cur.close()
    conn.close()

    # PDF anzeigen, falls vorhanden
    open_pdf(voucher_id, outgoing)


def cancel_voucher(voucher_id, reason, outgoing=False):
    table = "outgoing_vouchers" if outgoing else "vouchers"
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(f"SELECT status FROM {table} WHERE id=%s;", (voucher_id,))
    row = cur.fetchone()
    if not row:
        print("❌ Beleg nicht gefunden.")
        conn.close()
        return

    old_status = row[0]
    if old_status == "cancelled":
        print("⚠️  Beleg ist bereits storniert.")
        conn.close()
        return

    cur.execute(f"UPDATE {table} SET status='cancelled' WHERE id=%s;", (voucher_id,))
    log_revision(cur, table, voucher_id, "cancelled",
                 field="status", old_value=old_status, new_value="cancelled", reason=reason)
    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Beleg {voucher_id} ({table}) wurde storniert.")


def update_field(voucher_id, field, new_value, reason, outgoing=False):
    table = "outgoing_vouchers" if outgoing else "vouchers"
    conn = get_connection()
    cur = conn.cursor()

    cur.execute(f"SELECT {field} FROM {table} WHERE id=%s;", (voucher_id,))
    row = cur.fetchone()
    if not row:
        print("❌ Beleg nicht gefunden oder Feld ungültig.")
        conn.close()
        return

    old_value = row[0]
    cur.execute(f"UPDATE {table} SET {field}=%s WHERE id=%s;", (new_value, voucher_id))
    log_revision(cur, table, voucher_id, "update", field, str(old_value), str(new_value), reason)
    conn.commit()
    cur.close()
    conn.close()
    print(f"✅ Feld '{field}' von Beleg {voucher_id} aktualisiert: '{old_value}' → '{new_value}'")


def show_history(voucher_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT entity, action, field, old_value, new_value, reason, changed_at
          FROM audit_log
         WHERE entity_id=%s
         ORDER BY changed_at;
    """, (voucher_id,))
    rows = cur.fetchall()
    if not rows:
        print(f"ℹ️  Keine Änderungen für Beleg-ID {voucher_id} gefunden.")
    else:
        print(f"📜 Revisionshistorie für Beleg-ID {voucher_id}:\n")
        for entity, action, field, old, new, reason, ts in rows:
            f = f"Feld: {field}" if field else ""
            r = f"Grund: {reason}" if reason else ""
            print(f"🕒 {ts:%Y-%m-%d %H:%M} | {action.upper():10s} | {f:20s} | {old or '-'} → {new or '-'} | {r}")
    cur.close()
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="Revisionssichere Bearbeitung und Anzeige von Belegen.")
    ap.add_argument("--id", type=int, required=True, help="Beleg-ID")
    ap.add_argument("--outgoing", action="store_true", help="Für Ausgangsbeleg statt Eingangsbeleg")
    ap.add_argument("--cancel", help="Storniert den Beleg mit Begründung")
    ap.add_argument("--field", help="Zu änderndes Feld")
    ap.add_argument("--new", help="Neuer Feldwert")
    ap.add_argument("--reason", help="Begründung für Änderung")
    ap.add_argument("--show-history", action="store_true", help="Zeigt Änderungsverlauf an")
    ap.add_argument("--show", action="store_true", help="Zeigt den aktuellen Belegdatensatz an und öffnet das PDF")
    args = ap.parse_args()

    if args.show:
        show_voucher(args.id, outgoing=args.outgoing)
        return

    if args.show_history:
        show_history(args.id)
        return

    if args.cancel:
        cancel_voucher(args.id, args.cancel, outgoing=args.outgoing)
        return

    if args.field and args.new:
        update_field(args.id, args.field, args.new, args.reason or "Korrektur", outgoing=args.outgoing)
        return

    print("❌ Keine Aktion angegeben. Verwende --show, --cancel, --field/--new oder --show-history.")


if __name__ == "__main__":
    main()
