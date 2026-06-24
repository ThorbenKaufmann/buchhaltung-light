"""
Gemeinsame pytest-Fixtures für die BHL-Tests.

Voraussetzung: Die Test-Datenbank ist bereits initialisiert
(Schema + SKR03-Seed), z. B. über `python3 python/setup_db.py` in der
CI-Pipeline. Die Verbindungsdaten kommen aus config/db.yaml (via db.py).

Sicherheit: Tests dürfen NUR gegen eine Test-Datenbank laufen, niemals
gegen die Produktiv-DB. Die Fixture `db_conn` prüft das und bricht ab,
falls der DB-Name verdächtig nach Produktion aussieht.
"""

import yaml
from pathlib import Path

import pytest

import db  # python/db.py – via pytest.ini auf dem Importpfad

CONFIG_FILE = Path(__file__).resolve().parents[2] / "config" / "db.yaml"

# DB-Namen, gegen die NIEMALS getestet werden darf.
PRODUCTION_DB_NAMES = {"bhl-ug", "bhl"}


def _config() -> dict:
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


@pytest.fixture(scope="session")
def db_config() -> dict:
    cfg = _config()
    dbname = cfg.get("dbname", "")
    if dbname in PRODUCTION_DB_NAMES:
        pytest.exit(
            f"ABBRUCH: Tests laufen gegen mutmaßliche Produktiv-DB '{dbname}'. "
            f"config/db.yaml muss auf eine Test-Datenbank zeigen.",
            returncode=2,
        )
    return cfg


@pytest.fixture()
def db_conn(db_config):
    """
    Funktions-scoped Verbindung. Jeder Test läuft in einer eigenen
    Transaktion, die am Ende zurückgerollt wird – so bleiben Test-Inserts
    isoliert und die DB sauber.
    """
    conn = db.get_connection()
    try:
        yield conn
    finally:
        conn.rollback()
        conn.close()
