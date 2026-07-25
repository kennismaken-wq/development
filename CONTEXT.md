# Lay-out — "glassy" design system

**Voor:** Floris, bij het bouwen van deze nieuwe tool.
**Doel van dit document:** dat deze tool er van dag één uit ziet als een
onderdeel van dezelfde familie als `tools.handigerai.nl` (Outreach/Automatische
Mailer), zodat we 'm later zonder herontwerp kunnen integreren.

## De regel: letterlijk overnemen, niet "verbeteren"

Dit is de belangrijkste les uit het herontwerp van de Outreach-dashboard
(zie `INTEGRATIE-CONTEXT.md` in die repo als je 'm ooit onder ogen krijgt):
**neem CSS/structuur letterlijk over uit het goedgekeurde ontwerp, verzin
niks nieuws.** Elke keer dat daar iets werd "vereenvoudigd" of "netter"
gemaakt dan het origineel, leidde dat tot een zichtbare fout (vergeten
CSS-blokken, verkeerd uitgelijnde knoppen, kapotte iconen). Dezelfde regel
geldt hier: als je twijfelt over hoe iets eruit moet zien, kopieer de
CSS-klasse letterlijk uit `glass.html` (bijgevoegd in deze repo, root) in
plaats van er zelf iets op te verzinnen.

`glass.html` is het canonieke ontwerp-prototype — een losse HTML-file die je
gewoon in een browser kan openen. Bekijk 'm ernaast terwijl je bouwt.

## De basis-look in het kort

- **Achtergrond**: een vaste, warme gradient (donkerblauw → koraal), niet wit.
  Alle content staat in "glazen" kaarten erbovenop.
- **Glas-effect** (klasse `.glass`, gebruik deze op elke kaart/paneel):
  ```css
  .glass {
    background: rgba(255,255,255,0.10);
    backdrop-filter: blur(28px) saturate(150%);
    -webkit-backdrop-filter: blur(28px) saturate(150%);
    border: 1px solid rgba(255,255,255,0.20);
    box-shadow: 0 24px 70px rgba(0,0,0,0.30), inset 0 1px 0 rgba(255,255,255,0.15);
  }
  ```
- **Achtergrond-gradient** (op `<body>`):
  ```css
  background:
    radial-gradient(ellipse 60% 50% at 15% 10%, rgba(91,143,168,0.55), transparent 60%),
    radial-gradient(ellipse 55% 55% at 90% 95%, rgba(224,123,95,0.5), transparent 60%),
    linear-gradient(150deg, #1E3540 0%, #3B6376 30%, #6E8798 52%, #A5806A 76%, #C98B5E 100%);
  background-attachment: fixed;
  color: #FFFFFF;
  ```

## Fonts

Beide via Google Fonts, altijd samen laden:
```html
<link href="https://fonts.googleapis.com/css2?family=Fraunces:ital,wght@0,600;0,700;1,600;1,700&family=Inter:wght@400;500;600&display=swap" rel="stylesheet">
```
- **Inter** — alle gewone tekst, labels, knoppen, inputs.
- **Fraunces** (serif, *italic*, weight 600) — alleen voor koppen/titels/
  begroetingen (`h1`, kaart-titels, merknaam). Dit contrast (sans-serif body
  + italic-serif koppen) is de meest herkenbare stijl-vingerafdruk van de
  merk-familie — nooit Fraunces gebruiken voor body-tekst of andersom.

## Kleuren

```css
--accent: #5B8FA8;   /* koelblauw — primaire accentkleur, "aan"-status, links */
--warm:   #E07B5F;   /* koraal/oranje — secundair accent, waarschuwingen */
--ink:    #1A1A18;   /* bijna-zwart — tekst OP witte/lichte vlakken (bv. knoppen) */
```
Verder bijna alles wit met transparantie: tekst `rgba(255,255,255,0.55)` tot
`0.85)` afhankelijk van hiërarchie (hoe belangrijker, hoe ondoorzichtiger).
Statuskleuren: succes/groen `#7FE0A0` / `rgba(63,163,94,...)`, fout/koraal
`rgba(224,123,95,...)`, neutraal `rgba(255,255,255,0.12)`.

## Vormtaal

- **Border-radius schaal**: grote kaarten/modals 20–32px, kleinere widgets
  16–20px, chips/badges/knoppen altijd `999px` (volledig rond/pill-vorm).
  Nooit scherpe hoeken (`0px`/`4px`) gebruiken — voelt meteen "niet-glassy".
- **Knoppen**:
  - Primair: `.btn-white` — witte pil, donkere tekst (`--ink`), zachte shadow,
    hover = lichte lift (`translateY(-1px)`).
  - Secundair: `.btn-ghost` — transparant glas-effect, witte tekst, dunne
    rand.
- **Inputs**: `.glass-input` — zelfde transparante-glas-basis, `border-radius: 13px`.
- **Spacing**: ruim, lucht tussen elementen (`1–2.5rem` tussen secties,
  `.9–1.7rem` padding in kaarten). Niet compact/dicht-op-elkaar maken.

## Wat NIET te doen

- Geen wit/licht achtergrond ergens introduceren — alles leeft op de
  gradient, via glazen kaarten erbovenop.
- Geen ander font-paar erbij (geen system-font-fallback zonder Fraunces
  voor koppen).
- Geen sterke, verzadigde vlakke kleuren — alles is transparant/gedempt
  over de gradient heen.
- Geen scherpe hoeken.

## Bron van waarheid

Twijfel je over een specifiek onderdeel (tabel, modal, toggle, chip,
lege-staat) dat hier niet expliciet staat? `glass.html` in de root van deze
repo heeft voorbeelden van vrijwel alles: login-scherm, sidebar, dashboard-
widgets, stats, tabellen, modals, toggles, doc-kaarten, lege staten. Kopieer
de relevante `<style>`-regels en HTML-structuur letterlijk over — pas alleen
de data/tekst aan naar wat jouw tool nodig heeft.

Zodra jouw tool klaar is voor integratie in `tools.handigerai.nl`, is dit
de reden dat we het dan kunnen inpluggen als nieuwe sidebar-icoon +
tab zonder de rest van de site opnieuw te hoeven stylen.
