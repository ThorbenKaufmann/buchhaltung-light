#!/usr/bin/env python3
import os
import subprocess
import sys
from datetime import date, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP

import yaml
from jinja2 import Environment, FileSystemLoader

BASE_RATE    = Decimal("1.27")   # Basiszinssatz
DUNNING_DAYS = 7

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
LCO_DIR    = os.path.join(SCRIPT_DIR, "../../config/latex/lco")


# -----------------------------
# Helpers
# -----------------------------

def latex_escape(text):
    if text is None:
        return ""
    replacements = {
        '\\': r'\textbackslash{}',
        '&':  r'\&',
        '%':  r'\%',
        '$':  r'\$',
        '#':  r'\#',
        '_':  r'\_',
        '{':  r'\{',
        '}':  r'\}',
        '~':  r'\textasciitilde{}',
        '^':  r'\textasciicircum{}',
    }
    for k, v in replacements.items():
        text = text.replace(k, v)
    return text


def eur(x):
    return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


# -----------------------------
# Business Logic
# -----------------------------

def compute_data(data):
    lines = data["lines"]

    issue_date   = datetime.strptime(data["invoice"]["issue_date"], "%Y-%m-%d").date()
    payment_days = int(data.get("payment", {}).get("terms_days", 14))
    vat_rate_pct = int(data.get("tax", {}).get("rate", 19))

    if "due_date" in data:
        due_date = datetime.strptime(data["due_date"], "%Y-%m-%d").date()
    else:
        due_date = issue_date + timedelta(days=payment_days)

    data["due_date"] = due_date.isoformat()

    net_total = Decimal("0.00")
    for line in lines:
        net_total += Decimal(str(line["quantity"])) * Decimal(str(line["unit_price"]))
    net_total   = net_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    vat_amount  = (net_total * Decimal(vat_rate_pct) / 100).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    gross_total = net_total + vat_amount

    data["net_total"]        = eur(net_total)
    data["vat_amount"]       = eur(vat_amount)
    data["gross_total"]      = eur(gross_total)
    data["vat_rate_percent"] = vat_rate_pct

    today = date.today()
    days_in_delay = (today - due_date).days if today > due_date else 0
    data["days_in_delay"] = days_in_delay

    if days_in_delay > 0:
        interest_rate  = (BASE_RATE + Decimal("9.00")) / Decimal("100")
        delay_interest = (
            gross_total * interest_rate * Decimal(days_in_delay) / Decimal("365")
        ).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    else:
        delay_interest = Decimal("0.00")

    default_compensation_fee = Decimal("40.00")
    total_claim = (gross_total + delay_interest + default_compensation_fee).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )

    data["delay_interest"]           = eur(delay_interest)
    data["delay_interest_raw"]       = delay_interest
    data["default_compensation_fee"] = eur(default_compensation_fee)
    data["total_claim"]              = eur(total_claim)
    data["date_today"]               = today
    data["final_deadline"]           = today + timedelta(days=DUNNING_DAYS)
    data["final_days"]               = Decimal(DUNNING_DAYS)

    return data


# -----------------------------
# Render + compile
# -----------------------------

def render_tex(data, template_path, out_path):
    env = Environment(
        loader=FileSystemLoader("."),
        block_start_string='<%',
        block_end_string='%>',
        variable_start_string='<<',
        variable_end_string='>>',
        comment_start_string='<#',
        comment_end_string='#>',
        autoescape=False,
    )
    env.filters["latex"] = latex_escape
    template = env.get_template(template_path)
    with open(out_path, "w", encoding="utf-8") as f:
        f.write(template.render(**data))
    print(f"Wrote {out_path}")


def compile_pdf(tex_path):
    env = os.environ.copy()
    env["TEXINPUTS"] = f"{os.path.abspath(LCO_DIR)}:"
    for _ in range(2):
        result = subprocess.run(
            ["lualatex", "--interaction=nonstopmode", tex_path],
            env=env, capture_output=True, text=True,
        )
        if result.returncode != 0:
            print(result.stdout[-3000:])
            sys.exit(result.returncode)
    pdf_path = tex_path.replace(".tex", ".pdf")
    print(f"Wrote {pdf_path}")


# -----------------------------
# Main
# -----------------------------

def main(yaml_path, template_path):
    with open(yaml_path) as f:
        data = yaml.safe_load(f)

    data = compute_data(data)

    invoice_stem  = os.path.splitext(os.path.basename(yaml_path))[0]    # invoice_RE20260001
    template_stem = os.path.splitext(os.path.splitext(os.path.basename(template_path))[0])[0]  # dunning_letter_easy
    tex_path = f"{invoice_stem}_{template_stem}.tex"

    render_tex(data, template_path, tex_path)
    compile_pdf(tex_path)


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("usage: render_dunning.py invoice.yaml template.tex.j2")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2])
