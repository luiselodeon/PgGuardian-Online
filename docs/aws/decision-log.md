# Registro de decisiones del Entregable 2 (AWS)

Registro de desviaciones respecto del Entregable 1 y del documento fuente `PgGuardian - Requisitos del Entregable 2 (AWS).md` (Requirement 24, CA-27). Cada entrada tiene los campos `requisito_afectado`, `cambio`, `justificacion`, `fecha` (AAAA-MM-DD) y `aprobador`. La aprobación de cada entrada (nombre y fecha AAAA-MM-DD) se anota en un máximo de 2 días hábiles desde la fecha de la entrada (R24.11), en la sección «Aprobaciones» al final de este archivo. Una entrada sin alguno de esos campos o sin aprobación anotada se considera no aprobada (R24.12).

Este archivo se creó en la tarea 1.10 con la entrada R24.7 y se amplió con las decisiones de diseño y hallazgos de las fases 2 a 4. La tarea 9.4 (T-26) agrega las entradas R24.1 a R24.6 y R24.8 a R24.10, la sección «Aprobaciones» y la lista de cierre de T-26.

## Entradas

### R24.1: disco propio del sandbox

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | RF-01.4 (E1), reforzado por RF-04.4 (Requirement 4) |
| `cambio` | Sandbox_DB guarda sus datos en un volumen EBS propio (Volumen_Sandbox: gp3 cifrado de 8 GB montado en `/srv/sandbox`), separado del disco raíz donde están App_DB y el resto de los contenedores. En el E1 el aislamiento del sandbox era solo de contenedor y compartía disco con `app_db`. |
| `justificacion` | Un script que llena el disco no puede tumbar `app_db`. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |

### R24.2: Session Manager con el puerto 22 cerrado

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | RF-03.3 (E1), reemplazado por RF-05.5 (Requirement 11) |
| `cambio` | La administración del servidor se hace con AWS Systems Manager Session Manager en lugar de SSH. La Instancia se lanza sin par de llaves (`KeyName` vacío) y el Security_Group no tiene ninguna regla de entrada TCP/22. En el E1, RF-03.3 preveía SSH restringido a las IP del Equipo. |
| `justificacion` | Las IP domésticas cambian. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |

### R24.3: encendido y apagado de la Instancia (sustituye a RF-03.6)

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | RF-03.6 (E1), sustituido |
| `cambio` | La instancia se enciende o se detiene a criterio del Equipo; no es requisito que esté disponible 24/7 ni que se detenga fuera de las demostraciones. |
| `justificacion` | El peor caso (24/7, unos 22 USD al mes) cabe en los créditos de 100 USD, y el Presupuesto (R20) avisa si el gasto se desvía. La evaluación se hace con el documento y capturas de pantalla desde la URL pública (R25.5 admite capturas), no con acceso en vivo. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |

### R24.4: respaldos con snapshots manuales

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | RF-07.4 y CA-26 (Requirement 23) |
| `cambio` | Los respaldos se hacen con dos Snapshot_Manual por disco (disco raíz y Volumen_Sandbox), creados a mano desde la consola o la CLI, en lugar de una política de Amazon Data Lifecycle Manager. No se realiza prueba de restauración; CA-26 se verifica con los snapshots en estado `completed`. |
| `justificacion` | Con dos discos y un periodo de evaluación corto, dos snapshots manuales por disco bastan para tener un punto de recuperación, y evitan configurar y luego borrar una política de DLM. La prueba de restauración se omite para no crear volúmenes e instancias adicionales con costo. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |

### R24.5: miembros de `PgG-Admins`

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | RF-05.3 (Requirement 9) |
| `cambio` | El Grupo_Admins (`PgG-Admins`) tiene como miembros a los integrantes del Equipo, cada uno con su Usuario_IAM, en lugar de exactamente dos usuarios. |
| `justificacion` | Cada integrante necesita su propio Usuario_IAM con MFA para operar sin compartir credenciales; fijar exactamente dos usuarios obligaría a compartir cuentas o a dejar integrantes sin acceso. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |

