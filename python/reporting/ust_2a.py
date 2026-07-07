#!/usr/bin/env python3
"""
ust_2a.py – Ausfüllhilfe für die Umsatzsteuer-Jahreserklärung (Vordruck USt 2 A)

Erzeugt aus den bereinigten Buchungszeilen (vw_booking_lines_effective) eine nach
den amtlichen Kennziffern des Vordrucks USt 2 A gegliederte Aufstellung für ein Jahr.

Die Zahllast-Logik ist IDENTISCH zur maßgeblichen View vw_ust_report:
  - Periodenzuordnung Ausgangsumsätze nach Zahlungsdatum (IST), sonst Belegdatum
  - Vorsteuer immer nach Belegdatum (Rechnung)
  - geschuldete USt = Ausgangs-USt + USt aus Eingangsleistungen auf Konten 3xxx
    (innergem. Erwerbe / §13b) – zahllastneutral, da zugleich als Vorsteuer abziehbar
Der Steuersatz wird robust aus tax_amount/net_amount abgeleitet, weil tax_type in
den Altdaten nicht gepflegt ist (NULL) und tax_rate uneinheitlich gespeichert wurde.

Abschnitt F rechnet die geleisteten Vorauszahlungen an (USt-Vorauszahlungen der
Voranmeldungszeiträume PLUS Sondervorauszahlung Kz 39, wie von ELSTER abgefragt) und
weist die verbleibende Abschlusszahlung bzw. den Erstattungsanspruch aus. Die
Vorauszahlungen werden aus den Bank-Transaktionen nach VORANMELDUNGSZEITRAUM erkannt
(z. B. "USt. VZ. 2024-12", auch wenn erst 2025 gezahlt) und können per
--vorauszahlungen / --sondervorauszahlung überschrieben werden.

Aufruf:  python3 python/reporting/ust_2a.py --year 2024 [--md datei.md]
         [--vorauszahlungen 22789.93] [--sondervorauszahlung 1314]
"""
import sys
import os
import re
import argparse
from decimal import Decimal
from pathlib import Path

import yaml

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from db import get_connection

CONFIG = Path(__file__).resolve().parent.parent.parent / "config" / "business.yaml"

# SKR03: Kontenpräfixe der Konten für §13b-Leistungsempfänger (Reverse Charge
# sonstige Leistung EU). Alle übrigen 3xxx-Konten mit Steuer werden als
# innergemeinschaftlicher Erwerb behandelt (z. B. 3425 = ig. Erwerb 19 %).
RC_13B_PREFIXES = ("355", "357")

# Erkennung geleisteter USt-Vorauszahlungen aus dem Verwendungszweck der
# Bank-Transaktionen (nur Zahlungen ans Finanzamt). Zuordnung nach
# VORANMELDUNGSZEITRAUM (z. B. "USt. VZ. 2024-12" gehört zu 2024, auch wenn erst
# im Februar 2025 gezahlt). Säumniszuschläge ("VZ. SZ." / "USt. SZ.") werden
# ausgeschlossen. Zwei Zeitraum-Schreibweisen: Jahr-zuerst ("2024-Q1", "2024-04")
# und Quartal-zuerst ("Q4/2023", "Q4 2023").
VZ_PERIOD_YM = re.compile(r"VZ\.\s*(\d{4})-(Q?\d{1,2})", re.I)
VZ_PERIOD_QY = re.compile(r"VZ\.\s*(Q\d)[ /](\d{4})", re.I)
VZ_PENALTY = re.compile(r"\bSZ\b", re.I)  # Säumniszuschlag – nie als Vorauszahlung zählen
SVZ_YEAR = re.compile(r"SVZ\.\s*(\d{4})", re.I)


def parse_vz_period(purpose):
    """(jahr, label) des Voranmeldungszeitraums aus dem Verwendungszweck, sonst None."""
    m = VZ_PERIOD_YM.search(purpose)
    if m:
        return int(m.group(1)), m.group(2)
    m = VZ_PERIOD_QY.search(purpose)
    if m:
        return int(m.group(2)), m.group(1)
    return None


def taxation_mode():
    try:
        return str((yaml.safe_load(CONFIG.read_text()) or {}).get("taxation_mode", "SOLL")).strip().upper()
    except Exception:
        return "SOLL"


