#!/usr/bin/env python3
"""
apply_taxation_mode.py – Stellt die Reporting-Views auf die in config/business.yaml
konfigurierte Besteuerungsart um (taxation_mode: IST | SOLL).

- SOLL (Sollversteuerung): Periode = Belegdatum (Rechnungsdatum) – sowohl Umsatz als Aufwand.
- IST  (Istversteuerung / EÜR Zufluss-Abfluss):
    * Gewinn-Sicht (vw_guv_report, vw_susa_monthly, vw_journal): Periode = Zahlungsdatum
      (verknüpfte Banktransaktion), Fallback Belegdatum, wenn keine Zahlung verknüpft.
    * USt-Sicht (vw_ust_report): Ausgangs-USt nach Zahlung; Vorsteuer IMMER nach
      Rechnungseingang (Vorsteuerabzug ist zahlungsunabhängig, §15 UStG).
      Reverse-Charge (§13b, Konten 3xxx) wird als Aus- UND Eingang geführt (zahllast-neutral).

Quelle der Wahrheit ist config/business.yaml. Nach Änderung dort: dieses Skript erneut laufen lassen.

Aufruf: python3 python/apply_taxation_mode.py [--dry-run]
"""
import sys, os, argparse
from pathlib import Path
import yaml
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_connection

CONFIG = Path(__file__).parent.parent / "config" / "business.yaml"


def read_mode() -> str:
    cfg = yaml.safe_load(CONFIG.read_text()) or {}
    mode = str(cfg.get("taxation_mode", "SOLL")).strip().upper()
    if mode not in ("IST", "SOLL"):
        raise SystemExit(f"❌ Ungültiger taxation_mode '{mode}' in {CONFIG} (erlaubt: IST | SOLL)")
    return mode


# Basis-View: neues Modell im Legacy-Format + Beleg-/Zahlungsdatum + Status (modus-unabhängig)
BASE_VIEW = """
CREATE OR REPLACE VIEW vw_booking_lines_effective AS
SELECT vl.id, 'incoming'::text AS direction, vl.voucher_id, NULL::integer AS outgoing_id,
       vl.account_skr, vl.description, vl.net_amount, vl.tax_rate, vl.tax_amount,
       (COALESCE(vl.net_amount,0)+COALESCE(vl.tax_amount,0))::numeric(12,2) AS gross_amount,
       NULL::text AS tax_type,
       COALESCE(v.booking_date, v.voucher_date) AS beleg_datum,
       (SELECT MIN(t.booking_date) FROM voucher_links lk JOIN transactions t ON t.id=lk.transaction_id
          WHERE lk.voucher_id = vl.voucher_id) AS zahlung_datum,
       v.status AS status
  FROM voucher_lines vl JOIN vouchers v ON v.id = vl.voucher_id
UNION ALL
SELECT ol.id, 'outgoing'::text, NULL::integer, ol.outgoing_id,
       ol.account_skr, ol.description, ol.net_amount, ol.tax_rate, ol.tax_amount,
       (COALESCE(ol.net_amount,0)+COALESCE(ol.tax_amount,0))::numeric(12,2),
       NULL::text,
       COALESCE(ov.booking_date, ov.voucher_date),
       (SELECT MIN(t.booking_date) FROM outgoing_links lk JOIN transactions t ON t.id=lk.transaction_id
          WHERE lk.outgoing_id = ol.outgoing_id),
       ov.status
  FROM outgoing_lines ol JOIN outgoing_vouchers ov ON ov.id = ol.outgoing_id;
"""


