# Een web-app laten voelen als een echte app (PWA)

Recept voor elke app van HandigerAI, Django of Flask. Als voorbeeld dient de
klusapp: `klusapp/config/pwa.py`, `klusapp/templates/sw.js` en
`klusapp/static/js/app-installeren.js`. Opgesteld in oktober 2026, op basis van wat
ontwikkelaars er op GitHub, op fora en in WebKit-bugs over schrijven.

## Wat het wel en niet doet

- **In de browser blijft de adresbalk altijd staan.** Geen enkele site kan die
  weghalen.
- Het app-gevoel komt pas nadat de gebruiker de app installeert: "Zet op beginscherm"
  op de iPhone, "App installeren" op Android. Daarna opent hij vanaf een eigen icoon,
  schermvullend en zonder adresbalk, met een eigen opstartscherm, en staat hij als
  losse app in de app-wisselaar.
- Sinds iOS 26 opent elke site die je op het beginscherm zet standaard als web-app.
- In de EU werkt het gewoon. Apple wilde het hier in 2024 uitzetten, maar heeft dat
  teruggedraaid.

## De checklist

### 1. Manifest op `/manifest.webmanifest`

Velden:
- `id: "/"`, `name`, `short_name` (staat onder het icoon; houd hem kort),
  `start_url: "/"`, `scope: "/"`, `display: "standalone"`, `lang: "nl"`
- `theme_color` en `background_color`: de donkerste kleur uit [DESIGN.md](DESIGN.md).
  Het accent is te licht voor een statusbalk.
- Iconen van 192 en 512 px, plus een 512-variant met `"purpose": "maskable"`.
  - Op die maskable-variant valt het logo binnen de middelste 80%; Android snijdt er
    een cirkel of druppel uit.
  - Gebruik een vlakke tegel in de achtergrondkleur, geen transparant logo.

Content-type `application/manifest+json`. Gebruik gehashte static-URL's voor de
iconen.

### 2. Service worker op `/sw.js`

**In de root, niet onder `/static/`.** Een worker stuurt alleen paden onder zijn
eigen map aan. Zet hem dus via een eigen route neer, met deze headers:
- `Service-Worker-Allowed: /`
- `Cache-Control: no-cache` (Django: `@never_cache`)

De regels. Hier gaan de meeste projecten de mist in:
- **Schermen (navigaties) altijd van het netwerk.** Alleen als er geen netwerk is,
  toont hij de offline-pagina. Een gecachte pagina met een formulier geeft dagen
  later een CSRF-fout, en een gecachte ingelogde pagina laat andermans gegevens zien.
- **Alleen `/static/` in de cache.**
  - Bestanden met een hash in de naam (WhiteNoise in productie) komen direct uit de
    cache.
  - Bestanden zonder hash (lokaal, DEBUG) eerst van het netwerk, zodat CSS-wijzigingen
    meteen zichtbaar zijn.
- **Nooit** `/media/` of andere afgeschermde bestanden, POST-verzoeken, `/beheer/` of
  verzoeken naar een ander domein.
- **Versie in de cachenaam**, afgeleid van de gehashte bestandsnamen. Verandert er
  iets, dan verandert `sw.js`; de telefoon haalt hem zelf op en `activate` ruimt de
  oude cache op.
- Omdat er geen privégegevens in de cache staan, hoeft er bij uitloggen niets gewist
  te worden. `Clear-Site-Data` is dan niet nodig.

### 3. Offline-pagina

Een kale pagina: "Geen verbinding", met een knop "Opnieuw proberen"
(`location.reload()`).
- **Niet op de basistemplate bouwen.** Die neemt de navigatie en de naam mee van wie
  er ingelogd was, en de pagina staat in de cache van de telefoon.
- Geen login vereist.

### 4. Head-tags in de basistemplate

