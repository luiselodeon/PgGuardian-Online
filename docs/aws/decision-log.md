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

**Comprobación del build.** Tras `npm run build` (modo producción), el bundle `dist/assets/index-*.js` contiene 0 apariciones de `/full-scan`, `/bloat/`, `/config/`, `/health/`, `/indexes/`, `/queries/` y del texto «Ejecutar Escaneo»: Vite elimina ese código como inalcanzable. Un build con `--mode development` sí contiene `/full-scan`. La verificación en navegador de R26.3 se hizo en local el 2026-11-24 con el build de producción: aprobada, ver la sección de R26.3 al final de esta entrada y docs/aws/evidencia/r26-3/.

**Nota: pestaña local y etiqueta TiendaDB ocultas en producción (tarea 1.11, R26.4 a R26.7).**

- `frontend/src/components/AnalysisTabs.jsx`: con `TIENDADB_SCAN_ENABLED` falso, filtra en el render las pestañas con `kind === 'local'` (`visibleTabs`) y devuelve `null` si no queda ninguna, de modo que la barra se oculta sin análisis y solo muestra las pestañas de sandbox al crear uno.
- `frontend/src/pages/Overview.jsx`: `tabTitle` por defecto pasa a `'Análisis'`. Sin sandbox activo y con la bandera falsa, la píldora muestra «Sin análisis seleccionado» y el subtítulo «Selecciona o crea un análisis para ver el resumen». Con la bandera verdadera se conservan «TiendaDB (Local · init/)» y «Resumen de salud de la base de datos local».
- `frontend/src/App.jsx` no se modificó: la pestaña local sigue en `tabs`, `LOCAL_TAB_ID` sigue siendo el valor inicial de `activeTabId` y `tabs[0]` sigue siendo el respaldo de `activeTab`, así que `activeTab` nunca queda `undefined` (R26.5).

Resultado de la verificación (2026-11-24):

| Comprobación | Método | Resultado |
| --- | --- | --- |
| Build de producción compila | `npm run build` en `frontend/` | Aprobado (código 0) |
| Filtro de la pestaña local presente | Bundle `dist/assets/index-*.js`: `e.filter(e=>e.kind!==\`local\`)` seguido de `i.length===0?null` | Aprobado |
| Sin «TiendaDB» renderizable en el Overview | Bundle de producción: «TiendaDB (Local · init/)» 0 veces, «base de datos local» 0 veces; la única aparición de «TiendaDB» es el `label` de la pestaña local en el estado, que no se renderiza (barra filtrada y el Overview solo usa `tabTitle` en la píldora de sandbox) | Aprobado |
| Etiqueta neutral | Bundle de producción: «Sin análisis seleccionado» y «Selecciona o crea un análisis…» presentes | Aprobado |
| Desarrollo sin cambios (R26.7) | `vite build --mode development` (lee `.env.development` con `VITE_ENABLE_TIENDADB_SCAN=true`): «TiendaDB (Local · init/)» y «Resumen de salud de la base de datos local» presentes, «Sin análisis seleccionado» ausente | Aprobado |
| Lint | `npx eslint` sobre los dos archivos | Aprobado |
| Recorrido en navegador (0 pestañas «TiendaDB (Local)», solo la del sandbox al crear uno, consola sin errores por `activeTab`) | Playwright con Chromium headless (2026-11-24), build de producción servido con ite preview contra el backend real (docker compose up: db, app_db, sandbox_db, api) | Aprobado: 0 pestañas «TiendaDB (Local)» y sin barra de pestañas sin análisis; el Overview muestra «Sin análisis seleccionado» y no contiene «TiendaDB» ni «base de datos local»; las páginas bloat, config, health, indexes, queries e history cargan sin texto «TiendaDB»; al crear un sandbox solo aparece su pestaña (también tras recargar) y al cerrarla la barra desaparece; sin errores de consola por ctiveTab (el único error es el 401 esperado de GET /api/auth/me antes de iniciar sesión). En modo desarrollo (VITE_ENABLE_TIENDADB_SCAN=true) siguen la pestaña «TiendaDB (Local)», la píldora «TiendaDB (Local · init/)» y «Resumen de salud de la base de datos local», con los mismos 401 esperados y sin otros errores |

