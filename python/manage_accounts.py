#!/usr/bin/env python3
"""
manage_accounts.py
Verwaltet SKR03-Konten: Anzeigen, Suchen, Anlegen.
"""

import argparse
from db import get_connection

def list_accounts():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id, name, default_tax, category, is_expense, is_revenue FROM skr03_accounts ORDER BY id;")
    rows = cur.fetchall()
    for r in rows:
        print(f"{r[0]:6s} | {r[1]:40s} | {r[2]:>4.0f}% | {r[3]:10s} | {'A' if r[4] else ' '} {'E' if r[5] else ' '}")
    cur.close(); conn.close()

def search_accounts(term):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT id, name FROM skr03_accounts WHERE id ILIKE %s OR name ILIKE %s ORDER BY id;",
                (f"%{term}%", f"%{term}%"))
    rows = cur.fetchall()
    if not rows:
        print("Keine Treffer."); return
    for r in rows:
        print(f"{r[0]:6s} | {r[1]}")
    cur.close(); conn.close()

def add_account(id, name, tax, cat):
    conn = get_connection(); cur = conn.cursor()
    cur.execute("""
        INSERT INTO skr03_accounts (id, name, default_tax, category,
                                    is_expense, is_revenue)
        VALUES (%s,%s,%s,%s,
                (CASE WHEN %s='Aufwand' THEN TRUE ELSE FALSE END),
                (CASE WHEN %s='Erlös' THEN TRUE ELSE FALSE END))
        ON CONFLICT (id) DO UPDATE
            SET name=EXCLUDED.name, default_tax=EXCLUDED.default_tax, category=EXCLUDED.category;
    """, (id, name, tax, cat, cat, cat))
    conn.commit(); cur.close(); conn.close()
    print(f"✅ Konto {id} ({name}) gespeichert.")

if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Verwaltet SKR03-Konten.")
    ap.add_argument("--list", action="store_true", help="Alle Konten anzeigen")
    ap.add_argument("--search", help="Nach Text oder Nummer suchen")
    ap.add_argument("--add", nargs=4, metavar=("ID","NAME","TAX","CAT"),
                    help="Neues Konto anlegen: ID NAME TAX Kategorie(Aufwand/Erlös)")
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
