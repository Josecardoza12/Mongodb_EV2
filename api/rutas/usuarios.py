"""CRUD de usuarios."""
import logging
from datetime import datetime

from fastapi import APIRouter, Path, Query

from .. import db
from ..errores import ErrorAPI, no_encontrado
from ..schemas import Dispositivo, Genero, UsuarioActualizar, UsuarioCrear

router = APIRouter(prefix="/usuarios", tags=["Usuarios"])
log = logging.getLogger("contentflow.api")
ID_USUARIO = Path(pattern=r"^user_\d+$", examples=["user_10"])


@router.get("", summary="Listar usuarios con filtros y paginación")
def listar(pais: str | None = None, dispositivo: Dispositivo | None = None, genero: Genero | None = None,
           limit: int = Query(20, ge=1, le=100), skip: int = Query(0, ge=0)):
    filtro = {}
    if pais:
        filtro["pais"] = pais
    if dispositivo:
        filtro["dispositivo"] = dispositivo.value
    if genero:
        filtro["genero"] = genero.value
    col = db.get_db().usuarios
    items = list(col.find(filtro).sort("fecha_registro", -1).skip(skip).limit(limit))
    return {"total": col.count_documents(filtro), "limit": limit, "skip": skip, "items": items}


@router.get("/{usuario_id}", summary="Obtener un usuario")
def obtener(usuario_id: str = ID_USUARIO):
    doc = db.get_db().usuarios.find_one({"_id": usuario_id})
    if not doc:
        raise no_encontrado("Usuario", usuario_id)
    return doc


@router.post("", status_code=201, summary="Registrar usuario")
def crear(datos: UsuarioCrear):
    doc = {"_id": db.siguiente_id("usuarios"), **datos.model_dump(), "correo": datos.correo.lower(),
           "fecha_registro": datetime.now().replace(microsecond=0)}
    db.get_db().usuarios.insert_one(doc)  # correo duplicado -> DuplicateKeyError -> 409
    log.info("Usuario creado %s", doc["_id"])
    return doc


@router.patch("/{usuario_id}", summary="Actualizar datos de un usuario")
def actualizar(datos: UsuarioActualizar, usuario_id: str = ID_USUARIO):
    cambios = datos.model_dump(exclude_none=True)
    if not cambios:
        raise ErrorAPI(400, "Debe enviar al menos un campo para actualizar")
    if "correo" in cambios:
        cambios["correo"] = cambios["correo"].lower()
    r = db.get_db().usuarios.update_one({"_id": usuario_id}, {"$set": cambios})
    if r.matched_count == 0:
        raise no_encontrado("Usuario", usuario_id)
    log.info("Usuario %s actualizado: %s", usuario_id, list(cambios))
    return db.get_db().usuarios.find_one({"_id": usuario_id})


@router.delete("/{usuario_id}", summary="Eliminar usuario y todo su contenido (transacción)")
def eliminar(usuario_id: str = ID_USUARIO):
    base = db.get_db()
    if not base.usuarios.find_one({"_id": usuario_id}, {"_id": 1}):
        raise no_encontrado("Usuario", usuario_id)

    def operacion(s):
        pubs = [p["_id"] for p in base.publicaciones.find({"usuario_id": usuario_id}, {"_id": 1}, session=s)]
        filtro = {"$or": [{"usuario_id": usuario_id}, {"publicacion_id": {"$in": pubs}}]}
        return {
            "reacciones": base.reacciones.delete_many(filtro, session=s).deleted_count,
            "comentarios": base.comentarios.delete_many(filtro, session=s).deleted_count,
            "campanas_actualizadas": base.campanas.update_many(
                {"publicaciones_asociadas": {"$in": pubs}},
                {"$pull": {"publicaciones_asociadas": {"$in": pubs}}}, session=s).modified_count,
            "publicaciones": base.publicaciones.delete_many({"usuario_id": usuario_id}, session=s).deleted_count,
            "usuario": base.usuarios.delete_one({"_id": usuario_id}, session=s).deleted_count,
        }

    with db.get_client().start_session() as s:
        resumen = s.with_transaction(operacion)
    log.info("Usuario %s eliminado en cascada: %s", usuario_id, resumen)
    return {"mensaje": f"Usuario {usuario_id} eliminado", "detalle": resumen}
