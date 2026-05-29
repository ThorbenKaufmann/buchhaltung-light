# Buchhaltung-Light – Betriebshandbuch

Alle Befehle werden vom **Repo-Root** aus ausgeführt.

---

## 1. Setup und Initialisierung

### 1.1 Voraussetzungen

- Python 3.12+, PostgreSQL 15+, `psql` im PATH
- Python-Pakete: `pip install -r requirements.txt`
- XeLaTeX (für Rechnungs-PDF): `xelatex` im PATH

### 1.2 Datenbank konfigurieren

```bash
cp config/db.example.yaml config/db.yaml
# config/db.yaml anpassen: dbname, user, password, host, port
```

`config/db.yaml` steht in `.gitignore` und wird nie ins Repository committed.

### 1.3 Datenbank anlegen

```bash
python3 python/setup_db.py
```

Legt die Datenbank an (falls noch nicht vorhanden), spielt `sql/schema.sql` ein
und befüllt den SKR03-Kontenrahmen aus `sql/seed_skr03.sql`.

**Flags:**

| Flag | Wirkung |
|------|---------|
| `--skip-seed` | SKR03-Daten nicht einspielen |
| `--drop-existing` | Bestehende DB vorher löschen (Rückfrage!) |

### 1.4 Weitere Firma verwalten

Repo-Verzeichnis kopieren, eigene `config/db.yaml` mit anderem `dbname` anlegen,
dann `setup_db.py` ausführen. Alle Skripte lesen die Konfiguration relativ zu
ihrer eigenen Position – kein Pfad muss angepasst werden.

---

## 2. Bankkonten

### 2.1 Konten einrichten

Bankkonten sind Einträge in der Tabelle `accounts`. Neue Konten werden direkt per SQL angelegt (siehe `sql/accounts.sql`):

```sql
INSERT INTO accounts (name, type, iban)
VALUES ('Hauptkonto', 'bank', 'DE...');
```

Erlaubte Typen: `bank`, `credit`, `paypal`, `cash`, `savings`.

Bekannte Konten (Standard-Setup):

| ID | Name | Typ |
|----|------|-----|
| 1 | Hauptkonto | bank |
| 2 | Mastercard | credit |
| 3 | PayPal | paypal |
| 4 | Tagesgeld | savings |

Beispiel:

```bash
psql -h datacenter.itc-embedded.de -U postgres -d bhl-ug -f sql/accounts.sql
```



### 2.2 Umsätze importieren

**MT940 (Giro, Kreditkarte):**

```bash
# Einzelne Datei
python3 python/import_mt940.py <datei.mt940> <account_id>

# Ganzes Verzeichnis (alle *.mt940-Dateien)
python3 python/batch_import_mt940.py <verzeichnis> <account_id>
```

Die Dateien müssen die Endung `.mt940` haben.
Dubletten werden per Hash erkannt und stillschweigend übersprungen –
der Import ist idempotent.

**Commerzbank (CSV-Export):**

```bash
python3 python/import_commerzbank_csv.py <datei.csv> <account_id>
python3 python/import_commerzbank_csv.py <datei.csv> <account_id> --dry-run
```

CSV-Export unter: Online-Banking → Umsätze → Herunterladen → CSV.
Dateiname hat typischerweise die Form `DE36…_EUR_DD-MM-YYYY_HHMM.csv`.
Der Gegenparteiname wird automatisch aus dem Buchungstext extrahiert (vor BIC/IBAN/End-to-End-Ref).
Dubletten werden per Hash erkannt und übersprungen – der Import ist idempotent.

**PayPal (CSV-Export):**

```bash
python3 python/import_paypal_csv.py secret/PayPal_2024.csv
python3 python/import_paypal_csv.py secret/PayPal_2024.csv --dry-run
python3 python/import_paypal_csv.py secret/PayPal_2024.csv --account-id 3
```

CSV-Export aus paypal.com: Aktivitäten → Alle Transaktionen → Herunterladen → CSV.
Automatisch herausgefiltert werden: Bank Deposits, Pending, Memo-only, FX-Umbuchungen.

### 2.3 Transaktionen vorkategorisieren

Buchungsregeln verwalten (Muster → Konto, Flags):

```bash
python3 python/manage_booking_rules.py --list
python3 python/manage_booking_rules.py --add \
    --pattern "STRATO" --direction incoming --account 4905 --tax 19 --note "Hosting"
python3 python/manage_booking_rules.py --delete <ID>
```

Regeln anwenden (Dry-Run empfohlen):

```bash
python3 python/auto_assign_transactions.py --month 2024-01 --dry-run
python3 python/auto_assign_transactions.py --month 2024-01
```

