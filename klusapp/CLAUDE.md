# Klusapp — De Groene M

Urenregistratie-webapp voor hoveniersbedrijf De Groene M (Maasdijk, ~6 medewerkers),
gebouwd door HandigerAI. Contactpersoon bij de klant: Maarten (M. Morée).

**Lees eerst [docs/SPEC.md](docs/SPEC.md).** Daar staat wat er gebouwd moet worden,
welke ontwerpkeuzes al vastliggen en wat nog open is.

## Status

Contract is opgesteld (fase 1 verplicht, fase 2 en twee uitbreidingen optioneel).
Er is een klikbare demo geweest — die heeft zijn werk gedaan en wordt niet meer
aangepast. Dit is de echte bouw. Er staat nog geen regel productiecode.

De stack ligt nog niet vast. Dat is het eerste gesprek dat gevoerd moet worden.

## Werkafspraken

- Nederlands in de app, in commits en in gesprek met Floris.
- De scope van fase 1 is de lijst in SPEC.md, één op één overgenomen uit artikel 2
  van het contract. Wat daar niet in staat is meerwerk — bouw het niet ongevraagd.
- De app maakt **geen facturen**. Alleen urenoverzichten die de boekhouder verwerkt.
- Alles moet werken op een telefoon. De medewerker vult zijn uren 's avonds in de
  bus in, niet achter een bureau.
- Het Django-beheerscherm op `/beheer/` is voor HandigerAI, niet voor de klant.
  De rol "eigenaar" geeft er geen toegang toe; daar is `is_staff` voor, en die
  twee zijn bewust niet aan elkaar geknoopt. Wat Maarten dagelijks moet kunnen
  krijgt een eigen scherm in de stijl van de app.

## Lokaal draaien

```
.venv\Scripts\python manage.py runserver
```

Testgebruikers maak je met `python maak_testdata.py`: `maarten` (eigenaar) en
`sam` (medewerker), beide met wachtwoord `test1234`. Alleen voor lokaal.

Tests: `.venv\Scripts\python manage.py test`

## Stack

Django 6.1 op Python 3.14, server-gerenderde templates, HTMX voor de
interactieve stukken. Lokaal SQLite, op de VPS Postgres — dat schakelt via
`DATABASE_URL`. Statische bestanden via WhiteNoise, dus geen aparte webserver
nodig voor CSS.

Het uren-invoerscherm is het enige scherm dat later mogelijk client-side moet
worden, namelijk als blijkt dat uren schrijven offline moet werken. Houd dat
scherm daarom los van de rest.
