#!/usr/bin/env python3
"""Small terminal menu over the day-to-day invoicing scripts.

Uses whiptail for the dialogs, less for the reports and a curses list for the
quotes (hotkeys to accept, expire, reject and reopen); every action goes
through the existing scripts (quotes.py, scan_overdue.py, po_remaining.py,
record_payment.py), so the command line keeps working the same way.
"""

import contextlib
import curses
import io
import os
import shutil
import subprocess
import sys
from datetime import date
from pathlib import Path

import quotes
import scan_overdue
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
    res = subprocess.run(["whiptail", "--title", TITLE, *opts, box, text, *size, *rest],
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
HELP = " ↑↓/jk move   a accepted   e expired   r rejected   u reopen   f filter   q back "


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


def browse_quotes(scr):
    curses.curs_set(0)
    curses.use_default_colors()
    for pair, color in ((1, curses.COLOR_GREEN), (2, curses.COLOR_YELLOW),
                        (3, curses.COLOR_CYAN), (4, curses.COLOR_RED)):
        curses.init_pair(pair, color, -1)
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


def quote_list():
    os.environ.setdefault("ESCDELAY", "25")
    curses.wrapper(browse_quotes)


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

    args = ["record_payment.py", number, "--date", when.isoformat(), "--amount", amount]
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
    ("1", "Quotes: list, accept, expire, reject", quote_list),
    ("2", "Invoices: open items", lambda: page("scan_overdue.py", "--all")),
    ("3", "Customer POs: budget left", lambda: page("po_remaining.py")),
    ("4", "Record a payment", record_payment),
]


def main():
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
