# Informe de calidad de datos - ContentFlow

Generado: 2026-11-07 13:46:55

| Categoría | Regla revisada | Colección | Casos | Acción |
|---|---|---|---|---|
| Duplicado | Correos de usuario repetidos | usuarios | 0 | Índice único uq_correo (paso 5) |
| Duplicado | Reacciones repetidas (mismo usuario y publicación) | reacciones | 0 | Se conserva la más antigua, el resto a 'cuarentena' + índice único |
| Duplicado | Comentarios idénticos repetidos | comentarios | 0 | Se conserva el más antiguo, el resto a 'cuarentena' |
| Duplicado | Publicaciones con hashtags repetidos en el arreglo | publicaciones | 0 | Se deja un solo valor por hashtag |
| Referencia | publicaciones.usuario_id que no existe en usuarios | publicaciones | 0 | Se enviarían a 'cuarentena' |
| Referencia | reacciones.usuario_id que no existe en usuarios | reacciones | 0 | Se enviarían a 'cuarentena' |
| Referencia | reacciones.publicacion_id que no existe en publicaciones | reacciones | 0 | Se enviarían a 'cuarentena' |
| Referencia | comentarios.usuario_id que no existe en usuarios | comentarios | 0 | Se enviarían a 'cuarentena' |
| Referencia | comentarios.publicacion_id que no existe en publicaciones | comentarios | 0 | Se enviarían a 'cuarentena' |
| Referencia | campanas.publicaciones_asociadas inexistentes | campanas | 0 | Se quitarían con $pull |
| Inconsistencia | Reacciones con fecha anterior a la publicación | reacciones | 245 | Marcadas calidad.flags=['fecha_antes_publicacion'] |
| Inconsistencia | Comentarios con fecha anterior a la publicación | comentarios | 251 | Marcados calidad.flags=['fecha_antes_publicacion'] |
| Inconsistencia | Publicaciones anteriores al registro del autor | publicaciones | 48 | Marcadas calidad.flags=['publicada_antes_registro'] |
| Inconsistencia | Campañas con fecha_fin < fecha_inicio | campanas | 0 | Se corregiría intercambiando |
| Inconsistencia | Textos de usuario con espacios al inicio/fin | usuarios | 0 | Se aplicaría $trim |

**Correcciones:** 0 duplicados movidos a `cuarentena`; índice único `uq_reaccion_usuario_publicacion`; 544 documentos marcados con `calidad.flags` para excluirlos de análisis por fecha.

Para analizar solo datos consistentes: `{ "calidad.flags": { $exists: false } }`
