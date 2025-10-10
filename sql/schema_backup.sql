--
-- PostgreSQL database dump
--

\restrict 1IKxIgtdgWDDowKpBMkwnFmeFUVOnJgosDq6SDbR1NEPRvmB6bKWgSkX2uPhS31

-- Dumped from database version 14.19 (Ubuntu 14.19-0ubuntu0.22.04.1)
-- Dumped by pg_dump version 16.10 (Ubuntu 16.10-0ubuntu0.24.04.1)

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
    invoice_date date NOT NULL,
    booking_date date,
    customer_name text NOT NULL,
    description text,
    total_amount numeric(12,2),
    currency character(3) DEFAULT 'EUR'::bpchar,
    document_type text,
    status text DEFAULT 'draft'::text,
    source text,
    created_at timestamp without time zone DEFAULT now(),
    payment_due_date date,
    CONSTRAINT outgoing_vouchers_document_type_check CHECK ((document_type = ANY (ARRAY['invoice'::text, 'credit_note'::text, 'self_issued'::text]))),
    CONSTRAINT outgoing_vouchers_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'sent'::text, 'paid'::text, 'archived'::text])))
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
    tx_hash character(64)
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
    CONSTRAINT vouchers_document_type_check CHECK ((document_type = ANY (ARRAY['invoice'::text, 'receipt'::text, 'contract'::text, 'self_issued'::text, 'other'::text]))),
    CONSTRAINT vouchers_status_check CHECK ((status = ANY (ARRAY['draft'::text, 'booked'::text, 'archived'::text, 'paid'::text])))
);


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
-- Name: accounts id; Type: DEFAULT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts ALTER COLUMN id SET DEFAULT nextval('public.accounts_id_seq'::regclass);


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
-- Name: accounts accounts_pkey; Type: CONSTRAINT; Schema: public; Owner: -
--

ALTER TABLE ONLY public.accounts
    ADD CONSTRAINT accounts_pkey PRIMARY KEY (id);


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
-- Name: idx_outgoing_customer; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outgoing_customer ON public.outgoing_vouchers USING btree (customer_name);


--
-- Name: idx_outgoing_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_outgoing_date ON public.outgoing_vouchers USING btree (invoice_date);


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
-- Name: idx_vouchers_date; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vouchers_date ON public.vouchers USING btree (voucher_date);


--
-- Name: idx_vouchers_status; Type: INDEX; Schema: public; Owner: -
--

CREATE INDEX idx_vouchers_status ON public.vouchers USING btree (status);


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

\unrestrict 1IKxIgtdgWDDowKpBMkwnFmeFUVOnJgosDq6SDbR1NEPRvmB6bKWgSkX2uPhS31

