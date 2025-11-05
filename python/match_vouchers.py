#!/usr/bin/env python3
"""
match_vouchers.py v4 – erweiterte Version mit besserem Matching
"""

import sys
import argparse
from datetime import datetime, timedelta
from decimal import Decimal
from db import get_connection

# -------------------------------------------------------------------
#  Fuzzy Matching Setup
# -------------------------------------------------------------------
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

# -------------------------------------------------------------------
#  Helper Functions
# -------------------------------------------------------------------
def normalize_name(name: str) -> str:
    """Entfernt juristische Zusätze und Vereinheitlicht Namen"""
    if not name:
        return ""
    n = name.lower()
    replacements = {
        "gmbh & co. kg": "gmbh",
        "gmbh & co.": "gmbh",
        "gmbh.": "gmbh",
        "ug (haftungsbeschränkt)": "ug",
        "s.a.r.l.": "",
        "et cie": "",
        "ag & co.": "ag",
        "ag.": "ag",
        "sarl": "",
        "paypal europe": "",
        "finion capital": "",
    }
    for k, v in replacements.items():
        n = n.replace(k, v)
    return " ".join(n.split())

def amount_match_score(a, b):
    """Bewertet Ähnlichkeit nach Betrag (absolut)."""
    if a == 0 or b == 0:
        return 0.0
    diff = abs(abs(a) - abs(b))
    rel = diff / abs(a)
    return max(0, 1 - rel * 5)

def date_match_score(d1, d2):
    """Bewertet zeitliche Nähe."""
    delta = abs((d1 - d2).days)
    if delta <= 1:
        return 1.0
    elif delta <= 3:
        return 0.8
    elif delta <= 7:
        return 0.6
    elif delta <= 14:
        return 0.4
    elif delta <= 30:
        return 0.2
    else:
        return 0.0

def compute_score(v_amount, t_amount, v_date, t_date, v_name, t_name, purpose, normalize=False):
    if normalize:
        v_name, t_name, purpose = map(normalize_name, [v_name, t_name, purpose])
    # Sicherstellen, dass keine Decimal-Werte in Berechnung eingehen
    v_amount_f = float(v_amount)
    t_amount_f = float(t_amount)

    s_amount = amount_match_score(abs(v_amount_f), abs(t_amount_f))
    s_date = date_match_score(v_date, t_date)
    s_name = max(
        name_similarity(v_name, t_name),
        name_similarity(v_name, purpose),
        name_similarity(v_name, t_name + " " + purpose)
    )
    score = (float(s_amount) * 0.4) + (float(s_date) * 0.3) + (float(s_name) * 0.3)

    return score

# -------------------------------------------------------------------
#  Hauptfunktion
# -------------------------------------------------------------------
def match_vouchers(direction, month=None, window=30, show_all=False, normalize_names=False):
    conn = get_connection()
    cur = conn.cursor()

    if direction not in ("incoming", "outgoing"):
        print("❌ Ungültige Richtung. Bitte --direction incoming|outgoing angeben.")
        sys.exit(1)

    # Tabellenwahl
    if direction == "incoming":
        voucher_table, link_table, name_field, date_field, id_field = (
            "vouchers", "voucher_links", "partner_name", "voucher_date", "voucher_id"
        )
    else:
        voucher_table, link_table, name_field, date_field, id_field = (
            "outgoing_vouchers", "outgoing_links", "customer_name", "invoice_date", "outgoing_id"
        )

    # Zeitraum
    if month:
        mdate = datetime.strptime(month, "%Y-%m")
        start = mdate.replace(day=1)
        end = (start + timedelta(days=32)).replace(day=1)
    else:
        start, end = datetime(1970, 1, 1), datetime(2100, 1, 1)

    cur.execute(
        f"""
        SELECT id, {name_field}, total_amount, {date_field}, description, voucher_number
          FROM {voucher_table}
         WHERE status != 'paid'
           AND {date_field} BETWEEN %s AND %s
         ORDER BY {date_field};
        """,
        (start, end),
    )
    vouchers = cur.fetchall()
    print(f"{len(vouchers)} Beleg(e) gefunden.\n")

    for vid, name, amount, date, descr, vnum in vouchers:
        if not amount or not date:
            continue
        print("=" * 70)
        print(f"Beleg-ID {vid} | {name} | {amount:.2f} EUR | {date} | Nr: {vnum or '-'}")

        start_date = date - timedelta(days=1)
        end_date = date + timedelta(days=window)

        cur.execute(
            """
            SELECT id, booking_date, amount, counterpart_name, purpose
              FROM transactions
             WHERE booking_date BETWEEN %s AND %s
               AND ABS(amount) BETWEEN %s*0.8 AND %s*1.2;
            """,
            (start_date, end_date, abs(amount), abs(amount)),
        )
        txs = cur.fetchall()
        if not txs:
            print("  → Keine Transaktionen im Zeitraum gefunden.")
            continue

        candidates = []
        for tid, tdate, tamount, tname, purpose in txs:
            score = compute_score(amount, tamount, date, tdate, name, tname or "", purpose or "", normalize_names)
            if score > (0.1 if show_all else 0.2):
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

# -------------------------------------------------------------------
if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Erweitertes Matching zwischen Belegen und Transaktionen.")
    ap.add_argument("--direction", required=True, help="incoming | outgoing")
    ap.add_argument("--month", help="YYYY-MM (optional)")
    ap.add_argument("--window", type=int, default=30, help="Zeitraum in Tagen nach Belegdatum (Standard 30)")
    ap.add_argument("--show-all", action="store_true", help="Zeigt auch schwache Matches (Score > 0.1)")
    ap.add_argument("--normalize-names", action="store_true", help="Normalisiert juristische Zusätze in Namen")
    args = ap.parse_args()

    match_vouchers(
        args.direction,
        month=args.month,
        window=args.window,
        show_all=args.show_all,
        normalize_names=args.normalize_names,
    )
