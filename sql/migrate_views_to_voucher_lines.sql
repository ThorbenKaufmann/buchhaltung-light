-- Migration: Rewrite views from booking_lines_legacy to voucher_lines/outgoing_lines.
-- Must DROP+recreate (not CREATE OR REPLACE) because column types change.
-- Also truncates booking_lines_legacy (data already migrated to voucher_lines).
-- Safe to re-run.

-- ----------------------------------------------------------------
-- Drop full view chain (leaf → root, then dependents auto-dropped)
-- ----------------------------------------------------------------
DROP VIEW IF EXISTS public.vw_guv_result            CASCADE;
DROP VIEW IF EXISTS public.vw_guv_grouped           CASCADE;
DROP VIEW IF EXISTS public.vw_guv_classified        CASCADE;
DROP VIEW IF EXISTS public.vw_guv_report            CASCADE;
DROP VIEW IF EXISTS public.vw_susa_monthly_cumulative CASCADE;
DROP VIEW IF EXISTS public.vw_susa_monthly          CASCADE;
DROP VIEW IF EXISTS public.vw_susa                  CASCADE;
DROP VIEW IF EXISTS public.vw_journal               CASCADE;
DROP VIEW IF EXISTS public.vw_unclassified_accounts CASCADE;
DROP VIEW IF EXISTS public.vw_ust_report            CASCADE;


-- ================================================================
-- Recreate: base views first, then dependents
-- ================================================================

-- ----------------------------------------------------------------
-- vw_guv_report  (base for vw_guv_classified chain)
-- ----------------------------------------------------------------
CREATE VIEW public.vw_guv_report AS
SELECT
    DATE_TRUNC('month', COALESCE(v.booking_date, v.voucher_date)::timestamptz) AS periode,
    'incoming'::text AS direction,
    vl.account_skr,
    SUM(COALESCE(vl.net_amount, 0)) AS netto_summe,
    SUM(COALESCE(vl.tax_amount, 0)) AS steuer_summe,
    SUM(COALESCE(vl.net_amount + vl.tax_amount, 0)) AS brutto_summe
FROM public.voucher_lines vl
JOIN public.vouchers v ON v.id = vl.voucher_id
WHERE v.status <> 'draft'
GROUP BY 1, 2, 3

UNION ALL

SELECT
    DATE_TRUNC('month', COALESCE(ov.booking_date, ov.voucher_date)::timestamptz) AS periode,
    'outgoing'::text AS direction,
    ol.account_skr,
    SUM(COALESCE(ol.net_amount, 0)) AS netto_summe,
    SUM(COALESCE(ol.tax_amount, 0)) AS steuer_summe,
    SUM(COALESCE(ol.net_amount + ol.tax_amount, 0)) AS brutto_summe
FROM public.outgoing_lines ol
JOIN public.outgoing_vouchers ov ON ov.id = ol.outgoing_id
WHERE ov.status <> 'draft'
GROUP BY 1, 2, 3

ORDER BY 1, 2, 3;


-- ----------------------------------------------------------------
-- vw_guv_classified  (depends on vw_guv_report — unchanged logic)
-- ----------------------------------------------------------------
CREATE VIEW public.vw_guv_classified AS
SELECT
    g.periode,
    g.direction,
    g.account_skr,
    CASE
        WHEN g.direction = 'outgoing' THEN 'Haben'
        WHEN g.direction = 'incoming' THEN 'Soll'
        ELSE 'Neutral'
    END AS soll_haben,
    COALESCE(ag.gruppe, 'Unklassifiziert') AS bilanz_gruppe,
    g.netto_summe,
    g.steuer_summe,
    g.brutto_summe
FROM public.vw_guv_report g
LEFT JOIN public.account_groups ag
       ON g.account_skr >= ag.skr_min AND g.account_skr <= ag.skr_max
ORDER BY g.periode, g.account_skr;


-- ----------------------------------------------------------------
-- vw_guv_grouped  (depends on vw_guv_classified — unchanged logic)
-- ----------------------------------------------------------------
CREATE VIEW public.vw_guv_grouped AS
SELECT
    DATE_TRUNC('month', g.periode) AS periode,
    COALESCE(c.bilanz_gruppe, 'Unklassifiziert') AS bilanz_gruppe,
    SUM(COALESCE(g.netto_summe,   0)) AS netto_summe,
    SUM(COALESCE(g.steuer_summe,  0)) AS steuer_summe,
    SUM(COALESCE(g.brutto_summe,  0)) AS brutto_summe
FROM public.vw_guv_classified g
LEFT JOIN public.account_groups ag ON g.account_skr >= ag.skr_min AND g.account_skr <= ag.skr_max
LEFT JOIN LATERAL (SELECT ag.gruppe AS bilanz_gruppe) c ON true
GROUP BY DATE_TRUNC('month', g.periode), COALESCE(c.bilanz_gruppe, 'Unklassifiziert')
ORDER BY DATE_TRUNC('month', g.periode), COALESCE(c.bilanz_gruppe, 'Unklassifiziert');


