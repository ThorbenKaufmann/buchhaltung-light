#!/usr/bin/env python3
import sys
import os
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection


def fetch_ust_report(period=None, year=None):
    """
    Umsatzsteuer-Report: monatlich oder jährlich.
    period: '2025-10' → Einzelmonat
    year: 2025 → Jahresreport
    """
    conn = get_connection()
    cur = conn.cursor()      # RealDictCursor kommt automatisch


    if year:
        sql = """
            SELECT
                DATE_TRUNC('month', periode) AS monat,
                SUM(ust_output) AS ust_output,
                SUM(ust_input) AS ust_input,
                SUM(zahlbetrag) AS zahlbetrag
            FROM vw_ust_report
            WHERE DATE_PART('year', periode) = %s
            GROUP BY 1
            ORDER BY 1;
        """

        cur.execute(sql, (year,))
    elif period:
        sql = """
            SELECT * FROM vw_ust_report
            WHERE TO_CHAR(periode, 'YYYY-MM') = %s
            ORDER BY periode;
        """
        cur.execute(sql, (period,))
    else:
        sql = "SELECT * FROM vw_ust_report ORDER BY periode;"
        cur.execute(sql)

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
