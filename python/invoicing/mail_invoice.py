#!/usr/bin/env python3
"""Open a Thunderbird compose window for an invoice.

Recipients come from the invoice YAML: To is buyer.communication (purchaser),
Cc is buyer.contact (project lead), From is seller.communication (Thunderbird
picks the identity with that address). Attached are invoice_<n>_x.pdf
(Factur-X) and, if present, the activity report timesheet_<n>.pdf. The text
is German for German buyers, English otherwise.

Nothing is sent: Thunderbird only opens the filled-in window, sending stays a
click of its own.

Examples:
  python3 mail_invoice.py RE20260005 --dry-run
  python3 mail_invoice.py RE20260005
"""

import argparse
import os
import subprocess
import sys
import tempfile
from datetime import timedelta
from decimal import Decimal
from pathlib import Path

import yaml

from scan_overdue import DATA_DIR, gross_total, output_dir, parse_date

TEXT = {
    "en": {
        "subject": "Invoice {number}",
        "mr": "Dear Mr {name},", "ms": "Dear Ms {name},", "anon": "Dear Sir or Madam,",
        "intro": "please find attached our invoice {number}{ref}.",
        "po": " for PO {po}", "project": " ({project})",
        "period": "Service period: {start} to {end}",
        "amount": "Amount due: {amount} EUR, payable by {due}",
        "report": "The activity report with the hours per day ({hours} h) is attached as well.",
        "facturx": "The invoice is a Factur-X e-invoice (PDF with embedded EN 16931 data).",
        "closing": "Best regards",
    },
    "de": {
        "subject": "Rechnung {number}",
        "mr": "Sehr geehrter Herr {name},", "ms": "Sehr geehrte Frau {name},",
        "anon": "Sehr geehrte Damen und Herren,",
        "intro": "anbei erhalten Sie unsere Rechnung {number}{ref}.",
        "po": " zu Ihrer Bestellung {po}", "project": " ({project})",
        "period": "Leistungszeitraum: {start} bis {end}",
        "amount": "Rechnungsbetrag: {amount} EUR, zahlbar bis {due}",
        "report": "Den Leistungsnachweis mit den Stunden je Tag ({hours} h) finden Sie ebenfalls im Anhang.",
        "facturx": "Die Rechnung ist eine E-Rechnung im Format Factur-X (PDF mit eingebetteten Daten nach EN 16931).",
        "closing": "Mit freundlichen Grüßen",
    },
}


def salutation(person, t):
    """'Herr Marcel Mintert' -> 'Dear Mr Mintert,'; without Herr/Frau the neutral form."""
    words = str(person or "").split()
    if len(words) >= 2 and words[0] in ("Herr", "Mr", "Mr."):
        return t["mr"].format(name=words[-1])
    if len(words) >= 2 and words[0] in ("Frau", "Ms", "Ms.", "Mrs", "Mrs."):
        return t["ms"].format(name=words[-1])
    return t["anon"]


def amount(value, lang):
    s = f"{value:,.2f}"
    return s.replace(",", "X").replace(".", ",").replace("X", ".") if lang == "de" else s


def day(value, lang):
    return f"{value:%d.%m.%Y}" if lang == "de" else value.isoformat()


