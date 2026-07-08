#!/usr/bin/env python3
"""
gewst.py – Ausfüllhilfe für die Gewerbesteuererklärung (Vordruck GewSt 1 A)

Ermittelt aus dem EÜR-Gewinn den Gewerbeertrag, den Steuermessbetrag und – mit dem
Gemeinde-Hebesatz aus config/business.yaml – die Gewerbesteuer für ein Jahr.

Rechenweg (natürliche Person / Einzelunternehmen):
  Gewinn aus Gewerbebetrieb (EÜR)
  + Hinzurechnungen § 8 GewStG (Finanzierungsanteile § 8 Nr. 1, Saldo über 200.000 €)
  − Kürzungen § 9 GewStG
  = Gewerbeertrag  → abgerundet auf volle 100 € (§ 11 Abs. 1 S. 3)
  − Freibetrag 24.500 € (§ 11 Abs. 1 Nr. 1)
  × Steuermesszahl 3,5 % (§ 11 Abs. 2)          = Steuermessbetrag
  × Hebesatz der Gemeinde                        = Gewerbesteuer

Der Gewinn wird aus euer.build() gezogen (eine gemeinsame Quelle mit der EÜR). Die
Hinzurechnungen werden aus den Aufwandskonten (vw_guv_report) abgeleitet und sind
per --hinzurechnung / --kuerzung / --hebesatz überschreibbar.

Aufruf:  python3 python/reporting/gewst.py --year 2024 [--md datei.md]
"""
import sys
import os
import argparse
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection
from reporting import euer

CONFIG = Path(__file__).resolve().parent.parent.parent / "config" / "business.yaml"

# Gesetzliche Konstanten
FREIBETRAG = Decimal("24500")          # § 11 Abs. 1 Nr. 1 (natürl. Personen / PersGes)
MESSZAHL = Decimal("0.035")            # § 11 Abs. 2
FREIBETRAG_8_1 = Decimal("200000")     # § 8 Nr. 1 (Finanzierungsanteile)
FAKTOR_35 = Decimal("4.0")             # § 35 EStG: 4-facher Messbetrag anrechenbar

# § 8 Nr. 1 Finanzierungsanteile: (Label, [SKR03-Konten], Anteil, Buchstabe)
# Anteil lt. Gesetz: a) Zinsen 100 %, d) bewegl. Miete/Leasing 20 %, e) unbewegl.
# Miete/Pacht 50 %, f) Lizenzen 25 %. Kontenzuordnung an die Nutzung im Betrieb
# angelehnt (vgl. euer.py) – bei neuen Konten hier ergänzen.
HINZURECHNUNG_8_1 = [
    ("Entgelte für Schulden (Zinsen)",        ["7310"], Decimal("1.00"), "a"),
    ("Miete/Pacht unbewegliche WG (Räume)",   ["4210"], Decimal("0.50"), "e"),
    ("Miete/Leasing bewegliche WG (Kfz)",     ["4570"], Decimal("0.20"), "d"),
]


def _cfg():
    try:
        return yaml.safe_load(CONFIG.read_text()) or {}
    except Exception:
        return {}


def gewst_cfg():
    return (_cfg().get("gewerbesteuer") or {})


def fmt(x):
    return f"{x or 0:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fetch_konto_summen(year):
    """Netto-Aufwand je Konto (incoming) aus vw_guv_report für das Jahr."""
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT account_skr, SUM(netto_summe) FROM vw_guv_report "
        "WHERE direction='incoming' AND DATE_PART('year', periode)=%s GROUP BY 1",
        (year,),
    )
    rows = cur.fetchall()
    conn.close()
    return {r[0]: Decimal(str(r[1] or 0)) for r in rows}


