#!/usr/bin/env python3
"""Create an invoice against a customer PO.

Takes the customer order data/poin_*.yaml (found by customer PO number, our
order confirmation PI… or the quote AN…), turns its `quote:` block into an
`invoice:` block and sets the quantities to bill; the result is written to
data/invoice_RE<year><nnnn>.yaml, ready for render_invoice.py (--render does
that right away, German template for German buyers, English otherwise).

Defaults: the service period starts the day after the last invoice on this
PO (or at the PO start) and ends at the end of that month; the invoice number
is the next free RE<year><nnnn>. Refused unless --force: billing more than is
left on a PO line, a period outside the PO period, a period overlapping an
earlier invoice on this PO.

--from-timelog takes the hours from timelog.py: the not yet billed entries of
this PO in the period, rounded as in the activity report, go onto the hourly
line, and those entries get the invoice number so they can't be billed twice.

Examples:
  python3 invoice_po.py 5000225603 --qty 1000=120.5 --dry-run
  python3 invoice_po.py 5000225603 --qty 1000=120.5 --period 2026-11-01..2026-11-27 --render
  python3 invoice_po.py 5000225603 --from-timelog --period 2026-11-01..2026-11-27 --render
"""

import argparse
import calendar
import json
import re
import subprocess
import sys
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from pathlib import Path

import yaml

import timelog
from po_remaining import analyse, find_order, load_invoices, load_orders, load_yaml
from quotes import block_range, drop_status
from scan_overdue import DATA_DIR, parse_date

HERE = Path(__file__).parent


def load_po(key, data_dir):
    """(path, order, invoices) for a PO / PI / AN number."""
    found = find_order(load_orders(data_dir), key)
    if found is None:
        sys.exit(f"ERROR: no customer order for '{key}' in {data_dir}/poin_*.yaml")
    path, order = found
    return path, order, load_invoices(data_dir, str(order["purchase"]["po_number"]))


def po_period(order):
    period = order.get("quote", {}).get("service_period") or {}
    if period.get("start") and period.get("end"):
        return parse_date(period["start"]), parse_date(period["end"])
    return None


def invoice_periods(invoices):
    for inv in invoices:
        period = inv["invoice"].get("service_period") or {}
        if period.get("start") and period.get("end"):
            yield inv["invoice"]["number"], parse_date(period["start"]), parse_date(period["end"])


def default_period(order, invoices, today):
    """Day after the last invoiced period (or PO start) .. end of that month."""
    ends = [end for _, _, end in invoice_periods(invoices)]
    if ends:
        start = max(ends) + timedelta(days=1)
    elif po_period(order):
        start = po_period(order)[0]
    else:
        start = today.replace(day=1)
    end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
    return start, end


def next_invoice_number(data_dir, year):
    pattern = re.compile(rf"RE{year}(\d{{4}})")
    numbers = []
    for path in data_dir.glob("invoice_*.yaml"):
        data = load_yaml(path)
        m = pattern.fullmatch(str((data or {}).get("invoice", {}).get("number", "")))
        if m:
            numbers.append(int(m.group(1)))
    return f"RE{year}{max(numbers, default=0) + 1:04d}"


def hour_line(order):
    """assigned_id of the single hourly PO line (unit HUR), or None."""
    ids = [str(l["assigned_id"]) for l in order.get("lines", [])
           if l.get("unit_code") == "HUR" and Decimal(str(l["quantity"])) != 0]
    return ids[0] if len(ids) == 1 else None


def template_for(order):
    buyer = order.get("buyer", {})
    country = str(buyer.get("country_code") or buyer.get("country") or "").upper()
    lang = "de" if country in ("DE", "GERMANY", "DEUTSCHLAND") else "en"
    return f"templates/invoice.{lang}.tex.j2"


def parse_qty(value):
    try:
        qty = Decimal(str(value).replace(",", "."))
    except InvalidOperation:
        sys.exit(f"ERROR: invalid quantity: {value}")
    if qty < 0:
        sys.exit(f"ERROR: quantity must not be negative: {value}")
    return qty.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def check(order, invoices, quantities, start, end):
    """Problems that need --force; empty list if all is fine."""
    problems = []
    if end < start:
        problems.append(f"period end {end} is before start {start}")
    period = po_period(order)
    if period and (start < period[0] or end > period[1]):
        problems.append(f"period {start}..{end} is outside the PO period {period[0]}..{period[1]}")
    for number, s, e in invoice_periods(invoices):
        if start <= e and s <= end:
            problems.append(f"period overlaps {number} ({s}..{e})")
    lines = {l["id"]: l for l in analyse(order, invoices)[0]}
    for line_id, qty in quantities.items():
        if line_id not in lines:
            problems.append(f"line {line_id} is not on the PO")
        elif qty > lines[line_id]["remaining"]:
            problems.append(f"line {line_id}: {qty} {lines[line_id]['unit']} billed, "
                            f"only {lines[line_id]['remaining']:,.2f} left on the PO")
    if not any(qty > 0 for qty in quantities.values()):
        problems.append("nothing to bill (all quantities are 0)")
    return problems


