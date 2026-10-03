# Klusapp — De Groene M

Urenregistratie-webapp voor hoveniersbedrijf De Groene M (Maasdijk, ~6 medewerkers),
gebouwd door HandigerAI. Contactpersoon bij de klant: Maarten (M. Morée).

**Lees eerst [docs/SPEC.md](docs/SPEC.md).** Daar staat wat er gebouwd moet worden,
welke ontwerpkeuzes al vastliggen en wat nog open is.

**Daarna [CONTEXT.md](CONTEXT.md)** voor de aanpak van fase 1: wat er al af is, in welke
volgorde we bouwen, wie welk spoor doet en wat er per taak aan tijd staat.

**Bij UI-werk: [../DESIGN.md](../DESIGN.md).** De glass-stijl (kleuren, typografie,
spacing, radius-schaal, componenten) als opzoekbaar naslagwerk — gedeeld met de
root-tool, met de groene accentkleur van klusapp als het enige verschil. Vervangt de
regel "kopiëren, niet verzinnen" uit `../CONTEXT.md` niet, maakt 'm alleen sneller
te checken zonder eerst `glass.html` en app.css te moeten doorzoeken.

## Status

Contract is opgesteld (fase 1 verplicht, fase 2 en twee uitbreidingen optioneel).
De klikbare demo heeft zijn werk gedaan en wordt niet meer aangepast; dit is de
echte bouw, en die draait live op develop.handigerai.nl.

**Sinds 16-09-2026 hebben alle negen contractpunten van fase 1 een werkend
scherm en staan ze live.** `nog_te_bouwen` in `config/urls.py` is leeg en geen
tegel staat meer op `in_aanbouw`. Op 24-09-2026 is de lijst nagelopen tegen
artikel 2 én tegen het gespreksverslag met Maarten; de negen punten staan.
**Per contractpunt staat de stand in [CONTEXT.md](CONTEXT.md) §1.**

Wat nog open staat, is geen contractpunt maar komt wel uit de contractreview
(SPEC §8) en uit dat gesprek:

- De productiepunten in [docs/DEPLOY.md](docs/DEPLOY.md) — een échte off-site
  back-up voorop. De klusfoto's bestaan nergens anders. Uren en aanwezigheid
  gaan sinds 01-10-2026 wekelijks per mail de deur uit, vanaf
  kennismaken@handigerai.nl naar het adres dat de eigenaar op Mijn profiel zet
  (`uren/backup.py`).
- Data-export bij beëindiging en een periode op slot kunnen zetten.
- Vijf vragen in [docs/VRAGEN-MAARTEN.md](docs/VRAGEN-MAARTEN.md) hebben nog
  geen antwoord (2, 3, 6, 7 en 9). Vraag 4, 8 en 10 zijn op 01-10-2026
  beantwoord en gebouwd; zie CONTEXT.md §1.
- De lijst met negen onderdelen die Maarten zelf zou opsturen, is nooit
  binnengekomen. We bouwen tot nu toe op het gespreksverslag.

Houd die twee documenten bij als je iets aflevert. Ze liepen in september 2026
achter op de code, en de volgende die eraan begon heeft daardoor werk gepland dat
al af was.

## Werkafspraken

- Nederlands in de app, in commits en in gesprek met Floris.
- **Korte feature-branches**, zelf mergen naar `main` zonder PR-ceremonie. `main`
  ís de develop-omgeving en moet altijd draaien, dus geen half afgemaakte
  schermen daarheen. Bestandseigendom en wie welk spoor doet: CONTEXT.md §3.
- Schermen die nog gebouwd worden hebben hun url-naam al geregistreerd in
  `config/urls.py` en staan als gedimde tegel in `medewerkers/views.py:TEGELS`.
  Bouw je er een, haal dan de route daar weg en de vlag `in_aanbouw` uit de
  tegel — verder hoeft niemand die lijst aan te raken.
- De scope van fase 1 is de lijst in SPEC.md, één op één overgenomen uit artikel 2
  van het contract. Wat daar niet in staat is meerwerk — bouw het niet ongevraagd.
- De app maakt **geen facturen**. Alleen urenoverzichten die de boekhouder verwerkt.
- Alles moet werken op een telefoon. De medewerker vult zijn uren 's avonds in de
  bus in, niet achter een bureau.
- Het Django-beheerscherm op `/beheer/` is bedoeld voor HandigerAI, niet voor de
  klant: het toont alle velden en verwijdert zonder vangnet. Wat Maarten
  dagelijks moet kunnen krijgt daarom een eigen scherm in de stijl van de app —
  zie `/medewerkers/`.
  **Tijdelijk (sept. 2026):** er is nog geen apart beheeraccount, dus een
  eigenaar krijgt voorlopig wél toegang tot `/beheer/`. Dat hangt aan één regel
  in `Medewerker.save()`. Zodra dat account er is, moet die toegang weer los van
  de rol "eigenaar" komen te staan.
- **Tijdelijk (sept. 2026):** een eigenaar kan onderaan het startscherm met één
  tik als medewerker meekijken ("Bekijk als medewerker"), en via de balk
  bovenaan elk scherm terug. Handig om te testen, maar het is inloggen als
  iemand anders zonder zijn wachtwoord. Alles staat bij `wissel_naar` in
  `medewerkers/views.py`.
- **Twee omgevingen (okt. 2026):** develop.handigerai.nl om te testen en
  degroenem.handigerai.nl voor Maarten, met eigen database en zonder testdata.
  Op die laatste staan de twee tijdelijke dingen hierboven uit
  (`KLUSAPP_TESTFUNCTIES=0`), en hij updatet alleen met de hand via
  `docs/deploy-degroenem.sh`. Zie docs/DEPLOY.md.
- **Verborgen accounts:** `Medewerker.objects` slaat accounts met `verborgen`
  over (het HandigerAI-account `admin`); `Medewerker.alle` niet. Gebruik dus
  `objects` voor alles wat Maarten te zien krijgt.

## Lokaal draaien

```
.venv\Scripts\python manage.py runserver
```

Testgebruikers maak je met `python maak_testdata.py`: `maarten` (eigenaar) en
`sam` (medewerker), beide met wachtwoord `test1234`. Alleen voor lokaal.

Tests: `.venv\Scripts\python manage.py test` — de hele suite draait in een
seconde of tien. Tijdens het testen schakelt `settings.py` over op een snelle
wachtwoord-hasher; zonder dat duurde dezelfde suite twee en een halve minuut,
want bijna alle tijd ging op aan het hashen van testwachtwoorden.

## Stack

Django 6.1 op Python 3.14, server-gerenderde templates. Lokaal SQLite, op de VPS
Postgres — dat schakelt via `DATABASE_URL`. Statische bestanden via WhiteNoise,
dus geen aparte webserver nodig voor CSS.

Geen HTMX, geen frontend-framework: gewone formulieren, en waar het echt nodig
is een klein script naast de pagina (zie `static/js/kalender.js`). Voeg er geen
bij zonder overleg — dit is een app van acht schermen, geen SPA.

Geüploade foto's worden verkleind opgeslagen, niet als origineel
(`klussen/afbeeldingen.py`), en uitgeleverd via een view die op inloggen
controleert (`klussen.views.media_bestand`). Zet `MEDIA_ROOT` dus nooit open als
statische map.

Het uren-invoerscherm is het enige scherm dat later mogelijk client-side moet
worden, namelijk als blijkt dat uren schrijven offline moet werken. Houd dat
scherm daarom los van de rest.
