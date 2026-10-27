#!/usr/bin/env python3
"""Small terminal menu over the day-to-day invoicing scripts.

Uses whiptail for the dialogs, less for the reports and a curses list for the
quotes (hotkeys to accept, expire, reject and reopen); every action goes
through the existing scripts (quotes.py, scan_overdue.py, po_remaining.py,
record_payment.py), so the command line keeps working the same way.
--dir points the menu at another data directory (e.g. a copy for a demo).
"""

import argparse
import calendar
import contextlib
import curses
import io
import os
import shutil
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path

import invoice_po
import quotes
import scan_overdue
import timelog
from po_remaining import analyse
from scan_overdue import DATA_DIR, parse_date

HERE = Path(__file__).parent
TITLE = "ITC Embedded - invoicing"
# dark whiptail theme instead of the default pink/blue; NEWT_COLORS in the environment wins
DARK = ("root=white,black window=white,black border=red,black title=brightred,black "
        "textbox=white,black button=white,red actbutton=white,red compactbutton=white,black "
        "listbox=white,black actlistbox=black,white sellistbox=white,black actsellistbox=white,red "
        "checkbox=white,black actcheckbox=black,red entry=brightwhite,black label=white,black "
        "helpline=white,black roottext=white,black emptyscale=,black fullscale=,red")


def whiptail(box, text, *rest, opts=()):
    """Run a whiptail dialog; returns (ok, answer)."""
    cols, rows = shutil.get_terminal_size((100, 30))
    size = [str(min(rows - 2, 30)), str(min(cols - 4, 110))]
    # whiptail draws on the terminal and writes the answer to stderr
    env = {"NEWT_COLORS": DARK, **os.environ}
    title = TITLE if DATA_DIR == scan_overdue.DATA_DIR.resolve() else f"{TITLE} [data: {DATA_DIR.name}]"
    res = subprocess.run(["whiptail", "--title", title, *opts, box, text, *size, *rest],
                         stderr=subprocess.PIPE, text=True, env=env)
    return res.returncode == 0, res.stderr.strip()


def msgbox(text):
    whiptail("--msgbox", text, opts=["--scrolltext"])


def run_script(*args):
    res = subprocess.run([sys.executable, *args], cwd=HERE, capture_output=True, text=True)
    return res.returncode, (res.stdout + res.stderr).rstrip()


def page(*args):
    """Show a report in less (wide tables scroll sideways)."""
    _, out = run_script(*args)
    if shutil.which("less"):
        subprocess.run(["less", "-S", "-R", "+g"], input=out + "\n\n(q to go back)\n", text=True)
    else:
        print(out)
        input("\nEnter to go back ")


def ask_date(prompt, default):
    while True:
        ok, value = whiptail("--inputbox", prompt, default.isoformat())
        if not ok:
            return None
        try:
            return parse_date(value)
        except ValueError:
            msgbox(f"Not a date: {value!r} (YYYY-MM-DD)")


STATE_COLORS = {"open": 1, "lapsed": 2, "ordered": 3}
HELP = " ↑↓/jk move  i invoice  a accepted  e expired  r rejected  u reopen  f filter  q back "


def prompt(scr, label, default=""):
    """One-line input at the bottom; Enter returns the text, Esc returns None."""
    height, width = scr.getmaxyx()
    text = default
    curses.curs_set(1)
    try:
        while True:
            line = f"{label}: {text}"
            scr.move(height - 2, 0)
            scr.clrtoeol()
            scr.addstr(height - 2, 0, line[-(width - 1):], curses.A_BOLD)
            scr.refresh()
            key = scr.get_wch()
            if key in ("\n", "\r", curses.KEY_ENTER):
                return text.strip()
            if key == "\x1b":
                return None
            if key in (curses.KEY_BACKSPACE, "\x7f", "\b"):
                text = text[:-1]
            elif isinstance(key, str) and key.isprintable():
                text += key
    finally:
        curses.curs_set(0)


