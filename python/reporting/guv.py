#!/usr/bin/env python3
from db import get_connection


def fetch_guv_report(year=None):
    """
    Gewinn- und Verlustrechnung pro Monat oder Jahr.
    """
    conn = get_connection()
    cur = conn.cursor()      # RealDictCursor kommt automatisch


    if year:
        sql = """
            SELECT
                DATE_TRUNC('month', periode) AS monat,
                direction,
                SUM(netto_summe) AS netto_summe,
                SUM(steuer_summe) AS steuer_summe,
                SUM(brutto_summe) AS brutto_summe
            FROM vw_guv_report
            WHERE DATE_PART('year', periode) = %s
            GROUP BY 1, 2
            ORDER BY 1, 2;
        """
        cur.execute(sql, (year,))

    else:
        sql = "SELECT * FROM vw_guv_report ORDER BY periode;"
        cur.execute(sql)

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_guv_classified(year=None):
    """
    Klassifizierte GuV: Ausgabe mit Soll/Haben und Bilanzgruppe.
    Quelle: vw_guv_classified
    """
    conn = get_connection()
    cur = conn.cursor()

    if year:
        sql = """
            SELECT
                DATE_TRUNC('month', periode) AS monat,
                direction,
                account_skr,
                soll_haben,
                bilanz_gruppe,
                SUM(netto_summe)   AS netto_summe,
                SUM(steuer_summe)  AS steuer_summe,
                SUM(brutto_summe)  AS brutto_summe
            FROM vw_guv_classified
            WHERE DATE_PART('year', periode) = %s
            GROUP BY 1,2,3,4,5
            ORDER BY 1,2,3;
        """
        cur.execute(sql, (year,))
    else:
        sql = """
            SELECT
                DATE_TRUNC('month', periode) AS monat,
                direction,
                account_skr,
                soll_haben,
                bilanz_gruppe,
                netto_summe,
                steuer_summe,
                brutto_summe
            FROM vw_guv_classified
            ORDER BY 1,2,3;
        """
        cur.execute(sql)

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows

def fetch_guv_grouped(year=None):
    """
    Gruppierte GuV: Summen nach Bilanz-/GuV-Gruppe (aus account_groups).
    Quelle: vw_guv_grouped
    """
    conn = get_connection()
    cur = conn.cursor()

    if year:
        sql = """
            SELECT
                DATE_TRUNC('month', periode) AS monat,
                bilanz_gruppe,
                SUM(netto_summe)   AS netto_summe,
                SUM(steuer_summe)  AS steuer_summe,
                SUM(brutto_summe)  AS brutto_summe
            FROM vw_guv_grouped
            WHERE DATE_PART('year', periode) = %s
            GROUP BY 1, 2
            ORDER BY 1, 2;
        """
        cur.execute(sql, (year,))
    else:
        sql = """
            SELECT
                DATE_TRUNC('month', periode) AS monat,
                bilanz_gruppe,
                netto_summe,
                steuer_summe,
                brutto_summe
            FROM vw_guv_grouped
            ORDER BY 1, 2;
        """
        cur.execute(sql)

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_guv_result(year=None):
    """GuV-Ergebnis: Ertrag, Aufwand, Gewinn/Verlust"""
    conn = get_connection()
    cur = conn.cursor()

    if year:
        sql = """
            SELECT jahr, kategorie, SUM(netto_summe) AS netto_summe
            FROM vw_guv_result
            WHERE DATE_PART('year', jahr) = %s
            GROUP BY 1,2
            ORDER BY 2;
        """
        cur.execute(sql, (year,))
    else:
        sql = "SELECT * FROM vw_guv_result ORDER BY jahr, kategorie;"
        cur.execute(sql)

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_journal(year=None):
    """Buchungsjournal: alle Buchungen pro Jahr"""
    conn = get_connection()
    cur = conn.cursor()

    if year:
        sql = """
            SELECT *
            FROM vw_journal
            WHERE DATE_PART('year', datum) = %s
            ORDER BY datum, account_skr;
        """
        cur.execute(sql, (year,))
    else:
        sql = "SELECT * FROM vw_journal ORDER BY datum, account_skr;"
        cur.execute(sql)

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_unclassified():
    """Nicht klassifizierte Konten anzeigen"""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM vw_unclassified_accounts ORDER BY account_skr;")
    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_susa(year=None):
    """Summen- und Saldenliste"""
    conn = get_connection()
    cur = conn.cursor()

    if year:
        sql = """
            SELECT *
            FROM vw_susa
            WHERE account_skr IS NOT NULL
            ORDER BY account_skr;
        """
        cur.execute(sql)  # optional: Filter nach Jahr über Voucher-Datum möglich
    else:
        sql = "SELECT * FROM vw_susa ORDER BY account_skr;"
        cur.execute(sql)

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_susa_monthly(year=None):
    """Summen- und Saldenliste (monatsweise)"""
    conn = get_connection()
    cur = conn.cursor()

    if year:
        sql = """
            SELECT
                DATE_TRUNC('month', periode) AS monat,
                account_skr,
                bilanz_gruppe,
                SUM(soll_summe) AS soll_summe,
                SUM(haben_summe) AS haben_summe,
                SUM(saldo) AS saldo,
                MAX(richtung) AS richtung
            FROM vw_susa_monthly
            WHERE DATE_PART('year', periode) = %s
            GROUP BY 1, 2, 3
            ORDER BY 1, 2;
        """
        cur.execute(sql, (year,))
    else:
        sql = "SELECT * FROM vw_susa_monthly ORDER BY periode, account_skr;"
        cur.execute(sql)

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows


def fetch_susa_cumulative(year=None):
    """Summen- und Saldenliste (kumuliert, monatsweise)"""
    conn = get_connection()
    cur = conn.cursor()

    if year:
        sql = """
            SELECT
                DATE_TRUNC('month', periode) AS monat,
                account_skr,
                bilanz_gruppe,
                SUM(soll_summe) AS soll_summe,
                SUM(haben_summe) AS haben_summe,
                SUM(saldo) AS saldo,
                MAX(endsaldo) AS endsaldo,
                MAX(richtung) AS richtung
            FROM vw_susa_monthly_cumulative
            WHERE DATE_PART('year', periode) = %s
            GROUP BY 1,2,3
            ORDER BY 1,2;
        """
        cur.execute(sql, (year,))
    else:
        sql = "SELECT * FROM vw_susa_monthly_cumulative ORDER BY periode, account_skr;"
        cur.execute(sql)

    rows = cur.fetchall()
    cur.close()
    conn.close()
    return rows
