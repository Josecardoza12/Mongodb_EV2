"""Reacciones y comentarios (escritura en tiempo real sobre Atlas)."""
import logging
from datetime import datetime

from fastapi import APIRouter, Path, Query

from .. import db
from ..errores import ErrorAPI, no_encontrado
from ..schemas import ComentarioCrear, ComentarioLikes, ReaccionCrear, TipoReaccion

router = APIRouter(tags=["Reacciones y comentarios"])
log = logging.getLogger("contentflow.api")


def _validar_referencias(usuario_id: str, publicacion_id: str):
    base = db.get_db()
    if not base.usuarios.find_one({"_id": usuario_id}, {"_id": 1}):
        raise ErrorAPI(404, f"El usuario '{usuario_id}' no existe")
    if not base.publicaciones.find_one({"_id": publicacion_id}, {"_id": 1}):
        raise ErrorAPI(404, f"La publicación '{publicacion_id}' no existe")


# ----------------------------------------------------------------- reacciones
@router.get("/reacciones", summary="Listar reacciones (por publicación, usuario o tipo)")
def listar_reacciones(publicacion_id: str | None = Query(None, pattern=r"^pub_\d+$"),
                      usuario_id: str | None = Query(None, pattern=r"^user_\d+$"),
                      tipo_reaccion: TipoReaccion | None = None,
                      limit: int = Query(50, ge=1, le=200)):
    filtro = {k: v for k, v in (("publicacion_id", publicacion_id), ("usuario_id", usuario_id),
                                ("tipo_reaccion", tipo_reaccion.value if tipo_reaccion else None)) if v}
    col = db.get_db().reacciones
    return {"total": col.count_documents(filtro),
            "items": list(col.find(filtro).sort("fecha", -1).limit(limit))}


@router.post("/reacciones", status_code=201, summary="Reaccionar a una publicación")
def crear_reaccion(datos: ReaccionCrear):
    _validar_referencias(datos.usuario_id, datos.publicacion_id)
    doc = {"_id": db.siguiente_id("reacciones"), **datos.model_dump(),
           "fecha": datetime.now().replace(microsecond=0)}
    # Si el usuario ya reaccionó a esa publicación, el índice único lanza DuplicateKeyError -> 409
    db.get_db().reacciones.insert_one(doc)
    log.info("Reacción %s: %s -> %s (%s)", doc["_id"], datos.usuario_id, datos.publicacion_id,
             datos.tipo_reaccion)
    return doc


@router.delete("/reacciones/{reaccion_id}", summary="Quitar una reacción")
def eliminar_reaccion(reaccion_id: str = Path(pattern=r"^react_\d+$")):
    if db.get_db().reacciones.delete_one({"_id": reaccion_id}).deleted_count == 0:
        raise no_encontrado("Reacción", reaccion_id)
    log.info("Reacción %s eliminada", reaccion_id)
    return {"mensaje": f"Reacción {reaccion_id} eliminada"}


# ----------------------------------------------------------------- comentarios
@router.get("/comentarios", summary="Listar comentarios (por publicación o usuario, mínimo de likes)")
def listar_comentarios(publicacion_id: str | None = Query(None, pattern=r"^pub_\d+$"),
                       usuario_id: str | None = Query(None, pattern=r"^user_\d+$"),
                       min_likes: int = Query(0, ge=0),
                       limit: int = Query(50, ge=1, le=200)):
    filtro: dict = {"likes": {"$gte": min_likes}}
    if publicacion_id:
        filtro["publicacion_id"] = publicacion_id
    if usuario_id:
        filtro["usuario_id"] = usuario_id
    col = db.get_db().comentarios
    return {"total": col.count_documents(filtro),
            "items": list(col.find(filtro).sort([("likes", -1), ("fecha", -1)]).limit(limit))}


@router.post("/comentarios", status_code=201, summary="Comentar una publicación")
def crear_comentario(datos: ComentarioCrear):
    _validar_referencias(datos.usuario_id, datos.publicacion_id)
    doc = {"_id": db.siguiente_id("comentarios"), **datos.model_dump(),
           "fecha": datetime.now().replace(microsecond=0), "likes": 0}
    db.get_db().comentarios.insert_one(doc)
    log.info("Comentario %s en %s por %s", doc["_id"], datos.publicacion_id, datos.usuario_id)
    return doc


@router.patch("/comentarios/{comentario_id}/likes", summary="Sumar likes a un comentario ($inc atómico)")
def sumar_likes(datos: ComentarioLikes, comentario_id: str = Path(pattern=r"^comm_\d+$")):
    base = db.get_db()
    r = base.comentarios.update_one({"_id": comentario_id}, {"$inc": {"likes": datos.incremento}})
    if r.matched_count == 0:
        raise no_encontrado("Comentario", comentario_id)
    return base.comentarios.find_one({"_id": comentario_id})


@router.delete("/comentarios/{comentario_id}", summary="Eliminar comentario")
def eliminar_comentario(comentario_id: str = Path(pattern=r"^comm_\d+$")):
    if db.get_db().comentarios.delete_one({"_id": comentario_id}).deleted_count == 0:
        raise no_encontrado("Comentario", comentario_id)
    log.info("Comentario %s eliminado", comentario_id)
    return {"mensaje": f"Comentario {comentario_id} eliminado"}
