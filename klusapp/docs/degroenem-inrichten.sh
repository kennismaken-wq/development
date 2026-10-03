#!/bin/bash
# Eenmalig: Maartens echte omgeving degroenem.handigerai.nl inrichten, naast
# develop op dezelfde VPS maar met alles apart (map, database, .env, media,
# poort). Zie docs/DEPLOY.md, "degroenem.handigerai.nl".
#
# Als root, nadat de repo is gekloond:
#   git clone https://github.com/kennismaken-wq/development.git /srv/handigerai/degroenem
#   chown -R develop:develop /srv/handigerai/degroenem
#   bash /srv/handigerai/degroenem/klusapp/docs/degroenem-inrichten.sh <mailadres van Maarten>
#
# Geheimen maakt het script zelf aan (secret key, databasewachtwoord) en
# schrijft ze alleen in de .env; ze komen niet in beeld. De mailinstellingen
# neemt het over uit de .env van develop. HTTPS (certbot) is een losse stap
# erna, omdat daarvoor eerst het DNS-record moet bestaan.
set -euo pipefail

MAIL_MAARTEN=${1:?"Gebruik: $0 <mailadres van Maarten>"}
REPO=/srv/handigerai/degroenem
APP=$REPO/klusapp
DOMEIN=degroenem.handigerai.nl
POORT=5002
DEVELOP_ENV=/srv/handigerai/develop-tool/klusapp/.env

[ -d "$APP" ] || { echo "Eerst de repo klonen naar $REPO (zie bovenaan dit script)."; exit 1; }
[ -f "$APP/.env" ] && { echo "$APP/.env bestaat al; dit script is al gedraaid. Gestopt."; exit 1; }

echo "1/6 Python-omgeving"
sudo -u develop -H python3 -m venv "$REPO/.venv"
sudo -u develop -H "$REPO/.venv/bin/pip" install -q -r "$APP/requirements.txt"

echo "2/6 Database degroenem"
DB_WACHTWOORD=$(openssl rand -hex 24)
sudo -u postgres psql -q -c "CREATE ROLE degroenem LOGIN PASSWORD '$DB_WACHTWOORD';"
sudo -u postgres psql -q -c "CREATE DATABASE degroenem OWNER degroenem;"

echo "3/6 .env"
umask 077
{
  echo "DJANGO_DEBUG=0"
  echo "DJANGO_SECRET_KEY=$(openssl rand -base64 48 | tr -d '\n/+=')"
  echo "DJANGO_ALLOWED_HOSTS=$DOMEIN,127.0.0.1,localhost"
  echo "DJANGO_CSRF_TRUSTED_ORIGINS=https://$DOMEIN"
  echo "DATABASE_URL=postgres://degroenem:$DB_WACHTWOORD@127.0.0.1:5432/degroenem"
  # Geen meekijken als medewerker, geen /beheer/ voor de eigenaar.
  echo "KLUSAPP_TESTFUNCTIES=0"
  grep -E '^EMAIL_' "$DEVELOP_ENV"
} > "$APP/.env"
chown develop:develop "$APP/.env"
umask 022

echo "4/6 Database vullen (leeg) en statische bestanden"
sudo -u develop -H "$REPO/.venv/bin/python" "$APP/manage.py" migrate --noinput >/dev/null
sudo -u develop -H "$REPO/.venv/bin/python" "$APP/manage.py" collectstatic --noinput >/dev/null
sudo -u develop -H "$REPO/.venv/bin/python" "$APP/manage.py" maak_eigenaar maarten "$MAIL_MAARTEN" --voornaam Maarten

echo "5/6 Service degroenem.service op poort $POORT"
cat > /etc/systemd/system/degroenem.service <<EOF
[Unit]
Description=De Groene M - klusapp, Maartens omgeving (Django/gunicorn)
After=network.target postgresql.service

[Service]
LimitNOFILE=4096
Type=simple
User=develop
Group=develop
WorkingDirectory=$APP
ExecStart=$REPO/.venv/bin/gunicorn config.wsgi:application --chdir $APP --bind 127.0.0.1:$POORT --workers 3 --timeout 60
Restart=always
RestartSec=3
StandardOutput=append:$REPO/degroenem.log
StandardError=append:$REPO/degroenem.log
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=$REPO

[Install]
WantedBy=multi-user.target
EOF
systemctl daemon-reload
systemctl enable --now degroenem.service
sleep 2
systemctl is-active degroenem.service

echo "6/6 nginx"
cat > /etc/nginx/sites-available/$DOMEIN <<EOF
server {
    server_name $DOMEIN;
    client_max_body_size 50M;
    location / {
        proxy_pass http://127.0.0.1:$POORT;
        proxy_set_header Host \$host;
        proxy_set_header X-Real-IP \$remote_addr;
        proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto \$scheme;
    }
    listen 80;
}
EOF
ln -sf /etc/nginx/sites-available/$DOMEIN /etc/nginx/sites-enabled/$DOMEIN
nginx -t && systemctl reload nginx

echo
echo "Klaar. Nog te doen:"
echo "  - HTTPS:  certbot --nginx -d $DOMEIN"
echo "  - Maarten: 'Wachtwoord vergeten' op https://$DOMEIN met $MAIL_MAARTEN"
echo "  - Updaten: bash $APP/docs/deploy-degroenem.sh"
