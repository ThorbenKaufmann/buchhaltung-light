## Eine Rechnung anlegen im YAML Format

## Rechnung generieren

### Rendern

1. factur-x Format
```bash
./render_facturx.py ./data/invoice_RE20260001.yaml ./templates/factur-x.en16931.xml.j2  build/invoice_RE20260001.xml
```
```bash
facturx-xmlcheck build/invoice_RE20260001.xml
```

```bash
2026-02-18 17:02:25,507 [INFO] xmlcheck version 0.4 using factur-x lib version 3.15
2026-02-18 17:02:25,507 [INFO] Flavor is factur-x (autodetected)
2026-02-18 17:02:25,507 [INFO] Level is en16931 (autodetected)
2026-02-18 17:02:25,508 [INFO] factur-x XML file successfully validated against XSD
```

2. PDF
```bash
./render_invoice.py ./data/invoice_RE20260001.yaml ./templates/invoice.tex.j2  build/invoice_RE20260001.tex
TEXINPUTS=../../config/latex/lco/: xelatex build/invoice_RE20260001.tex
```


### Aggregieren

facturx-pdfgen invoice_RE20260001.pdf build/invoice_RE20260001.xml invoice_RE20260001_x.pdf

## Zahlungserinnerung generieren


## Mahnung generieren

./render_invoice.py ./data/invoice_RE20260001.yaml ./templates/dunning_letter_easy.tex.j2  build/invoice_RE20260001_dunning_letter.tex
TEXINPUTS=../../config/latex/lco/: xelatex build/invoice_RE20260001_dunning_letter.tex 


