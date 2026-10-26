#!/usr/bin/env python3
"""Quote pipeline: which quotes are open, lapsed, ordered or closed.

Scans data/quote_*.yaml. A quote counts as *ordered* when a data/poin_*.yaml
references it (purchase.quote or quote.number); the remaining PO value is then
taken from po_remaining.py, i.e. what can still be invoiced. Quotes can be
closed by hand with a top-level `status:` block (state rejected or expired),
written by the `mark` command and removed again by `reopen`. `accept` turns a
quote into a customer order: it writes data/poin_*.yaml (the quote plus a
`purchase:` block) for render_order_confirmation.py. Everything else is *open* until its validity
ends (same rule as render_quote.py: an explicit `due_date`, otherwise
issue_date + payment.terms_days) and *lapsed* afterwards — a lapsed quote is
a candidate for `mark ... expired`.

Examples:
  python3 quotes.py                      # open, lapsed and ordered-with-budget-left
  python3 quotes.py --all                # also closed and fully invoiced
  python3 quotes.py mark AN20260003 rejected --note "went with in-house team"
  python3 quotes.py mark AN20260004 expired --dry-run
  python3 quotes.py reopen AN20260004
  python3 quotes.py accept AN20260007 --po 5000225603 --order-date 2026-10-12
"""

import argparse
import contextlib
import io
import json
import re
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import yaml

from po_remaining import analyse, load_invoices, load_orders, load_yaml
from record_payment import TOP_LEVEL_KEY
from scan_overdue import DATA_DIR, parse_date

CLOSED_STATES = ("rejected", "expired")
QUOTE_NO = re.compile(r"AN\d{8}")


def net_total(data):
    total = sum(
        (Decimal(str(l["quantity"])) * Decimal(str(l["unit_price"])) for l in data.get("lines", [])),
        Decimal("0"),
    )
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def valid_until(data):
    if data.get("due_date"):
        return parse_date(data["due_date"])
    issue_date = parse_date(data["quote"]["issue_date"])
    return issue_date + timedelta(days=int(data.get("payment", {}).get("terms_days", 30)))


def quote_number(path, data):
    """Quote number from the file name; warns if the YAML says otherwise."""
    match = QUOTE_NO.search(path.stem)
    number = str(data.get("quote", {}).get("number", ""))
    if match and number and match.group(0) != number:
        print(f"WARN: {path.name}: quote.number is {number}, file name says {match.group(0)}",
              file=sys.stderr)
    return match.group(0) if match else number or path.stem


def order_for(orders, number):
    for path, data in orders:
        refs = {str(data["purchase"].get("quote", "")), str(data.get("quote", {}).get("number", ""))}
        if number in refs:
            return path, data
    return None


def collect(data_dir, today):
    orders = load_orders(data_dir)
    rows = []
    for path in sorted(data_dir.glob("quote_*.yaml")):
        data = load_yaml(path)
        if not data or "quote" not in data:
            continue
        number = quote_number(path, data)
        until = valid_until(data)
        row = {
            "file": path.name,
            "path": path,
            "number": number,
            "buyer": data.get("buyer", {}).get("name", "?"),
            "reference": data["quote"].get("buyer_reference", ""),
            "issue_date": parse_date(data["quote"]["issue_date"]),
            "valid_until": until,
            "net": net_total(data),
            "po": None,
            "left": None,
            "note": "",
        }

        found = order_for(orders, number)
        status = data.get("status") or {}
        if found:
            order = found[1]
            po_number = str(order["purchase"]["po_number"])
            lines, _ = analyse(order, load_invoices(data_dir, po_number))
            row["state"] = "ordered"
            row["po"] = po_number
            row["left"] = sum((l["value"] for l in lines), Decimal("0"))
            row["note"] = f"{order['purchase'].get('number', '')} {order['purchase'].get('order_date', '')}"
        elif status.get("state") in CLOSED_STATES:
            row["state"] = status["state"]
            row["note"] = " ".join(str(x) for x in (status.get("date", ""), status.get("note", "")) if x)
        elif until >= today:
            row["state"] = "open"
            row["note"] = f"{(until - today).days} days left"
        else:
            row["state"] = "lapsed"
            row["note"] = f"expired {(today - until).days} days ago, mark it"
        rows.append(row)
    return rows


def visible(row):
    """Rows shown without --all."""
    if row["state"] in ("open", "lapsed"):
        return True
    return row["state"] == "ordered" and row["left"] > 0


def print_table(rows, today):
    header = (
        f"{'Quote':<11} {'Buyer':<30} {'Ref':<8} {'Issued':<10} {'Valid to':<10} "
        f"{'Net':>12}  {'State':<8} {'PO':<11} {'Left EUR':>12}  Note"
    )
    print(header)
    print("-" * len(header))
    for r in rows:
        left = f"{r['left']:>12,.2f}" if r["left"] is not None else f"{'':>12}"
        print(
            f"{r['number']:<11} {r['buyer'][:30]:<30} {r['reference'][:8]:<8} "
            f"{r['issue_date'].isoformat():<10} {r['valid_until'].isoformat():<10} "
            f"{r['net']:>12,.2f}  {r['state']:<8} {r['po'] or '':<11} {left}  {r['note']}"
        )
    print("-" * len(header))

    def total(state, key):
        return sum((r[key] for r in rows if r["state"] == state), Decimal("0"))

    print(f"Open quotes {total('open', 'net'):,.2f} EUR, lapsed {total('lapsed', 'net'):,.2f} EUR, "
          f"left to invoice on POs {total('ordered', 'left'):,.2f} EUR (as of {today.isoformat()})")


