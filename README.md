# develop-tool

Deze repository bevat twee dingen:

- **`/`** — de huisstijl-tool zelf (Flask, `app.py`, `glass.html`). Zie hieronder.
- **`klusapp/`** — de urenregistratie-app voor hoveniersbedrijf De Groene M.
  Django-project, eigen README en spec in `klusapp/CLAUDE.md` en
  `klusapp/docs/SPEC.md`. Draait los van de tool hierboven en deelt er
  niets mee.

## Klusapp draaien

```
cd klusapp
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python manage.py migrate
.venv\Scripts\python maak_testdata.py     # testgebruikers en drie klussen
.venv\Scripts\python manage.py runserver 8010
```

Inloggen met `maarten` / `test1234` (eigenaar) of `sam` / `test1234`
(medewerker). Tests: `.venv\Scripts\python manage.py test`.

## De huisstijl-tool

Floris's new HandigerAI tool. Isolated dev environment, deploys independently
from the Outreach dashboard — see `CONTEXT.md` for the required "glassy"
lay-out before building any UI.

## Live

`http://develop.handigerai.nl` (HTTPS pending DNS — see below).

## Deploy

Push naar `main` → binnen een minuut live op develop.handigerai.nl. De VPS
haalt zelf elke minuut de nieuwste commits op. Er is géén GitHub
Actions-workflow meer, en geen deploy key of secret nodig: de repo is publiek,
dus de `git fetch` heeft geen authenticatie nodig.

Op de server draait een systemd-timer (`develop-auto-deploy.timer`) die elke
minuut `auto-deploy.sh` start. Dat script vergelijkt `HEAD` met `origin/main`
en doet alleen iets als er verschil is: `git reset --hard origin/main`,
`pip install -r requirements.txt`, en een herstart van `develop-tool.service`.

Handmatig deployen of het logboek bekijken (als root op de VPS):

    systemctl start develop-auto-deploy.service
    journalctl -u develop-auto-deploy.service -n 50

## Samenwerken

Er is bewust één branch: `main`. Thijmen en Floris pushen daar allebei
rechtstreeks naartoe, en `main` ís de develop-omgeving — er zit geen
aparte productie-omgeving achter deze repo.

## Local dev

```
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python app.py
```
Runs on `:5001`.

## VPS layout

- Path: `/srv/handigerai/develop-tool`
- Linux user: `develop`
- systemd service: `develop-tool.service`
- deploy-timer: `develop-auto-deploy.timer` → `auto-deploy.sh` (draait elke minuut)
- nginx: proxies `develop.handigerai.nl` → `127.0.0.1:5001`
