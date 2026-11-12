# Proceso de Software — PgGuardian Online (RF-01, RF-02 y RNF)

Este documento describe el proceso iterativo de ingeniería de software seguido en el repositorio `PgGuardian-Online` para evolucionar la plataforma desde su línea base local con TiendaDB hasta una aplicación multiusuario con análisis aislado de scripts SQL (**RF-01**), autenticación y seguridad criptográfica (**RF-02**) y cumplimiento de requisitos no funcionales (**RNF-01** a **RNF-05**).

---

## 1. Enfoque Metodológico y Flujo de Trabajo

El desarrollo se ejecutó mediante **entrega incremental basada en requisitos**, siguiendo el orden de arquitectura definido en [PgGuardian - Especificación de requisitos de nuevas funcionalidades.md](file:///e:/Github/PgGuardian-Online/PgGuardian%20-%20Especificaci%C3%B3n%20de%20requisitos%20de%20nuevas%20funcionalidades.md) y manteniendo en todo momento:

1. **Línea base auditable y documentación continua:** cada incremento quedó documentado en `scratchpad.md` antes de pasar al siguiente bloque funcional.
2. **Desacoplamiento progresivo por capas:** separación estricta entre la base objetivo local (`db` / TiendaDB), la base de aplicación (`app_db` para usuarios, sesiones y reportes) y el servidor efímero de ejecución (`sandbox_db`).
3. **Validación en cada incremento:** cada commit incorporó pruebas unitarias con `unittest` en `backend/tests/` (totalizando 57 pruebas aprobadas), compilación/linting en React (`eslint` y `vite build`) y verificaciones en vivo sobre contenedores Docker.
4. **Retrocompatibilidad (RNF-05):** preservación del flujo local `docker compose up` sobre TiendaDB a lo largo de toda la evolución.

### Cronología General de Iteraciones

```text
[Línea base d4e9046]
   │  Auditoría técnica y mapa de arquitectura (scratchpad.md + diagrama XML)
   ▼
[Iteración 1: RF-01 · Análisis aislado de scripts SQL]
   ├── cad55b5  RF-01.1 / RF-01.2  Carga ordenada (.sql, UTF-8, 10 MB / 25 MB)
   ├── 921cc9f  RF-01.3 / RF-01.4  Validador AST (pglast) + sandbox_db aislado
   ├── 41b77f3  RF-01.5 / RF-01.6  Desacoplamiento de detectores + estado no_aplica
   ├── 5fde03d  RF-01.7 / RF-01.8  Persistencia en app_db, purga 24h e historial
   ├── 3acb244  UX / Remediación   Navegación multi-pestaña y guías SQL accionables
   └── 8ab20a0  Estabilización     Corrección de estado inicial y Merge PR #1 (2d5f659)
   ▼
[Iteración 2: RF-02 · Autenticación, Argon2id, Sesiones y Persistencia]
   ├── 263bc02  RF-02.1 a RF-02.6  Argon2id OWASP, 10k+ passwords, JWT HttpOnly, bloqueo 15m, landing/rutas protegidas
   └── d45eee7  Persistencia / UX  FK user_id->users(id), restauración de análisis e ícono de ojo
   ▼
[Iteración 3: RNF · Auditoría y Endurecimiento Transversal]
   └── 833749d  RNF-01 a RNF-05    Aislamiento de redes Docker, rate limiting 10/min, AST O(N), español completo y fix CRLF
   ▼
[Iteración 4: RF-03 · Preparación en Repositorio para Despliegue AWS]
   └── Pendiente de commit  RF-03.2 / RF-03.4 / RF-03.5  docker-compose.prod.yml, Caddyfile, Dockerfile.prod + nginx, CORS/health-check por entorno
```

---

## 2. Línea Base e Inicio del Proceso

| Commit | Fecha | Autor | Descripción |
|---|---|---|---|
| `d4e9046` | 2026-11-05 | LuisArias | *Scratchpad y Diagrama* |

**Actividades realizadas:**
- Levantamiento de la arquitectura inicial de PgGuardian (5 módulos de detectores sobre catálogos `pg_*`, FastAPI en `backend/api/main.py` y dashboard React 19 + Vite).
- Documentación de brechas iniciales en `scratchpad.md` (acoplamiento a `get_connection()` sobre TiendaDB, ausencia de pruebas automatizadas y falta de autenticación/aislamiento).
- Creación del diagrama estructural inicial en `Diagrama de PgGuardian Online.xml`.

---

## 3. Iteración 1 — RF-01: Análisis desde Scripts SQL en Sandbox

Rama `RF-01-Análisis-Scripts-SQL`, integrada posteriormente a la rama principal mediante `2d5f659` (*Merge pull request #1*).

### 3.1 Carga ordenada y validación de archivos (RF-01.1 y RF-01.2)
- **Commit:** `cad55b5` (`2026-11-11`) — *implementar carga ordenada y validación de scripts SQL*
- **Diseño y cambios:**
  - Se incorporó `python-multipart==0.0.20` en `backend/requirements.txt` y el router `backend/api/routers/analyses.py` (`POST /api/analyses`).
  - Se implementó lectura por bloques de 1 MB para rechazar archivos > 10 MB o carga combinada > 25 MB (`413`) sin saturar memoria, límite de 1 a 5 archivos `.sql`, decodificación UTF-8 estricta (`422`) y validación del parámetro `order` como permutación válida (`400`).
  - En React se creó `NewAnalysisModal.jsx` / `.css` con drag-and-drop, reordenamiento (`↑`/`↓` y arrastre) y cliente en `frontend/src/api/pgguardian.js`.
  - Se inició la suite de pruebas con `backend/tests/test_analyses.py`.

### 3.2 Análisis estático AST y ejecución aislada (RF-01.3 y RF-01.4)
- **Commit:** `921cc9f` (`2026-11-11`) — *implementar validador AST con pglast y ejecución aislada en sandbox_db*
- **Diseño y cambios:**
  - Se agregó `pglast==6.17` (parser nativo de PostgreSQL 16 vía `libpg_query`) y se creó `backend/services/sql_validator.py` con `_SafetyVisitor` para bloquear `ALTER SYSTEM`, `COPY ... PROGRAM`/a archivo, creación/alteración de roles, creación/borrado de bases de datos, FDW/servidores externos, extensiones fuera de lista permitida y lenguajes no confiables (`sql` y `plpgsql` únicamente), reportando archivo y línea exactos antes de tocar la base de datos.
  - Se incorporó el servicio `sandbox_db` (`postgres:16`) en `docker-compose.yml` completamente separado de TiendaDB.
  - Se creó `backend/services/sandbox_runner.py` para provisionar bases efímeras `sandbox_<uuid>`, asegurar el rol sin privilegios `sandbox_runner` (`NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOREPLICATION`), aplicar `statement_timeout` global acumulado de 120 s por sentencia y ejecutar limpieza fail-fast (`DROP DATABASE ... WITH (FORCE)`).
  - Pruebas añadidas: `backend/tests/test_sql_validator.py` y `backend/tests/test_sandbox_runner.py`.

### 3.3 Desacoplamiento de detectores y detectores N/A (RF-01.5 y RF-01.6)
- **Commit:** `41b77f3` (`2026-11-11`) — *desacoplar detectores hacia sandbox_db y normalizar score con estado no_aplica*
- **Diseño y cambios:**
  - Se extrajo la lógica de `/api/full-scan` desde `backend/api/main.py` hacia `backend/services/scan_service.py` mediante `run_full_scan(conn, is_sandbox=...)`.
  - Se catalogaron los 9 detectores dependientes de tráfico o estadísticas acumuladas (`SANDBOX_NOT_APPLICABLE_DETECTORS`) para marcarlos como `status: "no_aplica"` en sandbox, normalizando la fórmula del Health Score únicamente sobre el peso de los 13 detectores evaluados (`active_weight = 69` vs `total_weight = 114`).
  - Se protegieron `bloat.py` y `health.py` con verificación previa de `pg_extension` y `SAVEPOINT` para ejecutarse sin superusuario.
  - Se añadió `backend/tests/test_scan_service.py` y soporte visual `NO_APLICA` en `SeverityBadge.jsx` y `CategoryCard.jsx`.

### 3.4 Persistencia temporal, purga 24 h y aislamiento multitenant (RF-01.7 y RF-01.8)
- **Commit:** `5fde03d` (`2026-11-11`) — *agregar historial en app_db, limpieza sandbox 24h, aislamiento por usuario y scripts de prueba*
- **Diseño y cambios:**
  - Se añadió el servicio `app_db` (`postgres:16`) en `docker-compose.yml` y la capa `backend/services/analysis_store.py` para persistir reportes en `analyses` sin guardar contenido SQL ni credenciales de sandbox.
  - Se creó `backend/services/sandbox_cleanup.py` integrado en el `lifespan` de FastAPI para purgar automáticamente bases sandbox con más de 24 h conservando el reporte histórico.
  - Se implementaron `GET /api/analyses`, `GET /api/analyses/{id}` y `DELETE /api/analyses/{id}` filtrados por propietario (`404` ante acceso ajeno, cumpliendo CA-03), junto con una dependencia temporal en `backend/api/auth.py`.
  - En frontend se creó `HistoryPage.jsx` / `.css` y en la raíz se añadieron scripts SQL problemáticos de prueba (`scripts_prueba/`).
  - Pruebas añadidas: `backend/tests/test_analyses_lifecycle.py`.

### 3.5 Experiencia multi-pestaña, guías de remediación y estabilización
- **Commits:** `3acb244`, `8ab20a0` y `2d5f659` (`2026-11-11`)
- **Diseño y cambios:**
  - `3acb244`: se añadió `_REMEDIATION_CATALOG` en `scan_service.py`, la barra de pestañas `AnalysisTabs.jsx`, los componentes reutilizables `RemediationPanel.jsx` y `FindingList.jsx`, integración en `DataTable.jsx` y scripts optimizados en `scripts_buenas_practicas/`.
  - `8ab20a0`: se corrigió un bug de inicialización de estado en `App.jsx` (`[createLocalTab]` $\rightarrow$ `() => [createLocalTab()]`), se cambió el auto-refresh a modo silencioso, se agregó redirección al seleccionar pestañas desde `/history` y se incluyó `http://127.0.0.1:5173` en CORS.
  - `2d5f659`: fusión del PR #1 a la rama principal.

---

## 4. Iteración 2 — RF-02: Autenticación, Criptografía Argon2id y Persistencia por Usuario

### 4.1 Registro, políticas de contraseña, Argon2id, login y rutas protegidas (RF-02.1 a RF-02.6)
- **Commit:** `263bc02` (`2026-11-11`) — *implementar autenticación Argon2id, sesiones JWT y landing de acceso obligatorio*
- **Diseño y cambios:**
  - **Criptografía (RF-02.3 / CA-04):** se agregó `argon2-cffi==25.1.0` y `backend/security/hashing.py` con `PasswordHasher(time_cost=2, memory_cost=19456, parallelism=1, hash_len=32, salt_len=16, type=Type.ID)` produciendo hashes PHC `$argon2id$...` sin texto plano.
  - **Políticas de contraseña (RF-02.1 y RF-02.2):** se creó `backend/security/password_policy.py` junto con `backend/security/common_passwords.txt` (100,000 entradas de SecLists, 96,517 únicas cargadas en un `frozenset` cacheado en memoria), validando longitud 12–128, no solo espacios, coincidencia con confirmación y exclusión del correo/parte local.
  - **Sesiones JWT y bloqueo (RF-02.4, RF-02.5, RF-02.6 / CA-05, CA-06):**
    - Se agregó `PyJWT==2.15.1`, `JWT_SECRET` en `docker-compose.yml` y `backend/security/sessions.py` para cookies `HttpOnly` (`pgguardian_session`, `SameSite=Lax`).
    - Se crearon las tablas `users` (con `failed_login_attempts`, `locked_until` y `chk_users_email_lowercase`) y `sessions` (revocable) en `app_db`, gestionadas desde `backend/services/user_store.py`.
    - Se creó `backend/api/routers/auth.py` con `POST /api/auth/register` (`201` + sesión), `POST /api/auth/login` (error genérico `"Credenciales inválidas."` `401` y bloqueo 15 min `429` al 6.º intento tras 5 fallos), `GET /api/auth/me`, `POST /api/auth/logout` y `POST /api/auth/password` (verifica contraseña actual y revoca las demás sesiones).
    - Se reemplazó el lector temporal `X-User-Id` en `backend/api/auth.py` por validación real de JWT + sesión activa en `app_db`, y se protegieron `/api/full-scan` y los 5 routers de detectores en `backend/api/main.py` dejando públicos únicamente `/api/auth/register`, `/api/auth/login` y `/api/health-check`.
  - **Frontend obligatorio:**
    - Se creó `AuthLandingPage.jsx`/`.css` en `/` con explicación del sistema y pestañas **Iniciar sesión** / **Crear cuenta**.
    - Se creó `ProtectedRoute.jsx` y se reestructuró `App.jsx` para verificar `/api/auth/me` con `credentials: 'include'`, redirigir `/` $\rightarrow$ `/dashboard` con sesión o rutas privadas $\rightarrow$ `/` sin sesión, y manejar respuestas `401` globalmente en `pgguardian.js`.
    - Se sustituyó el selector temporal de usuarios en `Sidebar.jsx` por la identidad real con acciones de `ChangePasswordModal.jsx` y cierre de sesión.
  - **Pruebas:** `backend/tests/test_auth_register.py` y actualización de `test_analyses_lifecycle.py` (49 pruebas unitarias en total).

### 4.2 Persistencia relacional por usuario y mejora visual de contraseñas
- **Commit:** `d45eee7` (`2026-11-11`) — *persistir y restaurar análisis por usuario en app_db y agregar ícono de ojo en contraseñas*
- **Diseño y cambios:**
  - **Integridad referencial en `app_db`:** en `backend/services/analysis_store.py` se formalizó `user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE` (`fk_analyses_user`) mediante migración idempotente que depura filas huérfanas pre-RF-02 conservando análisis de usuarios reales, además de guardas `_parse_uuid_or_none` y proyecciones `user_id::text`.
  - **Restauración automática de sesión/trabajo:** en `frontend/src/App.jsx`, al iniciar sesión o recargar con sesión activa se consulta `GET /api/analyses` y se precarga automáticamente el último análisis guardado (`getAnalysisDetail`) en `AnalysisTabs` junto a `TiendaDB (Local)`.
  - **Corrección y UX:** en `HistoryPage.jsx` se corrigió la interpolación de objeto `{currentUser}` en el estado vacío (React 19) y en `AuthLandingPage.jsx`/`.css` se reemplazó el botón de texto «Mostrar»/«Ocultar» por un ícono SVG accesible (`EyeIcon` / `PasswordInput`) en login y registro.
  - **Pruebas:** se añadió `test_analyses_schema_has_users_fk_and_store_guards_non_uuid_user` en `test_analyses_lifecycle.py` (55 pruebas en total).

---

## 5. Iteración 3 — Auditoría y Cumplimiento de RNF-01 a RNF-05

- **Commit:** `833749d` (`2026-11-11`) — *auditar y asegurar cumplimiento de requisitos no funcionales (RNF-01 a RNF-05)*
- **Diagnóstico y subsanaciones aplicadas:**

| RNF | Categoría | Brecha detectada | Solución implementada |
|---|---|---|---|
| **RNF-01** | Seguridad (Aislamiento) | Contenedores `sandbox_db`, `app_db` y `db` compartían la misma red puente por defecto en Docker. | Segregación en `docker-compose.yml` con redes `app_net`, `sandbox_net` y `tienda_net` (`internal: true`) más `public_net`. |
| **RNF-02** | Seguridad (Rate Limiting) | Endpoints `/api/auth/login` y `/api/auth/register` sin límite de peticiones por IP. | Creación de `backend/security/rate_limit.py` (`SlidingWindowRateLimiter`, 10 req/min por IP en memoria sin Redis) y middleware `enforce_auth_rate_limit` en `main.py` (`429` en español con `Retry-After`). |
| **RNF-03** | Rendimiento (Latencias) | `_locate_statement` en `sql_validator.py` escaneaba tokens y rebanadas desde el inicio en $O(N^2)$ (`4.75 s` en AST para 1 MB). | Refactorización a cursores incrementales de tokens y saltos de línea $O(N)$ (`0.48 s` en AST; análisis completo de 1 MB / 50 tablas en `4.11 s`; login HTTP `p95 = 50.1 ms`). |
| **RNF-04** | Usabilidad (Idioma) | Etiquetas en inglés en UI/detectores y errores nativos de FastAPI (`"Field required"`). | Handler `spanish_validation_exception_handler` en `main.py` y traducción de etiquetas en `scan_service.py` y 10 componentes/páginas de React. |
| **RNF-05** | Portabilidad (Local) | `tiendadb_idle_tx` reiniciaba en bucle (`exit 127`) por saltos de línea CRLF en `scripts/start_idle_tx.sh`. | Conversión a LF y creación de `.gitattributes` (`*.sh text eol=lf`), estabilizando `tiendadb_idle_tx` y el escaneo local de TiendaDB. |

- **Pruebas añadidas:** `backend/tests/test_rnf.py` verificando rate limiting, recuperación tras ventana de 60 s, precisión lineal del AST y traducción de errores de validación.

---

## 6. Iteración 4 — RF-03: Preparación en Repositorio para Despliegue en AWS

Para **RF-03** (*Despliegue en AWS · Prueba de concepto en 1 instancia EC2*), se implementaron dentro del repositorio todos los artefactos de empaquetado, proxy inverso y configuración por entorno, quedando fuera del alcance del código fuente únicamente las acciones operativas dentro de la consola/servidor de AWS:

- **En repositorio (implementado):**
  - **RF-03.2 (`docker-compose.prod.yml`, `frontend/Dockerfile.prod`, `frontend/nginx.conf`):** stack de 5 contenedores (`proxy` con Caddy 2, `frontend` compilado en Nginx con `try_files` para SPA, `api` con Uvicorn sin `--reload`, `app_db` y `sandbox_db`), exponiendo al exterior únicamente `80` y `443` en `proxy` y manteniendo redes `internal: true` para `app_db` y `sandbox_db`.
  - **RF-03.4 (`Caddyfile`):** enrutamiento `/api/*` $\rightarrow$ `api:8000` y `/` $\rightarrow$ `frontend:80` parametrizado con `{$APP_DOMAIN::80}` para TLS automático vía Let's Encrypt (`sslip.io` o DuckDNS) o modo HTTP `:80`.
  - **RF-03.5 (`.env.prod.example` y soporte en `backend/api/main.py`):** `_get_cors_origins()` configurable vía `CORS_ORIGINS`, adaptación de `/api/health-check` para consultar `app_db` cuando no se despliega `TiendaDB` (`DB_HOST` ausente), compatibilidad con `COOKIE_SECURE=true` y `TRUST_PROXY_HEADERS=true`, y plantilla `.env.prod.example` sin secretos reales.
  - **Pruebas:** `test_rf03_cors_origins_reads_env_or_falls_back_to_local_defaults` y `test_rf03_health_check_uses_app_db_without_db_host_and_tiendadb_when_set` en `backend/tests/test_rnf.py`, validación `docker compose -f docker-compose.prod.yml --env-file .env.prod.example config --quiet` y build de `frontend/Dockerfile.prod`.
- **Pendiente fuera del repositorio (operación en AWS/EC2):**
  - **RF-03.1 / RF-03.3 / RF-03.6:** crear instancia EC2 (Ubuntu 24.04, $\ge 2\text{ GB}$ RAM) con IP elástica, configurar Security Group (`80`/`443` abiertos, `22` restringido, sin puertos de PostgreSQL), crear `.env` con secretos reales y permisos `chmod 600 .env`, emitir certificado TLS contra la IP pública y configurar alerta en AWS Budgets.

---

## 7. Resumen de Verificación y Arquitectura Resultante

- **Cobertura de pruebas unitarias (`backend/tests/`):** 57 pruebas ejecutadas con `unittest` (`test_analyses.py`, `test_sql_validator.py`, `test_sandbox_runner.py`, `test_scan_service.py`, `test_analyses_lifecycle.py`, `test_auth_register.py`, `test_rnf.py`).
- **Construcción y calidad de frontend (`frontend/`):** validación con `eslint` sobre los módulos intervenidos, empaquetado de producción con Vite (`npm run build`) y build de imagen Nginx en `frontend/Dockerfile.prod`.
- **Aislamiento de bases en producción/local:**
  - `db` (`TiendaDB`): base objetivo demostrativa local con los 18 problemas sembrados (`H01`–`H18`) y `tiendadb_idle_tx` en `tienda_net` (solo en `docker-compose.yml` local).
  - `app_db`: base exclusiva de la aplicación en `app_net` (`users`, `sessions`, `analyses` sin código SQL fuente ni credenciales de sandbox).
  - `sandbox_db`: servidor aislado en `sandbox_net` ejecutando scripts validados por AST bajo rol sin privilegios `sandbox_runner` y purga automática a las 24 h.

---

## 8. Guía Paso a Paso de Despliegue en AWS EC2 (`RF-03`)

Esta guía describe cómo levantar PgGuardian en producción (Prueba de Concepto en una sola instancia EC2) utilizando exactamente los archivos preparados en el repositorio: `docker-compose.prod.yml`, `Caddyfile`, `frontend/Dockerfile.prod`, `frontend/nginx.conf`, `backend/Dockerfile.api` y `.env.prod.example`.

### Paso 1 — Provisionar la instancia EC2 e IP Elástica (RF-03.1)
1. En la consola de **AWS EC2**, lanza una nueva instancia en la VPC por defecto:
   - **Sistema operativo (AMI):** Ubuntu Server `24.04 LTS`.
   - **Tipo de instancia:** mínimo `2 GB` de RAM (por ejemplo `t3.small` o `t3a.small`).
   - **Almacenamiento:** volumen EBS `gp3` de al menos `20 GB` (para imágenes Docker, `caddy_data`, `app_data` y `sandbox_data`).
   - **Par de claves:** selecciona o crea tu llave `.pem` para acceso SSH.
2. En **EC2 $\rightarrow$ Elastic IPs**, solicita una **IP elástica** (*Allocate Elastic IP address*) y asóciala (*Associate Elastic IP*) a tu instancia recién creada.
   - *Ejemplo de referencia:* si la IP elástica asignada es `3.14.15.92`, el dominio `sslip.io` correspondiente será `3-14-15-92.sslip.io`.

### Paso 2 — Configurar Security Group y Alerta de Costos (RF-03.3 / RF-03.6)
1. Edita las **Inbound rules** (*Reglas de entrada*) del Security Group asociado a la instancia:
   - **`80/TCP` (HTTP):** origen `0.0.0.0/0` *(indispensable para que Let's Encrypt valide el dominio y para redirigir HTTP $\rightarrow$ HTTPS)*.
   - **`443/TCP` (HTTPS):** origen `0.0.0.0/0`.
   - **`22/TCP` (SSH):** origen **únicamente** la IP pública de tu equipo (*My IP*).
   - **No abrir** puertos `5432` (PostgreSQL), `8000` (FastAPI) ni `5173` (Vite).
2. En **AWS Billing and Cost Management $\rightarrow$ Budgets**, crea un presupuesto mensual con alerta por correo (RF-03.6) para evitar cargos inesperados.

### Paso 3 — Conectar por SSH e instalar Docker Engine + Compose v2
Conéctate desde tu máquina local:

```bash
chmod 400 tu-llave.pem
ssh -i tu-llave.pem ubuntu@<IP_ELASTICA>
```

Dentro de la instancia EC2, instala Docker y el plugin Docker Compose:

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc

echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
sudo usermod -aG docker "$USER"
newgrp docker
```

Verifica la instalación con `docker --version` y `docker compose version`.

### Paso 4 — Clonar el repositorio y configurar `.env` con permisos `600` (RF-03.5)
1. Clona el repositorio en la instancia:

```bash
git clone https://github.com/luiselodeon/PgGuardian-Online.git
cd PgGuardian-Online
```

2. Copia la plantilla de producción y genera secretos criptográficos únicos:

```bash
cp .env.prod.example .env
openssl rand -hex 32   # Úsalo para JWT_SECRET
openssl rand -base64 24 # Genera contraseñas distintas para APP_DB y SANDBOX_DB
```

3. Edita `.env` (por ejemplo con `nano .env`) reemplazando los valores de ejemplo según tu IP elástica (supongamos `3.14.15.92`):

```dotenv
APP_DOMAIN=3-14-15-92.sslip.io
VITE_API_URL=https://3-14-15-92.sslip.io/api
CORS_ORIGINS=https://3-14-15-92.sslip.io

COOKIE_SECURE=true
TRUST_PROXY_HEADERS=true
JWT_SECRET=<secreto_aleatorio_generado>

APP_DB_NAME=pgguardian_app
APP_DB_USER=pgguardian_app_user
APP_DB_PASSWORD=<password_fuerte_appdb>

SANDBOX_DB_NAME=postgres
SANDBOX_DB_ADMIN_USER=sandbox_admin
SANDBOX_DB_ADMIN_PASSWORD=<password_fuerte_sandbox_admin>
SANDBOX_DB_EXEC_USER=sandbox_runner
SANDBOX_DB_EXEC_PASSWORD=<password_fuerte_sandbox_runner>
```

> **Alternativas si `sslip.io` alcanza límite de emisión en Let's Encrypt:**
> - **Opción A (DuckDNS con HTTPS):** registra un subdominio gratuito (ej. `pgguardian-equipo.duckdns.org`) apuntando a `<IP_ELASTICA>` y sustitúyelo en `APP_DOMAIN`, `VITE_API_URL` y `CORS_ORIGINS` (no requiere editar `Caddyfile`).
> - **Opción B (Solo HTTP para demostración, RF-03.4):** usa `APP_DOMAIN=:80`, `VITE_API_URL=http://<IP_ELASTICA>/api`, `CORS_ORIGINS=http://<IP_ELASTICA>` y **`COOKIE_SECURE=false`** (para que el navegador acepte y envíe la cookie `pgguardian_session` sobre HTTP plano).

4. Protege el archivo de secretos en el servidor:

```bash
chmod 600 .env
```

### Paso 5 — Construir y levantar los 5 contenedores de producción (RF-03.2 / RF-03.4)
Ejecuta Docker Compose apuntando explícitamente al archivo de producción `docker-compose.prod.yml`:

```bash
docker compose -f docker-compose.prod.yml up -d --build
```

Este comando levantará los 5 servicios en sus redes correspondientes (`public_net`, `app_net` interna y `sandbox_net` interna):
- `pgguardian_proxy` (`caddy:2-alpine`, único contenedor con puertos `80` y `443` publicados, leyendo `./Caddyfile`).
- `pgguardian_frontend_prod` (`frontend/Dockerfile.prod` + `frontend/nginx.conf`, compilado con `VITE_API_URL`).
- `pgguardian_api_prod` (`uvicorn api.main:app --host 0.0.0.0 --port 8000` sin `--reload`).
- `pgguardian_appdb_prod` (`postgres:16` en `app_net` interna).
- `pgguardian_sandboxdb_prod` (`postgres:16` en `sandbox_net` interna).

Verifica que todos los servicios estén activos y revisa que Caddy haya obtenido el certificado TLS de Let's Encrypt:

```bash
docker compose -f docker-compose.prod.yml ps
docker compose -f docker-compose.prod.yml logs -f proxy
```

### Paso 6 — Verificación y prueba de humo en vivo (CA-06, CA-07, CA-08)
1. **Salud pública de la API (`/api/health-check`):**

```bash
curl -i https://3-14-15-92.sslip.io/api/health-check
```

Debe responder `HTTP/2 200` con `"status": "ok"` y `"target": "app_db"`.

2. **Verificación de bloqueo sin sesión (`CA-06`):**

```bash
curl -i https://3-14-15-92.sslip.io/api/analyses
```

Debe responder `401 Unauthorized`.

3. **Flujo completo en navegador (`CA-07` / `CA-08`):**
   - Abre `https://3-14-15-92.sslip.io` en tu navegador: debe mostrar la landing de acceso obligatorio con el candado HTTPS activo.
   - Crea una cuenta nueva en la pestaña **Crear cuenta** (contraseña $\ge 12$ caracteres).
   - Al ingresar a `/dashboard`, pulsa **«Nuevo análisis»** y sube por ejemplo `scripts_buenas_practicas/01_schema_optimizado.sql` (o `init/01_schema.sql`) para verificar ejecución en `sandbox_db`, cálculo de Health Score, persistencia en `/history` y **«Cerrar sesión»**.
   - Confirmar que los puertos `5432`, `8000` y `5173` **no** están accesibles desde Internet.

### Paso 7 — Mantenimiento, actualización y apagado fuera de demostraciones (RF-03.6)
- **Detener fuera de demostraciones (ahorro de costos):**
  - Los servicios de `docker-compose.prod.yml` usan `restart: unless-stopped`, por lo que volverán a arrancar automáticamente cuando reenciendas la EC2 en AWS (*Start instance*).
  - Desde la consola de AWS EC2 selecciona **Instance state $\rightarrow$ Stop instance** cuando no estés en demostración (la IP elástica y los volúmenes EBS `app_data`, `sandbox_data`, `caddy_data` se conservan).
- **Actualizar la aplicación ante nuevos cambios del repositorio:**

```bash
cd ~/PgGuardian-Online
git pull
docker compose -f docker-compose.prod.yml up -d --build
```


