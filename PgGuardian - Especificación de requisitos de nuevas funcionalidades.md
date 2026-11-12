# PgGuardian — Especificación de requisitos de nuevas funcionalidades

Oct 30, 2026 · @Luis Arias

## 1. Introducción

Este documento define tres incrementos para [PgGuardian](https://github.com/luiselodeon/PgGuardian): análisis desde scripts SQL cargados (RF-01), login con contraseñas hasheadas (RF-02) y una prueba de concepto de despliegue en AWS (RF-03). Las prioridades siguen MoSCoW: Debe, Debería, Podría.

Hoy el sistema solo analiza TiendaDB, con credenciales fijas en `backend/api/database.py`; la API y el dashboard no tienen autenticación y solo corren en local, en modo desarrollo. Quedan fuera de alcance la facturación, MFA, roles avanzados y la conexión a bases remotas del cliente.

**Base sandbox:** base PostgreSQL temporal y aislada donde se ejecuta un script cargado; se destruye al vencer.

## 2. RF-01 · Análisis desde scripts SQL

El usuario carga los scripts de creación de su base y obtiene su health score, en lugar de analizar siempre TiendaDB. Flujo: «Nuevo análisis» → carga de `.sql` → validación → ejecución en base sandbox → detectores → reporte en el historial.

| ID | Requisito | Prioridad |
| --- | --- | --- |
| RF-01.1 | Botón «Nuevo análisis» para cargar hasta 5 archivos `.sql` (UTF-8) en un orden definido. | Debe |
| RF-01.2 | Límite de 10 MB por archivo y 25 MB por análisis. | Debe |
| RF-01.3 | Rechazar antes de ejecutar: `ALTER SYSTEM`, `COPY … PROGRAM` o a archivo, `CREATE/ALTER ROLE`, `CREATE/DROP DATABASE`, extensiones fuera de una lista permitida y lenguajes no confiables. | Debe |
| RF-01.4 | Cada análisis corre en su propia base sandbox, en un servidor distinto al de la aplicación y con un rol sin superusuario; límite de 120 s y alto al primer error, mostrando archivo, línea y mensaje. | Debe |
| RF-01.5 | Los detectores usan la conexión a la base sandbox, no la conexión fija de `get_connection()`. | Debe |
| RF-01.6 | Los detectores que dependen de actividad (queries lentas, temp spills, idle in transaction) se marcan «no aplica» y no cuentan en el score, porque una base recién creada no tiene estadísticas de uso. | Debe |
| RF-01.7 | La base sandbox se borra a las 24 h; el reporte (nombre, fecha, score) queda en el historial. | Debe |
| RF-01.8 | Cada análisis solo es visible para su dueño. | Debe |

Endpoints: `POST` y `GET /api/analyses`, `GET` y `DELETE /api/analyses/{id}`.

## 3. RF-02 · Login y gestión de contraseñas

El dashboard y la API exigen sesión, y las contraseñas se guardan solo como hash Argon2id.

| ID | Requisito | Prioridad |
| --- | --- | --- |
| RF-02.1 | Registro con nombre, correo único y contraseña con confirmación. | Debe |
| RF-02.2 | Contraseña de 12 a 128 caracteres; se rechazan las comunes (lista ≥ 10,000) y las que contienen el correo. | Debe |
| RF-02.3 | Hash Argon2id con ≥ 19 MiB, ≥ 2 iteraciones y paralelismo 1, el mínimo de OWASP ([fuente](https://mojoauth.com/security-guides/sha-256-vs-argon2)), con sal aleatoria de 16 bytes en formato PHC. Nunca texto plano ni hashes rápidos (MD5, SHA-256). | Debe |
| RF-02.4 | Login con mensaje de error genérico y bloqueo de 15 min tras 5 intentos fallidos. | Debe |
| RF-02.5 | Todo `/api/` responde `401` sin sesión, salvo registro, login y `health-check`. | Debe |
| RF-02.6 | Cierre de sesión y cambio de contraseña (pide la actual y cierra las demás sesiones). | Debe |

Usuarios, sesiones y análisis viven en `app_db`, separada de las bases sandbox. Endpoints: `/api/auth/register`, `/login`, `/logout` y `/password`.

## 4. RF-03 · Despliegue en AWS (prueba de concepto)

El servicio corre en una sola instancia EC2 con Docker Compose y se accede por un link público.

&#91;embedded content: arquitectura de la prueba de concepto · 1 instancia EC2\]

Toda la solución vive en una instancia EC2 con IP elástica, donde Docker Compose levanta cinco contenedores en una red interna; solo Caddy publica los puertos 80 y 443. El usuario entra por HTTPS a la dirección de sslip.io y Caddy, que termina el cifrado, envía las rutas `/` al frontend (React compilado, servido por nginx) y las rutas `/api` a la API de FastAPI. La API valida la sesión y guarda usuarios, sesiones y reportes en `app_db`; cuando el usuario sube un script, lo ejecuta en una base temporal de `sandbox_db`, corre los detectores sobre ella, almacena el resultado en `app_db` y lo devuelve al dashboard por el mismo camino. Las bases nunca quedan expuestas a Internet y los scripts del usuario nunca tocan `app_db`.

| ID | Requisito | Prioridad |
| --- | --- | --- |
| RF-03.1 | Instancia EC2 (Ubuntu 24.04, ≥ 2 GB de RAM) con IP elástica en la VPC por defecto. | Debe |
| RF-03.2 | `docker-compose.prod.yml` con Caddy, frontend compilado (nginx), API sin `--reload`, `app_db` y `sandbox_db`. | Debe |
| RF-03.3 | Grupo de seguridad: 80 y 443 abiertos a Internet, 22 solo al equipo; PostgreSQL sin puertos públicos. | Debe |
| RF-03.4 | Link público con HTTPS mediante Caddy y `sslip.io` (por ejemplo `https://3-14-15-92.sslip.io`); si no es posible, HTTP solo para la demostración. | Debería |
| RF-03.5 | Secretos en un `.env` del servidor (permisos `600`); CORS y URL de la API por variables de entorno. | Debe |
| RF-03.6 | Alerta de AWS Budgets e instancia detenida fuera de las demostraciones. | Debe |

Fuera de alcance: alta disponibilidad, autoescalado, RDS, CDN y CI/CD.

### Notas de implementación: Caddy y sslip.io

**Caddy** es un servidor web de código abierto que corre como un contenedor más: reparte el tráfico (`/api` a FastAPI, lo demás al frontend) y obtiene y renueva solo un certificado HTTPS de Let's Encrypt. **sslip.io** es un DNS público sin registro: `3-14-15-92.sslip.io` resuelve a `3.14.15.92`, lo que da un dominio válido para el certificado; Let's Encrypt no emite certificados para los nombres `amazonaws.com`.

Ejemplo con la IP elástica `3.14.15.92`. Primero, el `Caddyfile` en la raíz del repositorio:

```
3-14-15-92.sslip.io {
    handle /api/* {
        reverse_proxy api:8000
    }
    handle {
        reverse_proxy frontend:80
    }
}
```

Después, el servicio en `docker-compose.prod.yml` (sin `ports` en `api` ni `frontend`, para que solo Caddy quede expuesto):

```yaml
  proxy:
    image: caddy:2
    restart: unless-stopped
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - ./Caddyfile:/etc/caddy/Caddyfile:ro
      - caddy_data:/data
    depends_on: [api, frontend]

volumes:
  caddy_data:
```

Finalmente, `VITE_API_URL=https://3-14-15-92.sslip.io/api`, el mismo dominio en la lista CORS, y `docker compose -f docker-compose.prod.yml up -d`.

- El puerto 80 debe estar abierto: Let's Encrypt valida el dominio por ahí.
- Si la IP cambia, cambia el nombre de sslip.io; por eso se usa IP elástica.
- sslip.io es compartido y Let's Encrypt puede rechazar el certificado por límites de emisión. La alternativa gratuita es un subdominio de DuckDNS (por ejemplo `pgguardian.duckdns.org`), configurado igual en el `Caddyfile`.

## 5. Requisitos no funcionales

Todos tienen prioridad Debe.

| ID | Categoría | Requisito |
| --- | --- | --- |
| RNF-01 | Seguridad | Un script cargado no puede afectar `app_db` ni la base sandbox de otro usuario. |
| RNF-02 | Seguridad | Login y registro limitados a 10 peticiones por minuto por IP. |
| RNF-03 | Rendimiento | Login en menos de 1 s (p95); análisis de un script de 1 MB y 50 tablas en menos de 60 s. |
| RNF-04 | Usabilidad | Interfaz y mensajes en español. |
| RNF-05 | Portabilidad | `docker compose up` sigue funcionando en local con TiendaDB. |

## 6. Actividades

Orden recomendado: RF-02 → RF-01 → RF-03, unas 80 horas-persona en total.

### RF-02 · Login (≈ 30 h)

- [ ] Agregar `app_db` con las tablas `users`, `sessions` y `analyses`.
- [ ] Implementar Argon2id, validación de contraseñas y JWT (`argon2-cffi`, `PyJWT`).
- [ ] Crear `routers/auth.py` y proteger los routers existentes con `get_current_user`.
- [ ] Frontend: login, registro y rutas protegidas.
- [ ] Probar hash, bloqueo y respuesta `401`.

### RF-01 · Scripts SQL (≈ 40 h)

- [ ] Agregar `sandbox_db` y el validador de sentencias con `pglast`.
- [ ] Servicio de sandbox: crear base, ejecutar scripts y limpiar a las 24 h.
- [ ] Refactorizar `full_scan` a `run_full_scan(conn)` y marcar detectores «no aplica».
- [ ] Router `analyses.py` y pantallas de carga e historial.
- [ ] Probar con `init/01_schema.sql`, un script inválido y uno con `ALTER SYSTEM`.

### RF-03 · AWS (≈ 12 h)

- [ ] Dockerfiles de producción, `docker-compose.prod.yml` y `Caddyfile`.
- [ ] Lanzar EC2 con grupo de seguridad e IP elástica; instalar Docker y crear `.env`.
- [ ] Configurar HTTPS con `sslip.io`, la alerta de Budgets y una prueba de humo.

## 7. Criterios de aceptación

| ID | Criterio | Cubre |
| --- | --- | --- |
| CA-01 | Al subir `init/01_schema.sql`, el usuario ve score y hallazgos en menos de 60 s. | RF-01.1–RF-01.5 |
| CA-02 | Un script con `ALTER SYSTEM` se rechaza antes de ejecutarse. | RF-01.3 |
| CA-03 | El usuario B recibe `404` al pedir un análisis del usuario A. | RF-01.8 |
| CA-04 | `password_hash` inicia con `$argon2id$` y no contiene la contraseña. | RF-02.3 |
| CA-05 | Tras 5 intentos fallidos, el sexto se bloquea 15 min. | RF-02.4 |
| CA-06 | `/api/full-scan` sin cookie responde `401`. | RF-02.6 |
| CA-07 | El link público abre el login y solo responden los puertos 80 y 443. | RF-03.1–RF-03.4 |
| CA-08 | En la instancia funcionan registro, login, análisis y cierre de sesión. | RF-01, RF-02, RF-03 |