-- ----------------------------------------------------------------
-- vw_guv_result  (depends on vw_guv_grouped — unchanged logic)
-- ----------------------------------------------------------------
CREATE VIEW public.vw_guv_result AS
SELECT
    DATE_TRUNC('year', periode) AS jahr,
    CASE
        WHEN bilanz_gruppe ILIKE '%Ertrag%'  THEN 'Ertrag'
        WHEN bilanz_gruppe ILIKE '%Aufwand%' THEN 'Aufwand'
        ELSE 'Neutral'
    END AS kategorie,
    SUM(COALESCE(netto_summe, 0)) AS netto_summe
FROM public.vw_guv_grouped
GROUP BY 1, 2
ORDER BY 1, 2;


-- ----------------------------------------------------------------
-- vw_journal
-- ----------------------------------------------------------------
CREATE VIEW public.vw_journal AS
SELECT
    COALESCE(v.booking_date, v.voucher_date) AS datum,
    'incoming'::text AS direction,
    vl.account_skr,
    vl.description,
    vl.net_amount,
    vl.tax_amount,
    (vl.net_amount + vl.tax_amount) AS gross_amount,
    v.partner_name  AS partner,
    v.voucher_number AS belegnummer,
    v.document_type  AS belegart
FROM public.voucher_lines vl
JOIN public.vouchers v ON v.id = vl.voucher_id
WHERE v.status <> 'draft'

UNION ALL

SELECT
    COALESCE(ov.booking_date, ov.voucher_date) AS datum,
    'outgoing'::text AS direction,
    ol.account_skr,
    ol.description,
    ol.net_amount,
    ol.tax_amount,
    (ol.net_amount + ol.tax_amount) AS gross_amount,
    ov.partner_name  AS partner,
    ov.voucher_number AS belegnummer,
    ov.document_type  AS belegart
FROM public.outgoing_lines ol
JOIN public.outgoing_vouchers ov ON ov.id = ol.outgoing_id
WHERE ov.status <> 'draft'

ORDER BY datum, account_skr;


-- ----------------------------------------------------------------
-- vw_susa  (base, all-time totals)
-- ----------------------------------------------------------------
CREATE VIEW public.vw_susa AS
WITH all_lines AS (
    SELECT vl.account_skr, COALESCE(vl.net_amount, 0) AS net_amount, 'incoming'::text AS direction
    FROM public.voucher_lines vl
    JOIN public.vouchers v ON v.id = vl.voucher_id
    WHERE v.status <> 'draft'

    UNION ALL

    SELECT ol.account_skr, COALESCE(ol.net_amount, 0) AS net_amount, 'outgoing'::text AS direction
    FROM public.outgoing_lines ol
    JOIN public.outgoing_vouchers ov ON ov.id = ol.outgoing_id
    WHERE ov.status <> 'draft'
)
SELECT
    al.account_skr,
    COALESCE(ag.gruppe, 'Unklassifiziert') AS bilanz_gruppe,
    SUM(CASE WHEN al.direction = 'incoming' THEN  al.net_amount ELSE 0 END) AS soll_summe,
    SUM(CASE WHEN al.direction = 'outgoing' THEN  al.net_amount ELSE 0 END) AS haben_summe,
    SUM(CASE WHEN al.direction = 'outgoing' THEN  al.net_amount
             WHEN al.direction = 'incoming' THEN -al.net_amount
             ELSE 0 END) AS saldo,
    CASE WHEN SUM(CASE WHEN al.direction = 'outgoing' THEN  al.net_amount
                       WHEN al.direction = 'incoming' THEN -al.net_amount
                       ELSE 0 END) >= 0 THEN 'Haben' ELSE 'Soll' END AS richtung
FROM all_lines al
LEFT JOIN public.account_groups ag ON al.account_skr >= ag.skr_min AND al.account_skr <= ag.skr_max
GROUP BY al.account_skr, COALESCE(ag.gruppe, 'Unklassifiziert')
ORDER BY al.account_skr;


-- ----------------------------------------------------------------
-- vw_susa_monthly  (base for cumulative)
-- ----------------------------------------------------------------
CREATE VIEW public.vw_susa_monthly AS
WITH all_lines AS (
    SELECT
        vl.account_skr,
        COALESCE(vl.net_amount, 0) AS net_amount,
        'incoming'::text AS direction,
        COALESCE(v.booking_date, v.voucher_date) AS datum
    FROM public.voucher_lines vl
    JOIN public.vouchers v ON v.id = vl.voucher_id
    WHERE v.status <> 'draft'

    UNION ALL

    SELECT
        ol.account_skr,
        COALESCE(ol.net_amount, 0) AS net_amount,
        'outgoing'::text AS direction,
        COALESCE(ov.booking_date, ov.voucher_date) AS datum
    FROM public.outgoing_lines ol
    JOIN public.outgoing_vouchers ov ON ov.id = ol.outgoing_id
    WHERE ov.status <> 'draft'
)
SELECT
    DATE_TRUNC('month', datum::timestamptz) AS periode,
    al.account_skr,
    COALESCE(ag.gruppe, 'Unklassifiziert') AS bilanz_gruppe,
    SUM(CASE WHEN al.direction = 'incoming' THEN  al.net_amount ELSE 0 END) AS soll_summe,
    SUM(CASE WHEN al.direction = 'outgoing' THEN  al.net_amount ELSE 0 END) AS haben_summe,
    SUM(CASE WHEN al.direction = 'outgoing' THEN  al.net_amount
             WHEN al.direction = 'incoming' THEN -al.net_amount
             ELSE 0 END) AS saldo,
    CASE WHEN SUM(CASE WHEN al.direction = 'outgoing' THEN  al.net_amount
                       WHEN al.direction = 'incoming' THEN -al.net_amount
                       ELSE 0 END) >= 0 THEN 'Haben' ELSE 'Soll' END AS richtung