def build_views(mode: str) -> str:
    # Periode für die GEWINN-Sicht (Umsatz + Aufwand)
    if mode == "IST":
        gewinn_date = "COALESCE(bl.zahlung_datum, bl.beleg_datum)"
        ust_out_date = "COALESCE(bl.zahlung_datum, bl.beleg_datum)"
    else:  # SOLL
        gewinn_date = "bl.beleg_datum"
        ust_out_date = "bl.beleg_datum"
    # Vorsteuer (incoming) immer nach Belegdatum – unabhängig vom Modus
    ust_in_date = "bl.beleg_datum"

    guv = f"""
CREATE OR REPLACE VIEW vw_guv_report AS
SELECT date_trunc('month', ({gewinn_date})::timestamp with time zone) AS periode,
       bl.direction, bl.account_skr,
       sum(COALESCE(bl.net_amount,0))   AS netto_summe,
       sum(COALESCE(bl.tax_amount,0))   AS steuer_summe,
       sum(COALESCE(bl.gross_amount,0)) AS brutto_summe
  FROM vw_booking_lines_effective bl
 WHERE COALESCE(bl.status,'draft') NOT IN ('draft','cancelled')
 GROUP BY 1, bl.direction, bl.account_skr;
"""

    ust = f"""
CREATE OR REPLACE VIEW vw_ust_report AS
 WITH basis AS (
   SELECT bl.direction, bl.account_skr, bl.net_amount, bl.tax_amount,
          date_trunc('month',
            (CASE WHEN bl.direction='outgoing' THEN ({ust_out_date}) ELSE ({ust_in_date}) END)::timestamp with time zone
          ) AS periode
     FROM vw_booking_lines_effective bl
    WHERE COALESCE(bl.status,'draft') NOT IN ('draft','cancelled')
 )
 SELECT periode,
   sum(CASE WHEN direction='outgoing' THEN COALESCE(tax_amount,0)
            WHEN direction='incoming' AND account_skr LIKE '3%' THEN COALESCE(tax_amount,0)
            ELSE 0 END) AS ust_output,
   sum(CASE WHEN direction='incoming' THEN COALESCE(tax_amount,0) ELSE 0 END) AS ust_input,
   sum(CASE WHEN direction='outgoing' THEN COALESCE(net_amount,0) ELSE 0 END) AS nettoumsatz,
   sum(CASE WHEN direction='incoming' THEN COALESCE(net_amount,0) ELSE 0 END) AS nettoeinkauf,
   sum(CASE WHEN direction='outgoing' THEN COALESCE(tax_amount,0)
            WHEN direction='incoming' AND account_skr LIKE '3%' THEN COALESCE(tax_amount,0)
            ELSE 0 END)
   - sum(CASE WHEN direction='incoming' THEN COALESCE(tax_amount,0) ELSE 0 END) AS zahlbetrag
   FROM basis
  GROUP BY periode
  ORDER BY periode;
"""

    susa_m = f"""
CREATE OR REPLACE VIEW vw_susa_monthly AS
SELECT date_trunc('month', ({gewinn_date})::timestamp with time zone) AS periode,
       bl.account_skr,
       COALESCE(ag.gruppe,'Unklassifiziert') AS bilanz_gruppe,
       sum(CASE WHEN bl.direction='incoming' THEN COALESCE(bl.net_amount,0) ELSE 0 END) AS soll_summe,
       sum(CASE WHEN bl.direction='outgoing' THEN COALESCE(bl.net_amount,0) ELSE 0 END) AS haben_summe,
       sum(CASE WHEN bl.direction='outgoing' THEN COALESCE(bl.net_amount,0)
                WHEN bl.direction='incoming' THEN -COALESCE(bl.net_amount,0) ELSE 0 END) AS saldo,
       CASE WHEN sum(CASE WHEN bl.direction='outgoing' THEN COALESCE(bl.net_amount,0)
                          WHEN bl.direction='incoming' THEN -COALESCE(bl.net_amount,0) ELSE 0 END) >= 0
            THEN 'Haben' ELSE 'Soll' END AS richtung
  FROM vw_booking_lines_effective bl
  LEFT JOIN account_groups ag ON bl.account_skr >= ag.skr_min AND bl.account_skr <= ag.skr_max
 WHERE COALESCE(bl.status,'draft') NOT IN ('draft','cancelled')
 GROUP BY 1, bl.account_skr, COALESCE(ag.gruppe,'Unklassifiziert')
 ORDER BY 1, bl.account_skr;
"""

    journal = f"""
CREATE OR REPLACE VIEW vw_journal AS
SELECT ({gewinn_date}) AS datum, bl.direction, bl.account_skr, bl.description,
       bl.net_amount, bl.tax_amount, bl.gross_amount,
       COALESCE(v.partner_name, ov.partner_name)     AS partner,
       COALESCE(v.voucher_number, ov.voucher_number) AS belegnummer,
       COALESCE(v.document_type, ov.document_type)   AS belegart
  FROM vw_booking_lines_effective bl
  LEFT JOIN vouchers v ON v.id = bl.voucher_id
  LEFT JOIN outgoing_vouchers ov ON ov.id = bl.outgoing_id
 WHERE COALESCE(bl.status,'draft') NOT IN ('draft','cancelled')
 ORDER BY ({gewinn_date}), bl.account_skr;
"""
    return BASE_VIEW + guv + ust + susa_m + journal


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    mode = read_mode()
    sql = build_views(mode)
    print(f"📋 taxation_mode = {mode}  (Quelle: {CONFIG})")
    if args.dry_run:
        print(sql)
        return

    conn = get_connection(); cur = conn.cursor()
    cur.execute(sql)
    conn.commit()
    cur.close(); conn.close()
    print(f"✅ Reporting-Views auf {mode} umgestellt "
          f"(vw_booking_lines_effective, vw_guv_report, vw_ust_report, vw_susa_monthly, vw_journal).")
    if mode == "IST":
        print("   Gewinn nach Zahlungsdatum (Zufluss/Abfluss); Vorsteuer nach Rechnungseingang.")


if __name__ == "__main__":
    main()
