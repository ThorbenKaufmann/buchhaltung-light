# Tests & CI

Das BHL-System wird gegen eine **dedizierte PostgreSQL-Test-Datenbank**
getestet. Produktivdaten werden dabei nie berührt – siehe Sicherheitshinweis
unten.

## Teststruktur

| Datei | Zweck |
|-------|-------|
| `python/tests/conftest.py` | DB-Fixtures; pro Test eine zurückgerollte Transaktion. Bricht ab, falls `config/db.yaml` auf eine Produktiv-DB (`bhl`, `bhl-ug`) zeigt. |
| `python/tests/test_schema.py` | Smoke-Tests: zentrale Tabellen & Views existieren, SKR03-Seed ist geladen, `vw_afa_schedule` ist ausführbar. |
| `python/tests/test_balance.py` | Logiktests zur Belegabstimmung (Sammelzahlungen), spiegelt `check_balanced_transactions.py`. |

## Lokal ausführen

```bash
# 1. Test-DB-Server bereitstellen (Beispiel: Wegwerf-Container)
docker run -d --name bhl_test_pg -e POSTGRES_PASSWORD=ci_test_pw \
  -p 5544:5432 postgres:14-alpine

# 2. config/db.yaml auf die Test-DB zeigen lassen (NICHT 'bhl' / 'bhl-ug')
cat > config/db.yaml <<'EOF'
dbname: bhl_ci_test
user: postgres
password: ci_test_pw
host: localhost
port: 5544
EOF

# 3. Abhängigkeiten + Test-Tools
python3 -m venv venv && . venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt

# 4. DB initialisieren (Schema + SKR03-Seed) und Tests laufen lassen
printf 'ja\n' | python3 python/setup_db.py --drop-existing
pytest
```

## Jenkins

Die Pipeline ist in `Jenkinsfile` definiert. Stages:

1. **Guard** – bricht ab, wenn `DB_NAME` eine Produktiv-DB ist.
2. **Test-Konfiguration schreiben** – erzeugt `config/db.yaml` aus den
   Jenkins-Werten (überschreibt die im Repo committete Datei).
3. **Python-Umgebung** – venv + `requirements*.txt`.
4. **Test-DB initialisieren** – `setup_db.py --drop-existing` (frische DB).
5. **Smoke** – `compileall` über alle Python-Skripte.
6. **pytest** – inkl. JUnit- und Coverage-Report unter `test-results/`.

### Voraussetzungen auf dem Jenkins-Agent
- `python3` (mit `venv`) und `psql` im PATH
- Netzzugriff auf den PostgreSQL-Testserver
- Jenkins-Credential (Secret Text) mit ID **`bhl-test-db-password`**

Host/User/DB-Name stehen im `environment`-Block des `Jenkinsfile` und können
dort angepasst werden. Der DB-Name ist auf `bhl_ci_test` voreingestellt.

## Sicherheitshinweis

`config/db.yaml` ist in `.gitignore`, war aber bereits **committet** und
enthält in der History Produktiv-Zugangsdaten. Empfehlung: die Datei aus dem
Tracking entfernen (`git rm --cached config/db.yaml`) und das Passwort des
Produktiv-Servers rotieren. Die CI überschreibt diese Datei ohnehin mit
Test-Werten und löscht sie nach dem Lauf wieder.