def confirm(scr, question):
    answer = prompt(scr, f"{question} [y/N]")
    return answer is not None and answer.lower() in ("y", "j", "yes", "ja")


def prompt_date(scr, label, default):
    while True:
        value = prompt(scr, f"{label} (YYYY-MM-DD)", default.isoformat())
        if value is None:
            return None
        try:
            return parse_date(value)
        except ValueError:
            curses.beep()


def quiet(func, *args, **kwargs):
    """Call a quotes.* function; returns its message, or the error it exits with."""
    with contextlib.redirect_stderr(io.StringIO()):
        try:
            return func(*args, **kwargs)
        except SystemExit as exc:
            return str(exc)


def close_quote(scr, row, state):
    force = False
    if row["state"] in quotes.CLOSED_STATES:
        if row["state"] == state or not confirm(scr, f"{row['number']} is {row['state']}, change to {state}?"):
            return ""
        force = True
    elif row["state"] == "ordered":
        return f"{row['number']} is ordered (PO {row['po']}), can't be {state}"
    if state == "expired" and row["state"] == "open":
        if not confirm(scr, f"{row['number']} is valid until {row['valid_until']}, expire anyway?"):
            return ""
        force = True
    when = prompt_date(scr, "Date of the decision", date.today())
    if when is None:
        return ""
    note = prompt(scr, "Note (optional)")
    if note is None or not confirm(scr, f"Mark {row['number']} {state} on {when}?"):
        return ""
    return quiet(quotes.mark, row["number"], state, when, note, DATA_DIR, force)


def accept_quote(scr, row):
    if row["state"] == "ordered":
        return f"{row['number']} is already ordered (PO {row['po']})"
    po_number = prompt(scr, f"{row['number']} accepted - customer PO number")
    if not po_number:
        return ""
    order_date = prompt_date(scr, "Date on the customer PO", date.today())
    if order_date is None:
        return ""
    confirmed = prompt_date(scr, "Letter date of our confirmation", date.today())
    if confirmed is None:
        return ""
    pi_number = prompt(scr, "Order confirmation number",
                       quotes.next_order_number(DATA_DIR, confirmed.year))
    if not pi_number or not confirm(scr, f"Create order {pi_number} for PO {po_number}?"):
        return ""
    result = quiet(quotes.accept, row["number"], po_number, order_date, DATA_DIR, confirmed, pi_number)
    if isinstance(result, str):
        return result
    message, target = result
    if confirm(scr, "Render the order confirmation PDF now?"):
        scr.addstr(scr.getmaxyx()[0] - 2, 0, "Rendering (lualatex) ...")
        scr.clrtoeol()
        scr.refresh()
        rc, out = run_script("render_order_confirmation.py", str(target),
                             "templates/order_confirmation.en.tex.j2")
        pdf = target.stem + ".pdf"
        message += f", {pdf} written" if rc == 0 else f", rendering failed: {out.splitlines()[-1:]}"
    return message


def show_text(scr, text, question=None):
    """Full-screen text with a y/N question at the bottom (or just Enter to go back)."""
    scr.erase()
    height, width = scr.getmaxyx()
    for i, line in enumerate(text.splitlines()[:height - 3]):
        attr = curses.color_pair(4) if line.startswith(("ERROR", "WARN")) else curses.A_NORMAL
        scr.addstr(i, 0, line[:width - 1], attr)
    if question is None:
        prompt(scr, "Enter = back")
        return False
    return confirm(scr, question)


