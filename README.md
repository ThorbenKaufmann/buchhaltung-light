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

# 2. Python-Umgebung
python3 -m venv venv
source venv/bin/activate
pip install psycopg2-binary pandas pyyaml

# 3. Konfiguration anpassen
cp config/db.yaml.example config/db.yaml

# 4. Testimport
python/python import_csv.py samples/sample.csv


