#!/usr/bin/env bash
# Sauvegarde de la base du projet avec mongodump.
# Lit l'URI depuis .env.local (ATLAS_URI en priorite, sinon LOCAL_URI).
# Usage : ./scripts/backup.sh [dossier_de_sortie]
set -euo pipefail

cd "$(dirname "$0")/.."
set -a; source .env.local; set +a

URI="${ATLAS_URI:-${LOCAL_URI:?Aucune URI dans .env.local}}"
DB="${DB_NAME:-off_projet}"
OUT="${1:-backups/$(date +%Y%m%d_%H%M%S)}"

mkdir -p "$OUT"
echo ">> mongodump  base=$DB  ->  $OUT"
mongodump --uri "$URI" --db "$DB" --out "$OUT" --gzip

echo ">> contenu :"
find "$OUT" -type f -exec ls -lh {} \; | awk '{print "   " $5 "  " $NF}'
echo ">> OK. Pour restaurer :  ./scripts/restore.sh $OUT/$DB"
