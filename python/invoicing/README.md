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
```

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
