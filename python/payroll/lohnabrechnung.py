#!/usr/bin/env python3
"""
Lohnabrechnung (zugleich Lohnkonto-Eintrag nach § 41 EStG) als PDF im Firmenlayout.

Eingabe: python/payroll/data/lohn_YYYY_MM.yaml (gitignored, enthält personenbezogene Daten).
Ausgabe: belege/lohn/YYYY/lohnabrechnung_YYYY_MM.pdf

Die Lohnsteuer wird NICHT berechnet, sondern aus dem BMF-Lohnsteuerrechner übernommen.
Für 2026 rechnet das Skript sie zur Kontrolle grob nach (Tarif § 32a EStG, nur
Werbungskosten-/Sonderausgaben-Pauschbetrag und PKV-Vorsorgepauschale, keine RV/AV)
und warnt bei Abweichung — so wäre die fehlende PKV-Vorsorgepauschale im September
2026 aufgefallen (588,50 statt 429,75).

  python3 python/payroll/lohnabrechnung.py --monat 2026-09
  python3 python/payroll/lohnabrechnung.py --monat 2026-09 --status RELEASED
"""
import argparse
import math
import sys
from datetime import date
from decimal import Decimal
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "python" / "reporting"))
from firmenlayout import FIRMA_DECKBLATT, render, tex  # noqa: E402

DATA_DIR = Path(__file__).resolve().parent / "data"


def fmt(x):
    return f"{Decimal(str(x)):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def abzug(x):
    return f"−{fmt(x)}" if x else fmt(0)


def datum_de(s):
    """YYYY-MM-DD → TT.MM.JJJJ, YYYY-MM → MM/JJJJ."""
    s = str(s)
    return f"{date.fromisoformat(s):%d.%m.%Y}" if len(s) == 10 else f"{s[5:7]}/{s[:4]}"


def lade(jahr, monat):
    p = DATA_DIR / f"lohn_{jahr}_{monat:02d}.yaml"
    if not p.is_file():
        sys.exit(f"Keine Lohndaten: {p}")
    return yaml.safe_load(p.read_text(encoding="utf-8"))


def kontroll_lst_2026(brutto_monat, elstam):
    """Grobe Kontrollrechnung Lohnsteuer 2026, StKl I/IV, ohne RV/AV-Anteil."""
    zve = brutto_monat * 12 - 1230 - 36 - (elstam["pkv_kv_vorsorge"] + elstam["pkv_pv_vorsorge"]) * 12
    zve = math.floor(zve)
    if zve <= 12348:
        est = 0
    elif zve <= 17799:
        y = (zve - 12348) / 10000
        est = math.floor((914.51 * y + 1400) * y)
    elif zve <= 69878:
        z = (zve - 17799) / 10000
        est = math.floor((173.10 * z + 2397) * z + 1034.87)
    elif zve <= 277825:
        est = math.floor(0.42 * zve - 11135.63)
    else:
        est = math.floor(0.45 * zve - 19470.38)
    return math.floor(est / 12 * 100) / 100


