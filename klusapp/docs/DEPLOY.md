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
| Database | **PostgreSQL 18**, database en user `klusapp`, via `DATABASE_URL` |
| Media | `klusapp/media/` |
| Back-up | `klusapp-backup.timer` → `/usr/local/bin/klusapp-backup.sh`, elke nacht 03:20 naar `/srv/backups/klusapp` |
| Uren off-site | `klusapp-urenbackup.timer` → `manage.py mail_urenbackup`, maandag 06:00, uren + aanwezigheid als Excel naar het adres op Mijn profiel van de eigenaar |

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
DATABASE_URL=postgres://klusapp:<geheim>@127.0.0.1:5432/klusapp
EMAIL_HOST=<smtp-server van handigerai.nl>
EMAIL_PORT=587
EMAIL_HOST_USER=kennismaken@handigerai.nl
EMAIL_HOST_PASSWORD=<app-wachtwoord>
```

Dezelfde `EMAIL_*`-regels versturen ook de "wachtwoord vergeten"-mails. Zonder
`EMAIL_HOST` gaat er niets de deur uit, en zeggen de reset-schermen dat eerlijk
("mail versturen is op deze server nog niet ingesteld"). Afzender is
`EMAIL_HOST_USER`. Sinds 01-10-2026 is dat **kennismaken@handigerai.nl**
(besluit Thijmen; daarvoor stond hier een eigen adres van De Groene M als
afspraak van 30-09). Dat geldt dus ook voor de resetmails.

Zonder `DATABASE_URL` valt `settings.py` terug op SQLite. Dat is prima lokaal,
maar niet op de server: SQLite vergrendelt bij schrijven en zes man die 's avonds
tegelijk hun uren invullen lopen dan tegen "database is locked" aan.

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
8. Back-up terugzetten: de database-dump en `media/` (zie "Back-ups"). Is de
   server helemaal weg, dan staan de uren nog in de laatste urenback-upmail.

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
    client_max_body_size 50M;
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

`client_max_body_size` is niet optioneel en niet cosmetisch. Zonder die regel staat
nginx op zijn standaard van 1 MB en wordt elke upload van een telefoonfoto geweigerd
vóórdat Django hem ziet. Django zelf legt géén grens op bestandsgrootte —
`DATA_UPLOAD_MAX_MEMORY_SIZE` in `settings.py` rekent expliciet buiten geüploade
bestanden om, en `FILE_UPLOAD_MAX_MEMORY_SIZE` is alleen het schakelpunt tussen
geheugen en een tijdelijk bestand. Deze regel is dus de enige echte bovengrens, en
wie hem weghaalt of verlaagt breekt het uploaden zonder dat er iets in de app te zien
is: de gebruiker krijgt de kale `413`-pagina van nginx.

Waarom 50M en niet 20M (de waarde die er tot 22-09-2026 stond): de grens geldt per
*request*, niet per bestand, en het uploadveld neemt bewust meerdere bestanden tegelijk
(`MeerdereBestandenInvoer` in `klussen/forms.py`). Acht telefoonfoto's van 4 MB is dus
één verzoek van 32 MB, en dat klapte er in zijn geheel uit — niet één foto, alles. Met
50M past zo'n selectie én een A0-tekening als PDF. Het is een plafond, geen reservering:
nginx streamt de body naar schijf.

## degroenem.handigerai.nl — Maartens echte omgeving

Sinds oktober 2026 draaien er twee installaties van de klusapp op deze VPS:

| | develop.handigerai.nl | degroenem.handigerai.nl |
|---|---|---|
| Voor | testen, door Thijmen en Floris | Maarten en zijn medewerkers, echte gegevens |
| Map | `/srv/handigerai/develop-tool` | `/srv/handigerai/degroenem` |
| Database | `klusapp` | `degroenem` |
| Poort · service | 5001 · `develop-tool.service` | 5002 · `degroenem.service` |
| Updaten | vanzelf, elke push naar `main` | met de hand: `docs/deploy-degroenem.sh` |
| Testfuncties | aan | uit (`KLUSAPP_TESTFUNCTIES=0`) |

Alles is apart: map, database, `.env` (eigen secret key), media en log. Alleen
de mailinstellingen zijn dezelfde (kennismaken@handigerai.nl). De werkwijze:
pushen naar `main`, op develop testen, en pas als het daar goed is
`deploy-degroenem.sh` draaien. Dat script maakt eerst een dump van de database
(`/srv/backups/degroenem/voor-deploy-*.sql.gz`) en laat zien welke commits erbij
komen.

`KLUSAPP_TESTFUNCTIES=0` zet twee hulpmiddelen uit die alleen voor het bouwen
bedoeld zijn: als eigenaar meekijken als medewerker, en een eigenaar die vanzelf
in `/beheer/` mag.

**HandigerAI kijkt mee met een verborgen account** (`manage.py maak_beheerder
admin`, vraagt zelf om een wachtwoord). Dat is eigenaar én superuser, dus het
ziet alles en komt in `/beheer/`, maar het staat in geen enkele lijst, telling,
rooster of back-upmail (`Medewerker.verborgen`; `Medewerker.objects` laat het
weg, `Medewerker.alle` niet). Wat je ermee invoert, zoals uren, is wel echte
data in Maartens administratie: alleen kijken.

**Inrichten** (eenmalig, als root): DNS-record `degroenem` → `178.105.192.98`, dan

```bash
git clone https://github.com/kennismaken-wq/development.git /srv/handigerai/degroenem
chown -R develop:develop /srv/handigerai/degroenem
bash /srv/handigerai/degroenem/klusapp/docs/degroenem-inrichten.sh <mailadres Maarten>
certbot --nginx -d degroenem.handigerai.nl
```

Het script maakt de database, de `.env` (met nieuwe geheimen die niet in beeld
komen), `degroenem.service` en de nginx-site aan, en één account: `maarten`, met
rol eigenaar, een willekeurig wachtwoord dat niemand kent, en de back-upmail
naar zijn adres (`manage.py maak_eigenaar`). Geen testdata. Maarten kiest
zijn wachtwoord zelf via "Wachtwoord vergeten" op de inlogpagina.

**Back-ups na de overstap:** de nachtelijke dump (`klusapp-backup.sh`) neemt
`degroenem` vanzelf mee zodra die map bestaat. Zet de wekelijkse mail om naar
Maartens omgeving, anders krijgt hij testdata:

```bash
sed -i 's#/srv/handigerai/develop-tool/#/srv/handigerai/degroenem/#g' /etc/systemd/system/klusapp-urenbackup.service
systemctl daemon-reload
```

## Back-ups

`klusapp-backup.timer` draait elke nacht om 03:20 `/usr/local/bin/klusapp-backup.sh`:
een `pg_dump` van de database en een tar van `media/`, allebei gzip, naar
`/srv/backups/klusapp`. Dumps ouder dan veertien dagen worden opgeruimd.

De restore is op 16-09-2026 één keer echt uitgevoerd (teruggezet in een
wegwerpdatabase `klusapp_restoretest`, rijen geteld, database daarna weggegooid) —
een ongeteste restore is geen back-up.

Terugzetten gaat zo:

```bash
gunzip -c /srv/backups/klusapp/db-<stempel>.sql.gz | sudo -u postgres psql klusapp
tar xzf /srv/backups/klusapp/media-<stempel>.tar.gz -C /srv/handigerai/develop-tool/klusapp
systemctl restart develop-tool.service
```

> **Dit is nog geen echte back-up.** De kopie staat op dezelfde schijf als wat hij
> moet beschermen: bij schijfverlies ben je alles kwijt, en de klusfoto's bestaan
> nergens anders. De verwerkersovereenkomst belooft off-site back-ups. Dit is een
> bewuste tussenoplossing (besluit Thijmen, 16-09-2026) totdat er een Hetzner
> Storage Box is; dan hoeft alleen het doelpad in het script te veranderen.

### Uren en aanwezigheid off-site: wekelijkse mail

Besluit 29-09-2026: alleen de **uren** hoeven off-site, en het moet gratis en
simpel; sinds 01-10-2026 gaat de **aanwezigheid** mee. Elke maandag om 06:00
mailt `manage.py mail_urenbackup` twee Excels, allebei met álles sinds het
begin: de uren (dezelfde opmaak als de urenexport) en de aanwezigheid (één
tabblad per jaar, dagen onder elkaar, een kolom per medewerker, net als de
werkplanning). De nieuwste mail is dus altijd compleet; de oudere zijn eerdere
versies. Code: `uren/backup.py`.

- **Van:** `kennismaken@handigerai.nl` — de SMTP-gegevens in `.env` (zie
  hierboven), met een **app-wachtwoord**, nooit het gewone wachtwoord.
- **Naar:** het adres dat een eigenaar invult op *Mijn profiel → Back-up per
  mail* (veld `Medewerker.backup_email`). Meerdere eigenaren met een adres
  krijgen hem allemaal. Daar staat ook een knop "Stuur nu een testmail".
  Staat er nergens een adres, dan faalt de service.

Foto's en klusdossiers gaan hier bewust niet mee. Die staan alleen op de VPS
en in de lokale dump hierboven. De verwerkersovereenkomst moet daarop
aangepast worden: die belooft nog off-site back-ups van alles.

```ini
# /etc/systemd/system/klusapp-urenbackup.service
[Unit]
Description=Wekelijkse back-up van uren en aanwezigheid per mail
[Service]
Type=oneshot
User=develop
WorkingDirectory=/srv/handigerai/develop-tool/klusapp
ExecStart=/srv/handigerai/develop-tool/.venv/bin/python manage.py mail_urenbackup

# /etc/systemd/system/klusapp-urenbackup.timer
[Timer]
OnCalendar=Mon 06:00 Europe/Amsterdam
Persistent=true
[Install]
WantedBy=timers.target
```

Handmatig testen of bekijken: `systemctl start klusapp-urenbackup.service` en
`journalctl -u klusapp-urenbackup.service -n 20`. Een mislukte verzending laat
de service falen (rood in `systemctl --failed`), niet stil slagen.

## Wat er nog niet staat

1. **Off-site back-up van foto's en database** — de uren gaan sinds 29-09-2026
   wekelijks per mail naar Maarten; de rest staat alleen op de VPS. Bewuste keuze.
2. **X-Accel-Redirect staat klaar maar is niet aangesloten.** `GEBRUIK_X_ACCEL`
   in `settings.py` en de view `klussen.views.media_bestand` zijn er al; de
   `internal`-locatie in nginx ontbreekt. Nu gaat elke foto door gunicorn heen.
   Bij de huidige hoeveelheid media niet urgent, bij een jaar klusfoto's wel.
3. **Data-export bij beëindiging** (uren als CSV, foto's als zip) — volgt uit de
   contractreview (SPEC §8), nog niet gebouwd.
