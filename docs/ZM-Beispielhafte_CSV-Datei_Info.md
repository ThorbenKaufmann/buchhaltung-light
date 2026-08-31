# Beispielhafte CSV-Datei
Das folgende Beispiel einer CSV-Datei kann mit Hilfe der Importfunktion in das Formular importiert werden. Das Beispiel dient lediglich zur Veranschaulichung der Importfunktion und stellt keinen realen Datensatz dar.

```
#v3.0
#ve3.2.1
Umsatzsteuer-Identifikationsnummer (USt-IdNr.),Summe (Euro),Art der Leistung
FRWL247100014,12345678911,L
HR12345678903,-12345678911,D
HR12345678900,2000,S
IE8Z49289F,1,D
IE3628739L,2,L
IE3628739UA,3,S
IE4769510A,3,D
IE8285018I,3,D
BG0101010007,4,D
EE100217418,5,L
ESW0068209F,7,D
IT00000008888,8,L
IT00000009993,6,S
BE1082047173,6,S
```

## Datensatztabellen und Satzarten
Die folgenden Datensatztabellen beschreiben alle in der Importfunktion verfügbaren Satzarten.

Es können maximal 1500 Datenzeilen in einer CSV-Datei importiert werden.

### Legende der Abkürzungen des Formats in der Spaltenbeschreibung:

| Abkürzung | Format |
|---|---|
|A oder AN	| alphanumerisch, d.h. Text und Ziffern |
| N	| numerisch, d.h. Ziffern |
| (X) | X ist die Anzahl maximal angebbarer Zeichen|

### Datensatztabelle Meldezeilen (Satzart 1)

| Feldbezeichnung |	Format | Erläuterung | Pflichtfeld |
|---|---|---|---|
| Umsatzsteuer-Identifikationsnummer (USt-IdNr.) | AN(7,14)	| Die Umsatzsteuer-Identifikationsnummer muss mit dem Länderkennzeichen, bestehend aus zwei Großbuchstaben A bis Z, beginnen. Die gültigen Länderkennzeichen finden Sie in der Liste der Länderkennzeichen. Die folgenden Zeichen können Buchstaben, Ziffern oder die Zeichen + und * sein. Nicht erlaubt sind Leerzeichen, Sonderzeichen und Umlaute. Die Angabe zur Umsatzsteuer-Identifikationsnummer muss mindestens 7 Zeichen enthalten. | Pflicht |
| Summe (Euro) | N(11) | Betrag in Euro. Dieses Feld beinhaltet eine ganze Zahl. Die Anzahl der Ziffern darf nicht größer als 11 sein, mit dem negativen Vorzeichen 12. Zulässige Zeichen sind die Ziffern 0 bis 9 und das Minuszeichen.| Pflicht |
| Art der Leistung | A(1) | Dieses Feld gibt an, ob es sich um ein Dreiecksgeschäft, eine innergemeinschaftliche Lieferung oder eine sonstige Leistung handelt. Zulässige Eingaben: D ( = Dreiecksgeschäft), L ( = Innergemeinschaftliche Lieferung), S ( = Sonstige Leistung) | |

### Liste der Länderkennzeichen
Die folgende Tabelle enthält die Liste der zulässigen Länderkennzeichen mit dem Hinweis, ab wann die jeweilige Länderkennzeichen in einer Zusammenfassenden Meldung verwendet werden dürfen.

| Länderkennzeichen	| Kommentar |
|---|---|
| AT |  |
| BE |  |
| BG | Ab 01.01.2007 |
| CY | Ab 01.05.2004 |
| CZ | Ab 01.05.2004 |
| DK |  |
| EE | Ab 01.05.2004 |
| EL |  |
| ES |  |
| FI |  |
| FR |  |
| GB | Bitte beachten Sie die Auswirkungen des Brexits |
| HR | Ab 01.07.2013 |
| HU | Ab 01.05.2004 |
| IE |  |
| IT |  |
| LT | Ab 01.05.2004 |
| LU |  |
| LV | Ab 01.05.2004 |
| MT | Ab 01.05.2004 |
| NL |  |
| XI | Bitte beachten Sie die Auswirkungen des Brexits. |
| PL | Ab 01.05.2004 |
| PT |  |
| RO | Ab 01.01.2007 |
| SE |  |
| SI | Ab 01.05.2004 |
| SK | Ab 01.05.2004 |