"""
PASO 6 - CRUD completo simulando operaciones reales de ContentFlow.

Historia simulada:
  1. CREATE  Se registra una usuaria nueva, publica, recibe reacciones y
             comentarios, y Marketing crea una campaña con su publicación.
  2. READ    Se consulta su perfil, su publicación con interacciones y la campaña.
  3. UPDATE  Edita la publicación, un comentario gana likes, la campaña suma
             otra publicación y se extiende, la usuaria cambia de dispositivo.
  4. VALID.  Se intenta insertar datos inválidos (el validador los rechaza).
  5. DELETE  La usuaria pide eliminar su cuenta: se borran en cascada sus
             publicaciones, reacciones y comentarios dentro de una TRANSACCIÓN,
             y se quitan sus publicaciones de las campañas.

Uso:  python scripts/06_crud.py   (ejecutar después del paso 5: usa el índice único de correo)
"""
import re
from datetime import datetime, timedelta

from pymongo.errors import DuplicateKeyError, WriteError

from config import get_client, MONGO_DB, titulo

client = get_client()
db = client[MONGO_DB]


def siguiente_id(coleccion: str, prefijo: str) -> str:
    """Genera el siguiente id correlativo (ej: user_501) según el mayor existente."""
    mayor = 0
    for d in db[coleccion].find({"_id": {"$regex": f"^{prefijo}_"}}, {"_id": 1}):
        m = re.match(rf"^{prefijo}_(\d+)$", d["_id"])
        if m:
            mayor = max(mayor, int(m.group(1)))
    return f"{prefijo}_{mayor + 1}"


ahora = datetime.now().replace(microsecond=0)

# ---------------------------------------------------------------- CREATE
titulo("1. CREATE - registro, publicación, interacciones y campaña")
user_id = siguiente_id("usuarios", "user")
db.usuarios.insert_one({
    "_id": user_id, "nombre": "Camila Rojas", "correo": f"camila.rojas.{user_id}@contentflow.cl",
    "pais": "Chile", "genero": "Femenino", "fecha_registro": ahora, "dispositivo": "Móvil",
})
print(f"[insert_one] usuario {user_id} registrado")

pub_id = siguiente_id("publicaciones", "pub")
db.publicaciones.insert_one({
    "_id": pub_id, "usuario_id": user_id,
    "contenido": "Tutorial: cómo armar tu primer dashboard en Power BI con datos de MongoDB.",
    "fecha_publicacion": ahora, "categoria": "Educación",
    "hashtags": ["#aprendizaje", "#innovacion"], "tipo": "Video",
})
print(f"[insert_one] publicación {pub_id} creada")

# Otros usuarios existentes reaccionan (insert_many)
otros = [u["_id"] for u in db.usuarios.find({"_id": {"$ne": user_id}}, {"_id": 1}).limit(4)]
base_r = int(siguiente_id("reacciones", "react").split("_")[1])
tipos = ["Me gusta", "Me encanta", "Me gusta", "Me encanta"]
res = db.reacciones.insert_many([
    {"_id": f"react_{base_r + i}", "usuario_id": u, "publicacion_id": pub_id,
     "tipo_reaccion": tipos[i], "fecha": ahora + timedelta(minutes=i + 1)}
    for i, u in enumerate(otros)
])
print(f"[insert_many] {len(res.inserted_ids)} reacciones: {res.inserted_ids}")

base_c = int(siguiente_id("comentarios", "comm").split("_")[1])
res = db.comentarios.insert_many([
    {"_id": f"comm_{base_c}", "usuario_id": otros[0], "publicacion_id": pub_id,
     "comentario": "¡Muy claro, gracias!", "fecha": ahora + timedelta(minutes=10), "likes": 0},
    {"_id": f"comm_{base_c + 1}", "usuario_id": otros[1], "publicacion_id": pub_id,
     "comentario": "¿Harás la parte 2 con agregaciones?", "fecha": ahora + timedelta(minutes=12), "likes": 2},
])
com_id = res.inserted_ids[0]
print(f"[insert_many] {len(res.inserted_ids)} comentarios: {res.inserted_ids}")

camp_id = siguiente_id("campanas", "camp")
db.campanas.insert_one({
    "_id": camp_id, "nombre": "Campaña Aprende Datos", "fecha_inicio": ahora,
    "fecha_fin": ahora + timedelta(days=30), "objetivo": "Aumentar engagement",
    "publicaciones_asociadas": [pub_id],
    "metricas_objetivo": {"likes": 50, "comentarios": 20, "compartidos": 10},
})
print(f"[insert_one] campaña {camp_id} creada con la publicación {pub_id}")

# ---------------------------------------------------------------- READ
titulo("2. READ - verificación de lo creado")
print("Usuario:", db.usuarios.find_one({"_id": user_id}, {"_id": 1, "nombre": 1, "correo": 1, "dispositivo": 1}))
detalle = list(db.publicaciones.aggregate([
    {"$match": {"_id": pub_id}},
    {"$lookup": {"from": "reacciones", "localField": "_id", "foreignField": "publicacion_id", "as": "reacciones"}},
    {"$lookup": {"from": "comentarios", "localField": "_id", "foreignField": "publicacion_id", "as": "comentarios"}},
    {"$project": {"categoria": 1, "tipo": 1, "hashtags": 1,
                  "n_reacciones": {"$size": "$reacciones"}, "n_comentarios": {"$size": "$comentarios"}}},
]))[0]
print("Publicación con interacciones:", detalle)
print("Campaña:", db.campanas.find_one({"_id": camp_id}, {"nombre": 1, "publicaciones_asociadas": 1, "fecha_fin": 1}))

