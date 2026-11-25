# Registro de decisiones del Entregable 2 (AWS)

Registro de desviaciones respecto del Entregable 1 y del documento fuente `PgGuardian - Requisitos del Entregable 2 (AWS).md` (Requirement 24, CA-27). Cada entrada tiene los campos `requisito_afectado`, `cambio`, `justificacion`, `fecha` (AAAA-MM-DD) y `aprobador`. Una entrada sin alguno de esos campos o sin aprobación anotada en la especificación se considera no aprobada (R24.9).

Este archivo se creó en la tarea 1.10 con la entrada R24.7. La tarea 9.4 (T-26) agrega las entradas R24.1 a R24.6, la columna de aprobación y la lista de cierre de T-26.

## Entradas

### R24.7: llamadas del Frontend a endpoints de TiendaDB

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | hallazgo del despliegue, sin RF ni CA en la fuente |
| `cambio` | Las llamadas del Frontend a `/api/full-scan` se condicionan a la variable de build de Vite `VITE_ENABLE_TIENDADB_SCAN`. Solo con el valor `"true"` se ejecutan. El build de producción (`frontend/Dockerfile.prod`, `vite build`) no la define, así que no hace esas solicitudes. En producción también se ocultan el botón «Ejecutar Escaneo» y el interruptor «Actualización automática (30 s)», y la pestaña «TiendaDB (Local)» no queda en estado de carga. Las funciones de `frontend/src/api/pgguardian.js` no se borran. |
| `justificacion` | En el backend, `/api/full-scan` y los routers `/api/bloat`, `/api/config`, `/api/health`, `/api/indexes` y `/api/queries` usan `get_connection()`, que conecta a TiendaDB. TiendaDB solo existe en el entorno de desarrollo (`docker-compose.yml`), así que en AWS esas llamadas fallarían al iniciar sesión y cada 30 s por la actualización automática (Requirement 26). |
| `fecha` | 2026-11-24 |
| `aprobador` | *pendiente* (se anota en la especificación en un máximo de 2 días hábiles, R24.8) |

**Resultado de la revisión (R26.1).** Búsqueda en `frontend/src` de las funciones de `pgguardian.js` de los seis prefijos:

| Función (`pgguardian.js`) | Endpoint | Invocada desde | ¿Se ejecutaba en producción? |
| --- | --- | --- | --- |
| `fullScan` | `/api/full-scan` | `App.jsx`, efecto inicial tras iniciar sesión | Sí, una vez al iniciar sesión o recargar con sesión activa |
| `fullScan` | `/api/full-scan` | `App.jsx`, `runScan`, llamado por el botón «Ejecutar Escaneo» | Sí, al pulsar el botón |
| `fullScan` | `/api/full-scan` | `App.jsx`, `runScan`, llamado por el intervalo de actualización automática (activada por defecto) | Sí, cada 30 s con sesión activa |
| `getTableBloat`, `getDisabledAutovacuum`, `getDeadTuples` | `/api/bloat/*` | Ningún componente | No |
| `getWorkMem`, `evaluateWorkMem`, `getSharedBuffers`, `evaluateSharedBuffers`, `evaluatePgStatMax`, `getPgStatLimit`, `getSlowQueryLogging` | `/api/config/*` | Ningún componente | No |
| `getPartitioningCandidates`, `getIdleInTransaction` | `/api/health/*` | Ningún componente | No |
| `getMissingPartialIndexes`, `getMissingIndexes`, `getDuplicateIndexes`, `getUnusedIndexes`, `getCoveringCandidates`, `getObsoleteStats`, `getLeadingWildcards` | `/api/indexes/*` | Ningún componente | No |
| `getPgStatStatus`, `getTempSpills`, `getSeqScans`, `getTopTimeQueries`, `getDatabaseTempUsage`, `getExplainSpills` | `/api/queries/*` | Ningún componente | No |

Las páginas `BloatPage`, `ConfigPage`, `HealthPage`, `IndexesPage` y `QueriesPage` no llaman a la API: muestran el `scanData` de la pestaña activa. `/api/health-check` (`healthCheck`) queda fuera de este hallazgo porque en producción usa App_DB (Requirement 6).

**Cambio aplicado (R26.2):**

- `frontend/src/config/features.js`: exporta `TIENDADB_SCAN_ENABLED`, verdadero solo si `import.meta.env.VITE_ENABLE_TIENDADB_SCAN === 'true'`.
- `frontend/src/App.jsx`: el efecto inicial, `runScan` y el intervalo de actualización automática no llaman a `fullScan()` si la bandera está desactivada. El botón «Ejecutar Escaneo» y el interruptor de actualización automática solo se muestran con la bandera activa. La pestaña local se crea sin estado de carga cuando la bandera está desactivada.
- `frontend/src/pages/Overview.jsx`: con la bandera desactivada, el mensaje sin datos remite a «Nuevo análisis» en lugar de a «Ejecutar Escaneo».
- `frontend/.env.development`: define `VITE_ENABLE_TIENDADB_SCAN=true`. Vite solo carga este archivo en modo desarrollo (`npm run dev`, contenedor `frontend` de `docker-compose.yml`), así que el entorno con TiendaDB conserva el escaneo y `vite build` no lo lee.

**Comprobación del build.** Tras `npm run build` (modo producción), el bundle `dist/assets/index-*.js` contiene 0 apariciones de `/full-scan`, `/bloat/`, `/config/`, `/health/`, `/indexes/`, `/queries/` y del texto «Ejecutar Escaneo»: Vite elimina ese código como inalcanzable. Un build con `--mode development` sí contiene `/full-scan`. La verificación en navegador de R26.3 (pestaña Red con 0 solicitudes a esos prefijos al recorrer login, registro y análisis) queda para el despliegue.
