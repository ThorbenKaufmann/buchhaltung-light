-- migrate_views_to_new_model.sql
-- 2026-06-25: EÜR-Cleanup. Stellt die Reporting-Views von booking_lines_legacy
-- auf das neue Modell (voucher_lines + outgoing_lines) um.
--
-- Strategie: eine Basis-View vw_booking_lines_effective im exakten Legacy-Spaltenformat
-- aus dem neuen Modell. Alle abhängigen Views lesen nur noch daraus — Logik unverändert,
-- zusätzlich werden 'cancelled'-Belege ausgefiltert (vorher nur 'draft').
--
-- Reversibel: booking_lines_legacy bleibt unangetastet; Views per pg_restore wiederherstellbar.
--
-- ⚠️ HINWEIS (2026-06-26): vw_booking_lines_effective sowie die periodenabhängigen Views
-- (vw_guv_report, vw_ust_report, vw_susa_monthly, vw_journal) werden inzwischen von
-- python/apply_taxation_mode.py verwaltet (config-gesteuert IST/SOLL, mit Beleg-/Zahlungsdatum).
-- Diese Datei NICHT nach apply_taxation_mode.py erneut ausführen, sonst fallen die Views auf
-- die Soll-Basis zurück. Danach ggf. wieder `python3 python/apply_taxation_mode.py` laufen lassen.

BEGIN;

-- 1) Basis: neues Modell in Legacy-Form (direction/voucher_id/outgoing_id/net/tax/gross/tax_type)
CREATE OR REPLACE VIEW vw_booking_lines_effective AS
SELECT vl.id,
       'incoming'::text AS direction,
       vl.voucher_id,
       NULL::integer    AS outgoing_id,
       vl.account_skr,
       vl.description,
       vl.net_amount,
       vl.tax_rate,
       vl.tax_amount,
       (COALESCE(vl.net_amount,0) + COALESCE(vl.tax_amount,0))::numeric(12,2) AS gross_amount,
       NULL::text       AS tax_type
  FROM voucher_lines vl
UNION ALL
SELECT ol.id,
       'outgoing'::text AS direction,
       NULL::integer    AS voucher_id,
       ol.outgoing_id,
       ol.account_skr,
       ol.description,
       ol.net_amount,
       ol.tax_rate,
       ol.tax_amount,
       (COALESCE(ol.net_amount,0) + COALESCE(ol.tax_amount,0))::numeric(12,2) AS gross_amount,
       NULL::text       AS tax_type
  FROM outgoing_lines ol;

-- 2) GuV-Basis (Wurzel der GuV-Kette; classified/grouped/result hängen daran)
CREATE OR REPLACE VIEW vw_guv_report AS
SELECT date_trunc('month'::text, COALESCE(v.booking_date, v.voucher_date, ov.booking_date, ov.voucher_date)::timestamp with time zone) AS periode,
       bl.direction,
       bl.account_skr,
       sum(COALESCE(bl.net_amount, 0::numeric))   AS netto_summe,
       sum(COALESCE(bl.tax_amount, 0::numeric))   AS steuer_summe,
       sum(COALESCE(bl.gross_amount, 0::numeric)) AS brutto_summe
  FROM vw_booking_lines_effective bl
  LEFT JOIN vouchers v ON v.id = bl.voucher_id
  LEFT JOIN outgoing_vouchers ov ON ov.id = bl.outgoing_id
 WHERE COALESCE(v.status, ov.status) NOT IN ('draft','cancelled')
 GROUP BY 1, bl.direction, bl.account_skr;

-- 3) USt-Report
CREATE OR REPLACE VIEW vw_ust_report AS
 WITH basis AS (
   SELECT bl.id, bl.direction, bl.net_amount, bl.tax_amount, bl.gross_amount, bl.tax_type,
          COALESCE(v.status, ov.status) AS status,
          date_trunc('month'::text, COALESCE(v.booking_date, v.voucher_date, ov.booking_date, ov.voucher_date)::timestamp with time zone) AS periode
     FROM vw_booking_lines_effective bl
     LEFT JOIN vouchers v ON v.id = bl.voucher_id
     LEFT JOIN outgoing_vouchers ov ON ov.id = bl.outgoing_id
 )
 SELECT b.periode,
   sum(CASE WHEN b.tax_type ~~ 'ust%'::text OR b.direction = 'outgoing'::text AND COALESCE(b.tax_amount,0::numeric) <> 0::numeric THEN COALESCE(b.tax_amount,0::numeric) ELSE 0::numeric END) AS ust_output,
   sum(CASE WHEN b.tax_type ~~ 'vst%'::text OR b.direction = 'incoming'::text AND COALESCE(b.tax_amount,0::numeric) <> 0::numeric THEN COALESCE(b.tax_amount,0::numeric) ELSE 0::numeric END) AS ust_input,
   sum(CASE WHEN b.tax_type ~~ 'ust%'::text OR b.direction = 'outgoing'::text THEN COALESCE(b.net_amount,0::numeric) ELSE 0::numeric END) AS nettoumsatz,
   sum(CASE WHEN b.tax_type ~~ 'vst%'::text OR b.direction = 'incoming'::text THEN COALESCE(b.net_amount,0::numeric) ELSE 0::numeric END) AS nettoeinkauf,
   sum(CASE WHEN b.tax_type ~~ 'ust%'::text OR b.direction = 'outgoing'::text AND COALESCE(b.tax_amount,0::numeric) <> 0::numeric THEN COALESCE(b.tax_amount,0::numeric) ELSE 0::numeric END)
   - sum(CASE WHEN b.tax_type ~~ 'vst%'::text OR b.direction = 'incoming'::text AND COALESCE(b.tax_amount,0::numeric) <> 0::numeric THEN COALESCE(b.tax_amount,0::numeric) ELSE 0::numeric END) AS zahlbetrag
   FROM basis b
  WHERE COALESCE(b.status, 'draft'::text) NOT IN ('draft','cancelled')
  GROUP BY b.periode
  ORDER BY b.periode;

