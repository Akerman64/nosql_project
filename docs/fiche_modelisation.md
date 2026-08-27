# Fiche de modélisation

Pour chaque relation : cardinalité · décision · **la question qui a tranché** · **ce que ça coûte**.

---

## 1. produit ↔ nutriments

- **Cardinalité** : 1–1. Un produit a un et un seul bloc de valeurs nutritionnelles (pour 100 g).
- **Décision** : **embarqué**, sous-document `nutriments`.
- **Question qui a tranché** : « lit-on jamais les nutriments sans le produit, ou l'inverse ? »
  Non. Toute requête métier (Nutri-Score, sucre, sel) part du produit et veut ses nutriments
  dans la foulée. Aucune raison de payer une jointure.
- **Ce que ça coûte** : les clés `*_100g` sont hétérogènes dans la source (plus de 100 variantes
  possibles). On en fige 9 au chargement ; si demain on veut `caffeine_100g`, il faut re-ingérer.
  Un sous-document séparé aurait absorbé ça sans toucher au produit.

## 2. produit ↔ ingredients

- **Cardinalité** : 1–N. Médiane observée ~8, maximum réel > 40.
- **Décision** : **embarqué**, tableau de sous-documents, **borné à 60** à l'ingestion.
- **Question qui a tranché** : « la liste d'ingrédients est-elle interrogée pour elle-même,
  indépendamment du produit ? » Non — on l'affiche et on l'analyse produit par produit.
  Tableau de taille raisonnable, lu avec le parent : cas d'école de l'embarquement.
- **Ce que ça coûte** : (a) la borne à 60 tronque les rares produits à rallonge (plats préparés
  composites) ; (b) les ingrédients composés d'Open Food Facts sont **récursifs** — on a aplati
  au premier niveau, donc « quels produits contiennent de la lécithine *dans* un ingrédient
  composé » n'est pas répondable sans re-parser ; (c) pas de dédoublonnage : « lécithine de soja »
  et « soja (lécithine) » restent deux entrées.

## 3. produit ↔ catégories

- **Cardinalité** : N–N, sur une **hiérarchie** (`en:snacks` → `en:sweet-snacks` → `en:biscuits`).
- **Décision** : **double stockage**. (a) `categories_tags` = tableau **aplati** de tous les
  ancêtres, copié dans le produit ; (b) `category_main` = la feuille ; (c) collection
  `categories` (référentiel) avec `name`, `parents`, `products_count`.
- **Question qui a tranché** : « quelle est la requête dominante ? » → « tous les produits sous
  *snacks* et ses sous-catégories », et « répartition par catégorie ». L'aplatissement rend la
  première triviale (`categories_tags: "en:snacks"`) et indexable, sans `$graphLookup`.
- **Ce que ça coûte** : (a) **redondance** — chaque produit répète toute sa chaîne d'ancêtres
  (~6 tags) ; (b) si la taxonomie Open Food Facts est réorganisée, il faut recalculer le tableau
  sur tous les produits ; (c) `products_count` dans `categories` est un **instantané** figé au
  chargement : tout `insert`/`delete` de produit le désynchronise (choix assumé : on le
  recalcule à l'ingestion, pas en temps réel).

## 4. produit ↔ additifs

- **Cardinalité** : N–N. 0 à ~30 additifs par produit.
- **Décision** : tableau de tags `additives` dans le produit **+** collection `additives`
  (référentiel : `code`, `products_count`).
- **Question qui a tranché** : « veut-on enrichir chaque additif d'infos partagées (libellé,
  classe, risque) et les requêter ? » Oui, à terme. Un tableau de chaînes seul obligerait à
  répéter ces infos sur chaque produit. Le référentiel les centralise ; le `$lookup` du rapport
  analytique (Q3) s'appuie dessus.
- **Ce que ça coûte** : une jointure applicative à maintenir cohérente ; aujourd'hui `name` ==
  `code` faute de table de correspondance E-number → libellé (à brancher sur la taxonomie OFF).

## 5. produit ↔ marques

- **Cardinalité** : N–N en théorie ; en pratique 1 marque pour ~95 % des produits.
- **Décision** : **embarqué en chaînes normalisées** (`brands: ["ferrero"]`). **Pas** de
  collection `brands`.
- **Question qui a tranché** : « qu'apporterait une entité marque ? » Presque rien ici : pas
  d'attribut de marque à stocker (siège, groupe…) dans le périmètre, et forte volatilité des
  libellés dans la source. Le coût d'une collection + jointure n'est pas payé par un besoin.
- **Ce que ça coûte** : pas de garantie d'unicité — `"cocacola"`, `"coca-cola"`, `"coca cola"`
  coexistent (on normalise en minuscule + trim, ça ne suffit pas). Un « top marques » est donc
  approximatif. Si le projet grossissait vers une analyse par groupe industriel, il faudrait
  promouvoir `brands` en référentiel.

## 6. produit ↔ pays

- **Cardinalité** : N–N. On a filtré sur la France mais un produit garde tous ses pays de vente.
- **Décision** : embarqué, tableau de tags `countries`.
- **Question qui a tranché** : « le pays est-il un axe d'analyse ou un simple filtre ? » Un
  filtre. Tableau de tags indexable, aucun attribut pays à porter.
- **Ce que ça coûte** : une agrégation « X par pays » **double-compte** un produit vendu dans
  5 pays. Acceptable ici (périmètre France) ; à corriger par `$unwind` + pondération sinon.

## 7. catégorie ↔ catégorie parente

- **Cardinalité** : N–N (une catégorie peut avoir plusieurs parents → DAG, pas arbre).
- **Décision** : `parents: [tag]` dans `categories`, **déduit de l'ordre** des tags sur les
  produits (le tag qui précède immédiatement est un parent).
- **Question qui a tranché** : « a-t-on besoin de remonter la hiérarchie par requête ? » Rarement
  — l'aplatissement dans le produit couvre le cas courant. On garde quand même `parents` pour
  documenter la structure et permettre un `$graphLookup` ponctuel.
- **Ce que ça coûte** : reconstruction **heuristique** — si aucun produit ne présente le couple
  (parent, enfant) adjacent, l'arête manque. La hiérarchie stockée est donc une approximation
  de la taxonomie officielle.

---

## Ce qui casserait à ×100 (catalogue mondial complet, ~3 M produits)

- `products_count` figés dans `categories`/`additives` : à remplacer par un recalcul planifié
  ou une vue matérialisée.
- Aplatissement des `categories_tags` : +~6 tags/produit × 3 M = coût de stockage et d'écriture
  réel ; envisager de ne garder que `category_main` + `$graphLookup` à la demande.
- Filtre pays retiré → double comptage massif : `$unwind` obligatoire sur `countries`.
- Marques en chaînes libres : ingérable pour une analyse fiable → référentiel + résolution
  d'alias.
