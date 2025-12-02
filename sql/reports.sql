CREATE OR REPLACE VIEW public.vw_ust_report AS
WITH basis AS (
  SELECT
    bl.id,
    bl.direction,
    bl.net_amount,
    bl.tax_amount,
    bl.gross_amount,
    bl.tax_type,
    COALESCE(v.status, ov.status) AS status,
    DATE_TRUNC(
      'month',
      COALESCE(v.booking_date, v.voucher_date, ov.booking_date, ov.voucher_date)
    ) AS periode
  FROM public.booking_lines bl
  LEFT JOIN public.vouchers v         ON v.id  = bl.voucher_id
  LEFT JOIN public.outgoing_vouchers ov ON ov.id = bl.outgoing_id
)
SELECT
  b.periode,
  /* Umsatzsteuer (Output) */
  SUM(
    CASE
      WHEN (b.tax_type LIKE 'ust%' OR (b.direction='outgoing' AND COALESCE(b.tax_amount,0) <> 0))
      THEN COALESCE(b.tax_amount,0) ELSE 0
    END
  ) AS ust_output,

  /* Vorsteuer (Input) */
  SUM(
    CASE
      WHEN (b.tax_type LIKE 'vst%' OR (b.direction='incoming' AND COALESCE(b.tax_amount,0) <> 0))
      THEN COALESCE(b.tax_amount,0) ELSE 0
    END
  ) AS ust_input,

  /* Nettoumsatz = nur Ausgangsseite */
  SUM(
    CASE
      WHEN (b.tax_type LIKE 'ust%' OR b.direction='outgoing')
      THEN COALESCE(b.net_amount,0) ELSE 0
    END
  ) AS nettoumsatz,

  /* Nettoeinkauf = nur Eingangsseite */
  SUM(
    CASE
      WHEN (b.tax_type LIKE 'vst%' OR b.direction='incoming')
      THEN COALESCE(b.net_amount,0) ELSE 0
    END
  ) AS nettoeinkauf,

  /* Zahllast */
  SUM(
    CASE
      WHEN (b.tax_type LIKE 'ust%' OR (b.direction='outgoing' AND COALESCE(b.tax_amount,0) <> 0))
      THEN COALESCE(b.tax_amount,0) ELSE 0
    END
  )
  -
  SUM(
    CASE
      WHEN (b.tax_type LIKE 'vst%' OR (b.direction='incoming' AND COALESCE(b.tax_amount,0) <> 0))
      THEN COALESCE(b.tax_amount,0) ELSE 0
    END
  ) AS zahlbetrag

FROM basis b
WHERE COALESCE(b.status, 'draft') <> 'draft'
GROUP BY 1
ORDER BY 1;



CREATE OR REPLACE VIEW public.vw_guv_report AS
SELECT
    DATE_TRUNC('month', v.booking_date) AS periode,
    bl.direction,
    SUM(bl.net_amount) AS netto_summe,
    SUM(bl.tax_amount) AS steuer_summe,
    SUM(bl.gross_amount) AS brutto_summe
FROM public.booking_lines bl
JOIN public.vouchers v ON v.id = bl.voucher_id
WHERE v.status = 'booked'
GROUP BY 1, 2
ORDER BY 1, 2;


CREATE INDEX IF NOT EXISTS idx_booking_lines_voucher_id ON public.booking_lines(voucher_id);
CREATE INDEX IF NOT EXISTS idx_booking_lines_tax_type   ON public.booking_lines(tax_type);
CREATE INDEX IF NOT EXISTS idx_vouchers_booking_date    ON public.vouchers(booking_date);
CREATE INDEX IF NOT EXISTS idx_vouchers_status          ON public.vouchers(status);

CREATE OR REPLACE VIEW public.vw_guv_classified AS
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
       ON g.account_skr BETWEEN ag.skr_min AND ag.skr_max
ORDER BY g.periode, g.account_skr;



CREATE TABLE public.account_groups (
    id SERIAL PRIMARY KEY,
    skr_min text NOT NULL,
    skr_max text NOT NULL,
    gruppe text NOT NULL,
    beschreibung text,
    created_at timestamp without time zone DEFAULT now()
);