-- 4) Journal
CREATE OR REPLACE VIEW vw_journal AS
SELECT COALESCE(v.voucher_date, ov.voucher_date) AS datum,
       bl.direction, bl.account_skr, bl.description, bl.net_amount, bl.tax_amount, bl.gross_amount,
       COALESCE(v.partner_name, ov.partner_name)   AS partner,
       COALESCE(v.voucher_number, ov.voucher_number) AS belegnummer,
       COALESCE(v.document_type, ov.document_type)  AS belegart
  FROM vw_booking_lines_effective bl
  LEFT JOIN vouchers v ON v.id = bl.voucher_id
  LEFT JOIN outgoing_vouchers ov ON ov.id = bl.outgoing_id
 WHERE COALESCE(v.status, ov.status) NOT IN ('draft','cancelled')
 ORDER BY COALESCE(v.voucher_date, ov.voucher_date), bl.account_skr;

-- 5) SuSa (gesamt)
CREATE OR REPLACE VIEW vw_susa AS
SELECT bl.account_skr,
       COALESCE(a.gruppe, 'Unklassifiziert'::text) AS bilanz_gruppe,
       sum(CASE WHEN bl.direction = 'incoming'::text THEN COALESCE(bl.net_amount,0::numeric) ELSE 0::numeric END) AS soll_summe,
       sum(CASE WHEN bl.direction = 'outgoing'::text THEN COALESCE(bl.net_amount,0::numeric) ELSE 0::numeric END) AS haben_summe,
       sum(CASE WHEN bl.direction = 'outgoing'::text THEN COALESCE(bl.net_amount,0::numeric) WHEN bl.direction = 'incoming'::text THEN - COALESCE(bl.net_amount,0::numeric) ELSE 0::numeric END) AS saldo,
       CASE WHEN sum(CASE WHEN bl.direction = 'outgoing'::text THEN COALESCE(bl.net_amount,0::numeric) WHEN bl.direction = 'incoming'::text THEN - COALESCE(bl.net_amount,0::numeric) ELSE 0::numeric END) >= 0::numeric THEN 'Haben'::text ELSE 'Soll'::text END AS richtung
  FROM vw_booking_lines_effective bl
  LEFT JOIN account_groups a ON bl.account_skr >= a.skr_min AND bl.account_skr <= a.skr_max
  LEFT JOIN vouchers v ON v.id = bl.voucher_id
  LEFT JOIN outgoing_vouchers ov ON ov.id = bl.outgoing_id
 WHERE COALESCE(v.status, ov.status) NOT IN ('draft','cancelled')
 GROUP BY bl.account_skr, COALESCE(a.gruppe, 'Unklassifiziert'::text)
 ORDER BY bl.account_skr;

-- 6) SuSa (monatlich)
CREATE OR REPLACE VIEW vw_susa_monthly AS
SELECT date_trunc('month'::text, COALESCE(v.booking_date, v.voucher_date, ov.booking_date, ov.voucher_date)::timestamp with time zone) AS periode,
       bl.account_skr,
       COALESCE(ag.gruppe, 'Unklassifiziert'::text) AS bilanz_gruppe,
       sum(CASE WHEN bl.direction = 'incoming'::text THEN COALESCE(bl.net_amount,0::numeric) ELSE 0::numeric END) AS soll_summe,
       sum(CASE WHEN bl.direction = 'outgoing'::text THEN COALESCE(bl.net_amount,0::numeric) ELSE 0::numeric END) AS haben_summe,
       sum(CASE WHEN bl.direction = 'outgoing'::text THEN COALESCE(bl.net_amount,0::numeric) WHEN bl.direction = 'incoming'::text THEN - COALESCE(bl.net_amount,0::numeric) ELSE 0::numeric END) AS saldo,
       CASE WHEN sum(CASE WHEN bl.direction = 'outgoing'::text THEN COALESCE(bl.net_amount,0::numeric) WHEN bl.direction = 'incoming'::text THEN - COALESCE(bl.net_amount,0::numeric) ELSE 0::numeric END) >= 0::numeric THEN 'Haben'::text ELSE 'Soll'::text END AS richtung
  FROM vw_booking_lines_effective bl
  LEFT JOIN vouchers v ON v.id = bl.voucher_id
  LEFT JOIN outgoing_vouchers ov ON ov.id = bl.outgoing_id
  LEFT JOIN account_groups ag ON bl.account_skr >= ag.skr_min AND bl.account_skr <= ag.skr_max
 WHERE COALESCE(v.status, ov.status) NOT IN ('draft','cancelled')
 GROUP BY 1, bl.account_skr, COALESCE(ag.gruppe, 'Unklassifiziert'::text)
 ORDER BY 1, bl.account_skr;

-- 7) Unklassifizierte Konten
CREATE OR REPLACE VIEW vw_unclassified_accounts AS
SELECT DISTINCT bl.account_skr
  FROM vw_booking_lines_effective bl
  LEFT JOIN account_groups ag ON bl.account_skr >= ag.skr_min AND bl.account_skr <= ag.skr_max
 WHERE ag.id IS NULL
 ORDER BY bl.account_skr;

COMMIT;
