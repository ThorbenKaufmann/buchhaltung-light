# Buchhaltung-Light (BHL)

**Ziel:**  
Eine vollständig nachvollziehbare, GoBD-konforme und quelloffene Buchhaltungs-Engine – lokal, ohne Cloud, ohne Abo.

**Grundidee:**  
- Alle Finanzdaten liegen in einer offenen PostgreSQL-Datenbank  
- Import aus CSV/MT940 (Bank, Kreditkarte, PayPal, etc.)  
- Automatische Kategorisierung über Regeln  
- Reports in Markdown und LaTeX (Bilanz, GuV, UStVA)  
- Fokus auf Einfachheit, Transparenz und Datenhoheit

**Kurz gesagt:**  
> „Buchhaltung wie sie sein sollte – verständlich, lokal, ehrlich.“

---

### Aufbau
| Verzeichnis | Inhalt |
|--------------|---------|
| `sql/` | Datenbankschema |
| `python/` | Import- und Verarbeitungsskripte |
| `config/` | Datenbankkonfiguration |
| `docs/` | Dokumentation und Konzepte |

---

### Setup

```bash
# 1. PostgreSQL bereitstellen
sudo -u postgres psql -c "CREATE DATABASE bhl;"
sudo -u postgres psql -d bhl -f sql/schema.sql
# oder remote:
psql -h dbserver-url -U postgres -c "CREATE DATABASE bhl;"
psql -h dbserver-url -U postgres -d bhl -f sql/schema.sql
psql -h datacenter.itc-embedded.de -U postgres -d bhl -c ""

# 2. Python-Umgebung
python3 -m venv venv
source venv/bin/activate
pip install psycopg2-binary pandas pyyaml mt-940 psycopg2-binary

# 3. Konfiguration anpassen
cp config/db.yaml.example config/db.yaml

# 4. Bankkonten anlegen
psql -h dbserver-url -U postgres -d bhl -f sql/accounts.sql

# 5. Testimport
python/python import_csv.py samples/sample.csv


🔹 4. Beispiele

Alle Konten anzeigen:

python3 python/manage_accounts.py --list


Nach Begriff suchen:

python3 python/manage_accounts.py --search Porto


Neues Konto anlegen oder ändern:

python3 python/manage_accounts.py --add 4950 "Werkzeuge und Kleinmaterial" 19 Aufwand




✅ Verwendung

Interaktiv mit PDF-Vorschau:

python3 python/assign_accounts.py --direction incoming --month 2024-01 --show-pdf


Automatisch mit Regeln (Batch-Modus):

python3 python/assign_accounts.py --direction incoming --month 2024-01 --auto


Beide kombiniert:

python3 python/assign_accounts.py --direction incoming --month 2024-01 --show-pdf --auto




python3 python/set_receipt_status.py voucher 97 complete
python3 python/set_receipt_status.py booking 233 missing

python3 python/match_vouchers.py --direction incoming --link --voucher-id 21 --tx-id 5991
python3 python/match_vouchers.py --direction incoming --month 2024-01

python3 python/unmatch_transaction.py --tx-id 6023
python3 python/unmatch_transaction.py --tx-id 6023 --unmatch


🔹 Belegnummer korrigieren
python3 python/revise_voucher.py --id 91 --field voucher_number --new RE20250021 --reason "Nummer korrigiert"

🔹 Beleg stornieren
python3 python/revise_voucher.py --id 91 --cancel "Falscher Lieferant, neu erfasst"

🔹 Historie anzeigen
python3 python/revise_voucher.py --id 91 --show-history


→ Beispielausgabe:

📜 Revisionshistorie für Beleg-ID 91:

🕒 2025-10-09 08:44 | UPDATE     | Feld: voucher_number     | RE20250020 → RE20250021 | Grund: Nummer korrigiert
🕒 2025-10-09 08:49 | CANCELLED  | Feld: status             | paid → cancelled         | Grund: Falscher Lieferant, neu erfasst


./python/create_self_voucher.py --date 2024-09-24 --partner "Camping Wagner"--amount 5.00 --reason "Mahngebühren zu Rechnung K20008-R4882538" --output belege/2024/09 --add-to-vouchers

✅ Eigenbeleg EB-2024-001 erstellt.
   Hash: 2e5cfb6e3dfafc5b45acbe4b7f6a9c2b...
   PDF:  /home/.../belege/2024/07/EB-2024-001.pdf



   🔧 Nutzung
Eingangsbelege
python add_voucher.py ./rechnung_123.pdf ./ --direction incoming

Ausgangsbelege
python add_outgoing_voucher.py ./Rechnung_Kunde.pdf ./belege/ausgang --direction auto

Hilfe anzeigen
python add_voucher.py --help


Ergebnis:

usage: add_voucher.py [-h] [--direction {incoming,outgoing,auto}] pdf base_dir

Erfasst Eingangs- oder Ausgangsbelege (ZUGFeRD/XRechnung-fähig).

positional arguments:
  pdf           Pfad zur PDF-Datei
  base_dir      Basisverzeichnis (z. B. ./belege)

options:
  --direction   Richtung des Belegs: incoming, outgoing oder auto (Standard: incoming)
  -h, --help    diese Hilfe anzeigen und beenden


  📘 Offiziell definierte TypeCodes laut UN/CEFACT

Hier die wichtigsten aus der Norm (UN/CEFACT 2005-Invoice-TypeCodes):

Code	Bedeutung	Übersetzung / Praxisname
380	Commercial Invoice	normale Rechnung
381	Credit Note	Gutschrift / Storno
382	Debit Note	Belastungsanzeige
383	Consolidated Invoice	Sammelrechnung
384	Corrected Invoice	Korrigierte Rechnung / Stornorechnung mit Neuausstellung
386	Prepayment Invoice	Anzahlungsrechnung
875	Self-Billed Invoice	Gutschrift, die der Empfänger selbst ausstellt



./python/manage_auto_rules.py --add --pattern "HORNBACH Baumarkt" --account 4980 --direction incoming --tax 19 --note "Werkzeug, Büromaterial und Entwicklungsbedarf"


## SQL:

SELECT DISTINCT partner_name
FROM vouchers
WHERE partner_name IS NOT NULL
ORDER BY partner_name;

SELECT DISTINCT partner_name
FROM (
    SELECT partner_name FROM vouchers
    UNION
    SELECT partner_name FROM outgoing_vouchers
) AS all_partners
WHERE partner_name IS NOT NULL
ORDER BY partner_name;


SELECT partner_name, COUNT(*) AS anzahl
FROM (
    SELECT partner_name FROM vouchers
    UNION ALL
    SELECT partner_name FROM outgoing_vouchers
) AS all_partners
WHERE partner_name IS NOT NULL
GROUP BY partner_name
ORDER BY partner_name;



Summen bilden über Geldsenken:
SELECT SUM(amount) AS total_amount FROM transactions WHERE purpose LIKE '%APPLE%' AND booking_date BETWEEN '2024-01-01' AND '2024-12-31';




----- reporting -----

### Monatsreport
SELECT * FROM public.vw_ust_report;

### Quartalsweise Aggregation:

SELECT DATE_TRUNC('quarter', periode) AS quartal,
       SUM(ust_output) AS ust_output,
       SUM(ust_input)  AS ust_input,
       SUM(zahlbetrag) AS zahlbetrag
FROM public.vw_ust_report
GROUP BY 1
ORDER BY 1;

### GuV-Monatsauswertung:
SELECT * FROM public.vw_guv_report;



## AFA

INSERT INTO depreciations (asset_name, account_skr, acquisition_date, acquisition_value, useful_life_years, note)
VALUES
('Büromöbel Experte - Stehschreibtisch', '0420', '2015-09-25', 576.46, 13, 'Büroeinrichtung'),
('profishop Jungheinrich - Werkbank', '0420', '2022-03-29', 1990.98, 13, 'Büroeinrichtung'),
('Tuxedo Infinitybook + Triple Dock', '0420', '2023-02-1', 2300.84, 3, 'Büroeinrichtung');
