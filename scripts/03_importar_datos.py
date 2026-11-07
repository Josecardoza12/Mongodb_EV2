"""
PASO 3 - Importar los cinco JSON del ZIP (Forma A).

- Convierte las fechas de texto ("2025-03-13T06:37:59") a tipo Date (BSON).
- Vacía cada colección antes de cargar (así el script se puede re-ejecutar).
- Verifica que la cantidad en MongoDB sea igual a la del archivo.
- Verifica que las fechas quedaron como Date y no como string.

Uso:  python scripts/03_importar_datos.py
"""
import json
from datetime import datetime

from config import COLECCIONES, DATA_DIR, get_db, titulo

CAMPOS_FECHA = {
    "usuarios": ["fecha_registro"],
    "publicaciones": ["fecha_publicacion"],
    "reacciones": ["fecha"],
    "comentarios": ["fecha"],
    "campanas": ["fecha_inicio", "fecha_fin"],
}


def convertir_fechas(doc: dict, campos: list[str]) -> dict:
    for c in campos:
        if isinstance(doc.get(c), str):
            doc[c] = datetime.fromisoformat(doc[c])
    return doc


titulo("PASO 3 - Importación de datos")
db = get_db()
resumen = []

for nombre in COLECCIONES:
    ruta = DATA_DIR / f"{nombre}.json"
    with open(ruta, encoding="utf-8") as f:
        docs = json.load(f)
    docs = [convertir_fechas(d, CAMPOS_FECHA[nombre]) for d in docs]

    col = db[nombre]
    col.delete_many({})
    resultado = col.insert_many(docs, ordered=False)
    en_bd = col.count_documents({})

    # ¿Quedó algún campo fecha como string?
    fechas_texto = sum(col.count_documents({c: {"$type": "string"}}) for c in CAMPOS_FECHA[nombre])
    ok = len(docs) == en_bd == len(resultado.inserted_ids) and fechas_texto == 0
    resumen.append((nombre, len(docs), en_bd, fechas_texto, "OK" if ok else "REVISAR"))

print(f"\n{'Colección':<15}{'En JSON':>10}{'En MongoDB':>12}{'Fechas texto':>14}{'Estado':>9}")
for fila in resumen:
    print(f"{fila[0]:<15}{fila[1]:>10}{fila[2]:>12}{fila[3]:>14}{fila[4]:>9}")

ejemplo = db.publicaciones.find_one({}, {"_id": 1, "fecha_publicacion": 1})
print(f"\nEjemplo de fecha convertida: {ejemplo['_id']} -> {ejemplo['fecha_publicacion']!r}")
print('Siguiente paso: mongosh "TU_MONGO_URI" --file mongosh/04_consultas.js')