COMMENT ON TABLE public.account_groups IS 'Kontengruppen-Mapping für GuV- und Bilanz-Klassifizierung';
COMMENT ON COLUMN public.account_groups.skr_min IS 'untere Grenze SKR-Kontonummer (inklusive)';
COMMENT ON COLUMN public.account_groups.skr_max IS 'obere Grenze SKR-Kontonummer (inklusive)';
COMMENT ON COLUMN public.account_groups.gruppe IS 'Klassifizierungsbezeichnung (z. B. Aufwand, Ertrag, Aktiva, Passiva)';


INSERT INTO public.account_groups (skr_min, skr_max, gruppe, beschreibung) VALUES
('0000','0999','Aktiva – Anlagevermögen','Langfristige Vermögenswerte'),
('1000','1999','Aktiva – Umlaufvermögen','Kurzfristige Vermögenswerte'),
('2000','2999','Passiva – Eigenkapital','Eigenkapital'),
('3000','6999','Aufwand (GuV – Soll)','Betriebliche Aufwendungen'),
('7000','7999','Finanzergebnis','Finanzergebnis und Zinsen'),
('8000','8999','Ertrag (GuV – Haben)','Betriebliche Erträge'),
('9000','9999','Abschluss- / Steuerkonten','Steuerliche Abschlusskonten');



CREATE OR REPLACE VIEW public.vw_guv_grouped AS
SELECT
    DATE_TRUNC('month', g.periode) AS periode,
    COALESCE(c.bilanz_gruppe, 'Unklassifiziert') AS bilanz_gruppe,
    SUM(COALESCE(g.netto_summe, 0))   AS netto_summe,
    SUM(COALESCE(g.steuer_summe, 0))  AS steuer_summe,
    SUM(COALESCE(g.brutto_summe, 0))  AS brutto_summe
FROM public.vw_guv_classified g
LEFT JOIN public.account_groups ag
       ON g.account_skr BETWEEN ag.skr_min AND ag.skr_max
LEFT JOIN LATERAL (SELECT ag.gruppe AS bilanz_gruppe) c ON TRUE
GROUP BY 1, 2
ORDER BY 1, 2;


CREATE OR REPLACE VIEW public.vw_guv_result AS
SELECT
    DATE_TRUNC('year', periode) AS jahr,
    CASE
        WHEN bilanz_gruppe ILIKE '%Ertrag%' THEN 'Ertrag'
        WHEN bilanz_gruppe ILIKE '%Aufwand%' THEN 'Aufwand'
        ELSE 'Neutral'
    END AS kategorie,
    SUM(COALESCE(netto_summe,0)) AS netto_summe
FROM public.vw_guv_grouped
GROUP BY 1,2
ORDER BY 1,2;


CREATE OR REPLACE VIEW public.vw_journal AS
SELECT
    COALESCE(v.voucher_date, ov.voucher_date) AS datum,
    bl.direction,
    bl.account_skr,
    bl.description,
    bl.net_amount,
    bl.tax_amount,
    bl.gross_amount,
    COALESCE(v.partner_name, ov.partner_name) AS partner,
    COALESCE(v.voucher_number, ov.voucher_number) AS belegnummer,
    COALESCE(v.document_type, ov.document_type) AS belegart
FROM public.booking_lines bl
LEFT JOIN public.vouchers v         ON v.id  = bl.voucher_id
LEFT JOIN public.outgoing_vouchers ov ON ov.id = bl.outgoing_id
WHERE COALESCE(v.status, ov.status) NOT IN ('draft')
ORDER BY datum, account_skr;


CREATE OR REPLACE VIEW public.vw_unclassified_accounts AS
SELECT DISTINCT bl.account_skr
FROM public.booking_lines bl
LEFT JOIN public.account_groups ag
       ON bl.account_skr BETWEEN ag.skr_min AND ag.skr_max
WHERE ag.id IS NULL
ORDER BY bl.account_skr;


