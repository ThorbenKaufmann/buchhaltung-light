
# Mapping: YAML → EN 16931 / XRechnung

Diese Tabelle beschreibt die Zuordnung der kanonischen BHL-YAML-Felder zu den
Business Terms (BT) der EN 16931 sowie deren Pflichtstatus.

## Dokumentkopf

| YAML-Pfad | EN16931 Feld | BT-ID | Pflicht | Bemerkung |
|---|---|---|---|---|
| invoice.number | Invoice number | BT-1 | M | Eindeutig |
| invoice.issue_date | Invoice issue date | BT-2 | M | ISO-Datum |
| invoice.invoice_type_code | Invoice type code | BT-3 | M | 380 = Rechnung |
| invoice.currency | Invoice currency | BT-5 | M | EUR |
| invoice.due_date | Payment due date | BT-9 | M | explizit |

## Verkäufer (Seller)

| YAML-Pfad | EN16931 Feld | BT-ID | Pflicht | Bemerkung |
|---|---|---|---|---|
| seller.name | Seller name | BT-27 | M | |
| seller.address.street | Seller address line | BT-35 | M | |
| seller.address.postcode | Seller postcode | BT-38 | M | |
| seller.address.city | Seller city | BT-37 | M | |
| seller.address.country_code | Seller country | BT-40 | M | ISO-3166 |
| seller.tax.vat_id | Seller VAT ID | BT-31 | C | optional |
| seller.tax.tax_id | Seller tax registration | BT-32 | C | |
| seller.electronic_address.value | Seller e-address | BT-34 | M | E-Mail ok |

## Käufer (Buyer)

| YAML-Pfad | EN16931 Feld | BT-ID | Pflicht | Bemerkung |
|---|---|---|---|---|
| buyer.name | Buyer name | BT-44 | M | |
| buyer.address.street | Buyer address line | BT-50 | M | |
| buyer.address.postcode | Buyer postcode | BT-53 | M | |
| buyer.address.city | Buyer city | BT-52 | M | |
| buyer.address.country_code | Buyer country | BT-55 | M | |
| buyer.electronic_address.value | Buyer e-address | BT-49 | M | |

## Rechnungspositionen (Lines)

| YAML-Pfad | EN16931 Feld | BT-ID | Pflicht | Bemerkung |
|---|---|---|---|---|
| lines[].line_id | Line ID | BT-126 | M | |
| lines[].description | Item name | BT-153 | M | |
| lines[].quantity | Invoiced quantity | BT-129 | M | |
| lines[].unit_code | Unit of measure | BT-130 | M | UNECE |
| lines[].unit_price | Net price | BT-146 | M | |
| lines[].net_amount | Line net amount | BT-131 | M | |
| lines[].tax.category_code | VAT category | BT-151 | M | |
| lines[].tax.rate | VAT rate | BT-152 | M | |
| lines[].tax.exemption_reason | VAT exemption text | BT-120 | C | empfohlen |

## Steuerzusammenfassung

| YAML-Pfad | EN16931 Feld | BT-ID | Pflicht |
|---|---|---|---|
| tax_summary[].taxable_amount | Taxable amount | BT-116 | M |
| tax_summary[].tax_amount | VAT amount | BT-117 | M |
| tax_summary[].rate | VAT rate | BT-119 | M |

## Summen

| YAML-Pfad | EN16931 Feld | BT-ID | Pflicht |
|---|---|---|---|
| totals.line_net_total | Sum of line net amounts | BT-106 | M |
| totals.tax_exclusive_amount | Invoice total excl. VAT | BT-109 | M |
| totals.tax_inclusive_amount | Invoice total incl. VAT | BT-112 | M |
| totals.payable_amount | Amount due | BT-115 | M |

## Zahlungsbedingungen

| YAML-Pfad | EN16931 Feld | BT-ID | Pflicht |
|---|---|---|---|
| payment_terms.description | Payment terms | BT-20 | C |
| payment_terms.due_date | Due date | BT-9 | M |