```html
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<meta name="theme-color" content="#…">
<link rel="manifest" href="/manifest.webmanifest">
<link rel="apple-touch-icon" href="…/icoon-180.png">
<meta name="apple-mobile-web-app-title" content="Korte naam">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
```

Met `black-translucent` loopt de pagina onder de statusbalk door. De body moet dan
ruimte houden met `padding-top: env(safe-area-inset-top)`.

### 5. Installeren aanbieden

Mensen vinden de installatie-optie niet vanzelf. Dat is de grootste klacht op elk
forum.
- **Android/Chrome:** vang `beforeinstallprompt` af en toon een eigen knop
  "Installeren".
- **iPhone/iPad:** Safari heeft geen installatieknop en ook geen event. Toon een korte
  uitleg: "Tik op Deel (het vierkantje met de pijl) en kies 'Zet op beginscherm'."
  iPadOS doet zich voor als Mac; herken hem aan `navigator.maxTouchPoints > 1`.
- Toon het **alleen op het startscherm**, en niet als de app al standalone draait
  (`matchMedia("(display-mode: standalone)")` of `navigator.standalone`).
- Na wegtikken komt hij niet meer terug: onthoud dat in `localStorage`, binnen een
  try/catch.

### 6. CSS voor het app-gevoel

- Elke vaste balk onderin: `bottom: calc(… + env(safe-area-inset-bottom))`.
- **Invoervelden minimaal 16px.** Bij kleinere tekst zoomt iOS in zodra je erop tikt.
  Let op zoekvelden die in een eigen pil staan.
- `:hover` alleen binnen `@media (hover:hover)`, anders blijven knoppen na een tik
  "hangen".
- Zet `-webkit-tap-highlight-color: transparent` en `touch-action: manipulation` op
  klikbare elementen.
- In standalone is er op de iPhone geen terugknop. Elk scherm heeft dus zijn eigen weg
  terug.

### 7. Inloggen

- **Op iOS heeft de geïnstalleerde app eigen cookies, los van Safari.** Na het
  installeren log je dus één keer opnieuw in. Een lange, meeschuivende sessie voorkomt
  dat dat daarna steeds terugkomt (klusapp: `SESSION_COOKIE_AGE` = 14 dagen +
  `SESSION_SAVE_EVERY_REQUEST`).
- Links met `target=_blank` naar eigen, afgeschermde bestanden kunnen in Safari
  openen, en daar ben je niet ingelogd. Test dat op een echte iPhone.

### 8. Per framework

- **Django:** de drie views in `config/urls.py`, iconen in `static/img/`, en
  `collectstatic` bij de deploy. Bij `DEBUG=0` geeft een bestand dat niet in het
  WhiteNoise-manifest staat een 500.
- **Flask:** `@app.route("/sw.js")`, `"/manifest.webmanifest"` en `"/offline"`. Bij
  een login-check in `before_request` moeten die drie open blijven (Outreach:
  `open_routes` in `dashboard.py`). Outreach heeft daarnaast nog geen viewport-tag en
  geen gedeelde basistemplate; die komen eerst.

## Bewust niet (zonder overleg)

- **Offline gegevens invullen.** Dat vraagt client-side opslag en synchroniseren;
  dat is een project op zich.
- **Pushmeldingen.** Op iOS alleen als de app geïnstalleerd is, en alleen na
  toestemming.
- **Een pakket als `django-pwa`.** Het wordt nauwelijks onderhouden (laatste release
  september 2024), en het zijn ±30 regels die we zelf schrijven.

## Testen

- **Lokaal:** `localhost` mag een service worker draaien zonder HTTPS. In de console
  van de browser: `navigator.serviceWorker.getRegistration()`, `caches.keys()`. Stop
  de server en open een scherm: dan moet de offline-pagina verschijnen.
- **Echt:** na de deploy (HTTPS) op een iPhone en een Android-toestel installeren,
  vanaf het icoon openen, één keer inloggen, en de "Openen"-links naar bestanden
  proberen.
