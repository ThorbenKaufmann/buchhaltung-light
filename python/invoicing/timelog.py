#!/usr/bin/env python3
"""Time tracking against customer POs, with an activity report for the customer.

Entries live in data/time/YYYY-MM.tsv, one work block per line, tab separated:

  date        start  end    op  po          task                        invoice
  2026-11-03  08:15  12:40  TK  5000225603  CAN driver bring-up

`end` is empty while a timer runs, `po` is "-" for internal (not billable)
work, `invoice` is reserved for the invoice number the block was billed on.
The files can be edited by hand; the script only appends lines or fills in
an end time, so comments and order survive. Operator codes are resolved via
data/time/operators.yaml (code: full name).

Raw timestamps are kept; rounding happens only in reports: every block is
rounded up to --step minutes (default 15), but never past the start of the
operator's next block, so a seamless task switch is not billed twice while
the preparation time in a gap is.

Examples:
  python3 timelog.py start "CAN driver bring-up" --po 5000225603
  python3 timelog.py stop
  python3 timelog.py add 2026-11-03 13:30-17:05 "Review balancing spec" --po 5000225603
  python3 timelog.py list --from 2026-11-01 --to 2026-11-30
  python3 timelog.py report 5000225603 --period 2026-11-01..2026-11-27
  python3 timelog.py report --invoice RE20260005
"""

import argparse
import math
import shutil
import sys
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path

import yaml

from po_remaining import find_order, load_orders, load_yaml
from scan_overdue import DATA_DIR, parse_date

HERE = Path(__file__).parent
ROOT = HERE.parents[1]

# set by main() from --dir
DIRS = {"data": DATA_DIR, "time": DATA_DIR / "time"}
HEADER = "# date\tstart\tend\top\tpo\ttask\tinvoice"
DEFAULT_OP = "TK"
DEFAULT_STEP = 15
INTERNAL = "-"


@dataclass
class Entry:
    day: date
    start: time
    end: time | None
    op: str
    po: str
    task: str
    invoice: str = ""
    path: Path | None = None
    lineno: int | None = None

    @property
    def minutes(self):
        if self.end is None:
            return None
        return (datetime.combine(self.day, self.end) - datetime.combine(self.day, self.start)).seconds // 60

    def line(self):
        end = self.end.strftime("%H:%M") if self.end else ""
        return "\t".join([self.day.isoformat(), self.start.strftime("%H:%M"), end, self.op, self.po,
                          self.task, self.invoice]).rstrip("\t")


def parse_time(value):
    return datetime.strptime(value.strip(), "%H:%M").time()


def parse_day(value):
    if value == "today":
        return date.today()
    if value == "yesterday":
        return date.today() - timedelta(days=1)
    return parse_date(value)


def load_entries(time_dir=None):
    time_dir = time_dir or DIRS["time"]
    entries = []
    for path in sorted(time_dir.glob("*.tsv")):
        for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines()):
            if not raw.strip() or raw.lstrip().startswith("#"):
                continue
            cols = raw.split("\t") + [""] * 7
            try:
                entries.append(Entry(parse_date(cols[0]), parse_time(cols[1]),
                                     parse_time(cols[2]) if cols[2].strip() else None,
                                     cols[3].strip(), cols[4].strip(), cols[5].strip(),
                                     cols[6].strip(), path, lineno))
            except ValueError as exc:
                sys.exit(f"ERROR: {path.name} line {lineno + 1}: {exc}\n  {raw}")
    entries.sort(key=lambda e: (e.day, e.op, e.start))
    return entries


def operators(time_dir=None):
    path = (time_dir or DIRS["time"]) / "operators.yaml"
    return (load_yaml(path) or {}) if path.is_file() else {}


def append(entry, time_dir=None):
    time_dir = time_dir or DIRS["time"]
    time_dir.mkdir(parents=True, exist_ok=True)
    path = time_dir / f"{entry.day:%Y-%m}.tsv"
    text = path.read_text(encoding="utf-8") if path.is_file() else HEADER + "\n"
    if not text.endswith("\n"):
        text += "\n"
    path.write_text(text + entry.line() + "\n", encoding="utf-8")


