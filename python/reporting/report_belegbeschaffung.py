#!/usr/bin/env python3
"""
report_belegbeschaffung.py

Belegbeschaffungs-Liste für ein gegebenes Jahr.

Zeigt alle Transaktionen ohne Belegzuordnung, gruppiert nach Gegenpartei,
sortiert nach Betrag (größte offene Posten zuerst).

Beispiel:
    python3 python/reporting/report_belegbeschaffung.py --year 2024
    python3 python/reporting/report_belegbeschaffung.py --year 2024 --show-ids
    python3 python/reporting/report_belegbeschaffung.py --year 2024 --min-amount 50
"""

import argparse
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection


def run(year: int, show_ids: bool = False, min_amount: float = 0.0):
    conn = get_connection(dict_cursor=True)
    cur = conn.cursor()

    # ------------------------------------------------------------------
    # 1. Statistik: Gesamtbild des Jahres
    # ------------------------------------------------------------------
    cur.execute("""
        SELECT
            COUNT(*)                                               AS gesamt,
            SUM(amount)                                            AS gesamt_betrag,
            COUNT(*) FILTER (WHERE is_private IS TRUE)             AS privat,
            SUM(amount) FILTER (WHERE is_private IS TRUE)          AS privat_betrag,
            COUNT(*) FILTER (WHERE is_internal IS TRUE)            AS intern,
            SUM(amount) FILTER (WHERE is_internal IS TRUE)         AS intern_betrag,
            COUNT(*) FILTER (
                WHERE is_private IS NOT TRUE
                  AND is_internal IS NOT TRUE
                  AND (
                      EXISTS (SELECT 1 FROM voucher_links  vl WHERE vl.transaction_id = t.id)
                   OR EXISTS (SELECT 1 FROM outgoing_links ol WHERE ol.transaction_id = t.id)
                  )
            )                                                      AS verbucht,
            SUM(amount) FILTER (
                WHERE is_private IS NOT TRUE
                  AND is_internal IS NOT TRUE
                  AND (
                      EXISTS (SELECT 1 FROM voucher_links  vl WHERE vl.transaction_id = t.id)
                   OR EXISTS (SELECT 1 FROM outgoing_links ol WHERE ol.transaction_id = t.id)
                  )
            )                                                      AS verbucht_betrag,
            COUNT(*) FILTER (
                WHERE is_private IS NOT TRUE
                  AND is_internal IS NOT TRUE
                  AND NOT EXISTS (SELECT 1 FROM voucher_links  vl WHERE vl.transaction_id = t.id)
                  AND NOT EXISTS (SELECT 1 FROM outgoing_links ol WHERE ol.transaction_id = t.id)
            )                                                      AS offen,
            SUM(amount) FILTER (
                WHERE is_private IS NOT TRUE
                  AND is_internal IS NOT TRUE
                  AND NOT EXISTS (SELECT 1 FROM voucher_links  vl WHERE vl.transaction_id = t.id)
                  AND NOT EXISTS (SELECT 1 FROM outgoing_links ol WHERE ol.transaction_id = t.id)
            )                                                      AS offen_betrag
        FROM transactions t
        WHERE DATE_PART('year', booking_date) = %s
    """, (year,))
    stats = cur.fetchone()

    print(f"\n{'='*70}")
    print(f"  BELEGBESCHAFFUNGS-LISTE {year}")
    print(f"{'='*70}")
    print(f"\nÜbersicht aller {year}-Transaktionen:")
    print(f"  Gesamt:   {stats['gesamt']:5}x  {float(stats['gesamt_betrag'] or 0):12.2f} €")
    print(f"  Privat:   {stats['privat']:5}x  {float(stats['privat_betrag'] or 0):12.2f} €  (is_private)")
    print(f"  Intern:   {stats['intern']:5}x  {float(stats['intern_betrag'] or 0):12.2f} €  (is_internal: Steuern, Darlehen etc.)")
    print(f"  Verbucht: {stats['verbucht']:5}x  {float(stats['verbucht_betrag'] or 0):12.2f} €  (Beleg vorhanden)")
    print(f"  Offen:    {stats['offen']:5}x  {float(stats['offen_betrag'] or 0):12.2f} €  ← Handlungsbedarf")

    if stats['offen'] == 0:
        print(f"\n✅ Alle Transaktionen für {year} sind klassifiziert oder verbucht.")
        cur.close()
        conn.close()
        return

    # ------------------------------------------------------------------
    # 2. Offene Transaktionen, gruppiert nach Gegenpartei
    # ------------------------------------------------------------------
    cur.execute("""
        SELECT
            COALESCE(NULLIF(TRIM(t.counterpart_name), ''), '(leer)')       AS name,
            COUNT(*)                                                         AS anzahl,
            SUM(t.amount)                                                    AS total,
            MIN(t.booking_date)                                              AS von,
            MAX(t.booking_date)                                              AS bis,
            ARRAY_AGG(t.id ORDER BY t.booking_date)                         AS ids
        FROM transactions t
        WHERE DATE_PART('year', t.booking_date) = %s
          AND t.is_private  IS NOT TRUE
          AND t.is_internal IS NOT TRUE
          AND NOT EXISTS (SELECT 1 FROM voucher_links  vl WHERE vl.transaction_id = t.id)
          AND NOT EXISTS (SELECT 1 FROM outgoing_links ol WHERE ol.transaction_id = t.id)
        GROUP BY COALESCE(NULLIF(TRIM(t.counterpart_name), ''), '(leer)')
        HAVING ABS(SUM(t.amount)) >= %s
        ORDER BY SUM(t.amount)
    """, (year, min_amount))
    rows = cur.fetchall()

    if not rows:
        print(f"\n✅ Keine offenen Transaktionen über {min_amount:.2f} € für {year}.")
        cur.close()
        conn.close()
        return

    print(f"\n{'─'*70}")
    print(f"  OFFENE POSITIONEN (ohne Belegzuordnung)")
    print(f"{'─'*70}")

    # separate into negative (expenses/unclear) and positive (income/refunds)
    negativ = [r for r in rows if float(r['total']) < 0]
    positiv = [r for r in rows if float(r['total']) >= 0]

    col_name = 44
    col_anz  = 4
    col_bet  = 12

    header = (f"{'Gegenpartei':{col_name}} {'Anz':>{col_anz}} {'Betrag':>{col_bet}}  "
              f"{'Zeitraum'}")
    print(f"\n{header}")
    print("─" * 70)

    for r in negativ:
        name = r['name'][:col_name]
        von  = str(r['von'])[:7]    # YYYY-MM
        bis  = str(r['bis'])[:7]
        zeitraum = von if von == bis else f"{von}…{bis}"
        ids  = r['ids']
        ids_str = ""
        if show_ids:
            id_preview = ", ".join(str(i) for i in ids[:6])
            if len(ids) > 6:
                id_preview += f", …(+{len(ids)-6})"
            ids_str = f"  [{id_preview}]"
        print(f"{name:{col_name}} {r['anzahl']:>{col_anz}}x {float(r['total']):>{col_bet}.2f} €  "
              f"{zeitraum}{ids_str}")

    if positiv:
        print(f"\n  Gutschriften / Erstattungen:")
        print("─" * 70)
        for r in positiv:
            name = r['name'][:col_name]
            von  = str(r['von'])[:7]
            bis  = str(r['bis'])[:7]
            zeitraum = von if von == bis else f"{von}…{bis}"
            ids  = r['ids']
            ids_str = ""
            if show_ids:
                id_preview = ", ".join(str(i) for i in ids[:6])
                if len(ids) > 6:
                    id_preview += f", …(+{len(ids)-6})"
                ids_str = f"  [{id_preview}]"
            print(f"{name:{col_name}} {r['anzahl']:>{col_anz}}x {float(r['total']):>{col_bet}.2f} €  "
                  f"{zeitraum}{ids_str}")

    # ------------------------------------------------------------------
    # 3. Zusammenfassung
    # ------------------------------------------------------------------
    total_offen = sum(float(r['total']) for r in rows)
    total_neg   = sum(float(r['total']) for r in negativ)
    total_pos   = sum(float(r['total']) for r in positiv)

    print(f"\n{'─'*70}")
    print(f"  Ausgaben offen:   {total_neg:12.2f} €  ({len(negativ)} Gegenparteien)")
    if positiv:
        print(f"  Gutschriften:     {total_pos:12.2f} €  ({len(positiv)} Gegenparteien)")
    print(f"  Netto offen:      {total_offen:12.2f} €")

    if min_amount > 0:
        print(f"\n  (Positionen unter {min_amount:.2f} € ausgeblendet, --min-amount anpassen)")

    cur.close()
    conn.close()


def main():
    ap = argparse.ArgumentParser(
        description="Belegbeschaffungs-Liste: offene Transaktionen ohne Belegzuordnung."
    )
    ap.add_argument("--year",       type=int, required=True, help="Geschäftsjahr (z. B. 2024)")
    ap.add_argument("--show-ids",   action="store_true",     help="Transaktions-IDs mit ausgeben")
    ap.add_argument("--min-amount", type=float, default=0.0, help="Mindestbetrag (Absolutwert) für Anzeige")
    args = ap.parse_args()
    run(args.year, args.show_ids, args.min_amount)


if __name__ == "__main__":
    main()
