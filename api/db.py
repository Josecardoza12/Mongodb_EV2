"""Conexión a MongoDB Atlas para la API (una sola instancia de MongoClient)."""
import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient, ReturnDocument

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

log = logging.getLogger("contentflow.db")

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "contentflow")

_client: MongoClient | None = None


def conectar() -> MongoClient:
    global _client
    if not MONGO_URI:
        raise RuntimeError("Falta MONGO_URI en .env")
    _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000, connectTimeoutMS=5000,
                          appname="contentflow-api")
    _client.admin.command("ping")
    log.info("Conectado a MongoDB (base=%s)", MONGO_DB)
    return _client


def cerrar():
    if _client:
        _client.close()
        log.info("Conexión a MongoDB cerrada")


def get_client() -> MongoClient:
    if _client is None:
        return conectar()
    return _client


def get_db():
    return get_client()[MONGO_DB]


# Prefijo de id por colección (los datos originales usan user_1, pub_1, ...)
PREFIJOS = {"usuarios": "user", "publicaciones": "pub", "reacciones": "react", "comentarios": "comm",
            "campanas": "camp"}


def siguiente_id(coleccion: str) -> str:
    """Id correlativo atómico usando la colección 'contadores' (seguro con varias peticiones a la vez)."""
    db = get_db()
    prefijo = PREFIJOS[coleccion]
    if db.contadores.count_documents({"_id": coleccion}) == 0:
        # Inicializa el contador con el mayor número existente
        mayor = 0
        for d in db[coleccion].find({"_id": {"$regex": f"^{prefijo}_\\d+$"}}, {"_id": 1}):
            mayor = max(mayor, int(d["_id"].split("_")[1]))
        db.contadores.update_one({"_id": coleccion}, {"$max": {"valor": mayor}}, upsert=True)
    doc = db.contadores.find_one_and_update({"_id": coleccion}, {"$inc": {"valor": 1}},
                                            return_document=ReturnDocument.AFTER, upsert=True)
    return f"{prefijo}_{doc['valor']}"
