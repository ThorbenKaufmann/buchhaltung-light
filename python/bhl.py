#!/usr/bin/env python3

from ui.menu import main_menu
import questionary

def main():
    while True:
        action = main_menu()

        if action == "tax_report":
            run_tax_report()
        elif action == "cashflow":
            run_cashflow()
        elif action == "open_items":
            run_open_items()
        elif action == "exit":
            break


def run_tax_report():
    import subprocess
    month = questionary.text("Monat (YYYY-MM):").ask()
    subprocess.run(["./reporting/report_tax_summary.py", "--month", month])


def run_cashflow():
    import subprocess
    year = questionary.text("Jahr (YYYY):").ask()
    subprocess.run(["./reporting/report_cashflow.py", "--year", year])


def run_open_items():
    import subprocess
    month = questionary.text("Monat (YYYY-MM):").ask()
    subprocess.run(["./reporting/report_open_vouchers.py", "--month", month])



if __name__ == "__main__":
    main()
