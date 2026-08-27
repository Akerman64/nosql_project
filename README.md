# Projet final — Base NoSQL : catalogue alimentaire français (Open Food Facts)

**Module** Conception et intégration d'une base de données NoSQL · MIA4 27.2 · NEEKOCODE x IPSSI

On conçoit, déploie sur MongoDB Atlas et analyse une base construite à partir d'un jeu de
données **réel** : les produits alimentaires vendus en France, issus d'[Open Food Facts](https://world.openfoodfacts.org/data).

- **Jeu de données** : Open Food Facts, API publique v2 — `https://world.openfoodfacts.org/api/v2/search`
  (données ouvertes, licences ODbL / DbCL, aucune donnée personnelle).
- **Volume cible** : ≥ 10 000 produits (`src/ingest.py` parcourt ~50 tranches de catégories).
- **Pourquoi MongoDB** : documents fortement imbriqués (`nutriments`, `ingredients` récursifs),
  tableaux de bornes inconnues (`categories_tags`, `additives`), champs absents par endroits,
  valeurs multilingues. Un schéma tabulaire régulier ne conviendrait pas — cf. `docs/fiche_modelisation.md`.

---

## Arborescence

```
projet_off/
├── src/
│   ├── db.py            connexion unique (URI depuis .env.local, jamais en clair)
│   ├── ingest.py        étape 1 : API OFF → transformation → 3 collections
│   ├── model.py         étape 2 : validateur JSON Schema (souple) sur products
│   ├── crud.py          étape 3 : CRUD + gestion d'erreurs réelle
│   ├── indexes.py       étape 4 : 3 index, explain() avant / après
│   ├── aggregations.py  étape 5 : 4 agrégations métier
│   └── vector_search.py bonus IA : recherche sémantique (Atlas Vector Search)
├── scripts/
│   ├── backup.sh        étape 6 : mongodump (gzip, horodaté)
│   └── restore.sh       étape 6 : mongorestore --drop
├── notebooks/
│   └── rapport_analytique.ipynb   les 4 agrégations + visualisations
├── docs/
│   ├── schema.md               schéma des collections
│   └── fiche_modelisation.md   décision / question / coût, relation par relation
├── requirements.txt
├── .env.example        modèle ; copier en .env.local (git-ignoré)
└── .gitignore
```

---

## Prérequis

- Python ≥ 3.9, MongoDB Database Tools (`mongodump`, `mongorestore`, `mongosh`)
- Un cluster **MongoDB Atlas** (rendu) ou un `mongod` local (dev)

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env.local
# éditer .env.local : renseigner ATLAS_URI (rendu) ou garder LOCAL_URI (dev)
```

`.env.local` n'est **jamais** versionné. Aucune chaîne de connexion, aucune clé n'apparaît
dans le code ni dans l'historique git.

---

## Lancer le projet, dans l'ordre

```bash
# 1. Charger les données réelles (≈ 10–30 min selon la disponibilité de l'API OFF)
python -m src.ingest                 # --limit 3000 pour un essai rapide

# 2. Poser le validateur de modélisation
python -m src.model                  # --show pour l'afficher

# 3. Démo CRUD (create / read / update / delete + cas d'erreur)
python -m src.crud

# 4. Index : mesure explain() AVANT, création, mesure APRÈS
python -m src.indexes                # --drop pour re-mesurer à zéro

# 5. Agrégations (aperçu console)
python -m src.aggregations
#    rapport complet avec visualisations :
jupyter nbconvert --to notebook --execute --inplace notebooks/rapport_analytique.ipynb

# 6. Sauvegarde / restauration
./scripts/backup.sh                          # → backups/AAAAMMJJ_HHMMSS/
./scripts/restore.sh backups/<...>/off_projet
```

Basculer local → Atlas : il suffit de renseigner `ATLAS_URI` dans `.env.local`. Tout le code
lit `src.db.get_db()`, rien d'autre à changer.

---

## Les 7 livrables — où les trouver

| # | Livrable | Emplacement |
|---|---|---|
| 1 | Base déployée sur Atlas | `ATLAS_URI` dans `.env.local` ; chargée par `src/ingest.py` |
| 2 | Modélisation justifiée | `docs/schema.md` + `docs/fiche_modelisation.md` + `src/model.py` |
| 3 | CRUD Python | `src/crud.py` (résultats typés, filtres vides refusés, erreurs PyMongo capturées) |
| 4 | Index mesurés | `src/indexes.py` — 4 index, `explain()` avant/après, ratio de sélectivité, taille |
| 5 | Rapport analytique | `src/aggregations.py` + `notebooks/rapport_analytique.ipynb` (4 pipelines + 4 graphes) |
| 6 | Scripts d'administration | `scripts/backup.sh`, `scripts/restore.sh` |
| 7 | Dépôt + README | ce fichier + `docs/` |

## Bonus IA — recherche vectorielle

`src/vector_search.py` : vectorise `name + ingredients_text`, crée un index Atlas Vector Search,
expose `search("une pâte à tartiner sans huile de palme")`. Nécessite Atlas + `sentence-transformers`
(gros téléchargement — voir le module). Démarche complète documentée, calquée sur le TP5.

---

## Index — synthèse des mesures

Généré par `python -m src.indexes` (voir `docs/mesures_index.txt` pour la sortie complète).

Mesuré sur 19 879 produits (base locale) :

| Index | Requête servie | Avant | Après |
|---|---|---|---|
| `idx_category_main` | produits d'une catégorie feuille | COLLSCAN 19 879 docs, 3 ms | IXSCAN, 68 docs examinés, 0 ms |
| `idx_nutriscore_sugars` | Nutri-Score + tri par sucre (ESR) | COLLSCAN 19 879 + SORT mémoire, 11 ms | IXSCAN, 4 236 docs, 3 ms, **tri fourni par l'index** |
| `idx_additives_multikey` | produits contenant un additif | COLLSCAN 19 879, 4 ms | IXSCAN multikey, 2 526 docs, 1 ms |
| `idx_last_modified` | modifiés depuis une date (plage + tri) | COLLSCAN 19 879 + SORT, 19 ms | IXSCAN, 10 ms, **étape SORT supprimée** |

Données ~45 Mo, index ~1,7 Mo au total. Sortie complète : `docs/mesures_index.txt`.

## Limites assumées (à défendre)

- Échantillon **France via API**, pas le dump mondial : volume et couverture plafonnés par la
  disponibilité de l'API publique le jour de l'ingestion. `src/ingest.py` est idempotent —
  relancer quand l'API est saine converge vers le volume cible.
- `products_count` des référentiels = instantané figé à l'ingestion (désynchronisé par tout
  CRUD ultérieur — choix assumé, cf. fiche).
- Hiérarchie de catégories reconstruite **heuristiquement** depuis l'ordre des tags.
- Marques stockées en chaînes libres → « top marques » approximatif.
- Ce qui casse à ×100 : section dédiée dans `docs/fiche_modelisation.md`.