**Verificación en navegador de R26.3 (2026-11-24).**

- Entorno: stack de producción levantado con `scripts/verify_phase1.ps1` (proyecto `pgguardian-prod`, `docker-compose.prod.yml`, `.env` local con `JWT_SECRET` definido, sin modificar). El mismo script aprobó CA-09 a CA-14 después de la tarea 1.11.
- Navegador: Chromium real con ventana (Chrome for Testing 1255, Playwright 1.65) en `http://localhost`, con DevTools abiertas en la pestaña Red, «Conservar registro» activo y filtro `/api/`.
- Flujo recorrido: registro de un usuario nuevo, cierre de sesión, inicio de sesión, «Nuevo análisis» con `scripts_prueba/01_schema.sql`, `02_seed_data.sql` y `03_plant_problems.sql`, apertura del resultado («Ver pestaña en Dashboard»), Historial y 35 s de inactividad para cubrir el intervalo de 30 s.
- Solicitudes `/api/` registradas (8): `GET /api/auth/me` 401, `POST /api/auth/register` 201, `GET /api/analyses` 200, `POST /api/auth/logout` 200, `POST /api/auth/login` 200, `GET /api/analyses` 200, `POST /api/analyses` 201, `GET /api/analyses` 200.
- Solicitudes a `/api/full-scan`, `/api/bloat`, `/api/config`, `/api/health/`, `/api/indexes` y `/api/queries`: 0. Ninguna solicitud durante los 35 s de inactividad.
- Resultado: **aprobado**.
- Evidencia: `docs/aws/evidencia/r26-3/`, con `r26-3.har` (HAR de las solicitudes `/api/`, sin cabeceras `Authorization`, `Cookie` ni `Set-Cookie` y sin los cuerpos de `/api/auth/*`), `solicitudes-api.json` (método, ruta, código y tiempo de cada solicitud, con los pasos del flujo), `red-final.png` (ventana con la pestaña Red al final del flujo) y `pagina-final.png` (vista del Historial). La pestaña Red de la captura muestra 7 solicitudes porque el primer `GET /api/auth/me` ocurrió antes de que DevTools empezara a registrar; la lista completa está en el HAR y en el JSON.

### Decisión de diseño de T-10: usuarios IAM creados en la consola

Esta entrada no corresponde a ninguno de los criterios R24.1 a R24.10: registra un cambio del diseño, no una desviación de la fuente. Usa los mismos campos y la misma regla de aprobación (R24.11, R24.12).

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | T-10 (RF-05.2, RF-05.3; Requirement 9). Cambia la forma de crear los recursos, no los criterios de verificación. |
| `cambio` | Los usuarios IAM, el grupo `PgG-Admins` y la política `Force_MFA` se crean a mano en la consola, como raíz y una sola vez, siguiendo la sección raíz/IAM de `docs/aws/runbook.md`. Se quita `scripts/aws/setup_iam.sh` de la lista de scripts de C14 del diseño. |
| `justificacion` | Con pocos usuarios, la consola evita dejar contraseñas en el historial de la shell, y la contraseña de acceso a la consola tiene que asignarse ahí de todas formas. |
| `fecha` | 2026-11-25 |
| `aprobador` | *pendiente* (se anota en la especificación en un máximo de 2 días hábiles, R24.11) |

### Monitor de anomalías por defecto reemplazado por el del stack

