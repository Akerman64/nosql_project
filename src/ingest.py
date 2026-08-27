"""Etape 1 du projet : constituer la base a partir de donnees reelles Open Food Facts.

On ne telecharge pas le dump complet (~3 M de produits, plusieurs Go). On interroge
l'API publique v2 par tranches de categories, pour un sous-ensemble francais
exploitable (>= 10 000 produits), puis on transforme chaque produit brut vers notre
modele et on charge trois collections :

    products    (racine : un produit = un code-barres)
    categories  (referentiel taxonomie, derive des produits)
    additives   (referentiel additifs, derive des produits)

Usage :
    python -m src.ingest              # ingestion complete
    python -m src.ingest --limit 3000 # version courte pour un test
"""
from __future__ import annotations

import argparse
import sys
import time
from datetime import datetime, timezone

import requests
from pymongo import ASCENDING, UpdateOne

from .db import get_db, target

API = "https://world.openfoodfacts.org/api/v2/search"
UA = {"User-Agent": "MIA4-27.2-projet-etudiant/1.0 (cours NoSQL IPSSI)"}

FIELDS = ",".join([
    "code", "product_name", "product_name_fr", "brands_tags", "quantity",
    "countries_tags", "categories_tags", "labels_tags",
    "additives_tags", "additives_original_tags",
    "ingredients_text_fr", "ingredients_text", "ingredients", "ingredients_n",
    "nutriments", "nutriscore_grade", "nova_group", "ecoscore_grade",
    "images", "created_t", "last_modified_t", "completeness", "unique_scans_n",
])

# Tranches de categories (valeurs de categories_tags_en). Le recouvrement entre
# tranches est volontaire : on dedoublonne sur le code-barres a l'ecriture.
CATEGORIES = [
    "Breakfasts", "Spreads", "Biscuits", "Chocolates", "Breakfast cereals",
    "Dairies", "Cheeses", "Yogurts", "Milks", "Plant-based foods",
    "Beverages", "Waters", "Sodas", "Fruit juices", "Teas",
    "Snacks", "Sweet snacks", "Salty snacks", "Crisps", "Candies",
    "Meats", "Poultries", "Prepared meats", "Fishes", "Seafood",
    "Frozen foods", "Pizzas", "Ready-made meals", "Soups", "Sauces",
    "Pastas", "Rices", "Legumes", "Breads", "Viennoiseries",
    "Cakes", "Ice creams", "Desserts", "Jams", "Honeys",
    "Condiments", "Vegetables", "Fruits", "Nuts", "Cereals and potatoes",
    "Olive oils", "Vinegars", "Baby foods", "Meat analogues", "Coffees",
]

PAGES_PER_CATEGORY = 15   # 15 * 100 = 1500 produits max par tranche
PAGE_SIZE = 100
PAUSE = 0.5               # politesse envers l'API publique


def epoch_to_dt(v):
    try:
        return datetime.fromtimestamp(int(v), tz=timezone.utc)
    except (TypeError, ValueError, OSError):
        return None


def to_float(v):
    try:
        f = float(v)
        return f if f == f else None  # rejette NaN
    except (TypeError, ValueError):
        return None


NUTRIMENT_KEYS = {
    "energy-kcal_100g": "energy_kcal_100g",
    "fat_100g": "fat_100g",
    "saturated-fat_100g": "saturated_fat_100g",
    "carbohydrates_100g": "carbohydrates_100g",
    "sugars_100g": "sugars_100g",
    "fiber_100g": "fiber_100g",
    "proteins_100g": "proteins_100g",
    "salt_100g": "salt_100g",
    "sodium_100g": "sodium_100g",
}


def clean_tags(v):
    if not v:
        return []
    if isinstance(v, str):
        v = [t.strip() for t in v.split(",")]
    return sorted({t.strip().lower() for t in v if t and t.strip()})


def transform(raw: dict) -> dict | None:
    """Produit brut de l'API -> document de notre modele. None si inexploitable."""
    code = (raw.get("code") or "").strip()
    name = (raw.get("product_name_fr") or raw.get("product_name") or "").strip()
    if not code or not name:
        return None  # sans identifiant ou sans nom, le document n'a aucune valeur

    cats = clean_tags(raw.get("categories_tags"))
    additives = clean_tags(raw.get("additives_tags"))

    nutr_raw = raw.get("nutriments") or {}
    nutriments = {}
    for src_key, dst_key in NUTRIMENT_KEYS.items():
        val = to_float(nutr_raw.get(src_key))
        if val is not None:
            nutriments[dst_key] = val

    ingredients = []
    for ing in (raw.get("ingredients") or [])[:60]:  # borne de securite
        if not isinstance(ing, dict):
            continue
        ingredients.append({
            "id": ing.get("id"),
            "text": ing.get("text"),
            "percent_estimate": to_float(ing.get("percent_estimate")),
            "vegan": ing.get("vegan"),
            "vegetarian": ing.get("vegetarian"),
        })

    nova = raw.get("nova_group")
    try:
        nova = int(nova)
    except (TypeError, ValueError):
        nova = None

    return {
        "_id": code,
        "name": name,
        "brands": clean_tags(raw.get("brands_tags")),
        "quantity": (raw.get("quantity") or "").strip() or None,
        "countries": clean_tags(raw.get("countries_tags")),
        "categories_tags": cats,                      # hierarchie aplatie (tous les ancetres)
        "category_main": cats[-1] if cats else None,  # la feuille : plus specifique
        "labels": clean_tags(raw.get("labels_tags")),
        "additives": additives,
        "additives_n": len(additives),
        "ingredients_text": (raw.get("ingredients_text_fr")
                             or raw.get("ingredients_text") or "").strip() or None,
        "ingredients": ingredients,
        "ingredients_n": raw.get("ingredients_n") or len(ingredients) or None,
        "nutriments": nutriments,
        "nutriscore_grade": (raw.get("nutriscore_grade") or "").lower() or None,
        "nova_group": nova,
        "ecoscore_grade": (raw.get("ecoscore_grade") or "").lower() or None,
        "images_n": len(raw.get("images") or {}),
        "unique_scans_n": raw.get("unique_scans_n") or 0,
        "completeness": to_float(raw.get("completeness")),
        "created_t": epoch_to_dt(raw.get("created_t")),
        "last_modified_t": epoch_to_dt(raw.get("last_modified_t")),
        "source": "openfoodfacts-api-v2",
        "ingested_at": datetime.now(timezone.utc),
    }


