"""Bonus IA : recherche semantique sur le catalogue (Atlas Vector Search).

Reprend la demarche du TP5 :
  1. vectoriser un champ porteur de sens : `name` + `ingredients_text`
  2. stocker l'embedding (384 dims) dans chaque produit
  3. creer un index de type vectorSearch sur Atlas
  4. requeter avec $vectorSearch (premiere etape du pipeline)

Necessite un cluster Atlas ET `pip install sentence-transformers` (~2 Go).
En local, seule l'etape 1-2 (calcul + stockage) fonctionne ; $vectorSearch
renverra une OperationFailure, comme au TP5.

    python -m src.vector_search embed          # calcule et stocke les vecteurs
    python -m src.vector_search index-def      # imprime la definition d'index Atlas
    python -m src.vector_search search "une pate a tartiner sans huile de palme"
"""
from __future__ import annotations

import sys

from .db import get_db

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
DIM = 384
INDEX_NAME = "idx_products_vec"

INDEX_DEFINITION = {
    "fields": [
        {"type": "vector", "path": "embedding", "numDimensions": DIM, "similarity": "cosine"},
        {"type": "filter", "path": "nutriscore_grade"},
        {"type": "filter", "path": "category_main"},
    ]
}


def _model():
    from sentence_transformers import SentenceTransformer
    return SentenceTransformer(MODEL_NAME)


def _text(p: dict) -> str:
    return " ".join(filter(None, [
        p.get("name"),
        " ".join(p.get("brands", [])),
        (p.get("category_main") or "").split(":")[-1].replace("-", " "),
        p.get("ingredients_text") or "",
    ]))[:1000]


def embed(batch_size: int = 256):
    db = get_db()
    model = _model()
    cur = db.products.find({"embedding": {"$exists": False}},
                           {"name": 1, "brands": 1, "category_main": 1, "ingredients_text": 1})
    buf = []
    done = 0
    for p in cur:
        buf.append(p)
        if len(buf) == batch_size:
            done += _flush(db, model, buf); buf.clear()
            print(f"  {done} produits vectorises")
    if buf:
        done += _flush(db, model, buf)
    print(f"termine : {done} produits.")


def _flush(db, model, docs):
    vecs = model.encode([_text(d) for d in docs], normalize_embeddings=True)
    from pymongo import UpdateOne
    db.products.bulk_write([
        UpdateOne({"_id": d["_id"]}, {"$set": {"embedding": v.tolist()}})
        for d, v in zip(docs, vecs)
    ], ordered=False)
    return len(docs)


def search(question: str, k: int = 5, only_grade: str | None = None):
    db = get_db()
    qv = _model().encode([question], normalize_embeddings=True)[0].tolist()
    vs = {
        "index": INDEX_NAME, "path": "embedding",
        "queryVector": qv, "numCandidates": 200, "limit": k,
    }
    if only_grade:
        vs["filter"] = {"nutriscore_grade": only_grade}
        vs["numCandidates"] = 500  # filtre => plus de candidats (cf. TP5)
    pipeline = [
        {"$vectorSearch": vs},
        {"$project": {"_id": 0, "name": 1, "brands": 1, "nutriscore_grade": 1,
                      "score": {"$meta": "vectorSearchScore"}}},
    ]
    try:
        for d in db.products.aggregate(pipeline):
            print(f"  {d['score']:.3f}  {d['name']}  [{d.get('nutriscore_grade')}]")
    except Exception as e:
        print("Non execute (cluster local ou index absent) :", type(e).__name__)
        print("Sur Atlas avec l'index", INDEX_NAME, ", ce pipeline renvoie les k plus proches.")


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else "index-def"
    if cmd == "embed":
        embed()
    elif cmd == "search":
        search(" ".join(sys.argv[2:]) or "un gouter pour enfant sans additifs")
    else:
        import json
        print(json.dumps(INDEX_DEFINITION, indent=2))
