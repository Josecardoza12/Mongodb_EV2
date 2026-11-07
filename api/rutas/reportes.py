"""Reportes de negocio (agregaciones) y lectura de campañas."""
from fastapi import APIRouter, Path, Query

from .. import db
from ..errores import no_encontrado

router = APIRouter(tags=["Reportes y campañas"])


@router.get("/reportes/usuarios-activos", summary="Top usuarios por actividad total")
def usuarios_activos(top: int = Query(10, ge=1, le=50)):
    return list(db.get_db().publicaciones.aggregate([
        {"$project": {"usuario_id": 1, "t": {"$literal": "pub"}}},
        {"$unionWith": {"coll": "reacciones", "pipeline": [{"$project": {"usuario_id": 1, "t": {"$literal": "rea"}}}]}},
        {"$unionWith": {"coll": "comentarios", "pipeline": [{"$project": {"usuario_id": 1, "t": {"$literal": "com"}}}]}},
        {"$group": {"_id": "$usuario_id",
                    "publicaciones": {"$sum": {"$cond": [{"$eq": ["$t", "pub"]}, 1, 0]}},
                    "reacciones": {"$sum": {"$cond": [{"$eq": ["$t", "rea"]}, 1, 0]}},
                    "comentarios": {"$sum": {"$cond": [{"$eq": ["$t", "com"]}, 1, 0]}},
                    "total": {"$sum": 1}}},
        {"$sort": {"total": -1, "_id": 1}},
        {"$limit": top},
        {"$lookup": {"from": "usuarios", "localField": "_id", "foreignField": "_id", "as": "u"}},
        {"$project": {"_id": 0, "usuario_id": "$_id", "nombre": {"$first": "$u.nombre"},
                      "pais": {"$first": "$u.pais"}, "publicaciones": 1, "reacciones": 1,
                      "comentarios": 1, "total": 1}},
    ]))


@router.get("/reportes/publicaciones-populares", summary="Top publicaciones por engagement")
def publicaciones_populares(top: int = Query(10, ge=1, le=50)):
    return list(db.get_db().publicaciones.aggregate([
        {"$lookup": {"from": "reacciones", "localField": "_id", "foreignField": "publicacion_id", "as": "r"}},
        {"$lookup": {"from": "comentarios", "localField": "_id", "foreignField": "publicacion_id", "as": "c"}},
        {"$project": {"usuario_id": 1, "categoria": 1, "tipo": 1, "fecha_publicacion": 1,
                      "reacciones": {"$size": "$r"}, "comentarios": {"$size": "$c"},
                      "likes_comentarios": {"$sum": "$c.likes"}}},
        {"$set": {"engagement": {"$add": ["$reacciones", "$comentarios", "$likes_comentarios"]}}},
        {"$sort": {"engagement": -1}},
        {"$limit": top},
    ]))


@router.get("/campanas", summary="Listar campañas")
def listar_campanas(objetivo: str | None = None, limit: int = Query(20, ge=1, le=100),
                    skip: int = Query(0, ge=0)):
    filtro = {"objetivo": objetivo} if objetivo else {}
    col = db.get_db().campanas
    return {"total": col.count_documents(filtro),
            "items": list(col.find(filtro).sort("fecha_inicio", -1).skip(skip).limit(limit))}


@router.get("/campanas/{campana_id}/rendimiento", summary="Rendimiento de una campaña vs. sus metas")
def rendimiento_campana(campana_id: str = Path(pattern=r"^camp_\d+$")):
    base = db.get_db()
    c = base.campanas.find_one({"_id": campana_id})
    if not c:
        raise no_encontrado("Campaña", campana_id)
    ventana = {"$gte": c["fecha_inicio"], "$lte": c["fecha_fin"]}
    pubs = c["publicaciones_asociadas"]
    likes = base.reacciones.count_documents({"publicacion_id": {"$in": pubs}, "fecha": ventana,
                                             "tipo_reaccion": {"$in": ["Me gusta", "Me encanta"]}})
    comentarios = base.comentarios.count_documents({"publicacion_id": {"$in": pubs}, "fecha": ventana})
    meta = c["metricas_objetivo"]

    def pct(x, m):
        return round(x / m * 100, 2) if m else None

    return {"campana": c["nombre"], "objetivo": c["objetivo"], "periodo": [c["fecha_inicio"], c["fecha_fin"]],
            "publicaciones": pubs,
            "likes": {"logrado": likes, "meta": meta["likes"], "cumplimiento_pct": pct(likes, meta["likes"])},
            "comentarios": {"logrado": comentarios, "meta": meta["comentarios"],
                            "cumplimiento_pct": pct(comentarios, meta["comentarios"])},
            "compartidos": {"logrado": None, "meta": meta["compartidos"],
                            "nota": "El dataset no registra compartidos"}}
