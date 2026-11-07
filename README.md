# ContentFlow – MongoDB Atlas + API REST (EP2 BDY0101, Forma A)

Implementación de una base de datos NoSQL en **MongoDB Atlas** para la plataforma ContentFlow
(usuarios, publicaciones, reacciones, comentarios y campañas), con consultas de negocio,
optimización con índices, CRUD, validación de calidad de datos y una **API REST en Python (FastAPI)**.

## Estructura

```
contentflow-mongodb/
├── data/                       # Los 5 JSON del ZIP (Forma A)
├── scripts/                    # Pasos 1, 2, 3, 5, 6 y 7 (Python + pymongo)
│   ├── config.py
│   ├── 01_verificar_conexion.py
│   ├── 02_crear_colecciones.py
│   ├── 03_importar_datos.py
│   ├── 05_optimizacion_indices.py
│   ├── 06_crud.py
│   └── 07_calidad_datos.py
├── mongosh/04_consultas.js     # Paso 4: 12 consultas de negocio
├── api/                        # Pasos 8 y 9: API REST (FastAPI)
├── postman/                    # Colección Postman con 31 requests y 71 tests
├── evidencias/                 # Salidas generadas (explain, calidad de datos)
├── logs/                       # api.log (registro de cada petición)
├── .env.example
└── requirements.txt
```

## Requisitos

