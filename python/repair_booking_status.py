#!/usr/bin/env python3
"""
repair_booking_status.py
Synchronisiert receipt_status in booking_lines anhand Belegverknüpfung.
"""

from db import get_connection


def repair_booking_status():
    conn = get_connection()
    cur = conn.cursor()

    print("🔄 Repariere Buchungsstatus...")

    # Komplettabgleich anhand Transaktions-ID im Feld description
    cur.execute("""
        WITH linked AS (
            SELECT DISTINCT CAST(description AS INTEGER) AS txid
              FROM booking_lines
             WHERE description ~ '^[0-9]+$'
        )
        UPDATE booking_lines bl
           SET receipt_status = CASE
                WHEN EXISTS (
                    SELECT 1 FROM voucher_links vl WHERE vl.transaction_id = CAST(bl.description AS INTEGER)
                    UNION ALL
                    SELECT 1 FROM outgoing_links ol WHERE ol.transaction_id = CAST(bl.description AS INTEGER)
                )
                THEN 'complete'
                ELSE 'missing'
            END
         WHERE bl.description ~ '^[0-9]+$';
    """)

    conn.commit()
    cur.close()
    conn.close()
    print("✅ Buchungsstatus erfolgreich aktualisiert.")


if __name__ == "__main__":
    repair_booking_status()