def invoice_order(scr, row):
    if row["state"] != "ordered":
        return f"{row['number']} has no customer order yet (a: accepted)"
    loaded = quiet(invoice_po.load_po, row["po"], DATA_DIR)
    if isinstance(loaded, str):
        return loaded
    _, order, invoices = loaded
    today = date.today()

    default_start, _ = invoice_po.default_period(order, invoices, today)
    start = prompt_date(scr, "Service period start", default_start)
    if start is None:
        return ""
    month_end = start.replace(day=calendar.monthrange(start.year, start.month)[1])
    end = prompt_date(scr, "Service period end (per timesheet)", month_end)
    if end is None:
        return ""
    logged = quiet(timelog.billable_hours, str(order["purchase"]["po_number"]), start, end)
    if isinstance(logged, str):
        return logged
    logged_hours, logged_rows = logged
    hour_id = invoice_po.hour_line(order)
    quantities = {}
    for line in analyse(order, invoices)[0]:
        default = f"{logged_hours}" if line["id"] == hour_id and logged_rows else ""
        source = f" (time log {logged_hours})" if default else ""
        while True:
            value = prompt(scr, f"{line['id']} {line['name'][:40]} - {line['remaining']:,.2f} "
                                f"{line['unit']} left{source}, bill", default)
            if value is None:
                return ""
            try:
                quantities[line["id"]] = quiet(invoice_po.parse_qty, value or "0")
                if isinstance(quantities[line["id"]], str):
                    raise ValueError
                break
            except ValueError:
                curses.beep()
    issue_date = prompt_date(scr, "Invoice date", today)
    if issue_date is None:
        return ""
    number = prompt(scr, "Invoice number", invoice_po.next_invoice_number(DATA_DIR, issue_date.year))
    if not number:
        return ""

    mark = bool(logged_rows) and (
        quantities.get(hour_id) == logged_hours
        or confirm(scr, f"Billing {quantities.get(hour_id)} h, time log has {logged_hours} h. "
                        f"Mark the {len(logged_rows)} entries as billed anyway?"))
    args = (row["po"], quantities, DATA_DIR, start, end, issue_date, number)
    result = quiet(invoice_po.create, *args, dry_run=True, mark_timelog=mark)
    force = False
    if isinstance(result, str):
        if "--force" not in result or not show_text(scr, result, "Write anyway, ignoring the checks?"):
            return result.splitlines()[0] if "--force" in result else result
        force = True
        result = quiet(invoice_po.create, *args, force=True, dry_run=True, mark_timelog=mark)
        if isinstance(result, str):
            return result
    if not show_text(scr, result[0], f"Write {number}?"):
        return ""
    result = quiet(invoice_po.create, *args, force=force, mark_timelog=mark)
    if isinstance(result, str):
        return result
    message, path = result
    if confirm(scr, "Render PDF + Factur-X now?"):
        scr.addstr(scr.getmaxyx()[0] - 2, 0, "Rendering (lualatex) ...")
        scr.clrtoeol()
        scr.refresh()
        ok, out = invoice_po.render(path, order)
        message += f"\n{path.stem}_x.pdf written" if ok else f"\nERROR: rendering failed\n{out}"
    if mark and confirm(scr, "Render the activity report (time log) too?"):
        scr.addstr(scr.getmaxyx()[0] - 2, 0, "Rendering activity report ...")
        scr.clrtoeol()
        scr.refresh()
        report = quiet(timelog.build_report, row["po"], start, end, number)
        message += f"\n{report}" if isinstance(report, str) else f"\n{report[0].name} written ({report[1]} h)"
    show_text(scr, message)
    return f"{number} written ({path.name})"


def init_colors():
    curses.curs_set(0)
    curses.use_default_colors()
    for pair, color in ((1, curses.COLOR_GREEN), (2, curses.COLOR_YELLOW),
                        (3, curses.COLOR_CYAN), (4, curses.COLOR_RED)):
        curses.init_pair(pair, color, -1)


