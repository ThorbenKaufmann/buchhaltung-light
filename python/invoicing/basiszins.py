#!/usr/bin/env python3
"""Basiszinssatz nach § 247 BGB und daraus abgeleitete Verzugszinsen.

Der Basiszinssatz wird von der Deutschen Bundesbank zum 1. Januar und zum
1. Juli jedes Jahres neu festgesetzt. Ein Verzugszeitraum kann deshalb ueber
mehrere Zinsstufen laufen; die Zinsen sind dann tagegenau je Stufe zu
berechnen (§ 288 i.V.m. § 247 BGB).

Quelle der Tabelle:
https://www.bundesbank.de/de/bundesbank/organisation/agb-und-regelungen/basiszinssatz-607820

WARTUNG: Die Tabelle ist zum 1. Januar und 1. Juli um den neuen Wert zu
ergaenzen. Liegt ein Zinstag hinter dem letzten Eintrag, warnt das Modul auf
stderr, rechnet aber mit dem letzten bekannten Wert weiter.
"""

import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP

# Zinstagebasis. Deutsche Praxis bei Verzugszinsen: taggenau / 365.
DAY_BASIS = Decimal("365")

# Verzugszinsaufschlag in Prozentpunkten auf den Basiszinssatz.
SURCHARGE_B2B      = Decimal("9.00")   # § 288 Abs. 2 BGB (kein Verbraucher beteiligt)
SURCHARGE_CONSUMER = Decimal("5.00")   # § 288 Abs. 1 BGB

# (gueltig ab, Basiszinssatz in Prozent) -- aufsteigend sortiert.
BASE_RATES = [
    (date(2002,  7, 1), Decimal("2.47")),
    (date(2003,  1, 1), Decimal("1.97")),
    (date(2003,  7, 1), Decimal("1.22")),
    (date(2004,  1, 1), Decimal("1.14")),
    (date(2004,  7, 1), Decimal("1.13")),
    (date(2005,  1, 1), Decimal("1.21")),
    (date(2005,  7, 1), Decimal("1.17")),
    (date(2006,  1, 1), Decimal("1.37")),
    (date(2006,  7, 1), Decimal("1.95")),
    (date(2007,  1, 1), Decimal("2.70")),
    (date(2007,  7, 1), Decimal("3.19")),
    (date(2008,  1, 1), Decimal("3.32")),
    (date(2008,  7, 1), Decimal("3.19")),
    (date(2009,  1, 1), Decimal("1.62")),
    (date(2009,  7, 1), Decimal("0.12")),
    (date(2010,  1, 1), Decimal("0.12")),
    (date(2010,  7, 1), Decimal("0.12")),
    (date(2011,  1, 1), Decimal("0.12")),
    (date(2011,  7, 1), Decimal("0.37")),
    (date(2012,  1, 1), Decimal("0.12")),
    (date(2012,  7, 1), Decimal("0.12")),
    (date(2013,  1, 1), Decimal("-0.13")),
    (date(2013,  7, 1), Decimal("-0.38")),
    (date(2014,  1, 1), Decimal("-0.63")),
    (date(2014,  7, 1), Decimal("-0.73")),
    (date(2015,  1, 1), Decimal("-0.83")),
    (date(2015,  7, 1), Decimal("-0.83")),
    (date(2016,  1, 1), Decimal("-0.83")),
    (date(2016,  7, 1), Decimal("-0.88")),
    (date(2017,  1, 1), Decimal("-0.88")),
    (date(2017,  7, 1), Decimal("-0.88")),
    (date(2018,  1, 1), Decimal("-0.88")),
    (date(2018,  7, 1), Decimal("-0.88")),
    (date(2019,  1, 1), Decimal("-0.88")),
    (date(2019,  7, 1), Decimal("-0.88")),
    (date(2020,  1, 1), Decimal("-0.88")),
    (date(2020,  7, 1), Decimal("-0.88")),
    (date(2021,  1, 1), Decimal("-0.88")),
    (date(2021,  7, 1), Decimal("-0.88")),
    (date(2022,  1, 1), Decimal("-0.88")),
    (date(2022,  7, 1), Decimal("-0.88")),
    (date(2023,  1, 1), Decimal("1.62")),
    (date(2023,  7, 1), Decimal("3.12")),
    (date(2024,  1, 1), Decimal("3.62")),
    (date(2024,  7, 1), Decimal("3.37")),
    (date(2025,  1, 1), Decimal("2.27")),
    (date(2025,  7, 1), Decimal("1.27")),
    (date(2026,  1, 1), Decimal("1.27")),
    (date(2026,  7, 1), Decimal("1.52")),
]