# ---------------------------------------------------------------- UPDATE
titulo("3. UPDATE - modificaciones de negocio")
r = db.publicaciones.update_one(
    {"_id": pub_id},
    {"$set": {"contenido": "Tutorial actualizado: dashboard en Power BI + MongoDB Atlas (parte 1).",
              "editada_en": datetime.now().replace(microsecond=0)},
     "$addToSet": {"hashtags": "#series"}},
)
print(f"[update_one $set/$addToSet] publicación editada: matched={r.matched_count} modified={r.modified_count}")

r = db.comentarios.update_one({"_id": com_id}, {"$inc": {"likes": 15}})
print(f"[update_one $inc] comentario {com_id} +15 likes -> "
      f"{db.comentarios.find_one({'_id': com_id})['likes']} likes")

pub_extra = db.publicaciones.find_one({"categoria": "Educación", "_id": {"$ne": pub_id}}, {"_id": 1})["_id"]
r = db.campanas.update_one(
    {"_id": camp_id},
    {"$push": {"publicaciones_asociadas": pub_extra}, "$set": {"fecha_fin": ahora + timedelta(days=45)}},
)
print(f"[update_one $push] campaña suma {pub_extra} y se extiende a 45 días: modified={r.modified_count}")

r = db.usuarios.update_one({"_id": user_id}, {"$set": {"dispositivo": "Desktop"}})
print(f"[update_one] usuario cambia de dispositivo a Desktop: modified={r.modified_count}")

r = db.reacciones.update_many({"publicacion_id": pub_id, "tipo_reaccion": "Me gusta"},
                              {"$set": {"tipo_reaccion": "Me encanta"}})
print(f"[update_many] reacciones 'Me gusta' -> 'Me encanta' en {pub_id}: modified={r.modified_count}")

# ---------------------------------------------------------------- VALIDACIONES
titulo("4. VALIDACIÓN - el servidor rechaza datos incorrectos")
try:
    db.reacciones.insert_one({"_id": "react_test", "usuario_id": user_id, "publicacion_id": pub_id,
                              "tipo_reaccion": "Me divierte", "fecha": ahora})
    print("[!!] Se insertó un tipo de reacción inválido (no debería)")
except WriteError as e:
    print(f"[OK] Reacción con tipo inválido rechazada (code {e.code}: Document failed validation)")

try:
    db.comentarios.insert_one({"_id": "comm_test", "usuario_id": user_id, "publicacion_id": pub_id,
                               "comentario": "x", "fecha": "2025-01-01", "likes": -3})
    print("[!!] Se insertó un comentario con fecha texto y likes negativos (no debería)")
except WriteError as e:
    print(f"[OK] Comentario con fecha como texto y likes negativos rechazado (code {e.code})")

try:
    db.usuarios.insert_one({**db.usuarios.find_one({"_id": user_id}), "_id": "user_999999"})
    print("[!!] Se insertó un correo duplicado (¿ejecutaste el paso 5?)")
    db.usuarios.delete_one({"_id": "user_999999"})
except DuplicateKeyError:
    print("[OK] Usuario con correo duplicado rechazado por índice único uq_correo")

# ---------------------------------------------------------------- DELETE
titulo("5. DELETE - baja de cuenta con borrado en cascada (transacción)")


def contar():
    pubs = [p["_id"] for p in db.publicaciones.find({"usuario_id": user_id}, {"_id": 1})]
    return {
        "usuario": db.usuarios.count_documents({"_id": user_id}),
        "publicaciones": len(pubs),
        "reacciones_en_sus_pubs": db.reacciones.count_documents({"publicacion_id": {"$in": pubs}}),
        "comentarios_en_sus_pubs": db.comentarios.count_documents({"publicacion_id": {"$in": pubs}}),
        "campanas_con_sus_pubs": db.campanas.count_documents({"publicaciones_asociadas": {"$in": pubs}}),
    }


print("Antes:  ", contar())


def eliminar_usuario(session):
    pubs = [p["_id"] for p in db.publicaciones.find({"usuario_id": user_id}, {"_id": 1}, session=session)]
    r1 = db.reacciones.delete_many({"$or": [{"publicacion_id": {"$in": pubs}}, {"usuario_id": user_id}]},
                                   session=session)
    r2 = db.comentarios.delete_many({"$or": [{"publicacion_id": {"$in": pubs}}, {"usuario_id": user_id}]},
                                    session=session)
    r3 = db.campanas.update_many({"publicaciones_asociadas": {"$in": pubs}},
                                 {"$pull": {"publicaciones_asociadas": {"$in": pubs}}}, session=session)
    r4 = db.publicaciones.delete_many({"usuario_id": user_id}, session=session)
    r5 = db.usuarios.delete_one({"_id": user_id}, session=session)
    return r1.deleted_count, r2.deleted_count, r3.modified_count, r4.deleted_count, r5.deleted_count


with client.start_session() as s:
    reac, com, camp, pubs, usr = s.with_transaction(eliminar_usuario)
print(f"[transacción] reacciones={reac} comentarios={com} campañas actualizadas={camp} "
      f"publicaciones={pubs} usuario={usr}")
print("Después:", contar())

r = db.campanas.delete_one({"_id": camp_id})
print(f"[delete_one] campaña de prueba {camp_id} eliminada: {r.deleted_count}")
print("\nCRUD completado. La base quedó igual que antes de la simulación.")
