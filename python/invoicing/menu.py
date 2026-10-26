#!/usr/bin/env python3
"""Small terminal menu over the day-to-day invoicing scripts.

Uses whiptail for the dialogs and less for the reports; every action just
calls the existing scripts (quotes.py, scan_overdue.py, po_remaining.py,
record_payment.py), so the command line keeps working the same way.
"""

import contextlib
import io
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


def whiptail(box, text, *rest, opts=()):
    """Run a whiptail dialog; returns (ok, answer)."""
    cols, rows = shutil.get_terminal_size((100, 30))
    size = [str(min(rows - 2, 30)), str(min(cols - 4, 110))]
    # whiptail draws on the terminal and writes the answer to stderr
    res = subprocess.run(["whiptail", "--title", TITLE, *opts, box, text, *size, *rest],
                         stderr=subprocess.PIPE, text=True)
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


def close_quote():
    today = date.today()
    with contextlib.redirect_stderr(io.StringIO()):
        rows = [r for r in quotes.collect(DATA_DIR, today) if r["state"] in ("open", "lapsed")]
    if not rows:
        msgbox("No open or lapsed quotes.")
        return
    items = []
    for r in rows:
        items += [r["number"], f"{r['state']:<7} {r['buyer'][:28]:<28} {r['net']:>11,.2f}  "
                               f"valid to {r['valid_until']}"]
    ok, number = whiptail("--menu", "Which quote is closed?", str(len(rows)), *items)
    if not ok:
        return
    row = next(r for r in rows if r["number"] == number)

    lapsed = row["state"] == "lapsed"
    ok, state = whiptail("--radiolist", f"{number}: how did it end?", "2",
                         "expired", "no answer, validity ran out", "ON" if lapsed else "OFF",
                         "rejected", "customer declined", "OFF" if lapsed else "ON")
    if not ok or not state:
        return
    force = False
    if state == "expired" and not lapsed:
        ok, _ = whiptail("--yesno", f"{number} is still valid until {row['valid_until']}.\n"
                                    "Mark it expired anyway?")
        if not ok:
            return
        force = True
    when = ask_date("Date of the decision", today)
    if when is None:
        return
    ok, note = whiptail("--inputbox", "Note (optional), e.g. reason or contact", "")
    if not ok:
        return

    try:
        with contextlib.redirect_stderr(io.StringIO()):
            preview = quotes.mark(number, state, when, note, DATA_DIR, force, dry_run=True)
        ok, _ = whiptail("--yesno", preview + "\n\nWrite this?")
        if not ok:
            return
        with contextlib.redirect_stderr(io.StringIO()):
            msgbox(quotes.mark(number, state, when, note, DATA_DIR, force))
    except SystemExit as exc:
        msgbox(str(exc))


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
    ("1", "Quotes: open / lapsed / ordered", lambda: page("quotes.py", "--all")),
    ("2", "Close a quote (rejected / expired)", close_quote),
    ("3", "Invoices: open items", lambda: page("scan_overdue.py", "--all")),
    ("4", "Customer POs: budget left", lambda: page("po_remaining.py")),
    ("5", "Record a payment", record_payment),
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
