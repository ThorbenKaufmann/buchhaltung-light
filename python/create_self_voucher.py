#!/usr/bin/env python3
"""
create_self_voucher.py – GoBD-konformer Eigenbeleg mit SHA256-Hash und PDF-Ausgabe

Beispiel:
  python3 ./python/create_self_voucher.py \
      --date 2024-07-01 \
      --partner "STRATO AG" \
      --amount 5.00 \
      --reason "Mahngebühr zu Rechnung 2024-021" \
      --output belege/2024/07
"""

import argparse, hashlib, os
from datetime import datetime
from decimal import Decimal
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from db import get_connection


def make_hash(voucher_number, date, reason, partner, amount):
    payload = f"{voucher_number}|{date}|{reason}|{partner}|{amount:.2f}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def next_voucher_number(cur) -> str:
    year = datetime.now().year
    cur.execute("SELECT COUNT(*) FROM self_vouchers WHERE EXTRACT(YEAR FROM created_at)=%s;", (year,))
    count = cur.fetchone()[0] + 1
    return f"EB-{year}-{count:03d}"


def create_pdf(path, data):
    c = canvas.Canvas(path, pagesize=A4)
    t = c.beginText(50, 780)
    t.setFont("Helvetica", 11)
    t.textLine("Eigenbeleg / Selbstbeleg")
    t.textLine(f"Nummer: {data['voucher_number']}")
    t.textLine(f"Datum:  {data['voucher_date']}")
    t.textLine("")
    t.textLine(f"Partner: {data['partner_name'] or '-'}")
    t.textLine(f"Betrag:  {data['amount']:.2f} {data['currency']}")
    t.textLine(f"Verwendungszweck: {data['reason']}")
    t.textLine("")
    t.textLine(f"Begründung: {data['remarks'] or 'Kein Fremdbeleg vorhanden.'}")
    t.textLine("")
    t.textLine(f"SHA256-Hash: {data['sha256_hash']}")
    c.drawText(t)
    c.showPage()
    c.save()


def create_self_voucher(args):
    conn = get_connection()
    cur = conn.cursor()

    voucher_number = next_voucher_number(cur)
    sha256_hash = make_hash(voucher_number, args.date, args.reason, args.partner, args.amount)

    # Pfad vorbereiten
    out_dir = os.path.abspath(args.output)
    os.makedirs(out_dir, exist_ok=True)
    pdf_name = f"{voucher_number}.pdf"
    pdf_path = os.path.join(out_dir, pdf_name)

    data = {
        "voucher_number": voucher_number,
        "voucher_date": args.date,
        "reason": args.reason,
        "partner_name": args.partner,
        "amount": args.amount,
        "currency": args.currency,
        "sha256_hash": sha256_hash,
        "file_path": pdf_path,
        "remarks": args.remarks,
    }

    # DB-Eintrag
    cur.execute("""
        INSERT INTO self_vouchers
            (voucher_number, voucher_date, reason, partner_name,
             amount, currency, sha256_hash, file_path, remarks)
        VALUES (%(voucher_number)s, %(voucher_date)s, %(reason)s,
                %(partner_name)s, %(amount)s, %(currency)s,
                %(sha256_hash)s, %(file_path)s, %(remarks)s)
        RETURNING id;
    """, data)
    sid = cur.fetchone()[0]

    # PDF-Erzeugung
    create_pdf(pdf_path, data)

    # Optional in vouchers aufnehmen
    if args.add_to_vouchers:
        cur.execute("""
            INSERT INTO vouchers
                (voucher_number, voucher_date, partner_name,
                 total_amount, currency, document_type, source, status)
            VALUES (%s, %s, %s, %s, %s, 'self_issued', 'system', 'booked')
            ON CONFLICT DO NOTHING;
        """, (voucher_number, args.date, args.partner, args.amount, args.currency))

    conn.commit()
    cur.close()
    conn.close()

    print(f"✅ Eigenbeleg {voucher_number} erstellt.")
    print(f"   Hash: {sha256_hash}")
    print(f"   PDF:  {pdf_path}\n")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Erzeugt einen Eigenbeleg (Self Voucher).")
    ap.add_argument("--date", required=True, help="Belegdatum (YYYY-MM-DD)")
    ap.add_argument("--partner", required=True, help="Empfänger / Partnername")
    ap.add_argument("--amount", required=True, type=Decimal, help="Betrag in EUR")
    ap.add_argument("--reason", required=True, help="Grund / Zweck der Ausgabe")
    ap.add_argument("--remarks", help="Ergänzende Beschreibung")
    ap.add_argument("--currency", default="EUR")
    ap.add_argument("--output", default="belege/self")
    ap.add_argument("--add-to-vouchers", action="store_true", help="auch in vouchers eintragen")
    args = ap.parse_args()

    create_self_voucher(args)
