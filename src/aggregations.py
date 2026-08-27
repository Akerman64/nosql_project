"""Etape 5 : le rapport analytique. Quatre agregations qui repondent a de vraies
questions metier sur le catalogue alimentaire francais.

Chaque fonction renvoie une liste de dicts prete a tracer (voir le notebook).

    python -m src.aggregations        # execute les 4 et imprime un apercu
"""
from __future__ import annotations

from .db import get_db


# Q1 - Le sucre est-il correle au Nutri-Score ? (mise en evidence d'une regle metier)
def sucre_par_nutriscore():
    db = get_db()
    return list(db.products.aggregate([
        {"$match": {"nutriscore_grade": {"$in": ["a", "b", "c", "d", "e"]},
                    "nutriments.sugars_100g": {"$ne": None}}},
        {"$group": {
            "_id": "$nutriscore_grade",
            "sucre_moyen_100g": {"$avg": "$nutriments.sugars_100g"},
            "sel_moyen_100g": {"$avg": "$nutriments.salt_100g"},
            "n": {"$sum": 1},
        }},
        {"$sort": {"_id": 1}},
    ]))


# Q2 - Quelles familles de produits sont les plus ultra-transformees ? (NOVA 4)
def part_ultra_transforme_par_categorie(min_produits=40):
    db = get_db()
    return list(db.products.aggregate([
        {"$match": {"nova_group": {"$ne": None}, "category_main": {"$ne": None}}},
        {"$group": {
            "_id": "$category_main",
            "n": {"$sum": 1},
            "n_nova4": {"$sum": {"$cond": [{"$eq": ["$nova_group", 4]}, 1, 0]}},
        }},
        {"$match": {"n": {"$gte": min_produits}}},
        {"$project": {
            "n": 1,
            "part_nova4": {"$round": [{"$multiply": [{"$divide": ["$n_nova4", "$n"]}, 100]}, 1]},
        }},
        {"$sort": {"part_nova4": -1}},
        {"$limit": 15},
    ]))


# Q3 - Les additifs les plus repandus, enrichis du libelle via la collection referentiel
def additifs_les_plus_frequents(top=15):
    db = get_db()
    return list(db.products.aggregate([
        {"$unwind": "$additives"},
        {"$group": {"_id": "$additives", "n_produits": {"$sum": 1}}},
        {"$sort": {"n_produits": -1}},
        {"$limit": top},
        {"$lookup": {
            "from": "additives",
            "localField": "_id",
            "foreignField": "_id",
            "as": "ref",
        }},
        {"$project": {
            "code": {"$ifNull": [{"$first": "$ref.code"}, "$_id"]},
            "n_produits": 1,
        }},
    ]))


# Q4 - Dynamique temporelle : nombre de produits ajoutes par annee, et Nutri-Score moyen
def ajouts_par_annee():
    db = get_db()
    grade_num = {"a": 1, "b": 2, "c": 3, "d": 4, "e": 5}
    rows = list(db.products.aggregate([
        {"$match": {"created_t": {"$ne": None}}},
        {"$group": {
            "_id": {"$year": "$created_t"},
            "n_ajouts": {"$sum": 1},
            "grades": {"$push": "$nutriscore_grade"},
        }},
        {"$sort": {"_id": 1}},
    ]))
    for r in rows:
        vals = [grade_num[g] for g in r.pop("grades") if g in grade_num]
        r["nutriscore_moyen"] = round(sum(vals) / len(vals), 2) if vals else None
        r["annee"] = r.pop("_id")
    return rows


ALL = {
    "Q1_sucre_par_nutriscore": sucre_par_nutriscore,
    "Q2_ultra_transforme_par_categorie": part_ultra_transforme_par_categorie,
    "Q3_additifs_les_plus_frequents": additifs_les_plus_frequents,
    "Q4_ajouts_par_annee": ajouts_par_annee,
}


if __name__ == "__main__":
    for name, fn in ALL.items():
        print(f"\n### {name}")
        for row in fn()[:8]:
            print("  ", row)
