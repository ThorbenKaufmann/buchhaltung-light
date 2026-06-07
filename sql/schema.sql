--
-- PostgreSQL database dump
--


-- Dumped from database version 14.22 (Ubuntu 14.22-0ubuntu0.22.04.1)
-- Dumped by pg_dump version 16.13 (Ubuntu 16.13-0ubuntu0.24.04.1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: public; Type: SCHEMA; Schema: -; Owner: -
--

-- *not* creating schema, since initdb creates it


SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: account_groups; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.account_groups (
    id integer NOT NULL,
    skr_min text NOT NULL,
    skr_max text NOT NULL,
    gruppe text NOT NULL,
    beschreibung text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: account_groups_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.account_groups_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: account_groups_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.account_groups_id_seq OWNED BY public.account_groups.id;


--
-- Name: accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.accounts (
    id integer NOT NULL,
    name text NOT NULL,
    iban text,
    bic text,
    type text,
    currency character(3) DEFAULT 'EUR'::bpchar,
    is_active boolean DEFAULT true,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT accounts_type_check CHECK ((type = ANY (ARRAY['bank'::text, 'credit'::text, 'paypal'::text, 'cash'::text, 'savings'::text])))
);


--
-- Name: accounts_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.accounts_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: accounts_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.accounts_id_seq OWNED BY public.accounts.id;


--
-- Name: audit_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.audit_log (
    id integer NOT NULL,
    entity text NOT NULL,
    entity_id integer NOT NULL,
    action text NOT NULL,
    field text,
    old_value text,
    new_value text,
    reason text,
    changed_at timestamp without time zone DEFAULT now()
);


--
-- Name: audit_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.audit_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: audit_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.audit_log_id_seq OWNED BY public.audit_log.id;


--
-- Name: auto_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.auto_rules (
    id integer NOT NULL,
    match_pattern text NOT NULL,
    direction text NOT NULL,
    account_skr text NOT NULL,
    tax_rate numeric(5,2) DEFAULT 19,
    tax_type text DEFAULT 'ust'::text,
    description text,
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT auto_rules_direction_check CHECK ((direction = ANY (ARRAY['incoming'::text, 'outgoing'::text])))
);


--
-- Name: auto_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.auto_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: auto_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.auto_rules_id_seq OWNED BY public.auto_rules.id;


--
-- Name: booking_lines_legacy; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.booking_lines_legacy (
    id integer NOT NULL,
    direction text NOT NULL,
    voucher_id integer,
    outgoing_id integer,
    account_skr text NOT NULL,
    description text,
    net_amount numeric(12,2),
    tax_rate numeric(5,2),
    tax_amount numeric(12,2),
    gross_amount numeric(12,2),
    created_at timestamp without time zone DEFAULT now(),
    receipt_status text DEFAULT 'complete'::text,
    tax_type text,
    CONSTRAINT booking_lines_direction_check CHECK ((direction = ANY (ARRAY['incoming'::text, 'outgoing'::text]))),
    CONSTRAINT booking_lines_receipt_status_check CHECK ((receipt_status = ANY (ARRAY['complete'::text, 'pending'::text, 'missing'::text, 'incomplete'::text]))),
    CONSTRAINT booking_lines_tax_type_check CHECK (((tax_type IS NULL) OR (tax_type = ANY (ARRAY['vst19'::text, 'vst7'::text, 'vst0'::text, 'ust19'::text, 'ust7'::text, 'ust0'::text, 'ig_erwerb'::text, 'reverse_charge'::text]))))
);


--
-- Name: booking_lines_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.booking_lines_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: booking_lines_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.booking_lines_id_seq OWNED BY public.booking_lines_legacy.id;


--
-- Name: booking_lines_new; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.booking_lines_new (
    id integer NOT NULL,
    source_type text NOT NULL,
    source_id integer NOT NULL,
    account_skr text NOT NULL,
    amount numeric(12,2) NOT NULL
);


--
-- Name: booking_lines_new_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.booking_lines_new_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: booking_lines_new_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.booking_lines_new_id_seq OWNED BY public.booking_lines_new.id;


--
-- Name: booking_rules; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.booking_rules (
    id integer NOT NULL,
    pattern text NOT NULL,
    default_account text NOT NULL,
    default_tax numeric(5,2) DEFAULT 19,
    direction text DEFAULT 'incoming'::text,
    note text,
    tax_type text,
    is_internal boolean DEFAULT false,
    is_private boolean DEFAULT false,
    is_cyclic boolean DEFAULT false,
    CONSTRAINT booking_rules_direction_check CHECK ((direction = ANY (ARRAY['incoming'::text, 'outgoing'::text]))),
    CONSTRAINT booking_rules_tax_type_check CHECK (((tax_type IS NULL) OR (tax_type = ANY (ARRAY['vst19'::text, 'vst7'::text, 'vst0'::text, 'ust19'::text, 'ust7'::text, 'ust0'::text, 'ig_erwerb'::text, 'reverse_charge'::text]))))
);


--
-- Name: booking_rules_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.booking_rules_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: booking_rules_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.booking_rules_id_seq OWNED BY public.booking_rules.id;


--
-- Name: depreciations; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.depreciations (
    id integer NOT NULL,
    asset_name text NOT NULL,
    account_skr text NOT NULL,
    acquisition_date date NOT NULL,
    acquisition_value numeric(12,2) NOT NULL,
    useful_life_years integer NOT NULL,
    method text DEFAULT 'linear'::text,
    note text,
    created_at timestamp without time zone DEFAULT now(),
    start_year integer,
    remaining_value numeric(12,2) DEFAULT NULL::numeric,
    last_afa_year integer,
    last_afa_run timestamp without time zone
);


--
-- Name: depreciations_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.depreciations_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: depreciations_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.depreciations_id_seq OWNED BY public.depreciations.id;


--
-- Name: outgoing_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.outgoing_documents (
    id integer NOT NULL,
    outgoing_id integer NOT NULL,
    file_name text NOT NULL,
    file_path text NOT NULL,
    mime_type text,
    file_hash character(64),
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: outgoing_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.outgoing_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: outgoing_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.outgoing_documents_id_seq OWNED BY public.outgoing_documents.id;


--
-- Name: outgoing_lines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.outgoing_lines (
    id integer NOT NULL,
    outgoing_id integer NOT NULL,
    account_skr text NOT NULL,
    description text,
    net_amount numeric(12,2),
    tax_rate numeric(5,2),
    tax_amount numeric(12,2),
    cost_center text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: outgoing_lines_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.outgoing_lines_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: outgoing_lines_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.outgoing_lines_id_seq OWNED BY public.outgoing_lines.id;


--
-- Name: outgoing_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.outgoing_links (
    id integer NOT NULL,
    outgoing_id integer NOT NULL,
    transaction_id integer NOT NULL,
    link_type text,
    amount numeric(12,2),
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT outgoing_links_link_type_check CHECK ((link_type = ANY (ARRAY['payment'::text, 'refund'::text, 'split'::text, 'open'::text])))
);


--
-- Name: outgoing_links_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.outgoing_links_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: outgoing_links_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.outgoing_links_id_seq OWNED BY public.outgoing_links.id;


--
-- Name: outgoing_vouchers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.outgoing_vouchers (
    id integer NOT NULL,
    voucher_number text,
    voucher_date date NOT NULL,
    booking_date date,
    partner_name text NOT NULL,
    description text,
    total_amount numeric(12,2),
    currency character(3) DEFAULT 'EUR'::bpchar,
    document_type text,
    status text DEFAULT 'draft'::text,
    source text,
    created_at timestamp without time zone DEFAULT now(),
    payment_due_date date,
    receipt_status text DEFAULT 'complete'::text,
    CONSTRAINT outgoing_vouchers_document_type_check CHECK ((document_type = ANY (ARRAY['invoice'::text, 'credit_note'::text, 'self_issued'::text]))),
    CONSTRAINT outgoing_vouchers_receipt_status_check CHECK ((receipt_status = ANY (ARRAY['complete'::text, 'pending'::text, 'missing'::text, 'incomplete'::text]))),
    CONSTRAINT outgoing_vouchers_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'sent'::text, 'paid'::text, 'archived'::text, 'cancelled'::text])))
);


