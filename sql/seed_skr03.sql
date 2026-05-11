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
-- Data for Name: account_groups; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.account_groups (id, skr_min, skr_max, gruppe, beschreibung, created_at) VALUES (1, '0000', '0999', 'Aktiva – Anlagevermögen', 'Langfristige Vermögenswerte', '2025-11-12 13:56:14.306583');
INSERT INTO public.account_groups (id, skr_min, skr_max, gruppe, beschreibung, created_at) VALUES (2, '1000', '1999', 'Aktiva – Umlaufvermögen', 'Kurzfristige Vermögenswerte', '2025-11-12 13:56:14.306583');
INSERT INTO public.account_groups (id, skr_min, skr_max, gruppe, beschreibung, created_at) VALUES (3, '2000', '2999', 'Passiva – Eigenkapital', 'Eigenkapital', '2025-11-12 13:56:14.306583');
INSERT INTO public.account_groups (id, skr_min, skr_max, gruppe, beschreibung, created_at) VALUES (4, '3000', '6999', 'Aufwand (GuV – Soll)', 'Betriebliche Aufwendungen', '2025-11-12 13:56:14.306583');
INSERT INTO public.account_groups (id, skr_min, skr_max, gruppe, beschreibung, created_at) VALUES (5, '7000', '7999', 'Finanzergebnis', 'Finanzergebnis und Zinsen', '2025-11-12 13:56:14.306583');
INSERT INTO public.account_groups (id, skr_min, skr_max, gruppe, beschreibung, created_at) VALUES (6, '8000', '8999', 'Ertrag (GuV – Haben)', 'Betriebliche Erträge', '2025-11-12 13:56:14.306583');
INSERT INTO public.account_groups (id, skr_min, skr_max, gruppe, beschreibung, created_at) VALUES (7, '9000', '9999', 'Abschluss- / Steuerkonten', 'Steuerliche Abschlusskonten', '2025-11-12 13:56:14.306583');


--
-- Data for Name: skr03_accounts; Type: TABLE DATA; Schema: public; Owner: -
--

INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4910', 'Porto (steuerfrei)', 0.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4905', 'Internetkosten', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4920', 'Telefonkosten', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4930', 'Büromaterial', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4940', 'Fachliteratur', 7.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4980', 'Büromaterial / Werkzeuge', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('0480', 'Büro- und Geschäftsausstattung (AFA)', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('0670', 'Computer-Hardware (AFA)', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('0030', 'Software-Kauf (immaterielle Wirtschaftsgüter) (AFA)', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4906', 'EDV Dienstleistungen', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4909', 'HW-/SW-Miete / Cloud-/SaaS-Gebühren', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4975', 'Beiträge an Kammern, Verbände, Vereinigungen', 0.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4520', 'Kfz-Miete, Leasing (ohneSonderzahlung)', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4855', 'Laufende Reparatur / Instandhaltung', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4806', 'Geringwertige Wirtschaftsgüter (GWG)', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4954', 'Steuerberatung', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('3400', 'Wareneingang', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4900', 'Betriebsbedarf / Entwicklungsaufwand', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4800', 'Arbeitskleidung / Schutzkleidung', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4970', 'Beiträge, Gebühren, Abonnements', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('6300', 'Strom, Licht, Energie', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4570', 'KFZ Kosten', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('3425', 'Innerg. Erwerb Dienstleistung 19% nach Art.138 Richtlinie 2006/112/EC', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('3125', 'Innergemeinschaftlicher Erwerb von Waren (Reverse-Charge)', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('1576', 'Vorsteuer 19%', 19.00, 'Steuer', NULL, false, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('1776', 'Umsatzsteuer 19%', 19.00, 'Steuer', NULL, false, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('6855', 'Nebenkosten des Geldverkehrs', 0.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4210', 'Miete für Geschäftsräume', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('1360', 'Geldtransit', 0.00, 'Intern', NULL, false, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('1780', 'Umsatzsteuerzahlung', 0.00, 'Steuer', NULL, false, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('2331', 'Vorauszahlungen Gewerbesteuer', 0.00, 'Steuer', NULL, false, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('2330', 'Gewerbesteuer', 0.00, 'Steuer', NULL, false, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('2332', 'Rückstellung Gewerbesteuer', 0.00, 'Steuer', NULL, false, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('8300', 'Erlöse 7 % USt', 7.00, 'Erlös', NULL, false, true, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('8400', 'Erlöse 19 % USt', 19.00, 'Erlös', NULL, false, true, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('1800', 'Privatentnahme', 0.00, 'Privat', NULL, false, false, false, NULL, true);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('1890', 'Privateinlage', 0.00, 'Privat', NULL, false, false, false, NULL, true);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4950', 'Versicherungen, Beiträge', 19.00, 'Aufwand', NULL, true, false, false, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('6600', 'Werbekosten allgemein', 19.00, 'Aufwand', NULL, true, false, false, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4600', 'Entwicklungsaufwand allgemein', 19.00, 'Aufwand', NULL, true, false, true, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4670', 'Reisekosten Kilometerpauschale (0.30€/km)', 0.00, 'Aufwand', NULL, true, false, false, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4660', 'Reisekosten Maut/Brücken/Fähren/Parken VSt 0', 0.00, 'Aufwand', NULL, true, false, false, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('4605', 'Maritime Entwicklung', 19.00, 'Aufwand', NULL, true, false, false, NULL, false);
INSERT INTO public.skr03_accounts (id, name, default_tax, category, ust_code, is_expense, is_revenue, is_active, remark, is_internal) VALUES ('7310', 'Zinsen und ähnliche Aufwendungen', 0.00, NULL, NULL, true, false, true, NULL, false);


--
-- Name: account_groups_id_seq; Type: SEQUENCE SET; Schema: public; Owner: -
--

SELECT pg_catalog.setval('public.account_groups_id_seq', 7, true);


--
-- PostgreSQL database dump complete
--

\unrestrict AfOba3dwbDUPsHRxD6TRGLoM1YPHCFVf7xls3BbOFkFKnQD54YJf2hY7lWyLM3C