def rewrite(entry, new):
    """Replace the entry's line by `new` (None deletes it); a new month moves it to that file."""
    lines = entry.path.read_text(encoding="utf-8").splitlines()
    if new is not None and f"{new.day:%Y-%m}" == entry.path.stem:
        lines[entry.lineno] = new.line()
        new = None
    else:
        del lines[entry.lineno]
    entry.path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    if new is not None:
        append(new, entry.path.parent)


def set_end(entry, end):
    """Fill in the end time of a running entry in place."""
    entry.end = end
    rewrite(entry, entry)


def running(entries, op):
    return next((e for e in entries if e.op == op and e.end is None), None)


def overlaps(entries, new, skip=None):
    """Entries of the same operator that overlap `new` (open entries count until now)."""
    new_end = new.end or datetime.now().time()
    hits = []
    for e in entries:
        if e.op != new.op or e.day != new.day or e is skip:
            continue
        end = e.end or (datetime.now().time() if e.day == date.today() else time(23, 59))
        if new.start < end and e.start < new_end:
            hits.append(e)
    return hits


def resolve_po(key):
    """Customer PO number for a PO / PI / AN key, or None if unknown."""
    if key == INTERNAL:
        return INTERNAL
    found = find_order(load_orders(DIRS["data"]), key)
    return str(found[1]["purchase"]["po_number"]) if found else None


def billed_minutes(entries, step=DEFAULT_STEP):
    """Rounded minutes per entry: up to `step`, capped at the operator's next block."""
    result = {}
    closed = sorted((e for e in entries if e.end is not None), key=lambda e: (e.op, e.day, e.start))
    for i, e in enumerate(closed):
        rounded = math.ceil(e.minutes / step) * step if e.minutes else 0
        nxt = closed[i + 1] if i + 1 < len(closed) else None
        if nxt and nxt.op == e.op and nxt.day == e.day:
            gap_cap = (datetime.combine(e.day, nxt.start) - datetime.combine(e.day, e.start)).seconds // 60
            rounded = min(rounded, max(gap_cap, e.minutes))
        result[id(e)] = rounded
    return result


def hours(minutes):
    return (Decimal(minutes) / 60).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


# -----------------------------
# Commands
# -----------------------------

def last_po(entries, op):
    for e in reversed(entries):
        if e.op == op:
            return e.po
    return None


def checked_po(po, force):
    po_number = resolve_po(po)
    if po_number is None and not force:
        sys.exit(f"ERROR: unknown PO '{po}' (no poin_*.yaml), use --force to log it anyway")
    return po_number or po


def checked_overlaps(entries, entry, force, skip=None):
    hits = overlaps(entries, entry, skip)
    if hits and not force:
        msgs = []
        for e in hits:
            end = e.end.strftime("%H:%M") if e.end else "..."
            msgs.append(f"ERROR: overlaps {e.day} {e.start:%H:%M}-{end} {e.task}")
        sys.exit("\n".join(msgs) + "\nNothing written. Use --force if this is intended.")


def parse_span(span):
    first, sep, last = span.partition("-")
    if not sep:
        sys.exit(f"ERROR: expected HH:MM-HH:MM, got {span}")
    try:
        start, end = parse_time(first), parse_time(last)
    except ValueError:
        sys.exit(f"ERROR: expected HH:MM-HH:MM, got {span}")
    if end <= start:
        sys.exit(f"ERROR: end {end:%H:%M} is not after start {start:%H:%M}")
    return start, end


def start_timer(task, po=None, op=DEFAULT_OP, force=False):
    """Start a timer, stopping the operator's running one. Returns a message."""
    entries = load_entries()
    now = datetime.now().replace(second=0, microsecond=0)
    po = po or last_po(entries, op)
    if not po:
        sys.exit("ERROR: no PO given and none used before, use --po (or --po - for internal)")
    po = checked_po(po, force)
    messages = []
    current = running(entries, op)
    if current:
        if current.day != now.date():
            sys.exit(f"ERROR: a timer from {current.day} is still running, stop it with an end time first")
        if current.start == now.time():
            rewrite(current, None)  # restarted within the same minute: replace it
        else:
            set_end(current, now.time())
            messages.append(f"stopped: {current.start:%H:%M}-{now:%H:%M} {current.task}")
    entry = Entry(now.date(), now.time(), None, op, po, task)
    append(entry)
    messages.append(f"started: {now:%H:%M} {entry.op} {entry.po} {entry.task}")
    return "\n".join(messages)