FROM all_lines al
LEFT JOIN public.account_groups ag ON al.account_skr >= ag.skr_min AND al.account_skr <= ag.skr_max
GROUP BY DATE_TRUNC('month', datum::timestamptz), al.account_skr, COALESCE(ag.gruppe, 'Unklassifiziert')
ORDER BY DATE_TRUNC('month', datum::timestamptz), al.account_skr;


-- ----------------------------------------------------------------
-- vw_susa_monthly_cumulative  (depends on vw_susa_monthly — unchanged logic)
-- ----------------------------------------------------------------
CREATE VIEW public.vw_susa_monthly_cumulative AS
SELECT
    periode,
    account_skr,
    bilanz_gruppe,
    soll_summe,
    haben_summe,
    saldo,
    SUM(saldo) OVER (
        PARTITION BY account_skr
        ORDER BY periode
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) AS endsaldo,
    CASE WHEN SUM(saldo) OVER (
        PARTITION BY account_skr
        ORDER BY periode
        ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
    ) >= 0 THEN 'Haben' ELSE 'Soll' END AS richtung
FROM public.vw_susa_monthly
ORDER BY account_skr, periode;


-- ----------------------------------------------------------------
-- vw_unclassified_accounts
-- ----------------------------------------------------------------
CREATE VIEW public.vw_unclassified_accounts AS
SELECT DISTINCT account_skr
FROM (
    SELECT vl.account_skr FROM public.voucher_lines vl
    UNION ALL
    SELECT ol.account_skr FROM public.outgoing_lines ol
) all_accounts
LEFT JOIN public.account_groups ag ON account_skr >= ag.skr_min AND account_skr <= ag.skr_max
WHERE ag.id IS NULL
ORDER BY account_skr;


-- ----------------------------------------------------------------
-- vw_ust_report
-- ----------------------------------------------------------------
CREATE VIEW public.vw_ust_report AS
WITH basis AS (
    SELECT
        vl.net_amount,
        vl.tax_amount,
        'incoming'::text AS direction,
        DATE_TRUNC('month', COALESCE(v.booking_date, v.voucher_date)::timestamptz) AS periode
    FROM public.voucher_lines vl
    JOIN public.vouchers v ON v.id = vl.voucher_id
    WHERE v.status <> 'draft'

    UNION ALL

    SELECT
        ol.net_amount,
        ol.tax_amount,
        'outgoing'::text AS direction,
        DATE_TRUNC('month', COALESCE(ov.booking_date, ov.voucher_date)::timestamptz) AS periode
    FROM public.outgoing_lines ol
    JOIN public.outgoing_vouchers ov ON ov.id = ol.outgoing_id
    WHERE ov.status <> 'draft'
)
SELECT
    b.periode,
    SUM(CASE WHEN b.direction = 'outgoing' AND COALESCE(b.tax_amount, 0) <> 0
             THEN COALESCE(b.tax_amount, 0) ELSE 0 END) AS ust_output,
    SUM(CASE WHEN b.direction = 'incoming' AND COALESCE(b.tax_amount, 0) <> 0
             THEN COALESCE(b.tax_amount, 0) ELSE 0 END) AS ust_input,
    SUM(CASE WHEN b.direction = 'outgoing' THEN COALESCE(b.net_amount, 0) ELSE 0 END) AS nettoumsatz,
    SUM(CASE WHEN b.direction = 'incoming' THEN COALESCE(b.net_amount, 0) ELSE 0 END) AS nettoeinkauf,
    SUM(CASE WHEN b.direction = 'outgoing' AND COALESCE(b.tax_amount, 0) <> 0
             THEN COALESCE(b.tax_amount, 0) ELSE 0 END) -
    SUM(CASE WHEN b.direction = 'incoming' AND COALESCE(b.tax_amount, 0) <> 0
             THEN COALESCE(b.tax_amount, 0) ELSE 0 END) AS zahlbetrag
FROM basis b
GROUP BY b.periode
ORDER BY b.periode;


-- ----------------------------------------------------------------
-- Clear legacy table (data already migrated to voucher_lines)
-- ----------------------------------------------------------------
TRUNCATE TABLE public.booking_lines_legacy;
