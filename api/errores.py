"""Errores HTTP de negocio + manejadores globales (traducen errores de MongoDB a códigos HTTP)."""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pymongo.errors import (AutoReconnect, ConnectionFailure, DuplicateKeyError, PyMongoError,
                            ServerSelectionTimeoutError, WriteError)

log = logging.getLogger("contentflow.api")


class ErrorAPI(Exception):
    def __init__(self, codigo: int, mensaje: str, detalle=None):
        self.codigo, self.mensaje, self.detalle = codigo, mensaje, detalle


def no_encontrado(recurso: str, id_: str) -> ErrorAPI:
    return ErrorAPI(404, f"{recurso} '{id_}' no existe")


def _respuesta(request: Request, codigo: int, mensaje: str, detalle=None) -> JSONResponse:
    return JSONResponse(status_code=codigo, content={"error": {
        "codigo": codigo, "mensaje": mensaje, "detalle": detalle,
        "request_id": getattr(request.state, "request_id", None),
        "ruta": f"{request.method} {request.url.path}"}})


def registrar_manejadores(app: FastAPI):
    @app.exception_handler(ErrorAPI)
    async def _api(request: Request, e: ErrorAPI):
        log.warning("rid=%s %s -> %s", request.state.request_id, e.codigo, e.mensaje)
        return _respuesta(request, e.codigo, e.mensaje, e.detalle)

    @app.exception_handler(RequestValidationError)
    async def _validacion(request: Request, e: RequestValidationError):
        errores = [{"campo": ".".join(str(x) for x in err["loc"][1:]), "problema": err["msg"]}
                   for err in e.errors()]
        log.warning("rid=%s 422 entrada inválida: %s", request.state.request_id, errores)
        return _respuesta(request, 422, "Datos de entrada inválidos", errores)

    @app.exception_handler(DuplicateKeyError)
    async def _duplicado(request: Request, e: DuplicateKeyError):
        campos = list((e.details or {}).get("keyValue", {}).keys())
        log.warning("rid=%s 409 duplicado %s", request.state.request_id, campos)
        return _respuesta(request, 409, "Ya existe un registro con esos datos", {"campos": campos})

    @app.exception_handler(WriteError)
    async def _escritura(request: Request, e: WriteError):
        # code 121 = el validador $jsonSchema de la colección rechazó el documento
        codigo = 422 if e.code == 121 else 400
        log.warning("rid=%s %s WriteError code=%s", request.state.request_id, codigo, e.code)
        return _respuesta(request, codigo, "MongoDB rechazó el documento", {"mongo_code": e.code})

    @app.exception_handler(ServerSelectionTimeoutError)
    @app.exception_handler(ConnectionFailure)
    @app.exception_handler(AutoReconnect)
    async def _sin_conexion(request: Request, e: Exception):
        log.error("rid=%s 503 sin conexión a MongoDB: %s", request.state.request_id, e)
        return _respuesta(request, 503, "Base de datos no disponible, intente nuevamente")

    @app.exception_handler(PyMongoError)
    async def _mongo(request: Request, e: PyMongoError):
        log.exception("rid=%s 500 error MongoDB", request.state.request_id)
        return _respuesta(request, 500, "Error interno de base de datos")

    @app.exception_handler(Exception)
    async def _general(request: Request, e: Exception):
        log.exception("rid=%s 500 error no controlado", request.state.request_id)
        return _respuesta(request, 500, "Error interno del servidor")