def stop_timer(op=DEFAULT_OP, at=None):
    current = running(load_entries(), op)
    if current is None:
        sys.exit(f"ERROR: no timer running for {op}")
    end = at or datetime.now().time().replace(second=0, microsecond=0)
    if end <= current.start:
        sys.exit(f"ERROR: end {end:%H:%M} is not after start {current.start:%H:%M}")
    set_end(current, end)
    return f"stopped: {current.day} {current.start:%H:%M}-{end:%H:%M} ({current.minutes} min) {current.task}"


def add_entry(day, start, end, task, po, op=DEFAULT_OP, force=False):
    entry = Entry(day, start, end, op, checked_po(po, force), task)
    checked_overlaps(load_entries(), entry, force)
    append(entry)
    return (f"added: {entry.day} {entry.start:%H:%M}-{entry.end:%H:%M} ({entry.minutes} min) "
            f"{entry.op} {entry.po} {entry.task}")


def edit_entry(entry, start, end, task, po, force=False):
    """Change times, task or PO of an entry (end None keeps a timer running)."""
    if entry.invoice and not force:
        sys.exit(f"ERROR: entry is billed on {entry.invoice}, use --force to change it")
    if end is not None and end <= start:
        sys.exit(f"ERROR: end {end:%H:%M} is not after start {start:%H:%M}")
    new = Entry(entry.day, start, end, entry.op, checked_po(po, force), task, entry.invoice)
    entries = load_entries()
    current = next((e for e in entries if e.path == entry.path and e.lineno == entry.lineno), None)
    checked_overlaps(entries, new, force, skip=current)
    rewrite(entry, new)
    end_str = end.strftime("%H:%M") if end else "..."
    return f"changed: {new.day} {new.start:%H:%M}-{end_str} {new.po} {new.task}"


def delete_entry(entry, force=False):
    if entry.invoice and not force:
        sys.exit(f"ERROR: entry is billed on {entry.invoice}, use --force to delete it")
    rewrite(entry, None)
    return f"deleted: {entry.day} {entry.start:%H:%M} {entry.task}"


def unbilled(po_number, first, last, entries):
    """Entries of a PO in a period that are not on an invoice yet; refuses running timers."""
    rows = [e for e in entries if e.po == po_number and first <= e.day <= last and not e.invoice]
    for e in rows:
        if e.end is None:
            sys.exit(f"ERROR: timer still running on {e.day} {e.start:%H:%M} ({e.task}), stop it first")
    return rows


def billable_hours(po_number, first, last, step=DEFAULT_STEP, time_dir=None):
    """(hours, entries) not billed yet for a PO and period, rounded as in the report."""
    entries = load_entries(time_dir)
    rounded = billed_minutes(entries, step)
    rows = unbilled(po_number, first, last, entries)
    return hours(sum(rounded[id(e)] for e in rows)), rows


def mark_invoiced(rows, number):
    """Write the invoice number into the given entries."""
    by_path = {}
    for e in rows:
        by_path.setdefault(e.path, []).append(e)
    for path, items in by_path.items():
        lines = path.read_text(encoding="utf-8").splitlines()
        for e in items:
            e.invoice = number
            lines[e.lineno] = e.line()
        path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return len(rows)


def cmd_start(args):
    print(start_timer(args.task, args.po, args.op, args.force))


def cmd_stop(args):
    print(stop_timer(args.op, parse_time(args.at) if args.at else None))


def cmd_add(args):
    start, end = parse_span(args.span)
    print(add_entry(parse_day(args.day), start, end, args.task, args.po, args.op, args.force))


