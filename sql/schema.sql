CREATE TABLE accounts (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    iban TEXT,
    bic TEXT,
    type TEXT CHECK (type IN ('bank', 'credit', 'paypal', 'cash', 'savings')),
    currency CHAR(3) DEFAULT 'EUR',
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE transactions (
    id SERIAL PRIMARY KEY,
    account_id INT NOT NULL REFERENCES accounts(id) ON DELETE CASCADE,
    booking_date DATE NOT NULL,
    value_date DATE,
    amount NUMERIC(12,2) NOT NULL,
    currency CHAR(3) DEFAULT 'EUR',
    counterpart_name TEXT,
    counterpart_iban TEXT,
    purpose TEXT,
    category TEXT,
    import_source TEXT,
    raw_data JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_transactions_date ON transactions(booking_date);
CREATE INDEX idx_transactions_account ON transactions(account_id);