LAST_KNOWN_FROM = BASE_RATES[-1][0]


def base_rate(day):
    """Basiszinssatz (Prozent), der an `day` gilt."""
    if day < BASE_RATES[0][0]:
        raise ValueError(f"kein Basiszinssatz fuer {day} hinterlegt (Tabelle beginnt {BASE_RATES[0][0]})")
    rate = BASE_RATES[0][1]
    for start, value in BASE_RATES:
        if start > day:
            break
        rate = value
    return rate


def _next_change_after(day):
    """Erster Stichtag nach `day`, an dem sich der Satz aendern kann."""
    for start, _ in BASE_RATES:
        if start > day:
            return start
    # Hinter der Tabelle: naechster regulaerer Stichtag (1.1. bzw. 1.7.).
    if day < date(day.year, 7, 1):
        return date(day.year, 7, 1)
    return date(day.year + 1, 1, 1)


def interest_periods(due_date, until, surcharge=SURCHARGE_B2B):
    """Zerlege den Verzugszeitraum in Abschnitte gleichen Basiszinssatzes.

    Verzinst werden die Tage `due_date + 1` bis einschliesslich `until`
    (§ 187 Abs. 1 BGB: der Faelligkeitstag zaehlt nicht mit).

    Liefert eine Liste von dicts: from, to, days, base_rate, rate_percent.
    """
    periods = []
    day = due_date + timedelta(days=1)
    while day <= until:
        rate = base_rate(day)
        end = min(until, _next_change_after(day) - timedelta(days=1))
        periods.append({
            "from":         day,
            "to":           end,
            "days":         (end - day).days + 1,
            "base_rate":    rate,
            "rate_percent": rate + surcharge,
        })
        day = end + timedelta(days=1)
    return periods


def delay_interest(amount, due_date, until, surcharge=SURCHARGE_B2B, warn=True):
    """Verzugszinsen auf `amount` von `due_date` (exkl.) bis `until` (inkl.).

    Rechnet je Basiszins-Abschnitt und rundet erst die Summe kaufmaennisch.
    Rueckgabe: (Betrag als Decimal mit 2 Nachkommastellen, Abschnittsliste).
    """
    if until <= due_date:
        return Decimal("0.00"), []

    if warn and until >= _next_change_after(LAST_KNOWN_FROM):
        print(
            f"WARN: Basiszins-Tabelle endet am {LAST_KNOWN_FROM.isoformat()}, "
            f"gerechnet wird bis {until.isoformat()}. Bitte BASE_RATES in "
            f"basiszins.py aktualisieren (Bundesbank, 1.1. und 1.7.).",
            file=sys.stderr,
        )

    periods = interest_periods(due_date, until, surcharge)
    total = Decimal("0")
    for p in periods:
        p["interest"] = amount * (p["rate_percent"] / 100) * p["days"] / DAY_BASIS
        total += p["interest"]

    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP), periods


if __name__ == "__main__":
    import argparse

    ap = argparse.ArgumentParser(description="Verzugszinsen nach § 288 BGB berechnen")
    ap.add_argument("amount", help="Forderungsbetrag, z.B. 10776.00")
    ap.add_argument("due_date", help="Faelligkeitsdatum YYYY-MM-DD")
    ap.add_argument("--until", help="Stichtag YYYY-MM-DD (Vorgabe: heute)")
    ap.add_argument("--consumer", action="store_true", help="5 statt 9 Prozentpunkte (§ 288 Abs. 1 BGB)")
    args = ap.parse_args()

    due   = date.fromisoformat(args.due_date)
    until = date.fromisoformat(args.until) if args.until else date.today()
    surch = SURCHARGE_CONSUMER if args.consumer else SURCHARGE_B2B

    total, periods = delay_interest(Decimal(args.amount), due, until, surch)
    for p in periods:
        print(
            f"{p['from']} - {p['to']}  {p['days']:>4} Tage  "
            f"Basis {p['base_rate']:>6} % + {surch} = {p['rate_percent']:>6} %  "
            f"{p['interest'].quantize(Decimal('0.01'), rounding=ROUND_HALF_UP):>10} EUR"
        )
    print(f"{'Summe':>58} {total:>10} EUR")