--
-- Name: outgoing_vouchers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.outgoing_vouchers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: outgoing_vouchers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.outgoing_vouchers_id_seq OWNED BY public.outgoing_vouchers.id;


--
-- Name: self_vouchers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.self_vouchers (
    id integer NOT NULL,
    voucher_number text NOT NULL,
    created_at timestamp without time zone DEFAULT now(),
    voucher_date date NOT NULL,
    reason text NOT NULL,
    partner_name text,
    amount numeric(12,2) NOT NULL,
    currency character(3) DEFAULT 'EUR'::bpchar,
    reference_voucher_id integer,
    sha256_hash character(64),
    signed boolean DEFAULT false,
    file_path text,
    remarks text
);


--
-- Name: self_vouchers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.self_vouchers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: self_vouchers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.self_vouchers_id_seq OWNED BY public.self_vouchers.id;


--
-- Name: signature_log; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.signature_log (
    id integer NOT NULL,
    self_voucher_id integer,
    signed_at timestamp without time zone DEFAULT now(),
    signer text,
    signature_method text,
    signature_hash character(64)
);


--
-- Name: signature_log_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.signature_log_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: signature_log_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.signature_log_id_seq OWNED BY public.signature_log.id;


--
-- Name: skr03_accounts; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.skr03_accounts (
    id text NOT NULL,
    name text NOT NULL,
    default_tax numeric(5,2),
    category text,
    ust_code text,
    is_expense boolean DEFAULT false,
    is_revenue boolean DEFAULT false,
    is_active boolean DEFAULT true,
    remark text,
    is_internal boolean DEFAULT false
);


