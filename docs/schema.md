# Schéma de la base `off_projet`

Source : Open Food Facts, API publique v2, produits vendus en France.
Trois collections. Le produit est le document racine ; catégories et additifs sont
des **référentiels** dérivés, référencés par tag.

```
┌─────────────────────────────┐
│ products                    │   _id = code-barres (EAN, string)
│                             │
│  name            string     │
│  brands          [string]   │◄─ embarqué : chaînes normalisées, pas de collection
│  quantity        string?    │
│  countries       [string]   │   tags ("en:france", …)
│  categories_tags [string]   │──┐ hiérarchie APLATIE (tous les ancêtres)
│  category_main   string?    │  │ = la feuille (catégorie la plus spécifique)
│  labels          [string]   │  │
│  additives       [string]   │──┼──┐ tags E-number
│  additives_n     int        │  │  │
│  ingredients_text string?   │  │  │
│  ingredients     [subdoc]   │◄─┼──┼─ embarqué : {id,text,percent_estimate,vegan,vegetarian}
│  ingredients_n   int?       │  │  │
│  nutriments      subdoc     │◄─┼──┼─ embarqué 1–1 : *_100g (energy_kcal, sugars, salt, …)
│  nutriscore_grade a–e|null  │  │  │
│  nova_group      1–4|null   │  │  │
│  ecoscore_grade  a–e|null   │  │  │
│  images_n        int        │  │  │
│  unique_scans_n  int        │  │  │
│  completeness    double?    │  │  │
│  created_t       date?      │  │  │  dimension temporelle
│  last_modified_t date?      │  │  │
│  source          string     │  │  │
└─────────────────────────────┘  │  │
              │ N:N par tag      │  │ N:N par tag
              ▼                  │  ▼
┌───────────────────────────┐   │  ┌──────────────────────────┐
│ categories                │   │  │ additives                │
│  _id   "en:biscuits"      │   │  │  _id  "en:e322"          │
│  name  "Biscuits"         │   │  │  code "E322"             │
│  parents [string]  ◄──────┼───┘  │  name "E322"             │
│  products_count int       │      │  products_count int      │
└───────────────────────────┘      └──────────────────────────┘
   auto-référence hiérarchique         (jointure $lookup dans le rapport)
```

## Clés et cardinalités

| Relation | Cardinalité | Traitement | Accès typique |
|---|---|---|---|
| produit → nutriments | 1–1 | embarqué (sous-doc) | toujours lu avec le produit |
| produit → ingredients | 1–N (borné ~60) | embarqué (tableau de sous-docs) | lu avec le produit |
| produit → categories | N–N | tableau de tags **+** référentiel `categories` | filtre direct sur le tableau ; libellé/hiérarchie via `categories` |
| produit → additives | N–N | tableau de tags **+** référentiel `additives` | filtre + `$lookup` pour le libellé |
| produit → brands | N–N (théorique) | embarqué, chaînes seules | filtre `brands: "..."` |
| produit → countries | N–N | embarqué, tags | filtre `countries: "en:france"` |
| categorie → parent | N–N (DAG) | `parents: [tag]` dans `categories` | remontée de hiérarchie |

## Index (voir `src/indexes.py`)

| Index | Clé | Sert |
|---|---|---|
| `idx_category_main` | `{category_main: 1}` | produits d'une catégorie feuille |
| `idx_nutriscore_sugars` | `{nutriscore_grade: 1, nutriments.sugars_100g: -1}` | Nutri-Score + tri sucre (règle ESR) |
| `idx_additives_multikey` | `{additives: 1}` | produits contenant un additif (multikey) |
| `idx_last_modified` | `{last_modified_t: -1}` | flux temporel des modifications |