def main():
    ap = argparse.ArgumentParser(description="Lohnabrechnung als PDF erzeugen")
    ap.add_argument("--monat", required=True, help="YYYY-MM")
    ap.add_argument("--status", default="DRAFT", choices=["DRAFT", "RELEASED"])
    args = ap.parse_args()
    jahr, monat = map(int, args.monat.split("-"))

    d = lade(jahr, monat)
    ag, an, el, sv = d["arbeitgeber"], d["arbeitnehmer"], d["elstam"], d["sozialversicherung"]
    brutto = sum(Decimal(str(b["betrag"])) for b in d["bezuege"])
    ab = {k: Decimal(str(v)) for k, v in d["abzuege"].items()}
    steuern = ab["lohnsteuer"] + ab["soli"] + ab["kirchensteuer"]
    netto = brutto - steuern
    gezahlt = sum(Decimal(str(a["betrag"])) for a in d.get("auszahlungen", []))
    offen = netto - gezahlt

    if jahr == 2026 and el.get("steuerklasse") in ("I", "IV") and not el.get("freibetrag_monat"):
        kontrolle = Decimal(str(kontroll_lst_2026(float(brutto), el)))
        if abs(kontrolle - ab["lohnsteuer"]) > Decimal("1.00"):
            print(f"⚠️  Lohnsteuer {fmt(ab['lohnsteuer'])} weicht von Kontrollrechnung {fmt(kontrolle)} ab "
                  f"– PKV-Vorsorgepauschale im BMF-Rechner geprüft?")

    # Jahreswerte (Lohnkonto) aus allen Monaten bis einschließlich diesem
    kum_brutto = kum_lst = kum_soli = kum_kist = Decimal(0)
    for m in range(1, monat + 1):
        p = DATA_DIR / f"lohn_{jahr}_{m:02d}.yaml"
        if p.is_file():
            x = yaml.safe_load(p.read_text(encoding="utf-8"))
            kum_brutto += sum(Decimal(str(b["betrag"])) for b in x["bezuege"])
            kum_lst += Decimal(str(x["abzuege"]["lohnsteuer"]))
            kum_soli += Decimal(str(x["abzuege"]["soli"]))
            kum_kist += Decimal(str(x["abzuege"]["kirchensteuer"]))

    zeitraum = f"{monat:02d}/{jahr}"
    md = []
    md.append("## Bezüge und Abzüge {.unnumbered}\n")
    md.append("| Lohnart | | Betrag € |")
    md.append("|:--|:--|--:|")
    for b in d["bezuege"]:
        md.append(f"| {tex(b['text'])} | laufend, steuerpflichtig | {fmt(b['betrag'])} |")
    md.append(f"| **Gesamtbrutto** | | **{fmt(brutto)}** |")
    md.append(f"| Steuerbrutto | | {fmt(brutto)} |")
    md.append("| SV-Brutto | versicherungsfrei | 0,00 |")
    md.append(f"| Lohnsteuer | StKl {el['steuerklasse']} | {abzug(ab['lohnsteuer'])} |")
    md.append(f"| Solidaritätszuschlag | | {abzug(ab['soli'])} |")
    md.append(f"| Kirchensteuer | {'–' if not el.get('konfession') else el['konfession']} | {abzug(ab['kirchensteuer'])} |")
    md.append("| Sozialversicherung (KV/RV/AV/PV) | versicherungsfrei | 0,00 |")
    md.append(f"| **Nettobezug** | | **{fmt(netto)}** |")
    md.append("")
    md.append("## Auszahlung {.unnumbered}\n")
    md.append("| Datum | Vorgang | Betrag € |")
    md.append("|:--|:--|--:|")
    for a in d.get("auszahlungen", []):
        md.append(f"| {datum_de(a['datum'])} | {tex(a['text'])} | {fmt(a['betrag'])} |")
    md.append(f"| | **Summe ausgezahlt** | **{fmt(gezahlt)}** |")
    if offen:
        md.append(f"| | **Noch auszuzahlen** | **{fmt(offen)}** |")
    md.append(f"\nÜberweisung auf {tex(an['iban'])}.\n")
    md.append("## Steuer- und SV-Merkmale {.unnumbered}\n")
    md.append("| Merkmal | Wert | Merkmal | Wert |")
    md.append("|:--|:--|:--|:--|")
    md.append(f"| Steuerklasse / Faktor | {el['steuerklasse']} / {el.get('faktor') or '–'} "
              f"| Kinderfreibeträge | {str(el['kinderfreibetraege']).replace('.', ',')} |")
    md.append(f"| Kirchensteuer | {el.get('konfession') or 'keine'} | Freibetrag mtl. | {fmt(el.get('freibetrag_monat', 0))} |")
    md.append(f"| PKV Basis-KV (Vorsorge) | {fmt(el['pkv_kv_vorsorge'])} | PKV PV (Vorsorge) | {fmt(el['pkv_pv_vorsorge'])} |")
    md.append(f"| AG-Zuschuss KV/PV | {fmt(sv['ag_zuschuss_kv_pv'])} | Beitragsgruppe | {sv['beitragsgruppe']} |")
    md.append(f"\nSozialversicherung: {tex(sv['status'])}.")
    if el.get("hinweis"):
        md.append(f" \\mbox{{ELStAM}}: {tex(el['hinweis'])}.")
    md.append("")
    md.append(f"## Lohnkonto {jahr} (kumuliert bis {zeitraum}) {{.unnumbered}}\n")
    md.append("| Steuerbrutto € | Lohnsteuer € | Soli € | Kirchensteuer € |")
    md.append("|--:|--:|--:|--:|")
    md.append(f"| {fmt(kum_brutto)} | {fmt(kum_lst)} | {fmt(kum_soli)} | {fmt(kum_kist)} |")

    ziel = ROOT / "belege" / "lohn" / str(jahr) / f"lohnabrechnung_{jahr}_{monat:02d}.pdf"
    ziel.parent.mkdir(parents=True, exist_ok=True)
    md_datei = ziel.with_suffix(".md")
    md_datei.write_text("\n".join(md) + "\n", encoding="utf-8")

    erstellt = d.get("erstellt") or date.today().isoformat()
    render(md_datei, ziel,
           titel=f"Lohnabrechnung {zeitraum}",
           untertitel=f"{tex(an['name'])} \\textbullet\\ Personal-Nr. {an['personalnummer']} \\textbullet\\ Lohnkonto § 41 EStG",
           deckblatt=[("Arbeitgeber", FIRMA_DECKBLATT, "Arbeitnehmer", f"{tex(an['name'])}\\newline {tex(an['anschrift'])}"),
                      ("Steuernummer", ag["steuernummer"], "Steuer-ID", an["steuer_id"]),
                      ("Finanzamt", tex(ag["finanzamt"]), "Eintritt", datum_de(an["eintritt"])),
                      ("Abrechnungsmonat", zeitraum, "Tätigkeit", tex(an["taetigkeit"])),
                      ("Erstellt", datum_de(erstellt), "Status", args.status)],
           kopfzeile=[f"Lohnabrechnung {zeitraum}", tex(an["name"]), "Vertraulich"],
           status=args.status, verzeichnis=False, eigene_deckblattseite=False)
    print(f"Brutto {fmt(brutto)}  LSt {fmt(ab['lohnsteuer'])}  Netto {fmt(netto)}  "
          f"ausgezahlt {fmt(gezahlt)}  offen {fmt(offen)}")
    print(f"📄 {ziel}")


if __name__ == "__main__":
    main()