Esta entrada no corresponde a ninguno de los criterios R24.1 a R24.10: registra un cambio del diseño, no una desviación de la fuente. Usa los mismos campos y la misma regla de aprobación (R24.11, R24.12).

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | R21 / RF-07.2 (Cost Anomaly Detection) y R29 (stack `pgguardian`). Cambia el estado previo de la cuenta, no los criterios de verificación. |
| `cambio` | Antes del primer despliegue del stack se borran el monitor de servicios por defecto de la cuenta (`Default-Services-Monitor`) y su suscripción (`Default-Services-Subscription`, umbral 100 USD y 40 %), después de guardar como evidencia en `docs/aws/evidencia/stack/` la salida de `get-anomaly-monitors` y `get-anomaly-subscriptions` (procedimiento en `docs/aws/runbook.md`, paso 2.1.3). Su lugar lo ocupa el monitor `DIMENSIONAL` de servicio del stack (o el de `scripts/aws/create_anomaly_detection.sh` si se activa el plan B). Al borrar el stack, la cuenta queda sin monitor de anomalías. |
| `justificacion` | AWS permite un solo monitor de servicios por cuenta, así que el del stack no puede crearse mientras exista el por defecto. Además, el umbral por defecto (100 USD y 40 %) no avisaría con el gasto esperado, de unos 22 USD al mes. |
| `fecha` | 2026-11-25 |
| `aprobador` | *pendiente* (se anota en la especificación en un máximo de 2 días hábiles, R24.11) |

### Código en la Instancia: clon por HTTPS (repositorio público)

Esta entrada no corresponde a ninguno de los criterios R24.1 a R24.10: registra un cambio del diseño, no una desviación de la fuente. Usa los mismos campos y la misma regla de aprobación (R24.11, R24.12).

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | T-17 y sección 5 del runbook (cómo llega el código a la Instancia). R10.2 y R19.2 como límite: sin claves de AWS ni secretos en el repositorio. No cambia criterios de verificación. |
| `cambio` | Se usa la variante A del runbook 5.1: clon por HTTPS del repositorio público `https://github.com/luiselodeon/PgGuardian-Online`. La rama es `e2-fase4` por ahora y pasa a `master` al fusionar las PR. La variante B (clon por SSH con una deploy key de solo lectura, limitada a este repositorio) queda documentada en el runbook 5.1 como alternativa si el repositorio vuelve a ser privado. |
| `justificacion` | El 2026-11-26 el repositorio `luiselodeon/PgGuardian-Online` se hizo público. Con el repositorio público, el clon por HTTPS no necesita credenciales en la Instancia: no queda ninguna clave ni token que guardar, rotar o revocar. El mismo día, después de hacerlo público, se revisó el historial completo (git log -p --all --no-textconv) en busca de claves AWS, llaves privadas, tokens de GitHub, archivos .env y contraseñas: sin hallazgos de secretos reales (solo placeholders, valores por defecto de desarrollo y datos de prueba). Alternativas: (B) deploy key de solo lectura por SSH, necesaria solo si el repositorio es privado; (C) token personal (PAT), que tiene más alcance y queda ligado a un usuario. |
| `fecha` | 2026-11-26 |
| `aprobador` | *pendiente* (se anota en la especificación en un máximo de 2 días hábiles, R24.11) |

### CA-06: /api/full-scan devolvía 500 sin cookie

Esta entrada no corresponde a ninguno de los criterios R24.1 a R24.10: registra un hallazgo del despliegue, no una desviación de la fuente. Usa los mismos campos y la misma regla de aprobación (R24.11, R24.12).

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | Hallazgo del despliegue, CA-06 (sin sesión, los endpoints protegidos responden 401). No cambia criterios de verificación. |
| `cambio` | En `backend/api/main.py`, la autenticación de `/api/full-scan` pasa al parámetro `dependencies=[Depends(get_current_user)]` del decorador y la función solo recibe `conn=Depends(get_connection)`. Se agrega `backend/tests/test_full_scan_auth.py`, que comprueba 401 sin cookie aunque `get_connection` falle. |
| `justificacion` | FastAPI resolvía `get_connection` antes que `get_current_user` por el orden de los parámetros; sin cookie intentaba conectar a TiendaDB, que no existe en producción, y respondía 500 en lugar de 401. Las dependencias de la ruta se resuelven antes que las de la función. Limitación conocida: con sesión, `/api/full-scan` sigue fallando en producción porque escanea TiendaDB, que solo existe en desarrollo (`docker-compose.yml`); la interfaz de producción no lo llama (ver entrada R24.7). |
| `fecha` | 2026-11-26 |
| `aprobador` | *pendiente* (se anota en la especificación en un máximo de 2 días hábiles, R24.11) |