def status_block(state, when, note):
    lines = [
        "status:",
        f'  state: "{state}"',
        f'  date: "{when.isoformat()}"',
    ]
    if note:
        # JSON strings are valid YAML double-quoted scalars
        lines.append(f"  note: {json.dumps(note, ensure_ascii=False)}")
    return lines


def block_range(lines, key):
    """(start, end) of a top-level block; trailing blank/comment lines stay outside."""
    start = next((i for i, l in enumerate(lines) if re.match(rf"^{key}\s*:", l)), None)
    if start is None:
        return None
    end = next((i for i in range(start + 1, len(lines)) if TOP_LEVEL_KEY.match(lines[i])), len(lines))
    while end > start + 1 and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
        end -= 1
    return start, end


def set_status(text, block):
    """Return `text` with its top-level `status:` block replaced or appended."""
    lines = text.splitlines()
    found = block_range(lines, "status")
    if found is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += [""] + block
    else:
        lines[found[0]:found[1]] = block
    return "\n".join(lines) + "\n"


def drop_status(text):
    """Return `text` without its top-level `status:` block."""
    lines = text.splitlines()
    found = block_range(lines, "status")
    if found:
        del lines[found[0]:found[1]]
        while lines and not lines[-1].strip():
            lines.pop()
    return "\n".join(lines) + "\n"


def find_row(number, data_dir):
    with contextlib.redirect_stderr(io.StringIO()):
        row = next((r for r in collect(data_dir, date.today()) if r["number"] == number), None)
    if row is None:
        sys.exit(f"ERROR: quote {number} not found in {data_dir}/quote_*.yaml")
    return row


def mark(number, state, when, note, data_dir, force=False, dry_run=False):
    """Close a quote as rejected/expired. Returns a message; raises SystemExit on refusal."""
    row = find_row(number, data_dir)
    if row["state"] == "ordered":
        sys.exit(f"ERROR: {number} has a customer order (PO {row['po']}), not marking it {state}")
    if row["state"] in CLOSED_STATES and not force:
        sys.exit(f"ERROR: {number} is already {row['state']} ({row['note']}), use --force to change")
    if state == "expired" and when < row["valid_until"] and not force:
        sys.exit(f"ERROR: {number} is valid until {row['valid_until']}, use --force to expire it early")

    path = row["path"]
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    block = status_block(state, when, note)
    new_text = set_status(text, block)

    # verify the edit parses and changed nothing but the status block
    new_data = yaml.safe_load(new_text)
    expected = {"state": state, "date": when.isoformat()}
    if note:
        expected["note"] = note
    rest_old = {k: v for k, v in data.items() if k != "status"}
    rest_new = {k: v for k, v in new_data.items() if k != "status"}
    if new_data.get("status") != expected or rest_old != rest_new:
        sys.exit("ERROR: YAML edit did not verify, nothing written. Please add the status by hand.")

    if dry_run:
        return "\n".join(block) + f"\n[dry-run] {number}: would be marked {state} in {path.name}"
    path.write_text(new_text, encoding="utf-8")
    return f"{number}: marked {state} on {when} in {path.name}"


def reopen(number, data_dir, dry_run=False):
    """Remove the status block of a rejected/expired quote."""
    row = find_row(number, data_dir)
    if row["state"] not in CLOSED_STATES:
        sys.exit(f"ERROR: {number} is {row['state']}, nothing to reopen")
    path = row["path"]
    text = path.read_text(encoding="utf-8")
    data = yaml.safe_load(text)
    new_text = drop_status(text)
    if yaml.safe_load(new_text) != {k: v for k, v in data.items() if k != "status"}:
        sys.exit("ERROR: YAML edit did not verify, nothing written. Please remove the status by hand.")
    if dry_run:
        return f"[dry-run] {number}: status '{row['state']}' would be removed from {path.name}"
    path.write_text(new_text, encoding="utf-8")
    return f"{number}: reopened ({row['state']} removed from {path.name})"


def next_order_number(data_dir, year):
    """Next order confirmation number PI<year><nnnn> after the existing poin files."""
    pattern = re.compile(rf"PI{year}(\d{{4}})")
    numbers = [
        int(m.group(1)) for _, d in load_orders(data_dir)
        if (m := pattern.fullmatch(str(d["purchase"].get("number", ""))))
    ]
    return f"PI{year}{max(numbers, default=0) + 1:04d}"