### R24.6: CA-16 sin prueba con usuario sin MFA

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | CA-16 (Requirement 9) |
| `cambio` | Se omite la prueba con un Usuario_IAM sin MFA. CA-16 se verifica con el reporte de credenciales de IAM (`aws iam generate-credential-report` / `get-credential-report`, columna `mfa_active`) y con la definición de la Politica_Force_MFA adjunta a `PgG-Admins` (`docs/aws/iam/force-mfa-policy.json`). |
| `justificacion` | La prueba exigiría crear un Usuario_IAM sin MFA con contraseña de consola, lo que abre temporalmente un acceso débil a la cuenta. El reporte de credenciales (línea CA-15 R9 de verificacion-iam.jsonl) muestra qué usuarios tienen MFA; mientras un integrante no lo active, Force_MFA le deniega toda acción salvo registrar su MFA, y la política muestra que se deniegan las acciones sin MFA. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |

### R24.7: llamadas del Frontend a endpoints de TiendaDB

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | hallazgo del despliegue, sin RF ni CA en la fuente |
| `cambio` | Las llamadas del Frontend a `/api/full-scan` se condicionan a la variable de build de Vite `VITE_ENABLE_TIENDADB_SCAN`. Solo con el valor `"true"` se ejecutan. El build de producción (`frontend/Dockerfile.prod`, `vite build`) no la define, así que no hace esas solicitudes. En producción también se ocultan el botón «Ejecutar Escaneo» y el interruptor «Actualización automática (30 s)», y la pestaña «TiendaDB (Local)» no queda en estado de carga. Las funciones de `frontend/src/api/pgguardian.js` no se borran. |
| `justificacion` | En el backend, `/api/full-scan` y los routers `/api/bloat`, `/api/config`, `/api/health`, `/api/indexes` y `/api/queries` usan `get_connection()`, que conecta a TiendaDB. TiendaDB solo existe en el entorno de desarrollo (`docker-compose.yml`), así que en AWS esas llamadas fallarían al iniciar sesión y cada 30 s por la actualización automática (Requirement 26). |
| `fecha` | 2026-11-24 |
| `aprobador` | Chus Avila (2026-11-26) |

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

### R24.8: CloudFormation para la infraestructura

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | Documento de cambios de la fuente («Debería»); Requirement 29 (stack `pgguardian`, T-11 a T-15 y T-19 a T-21) |
| `cambio` | CloudFormation en lugar de scripts de CLI para la infraestructura. |
| `justificacion` | Creación y borrado reproducibles en un solo stack; herramienta vista en el curso; estaba como 'Debería' en el documento de cambios. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |

### R24.9: alcance del E2

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | Alcance del E2 en la práctica de definición de requisitos |
| `cambio` | El E2 pasa de 'multi-cliente con registro de usuarios y de bases propias' a 'despliegue en AWS'; el registro de usuarios se entregó en el E1 y la conexión a bases propias del cliente pasa a Mejoras futuras. |
| `justificacion` | Decisión del Equipo: E1 = desarrollo, E2 = despliegue. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |

### R24.10: aviso de anomalías como resumen diario

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | R21.2 / RF-07.2 |
| `cambio` | El aviso de anomalías pasa de ≤ 60 minutos a un resumen diario por correo. |
| `justificacion` | El correo directo de Cost Anomaly Detection solo admite frecuencia diaria o semanal; el aviso inmediato requiere SNS, y el Presupuesto (R20) ya alerta por correo. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |

### Decisión de diseño de T-10: usuarios IAM creados en la consola

Esta entrada no corresponde a ninguno de los criterios R24.1 a R24.10: registra un cambio del diseño, no una desviación de la fuente. Usa los mismos campos y la misma regla de aprobación (R24.11, R24.12).

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | T-10 (RF-05.2, RF-05.3; Requirement 9). Cambia la forma de crear los recursos, no los criterios de verificación. |
| `cambio` | Los usuarios IAM, el grupo `PgG-Admins` y la política `Force_MFA` se crean a mano en la consola, como raíz y una sola vez, siguiendo la sección raíz/IAM de `docs/aws/runbook.md`. Se quita `scripts/aws/setup_iam.sh` de la lista de scripts de C14 del diseño. |
| `justificacion` | Con pocos usuarios, la consola evita dejar contraseñas en el historial de la shell, y la contraseña de acceso a la consola tiene que asignarse ahí de todas formas. |
| `fecha` | 2026-11-25 |
| `aprobador` | Chus Avila (2026-11-26) |

