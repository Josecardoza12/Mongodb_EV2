// =====================================================================
// PASO 4 - Consultas de negocio para ContentFlow (Forma A)
//
// CÓMO USARLO EN COMPASS:
//   Copia UN bloque a la vez (desde la línea "// ----- Cn." hasta antes
//   del siguiente "// -----"), pégalo en la consola Mongosh y presiona Enter.
//   Cada bloque funciona solo: no necesitas pegar nada antes.
//
// O ejecutar todo de una vez desde la terminal:
//   mongosh "TU_MONGO_URI" --file mongosh/04_consultas.js
// =====================================================================

// ---------------------------------------------------------------------
// C1. FILTRO + PROYECCIÓN + ORDEN
// Negocio: Marketing quiere los usuarios que se registraron en 2025 desde
// un celular, los más recientes primero, para una campaña mobile.
// ---------------------------------------------------------------------
db = db.getSiblingDB("contentflow");
print("\n======================================================================");
print("CONSULTA 1: Usuarios móviles registrados en 2025 (más recientes primero)");
print("======================================================================");
printjson(
  db.usuarios
    .find(
      { dispositivo: "Móvil", fecha_registro: { $gte: ISODate("2025-01-01"), $lt: ISODate("2026-01-01") } },
      { _id: 0, nombre: 1, pais: 1, fecha_registro: 1 }
    )
    .sort({ fecha_registro: -1 })
    .limit(10)
    .toArray()
);
print("Total que cumplen el filtro: " +
  db.usuarios.countDocuments({ dispositivo: "Móvil", fecha_registro: { $gte: ISODate("2025-01-01"), $lt: ISODate("2026-01-01") } }));

// ---------------------------------------------------------------------
// C2. BÚSQUEDA COMPUESTA ($and, $in, $all, rango de fechas)
// Negocio: contenido audiovisual de Tecnología con #innovacion publicado
// en el segundo trimestre 2025.
// ---------------------------------------------------------------------
db = db.getSiblingDB("contentflow");
print("\n======================================================================");
print("CONSULTA 2: Publicaciones Video/Imagen de Tecnología con #innovacion (Q2 2025)");
print("======================================================================");
printjson(
  db.publicaciones
    .find(
      {
        $and: [
          { categoria: "Tecnología" },
          { tipo: { $in: ["Video", "Imagen"] } },
          { hashtags: { $all: ["#innovacion"] } },
          { fecha_publicacion: { $gte: ISODate("2025-04-01"), $lt: ISODate("2025-07-01") } },
        ],
      },
      { contenido: 0 }
    )
    .sort({ fecha_publicacion: 1 })
    .toArray()
);

// ---------------------------------------------------------------------
// C3. FILTRO CON $or + $gte + ORDEN + LÍMITE
// Negocio: comentarios destacados (90+ likes) o muy recientes con 50+.
// ---------------------------------------------------------------------
db = db.getSiblingDB("contentflow");
print("\n======================================================================");
print("CONSULTA 3: Comentarios destacados (top 10 por likes)");
print("======================================================================");
printjson(
  db.comentarios
    .find(
      { $or: [{ likes: { $gte: 90 } }, { fecha: { $gte: ISODate("2025-07-01") }, likes: { $gte: 50 } }] },
      { _id: 1, usuario_id: 1, publicacion_id: 1, likes: 1, fecha: 1 }
    )
    .sort({ likes: -1, fecha: -1 })
    .limit(10)
    .toArray()
);

// ---------------------------------------------------------------------
// C4. AGREGACIÓN ($unionWith, $group, $lookup, $sort)
// Negocio: TOP 10 usuarios más activos (publicaciones + reacciones +
// comentarios). Sirve para programas de fidelización.
// ---------------------------------------------------------------------
db = db.getSiblingDB("contentflow");
print("\n======================================================================");
print("CONSULTA 4: Top 10 usuarios más activos");
print("======================================================================");
printjson(
  db.publicaciones.aggregate([
    { $project: { usuario_id: 1, tipo: { $literal: "publicacion" } } },
    { $unionWith: { coll: "reacciones", pipeline: [{ $project: { usuario_id: 1, tipo: { $literal: "reaccion" } } }] } },
    { $unionWith: { coll: "comentarios", pipeline: [{ $project: { usuario_id: 1, tipo: { $literal: "comentario" } } }] } },
    {
      $group: {
        _id: "$usuario_id",
        publicaciones: { $sum: { $cond: [{ $eq: ["$tipo", "publicacion"] }, 1, 0] } },
        reacciones: { $sum: { $cond: [{ $eq: ["$tipo", "reaccion"] }, 1, 0] } },
        comentarios: { $sum: { $cond: [{ $eq: ["$tipo", "comentario"] }, 1, 0] } },
        total_actividad: { $sum: 1 },
      },
    },
    { $sort: { total_actividad: -1, _id: 1 } },
    { $limit: 10 },
    { $lookup: { from: "usuarios", localField: "_id", foreignField: "_id", as: "usuario" } },
    { $unwind: "$usuario" },
    {
      $project: {
        _id: 0, usuario_id: "$_id", nombre: "$usuario.nombre", pais: "$usuario.pais",
        dispositivo: "$usuario.dispositivo", publicaciones: 1, reacciones: 1, comentarios: 1, total_actividad: 1,
      },
    },
  ]).toArray()
);

