"""Etape 4 : trois index, chacun mesure `explain()` AVANT et APRES.

Pour chaque index :
  - la requete reelle qu'il sert,
  - le plan avant (COLLSCAN) : docs examines, temps,
  - le plan apres (IXSCAN)   : docs examines, temps, ratio nRetournes/nExamines.

    python -m src.indexes            # mesure + cree les index
    python -m src.indexes --drop     # supprime les index du projet (pour re-mesurer)
"""
from __future__ import annotations

import argparse
import time
from datetime import datetime, timezone

from .db import get_db

# (nom, cle, requete servie, tri eventuel)
INDEXES = [
    {
        "name": "idx_category_main",
        "keys": [("category_main", 1)],
        "query": {"category_main": "en:biscuits"},
        "sort": None,
        "sert": "lister les produits d'une categorie feuille donnee",
    },
    {
        "name": "idx_nutriscore_sugars",
        "keys": [("nutriscore_grade", 1), ("nutriments.sugars_100g", -1)],
        "query": {"nutriscore_grade": "e"},
        "sort": [("nutriments.sugars_100g", -1)],
        "sert": "produits d'un Nutri-Score, tries du plus sucre au moins sucre (regle ESR)",
    },
    {
        "name": "idx_additives_multikey",
        "keys": [("additives", 1)],
        "query": {"additives": "en:e322"},
        "sort": None,
        "sert": "retrouver tous les produits contenant un additif (index multikey sur tableau)",
    },
    {
        "name": "idx_last_modified",
        "keys": [("last_modified_t", -1)],
        "query": {"last_modified_t": {"$gte": datetime(2024, 1, 1, tzinfo=timezone.utc)}},
        "sort": [("last_modified_t", -1)],
        "sert": "flux des produits modifies depuis une date (plage + tri, dimension temporelle)",
    },
]


def _measure(col, q, sort):
    plan = col.find(q)
    if sort:
        plan = plan.sort(sort)
    ex = plan.explain()
    stage = ex["queryPlanner"]["winningPlan"]
    exec_stats = ex["executionStats"]
    # descend jusqu'au stage feuille
    s = stage
    names = []
    while s:
        names.append(s.get("stage"))
        s = s.get("inputStage")
    return {
        "stages": " <- ".join(names),
        "n_returned": exec_stats["nReturned"],
        "docs_examined": exec_stats["totalDocsExamined"],
        "keys_examined": exec_stats["totalKeysExamined"],
        "millis": exec_stats["executionTimeMillis"],
    }


def _pick_query_values(col):
    """Choisit des valeurs de filtre qui existent vraiment dans la base chargee,
    pour que la demonstration AVANT/APRES porte sur des resultats non vides."""
    leaf = col.find_one({"category_main": {"$ne": None}}, sort=[("unique_scans_n", -1)])
    if leaf:
        INDEXES[0]["query"] = {"category_main": leaf["category_main"]}
    grade = next((g["_id"] for g in col.aggregate([
        {"$match": {"nutriscore_grade": {"$in": list("abcde")}}},
        {"$group": {"_id": "$nutriscore_grade", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}}, {"$limit": 1}])), "d")
    INDEXES[1]["query"] = {"nutriscore_grade": grade}
    add = next((a["_id"] for a in col.aggregate([
        {"$unwind": "$additives"},
        {"$group": {"_id": "$additives", "n": {"$sum": 1}}},
        {"$sort": {"n": -1}}, {"$limit": 1}])), "en:e322")
    INDEXES[2]["query"] = {"additives": add}


def run(drop_only: bool = False):
    db = get_db()
    col = db.products
    if not drop_only:
        _pick_query_values(col)

    project_idx = {i["name"] for i in INDEXES}
    for name in list(project_idx):
        if name in [ix["name"] for ix in col.list_indexes()]:
            col.drop_index(name)
    if drop_only:
        print("Index du projet supprimes.")
        return

    for spec in INDEXES:
        print("\n" + "=" * 78)
        print(f"{spec['name']}  ->  {spec['sert']}")
        print(f"requete : {spec['query']}" + (f"  tri : {spec['sort']}" if spec["sort"] else ""))

        before = _measure(col, spec["query"], spec["sort"])
        t0 = time.perf_counter()
        col.create_index(spec["keys"], name=spec["name"])
        build_ms = (time.perf_counter() - t0) * 1000
        after = _measure(col, spec["query"], spec["sort"])

        print(f"  AVANT : {before['stages']:<28} "
              f"docs_examines={before['docs_examined']:>6}  "
              f"retournes={before['n_returned']:>5}  {before['millis']} ms")
        print(f"  APRES : {after['stages']:<28} "
              f"docs_examines={after['docs_examined']:>6}  "
              f"cles_examinees={after['keys_examined']:>6}  "
              f"retournes={after['n_returned']:>5}  {after['millis']} ms")
        ratio = (after["n_returned"] / after["docs_examined"]) if after["docs_examined"] else 1.0
        print(f"  index construit en {build_ms:.0f} ms | "
              f"selectivite nRetournes/nExamines = {ratio:.2f}")

    # taille des index vs donnees
    stats = db.command("collStats", "products")
    print("\n" + "-" * 78)
    print(f"taille donnees  : {stats['size'] / 1e6:.1f} Mo")
    print(f"taille index    : {stats['totalIndexSize'] / 1e6:.1f} Mo")
    for name, size in stats["indexSizes"].items():
        print(f"    {name:<28} {size / 1e6:.2f} Mo")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--drop", action="store_true")
    a = ap.parse_args()
    run(drop_only=a.drop)