def build(year, hinzurechnung=None, kuerzung=None, hebesatz=None):
    """Erzeugt den GewSt-Report. hinzurechnung/kuerzung/hebesatz überschreiben bei
    Bedarf die automatisch ermittelten Werte (Decimal/float/None)."""
    _md, gewinn, _ust = euer.build(year)
    gewinn = Decimal(str(gewinn))
    konto = fetch_konto_summen(year)

    # § 8 Nr. 1 – Finanzierungsanteile
    komponenten, fin_summe = [], Decimal("0")
    for label, konten, anteil, bst in HINZURECHNUNG_8_1:
        basis = sum((konto.get(k, Decimal("0")) for k in konten), Decimal("0"))
        anteilbetrag = (basis * anteil).quantize(Decimal("0.01"), ROUND_HALF_UP)
        fin_summe += anteilbetrag
        komponenten.append((label, bst, basis, anteil, anteilbetrag))
    hinzu_8_1 = max(Decimal("0"), fin_summe - FREIBETRAG_8_1) * Decimal("0.25")
    hinzu = Decimal(str(hinzurechnung)) if hinzurechnung is not None else hinzu_8_1
    kuerz = Decimal(str(kuerzung)) if kuerzung is not None else Decimal("0")

    gewerbeertrag = gewinn + hinzu - kuerz
    # § 11 Abs. 1 S. 3: auf volle 100 € abrunden
    ertrag_ab = (gewerbeertrag // 100) * 100
    bemessung = max(Decimal("0"), ertrag_ab - FREIBETRAG)
    messbetrag = (bemessung * MESSZAHL).quantize(Decimal("0.01"), ROUND_HALF_UP)

    hs = Decimal(str(hebesatz)) if hebesatz is not None else Decimal(str(gewst_cfg().get("hebesatz", 380)))
    gewst = (messbetrag * hs / 100).quantize(Decimal("0.01"), ROUND_HALF_UP)
    gemeinde = gewst_cfg().get("gemeinde", "—")
    anrechnung_35 = min((messbetrag * FAKTOR_35).quantize(Decimal("0.01")), gewst)

    o = []
    o.append(f"# Gewerbesteuer {year} – Ausfüllhilfe (GewSt 1 A / Steuermessbetrag)\n")
    o.append("_it!consulting kaufmann — Einzelunternehmen (natürliche Person)_\n")
    o.append(f"_Gewinn aus EÜR (config/business.yaml: {_cfg().get('taxation_mode','SOLL')}-Versteuerung); "
             f"Hebesatz {fmt(hs)} % (Gemeinde {gemeinde})._\n")

    o.append("## A. Gewerbeertrag\n")
    o.append("| Position | Betrag |")
    o.append("|---|--:|")
    o.append(f"| Gewinn aus Gewerbebetrieb (EÜR) | {fmt(gewinn)} |")
    o.append(f"| + Hinzurechnungen (§ 8 GewStG) | {fmt(hinzu)} |")
    o.append(f"| − Kürzungen (§ 9 GewStG) | {fmt(kuerz)} |")
    o.append(f"| **= Gewerbeertrag** | **{fmt(gewerbeertrag)}** |")
    o.append(f"| abgerundet auf volle 100 € (§ 11 Abs. 1) | {fmt(ertrag_ab)} |")

    o.append("\n## B. Hinzurechnungen § 8 Nr. 1 (Finanzierungsanteile)\n")
    o.append("| Bestandteil | § 8 Nr. 1 | Aufwand | Anteil | anrechenbar |")
    o.append("|---|---|--:|--:|--:|")
    for label, bst, basis, anteil, anteilbetrag in komponenten:
        o.append(f"| {label} | {bst} | {fmt(basis)} | {int(anteil*100)} % | {fmt(anteilbetrag)} |")
    o.append(f"| **Summe Finanzierungsanteile** | | | | **{fmt(fin_summe)}** |")
    o.append(f"| − Freibetrag § 8 Nr. 1 | | | | {fmt(FREIBETRAG_8_1)} |")
    o.append(f"| **= Hinzurechnung (25 % des übersteigenden Betrags)** | | | | **{fmt(hinzu_8_1)}** |")

    o.append("\n## C. Steuermessbetrag\n")
    o.append("| Position | Betrag |")
    o.append("|---|--:|")
    o.append(f"| Gewerbeertrag (abgerundet) | {fmt(ertrag_ab)} |")
    o.append(f"| − Freibetrag (§ 11 Abs. 1 Nr. 1) | {fmt(FREIBETRAG)} |")
    o.append(f"| = verbleibender Betrag | {fmt(bemessung)} |")
    o.append(f"| × Steuermesszahl 3,5 % (§ 11 Abs. 2) | |")
    o.append(f"| **= Steuermessbetrag** | **{fmt(messbetrag)}** |")

    o.append("\n## D. Gewerbesteuer\n")
    o.append("| Position | Betrag |")
    o.append("|---|--:|")
    o.append(f"| Steuermessbetrag | {fmt(messbetrag)} |")
    o.append(f"| × Hebesatz {gemeinde} {fmt(hs)} % | |")
    o.append(f"| **= Gewerbesteuer {year}** | **{fmt(gewst)}** |")

    o.append("\n## Nachrichtlich / Hinweise\n")
    o.append(f"- **§ 35 EStG:** Auf die Einkommensteuer anrechenbar ist das {fmt(FAKTOR_35)}-fache des "
             f"Messbetrags = {fmt(messbetrag * FAKTOR_35)} €, begrenzt auf die tatsächliche "
             f"Gewerbesteuer → anrechenbar **{fmt(anrechnung_35)} €** (im ESt-Schritt zu berücksichtigen).")
    if hinzu_8_1 == 0:
        o.append(f"- Keine Hinzurechnung: Finanzierungsanteile {fmt(fin_summe)} € liegen unter dem "
                 f"Freibetrag von 200.000 € (§ 8 Nr. 1).")
    o.append("- Kürzungen § 9 (z. B. 1,2 % Einheitswert Grundbesitz) = 0 — kein Betriebsgrundbesitz.")
    o.append("- Gewerbesteuer-Vorauszahlungen werden über den GewSt-Bescheid der Gemeinde verrechnet "
             "(nicht Teil dieser Erklärung).")
    o.append("- Kontenzuordnung der Finanzierungsanteile (§ 8 Nr. 1) im Zweifel prüfen.")

    return "\n".join(o), messbetrag, gewst


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Gewerbesteuer-Ausfüllhilfe für ein Jahr")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--md", help="Markdown-Datei schreiben")
    ap.add_argument("--hinzurechnung", type=float, help="Hinzurechnungen § 8 manuell vorgeben")
    ap.add_argument("--kuerzung", type=float, help="Kürzungen § 9 manuell vorgeben")
    ap.add_argument("--hebesatz", type=float, help="Hebesatz in %% manuell vorgeben")
    a = ap.parse_args()
    md, messbetrag, gewst = build(a.year, hinzurechnung=a.hinzurechnung,
                                  kuerzung=a.kuerzung, hebesatz=a.hebesatz)
    if a.md:
        Path(a.md).write_text(md, encoding="utf-8")
        print(f"✅ GewSt-Report geschrieben: {a.md}")
    print(md)
