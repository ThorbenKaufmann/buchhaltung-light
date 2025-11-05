#!/usr/bin/env python3
"""
auto_assign_transactions.py
Automatische Buchung wiederkehrender Transaktionen anhand booking_rules
mit USt-/VSt-Klassifikation (tax_type) und booleschen Flags
(is_internal, is_private, is_cyclic).
"""

import argparse
from datetime import datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from db import get_connection


def get_rules(cur):
    cur.execute("""
        SELECT pattern, default_account, default_tax, direction, note,
               is_internal, is_private, is_cyclic
          FROM booking_rules;
    """)
    return cur.fetchall()


def get_unlinked_transactions(cur, start, end):
    cur.execute("""
        SELECT t.id, t.booking_date, t.amount, t.counterpart_name, t.purpose
          FROM transactions t
         WHERE t.is_private IS FALSE
           AND t.booking_date BETWEEN %s AND %s
           AND t.id NOT IN (
               SELECT CAST(description AS INTEGER)
                 FROM booking_lines
                 WHERE description ~ '^[0-9]+$'
           )
         ORDER BY t.booking_date;
    """, (start, end))
    return cur.fetchall()


def match_rule(rules, name, purpose):
    text = f"{name or ''} {purpose or ''}".lower()
    for pattern, account, tax, direction, note, is_internal, is_private, is_cyclic in rules:
        if pattern.lower() in text:
            return dict(
                account=account, tax=tax, direction=direction, note=note,
                is_internal=bool(is_internal), is_private=bool(is_private),
                is_cyclic=bool(is_cyclic)
            )
    return None


def determine_tax_type(direction: str, tax_rate: Decimal, note: str | None) -> str:
    if note and "reverse" in note.lower():
        return "reverse_charge"
    if note and "ig" in note.lower():
        return "ig_erwerb"
    if direction == "incoming":
        return {19: "vst19", 7: "vst7"}.get(float(tax_rate), "vst0")
    else:
        return {19: "ust19", 7: "ust7"}.get(float(tax_rate), "ust0")


def has_voucher_link(cur, txid: int) -> bool:
    cur.execute("""
        SELECT 1 FROM voucher_links WHERE transaction_id = %s
        UNION ALL
        SELECT 1 FROM outgoing_links WHERE transaction_id = %s;
    """, (txid, txid))
    return bool(cur.fetchone())


def auto_assign(month, dry_run=False):
    conn = get_connection()
    cur = conn.cursor()

    mdate = datetime.strptime(month, "%Y-%m")
    start = mdate.replace(day=1)
    end = (start + timedelta(days=32)).replace(day=1)

    rules = get_rules(cur)
    txs = get_unlinked_transactions(cur, start, end)

    print(f"📅 Zeitraum: {start.date()} bis {end.date()}")
    print(f"🔍 {len(txs)} Transaktionen ohne Zuordnung gefunden.\n")

    assigned = 0
    for tid, date, amount, name, purpose in txs:
        rule = match_rule(rules, name, purpose)
        if not rule:
            continue

        direction = rule["direction"]
        account = rule["account"]
        tax_rate = Decimal(str(rule["tax"]))
        tax_type = determine_tax_type(direction, tax_rate, rule.get("note"))

        net = Decimal(abs(amount)) / (Decimal(1) + tax_rate / 100)
        tax_amount = (net * tax_rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        gross = abs(Decimal(amount))

        # Prüfen, ob Beleg vorhanden
        linked = has_voucher_link(cur, tid)
        receipt_status = "complete" if linked or rule["is_cyclic"] else "missing"

        flags = []
        if rule["is_internal"]:
            flags.append("INTERNAL")
        if rule["is_private"]:
            flags.append("PRIVATE")
        if rule["is_cyclic"]:
            flags.append("CYCLIC")

        print(f"💡 {date} | {name[:35] if name else ''} | {gross:.2f} € "
              f"→ Konto {account} ({rule['note'] or ''}) | {tax_type} | {receipt_status} "
              f"{' '.join(['['+f+']' for f in flags])}")

        if not dry_run:
            # Flag-Update auf Transaktionsebene
            cur.execute("""
                UPDATE transactions
                   SET is_internal = %s,
                       is_private  = %s,
                       is_cyclic   = %s
                 WHERE id = %s;
            """, (rule["is_internal"], rule["is_private"], rule["is_cyclic"], tid))

            # Buchungszeile anlegen
            cur.execute("""
                INSERT INTO booking_lines
                    (direction, account_skr, description,
                     net_amount, tax_rate, tax_amount, gross_amount,
                     receipt_status, created_at, tax_type)
                VALUES (%s,%s,%s,%s,%s,%s,%s,%s,NOW(),%s);
            """, (
                direction, account, str(tid),
                net, tax_rate, tax_amount, gross, receipt_status, tax_type
            ))
            assigned += 1

    if not dry_run:
        conn.commit()

    cur.close()
    conn.close()
    print(f"\n✅ {assigned} Buchung(en) {'simuliert' if dry_run else 'angelegt'}.")


def main():
    ap = argparse.ArgumentParser(description="Automatische Verbuchung wiederkehrender Transaktionen.")
    ap.add_argument("--month", required=True, help="Monat im Format YYYY-MM")
    ap.add_argument("--dry-run", action="store_true", help="Nur anzeigen, keine Buchungen schreiben")
    args = ap.parse_args()
    auto_assign(args.month, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
