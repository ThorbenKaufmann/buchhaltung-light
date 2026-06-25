#!/usr/bin/env python3
"""
import_ibis_dyndns_2024.py – Einmalskript: bucht die beiden Backlog-Rechnungen
IBIS Budget Karlsruhe (tx 7265) und DynDNS/Oracle (tx 8306) als echte
Eingangsrechnungen (vouchers + voucher_documents + voucher_lines + voucher_links).

- IBIS: Beherbergung, 7% USt, Originalrechnung A-251259 vorhanden -> receipt_status=complete
- DynDNS: US-Service (Oracle), Reverse Charge §13b -> 0% VSt (Haus-Muster wie Toggl/DocuSign)

PDFs werden aus backlog/ in belege/JAHR/MONAT/ archiviert (move, wie process_voucher).
"""
import os
import re
import sys
import shutil
import hashlib
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from db import get_connection

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def slug(text):
    text = re.sub(r"[^A-Za-z0-9]+", "_", text).strip("_")
    return text[:60]


def sha256sum(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


# (src_pdf, tx_id, vnum, vdate, partner, desc, gross, account, tax_rate, tax_amount)
ITEMS = [
    ("backlog/2024/ibis_251259.pdf", 7265, "A-251259", "2024-03-25",
     "AccorInvest Germany GmbH",
     "ibis budget Karlsruhe – Übernachtung 25.03.2024 (Dienstreise)",
     Decimal("69.00"), "4664", Decimal("7.00"), Decimal("4.51")),
    ("backlog/2024/DynDNS Invoice #12991191.pdf", 8306, "12991191", "2024-02-01",
     "Oracle America, Inc. (DynDNS)",
     "Dynamic DNS Pro Renewal (1 Jahr) – Reverse Charge §13b UStG",
     Decimal("55.00"), "4905", Decimal("0.00"), Decimal("0.00")),
]


def ensure_account_4664(cur):
    cur.execute("SELECT 1 FROM skr03_accounts WHERE id='4664';")
    if cur.fetchone():
        return
    cur.execute("""
        INSERT INTO skr03_accounts (id, name, default_tax, category, is_expense, is_revenue, is_active)
        VALUES ('4664', 'Reisekosten Unternehmer Übernachtungsaufwand', 7.00, 'Aufwand', true, false, true);
    """)
    print("➕ SKR03-Konto 4664 'Reisekosten Unternehmer Übernachtungsaufwand' angelegt.")


def main():
    conn = get_connection()
    cur = conn.cursor()

    cur.execute("SELECT transaction_id FROM voucher_links WHERE transaction_id IN (7265,8306);")
    existing = [r[0] for r in cur.fetchall()]
    if existing:
        print(f"❌ Abbruch: Transaktionen bereits verknuepft: {existing}")
        sys.exit(1)

    ensure_account_4664(cur)

    for (src, tx_id, vnum, vdate, partner, desc, gross, account, tax_rate, tax) in ITEMS:
        src_abs = os.path.join(REPO, src)
        if not os.path.isfile(src_abs):
            print(f"❌ PDF fehlt: {src_abs}")
            sys.exit(1)
        net = gross - tax
        y, m = vdate[:4], vdate[5:7]
        target_dir_rel = f"belege/{y}/{m}"
        target_dir_abs = os.path.join(REPO, target_dir_rel)
        os.makedirs(target_dir_abs, exist_ok=True)
        new_filename = f"{vdate}_{slug(partner)}_{vnum}.pdf"
        target_abs = os.path.join(target_dir_abs, new_filename)

        file_hash = sha256sum(src_abs)
        shutil.move(src_abs, target_abs)

        # 1) Voucher
        cur.execute("""
            INSERT INTO vouchers
                (voucher_number, voucher_date, booking_date, partner_name, description,
                 total_amount, currency, document_type, source, status, receipt_status)
            VALUES (%s,%s,%s,%s,%s,%s,'EUR','invoice','manual','paid','complete')
            RETURNING id;
        """, (vnum, vdate, vdate, partner, desc, gross))
        vid = cur.fetchone()[0]

        # 2) Dokumentanhang (Original-PDF)
        cur.execute("""
            INSERT INTO voucher_documents (voucher_id, file_name, file_path, mime_type, file_hash)
            VALUES (%s,%s,%s,'application/pdf',%s);
        """, (vid, new_filename, target_dir_rel, file_hash))

        # 3) Buchungszeile
        cur.execute("""
            INSERT INTO voucher_lines
                (voucher_id, account_skr, description, net_amount, tax_rate, tax_amount)
            VALUES (%s,%s,%s,%s,%s,%s);
        """, (vid, account, desc, net, tax_rate, tax))

        # 4) Bank-Verknuepfung
        cur.execute("""
            INSERT INTO voucher_links (voucher_id, transaction_id, amount)
            VALUES (%s,%s,%s);
        """, (vid, tx_id, gross))

        vst = f"{tax_rate:.0f}% / {tax:.2f}" if tax > 0 else "Reverse Charge 0%"
        print(f"✅ {vnum:12} tx {tx_id}  brutto {gross:>6.2f} € = netto {net:.2f} + VSt {vst}  → SKR03 {account}")
        print(f"   PDF → {target_dir_rel}/{new_filename}")

    conn.commit()
    cur.close()
    conn.close()
    print("\n✅ Beide Rechnungen gebucht. Jetzt: rebuild_booking_lines --month 2024-02 und 2024-03")


if __name__ == "__main__":
    main()
