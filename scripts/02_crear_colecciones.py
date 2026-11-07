"""
PASO 2 - Crear la base de datos 'contentflow' y sus cinco colecciones.

Cada colección se crea con un validador $jsonSchema, para que MongoDB
rechace documentos con campos faltantes o tipos incorrectos (por ejemplo,
una fecha guardada como texto o un tipo de reacción inventado).

Uso:  python scripts/02_crear_colecciones.py
      (si las colecciones ya existen, se actualiza el validador)
"""
from config import COLECCIONES, get_db, titulo

ESQUEMAS = {
    "usuarios": {
        "bsonType": "object",
        "required": ["_id", "nombre", "correo", "pais", "genero", "fecha_registro", "dispositivo"],
        "properties": {
            "_id": {"bsonType": "string", "pattern": "^user_[0-9]+$"},
            "nombre": {"bsonType": "string", "minLength": 2},
            "correo": {"bsonType": "string", "pattern": "^[^@\\s]+@[^@\\s]+\\.[^@\\s]+$"},
            "pais": {"bsonType": "string"},
            "genero": {"enum": ["Femenino", "Masculino", "Otro"]},
            "fecha_registro": {"bsonType": "date"},
            "dispositivo": {"enum": ["Móvil", "Desktop", "Tablet"]},
        },
    },
    "publicaciones": {
        "bsonType": "object",
        "required": ["_id", "usuario_id", "contenido", "fecha_publicacion", "categoria", "hashtags", "tipo"],
        "properties": {
            "_id": {"bsonType": "string", "pattern": "^pub_[0-9]+$"},
            "usuario_id": {"bsonType": "string"},
            "contenido": {"bsonType": "string", "minLength": 1},
            "fecha_publicacion": {"bsonType": "date"},
            "categoria": {"enum": ["Tecnología", "Cultura", "Educación", "Deportes", "Entretenimiento"]},
            "hashtags": {"bsonType": "array", "items": {"bsonType": "string", "pattern": "^#"}},
            "tipo": {"enum": ["Imagen", "Video", "Texto"]},
        },
    },
    "reacciones": {
        "bsonType": "object",
        "required": ["_id", "usuario_id", "publicacion_id", "tipo_reaccion", "fecha"],
        "properties": {
            "_id": {"bsonType": "string"},
            "usuario_id": {"bsonType": "string"},
            "publicacion_id": {"bsonType": "string"},
            "tipo_reaccion": {"enum": ["Me gusta", "Me encanta", "Me entristece", "Me enoja"]},
            "fecha": {"bsonType": "date"},
        },
    },
    "comentarios": {
        "bsonType": "object",
        "required": ["_id", "usuario_id", "publicacion_id", "comentario", "fecha", "likes"],
        "properties": {
            "_id": {"bsonType": "string"},
            "usuario_id": {"bsonType": "string"},
            "publicacion_id": {"bsonType": "string"},
            "comentario": {"bsonType": "string", "minLength": 1},
            "fecha": {"bsonType": "date"},
            "likes": {"bsonType": ["int", "long"], "minimum": 0},
        },
    },
    "campanas": {
        "bsonType": "object",
        "required": ["_id", "nombre", "fecha_inicio", "fecha_fin", "objetivo",
                     "publicaciones_asociadas", "metricas_objetivo"],
        "properties": {
            "_id": {"bsonType": "string"},
            "nombre": {"bsonType": "string"},
            "fecha_inicio": {"bsonType": "date"},
            "fecha_fin": {"bsonType": "date"},
            "objetivo": {"enum": ["Captar nuevos usuarios", "Aumentar engagement", "Promover contenido"]},
            "publicaciones_asociadas": {"bsonType": "array", "items": {"bsonType": "string"}},
            "metricas_objetivo": {
                "bsonType": "object",
                "required": ["likes", "comentarios", "compartidos"],
                "properties": {
                    "likes": {"bsonType": ["int", "long"], "minimum": 0},
                    "comentarios": {"bsonType": ["int", "long"], "minimum": 0},
                    "compartidos": {"bsonType": ["int", "long"], "minimum": 0},
                },
            },
        },
    },
}

titulo("PASO 2 - Creación de la base de datos y colecciones")
db = get_db()
existentes = set(db.list_collection_names())

for nombre in COLECCIONES:
    validator = {"$jsonSchema": ESQUEMAS[nombre]}
    if nombre in existentes:
        db.command("collMod", nombre, validator=validator, validationLevel="strict", validationAction="error")
        print(f"[OK] '{nombre}' ya existía: validador actualizado")
    else:
        db.create_collection(nombre, validator=validator, validationLevel="strict", validationAction="error")
        print(f"[OK] Colección '{nombre}' creada con validador $jsonSchema")

print(f"\nColecciones en '{db.name}': {sorted(db.list_collection_names())}")
print("Siguiente paso: python scripts/03_importar_datos.py")
