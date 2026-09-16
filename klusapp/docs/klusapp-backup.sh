#!/bin/bash
# Dagelijkse dump van de klusapp: database + geuploade media.
#
# LET OP: dit is een tussenoplossing, geen echte back-up. De kopie staat op
# dezelfde schijf als wat hij moet beschermen, dus bij schijfverlies ben je
# alles kwijt. De verwerkersovereenkomst belooft off-site back-ups; zet dit
# zodra het kan door naar een Hetzner Storage Box. Zie klusapp/docs/DEPLOY.md.
set -euo pipefail
DOEL=/srv/backups/klusapp
APP=/srv/handigerai/develop-tool/klusapp
STAMP=$(date +%Y%m%d-%H%M%S)
BEWAARDAGEN=14
mkdir -p "$DOEL"

sudo -u postgres pg_dump --no-owner --no-privileges klusapp | gzip > "$DOEL/db-$STAMP.sql.gz"
tar czf "$DOEL/media-$STAMP.tar.gz" -C "$APP" media

# Oude dumps opruimen, anders loopt de schijf een keer vol.
find "$DOEL" -name "db-*.sql.gz" -mtime +$BEWAARDAGEN -delete
find "$DOEL" -name "media-*.tar.gz" -mtime +$BEWAARDAGEN -delete

echo "$(date -Is) back-up klaar: db-$STAMP.sql.gz ($(du -h "$DOEL/db-$STAMP.sql.gz" | cut -f1)), media-$STAMP.tar.gz ($(du -h "$DOEL/media-$STAMP.tar.gz" | cut -f1))"