--
-- Name: transactions; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.transactions (
    id integer NOT NULL,
    account_id integer NOT NULL,
    booking_date date NOT NULL,
    value_date date,
    amount numeric(12,2) NOT NULL,
    currency character(3) DEFAULT 'EUR'::bpchar,
    counterpart_name text,
    counterpart_iban text,
    purpose text,
    category text,
    import_source text,
    raw_data jsonb,
    created_at timestamp without time zone DEFAULT now(),
    tx_hash character(64),
    is_private boolean DEFAULT false,
    is_internal boolean DEFAULT false,
    is_cyclic boolean DEFAULT false
);


--
-- Name: transactions_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.transactions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: transactions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.transactions_id_seq OWNED BY public.transactions.id;


--
-- Name: voucher_lines; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.voucher_lines (
    id integer NOT NULL,
    voucher_id integer NOT NULL,
    account_skr text NOT NULL,
    description text,
    net_amount numeric(12,2),
    tax_rate numeric(5,2),
    tax_amount numeric(12,2),
    cost_center text,
    created_at timestamp without time zone DEFAULT now()
);


--
-- Name: vouchers; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.vouchers (
    id integer NOT NULL,
    voucher_number text,
    voucher_date date NOT NULL,
    booking_date date,
    partner_name text,
    description text,
    total_amount numeric(12,2),
    currency character(3) DEFAULT 'EUR'::bpchar,
    document_type text,
    source text,
    status text DEFAULT 'draft'::text,
    created_at timestamp without time zone DEFAULT now(),
    payment_due_date date,
    receipt_status text DEFAULT 'complete'::text,
    CONSTRAINT vouchers_document_type_check CHECK ((document_type = ANY (ARRAY['invoice'::text, 'receipt'::text, 'contract'::text, 'self_issued'::text, 'other'::text]))),
    CONSTRAINT vouchers_receipt_status_check CHECK ((receipt_status = ANY (ARRAY['complete'::text, 'pending'::text, 'missing'::text, 'incomplete'::text]))),
    CONSTRAINT vouchers_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'booked'::text, 'archived'::text, 'paid'::text, 'cancelled'::text])))
);


--
-- Name: unified_voucher_lines; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.unified_voucher_lines AS
 SELECT vl.id,
    'incoming'::text AS type,
    v.voucher_date,
    v.booking_date,
    vl.account_skr,
    vl.net_amount,
    vl.tax_amount
   FROM (public.voucher_lines vl
     JOIN public.vouchers v ON ((v.id = vl.voucher_id)))
UNION ALL
 SELECT ol.id,
    'outgoing'::text AS type,
    ov.voucher_date,
    ov.booking_date,
    ol.account_skr,
    ol.net_amount,
    ol.tax_amount
   FROM (public.outgoing_lines ol
     JOIN public.outgoing_vouchers ov ON ((ov.id = ol.outgoing_id)));


--
-- Name: voucher_documents; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.voucher_documents (
    id integer NOT NULL,
    voucher_id integer NOT NULL,
    file_name text NOT NULL,
    file_path text NOT NULL,
    mime_type text,
    file_hash character(64),
    created_at timestamp without time zone DEFAULT now(),
    embedded_xml text,
    xml_type text,
    xml_valid boolean,
    CONSTRAINT voucher_documents_xml_type_check CHECK ((xml_type = ANY (ARRAY['zugferd'::text, 'xrechnung'::text, 'factur-x'::text])))
);


