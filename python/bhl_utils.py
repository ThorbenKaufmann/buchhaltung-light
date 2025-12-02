"""
bhl_utils.py
Zentrale Hilfsfunktionen für das Buchhaltung-Light-System.
Robust und kompatibel mit DictCursor UND normalen Cursor-Tupeln.
"""

from datetime import datetime, date
from decimal import Decimal, ROUND_HALF_UP


# -----------------------------
#  Typ-robuste Row-Extraktion
# -----------------------------
def row_get(row, key, idx=None, default=None):
    """
    Gibt einen Wert aus einer DB-Row zurück – egal ob Dict oder Tuple.

    row: ein Dict (RealDictCursor) oder ein Tuple
    key: Schlüsselname (str)
    idx: fallback Index für Tuple (int)
    """
    if row is None:
        return default

    # DictCursor
    if isinstance(row, dict):
        return row.get(key, default)

    # Normaler Cursor: Indexzugriff
    if idx is not None and isinstance(row, (list, tuple)):
        try:
            return row[idx]
        except IndexError:
            return default

    return default


# -----------------------------
#  Zahlensicherheit
# -----------------------------
def safe_float(value, default=0.0):
    """
    Wandelt Strings, Decimal, int usw. sicher in float um.
    """
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def safe_decimal(value, default=Decimal("0.00")):
    """
    Liefert Decimal – robust für Strings, Float, None.
    """
    try:
        return Decimal(str(value))
    except Exception:
        return default


# -----------------------------
#  Datumsformatierung
# -----------------------------
def format_date(value):
    """
    Formatierung für date / datetime / ISO-Strings.
    Gibt IMMER einen YYYY-MM-DD String zurück.
    """
    if isinstance(value, (date, datetime)):
        return value.strftime("%Y-%m-%d")

    # ISO 8601 String?
    try:
        dt = datetime.fromisoformat(str(value))
        return dt.strftime("%Y-%m-%d")
    except Exception:
        pass

    # Letzter Ausweg: einfach in einen String wandeln
    return str(value)


# -----------------------------
#  Rundung nach kaufmännischer Regel
# -----------------------------
def round_money(value):
    """
    Rundet kaufmännisch auf 2 Dezimalstellen (für Geldbeträge).
    """
    dec = safe_decimal(value)
    return dec.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# -----------------------------
#  Hilfsmakros für Code-Lesbarkeit
# -----------------------------
def is_dict_row(row):
    """True, wenn Row ein DictCursor-Row ist."""
    return isinstance(row, dict)


def unwrap_amount(row, key, idx=None):
    """
    Extrahiert Betrag aus Row → float
    """
    return safe_float(row_get(row, key, idx))


def unwrap_date(row, key, idx=None):
    """
    Extrahiert Datum aus Row → formatiert YYYY-MM-DD
    """
    return format_date(row_get(row, key, idx))


def unwrap_text(row, key, idx=None):
    """
    Extrahiert Textfelder aus Row → garantiert String
    """
    val = row_get(row, key, idx)
    return str(val) if val is not None else ""