def compose(number, data_dir):
    """Build the mail for an invoice. Returns (fields, body, warnings)."""
    path = data_dir / f"invoice_{number}.yaml"
    if not path.is_file():
        sys.exit(f"ERROR: invoice not found: {path}")
    data = yaml.safe_load(path.read_text(encoding="utf-8"))
    head = data.get("invoice", {})
    buyer, seller = data.get("buyer", {}), data.get("seller", {})
    country = str(buyer.get("country_code") or buyer.get("country") or "").upper()
    lang = "de" if country in ("DE", "GERMANY", "DEUTSCHLAND") else "en"
    t = TEXT[lang]
    warnings = []

    purchaser = buyer.get("communication") or {}
    lead = buyer.get("contact") or {}
    to = purchaser.get("email") or lead.get("email")
    if not to:
        sys.exit(f"ERROR: {path.name} has no buyer e-mail (buyer.communication / buyer.contact)")
    cc = lead.get("email") if lead.get("email") and lead.get("email") != to else ""
    greeting = salutation(purchaser.get("person_name") if purchaser.get("email") else lead.get("person_name"), t)

    out = output_dir(data_dir)
    invoice_pdf = out / f"invoice_{number}_x.pdf"
    if not invoice_pdf.is_file():
        sys.exit(f"ERROR: {invoice_pdf.name} not found in {out}, render the invoice first")
    attachments = [invoice_pdf]
    report = out / f"timesheet_{number}.pdf"
    hours = sum((Decimal(str(l["quantity"])) for l in data.get("lines", [])
                 if l.get("unit_code") == "HUR"), Decimal("0"))
    if report.is_file():
        attachments.append(report)
    elif hours:
        warnings.append(f"WARN: no activity report {report.name}, the mail goes without it")

    issue = parse_date(head["issue_date"])
    due = parse_date(data["due_date"]) if data.get("due_date") else \
        issue + timedelta(days=int(data.get("payment", {}).get("terms_days", 14)))
    po = str(head.get("po_number") or "")
    project = str(head.get("buyer_reference") or "")
    ref = (t["po"].format(po=po) if po else "") + (t["project"].format(project=project) if project else "")

    subject = t["subject"].format(number=number)
    if po:
        subject += f" - PO {po}"
    if project:
        subject += f" ({project})"

    lines = [greeting, "", t["intro"].format(number=number, ref=ref), ""]
    period = head.get("service_period") or {}
    if period.get("start") and period.get("end"):
        lines.append(t["period"].format(start=day(parse_date(period["start"]), lang),
                                        end=day(parse_date(period["end"]), lang)))
    lines += [t["amount"].format(amount=amount(gross_total(data), lang), due=day(due, lang)), ""]
    if report in attachments:
        lines += [t["report"].format(hours=amount(hours, lang)), ""]
    lines += [t["facturx"], "", t["closing"]]
    lines += [n for n in ((seller.get("contact") or {}).get("person_name"), seller.get("name")) if n]

    fields = {
        "from": (seller.get("communication") or {}).get("email") or (seller.get("contact") or {}).get("email") or "",
        "to": to,
        "cc": cc,
        "subject": subject,
        "attachment": ",".join(p.resolve().as_uri() for p in attachments),
    }
    return fields, "\n".join(lines) + "\n", warnings


def launch(number, fields, body):
    """Open the compose window; the body goes through a file, so no quoting issues."""
    message = Path(tempfile.gettempdir()) / f"mail_{number}.txt"
    message.write_text(body, encoding="utf-8")
    # -compose values are quoted; a quote inside a value would end it early
    args = ",".join(f"{key}='{value.replace(chr(39), '')}'" for key, value in fields.items() if value)
    subprocess.Popen(["thunderbird", "-compose", f"{args},message='{message}'"],
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     start_new_session=True, env=os.environ.copy())


def summary(fields, body, warnings):
    out = [f"From:    {fields['from'] or '(Thunderbird default identity)'}",
           f"To:      {fields['to']}"]
    if fields["cc"]:
        out.append(f"Cc:      {fields['cc']}")
    out.append(f"Subject: {fields['subject']}")
    for uri in fields["attachment"].split(","):
        out.append(f"Attach:  {Path(uri).name}")
    return "\n".join(warnings + out + ["", body.rstrip()])


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("invoice", help="invoice number, e.g. RE20260005")
    ap.add_argument("--dry-run", action="store_true", help="show the mail, don't open Thunderbird")
    ap.add_argument("--dir", default=str(DATA_DIR), help="data directory")
    args = ap.parse_args()

    fields, body, warnings = compose(args.invoice, Path(args.dir))
    print(summary(fields, body, warnings))
    if args.dry_run:
        return
    launch(args.invoice, fields, body)
    print("\nThunderbird compose window opened - check and send it there.")


if __name__ == "__main__":
    main()
