# Projet final — Questions de justification à préparer

**Projet :** base MongoDB Atlas à partir d'Open Food Facts (produits alimentaires + marques /
catégories / additifs / pays). Analyse nutritionnelle par agrégations.

> Rappel du contrat : 8 points sur 20 portent sur la capacité à **défendre** les choix, pas à
> produire. Pour chaque décision : la cardinalité, la décision prise, **la question qui a tranché**,
> et **ce que ça coûte**. Toute case « ce que ça coûte » vide ou pas crédible = points perdus.

Chaque membre du groupe doit pouvoir répondre à TOUTES les questions, pas seulement à sa partie.

---

## 1. Choix du jeu de données

1. Pourquoi Open Food Facts et pas mflix ou les restaurants de New York ?
2. Pourquoi MongoDB ici et pas PostgreSQL ? Qu'est-ce qui, dans ces données précises, justifie
   le document plutôt que le relationnel ?
3. Auriez-vous pu faire ce projet sur Neo4j ? Quelle serait la requête dominante qui justifierait
   un graphe, et pourquoi ce n'est pas votre cas ?
4. Combien de documents avez-vous chargés exactement ? Comment avez-vous scopé le jeu
   (par pays ? par catégorie ?) et qu'est-ce que ce filtre exclut ?
5. Quelle est la fraîcheur des données ? À quelle date correspond votre export ?
6. Quelle licence, et qu'est-ce qu'elle vous autorise / vous interdit pour ce rendu ?
7. Quelles données personnelles auraient pu s'y trouver, et comment avez-vous vérifié qu'il n'y
   en a pas (contributeurs, `creator`, photos) ?
8. Qu'est-ce qui est « sale » dans ce jeu ? Donnez trois exemples concrets rencontrés
   (champ manquant, unité incohérente, tag en double, valeur aberrante).
9. Comment avez-vous géré les champs multilingues (`product_name_fr`, `product_name_en`…) ?

---

## 2. Modélisation — questions générales

10. Décrivez votre schéma en une minute : quelles collections, quel document racine, quelles
    clés `_id` ?
11. Quelle est la granularité d'un document « produit » ? Un code-barres = un document ?
    Que faites-vous des doublons de code-barres ?
12. Combien de collections avez-vous, et pourquoi pas une de plus / une de moins ?
13. Avez-vous un schéma figé (validator) ou libre ? Pourquoi ce choix, et qu'est-ce qu'il vous
    coûte à l'usage ?
14. Quels champs avez-vous décidé de **ne pas** importer, et pourquoi ce n'est pas une perte
    pour vos questions métier ?
15. Comment représentez-vous une valeur nutritionnelle absente : champ à `null`, champ absent,
    ou `0` ? Quelle conséquence sur vos agrégations ?
16. Quelle taille moyenne et maximale font vos documents ? Êtes-vous loin de la limite des 16 Mo ?

---

## 3. Modélisation — chaque relation (fiche de modélisation)

Pour **chacune** des relations ci-dessous : cardinalité ? embarqué ou référencé ? quelle question
a tranché ? qu'est-ce que ça coûte ?

### 3.1 Produit ↔ nutriments
17. Pourquoi les nutriments sont-ils embarqués dans le produit ?
18. Quelle serait la requête qui deviendrait pénible si vous les aviez sortis dans une collection
    à part ?
19. Coût de l'embarquement : que se passe-t-il si le référentiel de nutriments change de
    définition ?

### 3.2 Produit ↔ marque (`brands`)
20. Une marque est-elle une chaîne dans un tableau, un sous-document, ou une collection référencée ?
21. Cardinalité réelle : un produit a-t-il vraiment plusieurs marques ? Exemple.
22. Si un utilisateur veut « tous les produits de la marque X », votre modèle répond-il bien ?
    Coût si la marque est juste une chaîne (fautes de casse, alias) ?
23. Avez-vous une collection `brands` séparée ? Si oui, pourquoi ce n'était pas du sur-engineering ;
    si non, ce que ça vous coûtera à l'échelle.

### 3.3 Produit ↔ catégories (`categories_tags`, taxonomie hiérarchique)
24. Comment stockez-vous une hiérarchie de catégories (`en:snacks` > `en:sweet-snacks` >
    `en:chocolates`) dans un modèle document ?
