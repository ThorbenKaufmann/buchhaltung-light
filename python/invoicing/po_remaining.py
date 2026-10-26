#!/usr/bin/env python3
"""Show what is left on a customer purchase order (reorder alarm).

Looks up the customer PO in data/poin_*.yaml (by customer PO number, our
order-confirmation number or the quote number) and subtracts every line of
data/invoice_*.yaml whose invoice.po_number matches. Lines are matched by
assigned_id; zero-quantity PO lines (notes) are ignored. Invoice lines with an
unknown assigned_id or a different unit_price (e.g. a forfeited-discount
surcharge) are reported but not counted against the PO.

The burn rate is taken from the invoiced service periods and used to project
when the PO runs out. The alarm fires when the remaining share drops below
--warn percent or the projected run-out lies within --weeks weeks; the exit
code is then 2, so the script can be used in cron jobs.
"""

import argparse
import sys
from datetime import date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import yaml

from scan_overdue import parse_date

DATA_DIR = Path(__file__).parent / "data"
EXIT_ALARM = 2


def dec(value):
    return Decimal(str(value))


def load_yaml(path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        print(f"WARN: skipping {path.name}: {exc}", file=sys.stderr)
        return None


def load_orders(data_dir):
    orders = []
    for path in sorted(data_dir.glob("poin_*.yaml")):
        data = load_yaml(path)
        if data and data.get("purchase", {}).get("po_number"):
            orders.append((path, data))
    return orders


def find_order(orders, key):
    for path, data in orders:
        purchase = data["purchase"]
        keys = {
            str(purchase.get("po_number", "")),
            str(purchase.get("number", "")),
            str(purchase.get("quote", "")),
            str(data.get("quote", {}).get("number", "")),
        }
        if key in keys:
            return path, data
    return None


def load_invoices(data_dir, po_number):
    invoices = []
    for path in sorted(data_dir.glob("invoice_*.yaml")):
        data = load_yaml(path)
        if data and str(data.get("invoice", {}).get("po_number", "")) == po_number:
            invoices.append(data)
    invoices.sort(key=lambda d: parse_date(d["invoice"]["issue_date"]))
    return invoices


def analyse(order, invoices):
    lines = {}
    for line in order.get("lines", []):
        if dec(line["quantity"]) == 0:
            continue
        lines[str(line["assigned_id"])] = {
            "id": str(line["assigned_id"]),
            "name": line["name"],
            "unit": line.get("unit_code", ""),
            "price": dec(line["unit_price"]),
            "ordered": dec(line["quantity"]),
            "invoiced": Decimal("0"),
        }

    skipped = []
    for inv in invoices:
        number = inv["invoice"]["number"]
        for line in inv.get("lines", []):
            qty = dec(line["quantity"])
            if qty == 0:
                continue
            target = lines.get(str(line["assigned_id"]))
            if target is None:
                skipped.append(f"{number}: '{line['name']}' (id {line['assigned_id']}) not on PO")
            elif dec(line["unit_price"]) != target["price"]:
                skipped.append(
                    f"{number}: '{line['name']}' {qty} x {dec(line['unit_price']):.2f} "
                    f"(PO price {target['price']:.2f}) not counted"
                )
            else:
                target["invoiced"] += qty

    for line in lines.values():
        line["remaining"] = line["ordered"] - line["invoiced"]
        line["value"] = (line["remaining"] * line["price"]).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
        line["pct"] = (
            line["remaining"] / line["ordered"] * 100 if line["ordered"] else Decimal("0")
        )
    return list(lines.values()), skipped


def service_span(invoices):
    """First service start and last service end over all invoices (or None)."""
    starts, ends = [], []
    for inv in invoices:
        period = inv["invoice"].get("service_period") or {}
        if period.get("start") and period.get("end"):
            starts.append(parse_date(period["start"]))
            ends.append(parse_date(period["end"]))
    if not starts:
        return None
    return min(starts), max(ends)


def project(line, span):
    """Projected run-out date for one PO line, based on the invoiced burn rate."""
    if span is None or line["invoiced"] <= 0:
        return None
    days = (span[1] - span[0]).days + 1
    per_day = line["invoiced"] / days
    if line["remaining"] <= 0:
        return span[1]
    return span[1] + timedelta(days=int(line["remaining"] / per_day))


def report(path, order, invoices, today, warn_pct, warn_weeks):
    purchase = order["purchase"]
    buyer = order.get("buyer", {}).get("name", "?")
    period = order.get("quote", {}).get("service_period") or {}
    lines, skipped = analyse(order, invoices)
    span = service_span(invoices)

    print(f"PO {purchase['po_number']}  —  {buyer}")
    print(
        f"Order confirmation {purchase.get('number', '?')} (quote {purchase.get('quote', '?')}), "
        f"ordered {purchase.get('order_date', '?')}, file {path.name}"
    )
    if period:
        print(f"PO period {period.get('start')} .. {period.get('end')}")
    print()

    if invoices:
        print("Invoices against this PO:")
        for inv in invoices:
            head = inv["invoice"]
            sp = head.get("service_period") or {}
            qty = sum(
                (dec(l["quantity"]) for l in inv.get("lines", []) if str(l["assigned_id"]) in
                 {x["id"] for x in lines}),
                Decimal("0"),
            )
            print(f"  {head['number']}  {head['issue_date']}  "
                  f"{sp.get('start', '?')} .. {sp.get('end', '?')}  {qty:>10,.2f}")
    else:
        print("No invoices against this PO yet.")
    print()

    header = (
        f"{'ID':<6} {'Item':<42} {'Unit':<5} {'Ordered':>10} {'Invoiced':>10} "
        f"{'Left':>10} {'Left %':>7} {'Left EUR':>12}  Runs out ~"
    )
    print(header)
    print("-" * len(header))
    alarms = []
    po_end = parse_date(period["end"]) if period.get("end") else None
    for line in lines:
        runout = project(line, span)
        print(
            f"{line['id']:<6} {line['name'][:42]:<42} {line['unit']:<5} "
            f"{line['ordered']:>10,.2f} {line['invoiced']:>10,.2f} {line['remaining']:>10,.2f} "
            f"{line['pct']:>6.1f}% {line['value']:>12,.2f}  {runout.isoformat() if runout else '-'}"
        )
        if line["remaining"] <= 0:
            alarms.append(f"{line['id']}: PO line exhausted ({line['remaining']:,.2f} {line['unit']})")
        elif line["pct"] < warn_pct:
            alarms.append(f"{line['id']}: only {line['pct']:.1f}% left (< {warn_pct:g}%)")
        if runout and line["remaining"] > 0 and runout <= today + timedelta(weeks=warn_weeks):
            alarms.append(
                f"{line['id']}: projected to run out ~{runout.isoformat()} "
                f"(within {warn_weeks:g} weeks)"
            )
        if runout and po_end and line["remaining"] > 0 and runout < po_end:
            print(f"       note: runs out before PO period end {po_end.isoformat()}")
    print("-" * len(header))
    total = sum((l["value"] for l in lines), Decimal("0"))
    print(f"{total:,.2f} {order.get('quote', {}).get('currency', 'EUR')} left on PO "
          f"(as of {today.isoformat()})")

    if span:
        days = (span[1] - span[0]).days + 1
        for line in lines:
            if line["invoiced"] > 0:
                per_week = line["invoiced"] / days * 7
                print(f"Burn rate {line['id']}: {per_week:,.1f} {line['unit']}/week "
                      f"over {span[0].isoformat()} .. {span[1].isoformat()}")

    for msg in skipped:
        print(f"WARN: {msg}", file=sys.stderr)

    if alarms:
        print()
        print("*** REORDER ALARM ***")
        for msg in alarms:
            print(f"  {msg}")
    return bool(alarms)


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("po", nargs="?",
                    help="customer PO number, order confirmation (PI…) or quote (AN…) number; "
                         "omit to check all customer POs")
    ap.add_argument("--warn", type=float, default=25.0,
                    help="alarm when less than this percentage is left (default 25)")
    ap.add_argument("--weeks", type=float, default=6.0,
                    help="alarm when the projected run-out is within this many weeks (default 6)")
    ap.add_argument("--today", help="override current date (YYYY-MM-DD), for testing")
    ap.add_argument("--dir", default=str(DATA_DIR), help="data directory to scan")
    args = ap.parse_args()

    today = parse_date(args.today) if args.today else date.today()
    data_dir = Path(args.dir)
    orders = load_orders(data_dir)

    if args.po:
        found = find_order(orders, args.po)
        if found is None:
            known = ", ".join(str(d["purchase"]["po_number"]) for _, d in orders) or "none"
            sys.exit(f"PO '{args.po}' not found in {data_dir}/poin_*.yaml (known: {known})")
        orders = [found]
    elif not orders:
        sys.exit(f"No customer POs (poin_*.yaml with purchase.po_number) in {data_dir}")

    alarm = False
    for i, (path, order) in enumerate(orders):
        if i:
            print("\n" + "=" * 100 + "\n")
        invoices = load_invoices(data_dir, str(order["purchase"]["po_number"]))
        alarm |= report(path, order, invoices, today, args.warn, args.weeks)

    sys.exit(EXIT_ALARM if alarm else 0)


if __name__ == "__main__":
    main()
