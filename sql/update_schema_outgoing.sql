-- ------------------------------------------------------------
-- update_schema_outgoing.sql
-- Vereinheitlicht outgoing_vouchers mit vouchers (ZUGFeRD-kompatibel)
-- ------------------------------------------------------------

BEGIN;

-- 1. Spalten umbenennen (nur falls sie existieren)
DO $$
BEGIN
    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'outgoing_vouchers' AND column_name = 'invoice_number'
    ) THEN
        ALTER TABLE outgoing_vouchers RENAME COLUMN invoice_number TO voucher_number;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'outgoing_vouchers' AND column_name = 'invoice_date'
    ) THEN
        ALTER TABLE outgoing_vouchers RENAME COLUMN invoice_date TO voucher_date;
    END IF;

    IF EXISTS (
        SELECT 1 FROM information_schema.columns 
        WHERE table_name = 'outgoing_vouchers' AND column_name = 'customer_name'
    ) THEN
        ALTER TABLE outgoing_vouchers RENAME COLUMN customer_name TO partner_name;
    END IF;
END $$;

-- 2. Spalte receipt_status ergänzen (falls nicht vorhanden)
ALTER TABLE outgoing_vouchers
ADD COLUMN IF NOT EXISTS receipt_status TEXT DEFAULT 'complete';

-- 3. Zeitstempel ergänzen (optional, falls nicht vorhanden)
ALTER TABLE outgoing_vouchers
ADD COLUMN IF NOT EXISTS created_at TIMESTAMP DEFAULT NOW();

-- 4. Index für Duplikatschutz (Rechnungsnummer + Partner)
CREATE UNIQUE INDEX IF NOT EXISTS unique_outgoing_voucher
    ON outgoing_vouchers (voucher_number, partner_name);

COMMIT;