25. Avez-vous aplati la hiérarchie (tous les ancêtres dans un tableau) ou gardé seulement la
    feuille ? Quelle question métier a tranché ?
26. Coût de l'aplatissement : redondance, mise à jour de la taxonomie.
27. Comment répondez-vous à « tous les produits sous la catégorie *snacks* et ses
    sous-catégories » ?

### 3.4 Produit ↔ additifs (`additives_tags`)
28. Tableau de chaînes ou collection référencée d'additifs (avec libellé, code E, risque) ?
29. Si vous voulez enrichir chaque additif d'une fiche descriptive, votre choix tient-il ?
30. Cardinalité : borne du tableau ? Que faites-vous d'un produit à 30 additifs ?

### 3.5 Produit ↔ pays (`countries_tags`)
31. Un produit vendu dans plusieurs pays : comment est-ce modélisé, et est-ce que ça duplique
    le produit ou pas ?
32. Coût pour une agrégation « Nutri-Score moyen par pays » si un même produit compte dans
    5 pays ?

### 3.6 Produit ↔ ingrédients (`ingredients`, tableau potentiellement récursif)
33. Les ingrédients composés (un ingrédient qui a lui-même une liste) : gardez-vous la
    récursivité ou aplatissez-vous ?
34. Quelle profondeur maximale avez-vous observée ? Quel coût si vous l'aviez ignorée ?

---

## 4. CRUD Python

35. Comment la chaîne de connexion Atlas est-elle fournie au code ? Montrez qu'aucun identifiant
    n'est en clair, ni dans le code, ni dans l'historique git.
36. Sur le `update`, faites-vous `updateOne`/`updateMany`, `$set` ou remplacement complet ?
    Pourquoi, et quel risque avec l'autre option ?
37. Sur le `delete`, comment évitez-vous une suppression de masse accidentelle ? Filtre obligatoire ?
38. Quelles erreurs réelles gérez-vous : perte de connexion, timeout, `DuplicateKeyError`,
    `ValidationError` ? Montrez le bloc.
39. Que renvoie votre couche CRUD à l'appelant en cas d'échec — exception, `None`, code ?
    Pourquoi ce contrat ?
40. Gérez-vous les écritures en masse avec `bulk_write` / `insert_many` ? `ordered=True` ou
    `False`, et quelle conséquence sur un lot qui contient un doublon ?

---

## 5. Index (au moins 3, mesurés avant / après)

Pour **chaque** index :

41. Quelle requête précise cet index sert-il ? Montrez la requête.
42. `explain()` avant : quel `stage` (COLLSCAN ?), combien de documents examinés, quel temps ?
43. `explain()` après : `IXSCAN` ? ratio `nReturned / totalDocsExamined` ? gain de temps chiffré ?
44. Pourquoi cet ordre de champs dans un index composé ? (règle ESR : égalité, tri, portée)
45. Cet index couvre-t-il la requête (`PROJECTION_COVERED`) ou faut-il encore aller lire le
    document ?
46. Quel est le coût en écriture et en espace de cet index ? Combien pèsent vos index vs vos
    données ?
47. Avez-vous un index que vous avez volontairement **retiré** ? Pourquoi ?
48. Index sur un champ de tableau (`categories_tags`, `additives_tags`) : c'est un index
    multikey — quelles limites ça impose (pas deux tableaux dans un même index composé) ?
49. Avez-vous un index texte ou géospatial ? Sur quel champ, pour quelle requête ?
50. Un de vos index sert-il aussi une étape `$match` ou `$sort` de vos agrégations ? Montrez-le
    dans l'`explain` du pipeline.

---

## 6. Agrégations (au moins 3, questions métier réelles)

Pour **chaque** pipeline :

51. Quelle question métier concrète ce pipeline répond-il ? Qui, en dehors du groupe, s'y
    intéresserait ?
52. Déroulez le pipeline étape par étape, à voix haute, sans lire le code.
53. Pourquoi le `$match` est-il en première étape ? Que se passerait-il s'il était après le
    `$group` ?
54. Où sont vos `$unwind` ? Sur `categories_tags` ? Combien de documents ça multiplie, et est-ce
    que ça fausse un `count` ou une moyenne ?
55. Comment gérez-vous les valeurs manquantes dans un `$avg` (les `null` sont-ils ignorés,
    comptés à zéro) ?
