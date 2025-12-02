#!/usr/bin/env python3
"""
BHL Reporting CLI
-----------------
Beispiele:
    ./python/reporting/report.py --type ust --period 2025-10
    ./python/reporting/report.py --type ust --year 2025 --export md
    ./python/reporting/report.py --type guv --year 2025 --export csv
    ./python/reporting/report.py --type yearly --year 2025
"""

import argparse
import sys
from pathlib import Path
import pandas as pd
import tabulate


# Pfadkorrektur für Direktaufruf
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from reporting import ust, guv, afa


def fmt(df: pd.DataFrame) -> pd.DataFrame:
    """Formatiert Zahlen und Datumsspalten schön für Konsole/Markdown."""

    def fmt_money(x):
        # akzeptiert Decimal, float, int
        from decimal import Decimal
        if isinstance(x, (int, float, Decimal)):
            try:
                return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            except Exception:
                return str(x)
        return x

    # jede Spalte prüfen und bei numerischem Typ formatieren
    for col in df.columns:
        sample = df[col].dropna().iloc[0] if not df[col].dropna().empty else None
        if isinstance(sample, (int, float)):
            df[col] = df[col].apply(fmt_money)
        elif "Decimal" in str(type(sample)):  # Pandas kennt Decimal nicht direkt
            df[col] = df[col].apply(fmt_money)

    # Datumsformatierung
    if "periode" in df.columns:
        df["periode"] = df["periode"].astype(str).str[:10]

    if "monat" in df.columns:
        df["monat"] = pd.to_datetime(df["monat"]).dt.strftime("%Y-%m")


    return df



def export_markdown(rows, out_path: Path):
    if not rows:
        print("⚠️  Keine Daten gefunden.")
        return
    df = pd.DataFrame(rows)
    df = fmt(df)
    md = df.to_markdown(index=False)
    out_path.write_text(md, encoding="utf-8")
    print(f"✅ Markdown-Report geschrieben: {out_path}")


def export_csv(rows, out_path: Path):
    if not rows:
        print("⚠️  Keine Daten gefunden.")
        return
    df = pd.DataFrame(rows)
    df.to_csv(out_path, index=False)
    print(f"✅ CSV-Report geschrieben: {out_path}")


def display(rows):
    if not rows:
        print("Keine Daten gefunden.")
        return

    df = pd.DataFrame(rows)
    df = fmt(df)

    # --- Summenzeile (für numerische Spalten) ---
    totals = {c: "" for c in df.columns}
    totals[df.columns[0]] = "**Gesamt**"

    # Hilfsfunktion: Kommawerte wieder in float umwandeln
    def parse_num(val):
        if isinstance(val, (int, float)):
            return float(val)
        if isinstance(val, str):
            try:
                return float(val.replace(".", "").replace(",", "."))
            except ValueError:
                return 0.0
        return 0.0

    for c in df.columns[1:]:
        try:
            vals = [parse_num(v) for v in df[c]]
            s = sum(vals)
            if abs(s) > 0.0001:  # nur sinnvolle Summen anzeigen
                totals[c] = f"{s:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        except Exception:
            totals[c] = ""

    # Summenzeile anhängen
    df = pd.concat([df, pd.DataFrame([totals])], ignore_index=True)

    # Ausgabe
    print(tabulate.tabulate(df, headers="keys", tablefmt="github", showindex=False))


def yearly_summary(year: int):
    """Kompaktübersicht: USt-Zahllast + GuV-Ergebnis."""
    ust_rows = ust.fetch_ust_report(year=year)
    guv_rows = guv.fetch_guv_report(year=year)

    ust_sum = sum(float(r.get("zahlbetrag", 0)) for r in ust_rows)
    guv_ertrag = sum(float(r.get("netto_summe", 0))
                     for r in guv_rows if r.get("direction") == "outgoing")
    guv_aufwand = sum(float(r.get("netto_summe", 0))
                      for r in guv_rows if r.get("direction") == "incoming")
    guv_ergebnis = guv_ertrag - guv_aufwand

    data = [{
        "Jahr": year,
        "Umsatzsteuer-Zahllast": ust_sum,
        "Erträge": guv_ertrag,
        "Aufwendungen": guv_aufwand,
        "Ergebnis": guv_ergebnis,
        "Gewinn nach USt": guv_ergebnis - ust_sum
    }]
    df = pd.DataFrame(data)
    df = fmt(df)
    print("\n### Jahresabschluss kompakt\n")
    print(tabulate.tabulate(df, headers="keys", tablefmt="github", showindex=False))


def main():
    parser = argparse.ArgumentParser(description="Buchhaltung-Light Reporting Modul")
    parser.add_argument("--type",
    choices=[
        "ust",
        "guv",
        "guv_classified",
        "guv_grouped",
        "guv_result",
        "journal",
        "unclassified",
        "susa",
        "susa_monthly",
        "susa_cumulative",
        "afa",
        "yearly"
    ],
    required=True,
    help="Reporttyp"
    )

    parser.add_argument("--period", help="z.B. 2024-01")
    parser.add_argument("--year", type=int, help="z.B. 2025")
    parser.add_argument("--export", choices=["md", "csv"], help="Exportformat")
    args = parser.parse_args()

    if args.type == "ust":
        rows = ust.fetch_ust_report(period=args.period, year=args.year)
    elif args.type == "guv":
        rows = guv.fetch_guv_report(year=args.year)
    elif args.type == "guv_classified":
        rows = guv.fetch_guv_classified(year=args.year)
    elif args.type == "guv_grouped":
        rows = guv.fetch_guv_grouped(year=args.year)
    elif args.type == "guv_result":
        rows = guv.fetch_guv_result(year=args.year)
    elif args.type == "journal":
        rows = guv.fetch_journal(year=args.year)
    elif args.type == "susa":
        rows = guv.fetch_susa(year=args.year)
    elif args.type == "susa_monthly":
        rows = guv.fetch_susa_monthly(year=args.year)
    elif args.type == "susa_cumulative":
        rows = guv.fetch_susa_cumulative(year=args.year)
    elif args.type == "afa":
        rows = afa.fetch_afa(year=args.year)


    elif args.type == "unclassified":
        rows = guv.fetch_unclassified()

    else:  # yearly
        yearly_summary(args.year or pd.Timestamp.now().year)
        return


    if args.export == "md":
        export_markdown(rows, Path(f"report_{args.type}.md"))
    elif args.export == "csv":
        export_csv(rows, Path(f"report_{args.type}.csv"))
    else:
        display(rows)


if __name__ == "__main__":
    main()