CREATE OR REPLACE VIEW public.vw_susa AS
SELECT
    bl.account_skr,
    COALESCE(a.gruppe, 'Unklassifiziert') AS bilanz_gruppe,
    SUM(CASE WHEN bl.direction = 'incoming' THEN COALESCE(bl.net_amount,0) ELSE 0 END) AS soll_summe,
    SUM(CASE WHEN bl.direction = 'outgoing' THEN COALESCE(bl.net_amount,0) ELSE 0 END) AS haben_summe,
    SUM(
        CASE
            WHEN bl.direction = 'outgoing' THEN COALESCE(bl.net_amount,0)
            WHEN bl.direction = 'incoming' THEN -COALESCE(bl.net_amount,0)
            ELSE 0
        END
    ) AS saldo,
    CASE
        WHEN SUM(
            CASE
                WHEN bl.direction = 'outgoing' THEN COALESCE(bl.net_amount,0)
                WHEN bl.direction = 'incoming' THEN -COALESCE(bl.net_amount,0)
                ELSE 0
            END
        ) >= 0 THEN 'Haben'
        ELSE 'Soll'
    END AS richtung
FROM public.booking_lines bl
LEFT JOIN public.account_groups a
       ON bl.account_skr BETWEEN a.skr_min AND a.skr_max
LEFT JOIN public.vouchers v
       ON v.id = bl.voucher_id
LEFT JOIN public.outgoing_vouchers ov
       ON ov.id = bl.outgoing_id
WHERE COALESCE(v.status, ov.status) NOT IN ('draft')
GROUP BY 1,2
ORDER BY bl.account_skr;


CREATE OR REPLACE VIEW public.vw_susa_monthly AS
SELECT
    DATE_TRUNC(
        'month',
        COALESCE(v.booking_date, v.voucher_date, ov.booking_date, ov.voucher_date)
    ) AS periode,
    bl.account_skr,
    COALESCE(ag.gruppe, 'Unklassifiziert') AS bilanz_gruppe,
    SUM(CASE WHEN bl.direction = 'incoming' THEN COALESCE(bl.net_amount, 0) ELSE 0 END) AS soll_summe,
    SUM(CASE WHEN bl.direction = 'outgoing' THEN COALESCE(bl.net_amount, 0) ELSE 0 END) AS haben_summe,
    SUM(
        CASE
            WHEN bl.direction = 'outgoing' THEN COALESCE(bl.net_amount, 0)
            WHEN bl.direction = 'incoming' THEN -COALESCE(bl.net_amount, 0)
            ELSE 0
        END
    ) AS saldo,
    CASE
        WHEN SUM(
            CASE
                WHEN bl.direction = 'outgoing' THEN COALESCE(bl.net_amount, 0)
                WHEN bl.direction = 'incoming' THEN -COALESCE(bl.net_amount, 0)
                ELSE 0
            END
        ) >= 0 THEN 'Haben'
        ELSE 'Soll'
    END AS richtung
FROM public.booking_lines bl
LEFT JOIN public.vouchers v
       ON v.id = bl.voucher_id
LEFT JOIN public.outgoing_vouchers ov
       ON ov.id = bl.outgoing_id
LEFT JOIN public.account_groups ag
       ON bl.account_skr BETWEEN ag.skr_min AND ag.skr_max
WHERE COALESCE(v.status, ov.status) NOT IN ('draft')
GROUP BY 1, 2, 3
ORDER BY 1, 2;


CREATE OR REPLACE VIEW public.vw_susa_monthly_cumulative AS
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
    CASE
        WHEN SUM(saldo) OVER (
            PARTITION BY account_skr
            ORDER BY periode
            ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW
        ) >= 0 THEN 'Haben'
        ELSE 'Soll'
    END AS richtung
FROM public.vw_susa_monthly
ORDER BY account_skr, periode;


CREATE TABLE public.depreciations (
    id SERIAL PRIMARY KEY,
    asset_name text NOT NULL,
    account_skr text NOT NULL,
    acquisition_date date NOT NULL,
    acquisition_value numeric(12,2) NOT NULL,
    useful_life_years integer NOT NULL,
    method text DEFAULT 'linear',
    note text,
    created_at timestamp without time zone DEFAULT now()
);


CREATE OR REPLACE VIEW public.vw_afa_schedule AS
SELECT
    d.id,
    d.asset_name,
    d.account_skr,
    d.acquisition_date,
    d.acquisition_value,
    d.useful_life_years,
    ROUND(d.acquisition_value / d.useful_life_years, 2) AS afa_jahr,
    (d.acquisition_value / d.useful_life_years) AS afa_raw,
    (generate_series(
        date_part('year', d.acquisition_date)::int,
        (date_part('year', d.acquisition_date)::int + d.useful_life_years - 1)
     ))::int AS jahr,
    d.method
FROM public.depreciations d
ORDER BY d.account_skr, jahr;