- Python 3.10 o superior
- [mongosh](https://www.mongodb.com/try/download/shell) (o MongoDB Compass, que lo trae integrado)
- Postman
- Cuenta gratuita en [MongoDB Atlas](https://www.mongodb.com/cloud/atlas/register)

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     |   Mac/Linux: source .venv/bin/activate
pip install -r requirements.txt
```

---

## Paso a paso (en el orden de la pauta)

> 📸 = captura que debes sacar para el informe.

### 1. Configurar MongoDB Atlas
1. Crear cuenta en Atlas → **Create** → plan **M0 (Free)**, proveedor AWS, región **São Paulo (sa-east-1)** (la más cercana a Chile). Nombre: `Cluster0`.
2. **Database Access** → *Add New Database User* → método *Password* → usuario `contentflow_app` → rol **Read and write to any database** (o rol específico `readWrite@contentflow`). 📸
3. **Network Access** → *Add IP Address* → *Add Current IP Address*. Para la demo en clases también puedes agregar `0.0.0.0/0` (anótalo en el informe como riesgo y que se quita después). 📸
4. **Database → Connect → Drivers → Python** → copiar el URI.
5. Copiar `.env.example` a `.env` y pegar el URI con tu contraseña.
6. Ejecutar:
   ```bash
   python scripts/01_verificar_conexion.py
   ```
   Debe mostrar ping OK, versión, usuario/roles y prueba de escritura. 📸
7. Probar también con **Compass** (pegar el mismo URI) → segunda herramienta de conectividad (IE3). 📸

### 2. Crear base de datos y colecciones
```bash
python scripts/02_crear_colecciones.py
```
Crea la base `contentflow` con `usuarios`, `publicaciones`, `reacciones`, `comentarios`, `campanas`,
cada una con un **validador `$jsonSchema`** (tipos, campos obligatorios y valores permitidos). 📸 (Atlas → Browse Collections)

> El archivo original se llama `campañas.json`; la colección se nombra `campanas` (sin ñ) para evitar problemas de codificación.

### 3. Importar datos
```bash
python scripts/03_importar_datos.py
```
Carga los 5 JSON, **convierte las fechas a tipo `Date`** y verifica: 500 documentos por colección y 0 fechas como texto. 📸

### 4. Consultas
```bash
mongosh "TU_MONGO_URI" --file mongosh/04_consultas.js
```
12 consultas con filtros, proyecciones, ordenamientos, `$in`, `$all`, `$or`, `$match`, `$group`, `$lookup`
(incluido `$lookup` con `let/pipeline`), `$unwind`, `$unionWith`, `$facet`, `$hour`, `$switch` y dos `updateMany`.
Cada una indica el requerimiento de negocio que responde. 📸 una por consulta (puedes pegarlas una a una en Compass → *Mongosh*).

### 5. Optimización con índices
```bash
python scripts/05_optimizacion_indices.py
```
Corre `explain("executionStats")` **antes y después** de crear 8 índices y compara `docsExamined`, `keysExamined`,
plan (`COLLSCAN` → `IXSCAN`) y tiempos. Guarda `evidencias/05_explain_antes_despues.json`. 📸

Versión mongosh para la captura:
```js
use contentflow
db.usuarios.find({dispositivo:"Móvil", fecha_registro:{$gte:ISODate("2025-01-01")}}).sort({fecha_registro:-1}).explain("executionStats")
```

### 6. CRUD
```bash
python scripts/06_crud.py
```
Simula: registro de usuaria → publicación → reacciones/comentarios → campaña (CREATE), lectura con `$lookup` (READ),
edición, `$inc`, `$push`, `$addToSet`, `update_many` (UPDATE), intentos de datos inválidos rechazados, y baja de
cuenta con **borrado en cascada dentro de una transacción** (DELETE). Deja la base como estaba. 📸

### 7. Calidad de datos
```bash
python scripts/07_calidad_datos.py
```
Detecta duplicados, referencias inválidas e inconsistencias de fechas; corrige y genera
`evidencias/07_calidad_datos.md`. Ejecútalo dos veces: la segunda debe mostrar 0 duplicados. 📸

### 8 y 9. API REST + validaciones
```bash
uvicorn api.main:app --reload --port 8000
```
- Swagger: <http://localhost:8000/docs> 📸
- Lectura **y escritura** en `usuarios`, `publicaciones`, `reacciones` y `comentarios`; lectura/reportes de `campanas`.
- Validación de entradas con Pydantic (422), referencias inexistentes (404), duplicados (409), rango inválido (400),
  base caída (503), errores no controlados (500). Todas las respuestas de error tienen el mismo formato y `request_id`.
- Cada petición queda en `logs/api.log` con request_id, método, ruta, estado y duración. 📸

| Método | Ruta | Descripción |
|---|---|---|
| GET | `/health` | Ping a Atlas + latencia |
| GET/POST | `/usuarios` | Listar (filtros, paginación) / registrar |
| GET/PATCH/DELETE | `/usuarios/{id}` | Ver / editar / eliminar en cascada (transacción) |
| GET/POST | `/publicaciones` | Listar (categoría, tipo, hashtag, fechas, orden) / crear |
| GET/PATCH/DELETE | `/publicaciones/{id}` | Detalle con interacciones / editar / eliminar |
| GET/POST | `/reacciones` | Listar / reaccionar (1 por usuario y publicación) |
| DELETE | `/reacciones/{id}` | Quitar reacción |
| GET/POST | `/comentarios` | Listar / comentar |
| PATCH | `/comentarios/{id}/likes` | Sumar likes (`$inc`) |
| DELETE | `/comentarios/{id}` | Eliminar |
| GET | `/reportes/usuarios-activos` | Top usuarios |
| GET | `/reportes/publicaciones-populares` | Top publicaciones |
| GET | `/campanas`, `/campanas/{id}/rendimiento` | Campañas y cumplimiento de metas |

**Postman:** *Import* → `postman/ContentFlow_API.postman_collection.json` → *Run collection*. Deben pasar los 71 tests. 📸

### 10. Documentar y entregar
- Subir este repositorio a GitHub (**sin** el `.env`).
- Informe PDF con las capturas de cada paso.

```bash
git init
git add .
git commit -m "EP2 ContentFlow MongoDB Atlas"
git branch -M main
git remote add origin https://github.com/TU_USUARIO/contentflow-mongodb.git
git push -u origin main
```