// ---------------------------------------------------------------------
// C5. AGREGACIÓN ($lookup con pipeline, $size, $sum, $addFields)
// Negocio: TOP 10 publicaciones más populares.
// engagement = reacciones + comentarios + likes recibidos en comentarios
// ---------------------------------------------------------------------
db = db.getSiblingDB("contentflow");
print("\n======================================================================");
print("CONSULTA 5: Top 10 publicaciones más populares");
print("======================================================================");
printjson(
  db.publicaciones.aggregate([
    { $lookup: { from: "reacciones", localField: "_id", foreignField: "publicacion_id", as: "reacs" } },
    { $lookup: { from: "comentarios", localField: "_id", foreignField: "publicacion_id", as: "coms" } },
    {
      $addFields: {
        n_reacciones: { $size: "$reacs" },
        n_comentarios: { $size: "$coms" },
        likes_comentarios: { $sum: "$coms.likes" },
      },
    },
    { $addFields: { engagement: { $add: ["$n_reacciones", "$n_comentarios", "$likes_comentarios"] } } },
    { $sort: { engagement: -1 } },
    { $limit: 10 },
    { $project: { reacs: 0, coms: 0, contenido: 0 } },
  ]).toArray()
);

// ---------------------------------------------------------------------
// C6. AGREGACIÓN POR HORARIO ($hour, $bucket-like con $switch)
// Negocio: ¿a qué hora conviene publicar? Engagement promedio por franja.
// ---------------------------------------------------------------------
db = db.getSiblingDB("contentflow");
print("\n======================================================================");
print("CONSULTA 6: Engagement promedio por franja horaria de publicación");
print("======================================================================");
printjson(
  db.publicaciones.aggregate([
    { $lookup: { from: "reacciones", localField: "_id", foreignField: "publicacion_id", as: "r" } },
    { $lookup: { from: "comentarios", localField: "_id", foreignField: "publicacion_id", as: "c" } },
    {
      $project: {
        hora: { $hour: "$fecha_publicacion" },
        interacciones: { $add: [{ $size: "$r" }, { $size: "$c" }] },
      },
    },
    {
      $addFields: {
        franja: {
          $switch: {
            branches: [
              { case: { $lt: ["$hora", 6] }, then: "1. Madrugada (00-05)" },
              { case: { $lt: ["$hora", 12] }, then: "2. Mañana (06-11)" },
              { case: { $lt: ["$hora", 18] }, then: "3. Tarde (12-17)" },
            ],
            default: "4. Noche (18-23)",
          },
        },
      },
    },
    {
      $group: {
        _id: "$franja",
        publicaciones: { $sum: 1 },
        interacciones_totales: { $sum: "$interacciones" },
        promedio_por_publicacion: { $avg: "$interacciones" },
      },
    },
    { $addFields: { promedio_por_publicacion: { $round: ["$promedio_por_publicacion", 2] } } },
    { $sort: { _id: 1 } },
  ]).toArray()
);

// ---------------------------------------------------------------------
// C7. AGREGACIÓN ($lookup + $group compuesto)
// Negocio: perfil de audiencia que reacciona, por dispositivo y género.
// ---------------------------------------------------------------------
db = db.getSiblingDB("contentflow");
print("\n======================================================================");
print("CONSULTA 7: Perfil de audiencia que reacciona (dispositivo x género)");
print("======================================================================");
printjson(
  db.reacciones.aggregate([
    { $lookup: { from: "usuarios", localField: "usuario_id", foreignField: "_id", as: "u" } },
    { $unwind: "$u" },
    { $group: { _id: { dispositivo: "$u.dispositivo", genero: "$u.genero" }, reacciones: { $sum: 1 } } },
    { $sort: { reacciones: -1 } },
    { $project: { _id: 0, dispositivo: "$_id.dispositivo", genero: "$_id.genero", reacciones: 1 } },
  ]).toArray()
);

// ---------------------------------------------------------------------
// C8. AGREGACIÓN ($group por 2 campos, $avg, $round)
// Negocio: qué categoría y formato rinde mejor.
// ---------------------------------------------------------------------
db = db.getSiblingDB("contentflow");
print("\n======================================================================");
print("CONSULTA 8: Rendimiento por categoría y tipo de publicación");
print("======================================================================");
printjson(
  db.publicaciones.aggregate([
    { $lookup: { from: "reacciones", localField: "_id", foreignField: "publicacion_id", as: "r" } },
    { $group: {
        _id: { categoria: "$categoria", tipo: "$tipo" },
        publicaciones: { $sum: 1 },
        reacciones: { $sum: { $size: "$r" } },
    } },
    { $addFields: { reacciones_por_pub: { $round: [{ $divide: ["$reacciones", "$publicaciones"] }, 2] } } },
    { $sort: { reacciones_por_pub: -1 } },
  ]).toArray()
);

