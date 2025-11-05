#!/usr/bin/env python3
"""
sync_flags.py
Synchronisiert die booleschen Flags (is_internal, is_private, is_cyclic)
zwischen booking_rules und transactions.

• Vergleicht pattern in booking_rules mit counterpart_name / purpose
• Setzt oder entfernt Flags in transactions
• Unterstützt --dry-run und --month YYYY-MM
"""

import argparse
from datetime import datetime, timedelta
from db import get_connection


def get_rules(cur):
    cur.execute("""
        SELECT pattern, is_internal, is_private, is_cyclic
          FROM booking_rules
         WHERE is_internal = TRUE OR is_private = TRUE OR is_cyclic = TRUE;
    """)
    return cur.fetchall()


def sync_flags(month=None, dry_run=False):
    conn = get_connection()
    cur = conn.cursor()

    # Zeitraum optional einschränken
    if month:
        mdate = datetime.strptime(month, "%Y-%m")
        start = mdate.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
        print(f"📅 Zeitraum: {start.date()} bis {end.date()}")
    else:
        start = datetime(1970, 1, 1)
        end = datetime(2100, 1, 1)

    rules = get_rules(cur)
    print(f"🔍 {len(rules)} Regel(n) mit gesetzten Flags geladen.\n")

    cur.execute("""
        SELECT id, counterpart_name, purpose, is_internal, is_private, is_cyclic
          FROM transactions
         WHERE booking_date BETWEEN %s AND %s;
    """, (start, end))
    txs = cur.fetchall()

    updates = []
    for tid, name, purpose, is_int, is_priv, is_cyc in txs:
        text = f"{name or ''} {purpose or ''}".lower()
        new_flags = {"internal": False, "private": False, "cyclic": False}

        for pattern, r_int, r_priv, r_cyc in rules:
            if pattern and pattern.lower() in text:
                new_flags["internal"] |= bool(r_int)
                new_flags["private"] |= bool(r_priv)
                new_flags["cyclic"] |= bool(r_cyc)

        # Wenn sich Flags ändern, merken
        if (new_flags["internal"] != bool(is_int)
            or new_flags["private"] != bool(is_priv)
            or new_flags["cyclic"] != bool(is_cyc)):
            updates.append((tid, new_flags))

    if not updates:
        print("✅ Keine Änderungen erforderlich – alles synchron.")
        return

    print(f"🧾 {len(updates)} Transaktion(en) mit Flag-Änderungen gefunden.\n")

    for tid, flags in updates:
        print(f"TxID {tid:6d} → "
              f"is_internal={flags['internal']} "
              f"is_private={flags['private']} "
              f"is_cyclic={flags['cyclic']}")
        if not dry_run:
            cur.execute("""
                UPDATE transactions
                   SET is_internal = %s,
                       is_private  = %s,
                       is_cyclic   = %s
                 WHERE id = %s;
            """, (flags["internal"], flags["private"], flags["cyclic"], tid))

    if not dry_run:
        conn.commit()
        print(f"\n💾 Änderungen gespeichert.")
    else:
        print(f"\n🧩 (Dry-Run) – keine Änderungen geschrieben.")

    cur.close()
    conn.close()


def main():
    ap = argparse.ArgumentParser(description="Synchronisiert Flags aus booking_rules auf transactions.")
    ap.add_argument("--month", help="YYYY-MM (optional, Zeitraumfilter)")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, nichts ändern")
    args = ap.parse_args()

    sync_flags(args.month, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
