# Spec — Klusapp De Groene M

Bron: dienstverleningsovereenkomst HandigerAI × De Groene M, versie 1.0,
september 2026. Artikel 2 van dat contract is de enige lijst die telt: bij
oplevering geeft functionaliteit die daar niet in staat geen grond voor bezwaar,
en omgekeerd is alles wat er wél in staat toegezegd.

## 1. Wat het bedrijf doet, en waarom dat het ontwerp bepaalt

De Groene M is een hoveniersbedrijf met ongeveer zes medewerkers. Uren worden nu
doorgegeven in een WhatsApp-groep. Die groep verdwijnt zodra deze app er is — er
is dan geen terugval meer.

Twee dingen bepalen bijna elke ontwerpkeuze:

**Aanleg versus onderhoud.** Een aanlegklus is één adres waar wekenlang aan
gewerkt wordt. Een onderhoudsklant is een terugkerende afspraak zonder einddatum,
en bij onderhoud doet één persoon zes tot acht adressen op een dag. Een invoer-
scherm dat prettig is voor het eerste is onbruikbaar voor het tweede.

**Invoer gebeurt op een telefoon**, aan het eind van de dag, in de bus. Niet
achter een bureau, niet met twee handen, niet met geduld.

## 2. Fase 1 — de basisapplicatie (verplicht, € 1.350, 45 uur)

1. **Urenregistratie** voor medewerkers, mobiel en desktop: klus kiezen, tijdblok,
   toelichting, foto's toevoegen.
2. **Klusdossier per klus**: foto's, tekeningen en documenten uploaden.
3. **Overzicht per medewerker** van gewerkte uren per week en per maand.
4. **Beheerdersoverzicht (admin)**: kalender per medewerker, wie op welke klus
   heeft gewerkt.
5. **Fotodropbox**: gezamenlijke map voor losse foto's die niet aan een klus hangen.
6. **Urenexport**: gewerkte uren per medewerker per periode, bedoeld voor de
   boekhouder.
7. **Aanwezigheidsregistratie**: admin houdt per dag bij wie aanwezig is
   (groen/rood).
8. **Inlogbeheer** met rolgebaseerde toegang: medewerker versus admin.
9. **Snelkoppeling naar het loonstrookportaal** (loondossier.nl), als link vanuit
   de app.

Rollen: de eigenaar ziet alles. Een medewerker ziet alleen zijn eigen uren, maar
wél het volledige klusdossier.

Oplevering: werkende webapplicatie, bruikbaar via de browser op desktop en mobiel.

## 3. Fase 2 — de uitbouw (optioneel, € 900, 30 uur)

Statistieken over uren, klussen en medewerkersinzet · legacy base met profielen en
archieffoto's van huidige en voormalige medewerkers · ideeënbus · chat of
notitiesectie per klus · uitgebreid klantbestand met contracttype en
factuurperiode voor vaste onderhoudsklanten.

## 4. Optionele uitbreidingen

**Social media module** (€ 300, 10 uur) — foto album met alle klusfoto's bij
elkaar, foto's automatisch gegroepeerd per week, voorzien van het bedrijfslogo en
klaargezet als download. Automatisch posten valt buiten scope.

**Native app** (€ 750, 25 uur, maandbedrag gaat van € 35 naar € 45) — de webapp
omgezet naar een downloadbare app voor App Store en Google Play, inclusief het
verificatietraject.

## 5. Ontwerpkeuzes die al vastliggen

Deze zijn beslecht tijdens de demofase. Niet opnieuw ter discussie stellen zonder
reden.

- **Planbord in plaats van kalender voor de admin.** Rijen zijn medewerkers,
  kolommen zijn dagen. Een gewone dagkalender wordt onleesbaar zodra zes mensen op
  één dag staan — blokken worden dan zo'n vijftien pixels breed.
- **Eerste kolom blijft staan bij horizontaal scrollen** op mobiel, anders weet je
  niet meer van wie je de getallen leest.
- **Blokken op mobiel tonen begintijd en duur**, niet de omschrijving: die breekt
  bij die breedte in losse lettergrepen. De kleur draagt de klusidentiteit.
- **View-first.** Klikken op een blok toont precies hetzelfde scherm als bewerken,
  maar niet bewerkbaar, met een bewerkknop. Geen tussenvenster.
- **Bijlagen hangen aan het uurblok**, niet alleen aan de klus, en hebben een eigen
  toelichting. "Toegevoegd door" en "wanneer" gaan automatisch.
- **Geen hinttekst** in formulieren en menu's. De klant vond het te druk.
- **Huisstijl** `#1d1d1b` en `#95bf1d`.
- **Bedragen als hele centen** opslaan, nooit als kommagetal.

## 6. Wat er nog niet ligt

De stack, de hosting-inrichting en de opzet van de fotoopslag. Hosting wordt een
VPS bij Hetzner (Duitsland, EU) — dat staat zo in de verwerkersovereenkomst en kan
niet zomaar ergens anders heen.

Foto's zijn het volumeprobleem: ruwe telefoonfoto's van een heel jaar lopen richting
tientallen gigabytes, verkleinde versies richting enkele. Uploaden, verkleinen,
in object storage zetten en alleen de sleutel in de database bewaren is het patroon.

## 7. Open vragen aan Maarten

Deze verschuiven de bouw echt, dus stel ze vóór of tijdens de bouw van fase 1:

- **Hoe wil de boekhouder de uren aangeleverd krijgen?** Welk bestandsformaat, en
  per welke periode werkt hij: kalendermaand of vier weken? Punt 6 van fase 1 is
  niet af te bouwen zonder dit antwoord.
- **Moet uren schrijven offline werken?** Achter in een tuin is er niet altijd
  bereik. Dit is een groot verschil in bouwtijd.
- **Hoeveel foto's per maand** verwachten ze te uploaden?
- **Worden materialen doorbelast**, of gaat het puur om uren?

## 8. Uit de contractreview, mee te nemen in de bouw

- **Back-ups moeten off-site.** De verwerkersovereenkomst belooft dagelijkse
  back-ups, maar noemt de VPS zelf als opslagplek. Een kopie op de te beschermen
  machine is geen back-up, en klusfoto's en klusdossiers bestaan nergens anders —
  de boekhouder heeft alleen de uren. Een Hetzner Storage Box kost een paar euro
  per maand.
- **Data-export bij beëindiging** inbouwen: uren als CSV, foto's als zip. Het
  gebruiksrecht vervalt bij opzegging, dus zonder export is de klant zijn
  klusdossiers kwijt.
- **Een periode kunnen afsluiten** zodat uren niet meer wijzigen nadat de
  boekhouder ze heeft verwerkt. Dit stond in geen van de contractfases maar volgt
  wel uit het schrappen van facturering. Bespreek of dit fase 1 of meerwerk is.
- Beveiliging zoals toegezegd: HTTPS overal, gehashte wachtwoorden, rolgebaseerde
  toegang, beheertoegang tot de server alleen voor HandigerAI.
