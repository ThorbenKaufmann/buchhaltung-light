# Database Schema Overview

## accounts

| Column | Type |
|---------|------|
| id | integer |
| name | text |
| iban | text |
| bic | text |
| type | text |
| currency | character(3) |
| is_active | boolean |
| created_at | timestamp |

## audit_log

| Column | Type |
|---------|------|
| id | integer |
| entity | text |
| entity_id | integer |
| action | text |
| field | text |
| old_value | text |
| new_value | text |
| reason | text |
| changed_at | timestamp |

## booking_lines

| Column | Type |
|---------|------|
| id | integer |
| direction | text |
| voucher_id | integer |
| outgoing_id | integer |
| account_skr | text |
| description | text |
| net_amount | numeric(12,2) |
| tax_rate | numeric(5,2) |
| tax_amount | numeric(12,2) |
| gross_amount | numeric(12,2) |
| created_at | timestamp |
| receipt_status | text |
| tax_type | text |

## booking_rules

| Column | Type |
|---------|------|
| id | integer |
| pattern | text |
| default_account | text |
| default_tax | numeric(5,2) |
| direction | text |
| note | text |
| tax_type | text |
| is_internal | boolean |
| is_private | boolean |
| is_cyclic | boolean |

## outgoing_documents

| Column | Type |
|---------|------|
| id | integer |
| outgoing_id | integer |
| file_name | text |
| file_path | text |
| mime_type | text |
| file_hash | character(64) |
| created_at | timestamp |

## outgoing_lines

| Column | Type |
|---------|------|
| id | integer |
| outgoing_id | integer |
| account_skr | text |
| description | text |
| net_amount | numeric(12,2) |
| tax_rate | numeric(5,2) |
| tax_amount | numeric(12,2) |
| cost_center | text |
| created_at | timestamp |

## outgoing_links

| Column | Type |
|---------|------|
| id | integer |
| outgoing_id | integer |
| transaction_id | integer |
| link_type | text |
| amount | numeric(12,2) |
| created_at | timestamp |

## outgoing_vouchers

| Column | Type |
|---------|------|
| id | integer |
| voucher_number | text |
| invoice_date | date |
| booking_date | date |
| customer_name | text |
| description | text |
| total_amount | numeric(12,2) |
| currency | character(3) |
| document_type | text |
| status | text |
| source | text |
| created_at | timestamp |
| payment_due_date | date |
| receipt_status | text |

## self_vouchers

| Column | Type |
|---------|------|
| id | integer |
| voucher_number | text |
| created_at | timestamp |
| voucher_date | date |
| reason | text |
| partner_name | text |
| amount | numeric(12,2) |
| currency | character(3) |
| reference_voucher_id | integer |
| sha256_hash | character(64) |
| signed | boolean |
| file_path | text |
| remarks | text |

## signature_log

| Column | Type |
|---------|------|
| id | integer |
| self_voucher_id | integer |
| signed_at | timestamp |
| signer | text |
| signature_method | text |
| signature_hash | character(64) |

## skr03_accounts

| Column | Type |
|---------|------|
| id | text |
| name | text |
| default_tax | numeric(5,2) |
| category | text |
| ust_code | text |
| is_expense | boolean |
| is_revenue | boolean |
| is_active | boolean |
| remark | text |
| is_internal | boolean |

## transactions

| Column | Type |
|---------|------|
| id | integer |
| account_id | integer |
| booking_date | date |
| value_date | date |
| amount | numeric(12,2) |
| currency | character(3) |
| counterpart_name | text |
| counterpart_iban | text |
| purpose | text |
| category | text |
| import_source | text |
| raw_data | jsonb |
| created_at | timestamp |
| tx_hash | character(64) |
| is_private | boolean |
| is_internal | boolean |
| is_cyclic | boolean |

## voucher_documents

| Column | Type |
|---------|------|
| id | integer |
| voucher_id | integer |
| file_name | text |
| file_path | text |
| mime_type | text |
| file_hash | character(64) |
| created_at | timestamp |
| embedded_xml | text |
| xml_type | text |
| xml_valid | boolean |

## voucher_lines

| Column | Type |
|---------|------|
| id | integer |
| voucher_id | integer |
| account_skr | text |
| description | text |
| net_amount | numeric(12,2) |
| tax_rate | numeric(5,2) |
| tax_amount | numeric(12,2) |
| cost_center | text |
| created_at | timestamp |

## voucher_links

| Column | Type |
|---------|------|
| id | integer |
| voucher_id | integer |
| transaction_id | integer |
| link_type | text |
| amount | numeric(12,2) |
| created_at | timestamp |

## vouchers

| Column | Type |
|---------|------|
| id | integer |
| voucher_number | text |
| voucher_date | date |
| booking_date | date |
| partner_name | text |
| description | text |
| total_amount | numeric(12,2) |
| currency | character(3) |
| document_type | text |
| source | text |
| status | text |
| created_at | timestamp |
| payment_due_date | date |
| receipt_status | text |


# Potentially Redundant Columns

- `account_skr`
- `amount`
- `booking_date`
- `category`
- `cost_center`
- `created_at`
- `currency`
- `default_tax`
- `description`
- `direction`
- `document_type`
- `file_hash`
- `file_name`
- `file_path`
- `id`
- `is_active`
- `is_cyclic`
- `is_internal`
- `is_private`
- `link_type`
- `mime_type`
- `name`
- `net_amount`
- `outgoing_id`
- `partner_name`
- `payment_due_date`
- `reason`
- `receipt_status`
- `source`
- `status`
- `tax_amount`
- `tax_rate`
- `tax_type`
- `total_amount`
- `transaction_id`
- `voucher_date`
- `voucher_id`
- `voucher_number`