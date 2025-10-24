-- --------------------------------------------------------------------
-- SKR03-Kontenstammdaten
-- --------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS skr03_accounts (
    id TEXT PRIMARY KEY,                     -- Konto-Nr. (z.B. '4905')
    name TEXT NOT NULL,                      -- Bezeichnung
    default_tax NUMERIC(5,2),                -- typischer USt.-Satz
    category TEXT,                           -- 'Aufwand', 'Erlös', 'Privat', ...
    ust_code TEXT,                           -- Kennziffer für UStVA (optional)
    is_expense BOOLEAN DEFAULT FALSE,
    is_revenue BOOLEAN DEFAULT FALSE,
    is_active  BOOLEAN DEFAULT TRUE,
    remark TEXT
);

-- Beispielkonten ------------------------------------------------------
INSERT INTO skr03_accounts (id, name, default_tax, category, is_expense) VALUES
('4910', 'Porto (steuerfrei)', 0, 'Aufwand', TRUE),
('4905', 'Internetkosten', 19, 'Aufwand', TRUE),
('4920', 'Telefonkosten', 19, 'Aufwand', TRUE),
('4930', 'Büromaterial', 19, 'Aufwand', TRUE),
('4940', 'Fachliteratur', 7,  'Aufwand', TRUE),
('8400', 'Erlöse 19 % USt', 19, 'Erlös', FALSE),
('8300', 'Erlöse 7 % USt', 7,  'Erlös', FALSE);