### Monitor de anomalías por defecto reemplazado por el del stack

Esta entrada no corresponde a ninguno de los criterios R24.1 a R24.10: registra un cambio del diseño, no una desviación de la fuente. Usa los mismos campos y la misma regla de aprobación (R24.11, R24.12).

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | R21 / RF-07.2 (Cost Anomaly Detection) y R29 (stack `pgguardian`). Cambia el estado previo de la cuenta, no los criterios de verificación. |
| `cambio` | Antes del primer despliegue del stack se borran el monitor de servicios por defecto de la cuenta (`Default-Services-Monitor`) y su suscripción (`Default-Services-Subscription`, umbral 100 USD y 40 %), después de guardar como evidencia en `docs/aws/evidencia/stack/` la salida de `get-anomaly-monitors` y `get-anomaly-subscriptions` (procedimiento en `docs/aws/runbook.md`, paso 2.1.3). Su lugar lo ocupa el monitor `DIMENSIONAL` de servicio del stack (o el de `scripts/aws/create_anomaly_detection.sh` si se activa el plan B). Al borrar el stack, la cuenta queda sin monitor de anomalías. |
| `justificacion` | AWS permite un solo monitor de servicios por cuenta, así que el del stack no puede crearse mientras exista el por defecto. Además, el umbral por defecto (100 USD y 40 %) no avisaría con el gasto esperado, de unos 22 USD al mes. |
| `fecha` | 2026-11-25 |
| `aprobador` | Chus Avila (2026-11-26) |

### Código en la Instancia: clon por HTTPS (repositorio público)

Esta entrada no corresponde a ninguno de los criterios R24.1 a R24.10: registra un cambio del diseño, no una desviación de la fuente. Usa los mismos campos y la misma regla de aprobación (R24.11, R24.12).

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | T-17 y sección 5 del runbook (cómo llega el código a la Instancia). R10.2 y R19.2 como límite: sin claves de AWS ni secretos en el repositorio. No cambia criterios de verificación. |
| `cambio` | Se usa la variante A del runbook 5.1: clon por HTTPS del repositorio público `https://github.com/luiselodeon/PgGuardian-Online`. La rama es `e2-fase4` por ahora y pasa a `master` al fusionar las PR. La variante B (clon por SSH con una deploy key de solo lectura, limitada a este repositorio) queda documentada en el runbook 5.1 como alternativa si el repositorio vuelve a ser privado. |
| `justificacion` | El 2026-11-26 el repositorio `luiselodeon/PgGuardian-Online` se hizo público. Con el repositorio público, el clon por HTTPS no necesita credenciales en la Instancia: no queda ninguna clave ni token que guardar, rotar o revocar. El mismo día, después de hacerlo público, se revisó el historial completo (git log -p --all --no-textconv) en busca de claves AWS, llaves privadas, tokens de GitHub, archivos .env y contraseñas: sin hallazgos de secretos reales (solo placeholders, valores por defecto de desarrollo y datos de prueba). Alternativas: (B) deploy key de solo lectura por SSH, necesaria solo si el repositorio es privado; (C) token personal (PAT), que tiene más alcance y queda ligado a un usuario. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |

### CA-06: /api/full-scan devolvía 500 sin cookie

Esta entrada no corresponde a ninguno de los criterios R24.1 a R24.10: registra un hallazgo del despliegue, no una desviación de la fuente. Usa los mismos campos y la misma regla de aprobación (R24.11, R24.12).

