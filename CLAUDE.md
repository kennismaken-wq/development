# Werkwijze in deze repo

## Wat hier staat

- **root** — de huisstijl-tool (Flask: `app.py`, `templates/`, prototype `glass.html`).
- **`klusapp/`** — losse Django-app (urenregistratie, hoveniersbedrijf De Groene M.)
  met eigen `CLAUDE.md` en spec in `klusapp/docs/SPEC.md`. Deelt niets met de tool
  hierboven; werk je daarin, lees dan díé CLAUDE.md.

## Deployen: push naar `main` = binnen een minuut live

`main` is de develop-omgeving: alles wat naar `main` gaat staat binnen een minuut op
**develop.handigerai.nl**. Er is geen aparte productie-omgeving achter deze repo.

Zo werkt het technisch: op de VPS draait een systemd-timer
(`develop-auto-deploy.timer`) die elke minuut `auto-deploy.sh` start. Dat script
vergelijkt `HEAD` met `origin/main` en doet bij verschil `git reset --hard
origin/main`, `pip install -r requirements.txt` en een herstart van
`develop-tool.service`. De VPS haalt dus zélf op; er wordt niets naar de server
gepusht.

**Belangrijk — niet "repareren":**
- Er is **bewust geen GitHub Actions-workflow**. Die is in september 2026 verwijderd
  omdat de SSH-deploy-key-constructie onherstelbaar stuk was (de private key bij de
  toegestane public key was kwijt). Voeg geen `.github/workflows/deploy.yml` terug toe.
- Er zijn **geen deploy keys of GitHub secrets** meer nodig. De repo is publiek, dus de
  `git fetch` op de server heeft geen authenticatie. Stel geen oplossing voor die een
  token of secret vereist.

Handmatig forceren of debuggen (als root op de VPS):

    systemctl start develop-auto-deploy.service
    journalctl -u develop-auto-deploy.service -n 50

## Eén branch

Er is alleen `main`. Thijmen en Floris pushen daar allebei rechtstreeks naartoe — er is
geen dev-branch, en maak er ook geen aan zonder dat expliciet te overleggen.

Dus: `git pull` vóór je begint. Wordt een push geweigerd met "fetch first", dan heeft de
ander gepusht: `git pull`, daarna opnieuw `git push`. Niet forceren met `--force`.

## UI bouwen: kopiëren, niet verzinnen

Lees `CONTEXT.md` vóórdat je iets aan de UI doet. De kern daarvan: neem CSS en structuur
**letterlijk** over uit `glass.html` (het goedgekeurde ontwerp-prototype in de root) in
plaats van zelf iets te bedenken of te "vereenvoudigen". Elke afwijking daarvan heeft in
het zusterproject tot zichtbare fouten geleid.

Kort samengevat: warme gradient-achtergrond met glazen kaarten erop, Inter voor body en
*italic* Fraunces voor koppen, pill-vormige knoppen, ruime spacing, nooit scherpe hoeken
of witte vlakken. De details staan in `CONTEXT.md`.

## Lokaal draaien

    python3 -m venv .venv
    ./.venv/bin/pip install -r requirements.txt
    ./.venv/bin/python app.py

Draait op `:5001`.

## VPS-feiten (voor als er iets stuk is)

- Pad: `/srv/handigerai/develop-tool`
- Linux-user: `develop` — de repo daar is van die user. Git-commando's op de server
  moeten dus als die user draaien (`sudo -u develop -H git -C /srv/handigerai/develop-tool ...`),
  anders klaagt git over "dubious ownership".
- Service: `develop-tool.service` · timer: `develop-auto-deploy.timer`
- nginx stuurt `develop.handigerai.nl` → `127.0.0.1:5001`
- De server-kloon wordt bij elke deploy hard gereset. Bewerk daar dus nooit bestanden
  direct — dat werk is bij de volgende deploy weg.

## Niet doen

- Geen secrets, sleutels of wachtwoorden in de repo of in commits.
- Niet direct op de VPS ontwikkelen (zie hierboven).
- De deploy niet omkatten naar GitHub Actions of een andere aanpak zonder overleg.
