"""
API REST ContentFlow - FastAPI + MongoDB Atlas (pymongo).

Ejecutar desde la raíz del repo:
    uvicorn api.main:app --reload --port 8000
Documentación interactiva (Swagger): http://localhost:8000/docs
Logs: consola + logs/api.log
"""
import logging
import time
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path

from fastapi import FastAPI, Request

from . import db
from .errores import registrar_manejadores
from .rutas import interacciones, publicaciones, reportes, usuarios
from .schemas import SaludAPI

# ---------------------------------------------------------------- logs
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
formato = logging.Formatter("%(asctime)s | %(levelname)-7s | %(name)s | %(message)s")
archivo = RotatingFileHandler(LOG_DIR / "api.log", maxBytes=1_000_000, backupCount=3, encoding="utf-8")
archivo.setFormatter(formato)
consola = logging.StreamHandler()
consola.setFormatter(formato)
raiz = logging.getLogger("contentflow")
raiz.setLevel(logging.INFO)
raiz.handlers = [archivo, consola]
log = logging.getLogger("contentflow.api")


# ---------------------------------------------------------------- ciclo de vida
@asynccontextmanager
async def lifespan(app: FastAPI):
    for intento in range(1, 4):  # 3 intentos de conexión al iniciar
        try:
            db.conectar()
            break
        except Exception as e:  # noqa: BLE001
            log.error("Intento %s/3 de conexión a MongoDB falló: %s", intento, e)
            time.sleep(2)
    else:
        log.critical("No fue posible conectar con MongoDB. La API responderá 503 hasta que vuelva.")
    yield
    db.cerrar()


app = FastAPI(
    title="ContentFlow API",
    description="API REST sobre MongoDB Atlas: usuarios, publicaciones, reacciones, comentarios y reportes.",
    version="1.0.0",
    lifespan=lifespan,
)
registrar_manejadores(app)


# ---------------------------------------------------------------- trazabilidad
@app.middleware("http")
async def trazabilidad(request: Request, call_next):
    """Asigna un request_id a cada petición y registra método, ruta, estado y duración."""
    request.state.request_id = request.headers.get("X-Request-ID", uuid.uuid4().hex[:12])
    inicio = time.perf_counter()
    respuesta = await call_next(request)
    ms = (time.perf_counter() - inicio) * 1000
    respuesta.headers["X-Request-ID"] = request.state.request_id
    respuesta.headers["X-Response-Time-ms"] = f"{ms:.1f}"
    nivel = logging.WARNING if respuesta.status_code >= 400 else logging.INFO
    log.log(nivel, "rid=%s %s %s -> %s (%.1f ms) ip=%s", request.state.request_id, request.method,
            request.url.path, respuesta.status_code, ms, request.client.host if request.client else "-")
    return respuesta


# ---------------------------------------------------------------- rutas
@app.get("/health", response_model=SaludAPI, tags=["Sistema"], summary="Prueba de conectividad con Atlas")
def health():
    t0 = time.perf_counter()
    db.get_client().admin.command("ping")
    return SaludAPI(estado="ok", base_datos=db.MONGO_DB, latencia_ms=round((time.perf_counter() - t0) * 1000, 1),
                    fecha=datetime.now())


app.include_router(usuarios.router)
app.include_router(publicaciones.router)
app.include_router(interacciones.router)
app.include_router(reportes.router)