| Campo | Valor |
| --- | --- |
| `requisito_afectado` | Hallazgo del despliegue, CA-06 (sin sesión, los endpoints protegidos responden 401). No cambia criterios de verificación. |
| `cambio` | En `backend/api/main.py`, la autenticación de `/api/full-scan` pasa al parámetro `dependencies=[Depends(get_current_user)]` del decorador y la función solo recibe `conn=Depends(get_connection)`. Se agrega `backend/tests/test_full_scan_auth.py`, que comprueba 401 sin cookie aunque `get_connection` falle. |
| `justificacion` | FastAPI resolvía `get_connection` antes que `get_current_user` por el orden de los parámetros; sin cookie intentaba conectar a TiendaDB, que no existe en producción, y respondía 500 en lugar de 401. Las dependencias de la ruta se resuelven antes que las de la función. Limitación conocida: con sesión, `/api/full-scan` sigue fallando en producción porque escanea TiendaDB, que solo existe en desarrollo (`docker-compose.yml`); la interfaz de producción no lo llama (ver entrada R24.7). |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |

### R20.6: operador GREATER_THAN en las notificaciones de Budgets
Esta entrada no corresponde a ninguno de los criterios R24.1 a R24.10: registra un hallazgo de ejecución, no una desviación de la fuente. Usa los mismos campos y la misma regla de aprobación (R24.11, R24.12).
| Campo | Valor |
| --- | --- |
| `requisito_afectado` | R20 (Presupuesto), R20.6 («alcanza o supera») |
| `cambio` | Las notificaciones del presupuesto `PgGuardian-Mensual` usan `ComparisonOperator` `GREATER_THAN`, no «mayor o igual». |
| `justificacion` | AWS Budgets solo ofrece `GREATER_THAN` como `ComparisonOperator` para esta notificación, y R20.6 dice «alcanza o supera». La diferencia es de un centavo (el aviso llega al superar el umbral, no al igualarlo) y se acepta. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |
### R20: ThresholdType nulo en el bloque 7.1.3 del runbook
Esta entrada no corresponde a ninguno de los criterios R24.1 a R24.10: registra un hallazgo de ejecución, no una desviación de la fuente. Usa los mismos campos y la misma regla de aprobación (R24.11, R24.12).
| Campo | Valor |
| --- | --- |
| `requisito_afectado` | R20 (Presupuesto), bloque 7.1.3 del runbook |
| `cambio` | El bloque 7.1.3 de `docs/aws/runbook.md` lee el tipo de umbral con `(.ThresholdType // "PERCENTAGE")`. Agregar `ThresholdType: PERCENTAGE` a `pgguardian.yaml` se deja para después de la entrega (sin change set). |
| `justificacion` | La API devuelve `ThresholdType` nulo porque la plantilla no lo declara (AWS lo trata como `PERCENTAGE`). El bloque 7.1.3 se corrigió para tolerar el valor nulo y la comprobación se aprobó. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |
### R22: bloque 8.1.3 buscaba la acción en HistorySummary
Esta entrada no corresponde a ninguno de los criterios R24.1 a R24.10: registra un hallazgo de ejecución, no una desviación de la fuente. Usa los mismos campos y la misma regla de aprobación (R24.11, R24.12).
| Campo | Valor |
| --- | --- |
| `requisito_afectado` | R22 (R22.2, R22.4), bloque 8.1.3 del runbook |
| `cambio` | El bloque 8.1.3 de `docs/aws/runbook.md` busca el ARN de la acción de recuperación en `HistoryData` en lugar de `HistorySummary`. R22.4 queda `no_verificable`. |
| `justificacion` | El bloque buscaba el ARN de la acción en `HistorySummary`, pero CloudWatch lo guarda en `HistoryData`. R22.2 se aprobó revisando `docs/aws/evidencia/snapshots/recover-historial-20261126T2321Z.json`. La prueba se hizo con menos de 24 h de anticipación a la demostración y sin efecto sobre la Instancia (`boot_id` sin cambio). R22.4 sigue `no_verificable`: la recuperación real solo ocurre ante una falla de hardware. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |
### R20.6, R21.4 y R21.1: sin observación antes de la entrega
Esta entrada no corresponde a ninguno de los criterios R24.1 a R24.10: registra un hallazgo de ejecución, no una desviación de la fuente. Usa los mismos campos y la misma regla de aprobación (R24.11, R24.12).
| Campo | Valor |
| --- | --- |
| `requisito_afectado` | R20.6, R21.4 y R21.1 |
| `cambio` | R20.6 y R21.4 no se observan antes de la entrega. R21.1 queda `no_verificable` mientras el monitor no tenga `LastEvaluatedDate`. |
| `justificacion` | No hay gasto que dispare alertas del presupuesto ni anomalías de costo antes de la entrega, y no se puede forzar sin gastar. Mientras el monitor de anomalías no tenga `LastEvaluatedDate`, no hay evidencia de que haya evaluado. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |
### R23: sección 8.3 sin 8.2.2 ni 8.2.4
Esta entrada no corresponde a ninguno de los criterios R24.1 a R24.10: registra un hallazgo de ejecución, no una desviación de la fuente. Usa los mismos campos y la misma regla de aprobación (R24.11, R24.12).
| Campo | Valor |
| --- | --- |
| `requisito_afectado` | R23 (R23.2, R23.3), sección 8.3 del runbook |
| `cambio` | La sección 8.3 se ejecutó sin 8.2.2 ni 8.2.4. 8.3.4 (aprobado) cubre R23.2 y R23.3. |
| `justificacion` | Se omitieron 8.2.2 y 8.2.4 por falta de tiempo. R23.2 no exige un estado estable, así que 8.3.4 basta para R23.2 y R23.3. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |
### R27: sin Secreto_Huerfano en us-east-2
Esta entrada no corresponde a ninguno de los criterios R24.1 a R24.10: registra un hallazgo de ejecución, no una desviación de la fuente. Usa los mismos campos y la misma regla de aprobación (R24.11, R24.12).
| Campo | Valor |
| --- | --- |
| `requisito_afectado` | R27 |
| `cambio` | `list-secrets` en `us-east-2` devolvió una lista vacía; no hubo ningún Secreto_Huerfano que revisar. |
| `justificacion` | La consulta no encontró secretos en la región, así que no existe ningún Secreto_Huerfano. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |
### Paso 4.9 del runbook: snapshots anteriores borrados
Esta entrada no corresponde a ninguno de los criterios R24.1 a R24.10: registra un hallazgo de ejecución, no una desviación de la fuente. Usa los mismos campos y la misma regla de aprobación (R24.11, R24.12).
| Campo | Valor |
| --- | --- |
| `requisito_afectado` | Paso 4.9 del runbook (prueba de volumen ausente) y snapshots de 8.2 |
| `cambio` | Los snapshots anteriores se tomaron y se borraron después de crear los snapshots de estabilización (8.2). |
| `justificacion` | Los snapshots de estabilización de 8.2 son los que quedan como respaldo; los anteriores ya no se necesitan y su borrado evita un costo de almacenamiento innecesario. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |
### ID de cuenta en el historial público
Esta entrada no corresponde a ninguno de los criterios R24.1 a R24.10: registra un hallazgo de ejecución, no una desviación de la fuente. Usa los mismos campos y la misma regla de aprobación (R24.11, R24.12).
| Campo | Valor |
| --- | --- |
| `requisito_afectado` | Repositorio público; sin RF ni CA en la fuente |
| `cambio` | El commit `9e08688` agregó el ID de cuenta de AWS y el commit `6f3e2f3` lo quitó. No se reescribe el historial. |
| `justificacion` | AWS no considera el ID de cuenta un secreto, y un force push rompería los clones del Equipo. |
| `fecha` | 2026-11-26 |
| `aprobador` | Chus Avila (2026-11-26) |
## Aprobaciones

