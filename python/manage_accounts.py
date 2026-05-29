#!/usr/bin/env python3
"""
manage_accounts.py
Verwaltet SKR03-Konten: Anzeigen, Suchen, Anlegen.
Erweitert um is_active, is_internal, Kategorie „Privat“ und „Neutral“.
"""

import argparse
from db import get_connection


def list_accounts():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, default_tax, category,
               is_expense, is_revenue, is_active, is_internal
          FROM skr03_accounts
         ORDER BY id;
    """)
    rows = cur.fetchall()
    cur.close()
    conn.close()

    print(" ID    | Name                                   | Tax | Kategorie    | Typ")
    print("-------+----------------------------------------+-----+--------------+-----------------------------------")
    for r in rows:
        typ_flags = []
        if r[4]: typ_flags.append("A" )  # Aufwand
        if r[5]: typ_flags.append("E" )  # Erlös
        if r[6]: typ_flags.append("ACT") # Aktivkonto
        if r[7]: typ_flags.append("INT") # Intern
        tax = r[2] if r[2] is not None else 0
        cat = r[3] or ""
        print(f"{r[0]:6s} | {r[1]:40s} | {tax:>4.0f}% | {cat:12s} | {' '.join(typ_flags)}")


def search_accounts(term):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        SELECT id, name, category
          FROM skr03_accounts
         WHERE id ILIKE %s OR name ILIKE %s
         ORDER BY id;
    """, (f"%{term}%", f"%{term}%"))
    rows = cur.fetchall()
    cur.close()
    conn.close()

    if not rows:
        print("Keine Treffer.")
        return

    for r in rows:
        print(f"{r[0]:6s} | {r[1]:40s} | {r[2]}")


def add_account(id, name, tax, cat):
    valid_categories = {
        "Aufwand", "Erlös", "Aktivkonto", "Passivkonto", "Steuer", "Privat", "Neutral", "Intern"
    }
    if cat not in valid_categories:
        raise ValueError(f"Ungültige Kategorie '{cat}'. Erlaubt: {', '.join(valid_categories)}")

    # Automatische Flag-Logik
    is_expense = cat == "Aufwand"
    is_revenue = cat == "Erlös"
    is_active  = cat in ("Aktivkonto", "Passivkonto")
    is_internal = cat in ("Intern", "Privat", "Neutral")

    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        INSERT INTO skr03_accounts (
            id, name, default_tax, category,
            is_expense, is_revenue, is_active, is_internal
        )
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s)
        ON CONFLICT (id) DO UPDATE
        SET name = EXCLUDED.name,
            default_tax = EXCLUDED.default_tax,
            category = EXCLUDED.category,
            is_expense = EXCLUDED.is_expense,
            is_revenue = EXCLUDED.is_revenue,
            is_active = EXCLUDED.is_active,
            is_internal = EXCLUDED.is_internal;
    """, (id, name, tax, cat, is_expense, is_revenue, is_active, is_internal))
    conn.commit()
    cur.close()
    conn.close()

    print(f"✅ Konto {id} ({name}) gespeichert – Kategorie: {cat}")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Verwaltet SKR03-Konten.")
    ap.add_argument("--list", action="store_true", help="Alle Konten anzeigen")
    ap.add_argument("--search", help="Nach Text oder Nummer suchen")
    ap.add_argument("--add", nargs=4, metavar=("ID", "NAME", "TAX", "CAT"),
                    help="Neues Konto anlegen: ID NAME TAX Kategorie "
                         "(Aufwand/Erlös/Aktivkonto/Passivkonto/Steuer/Privat/Neutral/Intern)")
    args = ap.parse_args()

    if args.list:
        list_accounts()
    elif args.search:
        search_accounts(args.search)
    elif args.add:
        id, name, tax, cat = args.add
        add_account(id, name, float(tax), cat)
    else:
        ap.print_help()
