# Reprise après incident — « si on perdait le cluster demain »

Réponse à la question de défense : *« Si vous perdiez votre cluster Atlas demain,
que se passerait-il exactement ? »*

Testé pour de vrai le 2026-08-27 (sauvegarde depuis Atlas → restauration dans une
base neuve sur le même cluster, 18 417 produits + 5 314 catégories + 266 additifs
+ 4 index reconstruits, **0 erreur**).

---

## 1. Ce qui serait perdu, ce qui ne le serait pas

| Perdu avec le cluster | Conservé ailleurs |
|---|---|
| Les 3 collections en ligne (`products`, `categories`, `additives`) | Le **code** : GitHub `Akerman64/nodal_project` + un clone local par personne |
| L'utilisateur de base, la liste d'IP autorisées | Le **README** et les scripts de reconstruction |
| L'**index Atlas Vector Search** (bonus) | Le **dernier dump** : `projet_off/backups/AAAAMMJJ_HHMMSS/` produit par `backup.sh` |
| Les Cloud Backups d'Atlas s'ils sont liés au cluster supprimé | Les **données sources** : Open Food Facts est public → re-téléchargeables via `src/ingest.py` |

Autrement dit : **aucune donnée métier n'est définitivement perdue**, à condition
d'avoir un dump récent ou d'accepter de re-télécharger depuis Open Food Facts.

## 2. Deux niveaux de perte de données (RPO)

**RPO** = *Recovery Point Objective* = quelle quantité de données on perd, mesurée
en temps depuis la dernière sauvegarde utilisable.

- **Avec le dernier dump `backup.sh`** : on perd tout ce qui a changé depuis ce dump.
  Si on lance `backup.sh` une fois par jour → RPO ≤ 24 h.
- **Sans dump du tout** : on repart d'Open Food Facts avec `src/ingest.py`. RPO = 0
  au sens « on a des données à jour », mais elles ne sont **pas identiques** à
  celles perdues (l'API renvoie l'état actuel de la base collaborative, qui évolue).

## 3. La procédure de reprise, pas à pas

**RTO** (*Recovery Time Objective*, temps pour être de nouveau opérationnel) mesuré : **~7 min**.

1. **Recréer un cluster Atlas** M0 + un utilisateur de base (droit lecture/écriture
   sur `off_projet`) + autoriser les IP. — ~5 min
2. **Récupérer le code** : `git clone git@github.com:Akerman64/nodal_project.git`
   (déjà fait sur chaque poste). — 0 min
3. **Configurer** : mettre la nouvelle URL dans `.env.local` sous `ATLAS_URI`. — 30 s
4. **Restaurer les données** — deux cas :

   **Cas A — on a un dump** (chemin normal, fidèle) :
   ```bash
   ./scripts/restore.sh backups/<le-plus-récent>/off_projet
   ```
   → 3 collections + les 4 index reconstruits automatiquement depuis les
   fichiers `*.metadata.json.gz`. Mesuré : **~1 min 30** pour 24 000 documents.

   **Cas B — pas de dump disponible** (reconstruction complète) :
   ```bash
   python -m src.ingest        # re-télécharge depuis Open Food Facts, ~20–40 min
   python -m src.model         # repose le validateur
   python -m src.indexes       # recrée les 4 index
   ```

5. **Bonus vectoriel** (si utilisé) : recréer l'index Atlas Vector Search avec la
   définition de `python -m src.vector_search index-def`, puis
   `python -m src.vector_search embed`. — ~5 min + calcul des vecteurs

6. **Vérifier** :
   ```bash
   python -m src.aggregations                     # les 4 questions répondent
   mongosh "$ATLAS_URI" --eval 'db.getSiblingDB("off_projet").products.getIndexes()'
   ```

## 4. Ce qui garantit que ça marche

- La restauration a été **testée**, pas supposée : `backup.sh` puis restauration
  dans une base neuve, comptages et index vérifiés. Une sauvegarde jamais
  restaurée n'est pas une sauvegarde.
- `mongodump` embarque les **définitions d'index** (`*.metadata.json.gz`) :
  `mongorestore` les recrée sans intervention.

## 5. Faiblesses actuelles — et comment on les corrigerait

| Faiblesse | Correctif |
|---|---|
| Le dump n'est **pas versionné** (`.gitignore` exclut `backups/`) : il n'existe que sur le poste qui a lancé `backup.sh` | L'externaliser après chaque `backup.sh` : dépôt de fichiers partagé (Drive / S3), ou Git LFS. Règle **3-2-1** : 3 copies, 2 supports, 1 hors site. |
| **Pas de sauvegarde planifiée** : elle dépend de quelqu'un qui y pense | Une tâche `cron` quotidienne : `0 3 * * * cd .../projet_off && ./scripts/backup.sh` |
| Sur le plan **M0 gratuit**, les Cloud Backups Atlas ne sont pas inclus | En production, passer sur un plan M10+ : snapshots quotidiens automatiques + restauration *point-in-time* (RPO proche de zéro) |
| `backup.sh` fait un dump **sans `--oplog`** : sur une base active, les collections sont figées à des instants différents | Ajouter `--oplog` au dump et `--oplogReplay` à la restauration, ou utiliser un snapshot disque Atlas |

## 6. La réponse en 20 secondes (pour la vidéo)

> On recrée un cluster Atlas (~5 min), on a le code sur GitHub, et on restaure le
> dernier dump avec `./scripts/restore.sh` : 3 collections et 4 index reviennent en
> une minute et demie, testé. On perd au pire les données ajoutées depuis le
> dernier dump — sur un `backup.sh` quotidien, 24 h. Sans dump, on retélécharge
> depuis Open Food Facts en 30 minutes, avec des données à jour mais pas
> identiques. La faiblesse qu'on assume : aujourd'hui le dump n'est que sur un
> poste ; en vrai on l'enverrait sur un stockage hors site et on planifierait un
> `cron` quotidien.