Cada entrada se aprueba anotando aquí el nombre del aprobador y la fecha de aprobación (AAAA-MM-DD), en un máximo de 2 días hábiles desde la fecha de la entrada (R24.11). Al aprobar, el mismo nombre se copia al campo `aprobador` de la entrada. «Fecha límite» es la fecha de la entrada más 2 días hábiles (lunes a viernes). Las celdas vacías se llenan a mano por el Equipo.

| Entrada | Fecha de la entrada | Fecha límite | Aprobador (nombre) | Fecha de aprobación |
| --- | --- | --- | --- | --- |
| R24.1: disco propio del sandbox | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| R24.2: Session Manager con el puerto 22 cerrado | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| R24.3: encendido y apagado de la Instancia | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| R24.4: respaldos con snapshots manuales | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| R24.5: miembros de `PgG-Admins` | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| R24.6: CA-16 sin prueba con usuario sin MFA | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| R24.7: llamadas del Frontend a endpoints de TiendaDB | 2026-11-24 | 2026-11-26 | Chus Avila | 2026-11-26 |
| R24.8: CloudFormation para la infraestructura | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| R24.9: alcance del E2 | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| R24.10: aviso de anomalías como resumen diario | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| Decisión de diseño de T-10: usuarios IAM creados en la consola | 2026-11-25 | 2026-11-27 | Chus Avila | 2026-11-26 |
| Monitor de anomalías por defecto reemplazado por el del stack | 2026-11-25 | 2026-11-27 | Chus Avila | 2026-11-26 |
| Código en la Instancia: clon por HTTPS | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| CA-06: /api/full-scan devolvía 500 sin cookie | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| R20.6: operador GREATER_THAN en las notificaciones de Budgets | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| R20: ThresholdType nulo en el bloque 7.1.3 del runbook | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| R22: bloque 8.1.3 buscaba la acción en HistorySummary | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| R20.6, R21.4 y R21.1: sin observación antes de la entrega | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| R23: sección 8.3 sin 8.2.2 ni 8.2.4 | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| R27: sin Secreto_Huerfano en us-east-2 | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| Paso 4.9 del runbook: snapshots anteriores borrados | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |
| ID de cuenta en el historial público | 2026-11-26 | 2026-11-30 | Chus Avila | 2026-11-26 |

