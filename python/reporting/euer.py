#!/usr/bin/env python3
"""
euer.py – Erzeugt eine Anlage-EÜR-strukturierte Aufstellung für ein Jahr
aus den bereinigten Views (vw_guv_report, vw_afa_schedule, vw_ust_report).

Korrekte Behandlung:
- Anlagekonten (SKR03 Klasse 0) NICHT als Vollaufwand, sondern nur AfA (vw_afa_schedule).
- Reverse-Charge (Konto 3xxx): §13b USt auf Ausgangs- UND Eingangsseite (Zahllast-neutral).

Aufruf:  python3 python/reporting/euer.py --year 2024 [--md datei.md]
"""
import sys, os, argparse
from pathlib import Path
import yaml
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection

CONFIG = Path(__file__).resolve().parent.parent.parent / "config" / "business.yaml"


def taxation_mode():
    try:
        return str((yaml.safe_load(CONFIG.read_text()) or {}).get("taxation_mode", "SOLL")).strip().upper()
    except Exception:
        return "SOLL"

# Konto → EÜR-Ausgaben-Kategorie (Anlage EÜR Gruppierung)
KATEGORIEN = [
    ("Raumkosten (Miete, Energie)",          ["4210", "6300"]),
    ("KFZ-Kosten",                            ["4520", "4570"]),
    ("Reisekosten",                           ["4660", "4664"]),
    ("Telefon / Internet",                    ["4905", "4920"]),
    ("Software-Miete / Cloud / SaaS",         ["4909"]),
    ("GWG (Sofortabschreibung)",              ["4806"]),
    ("Betriebsbedarf / Entwicklung",          ["4600", "4900", "3425", "3125"]),
    ("Büromaterial / Werkzeug / Porto",       ["4930", "4980", "4910"]),
    ("Reparatur / Instandhaltung",            ["4855"]),
    ("Arbeitskleidung",                       ["4800"]),
    ("Werbe- / Reisekosten Werbung",          ["6600"]),
    ("Fortbildung / Fachliteratur",           ["4940"]),
    ("Rechts- / Steuerberatung",              ["4954"]),
    ("Versicherungen / Beiträge",             ["4950", "4970", "4975"]),
    ("Nebenkosten Geldverkehr",               ["6855"]),
    ("Zinsen",                                ["7310"]),
]


def fmt(x): return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build(year):
    conn = get_connection(); cur = conn.cursor()
    # Einnahmen
    cur.execute("SELECT COALESCE(SUM(netto_summe),0), COALESCE(SUM(steuer_summe),0) FROM vw_guv_report WHERE direction='outgoing' AND DATE_PART('year',periode)=%s;", (year,))
    ein_net, ein_ust = cur.fetchone()
    # Ausgaben je Konto
    cur.execute("SELECT account_skr, SUM(netto_summe) FROM vw_guv_report WHERE direction='incoming' AND DATE_PART('year',periode)=%s GROUP BY 1;", (year,))
    konto = {r[0]: r[1] for r in cur.fetchall()}
    # AfA
    cur.execute("SELECT COALESCE(SUM(afa_jahr),0) FROM vw_afa_schedule WHERE jahr=%s;", (year,))
    afa = cur.fetchone()[0]
    # USt aus vw_ust_report (maßgebliche Ist/Soll-Basis lt. config/business.yaml:
    # Ausgangs-USt n. Zahlung bei IST, Vorsteuer immer n. Rechnung, §13b/Reverse-Charge beidseitig).
    cur.execute("""SELECT COALESCE(SUM(ust_output),0), COALESCE(SUM(ust_input),0), COALESCE(SUM(zahlbetrag),0)
                   FROM vw_ust_report WHERE DATE_PART('year',periode)=%s;""", (year,))
    ust_output, ust_input, ust_zahllast = cur.fetchone()
    conn.close()

    mode = taxation_mode()
    basis_hinweis = ("Zufluss-/Abfluss-Prinzip — Umsatz/Aufwand nach Zahlungsdatum, Vorsteuer nach Rechnung"
                     if mode == "IST" else "Sollversteuerung — nach Rechnungsdatum")
    anlagen = sum(v for k, v in konto.items() if k.startswith("0"))
    erfasst = set()
    out = [f"# Anlage EÜR {year} – it!consulting kaufmann\n",
           f"_Besteuerungsart: **{mode}** (config/business.yaml) — {basis_hinweis}._\n"]
    out.append("## Betriebseinnahmen\n")
    out.append(f"| Position | Netto |\n|---|--:|")
    out.append(f"| Umsatzsteuerpflichtige Betriebseinnahmen (19 %) | {fmt(ein_net)} |")
    out.append(f"| **Summe Betriebseinnahmen** | **{fmt(ein_net)}** |\n")
    out.append("## Betriebsausgaben\n")
    out.append("| Kategorie | Betrag |\n|---|--:|")
    lfd = 0
    for label, konten in KATEGORIEN:
        s = sum(konto.get(k, 0) for k in konten); erfasst.update(konten)
        if s:
            out.append(f"| {label} | {fmt(s)} |"); lfd += s
    # nicht zugeordnete (außer Anlagen)
    rest = {k: v for k, v in konto.items() if k not in erfasst and not k.startswith("0") and v}
    for k, v in sorted(rest.items()):
        out.append(f"| Konto {k} (n. zugeordnet) | {fmt(v)} |"); lfd += v
    out.append(f"| Abschreibungen (AfA) | {fmt(afa)} |")
    out.append(f"| **Summe Betriebsausgaben** | **{fmt(lfd + afa)}** |\n")
    gewinn = ein_net - lfd - afa
    out.append("## Ergebnis\n")
    out.append(f"| | |\n|---|--:|")
    out.append(f"| Betriebseinnahmen | {fmt(ein_net)} |")
    out.append(f"| − laufende Betriebsausgaben | {fmt(lfd)} |")
    out.append(f"| − AfA | {fmt(afa)} |")
    out.append(f"| **= Gewinn {year}** | **{fmt(gewinn)}** |\n")
    out.append(f"_Hinweis: Anlagezugänge {fmt(anlagen)} € (SKR03 Klasse 0) sind NICHT im laufenden Aufwand, nur via AfA._\n")
    # USt (aus vw_ust_report – maßgebliche Basis lt. Konfiguration)
    out.append("## Umsatzsteuer (zur USt-Jahreserklärung)\n")
    out.append("| Position | Betrag |\n|---|--:|")
    out.append(f"| USt geschuldet (Umsätze 19 % inkl. §13b/Reverse-Charge) | {fmt(ust_output)} |")
    out.append(f"| − Vorsteuer (Rechnungsbasis, inkl. RC) | {fmt(ust_input)} |")
    out.append(f"| **= USt-Zahllast {year}** | **{fmt(ust_zahllast)}** |\n")
    return "\n".join(out), gewinn, ust_zahllast


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--md", help="Markdown-Datei schreiben")
    a = ap.parse_args()
    md, gewinn, zahllast = build(a.year)
    if a.md:
        with open(a.md, "w", encoding="utf-8") as f:
            f.write(md)
        print(f"✅ EÜR-Report geschrieben: {a.md}")
    print(md)
