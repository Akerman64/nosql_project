#!/usr/bin/env bash
# Restauration de la base du projet avec mongorestore.
# Usage : ./scripts/restore.sh chemin/vers/dump/<dbname>
#
#   backups/20260827_120000/off_projet   <-- on passe CE dossier (celui qui
#                                            contient products.bson.gz, ...)
#
# --drop : chaque collection est videe avant restauration, pour revenir
# EXACTEMENT a l'etat de la sauvegarde. Sans --drop, une restauration sur une
# base non vide n'ecrase RIEN (les insert en doublon de _id echouent en silence)
# et la base reste abimee -- c'est le piege vu au TP ops.
set -euo pipefail

cd "$(dirname "$0")/.."

# Lecture sûre de .env.local (voir backup.sh) : on n'exécute pas le fichier.
read_env() { grep -E "^$1=" .env.local | head -1 | cut -d= -f2- | sed -e 's/^"//' -e 's/"$//' -e "s/^'//" -e "s/'\$//"; }
ATLAS_URI="$(read_env ATLAS_URI)"
LOCAL_URI="$(read_env LOCAL_URI)"
DB_NAME="$(read_env DB_NAME)"

URI="${ATLAS_URI:-${LOCAL_URI:?Aucune URI dans .env.local}}"
DB="${DB_NAME:-off_projet}"
SRC="${1:?Chemin du dump attendu, ex: backups/20260827_120000/off_projet}"

SRC_DB="$(basename "$SRC")"          # nom de base d'origine (nom du dossier)
PARENT="$(dirname "$SRC")"           # racine du dump

echo ">> mongorestore  ${SRC_DB}  ->  ${DB}   (depuis ${SRC})"
mongorestore --uri "$URI" --gzip --drop \
  --nsInclude "${SRC_DB}.*" \
  --nsFrom "${SRC_DB}.*" --nsTo "${DB}.*" \
  "$PARENT"

echo ">> verification :"
mongosh "$URI" --quiet --eval "
  const d = db.getSiblingDB('$DB');
  ['products','categories','additives'].forEach(c =>
    print('   ' + c + ' : ' + d[c].countDocuments()));
"