def invoice_text(order_path, order, number, issue_date, start, end, quantities):
    """The poin text turned into an invoice; lines not billed (quantity 0) are dropped."""
    text = drop_status(order_path.read_text(encoding="utf-8"))
    lines = text.splitlines()

    purchase = block_range(lines, "purchase")
    if purchase:
        end_at = purchase[1]
        while end_at < len(lines) and not lines[end_at].strip():
            end_at += 1
        del lines[purchase[0]:end_at]

    quote = order["quote"]
    header = [
        "invoice:",
        f'  number:           "{number}"      # Rechnungsnummer',
        f'  issue_date:       "{issue_date.isoformat()}"      # Rechnungsdatum',
        f'  currency:         {json.dumps(quote.get("currency", "EUR"))}             # Währung',
        f'  buyer_reference:  {json.dumps(quote.get("buyer_reference", ""), ensure_ascii=False)}'
        f'          # Projektreferenz',
        f'  po_number:        {json.dumps(str(order["purchase"]["po_number"]))}'
        f'      # Kunden PO (aus Auftragsbestätigung {order_path.stem})',
        "",
        "  service_period:",
        f'      start:  "{start.isoformat()}" # Abrechnungszeitraum Start',
        f'      end:    "{end.isoformat()}" # Abrechnungszeitraum Ende',
    ]
    found = block_range(lines, "quote")
    lines[found[0]:found[1]] = header

    # line items: from one "- assigned_id" to the next, the last one up to the next top-level key
    start_at = block_range(lines, "lines")[0]
    keys = "|".join(re.escape(k) for k in order if k != "lines")
    stop = next((i for i in range(start_at + 1, len(lines)) if re.match(rf"^({keys})\s*:", lines[i])),
                len(lines))
    items = [i for i in range(start_at + 1, stop) if re.match(r"^\s+- assigned_id\s*:", lines[i])]
    bounds = list(zip(items, items[1:] + [stop]))
    for first, last in reversed(bounds):
        line_id = str(yaml.safe_load(lines[first].split(":", 1)[1]))
        if line_id not in quantities:
            continue  # notes (quantity 0 on the PO) stay as they are
        if quantities[line_id] == 0:
            # keep the blank lines that separate the next block
            while last > first and not lines[last - 1].strip():
                last -= 1
            del lines[first:last]
            continue
        q = next(i for i in range(first, last) if re.match(r"^\s+quantity\s*:", lines[i]))
        indent = lines[q][:len(lines[q]) - len(lines[q].lstrip())]
        lines[q] = f"{indent}quantity: {quantities[line_id]:.2f}"
    return "\n".join(lines) + "\n"


def expected_data(order, number, issue_date, start, end, quantities):
    data = {k: v for k, v in order.items() if k not in ("quote", "purchase", "status")}
    quote = order["quote"]
    data["invoice"] = {
        "number": number,
        "issue_date": issue_date.isoformat(),
        "currency": quote.get("currency", "EUR"),
        "buyer_reference": quote.get("buyer_reference", ""),
        "po_number": str(order["purchase"]["po_number"]),
        "service_period": {"start": start.isoformat(), "end": end.isoformat()},
    }
    lines = []
    for line in order["lines"]:
        line_id = str(line["assigned_id"])
        if line_id in quantities:
            if quantities[line_id] == 0:
                continue
            line = {**line, "quantity": float(quantities[line_id])}
        lines.append(line)
    data["lines"] = lines
    return data


