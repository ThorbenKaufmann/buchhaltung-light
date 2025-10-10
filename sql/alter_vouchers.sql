-- Alten eindeutigen Index auf voucher_number entfernen
ALTER TABLE vouchers DROP CONSTRAINT IF EXISTS vouchers_voucher_number_key;

-- Neuen kombinierten Unique Index anlegen
ALTER TABLE vouchers
    ADD CONSTRAINT vouchers_number_partner_unique
    UNIQUE (voucher_number, partner_name);

ALTER TABLE vouchers
    DROP CONSTRAINT IF EXISTS vouchers_status_check;

ALTER TABLE vouchers
    ADD CONSTRAINT vouchers_status_check
    CHECK (status IN ('draft','booked','archived','paid'));

-- Für Eingangsrechnungen
ALTER TABLE vouchers
    ADD COLUMN IF NOT EXISTS payment_due_date DATE;

-- Für Ausgangsrechnungen
ALTER TABLE outgoing_vouchers
    ADD COLUMN IF NOT EXISTS payment_due_date DATE;

ALTER TABLE outgoing_vouchers
    RENAME COLUMN invoice_number TO voucher_number;