def cmd_list(args):
    entries = load_entries()
    first = parse_day(args.start) if args.start else date.today()
    last = parse_day(args.end) if args.end else first
    rounded = billed_minutes(entries, args.step)
    rows = [e for e in entries if first <= e.day <= last and (not args.po or e.po == resolve_po(args.po))]
    if not rows:
        print(f"No entries {first} .. {last}.")
        return

    header = f"{'Date':<10} {'Start':<5} {'End':<5} {'Op':<3} {'PO':<11} {'Raw':>5} {'Bill':>5}  Task"
    print(header)
    print("-" * 100)
    day_raw = day_bill = 0
    total_raw = total_bill = 0
    for i, e in enumerate(rows):
        raw = e.minutes if e.minutes is not None else 0
        bill = rounded.get(id(e), 0) if e.po != INTERNAL else 0
        end = e.end.strftime("%H:%M") if e.end else "..."
        print(f"{e.day.isoformat():<10} {e.start:%H:%M} {end:<5} {e.op:<3} {e.po:<11} "
              f"{raw:>5} {bill:>5}  {e.task}{'  [' + e.invoice + ']' if e.invoice else ''}")
        day_raw, day_bill = day_raw + raw, day_bill + bill
        nxt = rows[i + 1] if i + 1 < len(rows) else None
        if nxt and nxt.day == e.day and nxt.op == e.op and e.end and nxt.start > e.end:
            gap = (datetime.combine(e.day, nxt.start) - datetime.combine(e.day, e.end)).seconds // 60
            print(f"{'':<10} {'':<5} {'':<5} {'':<3} {'':<11} {'':>5} {'':>5}  (gap {gap} min)")
        if not nxt or nxt.day != e.day:
            print(f"{'':<10} {'':<17} {'day':<11} {day_raw:>5} {day_bill:>5}  "
                  f"= {hours(day_raw)} h worked, {hours(day_bill)} h billable")
            total_raw, total_bill = total_raw + day_raw, total_bill + day_bill
            day_raw = day_bill = 0
    print("-" * 100)
    print(f"{first} .. {last}: {hours(total_raw)} h worked, {hours(total_bill)} h billable "
          f"(rounded up to {args.step} min per block)")


# -----------------------------
# Report
# -----------------------------

TEXT = {
    "en": {"title": "Activity Report", "customer": "Customer", "project": "Project",
           "po": "Purchase order", "pi": "Order confirmation", "period": "Service period",
           "invoice": "Invoice", "operator": "Operator", "total": "Total",
           "date": "Date", "tasks": "Activities", "hours": "Hours", "section": "Activities by day",
           "note": "Hours in decimal (industrial) hours."},
    "de": {"title": "Leistungsnachweis", "customer": "Kunde", "project": "Projekt",
           "po": "Bestellung", "pi": "Auftragsbestätigung", "period": "Leistungszeitraum",
           "invoice": "Rechnung", "operator": "Bearbeiter", "total": "Summe",
           "date": "Datum", "tasks": "Tätigkeiten", "hours": "Stunden", "section": "Tätigkeiten je Tag",
           "note": "Angaben in Industriestunden (dezimal)."},
}


def latex(s):
    for a, b in (("\\", "\\textbackslash{}"), ("{", "\\{"), ("}", "\\}"), ("%", "\\%"),
                 ("&", "\\&"), ("#", "\\#"), ("_", "\\_"), ("$", "\\$"),
                 ("~", "\\textasciitilde{}"), ("^", "\\textasciicircum{}")):
        s = s.replace(a, b)
    return s


def report_data(po_number, first, last, step, time_dir=None, invoice=None):
    """{operator: [(day, [tasks], minutes)]} for billable entries of one PO and period."""
    entries = load_entries(time_dir)
    rounded = billed_minutes(entries, step)
    days = {}
    for e in entries:
        if e.po != po_number or not first <= e.day <= last:
            continue
        if e.invoice and e.invoice != invoice:
            continue  # billed on another invoice
        if e.end is None:
            sys.exit(f"ERROR: timer still running on {e.day} {e.start:%H:%M} ({e.task}), stop it first")
        tasks, minutes = days.setdefault(e.op, {}).setdefault(e.day, ([], [0]))
        if e.task not in tasks:
            tasks.append(e.task)
        minutes[0] += rounded[id(e)]
    return {op: [(d, t, m[0]) for d, (t, m) in sorted(by_day.items())] for op, by_day in sorted(days.items())}


