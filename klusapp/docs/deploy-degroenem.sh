#!/bin/bash
# Maartens omgeving (degroenem.handigerai.nl) bijwerken naar de nieuwste main.
#
# Bewust met de hand en niet elke minuut zoals develop: wat op main staat,
# is eerst op develop getest. Als root:
#   bash /srv/handigerai/degroenem/klusapp/docs/deploy-degroenem.sh
#
# Het script staat zelf in de repo die het reset. Daarom draait het vanuit
# een kopie in /tmp; anders vervangt git het bestand terwijl bash het nog
# regel voor regel leest.
set -euo pipefail
if [ "${DEPLOY_KOPIE:-}" != "1" ]; then
  KOPIE=$(mktemp /tmp/deploy-degroenem.XXXXXX.sh)
  cp "$0" "$KOPIE"
  DEPLOY_KOPIE=1 exec bash "$KOPIE" "$@"
fi

REPO=/srv/handigerai/degroenem
APP=$REPO/klusapp

sudo -u develop -H git -C "$REPO" fetch origin main --quiet
OUD=$(sudo -u develop -H git -C "$REPO" rev-parse --short HEAD)
NIEUW=$(sudo -u develop -H git -C "$REPO" rev-parse --short origin/main)
if [ "$OUD" = "$NIEUW" ]; then
  echo "Al bij: $OUD"
  exit 0
fi

echo "Wat er bijkomt ($OUD -> $NIEUW):"
sudo -u develop -H git -C "$REPO" log --oneline "$OUD..origin/main"

# Vangnet: eerst een dump, zodat een mislukte migratie terug te draaien is.
mkdir -p /srv/backups/degroenem
sudo -u postgres pg_dump --no-owner --no-privileges degroenem | gzip > "/srv/backups/degroenem/voor-deploy-$OUD.sql.gz"

sudo -u develop -H git -C "$REPO" reset --hard origin/main --quiet
sudo -u develop -H "$REPO/.venv/bin/pip" install -q -r "$APP/requirements.txt"
sudo -u develop -H "$REPO/.venv/bin/python" "$APP/manage.py" migrate --noinput
sudo -u develop -H "$REPO/.venv/bin/python" "$APP/manage.py" collectstatic --noinput >/dev/null
systemctl restart degroenem.service
sleep 2
systemctl is-active degroenem.service
rm -f "$0"
echo "degroenem.handigerai.nl staat op $NIEUW"
