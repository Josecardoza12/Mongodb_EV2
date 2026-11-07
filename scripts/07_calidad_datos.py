"""
PASO 7 - Validación de calidad de datos.

Detecta:
  A. Duplicados        (correos, reacciones repetidas usuario+publicación,
                        comentarios repetidos, hashtags repetidos en un arreglo)
  B. Referencias       (usuario_id / publicacion_id que no existen,
     inválidas          publicaciones de campañas que no existen)
  C. Inconsistencias   (reacción/comentario ANTES de la publicación,
                        publicación ANTES del registro del usuario,
                        campaña con fin < inicio, textos con espacios sobrantes)

Corrige:
  - Duplicados: se conserva el registro más antiguo; los demás se copian a la
    colección 'cuarentena' (trazabilidad) y luego se eliminan.
  - Se crea índice ÚNICO (usuario_id, publicacion_id) en reacciones para que
    no vuelva a ocurrir.
  - Inconsistencias de fecha: NO se borran (son ~50% de los datos y no sabemos
    cuál fecha es la errónea). Se marcan con el campo calidad.flags para
    excluirlas de los análisis temporales.

Genera el informe evidencias/07_calidad_datos.md

Uso:  python scripts/07_calidad_datos.py   (re-ejecutable: la 2ª vez debe mostrar 0 duplicados)
"""
from datetime import datetime

from pymongo import ASCENDING

from config import EVIDENCIAS_DIR, get_db, titulo

db = get_db()
hallazgos = []  # (categoría, regla, colección, cantidad, acción)


def registrar(cat, regla, col, n, accion):
    hallazgos.append((cat, regla, col, n, accion))
    print(f"  [{'!!' if n else 'OK'}] {regla}: {n}")


def contar(col, pipeline):
    r = list(db[col].aggregate(pipeline + [{"$count": "n"}]))
    return r[0]["n"] if r else 0


titulo("PASO 7 - Calidad de datos")

# ------------------------------------------------------------------ A
print("\nA. DUPLICADOS")
n = contar("usuarios", [
    {"$group": {"_id": {"$toLower": {"$trim": {"input": "$correo"}}}, "n": {"$sum": 1}}},
    {"$match": {"n": {"$gt": 1}}}])
registrar("Duplicado", "Correos de usuario repetidos", "usuarios", n, "Índice único uq_correo (paso 5)")

grupos_dup = list(db.reacciones.aggregate([
    {"$sort": {"fecha": 1}},
    {"$group": {"_id": {"u": "$usuario_id", "p": "$publicacion_id"}, "ids": {"$push": "$_id"},
                "tipos": {"$push": "$tipo_reaccion"}, "n": {"$sum": 1}}},
    {"$match": {"n": {"$gt": 1}}}]))
for g in grupos_dup:
    print(f"       usuario {g['_id']['u']} -> {g['_id']['p']}: {list(zip(g['ids'], g['tipos']))}")
registrar("Duplicado", "Reacciones repetidas (mismo usuario y publicación)", "reacciones", len(grupos_dup),
          "Se conserva la más antigua, el resto a 'cuarentena' + índice único")

grupos_com = list(db.comentarios.aggregate([
    {"$sort": {"fecha": 1}},
    {"$group": {"_id": {"u": "$usuario_id", "p": "$publicacion_id", "t": "$comentario"},
                "ids": {"$push": "$_id"}, "n": {"$sum": 1}}},
    {"$match": {"n": {"$gt": 1}}}]))
registrar("Duplicado", "Comentarios idénticos repetidos", "comentarios", len(grupos_com),
          "Se conserva el más antiguo, el resto a 'cuarentena'")

n = contar("publicaciones", [
    {"$match": {"$expr": {"$ne": [{"$size": "$hashtags"}, {"$size": {"$setUnion": ["$hashtags", []]}}]}}}])
registrar("Duplicado", "Publicaciones con hashtags repetidos en el arreglo", "publicaciones", n,
          "Se deja un solo valor por hashtag")
if n:
    db.publicaciones.update_many(
        {"$expr": {"$ne": [{"$size": "$hashtags"}, {"$size": {"$setUnion": ["$hashtags", []]}}]}},
        [{"$set": {"hashtags": {"$setUnion": ["$hashtags", []]}}}])

# ------------------------------------------------------------------ B
print("\nB. REFERENCIAS INVÁLIDAS")


def huerfanos(col, campo, destino):
    return contar(col, [
        {"$lookup": {"from": destino, "localField": campo, "foreignField": "_id", "as": "ref"}},
        {"$match": {"ref": {"$size": 0}}}])


for col, campo, destino in [("publicaciones", "usuario_id", "usuarios"),
                            ("reacciones", "usuario_id", "usuarios"),
                            ("reacciones", "publicacion_id", "publicaciones"),
                            ("comentarios", "usuario_id", "usuarios"),
                            ("comentarios", "publicacion_id", "publicaciones")]:
    registrar("Referencia", f"{col}.{campo} que no existe en {destino}", col,
              huerfanos(col, campo, destino), "Se enviarían a 'cuarentena'")