def build_report(po_key, first, last, invoice=None, step=DEFAULT_STEP, draft=False, out_dir=HERE):
    sys.path.insert(0, str(ROOT / "python" / "reporting"))
    from firmenlayout import render  # company report layout, only needed here
    found = find_order(load_orders(DIRS["data"]), po_key)
    if found is None:
        sys.exit(f"ERROR: no customer order for '{po_key}'")
    order = found[1]
    po_number = str(order["purchase"]["po_number"])
    data = report_data(po_number, first, last, step, invoice=invoice)
    if not data:
        sys.exit(f"ERROR: no billable entries for PO {po_number} in {first} .. {last}")

    buyer = order.get("buyer", {})
    country = str(buyer.get("country_code") or buyer.get("country") or "").upper()
    lang = "de" if country in ("DE", "GERMANY", "DEUTSCHLAND") else "en"
    t = TEXT[lang]

    def num(value):
        s = f"{value:,.2f}"
        return s.replace(",", "X").replace(".", ",").replace("X", ".") if lang == "de" else s

    def day_str(d):
        return f"{d:%d.%m.%Y}" if lang == "de" else d.isoformat()

    names = operators()
    total = sum(m for days in data.values() for _, _, m in days)
    period = f"{day_str(first)} -- {day_str(last)}"

    md = [f"# {t['section']} {{.unnumbered}}", ""]
    for op, days in data.items():
        if len(data) > 1:
            md += [f"## {latex(names.get(op, op))} {{.unnumbered}}", ""]
        rows = []
        for d, tasks, minutes in days:
            items = "\\newline ".join(f"\\textbullet~{latex(task)}" for task in tasks)
            rows.append(f"{day_str(d)} & {items} & {num(hours(minutes))} \\\\")
        subtotal = sum(m for _, _, m in days)
        md += [
            "\\begin{longtable}{@{}p{2.4cm}>{\\raggedright\\arraybackslash}p{11.6cm}r@{}}",
            "\\toprule",
            f"\\textbf{{{t['date']}}} & \\textbf{{{t['tasks']}}} & \\textbf{{{t['hours']}}} \\\\",
            "\\midrule",
            "\\endhead",
            "\n\\addlinespace\n".join(rows),
            "\\midrule",
            f"\\multicolumn{{2}}{{@{{}}l}}{{\\textbf{{{t['total']}}}}} & \\textbf{{{num(hours(subtotal))}}} \\\\",
            "\\bottomrule",
            "\\end{longtable}",
            "",
        ]
    md += [f"\\textcolor{{graytext}}{{\\small {t['note']}}}", ""]

    stem = f"timesheet_{invoice}" if invoice else f"timesheet_{po_number}_{first:%Y%m%d}_{last:%Y%m%d}"
    build = HERE / "build"
    build.mkdir(exist_ok=True)
    md_file = build / f"{stem}.md"
    md_file.write_text("\n".join(md), encoding="utf-8")
    op_names = "\\newline ".join(latex(names.get(op, op)) for op in data)
    render(md_file, build / f"{stem}.pdf",
           titel=t["title"],
           untertitel=f"{latex(buyer.get('name', ''))} \\textbullet\\ PO {po_number} \\textbullet\\ {period}",
           deckblatt=[(t["customer"], latex(buyer.get("name", "")), t["project"],
                       latex(str(order.get("quote", {}).get("buyer_reference", "")))),
                      (t["po"], po_number, t["pi"], latex(str(order["purchase"].get("number", "")))),
                      (t["period"], f"{day_str(first)} --\\newline {day_str(last)}", t["invoice"],
                       latex(invoice) if invoice else "--"),
                      (t["operator"], op_names, t["total"], f"{num(hours(total))} h")],
           kopfzeile=[t["title"], f"PO {po_number}", period],
           status="DRAFT" if draft else "RELEASED",
           verzeichnis=False, eigene_deckblattseite=False)
    target = out_dir / f"{stem}.pdf"
    shutil.copyfile(build / f"{stem}.pdf", target)
    return target, hours(total)


