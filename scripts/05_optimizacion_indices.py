"""
PASO 5 - Optimización de consultas con índices.

1. Borra los índices propios (deja solo _id) para medir el ANTES.
2. Ejecuta explain("executionStats") sobre 4 consultas + mide el tiempo
   promedio de una agregación con $lookup.
3. Crea los índices.
4. Repite las mediciones (DESPUÉS) y muestra la comparación.
5. Guarda todo en evidencias/05_explain_antes_despues.json

Uso:  python scripts/05_optimizacion_indices.py
"""
import json
import time
from datetime import datetime

from pymongo import ASCENDING, DESCENDING

from config import EVIDENCIAS_DIR, get_db, titulo

db = get_db()

# Consultas que se usan en el negocio (mismas de mongosh/04_consultas.js)
CONSULTAS = [
    {
        "id": "Q1",
        "descripcion": "Usuarios móviles registrados en 2025, orden por fecha",
        "coleccion": "usuarios",
        "filtro": {"dispositivo": "Móvil",
                   "fecha_registro": {"$gte": datetime(2025, 1, 1), "$lt": datetime(2026, 1, 1)}},
        "orden": [("fecha_registro", DESCENDING)],
    },
    {
        "id": "Q2",
        "descripcion": "Publicaciones de Tecnología Video/Imagen en Q2 2025",
        "coleccion": "publicaciones",
        "filtro": {"categoria": "Tecnología", "tipo": {"$in": ["Video", "Imagen"]},
                   "fecha_publicacion": {"$gte": datetime(2025, 4, 1), "$lt": datetime(2025, 7, 1)}},
        "orden": [("fecha_publicacion", ASCENDING)],
    },
    {
        "id": "Q3",
        "descripcion": "Comentarios de una publicación (base del $lookup)",
        "coleccion": "comentarios",
        "filtro": {"publicacion_id": "pub_429"},
        "orden": None,
    },
    {
        "id": "Q4",
        "descripcion": "Reacciones de un usuario ordenadas por fecha",
        "coleccion": "reacciones",
        "filtro": {"usuario_id": "user_311"},
        "orden": [("fecha", DESCENDING)],
    },
]

INDICES = [
    ("usuarios", [("dispositivo", ASCENDING), ("fecha_registro", DESCENDING)], {"name": "idx_dispositivo_fecha"}),
    ("usuarios", [("correo", ASCENDING)], {"name": "uq_correo", "unique": True}),
    ("publicaciones", [("categoria", ASCENDING), ("tipo", ASCENDING), ("fecha_publicacion", ASCENDING)],
     {"name": "idx_categoria_tipo_fecha"}),
    ("publicaciones", [("usuario_id", ASCENDING)], {"name": "idx_pub_usuario"}),
    ("comentarios", [("publicacion_id", ASCENDING)], {"name": "idx_com_publicacion"}),
    ("comentarios", [("usuario_id", ASCENDING)], {"name": "idx_com_usuario"}),
    ("reacciones", [("publicacion_id", ASCENDING)], {"name": "idx_reac_publicacion"}),
    ("reacciones", [("usuario_id", ASCENDING), ("fecha", DESCENDING)], {"name": "idx_reac_usuario_fecha"}),
]

PIPELINE_POPULARES = [
    {"$lookup": {"from": "reacciones", "localField": "_id", "foreignField": "publicacion_id", "as": "r"}},
    {"$lookup": {"from": "comentarios", "localField": "_id", "foreignField": "publicacion_id", "as": "c"}},
    {"$project": {"engagement": {"$add": [{"$size": "$r"}, {"$size": "$c"}, {"$sum": "$c.likes"}]}}},
    {"$sort": {"engagement": -1}},
    {"$limit": 10},
]


def etapas(plan: dict) -> list[str]:
    """Recorre el winningPlan y devuelve las etapas (COLLSCAN, IXSCAN, FETCH...)."""
    salida = []
    if "stage" in plan:
        salida.append(plan["stage"] + (f"({plan['indexName']})" if "indexName" in plan else ""))
    for k in ("inputStage", "queryPlan"):
        if k in plan:
            salida += etapas(plan[k])
    for sub in plan.get("inputStages", []):
        salida += etapas(sub)
    return salida


