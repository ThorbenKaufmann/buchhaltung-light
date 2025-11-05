-- Tabelle für revisionssichere Eigenbelege
CREATE TABLE IF NOT EXISTS self_vouchers (
    id SERIAL PRIMARY KEY,
    voucher_number TEXT UNIQUE NOT NULL,              -- EB-2024-001 …
    created_at TIMESTAMP DEFAULT now(),
    voucher_date DATE NOT NULL,
    reason TEXT NOT NULL,
    partner_name TEXT,
    amount NUMERIC(12,2) NOT NULL,
    currency CHAR(3) DEFAULT 'EUR',
    reference_voucher_id INTEGER REFERENCES vouchers(id) ON DELETE SET NULL,
    sha256_hash CHAR(64),
    signed BOOLEAN DEFAULT FALSE,
    file_path TEXT,
    remarks TEXT
);

-- optionale Signaturhistorie (für spätere Erweiterungen)
CREATE TABLE IF NOT EXISTS signature_log (
    id SERIAL PRIMARY KEY,
    self_voucher_id INTEGER REFERENCES self_vouchers(id) ON DELETE CASCADE,
    signed_at TIMESTAMP DEFAULT now(),
    signer TEXT,
    signature_method TEXT,
    signature_hash CHAR(64)
);
