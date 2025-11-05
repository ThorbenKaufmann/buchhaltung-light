-- ============================================================================
-- normalize_booking_lines.sql
-- Vereinheitlicht bestehende Buchungen:
--  - ergänzt fehlenden tax_type anhand direction und tax_rate
--  - markiert fehlende receipt_status
--  - klassifiziert Sonderkonten (z.B. IG-Erwerb)
-- ============================================================================

-- 1️⃣ Eingangsbelege (Vorsteuer)
UPDATE booking_lines
   SET tax_type = CASE
       WHEN tax_rate = 19 THEN 'vst19'
       WHEN tax_rate = 7  THEN 'vst7'
       ELSE 'vst0'
   END
 WHERE direction = 'incoming'
   AND (tax_type IS NULL OR tax_type = '');

-- 2️⃣ Ausgangsrechnungen (Umsatzsteuer)
UPDATE booking_lines
   SET tax_type = CASE
       WHEN tax_rate = 19 THEN 'ust19'
       WHEN tax_rate = 7  THEN 'ust7'
       ELSE 'ust0'
   END
 WHERE direction = 'outgoing'
   AND (tax_type IS NULL OR tax_type = '');

-- 3️⃣ Sonderkonten
-- Konto 3425 = innergemeinschaftliche Lieferungen
UPDATE booking_lines
   SET tax_type = 'ig_erwerb'
 WHERE account_skr = '3425';

-- Reverse-Charge-Fälle anhand Text
UPDATE booking_lines
   SET tax_type = 'reverse_charge'
 WHERE (description ILIKE '%reverse%' OR description ILIKE '%§13b%')
   AND (tax_type IS NULL OR tax_type = '');

-- 4️⃣ Fehlende receipt_status nachtragen
UPDATE booking_lines
   SET receipt_status = 'complete'
 WHERE (receipt_status IS NULL OR receipt_status = '');

-- 5️⃣ Optional: Timestamp setzen, falls fehlt
UPDATE booking_lines
   SET created_at = NOW()
 WHERE created_at IS NULL;

-- Fertig.