Einzelne Transaktion manuell flaggen:

```bash
python3 python/set_transaction_flags.py --txid 1234 --is_private TRUE
python3 python/set_transaction_flags.py --txid 1234 --is_internal TRUE
```

**Flags:**

| Flag | Bedeutung |
|------|-----------|
| `is_private` | Privattransaktion, kein Beleg erforderlich |
| `is_internal` | Interne Umbuchung (z. B. Steuern, Darlehen) |
| `is_cyclic` | Wiederkehrende Zahlung (z. B. Lastschrift) |

Offene Transaktionen ohne Belegzuordnung prüfen:

```bash
python3 python/reporting/report_belegbeschaffung.py --year 2024
python3 python/reporting/report_belegbeschaffung.py --year 2024 --min-amount 50
python3 python/reporting/report_belegbeschaffung.py --year 2024 --show-ids
```

---

## 3. Belege

### 3.1 Neue Belege einpflegen

**Einzelner Beleg:**

```bash
python3 python/add_voucher.py <rechnung.pdf> ./belege --direction incoming
python3 python/add_voucher.py <rechnung.pdf> ./belege --direction outgoing
python3 python/add_voucher.py <rechnung.pdf> ./belege --direction auto
```

**Batch (ganzes Verzeichnis):**

```bash
python3 python/add_all_vouchers.py ./backlog/2024/01/ ./belege --direction incoming
python3 python/add_all_vouchers.py ./backlog/out/ ./belege --direction outgoing
```

ZUGFeRD/XRechnung-Metadaten werden automatisch extrahiert, falls vorhanden.

**Ausgangsbelege (separates Tool):**

```bash
python3 python/add_outgoing_voucher.py <rechnung.pdf> ./belege/ausgang
python3 python/add_all_outgoing_vouchers.py ./backlog/out/ ./belege/ausgang
```

### 3.2 Belege mit Transaktionen verknüpfen

Automatisches Matching (Betrag + Datum):

```bash
python3 python/match_vouchers.py --direction incoming --month 2024-01
python3 python/match_vouchers.py --direction outgoing --month 2024-01
python3 python/match_vouchers.py --direction incoming --month 2024-01 --window 60
python3 python/match_vouchers.py --direction incoming --show-all
```

Manuelle Verknüpfung:

```bash
python3 python/link_transactions_to_voucher.py --voucher-id <VID> --tx-ids 123 456
python3 python/link_vouchers_to_transaction.py --tx-id <TID> --voucher-ids 10 11
```

Verknüpfung aufheben:

```bash
python3 python/unmatch_transaction.py --txid <TID>
```

Offene Belege (noch nicht verknüpft) anzeigen:

```bash
python3 python/reporting/report_open_vouchers.py --month 2024-01
python3 python/reporting/report_unlinked_transactions.py --month 2024-01
```

### 3.3 Konten zuordnen (SKR03-Buchung)

Auto-Regeln für Belege verwalten:

```bash
python3 python/manage_auto_rules.py --add \
    --pattern "STRATO GmbH" --direction incoming --account 4905 --tax 19 --note "Hosting"
python3 python/auto_assign_vouchers.py
```

Manuelle Kontozuordnung (interaktiv):

```bash
python3 python/assign_accounts.py --direction incoming --month 2024-01
python3 python/assign_accounts.py --direction outgoing --month 2024-01
python3 python/assign_accounts.py --direction incoming --month 2024-01 --auto
```

Im `--auto`-Modus werden nur Einträge mit bekannter Regel gebucht;
Einträge ohne Regel werden übersprungen.

Belegstatus nachträglich setzen:

```bash
python3 python/set_receipt_status.py --voucher-id <VID> --status complete
# Status: complete | pending | missing | incomplete
```

### 3.4 Eigenbelege erstellen

Wenn kein externer Beleg vorhanden ist (Kfz, Reise, Kleinbetrag):

```bash
python3 python/create_self_voucher.py \
    --date 2024-03-15 \
    --partner "Reifen Salewski" \
    --amount 120.00 \
    --reason "Reifenwechsel LG Q 71" \
    --add-to-vouchers
```

Eigenbelege haben `status='draft'` und `receipt_status='missing`.
Sobald ein echter Beleg vorliegt, Voucher auf `status='booked'` setzen
und den Eigenbeleg ersetzen.

---

## 4. Ausgangsrechnungen

Arbeitsverzeichnis: `python/invoicing/`

### 4.1 Rechnungsdaten pflegen

Rechnungsdaten als YAML-Datei anlegen: `data/invoice_RE20260001.yaml`