--
-- Name: voucher_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.voucher_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: voucher_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.voucher_documents_id_seq OWNED BY public.voucher_documents.id;


--
-- Name: voucher_lines_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.voucher_lines_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: voucher_lines_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.voucher_lines_id_seq OWNED BY public.voucher_lines.id;


--
-- Name: voucher_links; Type: TABLE; Schema: public; Owner: -
--

CREATE TABLE public.voucher_links (
    id integer NOT NULL,
    voucher_id integer NOT NULL,
    transaction_id integer NOT NULL,
    link_type text,
    amount numeric(12,2),
    created_at timestamp without time zone DEFAULT now(),
    CONSTRAINT voucher_links_link_type_check CHECK ((link_type = ANY (ARRAY['payment'::text, 'refund'::text, 'split'::text, 'open'::text])))
);


--
-- Name: voucher_links_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.voucher_links_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: voucher_links_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.voucher_links_id_seq OWNED BY public.voucher_links.id;


--
-- Name: vouchers_id_seq; Type: SEQUENCE; Schema: public; Owner: -
--

CREATE SEQUENCE public.vouchers_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


--
-- Name: vouchers_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: -
--

ALTER SEQUENCE public.vouchers_id_seq OWNED BY public.vouchers.id;


--
-- Name: vw_afa_schedule; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_afa_schedule AS
 WITH params AS (
         SELECT d.id,
            d.asset_name,
            d.account_skr,
            d.acquisition_date,
            d.acquisition_value,
            d.useful_life_years,
            d.start_year,
            d.remaining_value,
            d.method,
            (EXTRACT(year FROM d.acquisition_date))::integer AS acq_year,
            (13 - (EXTRACT(month FROM d.acquisition_date))::integer) AS months_first
           FROM public.depreciations d
        ),
        series AS (
         SELECT p.id,
            p.asset_name,
            p.account_skr,
            p.acquisition_date,
            p.acquisition_value,
            p.useful_life_years,
            p.start_year,
            p.remaining_value,
            p.method,
            p.acq_year,
            p.months_first,
            gs.gs AS jahr
           FROM params p,
            LATERAL generate_series(p.acq_year, (p.acq_year + p.useful_life_years)) gs(gs)
        )
 SELECT s.id,
    s.asset_name,
    s.account_skr,
    s.acquisition_date,
    s.acquisition_value,
    s.useful_life_years,
    s.jahr,
    round(
        CASE
            WHEN ((s.remaining_value IS NOT NULL) AND (s.start_year IS NOT NULL) AND (s.jahr = s.start_year)) THEN s.remaining_value
            WHEN (s.jahr = s.acq_year) THEN (s.acquisition_value / (s.useful_life_years)::numeric) * s.months_first / 12.0
            WHEN (s.jahr = (s.acq_year + s.useful_life_years)) THEN (s.acquisition_value / (s.useful_life_years)::numeric) * (12 - s.months_first) / 12.0
            ELSE (s.acquisition_value / (s.useful_life_years)::numeric)
        END, 2) AS afa_jahr,
    s.method
   FROM series s
  WHERE NOT (s.months_first = 12 AND s.jahr = (s.acq_year + s.useful_life_years))
  ORDER BY s.account_skr, s.jahr;


--
-- Name: vw_guv_report; Type: VIEW; Schema: public; Owner: -
--

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


--
-- Name: vw_guv_classified; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_guv_classified AS
 SELECT g.periode,
    g.direction,
    g.account_skr,
        CASE
            WHEN (g.direction = 'outgoing'::text) THEN 'Haben'::text
            WHEN (g.direction = 'incoming'::text) THEN 'Soll'::text
            ELSE 'Neutral'::text
        END AS soll_haben,
    COALESCE(ag.gruppe, 'Unklassifiziert'::text) AS bilanz_gruppe,
    g.netto_summe,
    g.steuer_summe,
    g.brutto_summe
   FROM (public.vw_guv_report g
     LEFT JOIN public.account_groups ag ON (((g.account_skr >= ag.skr_min) AND (g.account_skr <= ag.skr_max))))
  ORDER BY g.periode, g.account_skr;


