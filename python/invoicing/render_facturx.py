#!/usr/bin/env python3
import sys
import yaml
from datetime import datetime
from jinja2 import Environment, FileSystemLoader


def yyyymmdd(value):
    return datetime.strptime(value, "%Y-%m-%d").strftime("%Y%m%d")


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

    issue_date = datetime.strptime(data["invoice"]["issue_date"], "%Y-%m-%d").date()
    payment_days = int(data.get("payment", {}).get("terms_days", 14))

    if "due_date" in data:
        due_date = datetime.strptime(data["due_date"], "%Y-%m-%d").date()
    else:
        due_date = issue_date + timedelta(days=payment_days)

    data["due_date"] = due_date.isoformat()



    net_total = Decimal("0.00")

    for line in lines:
        qty = Decimal(str(line["quantity"]))
        price = Decimal(str(line["unit_price"]))
        net_total += qty * price

    net_total = net_total.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    vat_rate = Decimal("0.19")
    vat_amount = (net_total * vat_rate).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    gross_total = net_total + vat_amount

    def eur(x):
        return f"{x:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")

    data["net_total"] = eur(net_total)
    data["vat_amount"] = eur(vat_amount)
    data["gross_total"] = eur(gross_total)
    data["vat_rate_percent"] = 19

    data["totals"] = {
    "net": f"{net_total:.2f}",
    "tax": f"{vat_amount:.2f}",
    "gross": f"{gross_total:.2f}",
    "prepaid": "0.00",
    "payable": f"{gross_total:.2f}",
}


    # Template

    env = Environment(loader=FileSystemLoader("."))
    env.filters["yyyymmdd"] = yyyymmdd

    template = env.get_template(template_path)

    xml_output = template.render(**data)

    with open(out_path, "w", encoding="utf-8") as f:
        f.write(xml_output)

    print(f"Wrote {out_path}")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        print("usage: render_facturx.py invoice.yaml template.xml.j2 output.xml")
        sys.exit(1)

    main(sys.argv[1], sys.argv[2], sys.argv[3])