## Lista de cierre de T-26

T-26 solo se cierra cuando todas las filas están en «aprobada». Una entrada a la que le falte alguno de los cinco campos o que no tenga nombre y fecha en «Aprobaciones» queda como **no aprobada**, y se completa antes del cierre (R24.12).

| Entrada | `requisito_afectado` | `cambio` | `justificacion` | `fecha` | `aprobador` | Aprobación anotada | Estado |
| --- | --- | --- | --- | --- | --- | --- | --- |
| R24.1 | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| R24.2 | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| R24.3 | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| R24.4 | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| R24.5 | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| R24.6 | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| R24.7 | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| R24.8 | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| R24.9 | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| R24.10 | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| Decisión de diseño de T-10 | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| Monitor de anomalías por defecto | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| Clon por HTTPS | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| CA-06: /api/full-scan sin cookie | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| Presupuesto: operador GREATER_THAN | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| Budgets: ThresholdType nulo en 7.1.3 | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| Bloque 8.1.3: HistoryData | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| R20.6, R21.4 y R21.1 sin observar | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| R23: sección 8.3 sin 8.2.2 ni 8.2.4 | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| R27: sin Secreto_Huerfano | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| Paso 4.9: snapshots anteriores | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |
| Historial: ID de cuenta | Sí | Sí | Sí | Sí | Sí | Sí | **aprobada** |

Para cerrar T-26:

- [x] Las diez entradas R24.1 a R24.10 existen y tienen los cinco campos.
- [x] Cada entrada tiene nombre y fecha en «Aprobaciones», dentro de su fecha límite, y el mismo nombre en su campo `aprobador`.
- [x] Todas las filas de la tabla anterior están en «aprobada».

Estado de T-26 al 2026-11-26: **cerrada** (2026-11-26). Las 22 entradas tienen los campos `requisito_afectado`, `cambio`, `justificacion`, `fecha` y `aprobador`, y la aprobación de Chus Avila (2026-11-26) anotada en «Aprobaciones», dentro de su fecha límite.