def summary(order, invoices, quantities, number, start, end):
    lines = {l["id"]: l for l in analyse(order, invoices)[0]}
    out = [f"{number}  {order.get('buyer', {}).get('name', '?')}  PO {order['purchase']['po_number']}",
           f"Service period {start} .. {end}"]
    net = Decimal("0")
    for line_id, qty in quantities.items():
        if qty == 0 or line_id not in lines:
            continue
        line = lines[line_id]
        amount = (qty * line["price"]).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        net += amount
        out.append(f"  {line_id} {line['name']}: {qty:,.2f} {line['unit']} x {line['price']:,.2f}"
                   f" = {amount:,.2f}  (left after: {line['remaining'] - qty:,.2f})")
    rate = Decimal(str(order.get("tax", {}).get("rate", 0)))
    tax = (net * rate / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    out.append(f"Net {net:,.2f} + tax {rate:g}% {tax:,.2f} = {net + tax:,.2f} "
               f"{order.get('quote', {}).get('currency', 'EUR')}")
    return "\n".join(out)


def next_steps(order, number, end):
    steps = [f"Next: book {number} as outgoing voucher in the DB (add_outgoing_voucher.py)"]
    if order.get("tax", {}).get("category") == "AE":
        steps.append(f"Reverse charge: {number} belongs in the ZM for {end:%Y-%m}")
    return "\n".join(steps)


def create(key, quantities, data_dir, start=None, end=None, issue_date=None, number=None,
           force=False, dry_run=False, mark_timelog=False):
    """Write the invoice YAML. Returns (message, path); raises SystemExit on refusal.

    mark_timelog: write the invoice number into the time log entries of this PO
    and period that are not billed yet.
    """
    order_path, order, invoices = load_po(key, data_dir)
    issue_date = issue_date or date.today()
    default_start, default_end = default_period(order, invoices, issue_date)
    start, end = start or default_start, end or default_end
    number = number or next_invoice_number(data_dir, issue_date.year)
    target = data_dir / f"invoice_{number}.yaml"
    if target.exists():
        sys.exit(f"ERROR: {target.name} already exists")

    problems = check(order, invoices, quantities, start, end)
    if problems and not force:
        sys.exit("ERROR: " + "\nERROR: ".join(problems) + "\nNothing written. Use --force if this is intended.")

    new_text = invoice_text(order_path, order, number, issue_date, start, end, quantities)
    if yaml.safe_load(new_text) != expected_data(order, number, issue_date, start, end, quantities):
        sys.exit("ERROR: YAML edit did not verify, nothing written. Please create the invoice by hand.")

    rows = []
    if mark_timelog:
        _, rows = timelog.billable_hours(str(order["purchase"]["po_number"]), start, end,
                                         time_dir=data_dir / "time")
    message = summary(order, invoices, quantities, number, start, end)
    message += "".join(f"\nWARN: {p}" for p in problems)
    if dry_run:
        marks = f", mark {len(rows)} time log entries" if rows else ""
        return f"{message}\n[dry-run] would write {target.name}{marks}", target
    target.write_text(new_text, encoding="utf-8")
    if rows:
        message += f"\nTime log: {timelog.mark_invoiced(rows, number)} entries marked {number}"
    return f"{message}\nWrote {target.name}\n{next_steps(order, number, end)}", target


def render(path, order):
    """Run render_invoice.py (PDF + Factur-X). Returns (ok, output)."""
    res = subprocess.run([sys.executable, "render_invoice.py", str(path), template_for(order)],
                         cwd=HERE, capture_output=True, text=True)
    return res.returncode == 0, (res.stdout + res.stderr).strip()


def main():
    ap = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    ap.add_argument("po", help="customer PO number, order confirmation (PI…) or quote (AN…) number")
    ap.add_argument("--qty", action="append", default=[], metavar="ID=QTY",
                    help="quantity to bill per PO line (assigned_id), repeatable; "
                         "PO lines not given are left out")
    ap.add_argument("--period", metavar="START..END",
                    help="service period, default day after the last invoice .. end of that month")
    ap.add_argument("--date", help="invoice date (YYYY-MM-DD), default today")
    ap.add_argument("--number", help="invoice number, default the next RE<year><nnnn>")
    ap.add_argument("--from-timelog", action="store_true",
                    help="bill the not yet billed time log hours of the period on the hourly line")
    ap.add_argument("--render", action="store_true", help="render PDF + Factur-X right away")
    ap.add_argument("--force", action="store_true", help="write despite the checks")
    ap.add_argument("--dry-run", action="store_true", help="show the result, don't write")
    ap.add_argument("--dir", default=str(DATA_DIR), help="data directory")
    args = ap.parse_args()

    data_dir = Path(args.dir)
    _, order, _ = load_po(args.po, data_dir)
    billable = [str(l["assigned_id"]) for l in order.get("lines", []) if Decimal(str(l["quantity"])) != 0]
    quantities = {line_id: Decimal("0") for line_id in billable}
    for item in args.qty:
        line_id, sep, value = item.partition("=")
        if not sep:
            sys.exit(f"ERROR: --qty expects ID=QTY, got {item}")
        quantities[line_id] = parse_qty(value)

    start = end = None
    if args.period:
        first, sep, last = args.period.partition("..")
        if not sep:
            sys.exit(f"ERROR: --period expects START..END, got {args.period}")
        start, end = parse_date(first), parse_date(last)

    issue_date = parse_date(args.date) if args.date else None
    if args.from_timelog:
        _, _, invoices = load_po(args.po, data_dir)
        if start is None:
            start, end = default_period(order, invoices, issue_date or date.today())
        line_id = hour_line(order)
        if line_id is None:
            sys.exit("ERROR: --from-timelog needs exactly one hourly (HUR) line on the PO, use --qty")
        hours, rows = timelog.billable_hours(str(order["purchase"]["po_number"]), start, end,
                                             time_dir=data_dir / "time")
        if any(item.startswith(f"{line_id}=") for item in args.qty):
            print(f"WARN: --qty for {line_id} overrides the time log ({hours} h)", file=sys.stderr)
        else:
            quantities[line_id] = hours
        print(f"Time log: {len(rows)} entries, {hours} h billable in {start} .. {end}")

    message, path = create(args.po, quantities, data_dir, start, end, issue_date, args.number,
                           args.force, args.dry_run, mark_timelog=args.from_timelog)
    print(message)
    if args.render and not args.dry_run:
        ok, out = render(path, order)
        print(out)
        if not ok:
            sys.exit("ERROR: rendering failed")


if __name__ == "__main__":
    main()
