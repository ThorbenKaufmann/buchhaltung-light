# Invoicing

Generates business letters (invoices, quotes, order confirmations, purchase
orders, dunning letters) from YAML data + Jinja2/LaTeX templates, and embeds a
Factur-X (EN16931) e-invoice into invoice PDFs.

## Requirements

### 1. LaTeX — **LuaLaTeX**
The templates use `fontspec`, so they compile **only** with `lualatex`
(the `render_*.py` scripts call `lualatex --interaction=nonstopmode`).
`pdflatex` will **not** work.

**Minimum: TeX Live 2021** (known-good: TeX Live 2023). Older distributions
ship outdated `fontspec`/`fontawesome5`/Roboto and fail to compile — an old
TeX Live is a common cause of build errors on a fresh machine. Check with
`lualatex --version`; on Debian/Ubuntu an apt TeX Live can lag well behind, so
prefer the [upstream installer](https://tug.org/texlive/) if the packaged
version is too old.

Packages/fonts used by the templates and `business.lco`:
`fontspec` + the **Roboto** font (`\setmainfont{Roboto}`), `fontawesome5`,
`svg`, `graphicx`, `lastpage`, `xcolor`, `ragged2e`, `babel` (ngerman + english).

Debian/Ubuntu — the simplest is the full distribution:

```bash
sudo apt install texlive-full
```

Minimal set instead of `texlive-full`:

```bash
sudo apt install texlive-luatex texlive-fonts-extra texlive-latex-extra texlive-pictures
```

(`texlive-fonts-extra` provides Roboto — a common missing piece.)

Verify the toolchain:

```bash
which lualatex && luaotfload-tool --find=Roboto
```

If `lualatex` is missing → install TeX Live. If Roboto isn't found →
install `texlive-fonts-extra`.

### 2. Python
Dependencies are pinned in the repo-root `requirements.txt`:

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

The `factur-x` package provides the `facturx-pdfgen` CLI used to embed the
e-invoice XML. If it is missing, `render_invoice.py` prints a warning and
produces the plain PDF **without** the embedded XML (no crash).

### 3. Letter branding — `business.lco` (**not in git**)
`\documentclass[business,…]{scrlttr2}` loads `config/latex/lco/business.lco`
(the KOMA letterhead: company address, footer, logo). This file and the logo
PDFs are **git-ignored** (`.gitignore`) because they carry company-specific
branding, so a fresh clone does **not** have them — this is the most common
reason "it doesn't compile on a teammate's machine".

To get a working (placeholder-branded) letterhead:

```bash
cp config/latex/lco/business.lco.example config/latex/lco/business.lco
```

The `.example` references the committed `banner.png`, so it compiles out of the
box. Edit `business.lco` to set your own company name, address and logo. To use
a custom logo PDF, place it in `config/latex/lco/` and point the `fromlogo`
komavars at it — note `*.pdf` is git-ignored, so share logo files out-of-band.

## Usage

Run the scripts **from this directory** (`python/invoicing/`). Each takes a YAML
data file and a template; output files are written to the current directory.

```bash
# Invoice (also writes <base>.xml and <base>_x.pdf with embedded Factur-X)
python3 render_invoice.py            data/invoice_RE20260001.yaml templates/invoice.de.tex.j2

# Quote
python3 render_quote.py              data/quote_AN20260001.yaml   templates/quote.de.tex.j2

# Order confirmation
python3 render_order_confirmation.py data/poin_AN20260001.yaml    templates/order_confirmation.en.tex.j2

# Purchase order
python3 render_purchase_order.py     data/po_BE20260001.yaml      templates/purchase_order.de.tex.j2

# Dunning letter (takes the *invoice* YAML)
python3 render_dunning.py            data/invoice_RE20260001.yaml templates/dunning_letter.tex.j2

# Open items: list overdue invoices, then record a received payment
python3 scan_overdue.py              # --all: also not yet due, --paid: also settled
python3 record_payment.py RE20260002 --date 2026-09-18 --reference "Bank ref"

# Customer PO: what is left, projected run-out, reorder alarm (exit code 2)
python3 po_remaining.py              5000222104   # omit the PO to check all poin_*.yaml

# Quotes: open / lapsed / ordered (with PO budget left), close one by hand
python3 quotes.py                    # --all: also closed and fully invoiced
python3 quotes.py mark AN20260003 rejected --note "customer declined"
python3 quotes.py reopen AN20260003  # undo a mark
python3 quotes.py accept AN20260007 --po 5000225603 --order-date 2026-10-12

# Invoice against a customer PO (checks: PO budget left, PO period, overlaps)
python3 invoice_po.py 5000225603     --qty 1000=120.5 --period 2026-11-01..2026-11-27 --render

# Time log against customer POs (data/time/YYYY-MM.tsv) and activity report PDF
python3 timelog.py start "CAN driver bring-up" --po 5000225603   # stop: timelog.py stop
python3 timelog.py add 2026-11-03 13:30-17:05 "Spec review" --po 5000225603
python3 timelog.py list --from 2026-11-01 --to 2026-11-30       # internal: timestamps, gaps
python3 timelog.py report --invoice RE20260005                  # PO + period from the invoice

# Menu (whiptail) over the scripts above; the quote list is interactive:
# i invoice, a accepted, e expired, r rejected, u reopen, f filter, q back
python3 menu.py
```

A quote is *ordered* as soon as a `poin_*.yaml` references it
(`purchase.quote`); `quotes.py mark` writes a top-level `status:` block
(`rejected` / `expired`) into the quote YAML, edited as text like
`record_payment.py`. `quotes.py accept` writes the `poin_*.yaml` (the quote
plus a `purchase:` block, next free `PI<year><nnnn>`); an optional
`purchase.confirmation_date` becomes the letter date of the order
confirmation, otherwise the order date is used.

`record_payment.py` appends to a `payments:` block in the invoice YAML
(`--amount` defaults to the open remainder; partial payments are fine) and
refuses duplicates and overpayments unless `--force`. It edits the file as
text so comments survive. The accounting side — linking the bank transaction
to the outgoing voucher — is still done in the bookkeeping DB.

The time log keeps raw timestamps; rounding happens only in reports: each
block is rounded up to 15 minutes (`--step`), but never past the start of the
operator's next block, so seamless task switches are not billed twice. The
activity report uses the company report layout (`config/latex/firmenbericht`,
via `python/reporting/firmenlayout.py`), German for German buyers, English
otherwise; operator codes resolve via `data/time/operators.yaml`.

Data files live in `data/`, which is **git-ignored** (they contain real customer
data), so no sample YAMLs ship with the repo — copy the field structure from an
existing file. Factur-X is invoice-only; the other document types produce a PDF
only.

## Template conventions

- Jinja delimiters are customised for LaTeX: `<< expr >>` for values,
  `<% stmt %>` for blocks (so `{}` stays literal for LaTeX). The Factur-X XML
  template uses the standard `{{ }}` / `{% %}`.
- Free-text values are escaped for their target format: `| latex` in `.tex.j2`
  templates, and the XML template renders with Jinja `autoescape` on. Money
  columns use the `| eur` filter (`1.234,56`).