--
-- Name: vw_guv_grouped; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_guv_grouped AS
 SELECT date_trunc('month'::text, g.periode) AS periode,
    COALESCE(c.bilanz_gruppe, 'Unklassifiziert'::text) AS bilanz_gruppe,
    sum(COALESCE(g.netto_summe, (0)::numeric)) AS netto_summe,
    sum(COALESCE(g.steuer_summe, (0)::numeric)) AS steuer_summe,
    sum(COALESCE(g.brutto_summe, (0)::numeric)) AS brutto_summe
   FROM ((public.vw_guv_classified g
     LEFT JOIN public.account_groups ag ON (((g.account_skr >= ag.skr_min) AND (g.account_skr <= ag.skr_max))))
     LEFT JOIN LATERAL ( SELECT ag.gruppe AS bilanz_gruppe) c ON (true))
  GROUP BY (date_trunc('month'::text, g.periode)), COALESCE(c.bilanz_gruppe, 'Unklassifiziert'::text)
  ORDER BY (date_trunc('month'::text, g.periode)), COALESCE(c.bilanz_gruppe, 'Unklassifiziert'::text);


--
-- Name: vw_guv_result; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_guv_result AS
 SELECT date_trunc('year'::text, vw_guv_grouped.periode) AS jahr,
        CASE
            WHEN (vw_guv_grouped.bilanz_gruppe ~~* '%Ertrag%'::text) THEN 'Ertrag'::text
            WHEN (vw_guv_grouped.bilanz_gruppe ~~* '%Aufwand%'::text) THEN 'Aufwand'::text
            ELSE 'Neutral'::text
        END AS kategorie,
    sum(COALESCE(vw_guv_grouped.netto_summe, (0)::numeric)) AS netto_summe
   FROM public.vw_guv_grouped
  GROUP BY (date_trunc('year'::text, vw_guv_grouped.periode)),
        CASE
            WHEN (vw_guv_grouped.bilanz_gruppe ~~* '%Ertrag%'::text) THEN 'Ertrag'::text
            WHEN (vw_guv_grouped.bilanz_gruppe ~~* '%Aufwand%'::text) THEN 'Aufwand'::text
            ELSE 'Neutral'::text
        END
  ORDER BY (date_trunc('year'::text, vw_guv_grouped.periode)),
        CASE
            WHEN (vw_guv_grouped.bilanz_gruppe ~~* '%Ertrag%'::text) THEN 'Ertrag'::text
            WHEN (vw_guv_grouped.bilanz_gruppe ~~* '%Aufwand%'::text) THEN 'Aufwand'::text
            ELSE 'Neutral'::text
        END;


--
-- Name: vw_journal; Type: VIEW; Schema: public; Owner: -
--

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


--
-- Name: vw_susa; Type: VIEW; Schema: public; Owner: -
--

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


--
-- Name: vw_susa_monthly; Type: VIEW; Schema: public; Owner: -
--

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


--
-- Name: vw_susa_monthly_cumulative; Type: VIEW; Schema: public; Owner: -
--

