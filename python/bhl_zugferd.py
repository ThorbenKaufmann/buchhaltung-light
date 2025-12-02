#!/usr/bin/env python3
"""
bhl_zugferd.py
Erkennung und Auslesen von ZugFeRD / Factur-X / XRechnung aus PDF-Dateien.

Unterstützt:
  • PDF/A-3 Container mit eingebetteter XML-Datei (pikepdf)
  • Inline-XML im Textstrom (pdfminer.six)

Abhängigkeiten:
  pip install pikepdf lxml pdfminer.six
"""

import os
import re
import pikepdf
from lxml import etree
from pdfminer.high_level import extract_text

# ------------------------------------------------------------
# Sanitize für fehlerhafte XMLs (z. B. OrgaMax &nbsp;)
# ------------------------------------------------------------
def sanitize_xml(text: str) -> str:
    """Ersetzt bekannte ungültige Entities wie &nbsp;"""
    replacements = {
        "&nbsp;": " ",
        "&nbsp": " ",
        "&ampnbsp;": " ",
        "&amp;nbsp": " ",
    }
    for bad, good in replacements.items():
        text = text.replace(bad, good)
    return text


# ------------------------------------------------------------
# 1. XML aus eingebetteten Anhängen (PDF/A-3)
# ------------------------------------------------------------
def extract_embedded_xml(pdf_path: str):
    """Extrahiert eingebettete XML-Dateien (ZugFeRD / Factur-X) aus PDF."""
    try:
        with pikepdf.open(pdf_path) as pdf:
            for name, file_spec in pdf.attachments.items():
                if not name.lower().endswith(".xml"):
                    continue
                try:
                    if hasattr(file_spec, "read_bytes"):
                        data = file_spec.read_bytes()
                        return data.decode("utf-8", errors="ignore"), name

                    if hasattr(file_spec, "open"):
                        with file_spec.open("rb") as f:
                            data = f.read()
                            return data.decode("utf-8", errors="ignore"), name

                    ef = getattr(file_spec, "embedded_file", None)
                    if ef and hasattr(ef, "read_bytes"):
                        data = ef.read_bytes()
                        return data.decode("utf-8", errors="ignore"), name

                    ef_dict = getattr(file_spec, "obj", {}).get("/EF", {})
                    if ef_dict and "/F" in ef_dict:
                        stream = ef_dict["/F"]
                        data = bytes(stream.read_bytes())
                        return data.decode("utf-8", errors="ignore"), name

                except Exception as e:
                    print(f"⚠️  Fehler beim Lesen des Attachments {name}: {e}")

            # Fallback über Names-Dictionary
            names = getattr(pdf.Root, "EmbeddedFiles", None)
            if names and hasattr(names, "Names"):
                name_list = names.Names
                for i in range(0, len(name_list), 2):
                    name = str(name_list[i])
                    file_spec = name_list[i + 1]
                    if name.lower().endswith(".xml"):
                        ef_stream = file_spec.get("/EF", {}).get("/F")
                        if ef_stream:
                            data = bytes(ef_stream.read_bytes())
                            return data.decode("utf-8", errors="ignore"), name

    except Exception as e:
        print(f"⚠️  Keine eingebettete XML-Datei gefunden ({pdf_path}): {e}")

    return None, None


# ------------------------------------------------------------
# 2. Inline-XML im sichtbaren Textstrom
# ------------------------------------------------------------
def extract_inline_xml(pdf_path: str) -> str | None:
    """Sucht nach einem XML-Block im PDF-Text (robuster Regex-Ansatz)."""
    try:
        text = extract_text(pdf_path)
        clean = re.sub(r"[\x00-\x1f]+", "", text).replace("\n", " ")
        m = re.search(r"(<rsm:CrossIndustryInvoice[\s\S]+?</rsm:CrossIndustryInvoice>)", clean)
        if m:
            return m.group(1)
        m = re.search(r"(<Invoice[\s\S]+?</Invoice>)", clean)
        if m:
            return m.group(1)
        if "urn:cen.eu:en16931" in clean:
            idx = clean.find("urn:cen.eu:en16931")
            snippet = clean[idx:idx + 500]
            return f"<Meta>{snippet}</Meta>"
    except Exception as e:
        print(f"⚠️  Inline-XML konnte nicht extrahiert werden: {e}")
    return None


# ------------------------------------------------------------
# 3. Typ-Erkennung
# ------------------------------------------------------------
def detect_xml_type(xml_content: str):
    """Erkennt, ob XML ZugFeRD/Factur-X oder XRechnung ist."""
    if not xml_content:
        return None
    if "factur-x.eu" in xml_content or "zugferd.de" in xml_content:
        return "zugferd"
    if "CrossIndustryInvoice" in xml_content or "urn:cen.eu:en16931" in xml_content:
        return "xrechnung"
    return None


