# Vragen aan Maarten — bellen in week 1

Vragen die de bouw van fase 1 echt verschuiven. Ze komen uit SPEC §7, uit de
contractreview (SPEC §8) en uit het gespreksverslag. Thijmen belt.

**Nog openstaand (24-09-2026):** 2, 3, 4, 6, 7, 8, 9 en 10. En: Maarten zou zijn eigen
lijst met negen onderdelen opsturen ("die 12 kantjes") — die is nooit binnengekomen.
Vraag die er nog een keer bij; we bouwen nu op het verslag alleen.

Bij elke vraag staat wat we bouwen als het antwoord uitblijft, zodat het gesprek geen
blokkade wordt. Vul het antwoord hier in, met de datum — dan weet de ander waar hij aan
toe is zonder na te hoeven vragen.

---

## 1. Hoe wil de boekhouder de uren aangeleverd krijgen?

**Vraag:** In welk bestandsformaat wil hij ze, en per welke periode werkt hij —
kalendermaand of vier weken?

**Waarom het uitmaakt:** SPEC §7 zegt letterlijk dat contractpunt 6 niet af te bouwen is
zonder dit antwoord. Vier weken versus kalendermaand is niet cosmetisch: bij vier weken
lopen perioden dwars door maanden heen en moet het overzicht anders gerekend worden.

**Als er geen antwoord komt:** CSV, kalendermaand, kolommen `medewerker, datum, klus,
van, tot, uren, toelichting`, met een totaalregel per medewerker.

**Antwoord (15-09-2026):** Excel, geen CSV — moet na het downloaden gewoon verder te
bewerken zijn, de administratie van De Groene M draait nu op Excel. Periode niet expliciet
afgewezen: we bouwen de kalendermaand-fallback. Facturen gaan via Exact Online, niet via
deze app (staat al vast, SPEC: "de app maakt geen facturen"); Maarten wil op termijn wel
een koppeling van "uren verzameld" naar "factuur in Exact Online" — dat is een apart,
nog niet uitgewerkt vervolgtraject (fase 2 of meerwerk, niet fase 1). Niet ongevraagd
beginnen, wel meenemen als Maarten er zelf over begint.

---

## 2. Moet uren schrijven offline werken?

**Vraag:** Hebben de mannen achter in een tuin wel eens geen bereik als ze hun uren
invullen? En vullen ze ze daar in, of pas in de bus of thuis?

**Waarom het uitmaakt:** Dit is het grootste verschil in bouwtijd van de hele lijst.
Offline werkend krijgen betekent het invoerscherm client-side maken, met opslag op het
toestel en synchronisatie achteraf. Dat is geen detail maar een ander scherm.

**Als er geen antwoord komt:** we bouwen het niet. Het staat niet in artikel 2 van het
contract, dus het is meerwerk — maar vraag het liever nu dan na oplevering.

**Antwoord:**

---

## 3. Hoeveel foto's per maand verwachten jullie?

**Vraag:** Ruwe schatting: maken de mannen van elke klus een paar foto's, of gaat het om
tientallen per dag?

**Waarom het uitmaakt:** bepaalt of een map op de VPS volstaat of dat er object storage
bij moet, en hoe groot de off-site back-up wordt. We bewaren alleen verkleinde versies
(~200-400 KB per foto in plaats van 3-8 MB), dus het valt waarschijnlijk mee — maar
gokken op een factor tien is geen plan.

**Als er geen antwoord komt:** rekenen met 500 foto's per maand. Dat is ruim voor zes
man en past makkelijk op de VPS plus een Storage Box.

**Antwoord:**

---

## 4. Worden materialen doorbelast, of gaat het puur om uren?

**Waarom het uitmaakt:** als er materiaalregels bij een klus moeten kunnen, raakt dat het
datamodel én de export naar de boekhouder. Staat niet in artikel 2, dus het zou meerwerk
zijn — maar als het antwoord "ja" is, willen we dat weten vóórdat de export af is en niet
erna.

**Als er geen antwoord komt:** puur uren. De app maakt sowieso geen facturen.

**Antwoord:**

---

## 5. Moet jij zelf medewerkers kunnen toevoegen en uit dienst zetten?

**Vraag:** Als er iemand in of uit dienst gaat, wil je dat zelf kunnen regelen, of bel je
ons daarvoor?

**Waarom het uitmaakt:** nu kan dat alleen via `/beheer/`, en dat scherm is bewust niet
voor de klant — het toont alle velden en verwijdert zonder vangnet. Contractpunt 8 heet
"inlogbeheer met rolgebaseerde toegang", dus een eigen beheerscherm valt er
waarschijnlijk binnen. Kost ongeveer 2 uur.

**Als er geen antwoord komt:** we bouwen het, maar pas nadat de negen contractpunten
staan.

**Antwoord:** — (nog geen antwoord, maar inmiddels ingehaald door de bouw: `/medewerkers/`
bestaat sinds september 2026 en kan toevoegen, bewerken, wachtwoord zetten en uit dienst
zetten. De vraag blijft staan als bevestiging, niet meer als beslissing.)

---

## 6. Mag een periode worden afgesloten?

**Vraag:** Als de boekhouder de uren van een maand heeft verwerkt — mogen die uren daarna
nog gewijzigd worden, of moeten ze op slot?

