"""
Firmenlayout der ITC Embedded UG für PDF-Berichte.

Setzt Markdown-Inhalt (pandoc) in die Vorlage config/latex/firmenbericht/vorlage.tex
und übersetzt mit latexmk/xelatex. Genutzt von businessplan.py und susa_bwa.py.

Konventionen im Markdown:
  - Überschriften ohne eigene Nummern, LaTeX nummeriert.
  - Jede Section beginnt auf neuer Seite; eine Zeile \\ohneumbruch direkt über
    der Überschrift hängt sie an die vorherige an.
  - \\label{HauptteilEnde} markiert das Seitenende der Zählung "x/Gesamt".
    Fehlt es, wird es ans Ende gesetzt.
  - \\anlagebeginn + Überschrift {.unnumbered .unlisted} für eine entnehmbare Anlage.
"""
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
VORLAGE_DIR = ROOT / "config/latex/firmenbericht"

# Firmierung mit festem Zeilenumbruch für die schmale Deckblattspalte
FIRMA_DECKBLATT = "ITC Embedded UG\\newline (haftungsbeschränkt)"

VERZEICHNIS = r"""{\color{accent}\hrule height 0.4pt}
\vspace{2mm}
{\Large\bfseries\color{accent}Inhalt}
\vspace{-2mm}
\renewcommand{\contentsname}{}
\ohneumbruch   % \tableofcontents setzt intern eine Section, kein Umbruch nach "Inhalt"
\tableofcontents
\newpage"""


def tex(s):
    """Maskiert LaTeX-Sonderzeichen in reinem Text."""
    for a, b in (("\\", "\\textbackslash{}"), ("%", "\\%"), ("&", "\\&"),
                 ("#", "\\#"), ("_", "\\_"), ("$", "\\$")):
        s = s.replace(a, b)
    return s


def infobox(titel, text):
    """Hinweisbox der Firmenvorlage als LaTeX-Rohblock für das Markdown."""
    return f"\\begin{{infobox}}[{tex(titel)}]\n{tex(text)}\n\\end{{infobox}}"


def render(md_datei, pdf_datei, *, titel, untertitel, deckblatt, kopfzeile,
           status="DRAFT", verzeichnis=True, eigene_deckblattseite=True):
    """
    deckblatt: Liste von Zeilen mit je vier Zellen (Bezeichnung, Wert, Bezeichnung, Wert).
               Werte dürfen LaTeX enthalten; reinen Text vorher mit tex() maskieren.
    kopfzeile: Liste kurzer Angaben für die zweite Kopfzeile, mit Punkten verbunden.
    eigene_deckblattseite: False setzt den Titelblock oben auf die erste Inhaltsseite
               (für einseitige Dokumente wie die Lohnabrechnung).
    """
    md_datei, pdf_datei = Path(md_datei), Path(pdf_datei)
    build = pdf_datei.parent / f"build_{pdf_datei.stem}"
    build.mkdir(parents=True, exist_ok=True)

    inhalt = subprocess.run(["pandoc", str(md_datei), "-f", "markdown", "-t", "latex"],
                            check=True, capture_output=True, text=True).stdout
    if "\\label{HauptteilEnde}" not in inhalt:
        inhalt += "\n\\label{HauptteilEnde}\n"

    werte = {
        "<<TITEL>>": titel,
        "<<UNTERTITEL>>": untertitel,
        "<<STATUS>>": status,
        "<<KOPFZEILE>>": "\\ \\textbullet\\ ".join(kopfzeile),
        "<<DECKBLATT>>": "\n".join("      " + " & ".join(z) + " \\\\" for z in deckblatt),
        "<<VERZEICHNIS>>": VERZEICHNIS if verzeichnis else "",
    }
    doc = (VORLAGE_DIR / "vorlage.tex").read_text(encoding="utf-8")
    for k, v in werte.items():
        doc = doc.replace(k, v)
    if not eigene_deckblattseite:
        deckblattseite = "\\vspace*{\\stretch{1}}\n\\titleblock\n\\vspace*{\\stretch{2}}\n\\newpage"
        assert deckblattseite in doc, "Deckblatt-Block in vorlage.tex geändert"
        doc = doc.replace(deckblattseite, "\\titleblock\n\\ohneumbruch")
    doc = doc.replace("<<INHALT>>", inhalt)   # zuletzt: Inhalt kann "<<" enthalten

    (build / "bericht.tex").write_text(doc, encoding="utf-8")
    logo = VORLAGE_DIR / "itc-embedded_logo_transparent.pdf"
    (build / logo.name).write_bytes(logo.read_bytes())

    r = subprocess.run(["latexmk", "-xelatex", "-interaction=nonstopmode", "-halt-on-error", "bericht.tex"],
                       cwd=build, capture_output=True, text=True)
    if r.returncode != 0:
        sys.exit(f"LaTeX-Fehler, siehe {build / 'bericht.log'}\n" + r.stdout[-2000:])
    pdf_datei.write_bytes((build / "bericht.pdf").read_bytes())
