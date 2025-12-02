#!/usr/bin/env python3
"""
manage_auto_rules.py
--------------------
Verwaltet automatische Kontierungsregeln (auto_rules).

Verwendung:
  ./python/manage_auto_rules.py --list
  ./python/manage_auto_rules.py --add --pattern "Telefonica" --direction incoming --account 4920 --tax 19 --note "Telefonie"
  ./python/manage_auto_rules.py --edit 3 --account 4905 --note "Hosting (aktualisiert)"
  ./python/manage_auto_rules.py --delete 4
"""

import argparse
from tabulate import tabulate
from db import get_connection


def list_rules(with_flags=False):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, match_pattern, direction, account_skr, tax_rate, tax_type, description, created_at
          FROM auto_rules
         ORDER BY direction, match_pattern;
    """)
    rows = cur.fetchall()
    if not rows:
        print("⚠️  Keine Regeln vorhanden.")
    else:
        headers = ["ID", "Muster", "Richtung", "Konto", "Steuer%", "Typ", "Beschreibung", "Angelegt"]
        print(tabulate(rows, headers=headers, tablefmt="psql"))
    cur.close()
    conn.close()


def add_rule(args):
    conn = get_connection()
    cur = conn.cursor()

    if not args.pattern or not args.direction or not args.account:
        print("❌ Für --add sind --pattern, --direction und --account erforderlich.")
        return

    tax = args.tax or 19.0
    note = args.note or None
    cur.execute("""
        INSERT INTO auto_rules (match_pattern, direction, account_skr, tax_rate, description)
        VALUES (%s, %s, %s, %s, %s)
        RETURNING id;
    """, (args.pattern, args.direction, args.account, tax, note))
    rid, = cur.fetchone()
    conn.commit()
    print(f"✅ Regel {rid} hinzugefügt: {args.pattern} → Konto {args.account}")
    cur.close()
    conn.close()


def edit_rule(args):
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT id FROM auto_rules WHERE id = %s;", (args.edit,))
    if not cur.fetchone():
        print(f"❌ Regel mit ID {args.edit} nicht gefunden.")
        return

    updates = []
    params = []
    if args.pattern:
        updates.append("match_pattern = %s")
        params.append(args.pattern)
    if args.direction:
        updates.append("direction = %s")
        params.append(args.direction)
    if args.account:
        updates.append("account_skr = %s")
        params.append(str(args.account))
    if args.tax:
        updates.append("tax_rate = %s")
        params.append(args.tax)
    if args.note:
        updates.append("description = %s")
        params.append(args.note)

    if not updates:
        print("⚠️  Keine Änderungen angegeben.")
        return

    params.append(args.edit)
    cur.execute(f"UPDATE auto_rules SET {', '.join(updates)} WHERE id = %s;", params)
    conn.commit()
    print(f"✅ Regel {args.edit} aktualisiert.")
    cur.close()
    conn.close()


def delete_rule(rule_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM auto_rules WHERE id = %s RETURNING id;", (rule_id,))
    if cur.rowcount:
        conn.commit()
        print(f"🗑️  Regel {rule_id} gelöscht.")
    else:
        print(f"⚠️  Regel {rule_id} nicht gefunden.")
    cur.close()
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="Verwalte automatische Kontierungsregeln (auto_rules).")
    ap.add_argument("--list", action="store_true", help="Listet alle Regeln auf")
    ap.add_argument("--add", action="store_true", help="Neue Regel anlegen")
    ap.add_argument("--edit", type=int, help="Regel bearbeiten (nach ID)")
    ap.add_argument("--delete", type=int, help="Regel löschen (nach ID)")

    # gemeinsame Argumente
    ap.add_argument("--pattern", help="Suchmuster (z. B. 'Telefonica')")
    ap.add_argument("--direction", choices=["incoming", "outgoing"], help="Richtung des Belegs")
    ap.add_argument("--account", type=str, help="SKR03-Konto")
    ap.add_argument("--tax", type=float, help="Steuersatz in Prozent")
    ap.add_argument("--note", help="Kommentar / Beschreibung")

    args = ap.parse_args()

    if args.list:
        list_rules()
    elif args.add:
        add_rule(args)
    elif args.edit:
        edit_rule(args)
    elif args.delete:
        delete_rule(args.delete)
    else:
        ap.print_help()


if __name__ == "__main__":
    main()
