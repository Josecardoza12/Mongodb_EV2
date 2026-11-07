"""
Configuración compartida por todos los scripts.

Lee MONGO_URI y MONGO_DB desde el archivo .env (en la raíz del repo).
Nunca subas el .env a GitHub: ya está en .gitignore.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from pymongo import MongoClient
from pymongo.errors import ConfigurationError, ServerSelectionTimeoutError

RAIZ = Path(__file__).resolve().parent.parent
DATA_DIR = RAIZ / "data"
EVIDENCIAS_DIR = RAIZ / "evidencias"
EVIDENCIAS_DIR.mkdir(exist_ok=True)

load_dotenv(RAIZ / ".env")

MONGO_URI = os.getenv("MONGO_URI")
MONGO_DB = os.getenv("MONGO_DB", "contentflow")

COLECCIONES = ["usuarios", "publicaciones", "reacciones", "comentarios", "campanas"]


def get_client(timeout_ms: int = 8000) -> MongoClient:
    if not MONGO_URI:
        sys.exit("ERROR: falta MONGO_URI en el archivo .env (copia .env.example a .env y complétalo)")
    try:
        client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=timeout_ms, appname="contentflow-scripts")
        client.admin.command("ping")
        return client
    except ServerSelectionTimeoutError as e:
        sys.exit(
            "ERROR: no se pudo conectar a MongoDB.\n"
            "  - ¿Agregaste tu IP en Atlas > Network Access?\n"
            "  - ¿El usuario y contraseña del URI son correctos?\n"
            f"  Detalle: {e}"
        )
    except ConfigurationError as e:
        sys.exit(f"ERROR: el MONGO_URI tiene un formato inválido: {e}")


def get_db():
    return get_client()[MONGO_DB]


def titulo(texto: str):
    print("\n" + "=" * 70)
    print(texto)
    print("=" * 70)