# ------------------------------------------------------------
# 4. XML Parsing (Felder extrahieren, robust)
# ------------------------------------------------------------
def parse_invoice_xml(xml_content: str):
    """Parst die wichtigsten Felder aus ZugFeRD / XRechnung XML."""
    ns = {
        "rsm": "urn:un:unece:uncefact:data:standard:CrossIndustryInvoice:100",
        "ram": "urn:un:unece:uncefact:data:standard:ReusableAggregateBusinessInformationEntity:100",
        "udt": "urn:un:unece:uncefact:data:standard:UnqualifiedDataType:100",
    }

    xml_status = "ok"
    try:
        root = etree.fromstring(xml_content.encode("utf-8"))
    except etree.XMLSyntaxError as e:
        print(f"⚠️  XML konnte nicht geparst werden: {e}")
        print("🔧  Versuche automatische Bereinigung …")
        xml_content = sanitize_xml(xml_content)
        try:
            root = etree.fromstring(xml_content.encode("utf-8"))
            xml_status = "repaired"
            print("✅  XML erfolgreich repariert.")
            print("⚠️  XML repariert – bitte Aussteller informieren (fehlerhafte Entitäten im XML).")
        except etree.XMLSyntaxError as e2:
            print(f"❌  XML nach Bereinigung weiterhin ungültig: {e2}")
            return {"xml_status": "invalid"}

    def get_text(xpath):
        res = root.xpath(xpath, namespaces=ns)
        if not res:
            return None
        val = res[0]
        if hasattr(val, "text"):
            val = val.text
        if isinstance(val, bytes):
            val = val.decode("utf-8", errors="ignore")
        if isinstance(val, str):
            return val.strip()
        return str(val)

    # ➕ NEU: Dokumenttyp (invoice / credit_note)
    # Robustere Suche nach TypeCode (Rechnung/Gutschrift)
    type_code_candidates = [
        "//rsm:ExchangedDocument/ram:TypeCode",
        "//ram:TypeCode",
        "//TypeCode",  # ohne Namespace
        "//rsm:ExchangedDocumentContext/ram:TypeCode",
        "//rsm:ExchangedDocumentContext//TypeCode"
    ]

    type_code = None
    for path in type_code_candidates:
        type_code = get_text(path)
        if type_code:
            break

    if type_code in ("381", "875"):
        document_type = "credit_note"
    elif type_code in ("380", "382", "383", "384", "386"):
        document_type = "invoice"
    else:
        document_type = "unknown"


    invoice = {
        "number": get_text("//rsm:ExchangedDocument/ram:ID | //rsm:ExchangedDocument/rsm:ID"),
        "date": get_text("//rsm:ExchangedDocument/ram:IssueDateTime//udt:DateTimeString | //rsm:ExchangedDocument/rsm:IssueDateTime//udt:DateTimeString"),
        "seller": get_text("//ram:SellerTradeParty/ram:Name"),
        "buyer": get_text("//ram:BuyerTradeParty/ram:Name"),
        "amount": get_text("//ram:GrandTotalAmount"),
        "currency": get_text("//ram:GrandTotalAmount/@currencyID") or "EUR",
        "xml_status": xml_status,
        "document_type": document_type,   # <--- hinzugefügt
        "type_code": type_code or "",     # <--- hinzugefügt
    }

    if invoice["amount"]:
        try:
            invoice["amount"] = float(invoice["amount"].replace(",", "."))
        except ValueError:
            pass

    return invoice



# ------------------------------------------------------------
# 5. Hauptfunktion
# ------------------------------------------------------------
def detect_and_parse_invoice(pdf_path: str):
    """Erkennt und extrahiert Rechnungsdaten aus einer PDF."""
    if not os.path.isfile(pdf_path):
        raise FileNotFoundError(f"Datei nicht gefunden: {pdf_path}")

    xml_content, xml_name = extract_embedded_xml(pdf_path)
    xml_type = None

    if not xml_content:
        xml_content = extract_inline_xml(pdf_path)
        xml_name = "inline"

    if xml_content:
        xml_type = detect_xml_type(xml_content)

    if not xml_content or not xml_type:
        return None

    info = parse_invoice_xml(xml_content)
    info.update({
        "xml_type": xml_type,
        "xml_filename": xml_name,
        "source_pdf": pdf_path,
    })
    return info
