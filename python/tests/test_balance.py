"""
Logik-Tests für die Belegabstimmung (Sammelzahlungen).

Spiegelt die Aggregat-Abfrage aus check_balanced_transactions.py:
eine Transaktion gilt als ausgeglichen, wenn die Summe der verknüpften
Belegbeträge betragsmäßig (±Toleranz) dem Transaktionsbetrag entspricht.

Alle Inserts laufen in der Test-Transaktion der `db_conn`-Fixture und
werden danach zurückgerollt – es bleiben keine Daten zurück.
"""

from decimal import Decimal

# identisch zur Default-Toleranz in check_balanced_transactions.py
TOLERANCE = Decimal("0.5")

# SQL-Logik aus check_balanced_transactions.py, auf eine TxID eingegrenzt.
LINKED_SUM_SQL = """
    SELECT COALESCE(SUM(vl.amount), 0) AS linked_amount,
           COUNT(vl.voucher_id)        AS voucher_count
    FROM transactions t
    LEFT JOIN voucher_links vl ON vl.transaction_id = t.id
    WHERE t.id = %s
    GROUP BY t.id;
"""


def _make_account(cur, name="CI Testkonto"):
    cur.execute(
        "INSERT INTO accounts (name, type) VALUES (%s, 'bank') RETURNING id",
        (name,),
    )
    return cur.fetchone()[0]


def _make_transaction(cur, account_id, amount):
    cur.execute(
        """
        INSERT INTO transactions (account_id, booking_date, amount, counterpart_name)
        VALUES (%s, DATE '2026-01-15', %s, 'CI Gegenpartei')
        RETURNING id
        """,
        (account_id, amount),
    )
    return cur.fetchone()[0]


def _make_voucher(cur, total):
    cur.execute(
        """
        INSERT INTO vouchers (voucher_date, document_type, total_amount, partner_name)
        VALUES (DATE '2026-01-15', 'receipt', %s, 'CI Lieferant')
        RETURNING id
        """,
        (total,),
    )
    return cur.fetchone()[0]


def _link(cur, voucher_id, transaction_id, amount):
    cur.execute(
        """
        INSERT INTO voucher_links (voucher_id, transaction_id, link_type, amount)
        VALUES (%s, %s, 'payment', %s)
        """,
        (voucher_id, transaction_id, amount),
    )


def _linked_sum(cur, tx_id):
    cur.execute(LINKED_SUM_SQL, (tx_id,))
    linked_amount, voucher_count = cur.fetchone()
    return Decimal(linked_amount), voucher_count


def _is_balanced(tx_amount, linked_amount):
    diff = abs(abs(Decimal(tx_amount)) - abs(Decimal(linked_amount)))
    return diff <= TOLERANCE


def test_collective_payment_is_balanced(db_conn):
    """Zwei Belege (-100 / -19) gleichen eine Sammelzahlung (-119) aus."""
    with db_conn.cursor() as cur:
        acc = _make_account(cur)
        tx = _make_transaction(cur, acc, Decimal("-119.00"))
        v1 = _make_voucher(cur, Decimal("-100.00"))
        v2 = _make_voucher(cur, Decimal("-19.00"))
        _link(cur, v1, tx, Decimal("-100.00"))
        _link(cur, v2, tx, Decimal("-19.00"))

        linked, count = _linked_sum(cur, tx)

    assert count == 2
    assert linked == Decimal("-119.00")
    assert _is_balanced(Decimal("-119.00"), linked)


def test_partial_link_is_unbalanced(db_conn):
    """Fehlt ein Beleg, ist die Differenz größer als die Toleranz."""
    with db_conn.cursor() as cur:
        acc = _make_account(cur)
        tx = _make_transaction(cur, acc, Decimal("-119.00"))
        v1 = _make_voucher(cur, Decimal("-100.00"))
        _link(cur, v1, tx, Decimal("-100.00"))

        linked, count = _linked_sum(cur, tx)

    assert count == 1
    assert linked == Decimal("-100.00")
    assert not _is_balanced(Decimal("-119.00"), linked)


def test_rounding_within_tolerance_is_balanced(db_conn):
    """Cent-Differenzen innerhalb der Toleranz (0,50 €) gelten als ausgeglichen."""
    with db_conn.cursor() as cur:
        acc = _make_account(cur)
        tx = _make_transaction(cur, acc, Decimal("-119.00"))
        v1 = _make_voucher(cur, Decimal("-118.70"))
        _link(cur, v1, tx, Decimal("-118.70"))

        linked, _ = _linked_sum(cur, tx)

    assert _is_balanced(Decimal("-119.00"), linked)  # Δ = 0,30 € ≤ 0,50 €
