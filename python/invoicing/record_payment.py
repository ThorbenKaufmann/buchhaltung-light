#!/usr/bin/env python3
"""Record a received payment in an invoice YAML.

Appends an entry to the invoice's `payments:` block (creating the block at the
end of the file if needed). The file is edited as text, not re-dumped, so
comments and formatting stay intact; the result is re-parsed and verified
before it is written.

This only tracks open items for scan_overdue.py / render_dunning.py. The
accounting side (linking the bank transaction to the outgoing voucher) is
done separately in the bookkeeping DB.

Examples:
  python3 record_payment.py RE20260002 --date 2026-09-18 --reference "Sunlight RE20260002"
  python3 record_payment.py RE20260002 --date 2026-09-18 --amount 5000.00 --dry-run
"""

import argparse
import json
import re
import sys
from datetime import date
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import yaml

from scan_overdue import DATA_DIR, gross_total, paid_total, parse_date

TOP_LEVEL_KEY = re.compile(r"^[A-Za-z_][\w-]*\s*:")


def resolve_invoice(arg, data_dir):
    path = Path(arg)
    if path.is_file():
        return path
    path = data_dir / f"invoice_{arg}.yaml"
    if path.is_file():
        return path
    sys.exit(f"ERROR: invoice not found: {arg} (looked for {path})")


def parse_amount(value):
    try:
        amount = Decimal(value.replace(",", "."))
    except InvalidOperation:
        sys.exit(f"ERROR: invalid amount: {value}")
    if amount <= 0:
        sys.exit(f"ERROR: amount must be positive: {value}")
    return amount.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def payment_entry(pay_date, amount, reference):
    lines = [
        f'  - date: "{pay_date.isoformat()}"',
        f"    amount: {amount}",
    ]
    if reference:
        # JSON strings are valid YAML double-quoted scalars
        lines.append(f"    reference: {json.dumps(reference, ensure_ascii=False)}")
    return lines


def insert_payment(text, entry):
    """Return `text` with `entry` appended to the top-level `payments:` block."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if re.match(r"^payments\s*:", l)), None)

    if start is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += ["", "payments:"] + entry
        return "\n".join(lines) + "\n"

    if lines[start].split(":", 1)[1].split("#", 1)[0].strip():
        sys.exit("ERROR: `payments:` is not a block list (inline value?), please fix by hand")

    # block ends at the next top-level key; trailing blank/comment lines stay after it
    end = next((i for i in range(start + 1, len(lines)) if TOP_LEVEL_KEY.match(lines[i])), len(lines))
    while end > start + 1 and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
        end -= 1
    lines[end:end] = entry
    return "\n".join(lines) + "\n"


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("invoice", help="invoice number (e.g. RE20260002) or path to the YAML")
    ap.add_argument("--date", help="value date of the payment (YYYY-MM-DD), default today")
    ap.add_argument("--amount", help="amount received, default the full open amount")
    ap.add_argument("--reference", help="bank reference / Verwendungszweck")
    ap.add_argument("--force", action="store_true", help="allow overpayment and duplicate entries")
    ap.add_argument("--dry-run", action="store_true", help="show the result, don't write")
    ap.add_argument("--dir", default=str(DATA_DIR), help="data directory")
    args = ap.parse_args()

    path = resolve_invoice(args.invoice, Path(args.dir))
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)

    number = data.get("invoice", {}).get("number", path.stem)
    gross = gross_total(data)
    paid = paid_total(data)
    open_amount = gross - paid

    pay_date = parse_date(args.date) if args.date else date.today()
    issue_date = parse_date(data["invoice"]["issue_date"])
    if pay_date < issue_date:
        sys.exit(f"ERROR: payment date {pay_date} is before issue date {issue_date}")
    if pay_date > date.today():
        sys.exit(f"ERROR: payment date {pay_date} is in the future")

    if args.amount:
        amount = parse_amount(args.amount)
    elif open_amount > 0:
        amount = open_amount
    else:
        sys.exit(f"ERROR: {number} is already fully paid ({paid:,.2f} of {gross:,.2f} EUR)")

    problems = []
    for p in data.get("payments") or []:
        if parse_date(p["date"]) == pay_date and Decimal(str(p["amount"])) == amount:
            problems.append(f"duplicate: {amount:,.2f} EUR on {pay_date} is already recorded")
    if amount > open_amount:
        problems.append(f"overpayment: {amount:,.2f} EUR received, only {open_amount:,.2f} EUR open")
    if problems and not args.force:
        for msg in problems:
            print(f"ERROR: {msg}", file=sys.stderr)
        sys.exit("Nothing written. Use --force if this is intended.")
    for msg in problems:
        print(f"WARN: {msg}", file=sys.stderr)

    entry = payment_entry(pay_date, amount, args.reference)
    new_text = insert_payment(text, entry)

    # verify the edit parses and changed nothing but the payments list
    new_data = yaml.safe_load(new_text)
    old_payments = data.get("payments") or []
    new_payments = new_data.get("payments") or []
    expected = {"date": pay_date.isoformat(), "amount": float(amount)}
    if args.reference:
        expected["reference"] = args.reference
    rest_old = {k: v for k, v in data.items() if k != "payments"}
    rest_new = {k: v for k, v in new_data.items() if k != "payments"}
    if new_payments != old_payments + [expected] or rest_old != rest_new:
        sys.exit("ERROR: YAML edit did not verify, nothing written. Please add the payment by hand.")

    remaining = open_amount - amount
    status = "fully paid" if remaining <= 0 else f"{remaining:,.2f} EUR still open"

    if args.dry_run:
        print("\n".join(entry))
        print(f"[dry-run] {number}: +{amount:,.2f} EUR on {pay_date} -> {status}")
        return

    path.write_text(new_text, encoding="utf-8")
    print(f"{number}: recorded {amount:,.2f} EUR on {pay_date} in {path.name} -> {status}")


if __name__ == "__main__":
    main()