def browse_quotes(scr):
    init_colors()
    show_all, pos, message = True, 0, ""
    while True:
        with contextlib.redirect_stderr(io.StringIO()):
            rows = quotes.collect(DATA_DIR, date.today())
        if not show_all:
            rows = [r for r in rows if quotes.visible(r)]
        pos = max(0, min(pos, len(rows) - 1))

        scr.erase()
        height, width = scr.getmaxyx()
        title = f" Quotes ({'all' if show_all else 'active'}) - {date.today().isoformat()} "
        scr.addstr(0, 0, title.ljust(width - 1)[:width - 1], curses.color_pair(4) | curses.A_BOLD)
        header = (f"{'Quote':<11} {'State':<8} {'Buyer':<24} {'Net':>11}  {'Valid to':<10} "
                  f"{'PO':<11} {'Left':>11}  Note")
        scr.addstr(1, 0, header[:width - 1], curses.A_UNDERLINE)
        top = max(0, pos - (height - 6))
        for i, r in enumerate(rows[top:top + height - 5]):
            left = f"{r['left']:>11,.2f}" if r["left"] is not None else ""
            line = (f"{r['number']:<11} {r['state']:<8} {r['buyer'][:24]:<24} {r['net']:>11,.2f}  "
                    f"{r['valid_until'].isoformat():<10} {r['po'] or '':<11} {left:>11}  {r['note']}")
            attr = (curses.color_pair(STATE_COLORS[r["state"]]) if r["state"] in STATE_COLORS
                    else curses.A_DIM)
            if top + i == pos:
                attr |= curses.A_REVERSE
            scr.addstr(2 + i, 0, line[:width - 1].ljust(width - 1), attr)
        if not rows:
            scr.addstr(3, 2, "No quotes to show (f: show all).")
        if message:
            scr.addstr(height - 2, 0, message[:width - 1], curses.A_BOLD)
        scr.addstr(height - 1, 0, HELP[:width - 1], curses.color_pair(4))
        scr.refresh()

        key = scr.getch()
        message = ""
        if key in (ord("q"), 27):
            return
        if key in (curses.KEY_DOWN, ord("j")):
            pos += 1
        elif key in (curses.KEY_UP, ord("k")):
            pos -= 1
        elif key == ord("f"):
            show_all = not show_all
        elif not rows:
            continue
        elif key == ord("e"):
            message = close_quote(scr, rows[pos], "expired")
        elif key == ord("r"):
            message = close_quote(scr, rows[pos], "rejected")
        elif key == ord("u"):
            if confirm(scr, f"Reopen {rows[pos]['number']}?"):
                message = quiet(quotes.reopen, rows[pos]["number"], DATA_DIR)
        elif key == ord("a"):
            message = accept_quote(scr, rows[pos])
        elif key == ord("i"):
            message = invoice_order(scr, rows[pos])


def quote_list():
    os.environ.setdefault("ESCDELAY", "25")
    curses.wrapper(browse_quotes)


TIME_HELP = (" ↑↓ select  ←→ day  t today  s start  x stop  a add  e edit  d delete  q back ")


def with_force(scr, func, *args):
    """Call a timelog function; on a refusal that --force would pass, ask and retry."""
    result = quiet(func, *args)
    if "--force" in result and show_text(scr, result, "Do it anyway?"):
        result = quiet(func, *args, force=True)
    return result.replace("\n", " | ")


def ask_span(scr, default="", allow_open=False):
    """(start, end) from HH:MM-HH:MM; end None for "HH:MM-" if allow_open. None on Esc."""
    while True:
        value = prompt(scr, "Time (HH:MM-HH:MM)", default)
        if value is None:
            return None
        first, sep, last = value.partition("-")
        try:
            start = timelog.parse_time(first)
            if allow_open and sep and not last.strip():
                return start, None
            end = timelog.parse_time(last)
            if end > start:
                return start, end
        except ValueError:
            pass
        curses.beep()


