#!/usr/bin/env python3
"""
manage_booking_rules.py
Verwalte booking_rules mit CRUD-Funktionen (create, read, update, delete)
inkl. Flags: is_internal, is_private, is_cyclic.
"""

import argparse
from tabulate import tabulate
from db import get_connection


def list_rules(show_flags=False):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, pattern, direction, default_account, default_tax, note,
               is_internal, is_private, is_cyclic
          FROM booking_rules
         ORDER BY id;
    """)
    rows = cur.fetchall()
    conn.close()

    if not rows:
        print("ℹ️  Keine Buchungsregeln vorhanden.")
        return

    headers = ["ID", "Pattern", "Richtung", "Konto", "Steuersatz", "Kommentar", "Intern", "Privat", "Zyklisch"]
    if not show_flags:
        rows = [r[:6] for r in rows]
        headers = headers[:6]
    print(tabulate(rows, headers=headers, tablefmt="github"))


def add_rule(pattern, direction, account, default_tax, note,
             is_internal, is_private, is_cyclic):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO booking_rules
            (pattern, direction, default_account, default_tax, note,
             is_internal, is_private, is_cyclic)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        RETURNING id;
    """, (pattern, direction, account, default_tax, note,
          is_internal, is_private, is_cyclic))
    rid = cur.fetchone()[0]
    conn.commit()
    conn.close()
    print(f"✅ Neue Regel #{rid} hinzugefügt: '{pattern}' → Konto {account}")


def delete_rule(rule_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM booking_rules WHERE id=%s RETURNING id;", (rule_id,))
    deleted = cur.fetchone()
    conn.commit()
    conn.close()
    if deleted:
        print(f"🗑️  Regel #{rule_id} gelöscht.")
    else:
        print(f"⚠️  Keine Regel mit ID {rule_id} gefunden.")


def edit_rule(rule_id, **kwargs):
    """Aktualisiert einzelne Felder einer Regel"""
    allowed = {
        "pattern": "pattern",
        "direction": "direction",
        "account": "default_account",
        "tax": "default_tax",
        "note": "note",
        "internal": "is_internal",
        "private": "is_private",
        "cyclic": "is_cyclic"
    }
    sets, values = [], []
    for key, val in kwargs.items():
        if key not in allowed or val is None:
            continue
        sets.append(f"{allowed[key]} = %s")
        values.append(val)

    if not sets:
        print("⚠️  Keine gültigen Änderungsparameter übergeben.")
        return

    conn = get_connection()
    cur = conn.cursor()
    sql = f"UPDATE booking_rules SET {', '.join(sets)} WHERE id=%s RETURNING id;"
    cur.execute(sql, (*values, rule_id))
    updated = cur.fetchone()
    conn.commit()
    conn.close()

    if updated:
        print(f"✏️  Regel #{rule_id} erfolgreich aktualisiert.")
    else:
        print(f"⚠️  Regel #{rule_id} nicht gefunden.")


def main():
    ap = argparse.ArgumentParser(description="Verwalte Buchungsregeln (booking_rules).")
    ap.add_argument("--list", action="store_true", help="Listet alle Regeln auf")
    ap.add_argument("--list-flags", action="store_true", help="Listet Regeln mit Flags auf")
    ap.add_argument("--add", action="store_true", help="Neue Regel anlegen")
    ap.add_argument("--delete", type=int, help="Regel löschen (nach ID)")
    ap.add_argument("--edit", type=int, help="Regel bearbeiten (nach ID)")

    # gemeinsame Argumente
    ap.add_argument("--pattern", help="Suchmuster")
    ap.add_argument("--direction", choices=["incoming", "outgoing"])
    ap.add_argument("--account", type=int, help="SKR03-Konto")
    ap.add_argument("--tax", type=float, help="Steuersatz")
    ap.add_argument("--note", help="Kommentar / Beschreibung")
    ap.add_argument("--internal", type=lambda x: x.lower() in ["true", "1", "yes", "y"],
                    help="Flag is_internal setzen (true/false)")
    ap.add_argument("--private", type=lambda x: x.lower() in ["true", "1", "yes", "y"],
                    help="Flag is_private setzen (true/false)")
    ap.add_argument("--cyclic", type=lambda x: x.lower() in ["true", "1", "yes", "y"],
                    help="Flag is_cyclic setzen (true/false)")

    args = ap.parse_args()

    if args.list or args.list_flags:
        list_rules(show_flags=args.list_flags)
    elif args.add:
        if not (args.pattern and args.direction and args.account):
            print("❌ Fehlende Parameter: --pattern, --direction und --account sind erforderlich.")
            return
        add_rule(args.pattern, args.direction, args.account, args.tax or 0.0,
                 args.note or "", bool(args.internal), bool(args.private), bool(args.cyclic))
    elif args.delete:
        delete_rule(args.delete)
    elif args.edit:
        edit_rule(
            args.edit,
            pattern=args.pattern,
            direction=args.direction,
            account=args.account,
            tax=args.tax,
            note=args.note,
            internal=args.internal,
            private=args.private,
            cyclic=args.cyclic,
        )
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
