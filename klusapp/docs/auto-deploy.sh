#!/bin/bash
# Referentiekopie van het deploy-script dat op de VPS draait.
#
# De draaiende versie staat op de server in de repo-root:
#   /srv/handigerai/develop-tool/auto-deploy.sh
# en wordt elke minuut gestart door develop-auto-deploy.timer.
#
# Bewust NIET in de repo-root gezet: de deploy doet `git reset --hard`, en dan
# zou git het script vervangen terwijl bash het nog regel voor regel aan het
# uitvoeren is. Deze kopie is er om het te kunnen terugbouwen, zie DEPLOY.md.
# Wijzig je 'm hier, zet 'm dan ook met de hand op de server.
set -euo pipefail
REPO=/srv/handigerai/develop-tool
APP=$REPO/klusapp

sudo -u develop -H git -C "$REPO" fetch origin main --quiet

LOCAL=$(sudo -u develop -H git -C "$REPO" rev-parse HEAD)
REMOTE=$(sudo -u develop -H git -C "$REPO" rev-parse origin/main)

if [ "$LOCAL" = "$REMOTE" ]; then
  exit 0
fi

echo "Nieuwe commits: ${LOCAL:0:7} -> ${REMOTE:0:7}"
sudo -u develop -H git -C "$REPO" reset --hard origin/main
sudo -u develop -H "$REPO/.venv/bin/pip" install -q -r "$APP/requirements.txt"
sudo -u develop -H "$REPO/.venv/bin/python" "$APP/manage.py" migrate --noinput
# Verplicht: bij DEBUG=0 gebruikt WhiteNoise de manifest-storage, en die gooit
# een fout op elke {% static %} die niet in staticfiles.json staat.
sudo -u develop -H "$REPO/.venv/bin/python" "$APP/manage.py" collectstatic --noinput >/dev/null
systemctl restart develop-tool.service
sleep 2
systemctl is-active develop-tool.service
echo "Deploy klaar op commit ${REMOTE:0:7}"