CREATE VIEW public.vw_susa_monthly_cumulative AS
 SELECT vw_susa_monthly.periode,
    vw_susa_monthly.account_skr,
    vw_susa_monthly.bilanz_gruppe,
    vw_susa_monthly.soll_summe,
    vw_susa_monthly.haben_summe,
    vw_susa_monthly.saldo,
    sum(vw_susa_monthly.saldo) OVER (PARTITION BY vw_susa_monthly.account_skr ORDER BY vw_susa_monthly.periode ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS endsaldo,
        CASE
            WHEN (sum(vw_susa_monthly.saldo) OVER (PARTITION BY vw_susa_monthly.account_skr ORDER BY vw_susa_monthly.periode ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) >= (0)::numeric) THEN 'Haben'::text
            ELSE 'Soll'::text
        END AS richtung
   FROM public.vw_susa_monthly
  ORDER BY vw_susa_monthly.account_skr, vw_susa_monthly.periode;


--
-- Name: vw_unclassified_accounts; Type: VIEW; Schema: public; Owner: -
--

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


--
-- Name: vw_ust_report; Type: VIEW; Schema: public; Owner: -
--

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


--
-- Name: account_groups id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_groups ALTER COLUMN id SET DEFAULT nextval('public.account_groups_id_seq'::regclass);


--
-- Name: accounts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts ALTER COLUMN id SET DEFAULT nextval('public.accounts_id_seq'::regclass);


--
-- Name: audit_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log ALTER COLUMN id SET DEFAULT nextval('public.audit_log_id_seq'::regclass);


--
-- Name: auto_rules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auto_rules ALTER COLUMN id SET DEFAULT nextval('public.auto_rules_id_seq'::regclass);


--
-- Name: booking_lines_legacy id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_lines_legacy ALTER COLUMN id SET DEFAULT nextval('public.booking_lines_id_seq'::regclass);


--
-- Name: booking_lines_new id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_lines_new ALTER COLUMN id SET DEFAULT nextval('public.booking_lines_new_id_seq'::regclass);


--
-- Name: booking_rules id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_rules ALTER COLUMN id SET DEFAULT nextval('public.booking_rules_id_seq'::regclass);


--
-- Name: depreciations id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.depreciations ALTER COLUMN id SET DEFAULT nextval('public.depreciations_id_seq'::regclass);


--
-- Name: outgoing_documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outgoing_documents ALTER COLUMN id SET DEFAULT nextval('public.outgoing_documents_id_seq'::regclass);


--
-- Name: outgoing_lines id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outgoing_lines ALTER COLUMN id SET DEFAULT nextval('public.outgoing_lines_id_seq'::regclass);


--
-- Name: outgoing_links id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outgoing_links ALTER COLUMN id SET DEFAULT nextval('public.outgoing_links_id_seq'::regclass);


--
-- Name: outgoing_vouchers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outgoing_vouchers ALTER COLUMN id SET DEFAULT nextval('public.outgoing_vouchers_id_seq'::regclass);


--
-- Name: self_vouchers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.self_vouchers ALTER COLUMN id SET DEFAULT nextval('public.self_vouchers_id_seq'::regclass);


--
-- Name: signature_log id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_log ALTER COLUMN id SET DEFAULT nextval('public.signature_log_id_seq'::regclass);


--
-- Name: transactions id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions ALTER COLUMN id SET DEFAULT nextval('public.transactions_id_seq'::regclass);


--
-- Name: voucher_documents id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voucher_documents ALTER COLUMN id SET DEFAULT nextval('public.voucher_documents_id_seq'::regclass);


--
-- Name: voucher_lines id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voucher_lines ALTER COLUMN id SET DEFAULT nextval('public.voucher_lines_id_seq'::regclass);


--
-- Name: voucher_links id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voucher_links ALTER COLUMN id SET DEFAULT nextval('public.voucher_links_id_seq'::regclass);


--
-- Name: vouchers id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vouchers ALTER COLUMN id SET DEFAULT nextval('public.vouchers_id_seq'::regclass);


--
-- Name: account_groups account_groups_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.account_groups
    ADD CONSTRAINT account_groups_pkey PRIMARY KEY (id);


--
-- Name: accounts accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (id);


--
-- Name: audit_log audit_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.audit_log
    ADD CONSTRAINT audit_log_pkey PRIMARY KEY (id);


--
-- Name: auto_rules auto_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.auto_rules
    ADD CONSTRAINT auto_rules_pkey PRIMARY KEY (id);


--
-- Name: booking_lines_new booking_lines_new_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_lines_new
    ADD CONSTRAINT booking_lines_new_pkey PRIMARY KEY (id);


--
-- Name: booking_lines_legacy booking_lines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_lines_legacy
    ADD CONSTRAINT booking_lines_pkey PRIMARY KEY (id);


--
-- Name: booking_rules booking_rules_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_rules
    ADD CONSTRAINT booking_rules_pkey PRIMARY KEY (id);


--
-- Name: depreciations depreciations_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.depreciations
    ADD CONSTRAINT depreciations_pkey PRIMARY KEY (id);


--
-- Name: outgoing_documents outgoing_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outgoing_documents
    ADD CONSTRAINT outgoing_documents_pkey PRIMARY KEY (id);


--
-- Name: outgoing_lines outgoing_lines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outgoing_lines
    ADD CONSTRAINT outgoing_lines_pkey PRIMARY KEY (id);


--
-- Name: outgoing_links outgoing_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outgoing_links
    ADD CONSTRAINT outgoing_links_pkey PRIMARY KEY (id);


--
-- Name: outgoing_vouchers outgoing_vouchers_invoice_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outgoing_vouchers
    ADD CONSTRAINT outgoing_vouchers_invoice_number_key UNIQUE (voucher_number);


--
-- Name: outgoing_vouchers outgoing_vouchers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outgoing_vouchers
    ADD CONSTRAINT outgoing_vouchers_pkey PRIMARY KEY (id);


--
-- Name: self_vouchers self_vouchers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.self_vouchers
    ADD CONSTRAINT self_vouchers_pkey PRIMARY KEY (id);


--
-- Name: self_vouchers self_vouchers_voucher_number_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.self_vouchers
    ADD CONSTRAINT self_vouchers_voucher_number_key UNIQUE (voucher_number);


--
-- Name: signature_log signature_log_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_log
    ADD CONSTRAINT signature_log_pkey PRIMARY KEY (id);


--
-- Name: skr03_accounts skr03_accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.skr03_accounts
    ADD CONSTRAINT skr03_accounts_pkey PRIMARY KEY (id);


--
-- Name: transactions transactions_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_pkey PRIMARY KEY (id);


--
-- Name: transactions transactions_tx_hash_key; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_tx_hash_key UNIQUE (tx_hash);


--
-- Name: voucher_documents voucher_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voucher_documents
    ADD CONSTRAINT voucher_documents_pkey PRIMARY KEY (id);


--
-- Name: voucher_lines voucher_lines_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voucher_lines
    ADD CONSTRAINT voucher_lines_pkey PRIMARY KEY (id);


--
-- Name: voucher_links voucher_links_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voucher_links
    ADD CONSTRAINT voucher_links_pkey PRIMARY KEY (id);


--
-- Name: vouchers vouchers_number_partner_unique; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vouchers
    ADD CONSTRAINT vouchers_number_partner_unique UNIQUE (voucher_number, partner_name);


--
-- Name: vouchers vouchers_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.vouchers
    ADD CONSTRAINT vouchers_pkey PRIMARY KEY (id);


--
-- Name: idx_booking_lines_tax_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_booking_lines_tax_type ON public.booking_lines_legacy USING btree (tax_type);


--
-- Name: idx_booking_lines_voucher_id; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_booking_lines_voucher_id ON public.booking_lines_legacy USING btree (voucher_id);


--
-- Name: idx_outgoing_customer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outgoing_customer ON public.outgoing_vouchers USING btree (partner_name);


--
-- Name: idx_outgoing_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outgoing_date ON public.outgoing_vouchers USING btree (voucher_date);


--
-- Name: idx_outgoing_docs_oid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outgoing_docs_oid ON public.outgoing_documents USING btree (outgoing_id);


--
-- Name: idx_outgoing_lines_account; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outgoing_lines_account ON public.outgoing_lines USING btree (account_skr);


--
-- Name: idx_outgoing_lines_oid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outgoing_lines_oid ON public.outgoing_lines USING btree (outgoing_id);


--
-- Name: idx_outgoing_links_oid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outgoing_links_oid ON public.outgoing_links USING btree (outgoing_id);


--
-- Name: idx_outgoing_links_txid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outgoing_links_txid ON public.outgoing_links USING btree (transaction_id);


--
-- Name: idx_outgoing_links_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outgoing_links_type ON public.outgoing_links USING btree (link_type);


--
-- Name: idx_outgoing_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outgoing_status ON public.outgoing_vouchers USING btree (status);


--
-- Name: idx_transactions_account; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transactions_account ON public.transactions USING btree (account_id);


--
-- Name: idx_transactions_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_transactions_date ON public.transactions USING btree (booking_date);


--
-- Name: idx_voucher_documents_vid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_voucher_documents_vid ON public.voucher_documents USING btree (voucher_id);


--
-- Name: idx_voucher_lines_account; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_voucher_lines_account ON public.voucher_lines USING btree (account_skr);


--
-- Name: idx_voucher_lines_vid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_voucher_lines_vid ON public.voucher_lines USING btree (voucher_id);


--
-- Name: idx_voucher_links_txid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_voucher_links_txid ON public.voucher_links USING btree (transaction_id);


--
-- Name: idx_voucher_links_type; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_voucher_links_type ON public.voucher_links USING btree (link_type);


--
-- Name: idx_voucher_links_vid; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_voucher_links_vid ON public.voucher_links USING btree (voucher_id);


--
-- Name: idx_vouchers_booking_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vouchers_booking_date ON public.vouchers USING btree (booking_date);


--
-- Name: idx_vouchers_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vouchers_date ON public.vouchers USING btree (voucher_date);


--
-- Name: idx_vouchers_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vouchers_status ON public.vouchers USING btree (status);


--
-- Name: unique_outgoing_voucher; Type: INDEX; Schema: public; Owner: -
--

CREATE UNIQUE INDEX unique_outgoing_voucher ON public.outgoing_vouchers USING btree (voucher_number, partner_name);


--
-- Name: booking_lines_legacy booking_lines; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_lines_legacy
    ADD CONSTRAINT booking_lines FOREIGN KEY (account_skr) REFERENCES public.skr03_accounts(id);


--
-- Name: booking_lines_legacy booking_lines_outgoing_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_lines_legacy
    ADD CONSTRAINT booking_lines_outgoing_id_fkey FOREIGN KEY (outgoing_id) REFERENCES public.outgoing_vouchers(id) ON DELETE CASCADE;


--
-- Name: booking_lines_legacy booking_lines_voucher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_lines_legacy
    ADD CONSTRAINT booking_lines_voucher_id_fkey FOREIGN KEY (voucher_id) REFERENCES public.vouchers(id) ON DELETE CASCADE;


--
-- Name: booking_rules booking_rules; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.booking_rules
    ADD CONSTRAINT booking_rules FOREIGN KEY (default_account) REFERENCES public.skr03_accounts(id);


--
-- Name: outgoing_documents outgoing_documents_outgoing_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outgoing_documents
    ADD CONSTRAINT outgoing_documents_outgoing_id_fkey FOREIGN KEY (outgoing_id) REFERENCES public.outgoing_vouchers(id) ON DELETE CASCADE;


--
-- Name: outgoing_lines outgoing_lines_outgoing_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outgoing_lines
    ADD CONSTRAINT outgoing_lines_outgoing_id_fkey FOREIGN KEY (outgoing_id) REFERENCES public.outgoing_vouchers(id) ON DELETE CASCADE;


--
-- Name: outgoing_links outgoing_links_outgoing_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outgoing_links
    ADD CONSTRAINT outgoing_links_outgoing_id_fkey FOREIGN KEY (outgoing_id) REFERENCES public.outgoing_vouchers(id) ON DELETE CASCADE;


--
-- Name: outgoing_links outgoing_links_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.outgoing_links
    ADD CONSTRAINT outgoing_links_transaction_id_fkey FOREIGN KEY (transaction_id) REFERENCES public.transactions(id) ON DELETE CASCADE;


--
-- Name: self_vouchers self_vouchers_reference_voucher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.self_vouchers
    ADD CONSTRAINT self_vouchers_reference_voucher_id_fkey FOREIGN KEY (reference_voucher_id) REFERENCES public.vouchers(id) ON DELETE SET NULL;


--
-- Name: signature_log signature_log_self_voucher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.signature_log
    ADD CONSTRAINT signature_log_self_voucher_id_fkey FOREIGN KEY (self_voucher_id) REFERENCES public.self_vouchers(id) ON DELETE CASCADE;


--
-- Name: transactions transactions_account_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.transactions
    ADD CONSTRAINT transactions_account_id_fkey FOREIGN KEY (account_id) REFERENCES public.accounts(id) ON DELETE CASCADE;


--
-- Name: voucher_documents voucher_documents_voucher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voucher_documents
    ADD CONSTRAINT voucher_documents_voucher_id_fkey FOREIGN KEY (voucher_id) REFERENCES public.vouchers(id) ON DELETE CASCADE;


--
-- Name: voucher_lines voucher_lines_voucher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voucher_lines
    ADD CONSTRAINT voucher_lines_voucher_id_fkey FOREIGN KEY (voucher_id) REFERENCES public.vouchers(id) ON DELETE CASCADE;


--
-- Name: voucher_links voucher_links_transaction_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voucher_links
    ADD CONSTRAINT voucher_links_transaction_id_fkey FOREIGN KEY (transaction_id) REFERENCES public.transactions(id) ON DELETE CASCADE;


--
-- Name: voucher_links voucher_links_voucher_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.voucher_links
    ADD CONSTRAINT voucher_links_voucher_id_fkey FOREIGN KEY (voucher_id) REFERENCES public.vouchers(id) ON DELETE CASCADE;


--
-- PostgreSQL database dump complete
--

\unrestrict anCxZ76HC28OuXRHSgulsS8DA9ECvux7UnJWWCJ9NJNIw6DspJJmzpK7SBhbiCT

