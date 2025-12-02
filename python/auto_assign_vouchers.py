#!/usr/bin/env python3
"""
auto_assign_vouchers.py
-----------------------
Erzeugt automatisch Buchungszeilen (voucher_lines / outgoing_lines)
für Belege anhand von Regeln in auto_rules.
"""

import re
from db import get_connection


def auto_assign_vouchers(dry_run=False):
    conn = get_connection()
    cur = conn.cursor()

    # Regeln laden
    cur.execute("""
        SELECT id, match_pattern, direction, account_skr, tax_rate, tax_type, description
          FROM auto_rules;
    """)
    rules = cur.fetchall()
    if not rules:
        print("⚠️  Keine Regeln in auto_rules gefunden.")
        return
    print(f"📜 {len(rules)} Regeln geladen.\n")

    # Eingangsbelege ohne Zeilen
    cur.execute("""
        SELECT id, partner_name, voucher_number, total_amount
          FROM vouchers
         WHERE id NOT IN (SELECT DISTINCT voucher_id FROM voucher_lines)
         ORDER BY voucher_date;
    """)
    incoming = [(r[0], r[1], r[2], r[3], "incoming") for r in cur.fetchall()]

    # Ausgangsbelege ohne Zeilen
    cur.execute("""
        SELECT id, partner_name, voucher_number, total_amount
          FROM outgoing_vouchers
         WHERE id NOT IN (SELECT DISTINCT outgoing_id FROM outgoing_lines)
         ORDER BY voucher_date;
    """)
    outgoing = [(r[0], r[1], r[2], r[3], "outgoing") for r in cur.fetchall()]

    vouchers = incoming + outgoing
    if not vouchers:
        print("✅ Keine unkontierten Belege gefunden.")
        cur.close()
        conn.close()
        return

    affected = 0

    for vid, pname, vnum, total, direction in vouchers:
        matched = False
        for rid, pattern, rdir, acc, rate, ttype, desc in rules:
            if rdir != direction:
                continue
            if pname and re.search(pattern, pname, re.IGNORECASE):
                matched = True
                print(f"💡 Regel {pattern!r} → {acc} ({desc or ''}) für Beleg {vnum or vid}")
                net = round(total / (1 + rate / 100), 2)
                tax = round(total - net, 2)
                if not dry_run:
                    tbl = "voucher_lines" if direction == "incoming" else "outgoing_lines"
                    col = "voucher_id" if direction == "incoming" else "outgoing_id"
                    cur.execute(f"""
                        INSERT INTO {tbl}
                            ({col}, account_skr, description,
                            net_amount, tax_rate, tax_amount)
                        VALUES (%s,%s,%s,%s,%s,%s);
                    """, (vid, acc, desc or pattern, net, rate, tax))


                affected += 1
                break

        if not matched:
            print(f"❔ Keine Regel für Beleg {vnum or vid} ({pname})")

    if dry_run:
        print(f"\n🧪 Dry-Run – {affected} Zeilen erkannt, keine geschrieben.")
        conn.rollback()
    else:
        conn.commit()
        print(f"\n✅ {affected} Buchungszeilen automatisch erzeugt.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    import argparse
    ap = argparse.ArgumentParser(description="Automatische Kontierung von Belegen anhand auto_rules.")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, keine Daten schreiben.")
    args = ap.parse_args()
    auto_assign_vouchers(dry_run=args.dry_run)
