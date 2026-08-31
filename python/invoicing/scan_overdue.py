#!/usr/bin/env python3
"""List invoices that are past their due date.

Scans data/invoice_*.yaml (paid invoices are expected to be moved to an
archive folder manually). Due date follows the same rule as render_dunning.py:
an explicit `due_date`, otherwise issue_date + payment.terms_days.
"""

import argparse
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import yaml

DATA_DIR = Path(__file__).parent / "data"


def parse_date(value):
    if isinstance(value, date):
        return value
    return datetime.strptime(str(value), "%Y-%m-%d").date()


def gross_total(data):
    total = Decimal("0.00")
    for line in data.get("lines", []):
        total += Decimal(str(line["quantity"])) * Decimal(str(line["unit_price"]))
        rate = Decimal(str(line.get("tax", data.get("tax", {})).get("rate", 0)))
        total += (
            Decimal(str(line["quantity"]))
            * Decimal(str(line["unit_price"]))
            * rate
            / 100
        )
    return total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def collect(data_dir, today):
    rows = []
    for path in sorted(data_dir.glob("invoice_*.yaml")):
        try:
            data = yaml.safe_load(path.read_text(encoding="utf-8"))
        except yaml.YAMLError as exc:
            print(f"WARN: skipping {path.name}: {exc}", file=sys.stderr)
            continue

        invoice = data.get("invoice", {})
        issue_date = parse_date(invoice.get("issue_date"))
        terms_days = int(data.get("payment", {}).get("terms_days", 14))

        if data.get("due_date"):
            due_date = parse_date(data["due_date"])
        else:
            due_date = issue_date + timedelta(days=terms_days)

        rows.append(
            {
                "file": path.name,
                "number": invoice.get("number", path.stem),
                "buyer": data.get("buyer", {}).get("name", "?"),
                "due_date": due_date,
                "days": (today - due_date).days,
                "gross": gross_total(data),
                "dunning": data.get("dunning", {}).get("level"),
            }
        )
    return rows


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--all", action="store_true", help="also list not-yet-due invoices")
    ap.add_argument("--today", help="override current date (YYYY-MM-DD), for testing")
    ap.add_argument("--dir", default=str(DATA_DIR), help="data directory to scan")
    args = ap.parse_args()

    today = parse_date(args.today) if args.today else date.today()
    rows = collect(Path(args.dir), today)

    if not args.all:
        rows = [r for r in rows if r["days"] > 0]
    rows.sort(key=lambda r: r["days"], reverse=True)

    if not rows:
        print("No overdue invoices.")
        return

    header = f"{'Invoice':<16} {'Buyer':<40} {'Due':<12} {'Days':>5} {'Gross':>12}  Dunning"
    print(header)
    print("-" * len(header))
    total = Decimal("0.00")
    for r in rows:
        total += r["gross"]
        dunning = f"level {r['dunning']}" if r["dunning"] else ""
        print(
            f"{r['number']:<16} {r['buyer'][:40]:<40} {r['due_date'].isoformat():<12} "
            f"{r['days']:>5} {r['gross']:>12,.2f}  {dunning}"
        )
    print("-" * len(header))
    print(f"{len(rows)} invoice(s), {total:,.2f} EUR open (as of {today.isoformat()})")


if __name__ == "__main__":
    main()