def time_view(scr):
    init_colors()
    day, pos, message = date.today(), 0, ""
    op = timelog.DEFAULT_OP
    while True:
        entries = quiet(timelog.load_entries)
        if isinstance(entries, str):
            show_text(scr, entries)
            return
        rounded = timelog.billed_minutes(entries)
        rows = [e for e in entries if e.day == day]
        pos = max(0, min(pos, len(rows) - 1))
        now = datetime.now()
        current = timelog.running(entries, op)

        scr.erase()
        height, width = scr.getmaxyx()
        title = f" Time log {day:%a %Y-%m-%d} "
        if current:
            elapsed = int((now - datetime.combine(current.day, current.start)).total_seconds() // 60)
            title += f"  - running: {current.task} since {current.start:%H:%M} ({elapsed // 60}:{elapsed % 60:02d})"
        scr.addstr(0, 0, title.ljust(width - 1)[:width - 1], curses.color_pair(4) | curses.A_BOLD)
        header = f"{'Start':<5} {'End':<5} {'Op':<3} {'PO':<11} {'Raw':>4} {'Bill':>4}  {'Task':<50} Invoice"
        scr.addstr(1, 0, header[:width - 1], curses.A_UNDERLINE)
        worked = billable = 0
        for i, e in enumerate(rows[:height - 6]):
            if e.end is None:
                raw = int((now - datetime.combine(e.day, e.start)).total_seconds() // 60) if e.day == now.date() else 0
            else:
                raw = e.minutes
            bill = rounded.get(id(e), 0) if e.po != timelog.INTERNAL else 0
            worked, billable = worked + raw, billable + bill
            end = e.end.strftime("%H:%M") if e.end else "..."
            line = (f"{e.start:%H:%M} {end:<5} {e.op:<3} {e.po:<11} {raw:>4} {bill:>4}  "
                    f"{e.task[:50]:<50} {e.invoice}")
            if e.end is None:
                attr = curses.color_pair(3) | curses.A_BOLD
            elif e.po == timelog.INTERNAL:
                attr = curses.A_DIM
            elif e.invoice:
                attr = curses.color_pair(1)
            else:
                attr = curses.A_NORMAL
            if i == pos:
                attr |= curses.A_REVERSE
            scr.addstr(2 + i, 0, line[:width - 1].ljust(width - 1), attr)
        if rows:
            scr.addstr(min(len(rows), height - 6) + 3, 0,
                       f"Day: {timelog.hours(worked)} h worked, {timelog.hours(billable)} h billable "
                       f"(rounded up to {timelog.DEFAULT_STEP} min per block)"[:width - 1])
        else:
            scr.addstr(3, 2, "No entries (s: start a timer, a: add a block).")
        if message:
            scr.addstr(height - 2, 0, message[:width - 1], curses.A_BOLD)
        scr.addstr(height - 1, 0, TIME_HELP[:width - 1], curses.color_pair(4))
        scr.refresh()

        key = scr.getch()
        message = ""
        selected = rows[pos] if rows else None
        if key in (ord("q"), 27):
            return
        if key in (curses.KEY_DOWN, ord("j")):
            pos += 1
        elif key in (curses.KEY_UP, ord("k")):
            pos -= 1
        elif key in (curses.KEY_LEFT, ord("h")):
            day, pos = day - timedelta(days=1), 0
        elif key in (curses.KEY_RIGHT, ord("l")):
            day, pos = day + timedelta(days=1), 0
        elif key == ord("t"):
            day, pos = date.today(), 0
        elif key == ord("s"):
            task = prompt(scr, "Task")
            po = task and prompt(scr, "PO / PI / AN (- = internal)", timelog.last_po(entries, op) or "")
            if task and po:
                message = with_force(scr, timelog.start_timer, task, po, op)
                day = date.today()
        elif key == ord("x"):
            if current is None:
                message = "No timer running."
                continue
            at = prompt(scr, f"Stop '{current.task}' at (HH:MM)", now.strftime("%H:%M"))
            try:
                message = quiet(timelog.stop_timer, op, timelog.parse_time(at)) if at else ""
            except ValueError:
                message = f"Not a time: {at}"
        elif key == ord("a"):
            span = ask_span(scr)
            task = span and prompt(scr, "Task")
            po = task and prompt(scr, "PO / PI / AN (- = internal)", timelog.last_po(entries, op) or "")
            if span and task and po:
                message = with_force(scr, timelog.add_entry, day, span[0], span[1], task, po, op)
        elif key == ord("e") and selected:
            end = selected.end.strftime("%H:%M") if selected.end else ""
            span = ask_span(scr, f"{selected.start:%H:%M}-{end}", allow_open=selected.end is None)
            task = span and prompt(scr, "Task", selected.task)
            po = task and prompt(scr, "PO / PI / AN (- = internal)", selected.po)
            if span and task and po:
                message = with_force(scr, timelog.edit_entry, selected, span[0], span[1], task, po)
        elif key == ord("d") and selected:
            if confirm(scr, f"Delete {selected.start:%H:%M} {selected.task}?"):
                message = with_force(scr, timelog.delete_entry, selected)


def time_log():
    os.environ.setdefault("ESCDELAY", "25")
    curses.wrapper(time_view)


def record_payment():
    today = date.today()
    with contextlib.redirect_stderr(io.StringIO()):
        rows = [r for r in scan_overdue.collect(DATA_DIR, today) if r["open"] > 0]
    if not rows:
        msgbox("No open invoices.")
        return
    items = []
    for r in rows:
        items += [r["number"], f"{r['buyer'][:28]:<28} open {r['open']:>11,.2f}  due {r['due_date']}"]
    ok, number = whiptail("--menu", "Payment for which invoice?", str(len(rows)), *items)
    if not ok:
        return
    row = next(r for r in rows if r["number"] == number)

    when = ask_date("Value date of the payment", today)
    if when is None:
        return
    ok, amount = whiptail("--inputbox", "Amount received (EUR)", f"{row['open']:.2f}")
    if not ok:
        return
    ok, reference = whiptail("--inputbox", "Bank reference / Verwendungszweck (optional)", "")
    if not ok:
        return

    args = ["record_payment.py", number, "--date", when.isoformat(), "--amount", amount,
            "--dir", str(DATA_DIR)]
    if reference:
        args += ["--reference", reference]
    rc, out = run_script(*args, "--dry-run")
    if rc != 0:
        msgbox(out)
        return
    ok, _ = whiptail("--yesno", out + "\n\nWrite this?")
    if ok:
        msgbox(run_script(*args)[1])


ACTIONS = [
    ("1", "Time log: start/stop, add, edit", time_log),
    ("2", "Quotes & orders: accept, invoice, expire, reject", quote_list),
    ("3", "Invoices: open items", lambda: page("scan_overdue.py", "--all", "--dir", str(DATA_DIR))),
    ("4", "Customer POs: budget left", lambda: page("po_remaining.py", "--dir", str(DATA_DIR))),
    ("5", "Record a payment", record_payment),
]


def main():
    global DATA_DIR
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--dir", default=str(DATA_DIR), help="data directory (time log in <dir>/time)")
    args = ap.parse_args()
    DATA_DIR = Path(args.dir).resolve()
    if not DATA_DIR.is_dir():
        sys.exit(f"ERROR: data directory {DATA_DIR} not found")
    timelog.DIRS["data"] = DATA_DIR
    timelog.DIRS["time"] = DATA_DIR / "time"
    if not shutil.which("whiptail"):
        sys.exit("whiptail not found (Debian/Ubuntu: package whiptail)")
    while True:
        items = [x for key, label, _ in ACTIONS for x in (key, label)]
        ok, choice = whiptail("--menu", "What do you want to do?", str(len(ACTIONS)),
                              *items, opts=["--cancel-button", "Quit"])
        if not ok:
            return
        next(action for key, _, action in ACTIONS if key == choice)()


if __name__ == "__main__":
    main()
