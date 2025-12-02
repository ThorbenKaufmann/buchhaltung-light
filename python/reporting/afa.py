#!/usr/bin/env python3
from db import get_connection

def fetch_afa(year=None):
    """Abschreibungsliste (AfA-Plan)"""
    conn = get_connection()
    cur = conn.cursor()
    if year:
        sql = "SELECT * FROM vw_afa_schedule WHERE jahr = %s ORDER BY account_skr;"
        cur.execute(sql, (year,))
    else:
        sql = "SELECT * FROM vw_afa_schedule ORDER BY jahr, account_skr;"
        cur.execute(sql)
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
