import questionary

def main_menu():
    choice = questionary.select(
        "BHL – Hauptmenü",
        choices=[
            {"name": "📊 Steuerreport", "value": "tax_report"},
            {"name": "💰 Cashflow", "value": "cashflow"},
            {"name": "📂 Offene Posten", "value": "open_items"},
            {"name": "❌ Beenden", "value": "exit"},
        ]
    ).ask()

    return choice
