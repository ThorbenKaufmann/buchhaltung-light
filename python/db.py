from psycopg2.extras import RealDictCursor
import psycopg2, yaml
from pathlib import Path

def get_connection():
    cfg_path = Path(__file__).parent.parent / "config/db.yaml"
    with open(cfg_path, "r") as f:
        cfg = yaml.safe_load(f)
    conn = psycopg2.connect(
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
        host=cfg["host"],
        port=cfg.get("port", 5432),
        cursor_factory=RealDictCursor,   # <<< das ist wichtig
    )
    return conn
