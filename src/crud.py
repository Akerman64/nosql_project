"""Etape 3 : CRUD Python sur `products`, avec gestion d'erreurs reelle.

- Connexion via src.db (jamais d'identifiant en clair).
- Chaque operation renvoie un resultat type (`OpResult`) plutot que de laisser
  filer une exception PyMongo brute vers l'appelant.
- `delete` et `update` refusent un filtre vide : pas de modification de masse
  accidentelle.

Demo :
    python -m src.crud
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from pymongo.errors import (
    ConnectionFailure,
    DuplicateKeyError,
    OperationFailure,
    PyMongoError,
    WriteError,
)

from .db import get_db


@dataclass
class OpResult:
    ok: bool
    data: Any = None
    error: str | None = None

    def __bool__(self) -> bool:
        return self.ok


def _col():
    return get_db().products


def _guard(filt: dict):
    if not filt:
        raise ValueError("filtre vide interdit pour cette operation")


# --------------------------------------------------------------------------- CREATE
def create_product(doc: dict) -> OpResult:
    if not doc.get("_id") or not doc.get("name"):
        return OpResult(False, error="`_id` (code-barres) et `name` obligatoires")
    doc.setdefault("source", "crud-manuel")
    doc.setdefault("categories_tags", [])
    doc.setdefault("nutriments", {})
    doc["ingested_at"] = datetime.now(timezone.utc)
    try:
        _col().insert_one(doc)
        return OpResult(True, data=doc["_id"])
    except DuplicateKeyError:
        return OpResult(False, error=f"le produit {doc['_id']} existe deja")
    except (WriteError, OperationFailure) as e:
        return OpResult(False, error=f"document rejete par le validateur : {e}")
    except (ConnectionFailure, PyMongoError) as e:
        return OpResult(False, error=f"erreur base : {e}")


# ----------------------------------------------------------------------------- READ
def get_product(code: str) -> OpResult:
    try:
        doc = _col().find_one({"_id": code})
        return OpResult(doc is not None, data=doc,
                        error=None if doc else "introuvable")
    except (ConnectionFailure, PyMongoError) as e:
        return OpResult(False, error=f"erreur base : {e}")


def find_products(filt: dict, projection: dict | None = None,
                  limit: int = 20, sort: list | None = None) -> OpResult:
    try:
        cur = _col().find(filt, projection).limit(limit)
        if sort:
            cur = cur.sort(sort)
        return OpResult(True, data=list(cur))
    except (OperationFailure, ConnectionFailure, PyMongoError) as e:
        return OpResult(False, error=f"erreur base : {e}")


# --------------------------------------------------------------------------- UPDATE
def update_product(code: str, changes: dict) -> OpResult:
    """MAJ ciblee par `_id` avec $set : on ne remplace jamais le document entier
    (sinon on perd les champs non transmis)."""
    if not changes:
        return OpResult(False, error="aucun changement fourni")
    try:
        res = _col().update_one(
            {"_id": code},
            {"$set": {**changes, "last_modified_local": datetime.now(timezone.utc)}},
        )
        if res.matched_count == 0:
            return OpResult(False, error=f"aucun produit {code}")
        return OpResult(True, data={"modified": res.modified_count})
    except (WriteError, OperationFailure) as e:
        return OpResult(False, error=f"changement rejete par le validateur : {e}")
    except (ConnectionFailure, PyMongoError) as e:
        return OpResult(False, error=f"erreur base : {e}")


# --------------------------------------------------------------------------- DELETE
def delete_product(code: str) -> OpResult:
    try:
        if not code:
            raise ValueError("code vide : suppression refusee")
        _guard({"_id": code})
        res = _col().delete_one({"_id": code})
        return OpResult(res.deleted_count == 1,
                        data={"deleted": res.deleted_count},
                        error=None if res.deleted_count else "rien a supprimer")
    except ValueError as e:
        return OpResult(False, error=str(e))
    except (ConnectionFailure, PyMongoError) as e:
        return OpResult(False, error=f"erreur base : {e}")


# ------------------------------------------------------------------------------ DEMO
def _demo():
    code = "0000000000000"
    print("CREATE ", create_product({
        "_id": code, "name": "Produit de test CRUD",
        "brands": ["marque-test"], "categories_tags": ["en:snacks"],
        "nutriments": {"sugars_100g": 12.0}, "nutriscore_grade": "c",
    }))
    print("CREATE2", create_product({"_id": code, "name": "doublon"}))  # DuplicateKeyError
    print("READ   ", get_product(code).data and get_product(code).data["name"])
    print("UPDATE ", update_product(code, {"nutriscore_grade": "d"}))
    # validateur en mode 'warn' : la valeur hors bornes est tracee cote serveur, pas bloquee
    print("UPDATE?", update_product(code, {"nova_group": 99}), "(warn, non bloquant - cf. model.py)")
    print("FIND   ", len(find_products({"categories_tags": "en:snacks"}, limit=5).data), "resultats")
    print("DELETE ", delete_product(code))
    print("DELETE0", delete_product(""))  # code vide -> refuse avant toute requete


if __name__ == "__main__":
    _demo()
