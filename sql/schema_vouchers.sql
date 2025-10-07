--
-- BHL – Buchhaltung-Light: Belegsystem
-- Version 2025-10-07
-- Dieses Schema ergänzt das Basisschema (accounts, transactions).
--

-- =========================================================
-- 1. Haupttabelle: vouchers (Belege)
-- =========================================================
CREATE TABLE IF NOT EXISTS vouchers (
    id SERIAL PRIMARY KEY,
    voucher_number TEXT UNIQUE,         -- z. B. RE-2025-001 oder EIGEN-2025-03
    voucher_date DATE NOT NULL,         -- Rechnungs- oder Belegdatum
    booking_date DATE,                  -- tatsächliche Buchung (optional)
    partner_name TEXT,                  -- Lieferant / Kunde / Empfänger
    description TEXT,                   -- Kurzbeschreibung (z. B. "Server März 2025")
    total_amount NUMERIC(12,2),         -- Gesamtbetrag (brutto)
    currency CHAR(3) DEFAULT 'EUR',
    document_type TEXT CHECK (document_type IN
        ('invoice','receipt','contract','self_issued','other')),
    source TEXT,                        -- z. B. 'GetMyInvoices', 'Scan', 'Manuell'
    status TEXT CHECK (status IN ('draft','booked','archived')) DEFAULT 'draft',
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_vouchers_date ON vouchers(voucher_date);
CREATE INDEX IF NOT EXISTS idx_vouchers_status ON vouchers(status);

-- =========================================================
-- 2. Dokumente zu Belegen
-- =========================================================
CREATE TABLE IF NOT EXISTS voucher_documents (
    id SERIAL PRIMARY KEY,
    voucher_id INT NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
    file_name TEXT NOT NULL,
    file_path TEXT NOT NULL,            -- relativer oder absoluter Pfad
    mime_type TEXT,
    file_hash CHAR(64),                 -- SHA256 für Revisionssicherheit
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_voucher_documents_vid ON voucher_documents(voucher_id);

-- =========================================================
-- 3. Einzelpositionen eines Belegs (SKR-Zuordnung)
-- =========================================================
CREATE TABLE IF NOT EXISTS voucher_lines (
    id SERIAL PRIMARY KEY,
    voucher_id INT NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
    account_skr TEXT NOT NULL,          -- z. B. '3125'
    description TEXT,
    net_amount NUMERIC(12,2),
    tax_rate NUMERIC(5,2),
    tax_amount NUMERIC(12,2),
    cost_center TEXT,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_voucher_lines_vid ON voucher_lines(voucher_id);
CREATE INDEX IF NOT EXISTS idx_voucher_lines_account ON voucher_lines(account_skr);

-- =========================================================
-- 4. Verknüpfung Beleg ↔ Bankbuchung
-- =========================================================
CREATE TABLE IF NOT EXISTS voucher_links (
    id SERIAL PRIMARY KEY,
    voucher_id INT NOT NULL REFERENCES vouchers(id) ON DELETE CASCADE,
    transaction_id INT NOT NULL REFERENCES transactions(id) ON DELETE CASCADE,
    link_type TEXT CHECK (link_type IN ('payment','refund','split','open')),
    amount NUMERIC(12,2),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_voucher_links_vid ON voucher_links(voucher_id);
CREATE INDEX IF NOT EXISTS idx_voucher_links_txid ON voucher_links(transaction_id);
CREATE INDEX IF NOT EXISTS idx_voucher_links_type ON voucher_links(link_type);

-- =========================================================
-- Ende des Schemas
-- =========================================================