### 4.2 Rechnung rendern

```bash
cd python/invoicing

# Factur-X XML (maschinenlesbar)
./render_facturx.py ./data/invoice_RE20260001.yaml \
    ./templates/factur-x.en16931.xml.j2 \
    build/invoice_RE20260001.xml

# Validierung
facturx-xmlcheck build/invoice_RE20260001.xml

# PDF (LaTeX)
./render_invoice.py ./data/invoice_RE20260001.yaml \
    ./templates/invoice.tex.j2 \
    build/invoice_RE20260001.tex
TEXINPUTS=../../config/latex/lco/: xelatex build/invoice_RE20260001.tex

# PDF + XML zusammenführen (ZUGFeRD)
facturx-pdfgen invoice_RE20260001.pdf \
    build/invoice_RE20260001.xml \
    invoice_RE20260001_x.pdf
```

### 4.3 Zahlungserinnerung / Mahnung

```bash
./render_invoice.py ./data/invoice_RE20260001.yaml \
    ./templates/dunning_letter_easy.tex.j2 \
    build/invoice_RE20260001_dunning_letter.tex
TEXINPUTS=../../config/latex/lco/: xelatex build/invoice_RE20260001_dunning_letter.tex
```

---

## 5. Regeln pflegen

### 5.1 Buchungsregeln (Transaktionsebene)

Regeln matchen auf `counterpart_name` (ILIKE) und setzen Konto, Steuer und Flags.

```bash
python3 python/manage_booking_rules.py --list
python3 python/manage_booking_rules.py --list-flags
python3 python/manage_booking_rules.py --add \
    --pattern "NETFLIX" --direction incoming --account 4900 --tax 19 \
    --private TRUE --note "Streaming privat"
python3 python/manage_booking_rules.py --edit <ID> --account 4905
python3 python/manage_booking_rules.py --delete <ID>
```

### 5.2 Auto-Regeln (Belegebene)

```bash
python3 python/manage_auto_rules.py --list
python3 python/manage_auto_rules.py --add \
    --pattern "Easybell" --direction incoming --account 4920 --tax 19 --note "Telefon"
```

---

## 6. Reporting und Abschluss

### 6.1 Monatlicher Überblick

```bash
# Kontenübersicht (Netto pro SKR03-Konto)
python3 python/reporting/report_account_summary.py --month 2024-01

# Cashflow-Überblick
python3 python/reporting/report_cashflow.py --year 2024

# BWA (alle Monate eines Jahres)
python3 python/reporting/report_bwa.py --year 2024
```

### 6.2 Umsatzsteuervoranmeldung (monatlich/quartalsweise)

```bash
python3 python/reporting/report_tax_summary.py --month 2024-01
```

Liefert: Umsatzsteuer (Ausgangsumsätze), Vorsteuer (Eingangsumsätze), Zahllast.

Für die UStVA-Übermittlung an Elster die Zahlen aus diesem Report verwenden.

### 6.3 Belegbeschaffungs-Liste (Jahresabschluss)

```bash
# Überblick: was ist noch offen?
python3 python/reporting/report_belegbeschaffung.py --year 2024

# Nur Positionen ab 50 €
python3 python/reporting/report_belegbeschaffung.py --year 2024 --min-amount 50

# Mit Transaktions-IDs für direkte DB-Arbeit
python3 python/reporting/report_belegbeschaffung.py --year 2024 --show-ids
```

Ziel: alle Transaktionen sind entweder `is_private`, `is_internal` oder haben
eine Verknüpfung in `voucher_links` / `outgoing_links`.

### 6.4 Integrität prüfen

```bash
python3 python/reporting/report_ist_integrity.py
python3 python/check_balanced_transactions.py
```

### 6.5 Daten exportieren

```bash
python3 python/reporting/export.py --year 2024
```

---

## 7. Sonstiges

### Transaktion komplett neutralisieren

Wenn eine Transaktion vollständig rückgängig gemacht werden soll
(alle Links, Buchungszeilen, Flags entfernen):

```bash
python3 python/neutralize_transaction.py --txid 1234 --dry-run
python3 python/neutralize_transaction.py --txid 1234
```

### Beleg entfernen

```bash
python3 python/remove_voucher.py --voucher-id <VID>
```

### Beleg korrigieren

```bash
python3 python/revise_voucher.py --voucher-id <VID>
```

### Buchungszeilen neu aufbauen

```bash
python3 python/rebuild_booking_lines.py --month 2024-01
```

### SKR03-Konten suchen

```bash
python3 python/manage_accounts.py --search "Reisekosten"
python3 python/manage_accounts.py --list
```
