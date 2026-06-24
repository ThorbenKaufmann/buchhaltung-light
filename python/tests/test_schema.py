"""
Smoke-Tests gegen das geladene Schema und den SKR03-Seed.

Diese Tests stellen sicher, dass `sql/schema.sql` und `sql/seed_skr03.sql`
fehlerfrei eingespielt wurden und die zentralen Objekte existieren.
Sie fangen Regressionen in den SQL-Dateien früh ab (z. B. ein kaputtes
View nach einer Migration).
"""

import pytest

EXPECTED_TABLES = [
    "accounts",
    "skr03_accounts",
    "account_groups",
    "transactions",
    "vouchers",
    "voucher_lines",
    "voucher_links",
    "depreciations",
]

EXPECTED_VIEWS = [
    "vw_afa_schedule",
    "vw_guv_report",
    "vw_journal",
    "vw_susa",
    "vw_ust_report",
]


def _names(cur, relkinds):
    cur.execute(
        """
        SELECT c.relname
        FROM pg_class c
        JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname = 'public' AND c.relkind = ANY(%s)
        """,
        (list(relkinds),),
    )
    return {row[0] for row in cur.fetchall()}


@pytest.mark.parametrize("table", EXPECTED_TABLES)
def test_table_exists(db_conn, table):
    with db_conn.cursor() as cur:
        tables = _names(cur, ["r"])  # r = ordinary table
    assert table in tables, f"Tabelle '{table}' fehlt im Schema"


@pytest.mark.parametrize("view", EXPECTED_VIEWS)
def test_view_exists(db_conn, view):
    with db_conn.cursor() as cur:
        views = _names(cur, ["v", "m"])  # v = view, m = materialized view
    assert view in views, f"View '{view}' fehlt im Schema"


def test_skr03_seed_loaded(db_conn):
    """Der SKR03-Seed legt Kontenrahmen-Stammdaten an."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM skr03_accounts")
        n_accounts = cur.fetchone()[0]
        cur.execute("SELECT COUNT(*) FROM account_groups")
        n_groups = cur.fetchone()[0]
    assert n_accounts > 0, "skr03_accounts ist leer – Seed nicht eingespielt?"
    assert n_groups == 7, f"account_groups sollte 7 Gruppen haben, hat {n_groups}"


def test_afa_schedule_view_is_queryable(db_conn):
    """vw_afa_schedule muss ausführbar sein (fängt kaputte View-Definition ab)."""
    with db_conn.cursor() as cur:
        cur.execute("SELECT * FROM vw_afa_schedule LIMIT 1")
        cur.fetchall()  # darf keine Exception werfen
