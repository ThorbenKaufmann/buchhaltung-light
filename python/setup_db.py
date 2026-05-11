#!/usr/bin/env python3
"""
setup_db.py

Initialisiert eine frische BHL-Datenbank anhand der Konfiguration in config/db.yaml.

Schritte:
  1. Verbindet sich mit dem PostgreSQL-Server (Datenbank 'postgres')
  2. Legt die Datenbank an, falls sie noch nicht existiert
  3. Spielt sql/schema.sql ein (Tabellen, Constraints, Indizes)
  4. Optional: Grunddaten aus sql/seed_skr03.sql (SKR03-Kontenrahmen)

Verwendung:
    python3 python/setup_db.py
    python3 python/setup_db.py --skip-seed
    python3 python/setup_db.py --drop-existing   # VORSICHT: löscht vorhandene DB!

Voraussetzungen:
  - PostgreSQL-Client (psql) im PATH
  - config/db.yaml mit gültigen Verbindungsparametern
  - Benutzer muss CREATEDB-Recht haben (oder Superuser sein)
"""

import argparse
import os
import subprocess
import sys
import yaml
from pathlib import Path

ROOT = Path(__file__).parent.parent
CONFIG_FILE = ROOT / "config" / "db.yaml"
SCHEMA_FILE = ROOT / "sql" / "schema.sql"
SEED_FILE   = ROOT / "sql" / "seed_skr03.sql"


def load_config() -> dict:
    if not CONFIG_FILE.exists():
        print(f"Fehler: {CONFIG_FILE} nicht gefunden.")
        print(f"Bitte {CONFIG_FILE.parent}/db.example.yaml kopieren und anpassen.")
        sys.exit(1)
    with open(CONFIG_FILE) as f:
        return yaml.safe_load(f)


def psql_env(cfg: dict) -> dict:
    env = os.environ.copy()
    env["PGPASSWORD"] = cfg["password"]
    return env


def psql_args(cfg: dict, dbname: str | None = None) -> list[str]:
    return [
        "psql",
        f"--host={cfg['host']}",
        f"--port={cfg.get('port', 5432)}",
        f"--username={cfg['user']}",
        f"--dbname={dbname or cfg['dbname']}",
        "--no-password",
    ]


def db_exists(cfg: dict) -> bool:
    result = subprocess.run(
        psql_args(cfg, dbname="postgres") + [
            "--tuples-only", "--no-align",
            f"--command=SELECT 1 FROM pg_database WHERE datname = '{cfg['dbname']}'",
        ],
        capture_output=True, text=True, env=psql_env(cfg),
    )
    return result.stdout.strip() == "1"


def create_db(cfg: dict):
    print(f"  Erstelle Datenbank '{cfg['dbname']}' ...")
    result = subprocess.run(
        psql_args(cfg, dbname="postgres") + [
            f"--command=CREATE DATABASE \"{cfg['dbname']}\" ENCODING 'UTF8'",
        ],
        capture_output=True, text=True, env=psql_env(cfg),
    )
    if result.returncode != 0:
        print(f"  Fehler: {result.stderr.strip()}")
        sys.exit(1)
    print(f"  ✓ Datenbank '{cfg['dbname']}' angelegt.")


def drop_db(cfg: dict):
    print(f"  Lösche Datenbank '{cfg['dbname']}' ...")
    result = subprocess.run(
        psql_args(cfg, dbname="postgres") + [
            f"--command=DROP DATABASE IF EXISTS \"{cfg['dbname']}\"",
        ],
        capture_output=True, text=True, env=psql_env(cfg),
    )
    if result.returncode != 0:
        print(f"  Fehler: {result.stderr.strip()}")
        sys.exit(1)
    print(f"  ✓ Datenbank '{cfg['dbname']}' gelöscht.")


def apply_sql_file(cfg: dict, sql_file: Path, label: str):
    if not sql_file.exists():
        print(f"  ⚠  {sql_file} nicht gefunden, übersprungen.")
        return
    print(f"  Spiele {label} ein ({sql_file.name}) ...")
    result = subprocess.run(
        psql_args(cfg) + [f"--file={sql_file}", "--quiet"],
        capture_output=True, text=True, env=psql_env(cfg),
    )
    if result.returncode != 0:
        print(f"  Fehler:\n{result.stderr.strip()}")
        sys.exit(1)
    if result.stderr.strip():
        print(f"  Hinweise: {result.stderr.strip()[:200]}")
    print(f"  ✓ {label} erfolgreich eingespielt.")


def main():
    ap = argparse.ArgumentParser(description="BHL-Datenbank initialisieren.")
    ap.add_argument("--drop-existing", action="store_true",
                    help="Vorhandene Datenbank vorher löschen (VORSICHT: alle Daten weg!)")
    ap.add_argument("--skip-seed", action="store_true",
                    help="SKR03-Grunddaten nicht einspielen")
    args = ap.parse_args()

    cfg = load_config()
    dbname = cfg["dbname"]
    host   = cfg["host"]
    port   = cfg.get("port", 5432)

    print(f"\nBHL Setup — Datenbank: '{dbname}' auf {host}:{port}")
    print("=" * 60)

    if args.drop_existing:
        confirm = input(f"  WARNUNG: Datenbank '{dbname}' wird GELÖSCHT. Fortfahren? [ja/N] ")
        if confirm.strip().lower() != "ja":
            print("  Abgebrochen.")
            sys.exit(0)
        drop_db(cfg)

    if db_exists(cfg):
        if not args.drop_existing:
            print(f"  Datenbank '{dbname}' existiert bereits.")
            print("  Verwende --drop-existing um sie neu zu erstellen.")
            print("  Schema wird trotzdem eingespielt (idempotent mit IF NOT EXISTS).")
    else:
        create_db(cfg)

    apply_sql_file(cfg, SCHEMA_FILE, "Schema")

    if not args.skip_seed and SEED_FILE.exists():
        apply_sql_file(cfg, SEED_FILE, "SKR03-Grunddaten")
    elif not args.skip_seed:
        print(f"  ⚠  {SEED_FILE.name} nicht gefunden — SKR03-Konten müssen manuell befüllt werden.")

    print()
    print("✅ Setup abgeschlossen.")
    print(f"   Verbindung: postgresql://{cfg['user']}:***@{host}:{port}/{dbname}")


if __name__ == "__main__":
    main()
