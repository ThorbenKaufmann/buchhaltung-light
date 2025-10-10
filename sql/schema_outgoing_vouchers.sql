--
-- BHL – Buchhaltung-Light: Ausgangsrechnungen
-- Version 2025-10-08
-- Ergänzt die Eingangsbelegstruktur um Ausgangsrechnungen.
--

-- =========================================================
-- 1. Haupttabelle: outgoing_vouchers (Ausgangsrechnungen)
-- =========================================================
CREATE TABLE IF NOT EXISTS outgoing_vouchers (
    id SERIAL PRIMARY KEY,
    invoice_number TEXT UNIQUE,                  -- z. B. RE-2025-001
    invoice_date DATE NOT NULL,                  -- Rechnungsdatum
    booking_date DATE,                           -- Zeitpunkt der Verbuchung
    customer_name TEXT NOT NULL,                 -- Debitor / Kunde
    description TEXT,                            -- Kurzbeschreibung
    total_amount NUMERIC(12,2),                  -- Gesamtbetrag (brutto)
    currency CHAR(3) DEFAULT 'EUR',
    document_type TEXT CHECK (document_type IN ('invoice','credit_note','self_issued')),
    status TEXT CHECK (status IN ('draft','sent','paid','archived')) DEFAULT 'draft',
    source TEXT,                                 -- z. B. 'OrgaMax', 'manual'
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outgoing_date ON outgoing_vouchers(invoice_date);
CREATE INDEX IF NOT EXISTS idx_outgoing_status ON outgoing_vouchers(status);
CREATE INDEX IF NOT EXISTS idx_outgoing_customer ON outgoing_vouchers(customer_name);

-- =========================================================
-- 2. Dokumente zu Ausgangsrechnungen
-- =========================================================
CREATE TABLE IF NOT EXISTS outgoing_documents (
    id SERIAL PRIMARY KEY,
    outgoing_id INT NOT NULL REFERENCES outgoing_vouchers(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,
    mime_type TEXT,
    file_hash CHAR(64),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outgoing_docs_oid ON outgoing_documents(outgoing_id);

-- =========================================================
-- 3. Einzelpositionen (SKR-Kontierung)
-- =========================================================
CREATE TABLE IF NOT EXISTS outgoing_lines (
    id SERIAL PRIMARY KEY,
    outgoing_id INT NOT NULL REFERENCES outgoing_vouchers(id) ON DELETE CASCADE,
    account_skr TEXT NOT NULL,                   -- z. B. '8400' Erlöse 19 %
    description TEXT,
    net_amount NUMERIC(12,2),
    tax_rate NUMERIC(5,2),
    tax_amount NUMERIC(12,2),
    cost_center TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outgoing_lines_oid ON outgoing_lines(outgoing_id);
CREATE INDEX IF NOT EXISTS idx_outgoing_lines_account ON outgoing_lines(account_skr);

-- =========================================================
-- 4. Verknüpfung zu Banktransaktionen (Zahlungseingänge)
-- =========================================================
CREATE TABLE IF NOT EXISTS outgoing_links (
    id SERIAL PRIMARY KEY,
    outgoing_id INT NOT NULL REFERENCES outgoing_vouchers(id) ON DELETE CASCADE,
    transaction_id INT NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    link_type TEXT CHECK (link_type IN ('payment','refund','split','open')),
    amount NUMERIC(12,2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_outgoing_links_oid ON outgoing_links(outgoing_id);
CREATE INDEX IF NOT EXISTS idx_outgoing_links_txid ON outgoing_links(transaction_id);
CREATE INDEX IF NOT EXISTS idx_outgoing_links_type ON outgoing_links(link_type);

-- =========================================================
-- Ende des Schemas
-- =========================================================
