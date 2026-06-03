#!/usr/bin/env python3
from datetime import date
from decimal import Decimal
import os
import subprocess
import sys
import yaml
from jinja2 import Environment, FileSystemLoader

LCO_DIR = os.path.join(os.path.dirname(__file__), "../../config/latex/lco")

BASE_RATE = Decimal(1.27)    # Basiszinssatz
DUNNING_DAYS = float(7)

# -----------------------------
# LaTeX Escape
# -----------------------------
def latex_escape(text):
    if text is None:
        return ""
    replacements = {
        '\\': r'\textbackslash{}',
        '&': r'\&',
        '%': r'\%',
        '$': r'\$',
        '#': r'\#',
        '_': r'\_',
        '{': r'\{',
        '}': r'\}',
        '~': r'\textasciitilde{}',
        '^': r'\textasciicircum{}',
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text



def main(yaml_path, template_path, out_path):
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    # -----------------------------
    # Business Logic (Totals)
    # -----------------------------
    from decimal import Decimal, ROUND_HALF_UP

    lines = data["lines"]

    from datetime import datetime, timedelta

    # Due Date berechnen aus payment.terms_days, oder aus payment.due_days direct nehmen (default terms days!).

    issue_date = datetime.strptime(data["quote"]["issue_date"], "%Y-%m-%d").date()
    payment_days = int(data.get("payment", {}).get("terms_days", 14))

    vat_rate_percent = int(data.get("tax", {}).get("rate", 19))

    if "due_date" in data:
        due_date = datetime.strptime(data["due_date"], "%Y-%m-%d").date()
    else:
        due_date = issue_date + timedelta(days=payment_days)

    data["due_date"] = due_date.isoformat()


    # Totals berechnen

    net_total = Decimal("0.00")

    for line in lines:
        qty = Decimal(str(line["quantity"]))
        price = Decimal(str(line["unit_price"]))
        net_total += qty * price

    net_total = net_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    vat_rate = Decimal(vat_rate_percent/100)
    vat_amount = (net_total * vat_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    gross_total = net_total + vat_amount

    def eur(x):
        return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    data["net_total"] = eur(net_total)
    data["vat_amount"] = eur(vat_amount)
    data["gross_total"] = eur(gross_total)
    data["vat_rate_percent"] = vat_rate_percent

    # Verzug und Zinsen berechnen

    today = date.today()

    # -----------------------------
    # Verzugstage berechnen
    # -----------------------------
    if today > due_date:
        days_in_delay = (today - due_date).days
    else:
        days_in_delay = 0

    data["days_in_delay"] = days_in_delay

    # -----------------------------
    # Verzugszins berechnen (B2B)
    # -----------------------------
    if days_in_delay > 0:
        interest_rate = (BASE_RATE + Decimal("9.00")) / Decimal("100")
        delay_interest = (
            Decimal(gross_total)
            * interest_rate
            * Decimal(days_in_delay)
            / Decimal("365")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        delay_interest = Decimal("0.00")

    default_compensation_fee = 40.00 # Verzugspauschale gem. § 288 Abs. 5 BGB: 40,00€ 

    total_claim = (
        Decimal(gross_total)
        + Decimal(delay_interest)
        + Decimal(default_compensation_fee)
    ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    # Letzte Frist setzen
 
    final_deadline = today + timedelta(days=DUNNING_DAYS)
        

    data["delay_interest"] = eur(delay_interest)
    data["delay_interest_raw"] = delay_interest
    data["default_compensation_fee"] = eur(default_compensation_fee)
    data["total_claim"] = eur(total_claim)
    data["date_today"] = today
    data["final_deadline"] = final_deadline
    data["final_days"]     = Decimal(DUNNING_DAYS)


    # Template...    

    env = Environment(
    loader=FileSystemLoader("."),
    block_start_string='<%',
    block_end_string='%>',
    variable_start_string='<<',
    variable_end_string='>>',
    comment_start_string='<#',
    comment_end_string='#>',
    autoescape=False,  # LaTeX != HTML
    )

    env.filters["latex"] = latex_escape

    # -----------------------------
    # Render LaTeX
    # -----------------------------
    template = env.get_template(template_path)
    rendered_tex = template.render(**data)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(rendered_tex)

    print(f"Wrote {out_path}")

    pdf_path = out_path.replace(".tex", ".pdf")
    lco_abs = os.path.abspath(LCO_DIR)
    env = os.environ.copy()
    env["TEXINPUTS"] = f"{lco_abs}:"

    for _ in range(2):  # two passes for cross-references
        result = subprocess.run(
            ["lualatex", "--interaction=nonstopmode", out_path],
            env=env,
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            print(result.stdout[-3000:])
            sys.exit(result.returncode)

    print(f"Wrote {pdf_path}")


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: render_quote.py quote.yaml template.tex.j2")
        sys.exit(1)

    quote_id = os.path.splitext(os.path.basename(sys.argv[1]))[0]  # e.g. quote_AN20260002
    main(sys.argv[1], sys.argv[2], f"{quote_id}.tex")
    



