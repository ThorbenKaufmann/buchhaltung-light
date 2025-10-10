-- Alten eindeutigen Index auf voucher_number entfernen
ALTER TABLE vouchers DROP CONSTRAINT IF EXISTS vouchers_voucher_number_key;

-- Neuen kombinierten Unique Index anlegen
ALTER TABLE vouchers
    ADD CONSTRAINT vouchers_number_partner_unique
    UNIQUE (voucher_number, partner_name);
