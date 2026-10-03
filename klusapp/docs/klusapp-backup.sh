#!/bin/bash
# Dagelijkse dump van de klusapp: database + geuploade media.
#
# LET OP: dit is een tussenoplossing, geen echte back-up. De kopie staat op
# dezelfde schijf als wat hij moet beschermen, dus bij schijfverlies ben je
# alles kwijt. De verwerkersovereenkomst belooft off-site back-ups; zet dit
# zodra het kan door naar een Hetzner Storage Box. Zie klusapp/docs/DEPLOY.md.
#
# Twee omgevingen sinds oktober 2026: develop (database klusapp) en Maartens
# echte omgeving degroenem.handigerai.nl (database degroenem). Elk in een
# eigen map onder /srv/backups.
set -euo pipefail
STAMP=$(date +%Y%m%d-%H%M%S)
BEWAARDAGEN=14

dump() {
  local naam=$1 database=$2 app=$3
  local doel=/srv/backups/$naam
  [ -d "$app" ] || return 0
  mkdir -p "$doel"
  sudo -u postgres pg_dump --no-owner --no-privileges "$database" | gzip > "$doel/db-$STAMP.sql.gz"
  if [ -d "$app/media" ]; then
    tar czf "$doel/media-$STAMP.tar.gz" -C "$app" media
  fi
  # Oude dumps opruimen, anders loopt de schijf een keer vol.
  find "$doel" -name "db-*.sql.gz" -mtime +$BEWAARDAGEN -delete
  find "$doel" -name "media-*.tar.gz" -mtime +$BEWAARDAGEN -delete
  echo "$(date -Is) back-up $naam klaar: db-$STAMP.sql.gz ($(du -h "$doel/db-$STAMP.sql.gz" | cut -f1))"
}

dump klusapp klusapp /srv/handigerai/develop-tool/klusapp
dump degroenem degroenem /srv/handigerai/degroenem/klusapp