// ---------------------------------------------------------------------
// C9. AGREGACIÓN ($unwind de arreglos + $group)
// Negocio: hashtags más usados y su alcance.
// ---------------------------------------------------------------------
db = db.getSiblingDB("contentflow");
print("\n======================================================================");
print("CONSULTA 9: Hashtags más usados");
print("======================================================================");
printjson(
  db.publicaciones.aggregate([
    { $unwind: "$hashtags" },
    { $group: { _id: "$hashtags", usos: { $sum: 1 }, categorias: { $addToSet: "$categoria" } } },
    { $sort: { usos: -1 } },
  ]).toArray()
);

// ---------------------------------------------------------------------
// C10. AGREGACIÓN AVANZADA ($lookup con let/pipeline, $in, ventana de fechas)
// Negocio: éxito de las campañas. Cuenta "Me gusta"/"Me encanta" y
// comentarios de sus publicaciones DENTRO del periodo de la campaña y los
// compara con la meta. (El dataset no registra "compartidos".)
// ---------------------------------------------------------------------
db = db.getSiblingDB("contentflow");
print("\n======================================================================");
print("CONSULTA 10: Cumplimiento de metas de campañas (top 10 por % likes)");
print("======================================================================");
printjson(
  db.campanas.aggregate([
    {
      $lookup: {
        from: "reacciones",
        let: { pubs: "$publicaciones_asociadas", ini: "$fecha_inicio", fin: "$fecha_fin" },
        pipeline: [
          { $match: { $expr: { $and: [
            { $in: ["$publicacion_id", "$$pubs"] },
            { $in: ["$tipo_reaccion", ["Me gusta", "Me encanta"]] },
            { $gte: ["$fecha", "$$ini"] }, { $lte: ["$fecha", "$$fin"] },
          ] } } },
          { $count: "n" },
        ],
        as: "likes_logrados",
      },
    },
    {
      $lookup: {
        from: "comentarios",
        let: { pubs: "$publicaciones_asociadas", ini: "$fecha_inicio", fin: "$fecha_fin" },
        pipeline: [
          { $match: { $expr: { $and: [
            { $in: ["$publicacion_id", "$$pubs"] },
            { $gte: ["$fecha", "$$ini"] }, { $lte: ["$fecha", "$$fin"] },
          ] } } },
          { $count: "n" },
        ],
        as: "comentarios_logrados",
      },
    },
    {
      $project: {
        nombre: 1, objetivo: 1,
        n_publicaciones: { $size: "$publicaciones_asociadas" },
        meta_likes: "$metricas_objetivo.likes",
        likes: { $ifNull: [{ $first: "$likes_logrados.n" }, 0] },
        meta_comentarios: "$metricas_objetivo.comentarios",
        comentarios: { $ifNull: [{ $first: "$comentarios_logrados.n" }, 0] },
      },
    },
    {
      $addFields: {
        pct_likes: { $round: [{ $multiply: [{ $divide: ["$likes", "$meta_likes"] }, 100] }, 2] },
        pct_comentarios: { $round: [{ $multiply: [{ $divide: ["$comentarios", "$meta_comentarios"] }, 100] }, 2] },
      },
    },
    { $sort: { pct_likes: -1 } },
    { $limit: 10 },
  ]).toArray()
);

// ---------------------------------------------------------------------
// C11. $facet: varios resúmenes en una sola consulta
// Negocio: tablero rápido de sentimiento y objetivos de campañas.
// ---------------------------------------------------------------------
db = db.getSiblingDB("contentflow");
print("\n======================================================================");
print("CONSULTA 11: Resumen de sentimiento de reacciones ($facet)");
print("======================================================================");
printjson(
  db.reacciones.aggregate([
    {
      $facet: {
        por_tipo: [{ $group: { _id: "$tipo_reaccion", total: { $sum: 1 } } }, { $sort: { total: -1 } }],
        por_mes: [
          { $group: { _id: { $dateToString: { format: "%Y-%m", date: "$fecha" } }, total: { $sum: 1 } } },
          { $sort: { _id: 1 } },
        ],
      },
    },
  ]).toArray()
);

// ---------------------------------------------------------------------
// C12. CONSULTAS DE MODIFICACIÓN (updateMany con filtro)
// Negocio: marcar como "destacadas" las publicaciones con 3+ reacciones
// y cerrar las campañas cuya fecha de fin ya pasó.
// ---------------------------------------------------------------------
db = db.getSiblingDB("contentflow");
print("\n======================================================================");
print("CONSULTA 12: Modificaciones: publicaciones destacadas y campañas finalizadas");
print("======================================================================");
var destacadas = db.reacciones.aggregate([
  { $group: { _id: "$publicacion_id", n: { $sum: 1 } } },
  { $match: { n: { $gte: 3 } } },
]).toArray().map((d) => d._id);
printjson(db.publicaciones.updateMany({ _id: { $in: destacadas } }, { $set: { destacada: true } }));
printjson(db.campanas.updateMany({ fecha_fin: { $lt: new Date() } }, { $set: { estado: "finalizada" } }));
print("Publicaciones destacadas: " + db.publicaciones.countDocuments({ destacada: true }));