n = contar("campanas", [
    {"$unwind": "$publicaciones_asociadas"},
    {"$lookup": {"from": "publicaciones", "localField": "publicaciones_asociadas", "foreignField": "_id",
                 "as": "ref"}},
    {"$match": {"ref": {"$size": 0}}}])
registrar("Referencia", "campanas.publicaciones_asociadas inexistentes", "campanas", n, "Se quitarían con $pull")

# ------------------------------------------------------------------ C
print("\nC. INCONSISTENCIAS")


def antes_de_publicacion(col):
    return [d["_id"] for d in db[col].aggregate([
        {"$lookup": {"from": "publicaciones", "localField": "publicacion_id", "foreignField": "_id", "as": "p"}},
        {"$unwind": "$p"},
        {"$match": {"$expr": {"$lt": ["$fecha", "$p.fecha_publicacion"]}}},
        {"$project": {"_id": 1}}])]


ids_r = antes_de_publicacion("reacciones")
registrar("Inconsistencia", "Reacciones con fecha anterior a la publicación", "reacciones", len(ids_r),
          "Marcadas calidad.flags=['fecha_antes_publicacion']")
ids_c = antes_de_publicacion("comentarios")
registrar("Inconsistencia", "Comentarios con fecha anterior a la publicación", "comentarios", len(ids_c),
          "Marcados calidad.flags=['fecha_antes_publicacion']")

ids_p = [d["_id"] for d in db.publicaciones.aggregate([
    {"$lookup": {"from": "usuarios", "localField": "usuario_id", "foreignField": "_id", "as": "u"}},
    {"$unwind": "$u"},
    {"$match": {"$expr": {"$lt": ["$fecha_publicacion", "$u.fecha_registro"]}}},
    {"$project": {"_id": 1}}])]
registrar("Inconsistencia", "Publicaciones anteriores al registro del autor", "publicaciones", len(ids_p),
          "Marcadas calidad.flags=['publicada_antes_registro']")

n = db.campanas.count_documents({"$expr": {"$lt": ["$fecha_fin", "$fecha_inicio"]}})
registrar("Inconsistencia", "Campañas con fecha_fin < fecha_inicio", "campanas", n, "Se corregiría intercambiando")

n = sum(db.usuarios.count_documents({c: {"$regex": r"^\s|\s$"}}) for c in ("nombre", "correo", "pais"))
registrar("Inconsistencia", "Textos de usuario con espacios al inicio/fin", "usuarios", n, "Se aplicaría $trim")

# ------------------------------------------------------------------ CORRECCIONES
titulo("CORRECCIONES APLICADAS")
cuarentena = db["cuarentena"]
movidos = 0
for col, grupos in (("reacciones", grupos_dup), ("comentarios", grupos_com)):
    for g in grupos:
        sobrantes = g["ids"][1:]  # el primero (más antiguo) se conserva
        for doc in db[col].find({"_id": {"$in": sobrantes}}):
            cuarentena.replace_one(
                {"_id": f"{col}:{doc['_id']}"},
                {"_id": f"{col}:{doc['_id']}", "coleccion": col, "motivo": "duplicado",
                 "conservado": g["ids"][0], "documento": doc, "fecha_cuarentena": datetime.now()},
                upsert=True)
        movidos += db[col].delete_many({"_id": {"$in": sobrantes}}).deleted_count
print(f"[OK] Duplicados movidos a 'cuarentena' y eliminados: {movidos}")

nombre = db.reacciones.create_index([("usuario_id", ASCENDING), ("publicacion_id", ASCENDING)],
                                    unique=True, name="uq_reaccion_usuario_publicacion")
print(f"[OK] Índice único creado: reacciones.{nombre}")

hoy = datetime.now().replace(microsecond=0)
for col, ids, flag in (("reacciones", ids_r, "fecha_antes_publicacion"),
                       ("comentarios", ids_c, "fecha_antes_publicacion"),
                       ("publicaciones", ids_p, "publicada_antes_registro")):
    r = db[col].update_many({"_id": {"$in": ids}},
                            {"$addToSet": {"calidad.flags": flag}, "$set": {"calidad.revisado_en": hoy}})
    print(f"[OK] {col}: {r.modified_count} documentos marcados con '{flag}'")

# ------------------------------------------------------------------ REPORTE
ruta = EVIDENCIAS_DIR / "07_calidad_datos.md"
with open(ruta, "w", encoding="utf-8") as f:
    f.write(f"# Informe de calidad de datos - ContentFlow\n\nGenerado: {hoy}\n\n")
    f.write("| Categoría | Regla revisada | Colección | Casos | Acción |\n|---|---|---|---|---|\n")
    for h in hallazgos:
        f.write(f"| {h[0]} | {h[1]} | {h[2]} | {h[3]} | {h[4]} |\n")
    f.write(f"\n**Correcciones:** {movidos} duplicados movidos a `cuarentena`; índice único "
            f"`uq_reaccion_usuario_publicacion`; {len(ids_r) + len(ids_c) + len(ids_p)} documentos marcados "
            "con `calidad.flags` para excluirlos de análisis por fecha.\n")
    f.write("\nPara analizar solo datos consistentes: `{ \"calidad.flags\": { $exists: false } }`\n")
print(f"\nReporte guardado en evidencias/{ruta.name}")
