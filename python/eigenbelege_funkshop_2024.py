#!/usr/bin/env python3
"""
eigenbelege_funkshop_2024.py – Einmalskript: erzeugt 3 GoBD-Eigenbelege für die
offenen Funkshop-Eingangsbelege 2024 (tx 8401/8403/7467), bucht sie in die EÜR
(vouchers + voucher_lines + voucher_links) und legt das Eigenbeleg-PDF ab.

Entscheidungen (vom Inhaber bestätigt 2026-06-25):
  - 19% Vorsteuer ansetzen (Originalrechnungen folgen, Funkshop = regulärer dt. Händler)
  - Icom IC-M605 als GWG sofort 2024 abschreiben (Netto 762,94 € < 800 €)

Belege werden mit receipt_status='pending' geführt → Original wird nach Urlaub
ausgetauscht (self_vouchers.sha256_hash sichert den Eigenbeleg GoBD-konform).
"""
import os
import sys
from decimal import Decimal, ROUND_HALF_UP

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_connection
from create_self_voucher import make_hash, create_pdf

PARTNER = "Funkshop.com"
REASON = ("Eigenbeleg als Ersatz fuer ausstehende Originalrechnung Funkshop.com "
          "(urlaubsbedingt verzoegert) - wird gegen Original ausgetauscht.")
REMARKS = ("Original folgt nach Urlaub. Vorsteuer 19% geltend gemacht. "
           "Beleg wird beim Eintreffen der Originalrechnung ausgetauscht (receipt_status=pending).")
OUT_DIR = os.path.abspath("belege/2024/11")

# (transaction_id, voucher_date, gross, account_skr, line_description)
ITEMS = [
    (8401, "2024-11-21", Decimal("907.90"), "4806",
     "Icom IC-M605 EURO Marine-VHF-Funkgeraet (GWG, Sofortabschreibung)"),
    (8403, "2024-11-21", Decimal("252.90"), "4806",
     "SIRIO SB-2-S Antenne + Icom HM-229B Mikrofon (GWG, Sofortabschreibung)"),
    (7467, "2024-11-29", Decimal("44.90"), "4900",
     "Funkshop Bestellung vom 26.11.2024 (Betriebsbedarf)"),
]


def split_gross(gross: Decimal):
    net = (gross / Decimal("1.19")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tax = gross - net
    return net, tax


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    conn = get_connection()
    cur = conn.cursor()

    # Safety: keine Doppelbuchung
    cur.execute("SELECT transaction_id FROM voucher_links WHERE transaction_id IN (8401,8403,7467);")
    existing = [r[0] for r in cur.fetchall()]
    if existing:
        print(f"❌ Abbruch: Transaktionen bereits verknuepft: {existing}")
        sys.exit(1)
    cur.execute("SELECT COUNT(*) FROM self_vouchers WHERE voucher_number LIKE 'EB-2026-%';")
    base = cur.fetchone()[0]

    print(f"📄 Eigenbelege werden abgelegt in: {OUT_DIR}\n")

    for i, (tx_id, vdate, gross, account, line_desc) in enumerate(ITEMS, start=1):
        vnum = f"EB-2026-{base + i:03d}"
        net, tax = split_gross(gross)
        sha = make_hash(vnum, vdate, REASON, PARTNER, gross)
        pdf_path = os.path.join(OUT_DIR, f"{vnum}.pdf")

        pdf_data = {
            "voucher_number": vnum, "voucher_date": vdate, "reason": REASON,
            "partner_name": PARTNER, "amount": gross, "currency": "EUR",
            "sha256_hash": sha, "file_path": pdf_path, "remarks": REMARKS,
        }
        create_pdf(pdf_path, pdf_data)

        # 1) Bookkeeping-Voucher
        cur.execute("""
            INSERT INTO vouchers
                (voucher_number, voucher_date, booking_date, partner_name, description,
                 total_amount, currency, document_type, source, status, receipt_status)
            VALUES (%s, %s, %s, %s, %s, %s, 'EUR', 'self_issued', 'eigenbeleg', 'paid', 'pending')
            RETURNING id;
        """, (vnum, vdate, vdate, PARTNER,
              f"Eigenbeleg Funkshop (Original ausstehend) – {line_desc}", gross))
        voucher_id = cur.fetchone()[0]

        # 2) GoBD-Eigenbeleg in self_vouchers (mit Hash + Verweis auf Buchungsbeleg)
        cur.execute("""
            INSERT INTO self_vouchers
                (voucher_number, voucher_date, reason, partner_name, amount, currency,
                 reference_voucher_id, sha256_hash, file_path, remarks)
            VALUES (%s, %s, %s, %s, %s, 'EUR', %s, %s, %s, %s);
        """, (vnum, vdate, REASON, PARTNER, gross, voucher_id, sha, pdf_path, REMARKS))

        # 3) Buchungszeile (Netto + 19% VSt)
        cur.execute("""
            INSERT INTO voucher_lines
                (voucher_id, account_skr, description, net_amount, tax_rate, tax_amount)
            VALUES (%s, %s, %s, %s, 19.00, %s);
        """, (voucher_id, account, line_desc, net, tax))

        # 4) Verknuepfung mit Bank-Transaktion
        cur.execute("""
            INSERT INTO voucher_links (voucher_id, transaction_id, amount)
            VALUES (%s, %s, %s);
        """, (voucher_id, tx_id, gross))

        print(f"✅ {vnum}  tx {tx_id}  brutto {gross:>7.2f} €  "
              f"= netto {net:.2f} + VSt {tax:.2f}  → SKR03 {account}")
        print(f"   PDF: {pdf_path}")
        print(f"   SHA256: {sha}\n")

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Alle 3 Eigenbelege gebucht. Jetzt: rebuild_booking_lines.py --month 2024-11")


if __name__ == "__main__":
    main()
