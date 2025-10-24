-- Einzelne Buchungspositionen (Kontierung je Position)
CREATE TABLE IF NOT EXISTS booking_lines (
    id SERIAL PRIMARY KEY,
    direction TEXT CHECK (direction IN ('incoming','outgoing')) NOT NULL,
    voucher_id INT REFERENCES vouchers(id) ON DELETE CASCADE,
    outgoing_id INT REFERENCES outgoing_vouchers(id) ON DELETE CASCADE,
    account_skr TEXT NOT NULL,               -- z. B. '4905' Internetkosten
    description TEXT,
    net_amount NUMERIC(12,2),
    tax_rate NUMERIC(5,2),                   -- 0, 7, 19
    tax_amount NUMERIC(12,2),
    gross_amount NUMERIC(12,2),
    created_at TIMESTAMP DEFAULT NOW()
);

-- Regelbasis für automatische Vorschläge
CREATE TABLE IF NOT EXISTS booking_rules (
    id SERIAL PRIMARY KEY,
    pattern TEXT NOT NULL,                   -- Suchbegriff in Belegname/Zweck
    default_account TEXT NOT NULL,           -- SKR03/04 Konto
    default_tax NUMERIC(5,2) DEFAULT 19,     -- Standard-Steuersatz
    direction TEXT CHECK (direction IN ('incoming','outgoing')) DEFAULT 'incoming',
    note TEXT
);

-- Beispielregeln
INSERT INTO booking_rules (pattern, default_account, default_tax, direction, note) VALUES
('STRATO', '4905', 19, 'incoming', 'Internetkosten'),
('Telefónica', '4920', 19, 'incoming', 'Telefonie'),
('Deutsche Post', '4910', 19, 'incoming', 'Porto'),
('Amazon', '4980', 19, 'incoming', 'Büromaterial'),
('Hitex GmbH', '8400', 19, 'outgoing', 'Erlöse 19%');
