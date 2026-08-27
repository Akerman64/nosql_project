"""Connexion MongoDB - un seul point d'entree pour tout le projet.

La chaine de connexion vient EXCLUSIVEMENT du fichier d'environnement `.env.local`
(non versionne). Jamais d'identifiant en clair dans le code.

Ordre de resolution de l'URI :
  1. ATLAS_URI   -> le cluster de production (rendu)
  2. LOCAL_URI   -> instance locale (developpement)
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.database import Database

_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(dotenv_path=os.getenv("ENV_FILE", str(_ROOT / ".env.local")), override=False)

DB_NAME = os.getenv("DB_NAME", "off_projet")


@lru_cache(maxsize=1)
def get_client() -> MongoClient:
    uri = os.getenv("ATLAS_URI") or os.getenv("LOCAL_URI")
    if not uri:
        raise RuntimeError(
            "Aucune URI. Renseignez ATLAS_URI ou LOCAL_URI dans .env.local "
            "(voir .env.example)."
        )
    client = MongoClient(uri, serverSelectionTimeoutMS=5000, appname="projet_off")
    client.admin.command("ping")  # echoue tot et clairement si injoignable
    return client


def get_db() -> Database:
    return get_client()[DB_NAME]


def target() -> str:
    """Pour les logs : dit sur quoi on travaille sans divulguer le mot de passe."""
    return "ATLAS" if os.getenv("ATLAS_URI") else "LOCAL"
