"""Petits utilitaires pour la vidéo de soutenance. Tout passe par src.db
(donc par Atlas si ATLAS_URI est dans .env.local).

    python demo/show.py collections   # les 3 collections + comptes (segment 2)
    python demo/show.py fiche         # une fiche produit lisible (segment 1)
    python demo/show.py casser        # abime la base pour la demo (segment 5)
    python demo/show.py etat          # etat de la base : cassee ou reparee (segment 5)
"""
import json
import sys

sys.path.insert(0, ".")
from src.db import get_db, target  # noqa: E402

CASSE_ID = "3017620422003"   # Nutella
FAUX_ID = "FAUX-PRODUIT-DEMO"


def collections():
    db = get_db()
    print(f"base : {target()} / {db.name}\n")
    for c in ("products", "categories", "additives"):
        print(f"  {c:12} {db[c].count_documents({}):>7} documents")


def fiche():
    db = get_db()
    d = db.products.find_one({
        "nutriscore_grade": "e",
        "additives.0": {"$exists": True},
        "ingredients.2": {"$exists": True},
    })
    print(json.dumps(d, ensure_ascii=False, indent=2, default=str))


def casser():
    db = get_db()
    db.products.update_one({"_id": CASSE_ID},
                           {"$set": {"name": "TITRE CASSE PENDANT LA DEMO"}})
    db.products.update_one(
        {"_id": FAUX_ID},
        {"$set": {"name": "produit ajoute apres la sauvegarde",
                  "categories_tags": [], "nutriments": {}, "source": "demo"}},
        upsert=True,
    )
    etat()


def etat():
    db = get_db()
    prod = db.products.find_one({"_id": CASSE_ID}) or {}
    faux = db.products.find_one({"_id": FAUX_ID}) is not None
    print(f"nombre de produits   : {db.products.count_documents({})}")
    print(f"produit {CASSE_ID} : {prod.get('name')}")
    print(f"faux produit present : {faux}")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "collections"
    {"collections": collections, "fiche": fiche,
     "casser": casser, "etat": etat}.get(cmd, collections)()
