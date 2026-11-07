"""CRUD de publicaciones."""
import logging
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Path, Query

from .. import db
from ..errores import ErrorAPI, no_encontrado
from ..schemas import Categoria, PublicacionActualizar, PublicacionCrear, TipoPublicacion

router = APIRouter(prefix="/publicaciones", tags=["Publicaciones"])
log = logging.getLogger("contentflow.api")
ID_PUB = Path(pattern=r"^pub_\d+$", examples=["pub_1"])


@router.get("", summary="Listar publicaciones (filtros, rango de fechas, orden y paginación)")
def listar(categoria: Categoria | None = None, tipo: TipoPublicacion | None = None,
           hashtag: str | None = Query(None, pattern=r"^#\w+$", examples=["#innovacion"]),
           usuario_id: str | None = Query(None, pattern=r"^user_\d+$"),
           desde: datetime | None = None, hasta: datetime | None = None,
           orden: Literal["fecha_desc", "fecha_asc"] = "fecha_desc",
           limit: int = Query(20, ge=1, le=100), skip: int = Query(0, ge=0)):
    if desde and hasta and desde > hasta:
        raise ErrorAPI(400, "'desde' no puede ser mayor que 'hasta'")
    filtro: dict = {}
    if categoria:
        filtro["categoria"] = categoria.value
    if tipo:
        filtro["tipo"] = tipo.value
    if hashtag:
        filtro["hashtags"] = hashtag.lower()
    if usuario_id:
        filtro["usuario_id"] = usuario_id
    if desde or hasta:
        filtro["fecha_publicacion"] = {k: v for k, v in (("$gte", desde), ("$lte", hasta)) if v}
    col = db.get_db().publicaciones
    items = list(col.find(filtro).sort("fecha_publicacion", -1 if orden == "fecha_desc" else 1)
                 .skip(skip).limit(limit))
    return {"total": col.count_documents(filtro), "limit": limit, "skip": skip, "items": items}


@router.get("/{publicacion_id}", summary="Detalle de publicación con sus reacciones y comentarios")
def obtener(publicacion_id: str = ID_PUB):
    r = list(db.get_db().publicaciones.aggregate([
        {"$match": {"_id": publicacion_id}},
        {"$lookup": {"from": "usuarios", "localField": "usuario_id", "foreignField": "_id",
                     "pipeline": [{"$project": {"nombre": 1, "pais": 1}}], "as": "autor"}},
        {"$lookup": {"from": "reacciones", "localField": "_id", "foreignField": "publicacion_id",
                     "pipeline": [{"$group": {"_id": "$tipo_reaccion", "total": {"$sum": 1}}}],
                     "as": "reacciones_por_tipo"}},
        {"$lookup": {"from": "comentarios", "localField": "_id", "foreignField": "publicacion_id",
                     "pipeline": [{"$sort": {"fecha": -1}}, {"$project": {"publicacion_id": 0}}],
                     "as": "comentarios"}},
        {"$set": {"autor": {"$first": "$autor"}}},
    ]))
    if not r:
        raise no_encontrado("Publicación", publicacion_id)
    return r[0]


@router.post("", status_code=201, summary="Crear publicación")
def crear(datos: PublicacionCrear):
    base = db.get_db()
    if not base.usuarios.find_one({"_id": datos.usuario_id}, {"_id": 1}):
        raise ErrorAPI(404, f"El usuario autor '{datos.usuario_id}' no existe")
    doc = {"_id": db.siguiente_id("publicaciones"), **datos.model_dump(),
           "fecha_publicacion": datetime.now().replace(microsecond=0)}
    base.publicaciones.insert_one(doc)
    log.info("Publicación creada %s por %s", doc["_id"], datos.usuario_id)
    return doc


@router.patch("/{publicacion_id}", summary="Editar publicación")
def actualizar(datos: PublicacionActualizar, publicacion_id: str = ID_PUB):
    cambios = datos.model_dump(exclude_none=True)
    if not cambios:
        raise ErrorAPI(400, "Debe enviar al menos un campo para actualizar")
    cambios["editada_en"] = datetime.now().replace(microsecond=0)
    r = db.get_db().publicaciones.update_one({"_id": publicacion_id}, {"$set": cambios})
    if r.matched_count == 0:
        raise no_encontrado("Publicación", publicacion_id)
    log.info("Publicación %s editada: %s", publicacion_id, list(cambios))
    return db.get_db().publicaciones.find_one({"_id": publicacion_id})


@router.delete("/{publicacion_id}", summary="Eliminar publicación con sus interacciones (transacción)")
def eliminar(publicacion_id: str = ID_PUB):
    base = db.get_db()
    if not base.publicaciones.find_one({"_id": publicacion_id}, {"_id": 1}):
        raise no_encontrado("Publicación", publicacion_id)

    def operacion(s):
        return {
            "reacciones": base.reacciones.delete_many({"publicacion_id": publicacion_id}, session=s).deleted_count,
            "comentarios": base.comentarios.delete_many({"publicacion_id": publicacion_id}, session=s).deleted_count,
            "campanas_actualizadas": base.campanas.update_many(
                {"publicaciones_asociadas": publicacion_id},
                {"$pull": {"publicaciones_asociadas": publicacion_id}}, session=s).modified_count,
            "publicacion": base.publicaciones.delete_one({"_id": publicacion_id}, session=s).deleted_count,
        }

    with db.get_client().start_session() as s:
        resumen = s.with_transaction(operacion)
    log.info("Publicación %s eliminada: %s", publicacion_id, resumen)
    return {"mensaje": f"Publicación {publicacion_id} eliminada", "detalle": resumen}
