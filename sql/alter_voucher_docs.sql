ALTER TABLE voucher_documents
ADD COLUMN embedded_xml TEXT,
ADD COLUMN xml_type TEXT CHECK (xml_type IN ('zugferd','xrechnung','factur-x')),
ADD COLUMN xml_valid BOOLEAN DEFAULT NULL;