def cmd_report(args):
    invoice_number = args.invoice
    po_key = args.po
    if invoice_number:
        path = DIRS["data"] / f"invoice_{invoice_number}.yaml"
        inv = load_yaml(path) if path.is_file() else None
        if not inv:
            sys.exit(f"ERROR: invoice {invoice_number} not found in {DIRS['data']}")
        head = inv["invoice"]
        po_key = po_key or str(head.get("po_number", ""))
        period = head.get("service_period") or {}
        first, last = parse_date(period["start"]), parse_date(period["end"])
    if args.period:
        a, sep, b = args.period.partition("..")
        if not sep:
            sys.exit(f"ERROR: --period expects START..END, got {args.period}")
        first, last = parse_day(a), parse_day(b)
    if not po_key or not (invoice_number or args.period):
        sys.exit("ERROR: give a PO with --period, or --invoice")

    target, total = build_report(po_key, first, last, invoice_number, args.step, args.draft)
    print(f"Wrote {target.name}: {total} h")
    if invoice_number:
        billed = sum((Decimal(str(l["quantity"])) for l in inv.get("lines", [])
                      if l.get("unit_code") == "HUR"), Decimal("0"))
        if billed != total:
            print(f"WARN: invoice {invoice_number} bills {billed} h, the time log has {total} h",
                  file=sys.stderr)


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=str(DATA_DIR), help="data directory (time log in <dir>/time)")
    sub = ap.add_subparsers(dest="command", required=True)

    st = sub.add_parser("start", help="start a timer (stops a running one)")
    st.add_argument("task")
    st.add_argument("--po", help="customer PO / PI / AN, '-' for internal; default the last one used")
    st.add_argument("--op", default=DEFAULT_OP, help=f"operator code (default {DEFAULT_OP})")
    st.add_argument("--force", action="store_true", help="accept an unknown PO")
    st.set_defaults(func=cmd_start)

    sp = sub.add_parser("stop", help="stop the running timer")
    sp.add_argument("--at", help="end time HH:MM, default now")
    sp.add_argument("--op", default=DEFAULT_OP)
    sp.set_defaults(func=cmd_stop)

    ad = sub.add_parser("add", help="add a finished block")
    ad.add_argument("day", help="YYYY-MM-DD, today or yesterday")
    ad.add_argument("span", help="HH:MM-HH:MM")
    ad.add_argument("task")
    ad.add_argument("--po", required=True, help="customer PO / PI / AN, '-' for internal")
    ad.add_argument("--op", default=DEFAULT_OP)
    ad.add_argument("--force", action="store_true", help="accept overlaps and unknown POs")
    ad.set_defaults(func=cmd_add)

    ls = sub.add_parser("list", help="internal view with timestamps, gaps and rounding")
    ls.add_argument("--from", dest="start", help="first day (default today)")
    ls.add_argument("--to", dest="end", help="last day (default = --from)")
    ls.add_argument("--po", help="only this PO")
    ls.add_argument("--step", type=int, default=DEFAULT_STEP, help="rounding step in minutes")
    ls.set_defaults(func=cmd_list)

    rp = sub.add_parser("report", help="activity report PDF for the customer")
    rp.add_argument("po", nargs="?", help="customer PO / PI / AN (default: from --invoice)")
    rp.add_argument("--period", metavar="START..END", help="default: the invoice's service period")
    rp.add_argument("--invoice", help="invoice number; takes PO and period from it, checks the hours")
    rp.add_argument("--step", type=int, default=DEFAULT_STEP, help="rounding step in minutes")
    rp.add_argument("--draft", action="store_true", help="DRAFT watermark")
    rp.set_defaults(func=cmd_report)

    args = ap.parse_args()
    DIRS["data"] = Path(args.dir)
    DIRS["time"] = Path(args.dir) / "time"
    args.func(args)


if __name__ == "__main__":
    main()
