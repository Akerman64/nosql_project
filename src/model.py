"""Etape 2 : la modelisation, rendue executable.

On applique un validateur JSON Schema *souple* sur `products` : il verrouille les
champs sur lesquels reposent les requetes et les agregations (identifiant, nom,
tableaux de tags, sous-document nutriments, dimension temporelle) et laisse le
reste libre. Choix assume : les donnees Open Food Facts sont incompletes par
nature ; un schema strict rejetterait des produits reels qu'on veut analyser.

    python -m src.model            # (re)pose le validateur
    python -m src.model --show     # affiche le validateur en place
"""
from __future__ import annotations

import argparse
import json

from .db import get_db

PRODUCT_VALIDATOR = {
    "$jsonSchema": {
        "bsonType": "object",
        "required": ["_id", "name", "categories_tags", "nutriments", "source"],
        "properties": {
            "_id": {"bsonType": "string", "description": "code-barres EAN"},
            "name": {"bsonType": "string", "minLength": 1},
            "brands": {"bsonType": "array", "items": {"bsonType": "string"}},
            "countries": {"bsonType": "array", "items": {"bsonType": "string"}},
            "categories_tags": {"bsonType": "array", "items": {"bsonType": "string"}},
            "category_main": {"bsonType": ["string", "null"]},
            "additives": {"bsonType": "array", "items": {"bsonType": "string"}},
            "nutriments": {
                "bsonType": "object",
                "description": "sous-document embarque, valeurs pour 100 g",
                "properties": {
                    "energy_kcal_100g": {"bsonType": ["double", "int"]},
                    "sugars_100g": {"bsonType": ["double", "int"]},
                    "salt_100g": {"bsonType": ["double", "int"]},
                    "proteins_100g": {"bsonType": ["double", "int"]},
                },
            },
            "ingredients": {"bsonType": "array"},
            "nutriscore_grade": {"enum": ["a", "b", "c", "d", "e", "unknown", None]},
            "nova_group": {"bsonType": ["int", "null"], "minimum": 1, "maximum": 4},
            "created_t": {"bsonType": ["date", "null"]},
            "last_modified_t": {"bsonType": ["date", "null"]},
        },
    }
}

COLLECTIONS = ("products", "categories", "additives")


def apply_model(verbose: bool = True):
    db = get_db()
    existing = set(db.list_collection_names())

    if "products" in existing:
        db.command("collMod", "products", validator=PRODUCT_VALIDATOR,
                   validationLevel="moderate", validationAction="warn")
        # 'warn' : on trace les documents non conformes sans bloquer l'ingestion.
    else:
        db.create_collection("products", validator=PRODUCT_VALIDATOR,
                             validationLevel="moderate", validationAction="warn")

    for name in ("categories", "additives"):
        if name not in existing:
            db.create_collection(name)

    if verbose:
        print("Validateur applique sur `products` (moderate / warn).")
        for name in COLLECTIONS:
            print(f"  {name:<12} {db[name].count_documents({}):>7} documents")


def show():
    db = get_db()
    opts = db.command("listCollections", filter={"name": "products"})
    validator = opts["cursor"]["firstBatch"][0].get("options", {}).get("validator")
    print(json.dumps(validator, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--show", action="store_true")
    a = ap.parse_args()
    show() if a.show else apply_model()