def accept(number, po_number, order_date, data_dir, confirmation_date=None, pi_number=None,
           dry_run=False):
    """Turn a quote into a customer order: write data/poin_*.yaml. Returns (message, path)."""
    row = find_row(number, data_dir)
    if row["state"] == "ordered":
        sys.exit(f"ERROR: {number} is already ordered (PO {row['po']})")
    for path, order in load_orders(data_dir):
        if str(order["purchase"]["po_number"]) == po_number:
            sys.exit(f"ERROR: PO {po_number} is already used in {path.name}")
    target = data_dir / row["file"].replace("quote_", "poin_", 1)
    if target.exists():
        sys.exit(f"ERROR: {target.name} already exists")
    pi_number = pi_number or next_order_number(data_dir, (confirmation_date or order_date).year)

    text = drop_status(row["path"].read_text(encoding="utf-8"))
    data = yaml.safe_load(text)
    block = [
        "purchase:",
        f'  number:           "{pi_number}"      # Billing/Order Reference',
        f'  quote:            "{number}"      # Angebotsnummer',
        f'  order_date:       "{order_date.isoformat()}"      # Bestelldatum',
    ]
    if confirmation_date:
        block.append(f'  confirmation_date: "{confirmation_date.isoformat()}"     '
                     f'# Datum der Auftragsbestätigung (Briefdatum)')
    block.append(f'  po_number:        {json.dumps(po_number)}      # Kunden PO')

    # the purchase block goes right after the quote block, as in the existing poin files
    lines = text.splitlines()
    quote_end = block_range(lines, "quote")[1]
    insert_at = next((i for i in range(quote_end, len(lines)) if TOP_LEVEL_KEY.match(lines[i])), len(lines))
    lines[insert_at:insert_at] = block + [""]
    new_text = "\n".join(lines) + "\n"

    # verify: same as the quote plus exactly the purchase block
    new_data = yaml.safe_load(new_text)
    expected = {"number": pi_number, "quote": number, "order_date": order_date.isoformat(),
                "po_number": po_number}
    if confirmation_date:
        expected["confirmation_date"] = confirmation_date.isoformat()
    rest_new = {k: v for k, v in new_data.items() if k != "purchase"}
    if new_data.get("purchase") != expected or rest_new != data:
        sys.exit("ERROR: YAML edit did not verify, nothing written. Please create the poin file by hand.")

    if dry_run:
        return "\n".join(block) + f"\n[dry-run] {number}: would write {target.name}", target
    target.write_text(new_text, encoding="utf-8")
    return f"{number}: ordered, PO {po_number}, {pi_number} -> {target.name}", target


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("--all", action="store_true", help="also list closed and fully invoiced quotes")
    ap.add_argument("--today", help="override current date (YYYY-MM-DD), for testing")
    ap.add_argument("--dir", default=str(DATA_DIR), help="data directory to scan")
    sub = ap.add_subparsers(dest="command")
    mk = sub.add_parser("mark", help="close a quote as rejected or expired")
    mk.add_argument("quote", help="quote number, e.g. AN20260003")
    mk.add_argument("state", choices=CLOSED_STATES)
    mk.add_argument("--date", help="date of the decision (YYYY-MM-DD), default today")
    mk.add_argument("--note", help="short reason, e.g. 'customer chose another supplier'")
    mk.add_argument("--force", action="store_true", help="overwrite an existing status / expire early")
    mk.add_argument("--dry-run", action="store_true", help="show the result, don't write")
    ro = sub.add_parser("reopen", help="remove a rejected/expired status again")
    ro.add_argument("quote", help="quote number")
    ro.add_argument("--dry-run", action="store_true", help="show the result, don't write")
    ac = sub.add_parser("accept", help="customer ordered: write data/poin_*.yaml")
    ac.add_argument("quote", help="quote number")
    ac.add_argument("--po", required=True, help="customer PO number")
    ac.add_argument("--order-date", required=True, help="date on the customer PO (YYYY-MM-DD)")
    ac.add_argument("--confirmation-date", help="letter date of our confirmation, default today")
    ac.add_argument("--pi", help="order confirmation number, default next PI<year><nnnn>")
    ac.add_argument("--dry-run", action="store_true", help="show the result, don't write")
    args = ap.parse_args()

    data_dir = Path(args.dir)
    if args.command == "mark":
        when = parse_date(args.date) if args.date else date.today()
        print(mark(args.quote, args.state, when, args.note, data_dir, args.force, args.dry_run))
        return
    if args.command == "reopen":
        print(reopen(args.quote, data_dir, args.dry_run))
        return
    if args.command == "accept":
        confirmed = parse_date(args.confirmation_date) if args.confirmation_date else date.today()
        message, _ = accept(args.quote, args.po, parse_date(args.order_date), data_dir,
                            confirmed, args.pi, args.dry_run)
        print(message)
        return

    today = parse_date(args.today) if args.today else date.today()
    rows = collect(data_dir, today)
    if not args.all:
        rows = [r for r in rows if visible(r)]
    if not rows:
        print("No open quotes.")
        return
    print_table(rows, today)


if __name__ == "__main__":
    main()
