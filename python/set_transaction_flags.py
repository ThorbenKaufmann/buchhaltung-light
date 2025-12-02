#!/usr/bin/env python3
"""
set_transaction_flags.py
------------------------
Setzt oder entfernt Flags für EINZELNE Transaktionen:

    --txid ID (Pflicht)
    --is_private TRUE/FALSE   (optional)
    --is_cyclic TRUE/FALSE    (optional)
    --is_internal TRUE/FALSE  (optional)

Beispiel:
    ./python/set_transaction_flags.py --txid 6123 --is_private TRUE
    ./python/set_transaction_flags.py --txid 7001 --is_internal TRUE
    ./python/set_transaction_flags.py --txid 7002 --is_cyclic FALSE

Ohne gesetzte --is_* Flags passiert nichts.
"""

import argparse
from db import get_connection
from bhl_utils import row_get, unwrap_text, safe_float, format_date


def to_bool(value):
    """Konvertiert TRUE/FALSE/true/false in bool."""
    if value is None:
        return None
    val = str(value).strip().lower()
    return val in ("true", "1", "yes", "y")


def set_transaction_flags(txid, is_private, is_cyclic, is_internal):

    conn = get_connection()
    cur = conn.cursor()

    # ---------------------------------------------------------
    # 1. Transaktion abrufen
    # ---------------------------------------------------------
    cur.execute("""
        SELECT id, booking_date, amount, counterpart_name, purpose,
               is_private, is_cyclic, is_internal
          FROM transactions
         WHERE id = %s
    """, (txid,))
    row = cur.fetchone()

    if not row:
        print(f"❌ Transaktion {txid} nicht gefunden.")
        return

    tid  = row_get(row, "id", 0)
    tdat = format_date(row_get(row, "booking_date", 1))
    amt  = safe_float(row_get(row, "amount", 2))
    name = unwrap_text(row, "counterpart_name", 3)
    purp = unwrap_text(row, "purpose", 4)

    old_private  = row_get(row, "is_private",  5)
    old_cyclic   = row_get(row, "is_cyclic",   6)
    old_internal = row_get(row, "is_internal", 7)

    print("\n📄 Transaktionsdetails:")
    print(f"  TxID {tid}")
    print(f"  Datum     : {tdat}")
    print(f"  Betrag    : {amt:.2f} EUR")
    print(f"  Name      : {name}")
    print(f"  Zweck     : {purp}")
    print("\n🔎 Alte Flags:")
    print(f"  privat    : {old_private}")
    print(f"  zyklisch  : {old_cyclic}")
    print(f"  intern    : {old_internal}")

    # ---------------------------------------------------------
    # 2. Prüfen, was gesetzt werden soll
    # ---------------------------------------------------------
    updates = {}
    if is_private is not None:
        updates["is_private"] = is_private
    if is_cyclic is not None:
        updates["is_cyclic"] = is_cyclic
    if is_internal is not None:
        updates["is_internal"] = is_internal

    if not updates:
        print("\nℹ️ Keine --is_* Flags gesetzt. Keine Änderung vorgenommen.")
        return

    print("\n🆕 Neue Werte:")
    for key, val in updates.items():
        print(f"  {key:10s} = {val}")

    # ---------------------------------------------------------
    # 3. Bestätigung
    # ---------------------------------------------------------
    confirm = input("\nÄnderungen durchführen? [y/N] ").strip().lower()
    if confirm != "y":
        print("Abgebrochen.")
        return

    # ---------------------------------------------------------
    # 4. Update bauen
    # ---------------------------------------------------------
    set_clauses = []
    params = []

    for col, val in updates.items():
        set_clauses.append(f"{col} = %s")
        params.append(val)

    params.append(txid)

    sql = f"""
        UPDATE transactions
           SET {", ".join(set_clauses)}
         WHERE id = %s
    """

    cur.execute(sql, params)
    conn.commit()

    print(f"\n✅ Transaktion {txid} aktualisiert.")

    cur.close()
    conn.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Setzt Flags für eine Transaktion.")

    ap.add_argument("--txid", type=int, required=True, help="Transaktions-ID (Pflicht)")

    ap.add_argument("--is_private", help="TRUE/FALSE")
    ap.add_argument("--is_cyclic", help="TRUE/FALSE")
    ap.add_argument("--is_internal", help="TRUE/FALSE")

    args = ap.parse_args()

    set_transaction_flags(
        txid=args.txid,
        is_private=to_bool(args.is_private),
        is_cyclic=to_bool(args.is_cyclic),
        is_internal=to_bool(args.is_internal),
    )
