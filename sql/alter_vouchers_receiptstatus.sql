ALTER TABLE vouchers
    ADD COLUMN receipt_status TEXT DEFAULT 'complete' CHECK (
        receipt_status IN ('complete', 'pending', 'missing', 'incomplete')
    );

ALTER TABLE outgoing_vouchers
    ADD COLUMN receipt_status TEXT DEFAULT 'complete' CHECK (
        receipt_status IN ('complete', 'pending', 'missing', 'incomplete')
    );

ALTER TABLE booking_lines
    ADD COLUMN receipt_status TEXT DEFAULT 'complete' CHECK (
        receipt_status IN ('complete', 'pending', 'missing', 'incomplete')
    );


ALTER TABLE vouchers ALTER COLUMN receipt_status SET DEFAULT 'complete';
ALTER TABLE outgoing_vouchers ALTER COLUMN receipt_status SET DEFAULT 'complete';
ALTER TABLE booking_lines ALTER COLUMN receipt_status SET DEFAULT 'complete';

UPDATE vouchers SET receipt_status = 'complete' WHERE receipt_status IS NULL;
UPDATE outgoing_vouchers SET receipt_status = 'complete' WHERE receipt_status IS NULL;
UPDATE booking_lines SET receipt_status = 'complete' WHERE receipt_status IS NULL;
