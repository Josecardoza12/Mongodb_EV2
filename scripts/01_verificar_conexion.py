"""
PASO 1 - Verificar la conexión con MongoDB Atlas.

Comprueba: ping al cluster, versión del servidor, usuario autenticado y
sus roles, y que tenga permisos de lectura y escritura (escribe y borra
un documento de prueba).

Uso:  python scripts/01_verificar_conexion.py
"""
import time
from datetime import datetime, timezone

from config import MONGO_DB, get_client, titulo

titulo("PASO 1 - Verificación de conexión con MongoDB Atlas")

t0 = time.perf_counter()
client = get_client()
latencia = (time.perf_counter() - t0) * 1000

info = client.server_info()
print(f"[OK] Conectado. Latencia de conexión + ping: {latencia:.0f} ms")
print(f"[OK] Versión de MongoDB: {info['version']}")

estado = client.admin.command("connectionStatus")
for u in estado["authInfo"]["authenticatedUsers"]:
    print(f"[OK] Usuario autenticado: {u['user']} (base de auth: {u['db']})")
for r in estado["authInfo"]["authenticatedUserRoles"]:
    print(f"     rol: {r['role']} en {r['db']}")

# Prueba de escritura/lectura/borrado (valida permisos readWrite)
db = client[MONGO_DB]
prueba = db["_prueba_conexion"]
doc_id = prueba.insert_one({"msg": "ping", "fecha": datetime.now(timezone.utc)}).inserted_id
leido = prueba.find_one({"_id": doc_id})
prueba.delete_one({"_id": doc_id})
db.drop_collection("_prueba_conexion")
print(f"[OK] Escritura, lectura y borrado en la base '{MONGO_DB}': {'correcto' if leido else 'FALLÓ'}")

print("\nConexión validada. Siguiente paso: python scripts/02_crear_colecciones.py")