def fmt(x):
    return f"{x or 0:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def fetch_vorauszahlungen(year):
    """Geleistete USt-Vorauszahlungen (UStVA) für die Voranmeldungszeiträume des
    Jahres aus den Bank-Transaktionen. Rückgabe: (items, summe, unparsed, svz).
      items    – Liste (zeitraum, zahldatum, betrag) der erkannten Vorauszahlungen
      summe    – Summe der angerechneten Vorauszahlungen (positiv)
      unparsed – nicht zuordenbare 'USt VZ'-Zeilen (zur manuellen Kontrolle)
      svz      – Sondervorauszahlung des Jahres (positiv) oder 0
    """
    conn = get_connection()
    cur = conn.cursor()
    # nur Zahlungen ans Finanzamt (interne Umbuchungen mit gleichem Zweck ausschließen)
    cur.execute(
        "SELECT booking_date, amount, purpose FROM transactions "
        "WHERE purpose ILIKE %s AND counterpart_name ILIKE %s ORDER BY booking_date",
        ("%USt%VZ.%", "%finanzamt%"),
    )
    vz_rows = cur.fetchall()
    cur.execute(
        "SELECT amount, purpose FROM transactions "
        "WHERE purpose ILIKE %s AND counterpart_name ILIKE %s",
        ("%SVZ.%", "%finanzamt%"),
    )
    svz_rows = cur.fetchall()
    conn.close()

    items, summe, unparsed = [], Decimal("0"), []
    for d, amount, purpose in vz_rows:
        if VZ_PENALTY.search(purpose) or "svz" in purpose.lower():
            continue  # Säumniszuschläge und Sondervorauszahlungen separat behandelt
        parsed = parse_vz_period(purpose)
        if parsed is None:
            # nur als Warnung führen, wenn die Zeile plausibel zum Berichtsjahr gehört
            if str(year) in purpose:
                unparsed.append((d, amount, purpose))
            continue
        pjahr, label = parsed
        if pjahr == year:
            betrag = -Decimal(str(amount))  # Zahlung ist negativ -> Anrechnung positiv
            items.append((label, d, betrag))
            summe += betrag

    svz = Decimal("0")
    for amount, purpose in svz_rows:
        if VZ_PENALTY.search(purpose):
            continue
        m = SVZ_YEAR.search(purpose)
        if m and int(m.group(1)) == year and amount < 0:
            svz += -Decimal(str(amount))

    return items, summe, unparsed, svz


def fetch_svz_refund(year):
    """Bereits erfolgte USt-Erstattung für den Dezember des Berichtsjahres (über den
    typischerweise die Sondervorauszahlung der Dauerfristverlängerung zurückfließt).
    Rückgabe: (summe, items) — summe positiv, items = Liste (datum, betrag, zweck).
    """
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        "SELECT booking_date, amount, purpose FROM transactions "
        "WHERE amount > 0 AND purpose ILIKE %s AND purpose ILIKE %s ORDER BY booking_date",
        ("%ERSTATT%", "%UMS%ST%"),
    )
    rows = cur.fetchall()
    conn.close()
    # Dezember-Erstattung des Berichtsjahres erkennen: "DEZ.24" (2-stellig) oder "DEZ 2024"
    dez = re.compile(rf"DEZ\.?\s*(?:0?{year % 100:d}|{year})\b", re.I)
    total, items = Decimal("0"), []
    for d, amount, purpose in rows:
        if dez.search(purpose):
            total += Decimal(str(amount))
            items.append((d, Decimal(str(amount)), purpose))
    return total, items


def rate_bucket(net, tax):
    """Steuersatz robust aus Betrag ableiten -> 19 / 7 / 0."""
    if not net:
        return 0
    pct = round(float(tax) / float(net) * 100)
    if pct >= 16:
        return 19
    if pct >= 5:
        return 7
    return 0


def fetch_lines(year):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute(
        """
        SELECT bl.direction, bl.account_skr, bl.net_amount, bl.tax_amount,
               CASE WHEN bl.direction = 'outgoing'
                    THEN COALESCE(bl.zahlung_datum, bl.beleg_datum)
                    ELSE bl.beleg_datum END AS wirksam_datum
          FROM vw_booking_lines_effective bl
         WHERE COALESCE(bl.status, 'draft') NOT IN ('draft', 'cancelled')
        """
    )
    rows = cur.fetchall()
    conn.close()
    out = []
    for r in rows:
        d = r["wirksam_datum"] if isinstance(r, dict) else r[4]
        if d is None or d.year != year:
            continue
        out.append(r if isinstance(r, dict) else {
            "direction": r[0], "account_skr": r[1],
            "net_amount": r[2], "tax_amount": r[3], "wirksam_datum": r[4],
        })
    return out


