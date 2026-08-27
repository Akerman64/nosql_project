# Statut du projet

## Fait et vérifié (exécuté en local sur `mongodb://localhost:27017`, base `off_projet`)

| Livrable | État | Preuve |
|---|---|---|
| 1. Base + ingestion données réelles | ✅ **19 879 produits**, 5 660 catégories, 271 additifs (cible ≥ 10 000 atteinte) | `src/ingest.py`, `data/ingest.log` |
| 2. Modélisation justifiée | ✅ | `docs/schema.md`, `docs/fiche_modelisation.md`, validateur dans `src/model.py` |
| 3. CRUD Python + gestion d'erreurs | ✅ testé | `python -m src.crud` (create/read/update/delete + doublon + filtre vide refusé) |
| 4. Index mesurés explain avant/après | ✅ testé, 4 index | `src/indexes.py`, sortie figée dans `docs/mesures_index.txt` |
| 5. Rapport analytique (4 agrégations + viz) | ✅ notebook exécuté | `notebooks/rapport_analytique.ipynb` + `q1..q4_*.png` |
| 6. Scripts backup / restore | ✅ testé (dump gzip + restore --drop, index restaurés depuis metadata, 0 failure) | `scripts/backup.sh`, `scripts/restore.sh` |
| 7. Dépôt + README | ✅ | `README.md`, `docs/`, `.gitignore` (`.env.local` exclu) |
| Bonus IA — recherche vectorielle | ⚙️ code prêt, non exécuté (besoin Atlas + `sentence-transformers`) | `src/vector_search.py` |

## Reste à faire par l'équipe (hors périmètre automatisable)

1. **Atlas** : créer le cluster, un utilisateur applicatif à droits limités, coller l'URI
   dans `.env.local` sous `ATLAS_URI`. Aucun autre changement de code (tout passe par
   `src.db.get_db()`). Relancer `python -m src.ingest` pour charger la base sur Atlas.
2. **Volume** : 19 879 produits chargés en local (cible ≥ 10 000 atteinte). Relancer
   `python -m src.ingest` une fois `ATLAS_URI` en place pour recharger la base **sur Atlas**.
   `src/ingest.py --keep` est idempotent (upsert par code-barres) si on veut compléter.
3. **Index Atlas Vector Search** : créer l'index `idx_products_vec` avec la définition
   imprimée par `python -m src.vector_search index-def`, puis
   `python -m src.vector_search embed` et `... search "..."`.
4. **Vidéo de soutenance** (12–15 min, 4 segments, démo écran continue, question de
   défense tirée au sort jeudi).
5. **Mini-défense jeudi** : s'appuyer sur `docs/fiche_modelisation.md` (chaque relation :
   décision / question qui a tranché / ce que ça coûte) et sur `../questions_justification_projet.md`.

## Répartition suggérée (4 personnes)

- **A — Données & modélisation** : `ingest.py`, `model.py`, `docs/schema.md`, `fiche_modelisation.md`
- **B — Accès & performance** : `crud.py`, `indexes.py`, `docs/mesures_index.txt`
- **C — Analytique** : `aggregations.py`, `notebooks/rapport_analytique.ipynb`
- **D — Ops & IA** : `scripts/backup.sh`+`restore.sh`, déploiement Atlas, `vector_search.py`

Chacun doit savoir défendre la partie des trois autres (règle des « trois questions » du jeudi).