**Waarom het uitmaakt:** zonder slot kan iemand een uurblok aanpassen dat al verwerkt en
uitbetaald is, en dan loopt de administratie stil uit elkaar. Dit staat in geen enkele
contractfase, maar volgt wel uit het schrappen van facturering (SPEC §8).

**Als er geen antwoord komt:** niet bouwen, maar wél expliciet benoemen bij oplevering,
zodat het later geen verwijt wordt.

**Antwoord:**

---

## 7. Wie mag er op een klus uren schrijven?

**Vraag:** Wil je zelf bepalen wie er op een klus mag werken, of mag iedereen op elke
klus uren schrijven?

**Waarom het uitmaakt:** nu ziet elke medewerker bij het uren schrijven **alle** actieve
klussen in de keuzelijst. Met een handvol klussen gaat dat prima. Maar bij onderhoud doet
één persoon zes tot acht adressen op een dag (SPEC §1), en dan scrol je 's avonds in de
bus door tientallen klussen om de goede te vinden — precies het scherm dat volgens de
spec pijnloos moet zijn.

Wie er op een klus heeft gewerkt leiden we nu af uit de geschreven uren, dus in het
klusdossier klopt het beeld hoe dan ook. De vraag gaat alleen over de invoerkant.

Dit staat **niet in artikel 2**, dus vooraf toewijzen is meerwerk (~5 uur).

**Als er geen antwoord komt:** niet bouwen. Wachten tot de lijst in de praktijk te lang
wordt; dan weten we ook meteen hoe lang "te lang" is.

**Antwoord:**

---

## 8. Mag "Aanleg" voortaan "Eenmalig" heten?

**Vraag:** In de app staat bij elke klus of het aanleg of onderhoud is. Klopt het woord
"aanleg" voor álles wat eenmalig is — ook een snoeibeurt, of stormschade opruimen?

**Waarom het uitmaakt:** het veld beschrijft eigenlijk het *ritme* (eenmalig of
doorlopend), niet het soort werk. Een snoeiklus is eenmalig maar geen aanleg, en met het
woord "aanleg" is niet duidelijk waar die dan thuishoort. Sinds 23-09-2026 staat het
label op **Eenmalig**; de databasewaarde is ongewijzigd `aanleg`, dus terugdraaien is
één regel.

**Als er geen antwoord komt:** het blijft "Eenmalig". Maar "aanleg versus onderhoud" is
Maartens eigen taal (zo staat het ook in SPEC §1), dus het is het vragen waard of het
woord uit het scherm halen niet verwarrender is dan het probleem dat het oplost.

**Antwoord:**

---

## 9. Hoe fijn moet een onderhoudsklus worden opgeknipt?

**Vraag:** Als je bij dezelfde klant op hetzelfde adres twee losse afspraken hebt — zeg
het groenonderhoud en apart de bestrating — wil je die dan als twee klussen zien, of als
één met verschillende werkzaamheden erin?

**Waarom het uitmaakt:** de app splitst op "wat wil je apart optellen". Twee klussen
betekent twee dossiers, twee totalen, en twee regels in de keuzelijst waar de medewerker
'''s avonds uit kiest. Eén klus betekent één totaal, met het verschil in de toelichting op
het uurblok. Het formulier waarschuwt sinds 23-09-2026 wel als er op een adres al een
klus staat, maar laat je bewust doorgaan — de keuze is aan Maarten, niet aan ons.

**Als er geen antwoord komt:** zo laten. De waarschuwing vangt het geval waar het
misgaat (per ongeluk een tweede dossier), en de rest blijft zijn beslissing.

**Antwoord:**

---

## 10. Wie mag de offerte met prijzen zien?

**Vraag:** Je uploadt je offerte als PDF bij een klus. Mogen de mannen die openen zoals
hij is, of moeten de prijzen eruit — of hoort zo'n document alleen bij jou?

**Waarom het uitmaakt:** je zei het zelf in het gesprek ("dan wil ik even over nadenken
van hey, wie mag wat zien... of kan ik een PDF erin gooien en dat die automatisch alle
prijzen eruit filtert"). Vandaag ziet iedereen alles: artikel 2 zegt dat een medewerker
het *volledige* klusdossier mag inzien, dus dat is zoals het hoort — maar in die offerte
staat wat jij aan de klant rekent, en dat is iets anders dan een tekening.

Prijzen automatisch wegfilteren uit een PDF is geen kleine ingreep en geen zekerheid;
een document als "alleen voor de eigenaar" markeren is dat wel (~2 uur).

**Als er geen antwoord komt:** het blijft zoals het is. Maar dan wél benoemen bij
oplevering, zodat het geen verrassing is de eerste keer dat iemand een offerte opent.

---

## Niet vragen, wel vertellen

- **Back-ups gaan off-site.** De verwerkersovereenkomst belooft dagelijkse back-ups maar
  noemt de VPS zelf als opslagplek. Een kopie op de machine die je wilt beschermen is
  geen back-up, en de klusfoto's bestaan nergens anders — de boekhouder heeft alleen de
  uren. Kost een paar euro per maand extra. Dit is een mededeling, geen keuze.
- **Het urenbudget.** Fase 1 staat op 45 uur; met de productie-inrichting en de back-up
  erbij komt het rond de 49 uit. Zeg dat vóór de rekening, niet erna.