def medir(q: dict, repeticiones: int = 30) -> dict:
    col = db[q["coleccion"]]
    cursor = col.find(q["filtro"])
    if q["orden"]:
        cursor = cursor.sort(q["orden"])
    exp = cursor.explain()  # pymongo usa verbosity executionStats por defecto
    stats = exp["executionStats"]

    t0 = time.perf_counter()
    for _ in range(repeticiones):
        c = col.find(q["filtro"])
        if q["orden"]:
            c = c.sort(q["orden"])
        list(c)
    prom_ms = (time.perf_counter() - t0) * 1000 / repeticiones

    return {
        "plan": " <- ".join(etapas(exp["queryPlanner"]["winningPlan"])),
        "nReturned": stats["nReturned"],
        "totalKeysExamined": stats["totalKeysExamined"],
        "totalDocsExamined": stats["totalDocsExamined"],
        "executionTimeMillis": stats["executionTimeMillis"],
        "tiempo_promedio_cliente_ms": round(prom_ms, 2),
    }


def medir_agregacion(repeticiones: int = 10) -> float:
    list(db.publicaciones.aggregate(PIPELINE_POPULARES))  # calentamiento (no se mide)
    t0 = time.perf_counter()
    for _ in range(repeticiones):
        list(db.publicaciones.aggregate(PIPELINE_POPULARES))
    return round((time.perf_counter() - t0) * 1000 / repeticiones, 2)


def borrar_indices():
    for col in {c for c, _, _ in INDICES}:
        db[col].drop_indexes()  # nunca borra el índice _id


def imprimir(resultado: dict):
    print(f"  plan: {resultado['plan']}")
    print(f"  devueltos={resultado['nReturned']}  keysExamined={resultado['totalKeysExamined']}  "
          f"docsExamined={resultado['totalDocsExamined']}  execTimeMs={resultado['executionTimeMillis']}  "
          f"promedio cliente={resultado['tiempo_promedio_cliente_ms']} ms")


titulo("PASO 5 - Optimización con índices (explain executionStats)")

print("\n--- ANTES (sin índices, solo _id) ---")
borrar_indices()
antes = {}
for q in CONSULTAS:
    print(f"\n{q['id']} {q['descripcion']}")
    antes[q["id"]] = medir(q)
    imprimir(antes[q["id"]])
agg_antes = medir_agregacion()
print(f"\nAgregación 'Top publicaciones' ($lookup x2): {agg_antes} ms promedio")

print("\n--- Creando índices ---")
for col, claves, opciones in INDICES:
    nombre = db[col].create_index(claves, **opciones)
    print(f"  [OK] {col}.{nombre}  {claves}")

print("\n--- DESPUÉS (con índices) ---")
despues = {}
for q in CONSULTAS:
    print(f"\n{q['id']} {q['descripcion']}")
    despues[q["id"]] = medir(q)
    imprimir(despues[q["id"]])
agg_despues = medir_agregacion()
print(f"\nAgregación 'Top publicaciones' ($lookup x2): {agg_despues} ms promedio")

titulo("RESUMEN COMPARATIVO")
print(f"{'Consulta':<9}{'Docs exam. antes':>17}{'Docs exam. desp.':>17}{'Plan antes':>12}{'Plan después':>14}")
for q in CONSULTAS:
    a, d = antes[q["id"]], despues[q["id"]]
    pa = "COLLSCAN" if "COLLSCAN" in a["plan"] else "IXSCAN"
    pd = "COLLSCAN" if "COLLSCAN" in d["plan"] else "IXSCAN"
    print(f"{q['id']:<9}{a['totalDocsExamined']:>17}{d['totalDocsExamined']:>17}{pa:>12}{pd:>14}")
variacion = (agg_despues / agg_antes - 1) * 100 if agg_antes else 0
print(f"\nAgregación $lookup: {agg_antes} ms -> {agg_despues} ms ({variacion:+.0f}%)")
print("Nota: con solo 500 documentos los tiempos son de 1-10 ms y varían entre ejecuciones;\n"
      "la métrica confiable es docsExamined. En la agregación, sin índice MongoDB puede usar\n"
      "un hash join en memoria (rápido con pocos datos); con índice usa búsquedas por índice,\n"
      "que escalan mejor cuando las colecciones crecen a miles/millones de documentos.")

salida = EVIDENCIAS_DIR / "05_explain_antes_despues.json"
with open(salida, "w", encoding="utf-8") as f:
    json.dump({"fecha": datetime.now().isoformat(timespec="seconds"),
               "consultas": [{**{k: q[k] for k in ("id", "descripcion", "coleccion")},
                              "antes": antes[q["id"]], "despues": despues[q["id"]]} for q in CONSULTAS],
               "agregacion_top_publicaciones_ms": {"antes": agg_antes, "despues": agg_despues}},
              f, ensure_ascii=False, indent=2)
print(f"\nEvidencia guardada en {salida.relative_to(EVIDENCIAS_DIR.parent)}")
