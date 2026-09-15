# Productie-inrichting — klusapp

Wat er op de VPS draait en hoe je het terugbouwt. Tot september 2026 stond dit
nergens: de server was met de hand ingericht en bij een schijfstoring was er geen
recept om het mee te herstellen. Dit document is dat recept.

**Bijgewerkt:** 16 september 2026, afgeleid van de draaiende server.

## Waar het staat

| | |
|---|---|
| Host | `178.105.192.98` (Hetzner, Duitsland — staat zo in de verwerkersovereenkomst) |
| SSH | `ssh handigerai-email-automator` (root), zie `~/.ssh/config` |
| Pad | `/srv/handigerai/develop-tool` — de repo; de app zelf in `klusapp/` |
| Linux-user | `develop` (eigenaar van de repo; git-commando's als root geven "dubious ownership") |
| Service | `develop-tool.service` — gunicorn op `127.0.0.1:5001` |
| Deploy | `develop-auto-deploy.timer` → `auto-deploy.sh`, elke minuut |
| Webserver | nginx, `develop.handigerai.nl` → `127.0.0.1:5001`, HTTPS via certbot |
| Database | **SQLite** (`klusapp/db.sqlite3`) |
| Media | `klusapp/media/` |

De naam `develop-tool` is historisch: die service draaide eerst de Flask-huisstijl-
tool. Hij draait nu de klusapp.

## Deploy: push naar `main` = binnen een minuut live

`auto-deploy.sh` op de server vergelijkt `HEAD` met `origin/main` en doet bij
verschil:

```bash
git reset --hard origin/main
.venv/bin/pip install -q -r klusapp/requirements.txt
.venv/bin/python klusapp/manage.py migrate --noinput
.venv/bin/python klusapp/manage.py collectstatic --noinput
systemctl restart develop-tool.service
```

`collectstatic` is niet optioneel: `settings.py` gebruikt bij `DEBUG=0` de
manifest-storage van WhiteNoise, en die gooit een fout op elke `{% static %}`
die niet in `staticfiles.json` staat. Zonder collectstatic geeft élke pagina een
500.

Handmatig forceren of het logboek bekijken (als root):

```bash
systemctl start develop-auto-deploy.service
journalctl -u develop-auto-deploy.service -n 50
tail -50 /srv/handigerai/develop-tool/develop-tool.log
```

De serverkloon wordt bij elke deploy hard gereset. Bewerk daar dus nooit
bestanden — dat werk is bij de volgende deploy weg. `media/` en `db.sqlite3`
staan in `.gitignore` en overleven de reset.

## Omgevingsvariabelen

Staan in `/srv/handigerai/develop-tool/klusapp/.env`, gelezen door python-dotenv
in `settings.py`. Niet in de systemd-unit, en niet in de repo.

```
DJANGO_DEBUG=0
DJANGO_SECRET_KEY=<geheim>
DJANGO_ALLOWED_HOSTS=develop.handigerai.nl,127.0.0.1,localhost
DJANGO_CSRF_TRUSTED_ORIGINS=https://develop.handigerai.nl
```

`DJANGO_DEBUG=0` staat er expliciet in. Laat dat zo: met `DEBUG=1` toont een
foutpagina de secret key en de omgeving aan wie de fout veroorzaakt.

## Terugbouwen op een lege server

1. Pakketten: `python3`, `python3-venv`, `nginx`, `certbot`, `git`.
2. User `develop` aanmaken, `/srv/handigerai/develop-tool` klonen als die user.
3. `python3 -m venv .venv` in de repo-root (dus náást `klusapp/`, niet erin) en
   `pip install -r klusapp/requirements.txt`.
4. `.env` aanmaken zoals hierboven, met een **nieuwe** secret key.
5. `manage.py migrate`, `manage.py collectstatic`, en een eigenaar aanmaken met
   `manage.py createsuperuser` (daarna in `/beheer/` de rol op "eigenaar" zetten).
6. `develop-tool.service`, `develop-auto-deploy.service` en
   `develop-auto-deploy.timer` plaatsen in `/etc/systemd/system/` (zie hieronder),
   `systemctl enable --now` beide.
7. nginx-site aanmaken (zie hieronder), daarna `certbot --nginx -d develop.handigerai.nl`.
8. Back-up terugzetten: `db.sqlite3` en `media/` (zie "Back-ups").

### develop-tool.service

```ini
[Unit]
Description=HandigerAI develop-tool - klusapp (Django/gunicorn)
After=network.target

[Service]
LimitNOFILE=4096
Type=simple
User=develop
Group=develop
WorkingDirectory=/srv/handigerai/develop-tool/klusapp
ExecStart=/srv/handigerai/develop-tool/.venv/bin/gunicorn config.wsgi:application \
    --chdir /srv/handigerai/develop-tool/klusapp \
    --bind 127.0.0.1:5001 --workers 3 --timeout 60
Restart=always
RestartSec=3
StandardOutput=append:/srv/handigerai/develop-tool/develop-tool.log
StandardError=append:/srv/handigerai/develop-tool/develop-tool.log
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/srv/handigerai/develop-tool

[Install]
WantedBy=multi-user.target
```

### develop-auto-deploy.timer / .service

```ini
# .timer
[Timer]
OnBootSec=1min
OnUnitActiveSec=1min
AccuracySec=10s
[Install]
WantedBy=timers.target

# .service
[Service]
Type=oneshot
ExecStart=/srv/handigerai/develop-tool/auto-deploy.sh
```

### nginx

```nginx
server {
    server_name develop.handigerai.nl;
    location / {
        proxy_pass http://127.0.0.1:5001;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
    listen 443 ssl;   # certbot vult de certificaatregels aan
}
```

## Wat er nog niet staat

Drie dingen die vóór echte oplevering aan De Groene M geregeld moeten zijn:

1. **Back-ups. Er zijn er geen.** Geen cron, geen off-site kopie. `db.sqlite3` en
   `media/` bestaan op precies één schijf, en de klusfoto's en klusdossiers staan
   nergens anders — de boekhouder heeft alleen de uren. De verwerkersovereenkomst
   belooft dagelijkse back-ups. Nodig: dagelijkse dump naar een Hetzner Storage
   Box (een paar euro per maand), plus **één keer een restore echt uitvoeren** —
   een ongeteste restore is geen back-up.
2. **SQLite in plaats van Postgres.** SQLite vergrendelt bij schrijven; zes man
   die 's avonds tegelijk hun uren invullen kunnen "database is locked" krijgen.
   `settings.py` schakelt al om zodra `DATABASE_URL` gezet is, en `psycopg` staat
   in `requirements.txt` — het is dus vooral een migratie van de bestaande data.
3. **X-Accel-Redirect staat klaar maar is niet aangesloten.** `GEBRUIK_X_ACCEL`
   in `settings.py` en de view `klussen.views.media_bestand` zijn er al; de
   `internal`-locatie in nginx ontbreekt. Nu gaat elke foto door gunicorn heen.
   Bij 80 KB media niet urgent, bij een jaar klusfoto's wel.