def build(year, vorauszahlungen=None, sondervorauszahlung=None):
    """Erzeugt den USt-2A-Report. vorauszahlungen/sondervorauszahlung überschreiben
    bei Bedarf die automatisch aus den Bank-Transaktionen erkannten Beträge
    (Decimal/float/None)."""
    rows = fetch_lines(year)

    # Sammel-Buckets
    umsatz = {19: [0, 0], 7: [0, 0], 0: [0, 0]}     # steuerpfl. Ausgangsumsätze [BMG, USt]
    ig_erwerb = {19: [0, 0], 7: [0, 0]}             # innergem. Erwerbe [BMG, USt]
    rc13b = {19: [0, 0], 7: [0, 0]}                 # §13b Leistungsempfänger [BMG, USt]
    vst_regulaer = [0]                              # Kz 320
    vst_ig = [0]                                    # Kz 461
    vst_13b = [0]                                   # Kz 467
    eingang_ohne_ust = [0]                          # nachrichtlich (0 % Eingang)
    dreier_konten = {}                              # account -> [BMG, Steuer] (Datenqualitäts-Flag)

    for r in rows:
        direction = r["direction"]
        acct = (r["account_skr"] or "")
        net = r["net_amount"] or 0
        tax = r["tax_amount"] or 0
        satz = rate_bucket(net, tax)

        if direction == "outgoing":
            umsatz.setdefault(satz, [0, 0])
            umsatz[satz][0] += net
            umsatz[satz][1] += tax
            continue

        # incoming
        if acct.startswith("3"):
            # innergem. Erwerb bzw. §13b: USt wird selbst geschuldet UND als VSt abgezogen
            dreier_konten.setdefault(acct, [0, 0])
            dreier_konten[acct][0] += net
            dreier_konten[acct][1] += tax
            if any(acct.startswith(p) for p in RC_13B_PREFIXES):
                rc13b.setdefault(satz, [0, 0])
                rc13b[satz][0] += net
                rc13b[satz][1] += tax
                vst_13b[0] += tax
            else:
                ig_erwerb.setdefault(satz, [0, 0])
                ig_erwerb[satz][0] += net
                ig_erwerb[satz][1] += tax
                vst_ig[0] += tax
        else:
            # reguläre Vorsteuer aus Eingangsrechnungen
            if tax:
                vst_regulaer[0] += tax
            else:
                eingang_ohne_ust[0] += net

    ust_geschuldet = (sum(v[1] for v in umsatz.values())
                      + sum(v[1] for v in ig_erwerb.values())
                      + sum(v[1] for v in rc13b.values()))
    vst_gesamt = vst_regulaer[0] + vst_ig[0] + vst_13b[0]
    zahllast = ust_geschuldet - vst_gesamt

    mode = taxation_mode()
    basis_hinweis = ("Ist-Versteuerung — Ausgangsumsätze nach Zahlungseingang, Vorsteuer nach Rechnung"
                     if mode == "IST" else "Soll-Versteuerung — nach Rechnungsdatum")

    o = []
    o.append(f"# Umsatzsteuer-Jahreserklärung {year} – Ausfüllhilfe Vordruck USt 2 A\n")
    o.append("_it!consulting kaufmann_\n")
    o.append(f"_Besteuerungsart: **{mode}** (config/business.yaml) — {basis_hinweis}._\n")
    o.append("_Die Kennziffern (Kz) dienen als Orientierung; bitte im ELSTER-Formular des "
             "jeweiligen Jahres gegenprüfen._\n")

    o.append("## A. Steuerpflichtige Lieferungen und sonstige Leistungen\n")
    o.append("| Position | Kz (Bemessungsgrundlage) | Bemessungsgrundlage | Umsatzsteuer |")
    o.append("|---|---|--:|--:|")
    o.append(f"| Umsätze zum Steuersatz 19 % | 177 | {fmt(umsatz[19][0])} | {fmt(umsatz[19][1])} |")
    o.append(f"| Umsätze zum Steuersatz 7 % | 275 | {fmt(umsatz[7][0])} | {fmt(umsatz[7][1])} |")
    if umsatz[0][0]:
        o.append(f"| Umsätze 0 % / steuerfrei (Art prüfen: Kz 205 / §4 UStG) | – | {fmt(umsatz[0][0])} | {fmt(umsatz[0][1])} |")

    ig_total = sum(v[1] for v in ig_erwerb.values())
    if any(v[0] for v in ig_erwerb.values()):
        o.append("\n## B. Innergemeinschaftliche Erwerbe\n")
        o.append("| Position | Kz (BMG) | Kz (Steuer) | Bemessungsgrundlage | Umsatzsteuer |")
        o.append("|---|---|---|--:|--:|")
        o.append(f"| ig. Erwerbe zum Steuersatz 19 % | 761 | 764 | {fmt(ig_erwerb[19][0])} | {fmt(ig_erwerb[19][1])} |")
        if ig_erwerb[7][0]:
            o.append(f"| ig. Erwerbe zum Steuersatz 7 % | 760 | 763 | {fmt(ig_erwerb[7][0])} | {fmt(ig_erwerb[7][1])} |")

    if any(v[0] for v in rc13b.values()):
        o.append("\n## C. Leistungen, für die der Leistungsempfänger die Steuer schuldet (§ 13b UStG)\n")
        o.append("| Position | Kz (BMG) | Kz (Steuer) | Bemessungsgrundlage | Umsatzsteuer |")
        o.append("|---|---|---|--:|--:|")
        o.append(f"| § 13b Leistungen (EU: Kz 846/847, sonst prüfen) | 846 | 847 | {fmt(rc13b[19][0])} | {fmt(rc13b[19][1])} |")

    o.append("\n## D. Abziehbare Vorsteuerbeträge\n")
    o.append("| Position | Kz | Betrag |")
    o.append("|---|---|--:|")
    o.append(f"| Vorsteuer aus Rechnungen anderer Unternehmer (§ 15 Abs. 1 Nr. 1) | 320 | {fmt(vst_regulaer[0])} |")
    if vst_ig[0]:
        o.append(f"| Vorsteuer aus innergemeinschaftlichen Erwerben | 461 | {fmt(vst_ig[0])} |")
    if vst_13b[0]:
        o.append(f"| Vorsteuer aus Leistungen i. S. d. § 13b (§ 15 Abs. 1 Nr. 4) | 467 | {fmt(vst_13b[0])} |")
    o.append(f"| **Summe abziehbare Vorsteuer** | | **{fmt(vst_gesamt)}** |")

    o.append("\n## E. Berechnung der zu entrichtenden Umsatzsteuer\n")
    o.append("| Position | Betrag |")
    o.append("|---|--:|")
    o.append(f"| Umsatzsteuer aus steuerpflichtigen Umsätzen | {fmt(sum(v[1] for v in umsatz.values()))} |")
    if ig_total:
        o.append(f"| + Umsatzsteuer aus innergemeinschaftlichen Erwerben | {fmt(ig_total)} |")
    rc_total = sum(v[1] for v in rc13b.values())
    if rc_total:
        o.append(f"| + Umsatzsteuer aus § 13b-Leistungen | {fmt(rc_total)} |")
    o.append(f"| **= Umsatzsteuer gesamt** | **{fmt(ust_geschuldet)}** |")
    o.append(f"| − abziehbare Vorsteuer | {fmt(vst_gesamt)} |")
    o.append(f"| **= verbleibende Umsatzsteuer / Zahllast {year}** | **{fmt(zahllast)}** |")

    # F) Anrechnung geleisteter Vorauszahlungen inkl. Sondervorauszahlung (Kz 39),
    #    wie von ELSTER abgefragt -> Abschlusszahlung/Erstattung
    vz_items, vz_auto, vz_unparsed, svz_auto = fetch_vorauszahlungen(year)
    vz_summe = Decimal(str(vorauszahlungen)) if vorauszahlungen is not None else vz_auto
    svz = Decimal(str(sondervorauszahlung)) if sondervorauszahlung is not None else svz_auto
    anrechnung = vz_summe + svz
    abschluss = Decimal(str(zahllast)) - anrechnung
    o.append("\n## F. Anrechnung geleisteter Vorauszahlungen\n")
    o.append("| Position | Betrag |")
    o.append("|---|--:|")
    o.append(f"| verbleibende Umsatzsteuer (Zahllast) | {fmt(zahllast)} |")
    q_vz = " (manuell)" if vorauszahlungen is not None else ""
    o.append(f"| USt-Vorauszahlungen (Voranmeldungszeiträume){q_vz} | {fmt(vz_summe)} |")
    if svz:
        q_svz = " (manuell)" if sondervorauszahlung is not None else ""
        o.append(f"| Sondervorauszahlung (Dauerfristverlängerung, Kz 39){q_svz} | {fmt(svz)} |")
        o.append(f"| Summe angerechnete Vorauszahlungen | {fmt(anrechnung)} |")
    if abschluss >= 0:
        o.append(f"| **= verbleibende Abschlusszahlung {year}** | **{fmt(abschluss)}** |")
    else:
        o.append(f"| **= Erstattungsanspruch {year}** | **{fmt(-abschluss)}** |")

    # Kontrollzeile: bereits über die Dezember-UStVA erfolgte SVZ-Erstattung, damit der
    # SVZ-Anteil der obigen Erstattung nicht doppelt erwartet wird.
    if svz:
        refund_sum, refund_items = fetch_svz_refund(year)
        if refund_sum:
            rdate = refund_items[0][0]
            o.append("")
            o.append(f"_**Kontrolle SVZ:** {fmt(refund_sum)} € wurden am {rdate} bereits über "
                     f"die Dezember-UStVA erstattet (SVZ-Rückfluss). Der SVZ-Anteil der obigen "
                     f"Anrechnung ist damit schon geflossen._")
            if abschluss < 0:
                o.append(f"_→ effektiv noch offener Erstattungsbetrag ≈ {fmt(-abschluss)} − "
                         f"{fmt(refund_sum)} = **{fmt(-abschluss - refund_sum)} €**._")
            if refund_sum != svz:
                o.append(f"_⚠️ Erkannte Dez-Erstattung ({fmt(refund_sum)} €) ≠ Sondervorauszahlung "
                         f"({fmt(svz)} €) — bitte Zuordnung prüfen._")

    # Nachrichtlich & Datenqualität
    o.append("\n## Nachrichtlich / Hinweise\n")
    if eingang_ohne_ust[0]:
        o.append(f"- Eingangsleistungen ohne Vorsteuer (0 %/steuerfrei), nachrichtlich: **{fmt(eingang_ohne_ust[0])} €** netto — nicht USt-relevant.")
    if dreier_konten:
        konten = ", ".join(f"{k} ({fmt(v[0])} € BMG)" for k, v in sorted(dreier_konten.items()))
        o.append(f"- Konten mit Erwerbs-/§13b-Buchung (Klassifizierung im Formular prüfen): {konten}.")
    if vorauszahlungen is None and vz_items:
        detail = ", ".join(f"{per} {fmt(b)}" for per, _d, b in vz_items)
        o.append(f"- Angerechnete Vorauszahlungen ({len(vz_items)}, Zuordnung nach Voranmeldungszeitraum): {detail}.")
    if svz:
        o.append(f"- Sondervorauszahlung {year} ({fmt(svz)} €, Dauerfristverlängerung) ist in Abschnitt F angerechnet — ELSTER fragt die Vorauszahlungen inkl. SVZ ab (Kz 39).")
    if vorauszahlungen is None and not vz_items:
        o.append("- ⚠️ Keine USt-Vorauszahlungen automatisch erkannt — ggf. per `--vorauszahlungen BETRAG` vorgeben.")
    if vz_unparsed:
        o.append(f"- ⚠️ {len(vz_unparsed)} 'USt-VZ'-Buchung(en) ohne erkennbaren Zeitraum (nicht angerechnet) — Verwendungszweck prüfen.")
    o.append("- Zahllast und Summen sind deckungsgleich mit `vw_ust_report` (maßgebliche Basis lt. config/business.yaml).")

    return "\n".join(o), zahllast


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="USt-2A-Ausfüllhilfe für ein Jahr")
    ap.add_argument("--year", type=int, required=True)
    ap.add_argument("--md", help="Markdown-Datei schreiben")
    ap.add_argument("--vorauszahlungen", type=float,
                    help="geleistete USt-Vorauszahlungen manuell vorgeben (überschreibt Auto-Erkennung)")
    ap.add_argument("--sondervorauszahlung", type=float,
                    help="Sondervorauszahlung (Dauerfristverlängerung, Kz 39) manuell vorgeben")
    a = ap.parse_args()
    md, zahllast = build(a.year, vorauszahlungen=a.vorauszahlungen,
                         sondervorauszahlung=a.sondervorauszahlung)
    if a.md:
        Path(a.md).write_text(md, encoding="utf-8")
        print(f"✅ USt-2A-Report geschrieben: {a.md}")
    print(md)
