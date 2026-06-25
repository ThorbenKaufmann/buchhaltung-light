#!/usr/bin/env python3
"""
eigenbeleg_cisco_2024.py – GoBD-Eigenbeleg für Cisco Webex (tx 8340).

Inhaber-Angabe: deutsche USt 19%. Provider liefert keine §14-Rechnung mehr,
daher Eigenbeleg; receipt_status='pending' (Original ggf. direkt bei Cisco ziehen).
HINWEIS: Ohne §14-Originalrechnung ist der 19%-Vorsteuerabzug formal angreifbar.
"""
import os, sys
from decimal import Decimal, ROUND_HALF_UP
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_connection
from create_self_voucher import make_hash, create_pdf

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
TX = 8340
PARTNER = "Cisco Webex"
VDATE = "2024-05-11"
GROSS = Decimal("207.60")
ACCOUNT = "4909"  # HW-/SW-Miete / Cloud-/SaaS-Gebühren
LINE_DESC = "Cisco Webex Order 123988076300 (SaaS), 19% deutsche USt lt. Inhaber"
REASON = ("Eigenbeleg fuer Cisco Webex (Order 123988076300) - Provider liefert keine "
          "Rechnung mehr; wird gegen Original ausgetauscht, falls noch beschaffbar.")
REMARKS = ("Inhaber: deutsche USt 19%. Ohne §14-Originalrechnung ist der Vorsteuerabzug "
           "formal angreifbar - Original moeglichst direkt bei Cisco nachfordern. receipt_status=pending.")
OUT_DIR = os.path.join(REPO, "belege/2024/05")


def main():
    os.makedirs(OUT_DIR, exist_ok=True)
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT 1 FROM voucher_links WHERE transaction_id=%s;", (TX,))
    if cur.fetchone():
        print(f"❌ Abbruch: tx {TX} bereits verknuepft."); sys.exit(1)
    cur.execute("SELECT COUNT(*) FROM self_vouchers WHERE voucher_number LIKE 'EB-2026-%';")
    vnum = f"EB-2026-{cur.fetchone()[0] + 1:03d}"

    net = (GROSS / Decimal("1.19")).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    tax = GROSS - net
    sha = make_hash(vnum, VDATE, REASON, PARTNER, GROSS)
    pdf_path = os.path.join(OUT_DIR, f"{vnum}.pdf")
    create_pdf(pdf_path, {"voucher_number": vnum, "voucher_date": VDATE, "reason": REASON,
                          "partner_name": PARTNER, "amount": GROSS, "currency": "EUR",
                          "sha256_hash": sha, "file_path": pdf_path, "remarks": REMARKS})

    cur.execute("""
        INSERT INTO vouchers (voucher_number, voucher_date, booking_date, partner_name, description,
            total_amount, currency, document_type, source, status, receipt_status)
        VALUES (%s,%s,%s,%s,%s,%s,'EUR','self_issued','eigenbeleg','paid','pending') RETURNING id;
    """, (vnum, VDATE, VDATE, PARTNER, f"Eigenbeleg Cisco Webex (Original ausstehend) – {LINE_DESC}", GROSS))
    vid = cur.fetchone()[0]
    cur.execute("""INSERT INTO self_vouchers (voucher_number, voucher_date, reason, partner_name, amount,
        currency, reference_voucher_id, sha256_hash, file_path, remarks)
        VALUES (%s,%s,%s,%s,%s,'EUR',%s,%s,%s,%s);""",
        (vnum, VDATE, REASON, PARTNER, GROSS, vid, sha, pdf_path, REMARKS))
    cur.execute("""INSERT INTO voucher_lines (voucher_id, account_skr, description, net_amount, tax_rate, tax_amount)
        VALUES (%s,%s,%s,%s,19.00,%s);""", (vid, ACCOUNT, LINE_DESC, net, tax))
    cur.execute("""INSERT INTO voucher_links (voucher_id, transaction_id, amount) VALUES (%s,%s,%s);""",
        (vid, TX, GROSS))

    conn.commit(); cur.close(); conn.close()
    print(f"✅ {vnum}  tx {TX}  brutto {GROSS:.2f} € = netto {net:.2f} + 19% VSt {tax:.2f}  → SKR03 {ACCOUNT}")
    print(f"   PDF: {pdf_path}\n   SHA256: {sha}")


if __name__ == "__main__":
    main()
