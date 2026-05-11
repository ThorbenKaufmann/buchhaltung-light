
## Belege für Monat aus Backlog einlesen:

```bash
./python/add_all_vouchers.py --direction incoming ./backlog/2024/01/ ./belege/
```

```bash
    python add_all_vouchers.py ./backlog/in ./belege --direction incoming
    python add_all_vouchers.py ./backlog/out ./belege/ausgang --direction outgoing
    python add_all_vouchers.py ./backlog/mixed ./belege --direction auto
```

./add_voucher.py
./add_outgoing-voucher.py

## Banktransaktionen einlesen/importieren

!!! todo: Konten/Account-IDs auslesen und anzeigen !!!

```bash
./import_mt940.py
```

```bash
./batch_import_mt940.py
```

## Belege vs. Banktransaktionen matchen

```bash
./match_vouchers.py --direction incoming --month 2024-01
```

## Auto Assign Vouchers

```bash
./manage_auto_rules.py --add --pattern "STRATO GmbH" --direction incoming --account 4905 --tax 19 --note Internetkosten
```

```bash
./auto_assign_vouchers.py
```

## Auto Assign Transactions

```bash
./manage_booking_rules.py --list
```

```bash
./auto_assign_transactions.py --month 2024-01 --dry-run
```


## Belege ohne Buchung/Zuordnung anzeigen

```bash
./report_open_vouchers.py --month 2024-01
```

## Banktransaktionen auf fehlende Belegzuordnung prüfen

```bash
./report_unlinked_transactions.py --month 2024-01
```

??? Wozu ist dann dieser Befehl: ???
```bash
./report_missing_receipts.py --month 2024-01 --non-private
```


## Umsatzsteuer Zahllast ermitteln
```bash
./report_tax_summary.py --month 2024-09
```

## Liste fehlender Belege
### Alle offenen Positionen ≥ 50€
python3 python/reporting/report_belegbeschaffung.py --year 2024 --min-amount 50

### Mit Transaktions-IDs (für direkte DB-Arbeit)
python3 python/reporting/report_belegbeschaffung.py --year 2024 --show-ids

### Alle Positionen ohne Filter
python3 python/reporting/report_belegbeschaffung.py --year 2024

### Nächstes Jahr direkt einsetzbar
python3 python/reporting/report_belegbeschaffung.py --year 2025