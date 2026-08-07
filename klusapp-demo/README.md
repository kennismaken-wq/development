# Klusapp — klikbare demo

Demo voor de klant, om een idee te geven van de app vóórdat er scope-vragen
worden gesteld. **Eén bestand, geen backend, geen installatie** — open
`index.html` in een browser, of zet 'm op `develop.handigerai.nl`.

Alle gegevens zijn verzonnen (fictief "Van Dijk Bouw"). Er wordt niets
opgeslagen: bij verversen staat alles weer op de begintoestand.

## Wat werkt er echt

- **Timer** start/stopt en telt live door; bij stoppen wordt afgerond op een
  half uur en komen de uren op de juiste klus te staan
- **Uren schrijven** via de snelkeuze-pillen (2/4/6/8/9 uur) of handmatig
- **Klus aanmaken** — verschijnt direct in de lijst
- **Conceptfactuur** wordt écht berekend uit de geschreven uren: één regel per
  medewerker, tarief × uren, 21% BTW. De gebruikte uren worden gemarkeerd als
  gefactureerd, zodat ze niet dubbel op een factuur kunnen komen
- **Definitief maken** zet de factuur in het documentendossier van de klus
- **Fotomodule** — sjabloon kiezen, foto's selecteren, live voorbeeld van de post

## Wat nog nep is

- Inloggen doet niets (elke druk op de knop werkt)
- Foto's zijn gegenereerde kleurvlakken, geen echte beelden
- Uploaden, PDF en delen tonen alleen een melding
- Alleen Jeroen (eigenaar) is ingelogd; rollen/rechten zitten er nog niet in

## Bewuste keuzes die in de echte app blijven

- **Bedragen in centen** (integer), nooit floats — anders scheelt een factuur
  een cent door afronding
- **Factuurregels leggen het tarief als getal vast**, niet als verwijzing naar
  de medewerker. Verhoogt de eigenaar later een uurtarief, dan verandert een
  oude factuur niet mee
- **Tarief-hiërarchie**: het tarief van de klus wint van het standaardtarief
  van de medewerker
- **Facturen gaan nooit automatisch de deur uit** — altijd concept → eigenaar
  controleert → definitief

## Huisstijl

CSS letterlijk overgenomen uit `glass.html` in de `development`-repo, volgens
de regel in `CONTEXT.md`: kopiëren, niet "verbeteren".
