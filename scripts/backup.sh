#!/usr/bin/env bash
# Sauvegarde de la base du projet avec mongodump.
# Lit l'URI depuis .env.local (ATLAS_URI en priorite, sinon LOCAL_URI).
# Usage : ./scripts/backup.sh [dossier_de_sortie]
set -euo pipefail

cd "$(dirname "$0")/.."

# Lecture sûre de .env.local : on n'exécute pas le fichier (le '&' de l'URI
# Atlas casserait `source`). On extrait chaque variable et on retire les guillemets.
read_env() { grep -E "^$1=" .env.local | head -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'\$//"; }
ATLAS_URI="$(read_env ATLAS_URI)"
LOCAL_URI="$(read_env LOCAL_URI)"
DB_NAME="$(read_env DB_NAME)"

URI="${ATLAS_URI:-${LOCAL_URI:?Aucune URI dans .env.local}}"
DB="${DB_NAME:-off_projet}"
OUT="${1:-backups/$(date +%Y%m%d_%H%M%S)}"

mkdir -p "$OUT"
echo ">> mongodump  base=$DB  ->  $OUT"
mongodump --uri "$URI" --db "$DB" --out "$OUT" --gzip

echo ">> contenu :"
find "$OUT" -type f -exec ls -lh {} \; | awk '{print "   " $5 "  " $NF}'
echo ">> OK. Pour restaurer :  ./scripts/restore.sh $OUT/$DB"
