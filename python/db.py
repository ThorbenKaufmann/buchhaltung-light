import psycopg2
import yaml

def get_connection():
    with open("config/db.yaml", "r") as f:
        cfg = yaml.safe_load(f)
    return psycopg2.connect(
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
        host=cfg["host"],
        port=cfg.get("port", 5432)
    )

