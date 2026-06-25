#!/usr/bin/env python3
"""
import_amazon_2024.py – bucht die beiden Amazon-Business-Rechnungen 2024 als echte
Eingangsrechnungen (vouchers + voucher_documents + voucher_lines + voucher_links).

- tx 7278 Apr: DE41CHWUABEI, 2x BenQ-Monitor, 19% USt -> GWG (4806)
- tx 7440 Okt: DE44EMM6ABEI, Philips Wake-up Light, 19% USt -> GWG (4806)
PDFs werden aus backlog/ nach belege/JAHR/MONAT/ archiviert (move).
"""
import os, re, sys, shutil, hashlib
from decimal import Decimal
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_connection

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def slug(t): return re.sub(r"[^A-Za-z0-9]+", "_", t).strip("_")[:60]


def sha256sum(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for c in iter(lambda: f.read(8192), b""):
            h.update(c)
    return h.hexdigest()


# (src_pdf, tx_id, vnum, vdate, partner, desc, gross, account, tax_rate, tax_amount)
ITEMS = [
    ("backlog/2024/invoice_Amazon_DE41CHWUABEI.pdf", 7278, "DE41CHWUABEI", "2024-04-05",
     "Amazon Business EU S.à r.l",
     "2x BenQ GW2480 60,5cm Monitor (GWG, Sofortabschreibung)",
     Decimal("194.40"), "4806", Decimal("19.00"), Decimal("31.04")),
    ("backlog/2024/invoice_Amazon_TR9WH0324.pdf", 7440, "DE44EMM6ABEI", "2024-10-28",
     "Amazon Business EU S.à r.l, Niederlassung Deutschland",
     "Philips HF3519/01 Wake-up Light (GWG, Sofortabschreibung)",
     Decimal("144.99"), "4806", Decimal("19.00"), Decimal("23.15")),
]


def main():
    conn = get_connection(); cur = conn.cursor()
    cur.execute("SELECT transaction_id FROM voucher_links WHERE transaction_id IN (7278,7440);")
    ex = [r[0] for r in cur.fetchall()]
    if ex:
        print(f"❌ Abbruch: bereits verknuepft: {ex}"); sys.exit(1)

    for (src, tx_id, vnum, vdate, partner, desc, gross, account, tax_rate, tax) in ITEMS:
        src_abs = os.path.join(REPO, src)
        if not os.path.isfile(src_abs):
            print(f"❌ PDF fehlt: {src_abs}"); sys.exit(1)
        net = gross - tax
        y, m = vdate[:4], vdate[5:7]
        tdir_rel = f"belege/{y}/{m}"
        tdir_abs = os.path.join(REPO, tdir_rel); os.makedirs(tdir_abs, exist_ok=True)
        fname = f"{vdate}_{slug(partner)}_{vnum}.pdf"
        tgt = os.path.join(tdir_abs, fname)
        fh = sha256sum(src_abs)
        shutil.move(src_abs, tgt)

        cur.execute("""
            INSERT INTO vouchers (voucher_number, voucher_date, booking_date, partner_name,
                description, total_amount, currency, document_type, source, status, receipt_status)
            VALUES (%s,%s,%s,%s,%s,%s,'EUR','invoice','manual','paid','complete') RETURNING id;
        """, (vnum, vdate, vdate, partner, desc, gross))
        vid = cur.fetchone()[0]
        cur.execute("""INSERT INTO voucher_documents (voucher_id, file_name, file_path, mime_type, file_hash)
                       VALUES (%s,%s,%s,'application/pdf',%s);""", (vid, fname, tdir_rel, fh))
        cur.execute("""INSERT INTO voucher_lines (voucher_id, account_skr, description, net_amount, tax_rate, tax_amount)
                       VALUES (%s,%s,%s,%s,%s,%s);""", (vid, account, desc, net, tax_rate, tax))
        cur.execute("""INSERT INTO voucher_links (voucher_id, transaction_id, amount) VALUES (%s,%s,%s);""",
                    (vid, tx_id, gross))
        print(f"✅ {vnum:14} tx {tx_id}  brutto {gross:>7.2f} € = netto {net:.2f} + 19% VSt {tax:.2f}  → SKR03 {account}")
        print(f"   PDF → {tdir_rel}/{fname}")

    conn.commit(); cur.close(); conn.close()
    print("\n✅ Amazon gebucht. Jetzt: rebuild_booking_lines --month 2024-04 und 2024-10")


if __name__ == "__main__":
    main()