56. Un `$group` avec `_id: null` vs `_id: "$champ"` : lequel utilisez-vous où et pourquoi ?
57. Avez-vous une étape `$lookup` ? Vers quelle collection, et pourquoi ce join ne remet-il pas
    en cause votre choix d'avoir séparé les deux entités ?
58. Le pipeline tient-il en mémoire ? Avez-vous eu besoin de `allowDiskUse` ? Pourquoi ?
59. Votre visualisation : que montre-t-elle exactement, quel axe, et quelle décision de lecture
    elle permet ?
60. Si le volume était multiplié par 100, ce pipeline tiendrait-il ? Qu'est-ce qui casserait
    en premier ?

---

## 7. Scripts d'administration (mongodump / mongorestore)

61. Que capture `mongodump` que `mongoexport` ne capture pas ? (types BSON, index, options de
    collection)
62. Votre script de restauration utilise-t-il `--drop` ? Dans quel cas c'est salutaire, dans
    quel cas c'est dangereux ?
63. Sans `--drop`, que se passe-t-il si les `_id` existent déjà ? Pourquoi une restauration qui
    « ne plante pas » mais ne restaure rien est-elle le pire scénario ?
64. Votre base fait X Go et le dump dure Y minutes pendant lesquelles l'app écrit : votre
    sauvegarde est-elle cohérente entre collections ? Avez-vous utilisé `--oplog` ?
65. Où est stocké le dump ? Sur le serveur de prod, ou externalisé ? Rétention prévue ?
66. Avez-vous **testé** la restauration sur un environnement vierge ? Preuve ?
67. Sur Atlas, qui fait réellement la sauvegarde en production, et à quelle fréquence ?
    Votre script est-il un complément ou un substitut ?

---

## 8. Déploiement Atlas & sécurité

68. Comment le correcteur se connecte-t-il vendredi ? Utilisateur dédié, droits limités ?
69. Le cluster est-il ouvert à `0.0.0.0/0` ? Pourquoi c'est un choix par défaut discutable, et
    qu'auriez-vous mis en vrai ?
70. `.gitignore`, historique git : montrez qu'aucune URI avec mot de passe n'a jamais été
    commitée. Comment l'avez-vous vérifié dans l'historique, pas juste au dernier commit ?
71. Si une clé fuitait, quelle est votre procédure de rotation ?

---

## 9. Bonus IA (si tenté)

72. Sur quel champ porte votre recherche vectorielle, et pourquoi ce champ a du sens à
    « embedder » ?
73. Quel modèle d'embedding, quelle dimension, quelle métrique de similarité, et pourquoi ?
74. Montrez une requête où la recherche vectorielle bat une recherche texte classique, et une
    où elle est moins bonne.
75. (Si journal de prompts) Donnez un cas où le modèle s'est trompé sur vos données, comment
    vous l'avez repéré et corrigé. Quelle limite en avez-vous tirée ?
76. Qu'est-ce que vous avez écrit vous-même vs généré ? Sauriez-vous réécrire l'agrégation
    générée sans l'IA ?

---

## 10. Recul critique (ce qui rapporte des points)

77. Quelle est la plus grande faiblesse de votre modèle ? Nommez-la avant qu'on la trouve.
78. Qu'est-ce qui casserait si le volume était multiplié par 100 ? Et qu'est-ce que vous feriez
    à la place ?
79. Quelle décision de modélisation regrettez-vous, avec le recul, et qu'auriez-vous fait
    autrement ?
80. Qu'est-ce qui, dans ce projet, vous a coûté le plus de temps pour le moins de valeur ?
81. Si vous aviez deux jours de plus, sur quoi les passeriez-vous et pourquoi ?
82. Répartition du travail : qui a fait quoi, et chacun peut-il défendre la partie des autres ?

---

## 11. Format vidéo (points de forme, à vérifier avant d'enregistrer)

83. Durée entre 12 et 15 min ?
84. Les 4 membres apparaissent à visage découvert en ouverture de leur segment ?
85. La démonstration est-elle un enregistrement d'écran **continu, non monté** ?
86. La question de défense tirée au sort jeudi est-elle annoncée à l'écran puis traitée
    explicitement ?
87. Fichier mp4 720p, déposé avant vendredi 16h45 (pas à 16h40) ?
