#!/usr/bin/env python3
"""Quote pipeline: which quotes are open, lapsed, ordered or closed.

Scans data/quote_*.yaml. A quote counts as *ordered* when a data/poin_*.yaml
references it (purchase.quote or quote.number); the remaining PO value is then
taken from po_remaining.py, i.e. what can still be invoiced. Quotes can be
closed by hand with a top-level `status:` block (state rejected or expired),
written by the `mark` command. Everything else is *open* until its validity
ends (same rule as render_quote.py: an explicit `due_date`, otherwise
issue_date + payment.terms_days) and *lapsed* afterwards — a lapsed quote is
a candidate for `mark ... expired`.

Examples:
  python3 quotes.py                      # open, lapsed and ordered-with-budget-left
  python3 quotes.py --all                # also closed and fully invoiced
  python3 quotes.py mark AN20260003 rejected --note "went with in-house team"
  python3 quotes.py mark AN20260004 expired --dry-run
"""

import argparse
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


def set_status(text, block):
    """Return `text` with its top-level `status:` block replaced or appended."""
    lines = text.splitlines()
    start = next((i for i, l in enumerate(lines) if re.match(r"^status\s*:", l)), None)
    if start is None:
        while lines and not lines[-1].strip():
            lines.pop()
        lines += [""] + block
    else:
        end = next((i for i in range(start + 1, len(lines)) if TOP_LEVEL_KEY.match(lines[i])), len(lines))
        while end > start + 1 and (not lines[end - 1].strip() or lines[end - 1].lstrip().startswith("#")):
            end -= 1
        lines[start:end] = block
    return "\n".join(lines) + "\n"


def mark(number, state, when, note, data_dir, force=False, dry_run=False):
    """Close a quote as rejected/expired. Returns a message; raises SystemExit on refusal."""
    row = next((r for r in collect(data_dir, date.today()) if r["number"] == number), None)
    if row is None:
        sys.exit(f"ERROR: quote {number} not found in {data_dir}/quote_*.yaml")
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
    args = ap.parse_args()

    data_dir = Path(args.dir)
    if args.command == "mark":
        when = parse_date(args.date) if args.date else date.today()
        print(mark(args.quote, args.state, when, args.note, data_dir, args.force, args.dry_run))
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
