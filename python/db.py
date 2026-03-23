from psycopg2.extras import RealDictCursor
import psycopg2, yaml
from pathlib import Path

import psycopg2.extensions
from decimal import Decimal

DEC2FLOAT = psycopg2.extensions.new_type(
    psycopg2.extensions.DECIMAL.values,
    'DEC2FLOAT',
    lambda value, curs: Decimal(value) if value is not None else None
)

psycopg2.extensions.register_type(DEC2FLOAT)

def get_connection(dict_cursor=False):
    cfg_path = Path(__file__).parent.parent / "config/db.yaml"
    with open(cfg_path, "r") as f:
        cfg = yaml.safe_load(f)

    if dict_cursor:
        return psycopg2.connect(
            dbname=cfg["dbname"],
            user=cfg["user"],
            password=cfg["password"],
            host=cfg["host"],
            port=cfg.get("port", 5432),
            cursor_factory=RealDictCursor,
        )

    return psycopg2.connect(
        dbname=cfg["dbname"],
        user=cfg["user"],
        password=cfg["password"],
        host=cfg["host"],
        port=cfg.get("port", 5432),
    )
