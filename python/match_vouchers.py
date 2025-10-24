#!/usr/bin/env python3
"""
match_vouchers.py – Version 3
Berücksichtigt Zahlungsziel und sucht Transaktionen nur ab Rechnungsdatum (−1 Tag)
bis zum Zahlungsziel (+ Toleranz).

• vergleicht Beträge betragsweise (abs)
• berücksichtigt payment_due_date (optional)
• zeigt bis zu 3 Kandidaten mit Score an
• erlaubt interaktive Auswahl
• nutzt rapidfuzz, falls verfügbar
"""

import sys
import argparse
from datetime import datetime, timedelta
from db import get_connection

try:
    from rapidfuzz import fuzz
    def name_similarity(a, b):
        return fuzz.token_set_ratio(a or "", b or "") / 100.0
except ImportError:
    from difflib import SequenceMatcher
    def name_similarity(a, b):
        if not a or not b:
            return 0.0
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def amount_match_score(a, b):
    if a == 0 or b == 0:
        return 0.0
    diff = abs(abs(a) - abs(b))
    rel = diff / abs(a)
    return max(0, 1 - rel * 5)


def date_match_score(d1, d2):
    delta = abs((d1 - d2).days)
    if delta <= 1:
        return 1.0
    elif delta <= 3:
        return 0.8
    elif delta <= 7:
        return 0.6
    elif delta <= 14:
        return 0.4
    else:
        return 0.0


def compute_score(v_amount, t_amount, v_date, t_date, v_name, t_name, purpose):
    v_amount = float(v_amount)
    t_amount = float(t_amount)
    s_amount = amount_match_score(abs(v_amount), abs(t_amount))
    s_date = date_match_score(v_date, t_date)
    s_name = max(name_similarity(v_name, t_name), name_similarity(v_name, purpose))
    return s_amount * 0.5 + s_date * 0.3 + s_name * 0.2


def match_vouchers(direction: str, month: str | None):
    conn = get_connection()
    cur = conn.cursor()

    if direction not in ("incoming", "outgoing"):
        print("❌ Ungültige Richtung. Bitte --direction incoming|outgoing angeben.")
        sys.exit(1)

    # Tabellen und Felder
    if direction == "incoming":
        voucher_table = "vouchers"
        link_table = "voucher_links"
        name_field = "partner_name"
        date_field = "voucher_date"
        due_field = "payment_due_date"
        id_field = "voucher_id"
    else:
        voucher_table = "outgoing_vouchers"
        link_table = "outgoing_links"
        name_field = "customer_name"
        date_field = "invoice_date"
        due_field = "payment_due_date"
        id_field = "outgoing_id"

    # Zeitraumfilter
    if month:
        mdate = datetime.strptime(month, "%Y-%m")
        start = mdate.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
    else:
        start = datetime(1970, 1, 1)
        end = datetime(2100, 1, 1)

    cur.execute(
        f"""
        SELECT id, voucher_number, {name_field}, total_amount,
               {date_field}, COALESCE({due_field}, {date_field} + INTERVAL '14 days') AS payment_due_date,
               description
          FROM {voucher_table}
         WHERE status != 'paid'
           AND {date_field} BETWEEN %s AND %s
         ORDER BY {date_field};
        """,
        (start, end),
    )
    vouchers = cur.fetchall()
    print(f"{len(vouchers)} Beleg(e) gefunden.\n")

    for vid, number, name, amount, date, due_date, descr in vouchers:
        if not amount or not date:
            continue

        # Zeitfenster bestimmen
        default_days = 14 if amount < 500 else 45
        if not due_date:
            due_date = date + timedelta(days=default_days)
        start_date = date - timedelta(days=14)
        end_date = due_date + timedelta(days=10)

        print("=" * 70)
        print(f"Beleg-ID {vid} | Rg.-Nr. {number or '-'} | {name} | {amount:.2f} EUR")
        print(f"  Datum: {date} | Fälligkeit: {due_date.date()} | Beschreibung: {descr or ''}")

        cur.execute(
            """
            SELECT id, booking_date, amount, counterpart_name, purpose
            FROM transactions
            WHERE booking_date BETWEEN %s AND %s
            AND (is_private IS FALSE OR is_private IS NULL)
            AND ABS(amount) BETWEEN %s*0.9 AND %s*1.1;
            """,
            (start_date, end_date, abs(amount), abs(amount)),
        )

        txs = cur.fetchall()

        if not txs:
            print("  → Keine Transaktionen im Zeitraum gefunden.")
            continue

        candidates = []
        for tid, tdate, tamount, tname, purpose in txs:
            score = compute_score(amount, tamount, date, tdate, name, tname or "", purpose or "")
            if score > 0.2:
                candidates.append((score, tid, tdate, tamount, tname or "", purpose or ""))

        if not candidates:
            print("  → Keine relevanten Kandidaten.")
            continue

        candidates.sort(reverse=True)
        print("  → Kandidaten:")
        for i, (score, tid, tdate, tamount, tname, purpose) in enumerate(candidates[:3], 1):
            print(f"     [{i}] TxID {tid:5d} | {tdate} | {tamount:8.2f} EUR | {tname[:40]:40s} | Score {score:.2f}")
            print(f"          {purpose[:80]}")

        sel = input("     Auswahl [1-3] oder [n]one: ").strip().lower()
        if sel in ("n", "", "s"):
            print("     ➜ übersprungen.\n")
            continue

        try:
            idx = int(sel) - 1
            _, tid, _, tamount, _, _ = candidates[idx]
        except (ValueError, IndexError):
            print("     ⚠️  Ungültige Auswahl.\n")
            continue

        cur.execute(
            f"""
            INSERT INTO {link_table} ({id_field}, transaction_id, link_type, amount)
            VALUES (%s,%s,'payment',%s)
            ON CONFLICT DO NOTHING;
            """,
            (vid, tid, abs(tamount)),
        )
        cur.execute(f"UPDATE {voucher_table} SET status='paid' WHERE id=%s;", (vid,))
        conn.commit()
        print("     ✅ Verknüpfung gespeichert & Beleg als 'paid' markiert.\n")

    cur.close()
    conn.close()
    print("\n✅ Matching-Durchlauf beendet.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Verknüpft Belege mit Banktransaktionen.")
    ap.add_argument("--direction", required=True, help="incoming | outgoing")
    ap.add_argument("--month", help="YYYY-MM (optional)")
    args = ap.parse_args()
    match_vouchers(args.direction, args.month)
