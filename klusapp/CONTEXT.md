# Fase 1 — aanpak en taakverdeling

**Voor:** Thijmen en Floris. **Bijgewerkt:** 13 september 2026.

Dit document gaat over *hoe* we fase 1 bouwen en wie wat doet.
Wat er gebouwd moet worden staat in [docs/SPEC.md](docs/SPEC.md) — dat blijft de
bron van waarheid, dit document niet.

---

## 1. Waar we staan

De Groene M (hoveniersbedrijf, ~6 medewerkers, contactpersoon Maarten Morée) geeft
uren nu door in een WhatsApp-groep. Die groep verdwijnt zodra deze app er is — er is
dan geen terugval meer. Contract artikel 2 legt negen verplichte onderdelen vast voor
fase 1 (€ 1.350 / 45 uur); wat daar niet in staat is meerwerk.

Er staat al meer dan je zou denken. Het Django-skelet, het datamodel, inloggen, het
startscherm met rolgebaseerde tegels, de weekkalender voor uren schrijven en de
loonstrook-snelkoppeling zijn af. **De app draait live op develop.handigerai.nl.**

Wat ontbreekt is bijna alles rond klussen en foto's: zes van de negen contractpunten
hebben nog geen scherm.

| # | Contractpunt | Status | Wat ontbreekt |
|---|---|---|---|
| 1 | Urenregistratie (klus, tijdblok, toelichting, **foto's**) | 🟡 ~70% | Foto's bij een uurblok; view-first detailscherm |
| 2 | Klusdossier per klus | 🔴 0% | `klussen/views.py` is leeg, geen urls, geen templates |
| 3 | Overzicht per medewerker week **en maand** | 🟡 ~30% | Week zit in de kalender; maand ontbreekt, tegel is dood |
| 4 | Beheerdersoverzicht / planbord | 🔴 0% | Tegel is dood |
| 5 | Fotodropbox | 🟡 ~40% | Kaal scherm + upload staan (0c); filters en "koppel aan klus" = T1 |
| 6 | Urenexport voor de boekhouder | 🔴 0% | **Geblokkeerd** op vraag aan Maarten |
| 7 | Aanwezigheidsregistratie | 🟡 10% | Model + constraint + test staan er, geen UI |
| 8 | Inlogbeheer rolgebaseerd | 🟢 ~80% | Eigenaar kan zelf geen medewerker toevoegen/uit dienst zetten |
| 9 | Loonstrook-snelkoppeling | 🟢 100% | Klaar, iOS/Android afgehandeld, getest |

Het datamodel loopt voor op de schermen: `Klus`, `Bijlage`, `Uurblok` en
`Aanwezigheid` staan er mét constraints, indexen en tests. Er hoeft weinig model bij —
het werk zit in views, templates en opslag.

## 2. Het uitgangspunt: de klus is de spil

Bouw de hiërarchie vanuit de klus op. Een klus bevat uren (per persoon), foto's en
documenten — precies wat fase 1 vraagt. Dat fundament eerst, en pas daarna splitsen:
**Floris op uren, Thijmen op foto's.**

De reden om het zo te doen: klusdossier (punt 2), foto's bij een uurblok (punt 1) en
de fotodropbox (punt 5) hangen alledrie aan hetzelfde `Bijlage`-model. Bouwt ieder dat
apart, dan staan er straks drie upload-implementaties.

## 2b. URL-kaart

Vastgelegd in blok 0a. De namen zijn geregistreerd in `config/urls.py`, ook van schermen
die nog niet bestaan — zo kan de rest van de app er nu al naar verwijzen en hoeft niemand
halverwege links om te hangen. Bouw je een scherm, haal dan de route uit `config/urls.py`,
zet 'm in de `urls.py` van je eigen app, en haal de vlag `in_aanbouw` uit de tegel in
`medewerkers/views.py`.

| Pad | Naam | Scherm | Van wie |
|---|---|---|---|
| `/uren/` | `mijn_uren` | uren schrijven | ✅ af |
| `/fotos/` | `fotos` | fotodropbox | ✅ kaal (0c) → T1 |
| `/bijlagen/toevoegen/` | `bijlage_toevoegen` | upload, generiek | ✅ af (0c) |
| `/bijlagen/<pk>/verwijderen/` | `bijlage_verwijderen` | | ✅ af (0c) |
| `/media/<pad>` | `media_bestand` | bestand achter login | ✅ af (0c) |
| `/loonstrook/` | `loonstrook` | | ✅ af |
| `/klussen/` | `klussen` | klussenlijst | 0b Floris |
| `/klussen/<pk>/` | `klus_detail` | klusdossier | 0b Floris |
| `/overzicht/` | `mijn_overzicht` | week en maand | F2 Floris |
| `/planbord/` | `planbord` | planbord eigenaar | F3 Floris |
| `/aanwezigheid/` | `aanwezigheid` | groen/rood | F4 Floris |
| `/export/` | `urenexport` | boekhouder | T3 Thijmen |

## 3. Werkafspraken

- **Korte feature-branches.** Elk scherm een branch van maximaal 1–2 dagen, zelf mergen
  naar `main` zonder PR-ceremonie. `main` ís de develop-omgeving en moet altijd
  draaien; half afgemaakte schermen horen daar niet. (Dit vervangt de "alleen main"-regel
  in `../CLAUDE.md` — dit is het overleg dat daar om gevraagd werd.)
- **Bestandseigendom.** Na blok 0 raakt alleen Floris `static/css/app.css`,
  `templates/basis.html` en de `TEGELS`-lijst in `medewerkers/views.py` aan. Nodig je
  daar iets, vraag het even — kost een minuut, scheelt een conflict.
- **Nederlands** in de app, in commits en onderling.
- **Geen facturen in de app.** Alleen urenoverzichten die de boekhouder verwerkt.
- **Telefoon eerst.** Elk scherm op 375px breed testen vóór het gemerged wordt. De
  medewerker vult zijn uren 's avonds in de bus in, niet achter een bureau.

## 4. Meenemen tijdens de bouw (geen aparte taken)

1. ~~**Foto's zijn straks niet zichtbaar.**~~ ✅ opgelost in 0c. Bestanden gaan langs
   `klussen.views.media_bestand`, die op inloggen controleert en paden buiten
   `MEDIA_ROOT` weigert. Voor productie staat `GEBRUIK_X_ACCEL` klaar in
   `settings.py`: nginx neemt het uitleveren dan over. → rest is taak T2.
2. **`date.today()` geeft 's avonds de verkeerde dag.** `uren/views.py:21` en `:40` en
   `medewerkers/views.py:51` gebruiken `date.today()` terwijl `USE_TZ=True` en
   `TIME_ZONE="Europe/Amsterdam"`. Op een UTC-server is dat na 22:00 een dag mis —
   precies het moment waarop uren worden ingevuld. `klussen/models.py:46` doet het al
   goed met `timezone.localdate()`. → taak F1.
3. **View-first is niet gevolgd.** SPEC §5: klikken op een blok toont hetzelfde scherm,
   niet bewerkbaar, met een bewerkknop. Nu gaat klikken direct naar bewerken
   (`templates/uren/mijn_uren.html:40`). → taak F1.
4. **De deploy-documentatie klopt niet meer.** `../CLAUDE.md` en `../README.md`
   beschrijven de Flask-tool op `:5001`, en `auto-deploy.sh` installeert de
   root-`requirements.txt` — die bevat alleen `flask`. De klusapp-requirements worden
   dus nooit geïnstalleerd; er is handmatig iets op de VPS ingericht dat nergens is
   vastgelegd. Bij de eerste storing is dat niet te herstellen. → taak T4.
5. ~~**`CLAUDE.md` in deze map is achterhaald.**~~ ✅ bijgewerkt in 0a.
6. ~~**Geen HTMX, wel genoemd in de stack.**~~ ✅ besloten in 0a: geen HTMX. Gewone
   formulieren, en waar nodig een klein script zoals `static/js/kalender.js`. Staat nu
   zo in `CLAUDE.md`.

---

## 5. Blok 0 — het fundament (≈ 7 uur)

Moet af zijn vóór de sporen splitsen: beide hangen eraan. 0b en 0c raken verschillende
bestanden en kunnen dus tegelijk.

### 0a · Samen, één sessie (~1,5 u) — ✅ gedaan

- URL-kaart vastgelegd in §2b hierboven — **niet** in `docs/SPEC.md`: dat document
  bakent de contractscope af, daar hoort geen technische URL-structuur in.
- Tegels bevroren: elke tegel heeft nu zijn definitieve `url_naam`, en wie nog niet af is
  staat op `in_aanbouw` (gedimd, niet klikbaar). Routes staan in `config/urls.py`.
- `CLAUDE.md` bijgewerkt: status, stack-zin, HTMX-zin, branch-afspraak.
- Vragen aan Maarten uitgewerkt in [docs/VRAGEN-MAARTEN.md](docs/VRAGEN-MAARTEN.md),
  met per vraag de fallback als het antwoord uitblijft.

### 0b · Floris — klussenlijst en klusdetail (~3 u) · contractpunt 2

Het geraamte waar al het andere in hangt.

- `klussen/urls.py` + `klussen/views.py` (nu leeg).
- **Klussenlijst**: filter actief/afgerond en aanleg/onderhoud, zoeken op naam, adres en
  opdrachtgever (`KlusAdmin.search_fields` heeft de velden al). Kleurstip per klus via
  `uren.kalender.kleur_van`.
- **Klusdetail** — de spil, vier secties onder elkaar:
  1. gegevens (opdrachtgever, adres, soort, kleur)
  2. **uren op deze klus**: wie, wanneer, hoeveel, totaal onderaan. Gebruik de bestaande
     index `["klus", "datum"]` en `kalender.als_uren()`.
  3. **foto's** — raster, partial uit taak 0c
  4. **documenten** — lijst, zelfde partial
- Rechten: een medewerker ziet het **volledige** dossier, maar alleen zijn eigen uren
  (SPEC §2). De eigenaar ziet alle uren. Test dat expliciet.
- Klus aanmaken en bewerken, alleen eigenaar.
- Gedeelde CSS-bouwstenen in `app.css`: tabel, lege staat, uploadveld, chip/badge,
  filterbalk, terugknop. Vormtaal letterlijk overnemen uit wat er staat — pill-knoppen,
  ronde hoeken, `.glas`, geen witte vlakken.
- Tests: lijst filtert, detail toont uren, medewerker ziet andermans uren niet.

### 0c · Thijmen — bijlagen-fundament (~2,5 u) — ✅ gebouwd

Blokkeert drie contractpunten (2, 1-foto's, 5). Hier begint het fotospoor.

**Voor Floris — dit kun je includen in klusdetail (0b):**

```django
{% include "klussen/_uploadveld.html" %}     {# formulier, upload_url, terug, klus_pk #}
{% include "klussen/_fotoraster.html" %}     {# foto_bijlagen, terug #}
{% include "klussen/_documentenlijst.html" %}{# document_bijlagen, terug #}
```

In je view: `BijlageForm()` als `formulier`, `reverse("bijlage_toevoegen")` als
`upload_url`, `request.get_full_path()` als `terug`, en de bijlagen gesplitst in
`foto_bijlagen` / `document_bijlagen` (`Bijlage.is_foto`). Het verwijderknopje regelt
zichzelf — de partial gebruikt het filter `mag_weg` uit
`klussen/templatetags/bijlagen.py`.

- Eén generieke upload-view voor alle drie de gevallen: bijlage aan een klus, aan een
  uurblok, of aan geen van beide (= dropbox). `Bijlage` heeft de velden al.
- Verkleinen met Pillow (staat al in `requirements.txt`): bewaar een versie van max
  ~2000px lange zijde plus een thumbnail, en **respecteer EXIF-rotatie** — telefoonfoto's
  komen anders gekanteld binnen. SPEC §6: ruwe foto's van een jaar lopen richting
  tientallen GB, verkleind richting enkele.
- Media serveren **achter login** (zie §4.1). In DEBUG via een view, in productie via
  `X-Accel-Redirect`.
- Rechten: iedereen mag toevoegen; verwijderen alleen je eigen bijlage, of eigenaar.
  "Toegevoegd door" en "wanneer" gaan automatisch (SPEC §5).
- Herbruikbare partials `_fotoraster.html` en `_documentenlijst.html` die Floris in
  klusdetail include't — spreek de contextnaam nu af.
- Tests: upload verkleint, EXIF-rotatie klopt, media zonder login geeft 302/403.

---

## 6. Spoor Floris — uren (≈ 14 uur)

| Taak | Punt | Uur |
|---|---|---|
| F1 · Uurblok afmaken | 1 | 3 |
| F2 · Mijn overzicht: week en maand | 3 | 3 |
| F3 · Planbord voor de eigenaar | 4 | 5 |
| F4 · Aanwezigheidsregistratie | 7 | 3 |

**F1 · Uurblok afmaken.** Foto's bij een uurblok via de partial uit 0c, met een eigen
toelichting per bijlage (SPEC §5: bijlagen hangen aan het uurblok, niet alleen aan de
klus). View-first detailscherm bouwen (§4.3). En `date.today()` vervangen door
`timezone.localdate()` (§4.2), met een test die de dag rond middernacht vastzet.

**F2 · Mijn overzicht.** Maandoverzicht naast de bestaande weekkalender: totaal per week,
per klus en per dag. Hergebruik `kalender.als_uren()`. Eigenaar kan een medewerker
kiezen, medewerker ziet alleen zichzelf. Vult de dode tegel "Mijn overzicht" en levert de
cijfers waar T3 op leunt — **stem het queryset met Thijmen af**, één berekening, niet twee.

**F3 · Planbord.** Rijen zijn medewerkers, kolommen zijn dagen — géén dagkalender
(SPEC §5, expliciet beslecht: met zes mensen op een dag worden blokken vijftien pixels
breed). Eerste kolom blijft staan bij horizontaal scrollen. Blokken tonen begintijd en
duur, niet de omschrijving; de kleur draagt de klusidentiteit. Hergebruik
`uren/kalender.py` (`kleur_van`, `als_uren`) en de weeknavigatie uit `mijn_uren.html`;
klik door naar het blokdetail uit F1. Zwaarste taak, en het scherm waar Maarten dagelijks
in kijkt.

**F4 · Aanwezigheid.** Dagscherm voor de eigenaar: alle medewerkers op een rij,
groen/rood tikken, optionele opmerking. Model, unique-constraint en test bestaan al
(`uren/models.py:Aanwezigheid`). Medewerker ziet het alleen-lezen. Hoort in dit spoor
omdat het dezelfde weeknavigatie en medewerkersrij gebruikt als het planbord.

## 7. Spoor Thijmen — foto's, export en productie (≈ 15 uur)

| Taak | Punt | Uur |
|---|---|---|
| T1 · Fotodropbox | 5 | 3 |
| T2 · Fotoopslag productiewaardig | SPEC §6 | 3 |
| T3 · Urenexport boekhouder | 6 | 3 |
| T4 · Productie-inrichting vastleggen | SPEC §8 | 4 |
| T5 · Back-up off-site + data-export | SPEC §8 | 2 |

**T1 · Fotodropbox.** Gezamenlijk raster van alle bijlagen zónder klus
(`Bijlage.in_dropbox`), uploaden vanaf de telefoon (meerdere tegelijk), en "koppel
alsnog aan een klus" — dat laatste houdt de dropbox bruikbaar in plaats van een
vergaarbak. Filter op maand en op wie het toevoegde.

**T2 · Fotoopslag productiewaardig.** Vervolg op 0c: opslagpad buiten de repo
(`MEDIA_ROOT` staat al in `.env.example`), `X-Accel-Redirect` in nginx, en meten wat een
maand foto's kost. SPEC §6 noemt object storage als patroon; voor zes medewerkers is een
map op de VPS plus de Storage Box uit T5 voorlopig genoeg — leg die keuze mét reden vast
in SPEC §6, zodat we 'm later bewust kunnen omzetten.

**T3 · Urenexport.** Gewerkte uren per medewerker per periode, voor de boekhouder.
**Geblokkeerd tot Maarten antwoordt** (§8); SPEC §7 zegt letterlijk dat punt 6 niet af te
bouwen is zonder dat antwoord. Bel hem in week 1. Fallback als het antwoord uitblijft:
CSV, kalendermaand, kolommen `medewerker, datum, klus, van, tot, uren, toelichting`, met
een totaalregel per medewerker. Gebruik het queryset uit F2.

**T4 · Productie-inrichting vastleggen.** Zie §4.4 — wat er op de VPS draait staat
nergens. Concreet: klusapp-requirements in de deploy-keten, `DJANGO_DEBUG=0` met een
echte `DJANGO_SECRET_KEY`, Postgres via `DATABASE_URL` (SQLite houdt zes gelijktijdige
schrijvers niet), `collectstatic` bij elke deploy (de manifest-storage in
`settings.py:STATIC_BACKEND` eist dat), HTTPS. Vastleggen in `README.md` en een
`docs/DEPLOY.md`. Los te beantwoorden, niet nu te bouwen: blijft dit op
develop.handigerai.nl of krijgt De Groene M bij oplevering een eigen omgeving? De
verwerkersovereenkomst noemt Hetzner Duitsland — controleer waar 178.105.192.98 staat.

**T5 · Back-up off-site + data-export.** SPEC §8: de verwerkersovereenkomst belooft
dagelijkse back-ups maar noemt de VPS zelf als opslagplek, en een kopie op de te
beschermen machine is geen back-up. Klusfoto's en klusdossiers bestaan nergens anders —
de boekhouder heeft alleen de uren. Hetzner Storage Box, dagelijkse dump van Postgres +
media, en de **restore één keer echt testen**; een ongeteste restore is geen back-up.
Plus de export bij beëindiging: uren als CSV, foto's als zip.

---

## 8. Openstaande vragen aan Maarten — Thijmen belt, week 1

1. **Hoe wil de boekhouder de uren aangeleverd krijgen?** Bestandsformaat, en per
   kalendermaand of per vier weken? Blokkeert T3.
2. **Moet uren schrijven offline werken?** Achter in een tuin is niet altijd bereik.
   Groot verschil in bouwtijd — bij "ja" is dit meerwerk, niet fase 1.
3. **Hoeveel foto's per maand** verwachten ze? Bepaalt T2 en T5.
4. **Worden materialen doorbelast**, of gaat het puur om uren?
5. **Moet de eigenaar zelf medewerkers kunnen toevoegen en uit dienst zetten?** Dat kan
   nu alleen via `/beheer/`, en dat is bewust niet voor de klant. Contractpunt 8 heet
   "inlogbeheer", dus dit valt waarschijnlijk binnen scope — ~2 uur.
6. **Mag een periode worden afgesloten**, zodat uren niet meer wijzigen nadat de
   boekhouder ze heeft verwerkt? Staat in geen enkele contractfase, maar volgt uit het
   schrappen van facturering (SPEC §8). Fase 1 of meerwerk?

## 9. Urenbudget — eerlijk gerekend

| | Uur |
|---|---|
| Al gedaan (skelet, model, login, weekkalender, loonstrook) | ~13 |
| Blok 0 — fundament | 7 |
| Spoor Floris | 14 |
| Spoor Thijmen | 15 |
| **Totaal** | **~49** |

Contract fase 1 is **45 uur**. Het gaat er dus ~4 uur overheen, en dat zit volledig in T4
en T5 — productie-inrichting en back-up. Verdedigbaar als hosting in plaats van bouw
(daar staat een maandbedrag tegenover), maar noem het richting Maarten vóórdat de
rekening gaat, niet erna. Landt vraag 5 of 6 uit §8 in fase 1, dan komt daar 2–4 uur bij
en is het meerwerk.

Volgorde die de meeste onzekerheid vroeg wegneemt:
**blok 0 → bellen met Maarten → F1 en T1 parallel → de rest.**

## 10. Verifiëren

Per taak, vóór mergen naar `main`:

```
.venv\Scripts\python manage.py test
```

De bestaande suite is de standaard: `uren/tests.py` dekt duur, constraints, rechten
("blok van ander niet te bewerken"), weektotalen en rasterplaatsing;
`medewerkers/tests.py` dekt de rolgebaseerde tegels en de loonstrookroutes. Elke nieuwe
view krijgt minimaal drie tests: inloggen vereist, medewerker ziet andermans data niet,
eigenaar wel.

Handmatig, per scherm:

```
.venv\Scripts\python manage.py runserver 8010
```

Inloggen als `maarten` (eigenaar) en `sam` (medewerker), beide `test1234`, aangemaakt met
`maak_testdata.py`. **Beide rollen langslopen** — de rolsplitsing is waar het misgaat.
Daarna op 375px breed narrow-testen: de eerste kolom van het planbord moet blijven staan
bij horizontaal scrollen, en invoervelden mogen niet inzoomen op iOS (daarom staat
`font-size:16px` in `app.css`).

Na merge naar `main` haalt de VPS binnen een minuut op: controleer
develop.handigerai.nl — dat is de enige omgeving die er is. Bewerk daar nooit bestanden;
elke deploy doet `git reset --hard`.
