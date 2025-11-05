CREATE TABLE IF NOT EXISTS audit_log (
    id SERIAL PRIMARY KEY,
    entity TEXT NOT NULL,
    entity_id INTEGER NOT NULL,
    action TEXT NOT NULL,
    field TEXT,
    old_value TEXT,
    new_value TEXT,
    reason TEXT,
    changed_at TIMESTAMP DEFAULT NOW()
);
