-- =====================================================================
--  Tabelle: auto_rules
--  Zweck:   Automatische Kontierung von Belegen anhand Partnername-Muster
-- =====================================================================

DROP TABLE IF EXISTS auto_rules CASCADE;

CREATE TABLE auto_rules (
    id SERIAL PRIMARY KEY,
    match_pattern TEXT NOT NULL,          -- Suchmuster im partner_name
    direction TEXT CHECK (direction IN ('incoming','outgoing')) NOT NULL,
    account_skr TEXT NOT NULL,            -- Zielkonto (z.B. 4920)
    tax_rate NUMERIC(5,2) DEFAULT 19,
    tax_type TEXT DEFAULT 'ust',
    description TEXT,                     -- Freitext, z.B. "Telefonie"
    created_at TIMESTAMP DEFAULT NOW()
);

COMMENT ON TABLE auto_rules IS
'Regeln für automatische Kontierung eingehender/ausgehender Belege anhand von Lieferantenmustern.';