def fetch_category(cat: str):
    out = []
    for page in range(1, PAGES_PER_CATEGORY + 1):
        params = {
            "categories_tags_en": cat,
            "countries_tags_en": "France",
            "page_size": PAGE_SIZE,
            "page": page,
            "fields": FIELDS,
            # pas de sort_by : l'ordre naturel donne plus de diversite entre
            # tranches (trier par popularite ramene les memes produits partout).
        }
        for attempt in range(3):
            try:
                r = requests.get(API, params=params, headers=UA, timeout=30)
                if r.status_code != 200 or "application/json" not in r.headers.get("content-type", ""):
                    raise ValueError(f"HTTP {r.status_code}")
                prods = r.json().get("products", [])
                break
            except (requests.RequestException, ValueError) as e:
                if attempt == 2:
                    print(f"    ! {cat} p{page} abandonnee ({e})")
                    prods = []
                else:
                    time.sleep(2 * (attempt + 1))
        if not prods:
            break
        out.extend(prods)
        time.sleep(PAUSE)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=0,
                    help="arrete des que ce nombre de produits distincts est atteint")
    ap.add_argument("--keep", action="store_true",
                    help="ne pas vider `products` au demarrage (reprise / complement)")
    args = ap.parse_args()

    db = get_db()
    print(f"Cible : {target()}  base : {db.name}")
    if not args.keep:
        db.products.drop()
    db.products.create_index([("_id", ASCENDING)])

    for i, cat in enumerate(CATEGORIES, 1):
        got = fetch_category(cat)
        ops = []
        for raw in got:
            doc = transform(raw)
            if doc:
                _id = doc.pop("_id")
                ops.append(UpdateOne({"_id": _id}, {"$setOnInsert": doc}, upsert=True))
        upserted = 0
        if ops:
            res = db.products.bulk_write(ops, ordered=False)
            upserted = res.upserted_count
        total = db.products.count_documents({})
        print(f"[{i:2d}/{len(CATEGORIES)}] {cat:<22} +{upserted:4d} nouveaux "
              f"(total {total})", flush=True)
        if args.limit and total >= args.limit:
            print("  limite atteinte, arret de la collecte.")
            break

    build_referentials(db)
    total = db.products.count_documents({})
    if total < 10_000:
        print(f"\n!! Seulement {total} produits (< 10 000). L'API OFF a limite la "
              f"profondeur. Relancez `python -m src.ingest --keep` quand elle est saine.")
    print("\nIngestion terminee.")


def build_referentials(db):
    """Reconstruit `categories` et `additives` a partir de `products` en base."""
    print("\nReconstruction des referentiels...")
    db.categories.drop()
    db.additives.drop()
    products = db.products.find({}, {"categories_tags": 1, "additives": 1})

    cat_parents: dict[str, set] = {}
    cat_count: dict[str, int] = {}
    add_count: dict[str, int] = {}
    for p in products:
        tags = p.get("categories_tags", [])
        for pos, t in enumerate(tags):
            cat_count[t] = cat_count.get(t, 0) + 1
            cat_parents.setdefault(t, set())
            if pos > 0:
                cat_parents[t].add(tags[pos - 1])
        for a in p.get("additives", []):
            add_count[a] = add_count.get(a, 0) + 1
    cat_docs = [
        {
            "_id": t,
            "name": t.split(":", 1)[-1].replace("-", " ").capitalize(),
            "parents": sorted(cat_parents[t]),
            "products_count": cat_count[t],
        }
        for t in cat_count
    ]
    if cat_docs:
        db.categories.insert_many(cat_docs, ordered=False)
    print(f"  categories   : {db.categories.count_documents({})}")

    add_docs = [
        {"_id": a, "code": a.split(":", 1)[-1].upper(),
         "name": a.split(":", 1)[-1].upper(), "products_count": n}
        for a, n in add_count.items()
    ]
    if add_docs:
        db.additives.insert_many(add_docs, ordered=False)
    print(f"  additives    : {db.additives.count_documents({})}")


if __name__ == "__main__":
    sys.exit(main())
