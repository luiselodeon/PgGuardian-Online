# Requirements Document

## Introduction

Este documento convierte los requisitos del Entregable 2 de PgGuardian (despliegue en AWS) en requisitos en formato EARS con trazabilidad completa. Fuente: `PgGuardian - Requisitos del Entregable 2 (AWS).md` (RF-04 a RF-08, CA-09 a CA-27, T-01 a T-27, sección 3 de cambios al E1 y sección 6 de pendientes). La cadena de trazabilidad es RF → T → CA. Cada requisito indica sus RF originales, sus tareas T-xx y sus criterios CA-xx. La matriz completa está al final del documento.

El diseño base no cambia: una instancia EC2 t3.small con Ubuntu 24.04 en us-east-2, Docker Compose con cinco contenedores, solo Caddy expuesto a internet, Elastic IP y `sslip.io`. La infraestructura AWS se crea con una plantilla de CloudFormation en un único stack llamado `pgguardian` (Requirement 29). El presupuesto es de 100 USD en créditos que vencen el 11 de mayo de 2027, con un costo estimado 24/7 de unos 22 USD al mes. La Instancia se enciende o se detiene a criterio del Equipo (Requirement 24, criterio 3), y la evaluación se hace con un video grabado que muestra el funcionamiento desde la URL pública, no con acceso en vivo. La numeración continúa la del Entregable 1 (RF-01 a RF-03, CA-01 a CA-08, RNF-05).

Prioridades MoSCoW de la fuente: Debe, Debería, Podría. Cada requisito declara la suya. Los elementos de la fuente que se recortaron en esta versión se listan en la sección «Mejoras futuras», al final del documento, y cada desviación se registra según el Requirement 24.

## Glossary

- **Compose_Prod**: Archivo `docker-compose.prod.yml` que define los cinco contenedores de producción.
- **Caddy**: Proxy inverso, único servicio expuesto a internet, configurado en `Caddyfile`.
- **API**: Servicio backend en `backend/api/main.py`.
- **Frontend**: Aplicación web en `frontend/`, cuyo build de producción sirve Caddy.
- **TiendaDB**: Base de datos de ejemplo del entorno de desarrollo, accesible mediante `get_connection()` de `backend/api/database.py`, que no existe en producción.
- **Sandbox_DB**: Contenedor `sandbox_db` con la base de datos de ejecución aislada.
- **App_DB**: Contenedor `app_db` con la base de datos de la aplicación.
- **Volumen_Sandbox**: Volumen EBS gp3 cifrado de 8 GB montado en `/srv/sandbox`.
- **Instancia**: Instancia EC2 t3.small con Ubuntu 24.04 en us-east-2.
- **Security_Group**: Grupo de seguridad asociado a la Instancia.
- **Elastic_IP**: Dirección IPv4 pública fija asociada a la Instancia.
- **Dominio_Publico**: Dominio `<ip-con-guiones>.sslip.io` o, como respaldo, un subdominio de DuckDNS.
- **Cuenta_Raiz**: Usuario raíz de la cuenta AWS.
- **Usuario_IAM**: Usuario IAM individual de un integrante del equipo.
- **Grupo_Admins**: Grupo IAM `PgG-Admins`.
- **Politica_Force_MFA**: Política IAM que deniega acciones a sesiones sin MFA.
- **Rol_EC2**: Rol IAM `PgGuardian-EC2-Role` con la política `AmazonSSMManagedInstanceCore`.
- **Session_Manager**: Servicio SSM Session Manager de AWS para administrar la Instancia.
- **Presupuesto**: Presupuesto de AWS Budgets de 30 USD al mes.
- **Anomaly_Detection**: Servicio AWS Cost Anomaly Detection.
- **Alarma_Recover**: Alarma de CloudWatch sobre `StatusCheckFailed_System` con acción *recover*.
- **Snapshot_Manual**: Snapshot de EBS que el Equipo crea a mano desde la consola o la CLI de AWS, sin política de automatización.
- **Secreto_Huerfano**: Secreto de AWS Secrets Manager en us-east-2 que no pertenece al despliegue actual de PgGuardian.
- **Paquete_Evidencia**: Conjunto de entregables de verificación: reporte ZAP baseline, salida de `nmap` y resultados de CA-01 a CA-08.
- **Registro_Decisiones**: Registro de desviaciones respecto del Entregable 1 y de la fuente, con justificación y aprobación del equipo.
- **SANDBOX_DATA_DIR**: Variable de entorno que define el directorio del host montado como datos de Sandbox_DB; valor por defecto `./.data/sandbox`, y `/srv/sandbox/pgdata` en la Instancia.
- **Script_Verificacion_Local**: Script que ejecuta la verificación local de T-08 (precondiciones, arranque de `docker-compose.prod.yml` y criterios CA-09 a CA-14).
- **TIENDADB_SCAN_ENABLED**: Constante del Frontend derivada de `VITE_ENABLE_TIENDADB_SCAN`; es falsa en el build de producción (variable no definida) y verdadera en desarrollo.
- **Pestaña_Local**: Pestaña `TiendaDB (Local)` (`LOCAL_TAB_ID = 'tiendadb-local'`, `kind: 'local'`) creada por `createLocalTab()` en `frontend/src/App.jsx`.
- **Equipo**: Los integrantes del proyecto PgGuardian.
- **Plantilla_CFN**: Plantilla de CloudFormation infra/cloudformation/pgguardian.yaml que crea la infraestructura AWS del despliegue.
- **Stack**: Stack de CloudFormation llamado `pgguardian`, creado a partir de la Plantilla_CFN.

## Requirements

### Requirement 1: JWT_SECRET obligatorio en producción

**User Story:** Como integrante del equipo, quiero que el despliegue falle si falta `JWT_SECRET`, para que nunca se use la clave de desarrollo de `sessions.py`.

**Trazabilidad:** RF-04.1 (Debe) · Tareas: T-01, T-17 · Criterios: CA-09

#### Acceptance Criteria

1. THE Compose_Prod SHALL declarar `JWT_SECRET` con la sintaxis `${JWT_SECRET:?falta JWT_SECRET}` en la configuración del servicio de la API.
2. IF `JWT_SECRET` no está definido o es una cadena vacía, THEN THE Compose_Prod SHALL terminar `docker compose config` con código de salida distinto de 0, mostrar el mensaje «falta JWT_SECRET» en la salida de error y no generar la configuración resuelta.
3. IF `JWT_SECRET` no está definido o es una cadena vacía, THEN THE Compose_Prod SHALL terminar `docker compose up` con código de salida distinto de 0 sin crear ni iniciar ningún contenedor.
4. WHEN se crea el archivo `.env` en la Instancia, THE Equipo SHALL definir en él un `JWT_SECRET` generado aleatoriamente de al menos 32 bytes (64 caracteres hexadecimales o 43 caracteres base64 como mínimo).

### Requirement 2: Rotación de logs de los contenedores

**User Story:** Como operador, quiero que los logs rotén, para que no llenen el disco raíz.

**Trazabilidad:** RF-04.2 (Debe) · Tareas: T-02 · Criterios: CA-10

#### Acceptance Criteria

1. THE Compose_Prod SHALL definir un único bloque `logging` común mediante el ancla YAML `x-logging`, y cada servicio SHALL referenciarlo con el alias YAML `*logging` (sin declarar un bloque `logging` propio distinto).
2. THE Compose_Prod SHALL aplicar a los cinco servicios el driver `json-file` con `max-size: 10m` y `max-file: 3`, de modo que el espacio máximo de logs por contenedor sea de 30 MB (3 archivos × 10 MB) y el máximo total para los cinco servicios sea de 150 MB.
3. WHEN se ejecuta `docker inspect -f '{{.HostConfig.LogConfig}}'` sobre cada uno de los cinco contenedores en ejecución, THE Compose_Prod SHALL mostrar en la salida de cada contenedor el tipo `json-file`, `max-size:10m` y `max-file:3`, sin ningún contenedor con otro driver o con valores distintos.
4. WHEN el archivo de log activo de un contenedor alcanza 10 MB, THE Compose_Prod SHALL rotar el archivo y conservar como máximo 3 archivos de log por contenedor, eliminando el más antiguo al crear un cuarto.
5. IF el comando `docker compose -f docker-compose.prod.yml config` se ejecuta y algún servicio no resuelve `json-file`, `max-size: 10m` y `max-file: 3`, THEN THE Compose_Prod SHALL ser considerado no conforme con CA-10, y la verificación SHALL terminar con un resultado de fallo que identifique el servicio afectado.

### Requirement 3: Límites de memoria por contenedor

**User Story:** Como operador, quiero límites de memoria, para que un contenedor no agote la RAM de la t3.small.

**Trazabilidad:** RF-04.3 (Debe) · Tareas: T-03 · Criterios: CA-11

#### Acceptance Criteria

1. THE Compose_Prod SHALL asignar `mem_limit` de 512m a Sandbox_DB.
2. THE Compose_Prod SHALL asignar `mem_limit` de 384m a App_DB.
3. THE Compose_Prod SHALL asignar `mem_limit` de 512m a la API.
4. WHEN se ejecuta `docker stats --no-stream` con Sandbox_DB, App_DB y la API en estado running, THE Compose_Prod SHALL mostrar en la columna MEM USAGE / LIMIT un límite de 512 MiB para Sandbox_DB, 384 MiB para App_DB y 512 MiB para la API.
5. IF un contenedor con `mem_limit` definido intenta usar más memoria que su límite, THEN THE Compose_Prod SHALL terminar los procesos de ese contenedor por falta de memoria (OOM kill) sin terminar ni reiniciar los otros dos contenedores, y `docker inspect` SHALL reportar `OOMKilled` igual a `true` para el contenedor afectado.
6. THE Compose_Prod SHALL mantener la suma de los tres valores de `mem_limit` en 1408 MiB como máximo, dejando al menos 600 MiB de los 2048 MiB de la t3.small para el sistema operativo y Docker.

### Requirement 4: Disco propio para el sandbox

**User Story:** Como integrante del equipo, quiero que Sandbox_DB tenga su propio disco, para que un script que llene el disco no tumbe App_DB.

**Trazabilidad:** RF-04.4 (Debe), RF-06.3 (Debe), refuerza RF-01.4 del E1 · Tareas: T-04, T-14 · Criterios: CA-12, CA-20

#### Acceptance Criteria

1. THE Compose_Prod SHALL montar los datos de Sandbox_DB en el servicio `sandbox_db` mediante un bind mount en sintaxis larga con `type: bind`, `source: ${SANDBOX_DATA_DIR:-./.data/sandbox}`, `target: /var/lib/postgresql/data` y `bind: { create_host_path: false }`, en lugar de la sintaxis corta y del volumen `sandbox_data`, y SHALL NOT declarar el volumen `sandbox_data` en ninguno de sus servicios.
2. THE Compose_Prod SHALL montar en `/var/lib/postgresql/data` un directorio de datos que sea un subdirectorio de `/srv/sandbox` (`/srv/sandbox/pgdata`) y no la raíz del disco, de modo que PostgreSQL no encuentre `lost+found` (que permanece en la raíz `/srv/sandbox`) dentro de su directorio de datos.
3. THE `.gitignore` SHALL incluir la entrada `.data/` para que el directorio de datos por defecto del entorno local no se versione.
4. WHEN el Equipo crea el archivo `.env` en la Instancia, THE Equipo SHALL definir en él `SANDBOX_DATA_DIR=/srv/sandbox/pgdata`, porque sin esa variable el valor por defecto `./.data/sandbox` dejaría los datos de Sandbox_DB en el disco raíz y CA-12 fallaría, lo cual es verificable con `df -h` sobre la ruta del bind mount, que debe mostrar el dispositivo del Volumen_Sandbox y no el de `/`.
5. WHEN el Equipo prepara el Volumen_Sandbox, THE Equipo SHALL adjuntarlo a la Instancia como dispositivo de bloques independiente del volumen raíz, formatearlo con un sistema de archivos y montarlo en `/srv/sandbox` por UUID mediante una entrada en `/etc/fstab` con la opción `nofail`.
6. WHEN se ejecuta `df -h /srv/sandbox`, THE Instancia SHALL mostrar un dispositivo distinto al mostrado por `df -h /`.
7. WHEN se ejecuta `findmnt /srv/sandbox` tras reiniciar la Instancia, THE Instancia SHALL mostrar `/srv/sandbox` montado desde el UUID registrado en `/etc/fstab`, sin intervención manual.
8. IF `SANDBOX_DATA_DIR` apunta a una ruta que no existe en el host (por ejemplo, el Volumen_Sandbox no se montó y `/srv/sandbox/pgdata` no existe), THEN Docker SHALL negarse a iniciar el contenedor `sandbox_db` sin crear el directorio, tanto con `docker compose up` como en el reinicio automático por `restart: unless-stopped` tras reiniciar la Instancia, y la ruta `/srv/sandbox/pgdata` SHALL NOT aparecer en el disco raíz. Esta garantía la proporciona `create_host_path: false` del criterio 1 en Compose_Prod, sin depender de ninguna unidad systemd. En ese mismo caso, si el Volumen_Sandbox no está adjunto durante el arranque, la Instancia SHALL completar el arranque del sistema operativo sin entrar en modo de emergencia gracias a la opción `nofail` del criterio 5.
9. WHEN el Equipo crea el directorio `/srv/sandbox/pgdata`, THE Equipo SHALL crearlo únicamente después de confirmar con `findmnt /srv/sandbox` que `/srv/sandbox` es un punto de montaje del Volumen_Sandbox, porque un directorio creado antes del montaje quedaría en el disco raíz y la protección de `create_host_path: false` del criterio 8 no tendría efecto.
10. WHILE un script con `generate_series` llena el Volumen_Sandbox hasta 100 % de uso según `df -h /srv/sandbox`, THE App_DB SHALL responder a un login válido y a una consulta de historial con éxito en un máximo de 3 segundos cada uno, y el uso de `/` SHALL variar en no más de 1 punto porcentual respecto al valor previo al script.

### Requirement 5: Cabeceras de seguridad en Caddy

**User Story:** Como responsable de seguridad, quiero cabeceras HTTP de seguridad, para reducir la superficie de ataque del navegador.

**Trazabilidad:** RF-04.5 (Debe) · Tareas: T-05, T-06 · Criterios: CA-13

#### Acceptance Criteria

1. WHEN Caddy envía una respuesta HTTPS con cualquier código de estado (2xx, 3xx, 4xx o 5xx), THE Caddy SHALL incluir en ella las cabeceras `Strict-Transport-Security: max-age=31536000; includeSubDomains`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, `Referrer-Policy: strict-origin-when-cross-origin` y `Content-Security-Policy`, cada una exactamente una vez.
2. WHEN Caddy envía una respuesta, THE Caddy SHALL omitir la cabecera `Server` mediante `-Server` en el bloque `header` del `Caddyfile`.
3. THE Caddy SHALL usar como valor inicial de `Content-Security-Policy` exactamente `default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'`.
4. WHEN el Equipo carga el build de producción del frontend en un navegador y recorre las pantallas de login, registro y análisis, THE Equipo SHALL verificar que la consola del navegador muestra 0 mensajes de violación de CSP.
5. IF la consola del navegador muestra 1 o más violaciones de CSP durante la verificación del criterio 4, THEN THE Equipo SHALL ampliar la CSP solo con las directivas de la fuente bloqueada, repetir la verificación hasta obtener 0 violaciones y documentar cada directiva añadida.
6. WHEN se ejecuta `curl -sI https://<dominio>`, THE Caddy SHALL devolver las cinco cabeceras del criterio 1 con los valores indicados y 0 cabeceras `Server`.

### Requirement 6: Health-check sin filtración de información

**User Story:** Como responsable de seguridad, quiero que `/api/health-check` no revele detalles internos, para no exponer errores ni versiones.

**Trazabilidad:** RF-04.6 (Debe) · Tareas: T-07 · Criterios: CA-14

#### Acceptance Criteria

1. WHEN se solicita `/api/health-check` y App_DB responde a una consulta de verificación en un máximo de 2 segundos, THE API SHALL responder en un máximo de 3 segundos con un objeto JSON que contenga únicamente la clave `status` con el valor `"ok"`.
2. IF App_DB no responde a la consulta de verificación en un máximo de 2 segundos o rechaza la conexión, THEN THE API SHALL responder en un máximo de 3 segundos con un objeto JSON que contenga únicamente la clave `status` con el valor `"error"`, sin mensaje de error, sin versión de PostgreSQL, sin nombre de host y sin traza de pila.
3. IF ocurre una excepción no controlada durante el health-check, THEN THE API SHALL responder con un objeto JSON que contenga únicamente la clave `status` con el valor `"error"`, sin ningún otro campo ni texto de la excepción.
4. IF ocurre un error durante el health-check (incluida la indisponibilidad de App_DB), THEN THE API SHALL registrar en el log del servidor la marca de tiempo, el tipo de excepción y el mensaje de error, sin incluir esa información en la respuesta HTTP.
5. WHEN se solicita `/api/health-check` sin credenciales de autenticación, THE API SHALL procesar la solicitud y responder según los criterios 1 a 3.

### Requirement 7: Verificación local previa al despliegue

**User Story:** Como integrante del equipo, quiero validar los cambios de código en local, para no llevar regresiones a AWS.

**Trazabilidad:** RNF-05 del E1; cierra la Fase 1 · Tareas: T-08 · Criterios: CA-09 a CA-14 (verificables en local)

#### Acceptance Criteria

1. IF el archivo `.env` local no existe, o `JWT_SECRET` falta o está vacío en él, THEN THE Script_Verificacion_Local SHALL detenerse antes de levantar contenedores, mostrar un mensaje que indique qué falta (el archivo `.env` o `JWT_SECRET`) y cómo corregirlo, y terminar con código de salida distinto de 0.
2. WHEN el Script_Verificacion_Local ejecuta `docker compose -f docker-compose.prod.yml up -d --build`, THE Script_Verificacion_Local SHALL crear antes de ese comando el directorio `./.data/sandbox` si no existe, o el directorio indicado por `SANDBOX_DATA_DIR` si el `.env` lo define, porque `create_host_path: false` (Requirement 4, criterio 1) impide que Docker lo cree.
3. IF el Script_Verificacion_Local no puede crear el directorio de datos de Sandbox_DB, THEN THE Script_Verificacion_Local SHALL detenerse antes de levantar contenedores, mostrar un mensaje que indique la ruta que no pudo crear y la causa, y terminar con código de salida distinto de 0.
4. WHEN se completan T-01 a T-07 y el `.env` local define un `JWT_SECRET` no vacío, THE Equipo SHALL ejecutar `docker compose -f docker-compose.prod.yml up -d --build` en local y confirmar que los cinco servicios definidos en `docker-compose.prod.yml` (no los de `docker-compose.yml`, cuyo `docker compose up -d` levanta solo el entorno de desarrollo con TiendaDB) alcanzan el estado "running" o "healthy" en un máximo de 120 segundos.
5. WHEN todos los servicios de `docker-compose.prod.yml` están en estado "running" o "healthy", THE Equipo SHALL verificar que el endpoint de salud de la API responde con éxito en un máximo de 5 segundos.
6. WHEN la API responde con éxito, THE Equipo SHALL ejecutar los criterios CA-09 a CA-14 en local y registrar el resultado de cada uno como aprobado o no aprobado, y para CA-09 THE Script_Verificacion_Local SHALL ejecutar `docker compose -f docker-compose.prod.yml config` con `JWT_SECRET` definido como vacío solo en el entorno del proceso, sin modificar el archivo `.env`, y SHALL aprobar el criterio únicamente si el comando termina con código de salida distinto de 0 y muestra «falta JWT_SECRET».
7. IF algún servicio de `docker-compose.prod.yml` no alcanza el estado "running" o "healthy" en 120 segundos, o algún criterio de CA-09 a CA-14 no se aprueba, THEN THE Equipo SHALL abstenerse de abrir el Pull Request, registrar el servicio o criterio que falló y corregir los cambios antes de repetir la verificación completa.
8. WHEN los seis criterios CA-09 a CA-14 se registran como aprobados y todos los servicios están en estado "running" o "healthy", THE Equipo SHALL abrir un Pull Request con los cambios de la Fase 1 que incluya el resultado registrado de cada criterio.

### Requirement 8: Protección de la cuenta raíz

**User Story:** Como responsable de la cuenta, quiero proteger la cuenta raíz, para que no sea un vector de compromiso.

**Trazabilidad:** RF-05.1 (Debe) · Tareas: T-09 · Criterios: CA-15

#### Acceptance Criteria

1. WHILE la Cuenta_Raiz está en operación, THE Cuenta_Raiz SHALL tener al menos 1 dispositivo MFA activo y habilitado, de modo que el inicio de sesión raíz requiera un segundo factor.
2. WHILE la Cuenta_Raiz está en operación, THE Cuenta_Raiz SHALL tener 0 access keys, activas o inactivas.
3. WHILE la Cuenta_Raiz está en operación, THE Cuenta_Raiz SHALL tener activado el acceso de usuarios y roles IAM a la información de facturación.
4. WHEN se consulta el resumen de la cuenta, THE Cuenta_Raiz SHALL mostrar `AccountMFAEnabled=1` y `AccountAccessKeysPresent=0`.
5. IF el resumen de la cuenta muestra `AccountMFAEnabled=0` o `AccountAccessKeysPresent` distinto de 0, THEN THE Cuenta_Raiz SHALL ser marcada como no conforme con CA-15 en el resultado de la verificación, indicando cuál de las dos condiciones falló, y el estado de la cuenta SHALL permanecer sin modificaciones por la verificación.
6. IF la consulta del resumen de la cuenta falla o no devuelve alguno de los dos valores `AccountMFAEnabled` y `AccountAccessKeysPresent`, THEN THE Cuenta_Raiz SHALL ser reportada como no verificable, con un error que indique la causa de la falla, y la verificación SHALL NOT darse por aprobada.

### Requirement 9: Usuarios IAM con MFA obligatorio

**User Story:** Como responsable de la cuenta, quiero un usuario IAM por integrante con MFA obligatorio, para que nadie opere sin segundo factor ni con llaves de larga duración.

**Trazabilidad:** RF-05.2 (Debe), RF-05.3 (Debe; desviación registrada en Requirement 24, criterio 5) · Tareas: T-10 · Criterios: CA-15, CA-16 (desviación registrada en Requirement 24, criterio 6)

#### Acceptance Criteria

1. THE Equipo SHALL tener exactamente un Usuario_IAM por integrante, sin ninguna access key creada (0 access keys por usuario, activas o inactivas).
2. WHILE una sesión de un Usuario_IAM no tiene MFA autenticado, THE Politica_Force_MFA SHALL denegar todas las acciones de AWS, excepto las necesarias para que el usuario gestione su propia contraseña y registre, active y sincronice su propio dispositivo MFA.
3. THE Grupo_Admins SHALL tener adjunta la política `AdministratorAccess`, con la Politica_Force_MFA aplicada a sus miembros, y SHALL tener como miembros a los integrantes del Equipo.
4. WHERE se necesita la CLI de AWS, THE Equipo SHALL usar CloudShell y SHALL NOT crear ni almacenar credenciales locales de larga duración (access keys) en ningún equipo.
5. WHEN se genera y descarga el reporte de credenciales de IAM, THE Usuario_IAM SHALL aparecer en el reporte con `mfa_active=true`, `access_key_1_active=false` y `access_key_2_active=false` para el 100 % de los usuarios.
6. WHEN un Usuario_IAM inicia sesión con MFA autenticado y ejecuta una acción permitida por los permisos de su grupo, THE Politica_Force_MFA SHALL permitir la acción sin responder `AccessDenied`.

### Requirement 10: Rol de la instancia sin credenciales en disco

**User Story:** Como operador, quiero que la Instancia use un rol IAM, para administrarla por SSM sin guardar credenciales.

**Trazabilidad:** RF-05.4 (Debe) · Tareas: T-11, T-13 · Criterios: CA-17

**Recurso:** la Plantilla_CFN crea el Rol_EC2, su perfil de instancia y la Instancia en el Stack `pgguardian` (Requirement 29). Los criterios de verificación no cambian.

#### Acceptance Criteria

1. THE Rol_EC2 SHALL tener adjunta la política administrada `AmazonSSMManagedInstanceCore`, y la consulta de las políticas adjuntas al Rol_EC2 SHALL listar esa política.
2. THE Instancia SHALL obtener sus credenciales de AWS exclusivamente del Rol_EC2 mediante credenciales temporales entregadas por el servicio de metadatos de la Instancia, sin almacenar claves de acceso de AWS (ID de clave de acceso ni clave secreta) en ningún archivo del disco de la Instancia, incluidos los archivos de entorno, de configuración de AWS y de la aplicación.
3. WHEN la Instancia alcanza el estado `running`, THE Instancia SHALL aparecer como `Online` en Systems Manager en un máximo de 300 segundos.
4. IF la Instancia no aparece como `Online` en Systems Manager dentro de 300 segundos tras alcanzar el estado `running`, THEN THE Equipo SHALL reportar un fallo que indique que la Instancia no es administrable por SSM, sin modificar el Rol_EC2 ni los recursos ya creados.

### Requirement 11: Administración solo por Session Manager

**User Story:** Como operador, quiero administrar el servidor sin SSH, para evitar exponer el puerto 22 y repartir llaves `.pem`.

**Trazabilidad:** RF-05.5 (Debe), reemplaza RF-03.3 del E1 · Tareas: T-16 · Criterios: CA-17, CA-18

#### Acceptance Criteria

1. THE Security_Group SHALL mantener 0 reglas de entrada (ingress) para el puerto TCP 22, tanto para IPv4 (`0.0.0.0/0`) como para IPv6 (`::/0`) y para cualquier otro origen.
2. THE Instancia SHALL ser lanzada sin par de llaves asociado (sin llave `.pem`), de modo que el atributo de nombre de llave de la Instancia esté vacío.
3. WHEN un Usuario_IAM con permiso para iniciar sesiones abre una sesión de Session_Manager hacia la Instancia, THE Session_Manager SHALL abrir una consola interactiva en la Instancia en un máximo de 30 segundos, y CloudTrail SHALL registrar un evento `StartSession` que identifique a ese Usuario_IAM y a la Instancia en un máximo de 15 minutos.
4. WHEN el Equipo verifica el acceso sin SSH, THE Equipo SHALL confirmar que la Instancia no tiene par de llaves asociado, mediante `aws ec2 describe-instances` con el campo `KeyName` vacío o ausente, y que el puerto 22 está cerrado en el Security_Group, mediante `aws ec2 describe-security-groups` sin ninguna regla de entrada TCP/22.
5. IF un cliente intenta conectarse a la Instancia por SSH en el puerto 22, THEN THE Instancia SHALL rechazar o no responder a la conexión, sin establecer ninguna sesión.

### Requirement 12: Security Group mínimo

**User Story:** Como responsable de seguridad, quiero exponer solo 80 y 443, para minimizar la superficie de ataque.

**Trazabilidad:** RF-06.1 (Debe) · Tareas: T-12 · Criterios: CA-18

**Recurso:** la Plantilla_CFN crea el Security_Group con sus 2 reglas de entrada en el Stack `pgguardian` (Requirement 29). Los criterios de verificación no cambian.

#### Acceptance Criteria

1. THE Security_Group SHALL permitir la entrada de tráfico TCP en los puertos 80 y 443 desde `0.0.0.0/0`.
2. THE Security_Group SHALL contener exactamente 2 reglas de entrada: una para TCP/80 y otra para TCP/443, ambas con origen `0.0.0.0/0`, sin reglas de entrada para otros puertos, protocolos u orígenes (incluido SSH en el puerto 22 e IPv6 `::/0`).
3. WHEN se ejecuta `nmap -Pn -p- <elastic-ip>` desde una red externa a la VPC, THE Instancia SHALL mostrar los puertos TCP 80 y 443 en estado `open` y los 65533 puertos TCP restantes en estado `filtered` o `closed`.
4. IF se intenta una conexión TCP a un puerto distinto de 80 y 443 en la `<elastic-ip>`, THEN THE Security_Group SHALL descartar el tráfico sin establecer la conexión, de modo que el cliente agote el tiempo de espera o reciba un rechazo, y no se abra ninguna sesión.

### Requirement 13: IMDSv2 obligatorio

**User Story:** Como responsable de seguridad, quiero exigir IMDSv2, para mitigar el robo de credenciales por SSRF.

**Trazabilidad:** RF-06.2 (Debe) · Tareas: T-13 · Criterios: CA-19

**Recurso:** la Plantilla_CFN define las opciones de metadatos de la Instancia (`MetadataOptions`) en el Stack `pgguardian` (Requirement 29). Los criterios de verificación no cambian.

#### Acceptance Criteria

1. THE Instancia SHALL tener `HttpTokens=required`, `HttpEndpoint=enabled` y `HttpPutResponseHopLimit=1` en sus opciones de metadatos, verificable con `aws ec2 describe-instances` para el identificador de la Instancia.
2. WHEN se ejecuta desde la Instancia `curl http://169.254.169.254/latest/meta-data/` sin token de sesión IMDSv2, THE Instancia SHALL responder con código HTTP `401` y no devolver ningún contenido de metadatos en el cuerpo de la respuesta.
3. WHEN se ejecuta desde la Instancia una solicitud `PUT` a `http://169.254.169.254/latest/api/token` con el encabezado `X-aws-ec2-metadata-token-ttl-seconds: 60` y después una solicitud `GET` a `http://169.254.169.254/latest/meta-data/` con el token obtenido en el encabezado `X-aws-ec2-metadata-token`, THE Instancia SHALL responder a la solicitud `GET` con código HTTP `200` y la lista de categorías de metadatos.
4. IF se ejecuta desde la Instancia una solicitud `GET` a `http://169.254.169.254/latest/meta-data/` con un token expirado o con un valor de token inválido, THEN THE Instancia SHALL responder con código HTTP `401` y no devolver ningún contenido de metadatos.
5. WHEN un contenedor Docker en la Instancia (red bridge) intenta `PUT http://169.254.169.254/latest/api/token`, THE Instancia SHALL no entregar el token, de modo que la solicitud falle o agote el tiempo en un máximo de 5 segundos y los contenedores no alcancen el servicio de metadatos. El salto adicional del contenedor excede `HttpPutResponseHopLimit=1`; el agente SSM del host no se ve afectado.

### Requirement 14: Discos cifrados

**User Story:** Como responsable de seguridad, quiero discos cifrados con tamaño definido, para proteger los datos en reposo.

**Trazabilidad:** RF-06.3 (Debe) · Tareas: T-13, T-14 · Criterios: CA-20

**Recurso:** la Plantilla_CFN crea el disco raíz (en la definición de la Instancia) y el Volumen_Sandbox con su attachment en `/dev/sdf`, en el Stack `pgguardian` (Requirement 29). El formateo y el montaje en `/srv/sandbox` siguen en `bootstrap_host.sh`. Los criterios de verificación no cambian.

#### Acceptance Criteria

1. THE Instancia SHALL tener un disco raíz de tipo gp3 con tamaño de exactamente 20 GB y con el atributo `Encrypted=true`.
2. THE Instancia SHALL tener un segundo volumen de tipo gp3 con tamaño de exactamente 8 GB y con el atributo `Encrypted=true`, denominado Volumen_Sandbox, montado en `/srv/sandbox`.
3. WHEN la Instancia se reinicia con `sudo reboot` y vuelve al estado `running` en un máximo de 300 segundos, THE Instancia SHALL mostrar ambos volúmenes con `Encrypted=true` y `/srv/sandbox` montado como punto de montaje activo del Volumen_Sandbox.
4. IF la Instancia no vuelve al estado `running` en 300 segundos después de `sudo reboot`, o `/srv/sandbox` no está montado tras el reinicio, THEN THE Instancia SHALL conservar sin modificación los datos de ambos volúmenes y el criterio 3 SHALL considerarse fallido.
5. IF se intenta crear o adjuntar un volumen con `Encrypted=false` a la Instancia, THEN THE Instancia SHALL ser considerada no conforme con este requisito.

### Requirement 15: Swap persistente

**User Story:** Como operador, quiero 2 GB de swap, para amortiguar picos de memoria en la t3.small.

**Trazabilidad:** RF-06.4 (Debe) · Tareas: T-16 · Criterios: CA-20

#### Acceptance Criteria

1. WHEN la configuración de la Instancia finaliza, THE Instancia SHALL tener exactamente un área de swap activa con un tamaño de 2 GiB (2 147 483 648 bytes), con una tolerancia de ±1 MiB, verificable con `swapon --show`.
2. WHEN la Instancia se reinicia, THE Instancia SHALL tener activa, a los 60 segundos de completado el arranque, el área de swap de 2 GiB (±1 MiB) sin intervención manual, verificable con `swapon --show`.
3. WHEN la Instancia se reinicia, THE Instancia SHALL conservar la misma configuración de swap (tamaño de 2 GiB y un único área de swap) tras 3 reinicios consecutivos, sin duplicar áreas de swap.
4. IF el área de swap no se activa durante el arranque, THEN THE Instancia SHALL completar el arranque, dejar `swapon --show` sin áreas activas y registrar un mensaje de error en el registro del sistema que indique el fallo de activación del swap.

### Requirement 16: Protección contra terminación

**User Story:** Como responsable de la cuenta, quiero evitar la terminación accidental, para no perder la Instancia.

**Trazabilidad:** RF-06.5 (Debe) · Tareas: T-13 · Criterios: CA-20

**Recurso:** la Plantilla_CFN fija `DisableApiTermination: true` en la Instancia del Stack `pgguardian` (Requirement 29). Los criterios de verificación no cambian.

#### Acceptance Criteria

1. WHEN la Instancia entra en estado `running` por primera vez tras su aprovisionamiento, THE Instancia SHALL tener el atributo `disableApiTermination` con valor `true`.
2. WHEN la Instancia se reinicia, THE Instancia SHALL conservar el atributo `disableApiTermination` con valor `true`.
3. IF se envía una solicitud de terminación de la Instancia por API o consola mientras `disableApiTermination` tiene valor `true`, THEN THE Instancia SHALL rechazar la solicitud, SHALL permanecer en su estado actual sin pérdida de datos y SHALL devolver al solicitante un error que indique que la protección contra terminación está activa.
4. IF el atributo `disableApiTermination` tiene un valor distinto de `true` tras el aprovisionamiento o tras un reinicio, THEN THE Instancia SHALL ser reportada como no conforme en la verificación de CA-20.

### Requirement 17: Etiquetado de recursos

**User Story:** Como responsable de costos, quiero recursos etiquetados, para identificarlos y asignarles responsables.

**Trazabilidad:** RF-06.6 (Debería) · Tareas: T-13 (T-14 y T-15 para volumen y Elastic IP) · Criterios: CA-21

**Recurso:** la Plantilla_CFN asigna las etiquetas a la Instancia, al disco raíz (`PropagateTagsToVolumeOnCreation: true`), al Volumen_Sandbox y a la Elastic_IP, y valida la longitud de `Owner` con su parámetro (Requirement 29). Los criterios de verificación no cambian.

#### Acceptance Criteria

1. WHEN la Instancia es creada o actualizada, THE Equipo SHALL asignar a la Instancia las etiquetas `Project=PgGuardian`, `Env=prod` y `Owner`, donde el valor de `Owner` es una cadena no vacía de 1 a 256 caracteres.
2. WHEN el Volumen_Sandbox, el disco raíz o la Elastic_IP es creado o actualizado, THE Equipo SHALL asignar a cada uno de estos recursos las etiquetas `Project=PgGuardian`, `Env=prod` y `Owner`, donde el valor de `Owner` es una cadena no vacía de 1 a 256 caracteres.
3. IF el valor de `Owner` está vacío, no está definido o excede 256 caracteres, THEN THE Equipo SHALL tratar el recurso como no conforme con CA-21, indicar que la etiqueta `Owner` es inválida y corregirla sin modificar el resto del recurso.

### Requirement 18: Parches automáticos de seguridad

**User Story:** Como operador, quiero parches de seguridad automáticos, para reducir el trabajo de mantenimiento.

**Trazabilidad:** RF-06.7 (Debería) · Tareas: T-16 · Criterios: CA-22

#### Acceptance Criteria

1. THE Instancia SHALL tener el paquete `unattended-upgrades` instalado y habilitado para que arranque en cada reinicio del sistema operativo, configurado para instalar únicamente parches de seguridad del sistema operativo.
2. THE Instancia SHALL tener en `/etc/apt/apt.conf.d/20auto-upgrades` los valores `APT::Periodic::Update-Package-Lists "1"` y `APT::Periodic::Unattended-Upgrade "1"`, es decir, ejecución una vez cada 1 día para ambas tareas.
3. WHEN se ejecuta `systemctl is-active unattended-upgrades`, THE Instancia SHALL devolver `active` con código de salida 0.
4. WHEN se ejecuta `systemctl is-enabled unattended-upgrades`, THE Instancia SHALL devolver `enabled` con código de salida 0.
5. IF `unattended-upgrades` falla al instalar un parche, THEN THE Instancia SHALL registrar el error en `/var/log/unattended-upgrades/unattended-upgrades.log` y conservar los paquetes ya instalados sin revertirlos.

### Requirement 19: Elastic IP y despliegue con HTTPS válido

**User Story:** Como usuario final, quiero acceder por HTTPS con certificado válido, para usar PgGuardian de forma segura.

**Trazabilidad:** RF-06.8 (Podría), RF-03.1, RF-03.4 y RF-03.5 del E1; el criterio 8 apoya la sustitución de RF-03.6 (Requirement 24, criterio 3) · Tareas: T-15, T-17, T-18 y la sección «Encender y detener» del runbook (sin T-xx en la fuente) · Criterios: CA-23

**Recurso:** la Plantilla_CFN crea la Elastic_IP del criterio 1 y la asocia a la Instancia en el Stack `pgguardian` (Requirement 29); su output `AppDomain` da el valor de `APP_DOMAIN` del criterio 2. Los criterios de verificación no cambian.

#### Acceptance Criteria

1. THE Elastic_IP SHALL permanecer asignada a la cuenta de AWS y asociada a la Instancia, de modo que la dirección IPv4 pública de la Instancia sea idéntica a la de la Elastic_IP antes y después de detener e iniciar la Instancia.
2. WHEN se despliega, THE Equipo SHALL crear el archivo `.env` con permisos `600` y con la variable `APP_DOMAIN=<ip-con-guiones>.sslip.io`, donde `<ip-con-guiones>` es la dirección de la Elastic_IP con los cuatro octetos separados por guiones (por ejemplo, `203-0-113-10` para `203.0.113.10`).
3. WHEN se ejecuta `docker compose -f docker-compose.prod.yml up -d --build`, THE Caddy SHALL obtener un certificado de Let's Encrypt para el Dominio_Publico en un máximo de 120 segundos desde que el contenedor de Caddy está en ejecución.
4. IF Caddy no obtiene el certificado de Let's Encrypt para el dominio `sslip.io` en 120 segundos o Let's Encrypt rechaza la solicitud, THEN THE Equipo SHALL configurar un subdominio de DuckDNS que resuelva a la Elastic_IP como Dominio_Publico, actualizar `APP_DOMAIN` en `.env` y volver a ejecutar `docker compose -f docker-compose.prod.yml up -d`.
5. WHEN se abre `https://<Dominio_Publico>` en un navegador, THE Caddy SHALL presentar un certificado emitido por Let's Encrypt, vigente y cuyo nombre coincida con el Dominio_Publico, sin advertencias de seguridad del navegador.
6. WHEN se solicita `http://<Dominio_Publico>` en el puerto 80, THE Caddy SHALL redirigir la solicitud a `https://<Dominio_Publico>`.
7. IF el certificado no se obtiene tras usar el dominio de DuckDNS, THEN THE Caddy SHALL rechazar las conexiones HTTPS sin servir la aplicación por HTTP sin cifrar, y THE Equipo SHALL registrar el error de Caddy visible en los logs del contenedor.
8. WHEN el Equipo detiene e inicia la Instancia, THE aplicación SHALL responder {"status":"ok"} en /api/health-check por la misma URL HTTPS en un máximo de 5 minutos después del inicio, sin intervención manual.

### Requirement 20: Presupuesto y alertas de gasto

**User Story:** Como responsable de costos, quiero alertas de gasto, para no agotar los 100 USD de créditos.

**Trazabilidad:** RF-07.1 (Debe); respalda la sustitución de RF-03.6 del E1 (Requirement 24, criterio 3) · Tareas: T-19 · Criterios: CA-24

**Recurso:** la Plantilla_CFN crea el Presupuesto en el Stack `pgguardian` (Requirement 29), con el monto del parámetro `MonthlyBudgetUsd` (por defecto 30) y las notificaciones dirigidas al parámetro `AlertEmail`. Los criterios de verificación no cambian.

#### Acceptance Criteria

1. THE Presupuesto SHALL tener un monto límite de 30.00 USD por periodo mensual calendario, con tipo de costo "gasto real", reinicio el día 1 de cada mes y `CostTypes` con `IncludeCredit=false` e `IncludeRefund=false`, de modo que mida el gasto bruto antes de aplicar créditos, porque con los créditos descontados el gasto real sería 0 USD y ninguna alerta se dispararía.
2. THE Presupuesto SHALL tener tres alertas sobre el gasto real, con umbrales de 50 % (15.00 USD), 80 % (24.00 USD) y 100 % (30.00 USD) del monto límite.
3. THE Presupuesto SHALL tener una alerta sobre el gasto pronosticado, con umbral de 100 % (30.00 USD) del monto límite.
4. THE Presupuesto SHALL enviar cada alerta a al menos 1 y como máximo 5 direcciones de correo electrónico de destinatarios configurados.
5. WHEN se consulta AWS Budgets, THE Presupuesto SHALL mostrar exactamente cuatro notificaciones: tres de gasto real (50 %, 80 % y 100 %) y una de gasto pronosticado (100 %).
6. WHEN el gasto real acumulado del mes alcanza o supera el umbral de una alerta, THE Presupuesto SHALL enviar una notificación por correo electrónico a los destinatarios configurados.
7. IF el presupuesto no existe o no tiene exactamente cuatro notificaciones al consultar AWS Budgets, THEN THE Presupuesto SHALL considerarse no conforme con CA-24 y la verificación SHALL registrar la diferencia encontrada (notificaciones faltantes o sobrantes).

### Requirement 21: Detección de anomalías de costo

**User Story:** Como responsable de costos, quiero detectar gastos anómalos, para reaccionar a tiempo.

**Trazabilidad:** RF-07.2 (Debería; desviación de R21.2 registrada en Requirement 24, criterio 10) · Tareas: T-20 · Criterios: CA-24

**Recurso:** la Plantilla_CFN crea el monitor y la suscripción de Anomaly_Detection en el Stack `pgguardian` (Requirement 29). Si el despliegue falla en esos dos recursos, se crean con `scripts/aws/create_anomaly_detection.sh` (Requirement 29, criterio 10). Los criterios de verificación no cambian.

#### Acceptance Criteria

1. WHILE el servicio Anomaly_Detection está desplegado, THE Anomaly_Detection SHALL mantener al menos 1 monitor en estado activo que evalúe el gasto de la cuenta, con un máximo de 10 monitores activos.
2. WHEN el Anomaly_Detection detecta un gasto anómalo, THE Anomaly_Detection SHALL enviar un resumen diario por correo con las anomalías detectadas, mediante una suscripción con frecuencia `DAILY` y correo directo al Equipo.
3. IF la suscripción de correo del Equipo no está confirmada o el envío del aviso falla, THEN THE Anomaly_Detection SHALL conservar el registro de la anomalía detectada y SHALL indicar el fallo de entrega en el estado del monitor, de modo que el Equipo pueda corregir la suscripción.
4. WHEN el Anomaly_Detection envía un aviso, THE Anomaly_Detection SHALL incluir en el aviso el nombre del monitor, el monto del gasto anómalo en USD y la fecha en que se detectó.

### Requirement 22: Recuperación automática de la instancia

**User Story:** Como operador, quiero recuperación automática ante fallos del sistema, para reducir el tiempo de caída.

**Trazabilidad:** RF-07.3 (Debería) · Tareas: T-21 · Criterios: CA-25

**Recurso:** la Plantilla_CFN crea la Alarma_Recover en el Stack `pgguardian` (Requirement 29). Los criterios de verificación no cambian.

#### Acceptance Criteria

1. THE Alarma_Recover SHALL existir en us-east-2 sobre la métrica `StatusCheckFailed_System` de la Instancia, con estadística Maximum, periodo de 60 segundos, umbral mayor o igual a 1 y 2 periodos consecutivos de evaluación.
2. WHEN la métrica `StatusCheckFailed_System` activa la alarma, THE Alarma_Recover SHALL ejecutar la acción `arn:aws:automate:us-east-2:ec2:recover` en un máximo de 60 segundos después del cambio de estado de la alarma a ALARM.
3. IF la métrica `StatusCheckFailed_System` no reporta datos durante un periodo de evaluación, THEN THE Alarma_Recover SHALL tratar los datos faltantes como no incumplimiento (notBreaching) y mantener su estado actual sin ejecutar la acción de recuperación.
4. WHEN la acción de recuperación finaliza, THE Instancia SHALL conservar su identificador de instancia, su dirección IP privada, su dirección IP elástica asociada y los datos de sus volúmenes EBS.

### Requirement 23: Respaldos con snapshots manuales de EBS

**User Story:** Como operador, quiero snapshots de EBS verificados, para poder restaurar los datos.

**Trazabilidad:** RF-07.4 (Debe; desviación registrada en Requirement 24, criterio 4) · Tareas: T-22, T-27 · Criterios: CA-26

#### Acceptance Criteria

1. WHEN el sistema alcanza el estado estable (los servicios de App_DB y de la aplicación responden a sus verificaciones de salud durante al menos 5 minutos consecutivos), THE Equipo SHALL tomar un Snapshot_Manual del disco raíz (que contiene los datos de App_DB) y un Snapshot_Manual del Volumen_Sandbox.
2. WHEN faltan 24 horas o menos para la grabación del video, THE Equipo SHALL tomar un segundo Snapshot_Manual del disco raíz y un segundo Snapshot_Manual del Volumen_Sandbox antes de que empiece la grabación del video.
3. WHEN el Equipo toma un Snapshot_Manual, THE Equipo SHALL verificar que el snapshot queda en estado `completed`, sin restaurarlo.
4. IF un Snapshot_Manual termina en estado `error`, THEN THE Equipo SHALL repetir el Snapshot_Manual del mismo volumen hasta obtener uno en estado `completed`.

### Requirement 24: Registro de decisiones y cambios al E1

**User Story:** Como integrante del equipo, quiero registrar cada desviación del E1 y de la fuente, para tener justificación y aprobación documentadas.

**Trazabilidad:** RF-08.1 (Debe), sección 3 de la fuente (cambios a RF-01.4, RF-03.3 y RF-03.6), desviaciones de RF-07.4/CA-26, RF-05.3 y CA-16, hallazgo del despliegue del Requirement 26, decisión de usar CloudFormation (Requirement 29), cambio de alcance del E2 (Requirement 28) y cambio de R21.2 (Requirement 21) · Tareas: T-26 · Criterios: CA-27

#### Acceptance Criteria

1. THE Registro_Decisiones SHALL contener una entrada para el refuerzo de RF-01.4 mediante el disco propio del sandbox (RF-04.4), con los campos: identificador del requisito afectado, descripción del cambio respecto al E1, justificación, fecha (formato AAAA-MM-DD) y aprobador, y con la justificación «un script que llena el disco no puede tumbar `app_db`».
2. THE Registro_Decisiones SHALL contener una entrada para el reemplazo de RF-03.3 por Session Manager con el puerto 22 cerrado (RF-05.5), con los mismos campos que el criterio 1 y con la justificación «las IP domésticas cambian».
3. THE Registro_Decisiones SHALL contener una entrada que sustituye a RF-03.6, con los mismos campos que el criterio 1, con el cambio «la instancia se enciende o se detiene a criterio del Equipo; no es requisito que esté disponible 24/7 ni que se detenga fuera de las demostraciones» y con la justificación «el peor caso (24/7, unos 22 USD al mes) cabe en los créditos de 100 USD, y el Presupuesto (R20) avisa si el gasto se desvía. La evaluación se hace con un video grabado, no con acceso en vivo».
4. THE Registro_Decisiones SHALL contener una entrada para RF-07.4 y CA-26, con los mismos campos que el criterio 1, que indique que los respaldos se hacen con dos Snapshot_Manual por disco (Requirement 23) en lugar de una política de Amazon Data Lifecycle Manager, y que no se realiza prueba de restauración.
5. THE Registro_Decisiones SHALL contener una entrada para RF-05.3, con los mismos campos que el criterio 1, que indique que el Grupo_Admins tiene como miembros a los integrantes del Equipo en lugar de exactamente dos usuarios.
6. THE Registro_Decisiones SHALL contener una entrada para CA-16, con los mismos campos que el criterio 1, que indique que se omite la prueba con un Usuario_IAM sin MFA y que CA-16 se verifica con el reporte de credenciales y la definición de la Politica_Force_MFA (Requirement 9).
7. THE Registro_Decisiones SHALL contener una entrada para el hallazgo del despliegue sobre las llamadas del Frontend a `/api/full-scan` y a los routers de detectores que dependen de TiendaDB (Requirement 26), con los mismos campos que el criterio 1, en la que el campo de requisito afectado indique «hallazgo del despliegue, sin RF ni CA en la fuente».
8. THE Registro_Decisiones SHALL contener una entrada para el uso de CloudFormation (Requirement 29), con los mismos campos que el criterio 1, con el cambio «CloudFormation en lugar de scripts de CLI para la infraestructura» y con la justificación «creación y borrado reproducibles en un solo stack; herramienta vista en el curso; estaba como 'Debería' en el documento de cambios».
9. THE Registro_Decisiones SHALL contener una entrada con los mismos campos que el criterio 1, con el requisito afectado «alcance del E2 en la práctica de definición de requisitos», el cambio «el E2 pasa de 'multi-cliente con registro de usuarios y de bases propias' a 'despliegue en AWS'; el registro de usuarios se entregó en el E1 y la conexión a bases propias del cliente pasa a Mejoras futuras» y la justificación «decisión del Equipo: E1 = desarrollo, E2 = despliegue».
10. THE Registro_Decisiones SHALL contener una entrada con los mismos campos que el criterio 1, con el requisito afectado «R21.2 / RF-07.2», el cambio «el aviso de anomalías pasa de ≤ 60 minutos a un resumen diario por correo» y la justificación «el correo directo de Cost Anomaly Detection solo admite frecuencia diaria o semanal; el aviso inmediato requiere SNS, y el Presupuesto (R20) ya alerta por correo».
11. WHEN se agrega una entrada al Registro_Decisiones, THE Equipo SHALL anotar en la especificación la aprobación de esa entrada, indicando nombre del aprobador y fecha (formato AAAA-MM-DD), en un plazo máximo de 2 días hábiles desde la fecha de la entrada.
12. IF una entrada del Registro_Decisiones carece de alguno de los campos del criterio 1 o no tiene aprobación anotada en la especificación, THEN THE Equipo SHALL considerar la decisión como no aprobada y SHALL completar el campo faltante o la aprobación antes de dar por cerrada la tarea T-26.

### Requirement 25: Paquete de evidencia

**User Story:** Como integrante del equipo, quiero reunir la evidencia de seguridad y aceptación, para sustentar la entrega.

**Trazabilidad:** RF-08.2 (Debe) · Tareas: T-23, T-24, T-25 · Criterios: CA-27 (también CA-01 a CA-08 del E1)

#### Acceptance Criteria

1. WHEN el sistema está desplegado y responde con HTTP exitoso en la URL pública, THE Equipo SHALL ejecutar ZAP baseline contra la URL pública y guardar el reporte completo en formato HTML, con fecha y hora de ejecución y URL analizada.
2. IF el reporte de ZAP baseline contiene uno o más hallazgos de riesgo medio o alto, THEN THE Equipo SHALL corregir cada hallazgo y volver a ejecutar ZAP baseline hasta que el reporte no contenga hallazgos de riesgo medio o alto, o documentar para cada hallazgo restante una justificación escrita que indique la causa y la razón de aceptación del riesgo.
3. WHEN el sistema está desplegado y la Elastic_IP está asignada, THE Equipo SHALL ejecutar `nmap` contra la Elastic_IP sobre los puertos TCP 1 a 65535 y guardar la salida completa en un archivo de texto con fecha y hora de ejecución.
4. IF la salida de `nmap` muestra algún puerto abierto distinto de 80 y 443, THEN THE Equipo SHALL cerrar el puerto o documentar una justificación escrita para cada puerto adicional abierto.
5. WHEN el sistema está desplegado, THE Equipo SHALL repetir CA-01 a CA-08 desde la URL pública y guardar, para cada criterio, evidencia que muestre el resultado (aprobado o fallido) junto con la URL pública utilizada. La evidencia puede ser una captura de pantalla o el fragmento de la grabación del video en que se ejecuta el criterio, identificado por su marca de tiempo, siempre que la URL pública se vea en pantalla; no se exigen capturas por separado.
6. THE Paquete_Evidencia SHALL incluir el reporte de ZAP sin hallazgos de riesgo medio o alto sin justificar, la salida de `nmap`, las justificaciones escritas de los puntos 2 y 4 si existen, y la evidencia del criterio 5 (capturas o marcas de tiempo de la grabación del video) con el resultado (aprobado o fallido) de los 8 criterios CA-01 a CA-08.

### Requirement 26: Llamadas del frontend a endpoints de TiendaDB

**User Story:** Como integrante del equipo, quiero que el Frontend de producción no llame a endpoints que dependen de TiendaDB, para que la aplicación no falle al iniciar sesión en AWS.

**Trazabilidad:** Hallazgo del despliegue, sin RF ni CA en la fuente · Tareas: nueva tarea de la Fase 1 (sin T-xx en la fuente) · Archivos: `frontend/src/App.jsx`, `frontend/src/components/AnalysisTabs.jsx`, `frontend/src/pages/Overview.jsx` y `frontend/src/api/pgguardian.js` · Registro: Requirement 24, criterio 7

Contexto verificado: `frontend/src/App.jsx` llama a `fullScan()` al iniciar sesión (líneas 114 y 131), y `frontend/src/api/pgguardian.js` define funciones para `/full-scan` y para los routers `/bloat`, `/config`, `/health`, `/indexes` y `/queries`. En el backend estos endpoints (`/api/full-scan`, `/api/bloat/*`, `/api/config/*`, `/api/health/*`, `/api/indexes/*` y `/api/queries/*`) usan `get_connection()`, que conecta a TiendaDB. El endpoint `/api/health-check` del Requirement 6 queda fuera de este requisito.

Contexto verificado de la pestaña local (con `VITE_ENABLE_TIENDADB_SCAN` no definida, es decir, en producción): `frontend/src/App.jsx` crea siempre la Pestaña_Local mediante `createLocalTab()` (id `LOCAL_TAB_ID = 'tiendadb-local'`, label «TiendaDB (Local)», `kind: 'local'`) y la deja en el estado `tabs`. `tabs[0]` es la pestaña de respaldo de `activeTab`, y `LOCAL_TAB_ID` es el valor inicial de `activeTabId` y se usa también en `closeTab`, `updateLocalTab` y `resetSessionState`. `frontend/src/components/AnalysisTabs.jsx` pinta todas las pestañas de `tabs`, por lo que en producción la Pestaña_Local aparece en la barra sin contenido. `frontend/src/pages/Overview.jsx` muestra en la píldora «TiendaDB (Local · init/)» cuando no hay un sandbox activo, usa «TiendaDB (Local)» como `tabTitle` por defecto y muestra el subtítulo «Resumen de salud de la base de datos local». Decisión: no borrar la Pestaña_Local del estado, porque `activeTab` podría quedar `undefined` y romper el Overview y las páginas por categoría; ocultarla solo en el render de `AnalysisTabs` y usar una etiqueta neutral en el Overview. El mensaje de «Nuevo análisis» del estado vacío ya existe y no se modifica.

#### Acceptance Criteria

1. WHEN el Equipo prepara el build de producción del Frontend, THE Equipo SHALL revisar `frontend/src/App.jsx` y `frontend/src/api/pgguardian.js` y registrar qué llamadas a `/api/full-scan`, `/api/bloat`, `/api/config`, `/api/health`, `/api/indexes` y `/api/queries` se ejecutan en producción.
2. IF el Frontend de producción llama a alguno de los endpoints del criterio 1, THEN THE Equipo SHALL quitar esas llamadas del Frontend de producción y registrar el cambio en el Registro_Decisiones como hallazgo del despliegue (Requirement 24, criterio 7).
3. WHEN un usuario inicia sesión en el Frontend de producción y recorre las pantallas de login, registro y análisis, THE Frontend SHALL enviar 0 solicitudes a los endpoints del criterio 1, verificable en la pestaña Red de las herramientas de desarrollo del navegador.
4. WHEN `TIENDADB_SCAN_ENABLED` es falso (build de producción), THE Frontend SHALL no mostrar la Pestaña_Local `TiendaDB (Local)` en la barra de pestañas (`AnalysisTabs`), y SHALL ocultar la barra por completo si no queda ninguna pestaña visible.
5. THE Frontend SHALL conservar la Pestaña_Local en el estado de `App.jsx` (`tabs`, `LOCAL_TAB_ID` como valor inicial de `activeTabId` y `tabs[0]` como pestaña de respaldo de `activeTab`) aunque no se muestre, de modo que `activeTab` nunca sea `undefined` y el Overview y las páginas por categoría no fallen.
6. WHEN `TIENDADB_SCAN_ENABLED` es falso y no hay un análisis sandbox activo, THE Frontend SHALL mostrar en el Overview la etiqueta «Sin análisis seleccionado» en lugar de «TiendaDB (Local · init/)», y SHALL NOT mostrar el texto «TiendaDB» ni «base de datos local» en el encabezado del Overview (incluido el subtítulo y el título por defecto).
7. WHEN `TIENDADB_SCAN_ENABLED` es verdadero (entorno de desarrollo), THE Frontend SHALL mantener la Pestaña_Local visible y las etiquetas actuales, sin cambio de comportamiento.

### Requirement 27: Secreto huérfano en Secrets Manager

**User Story:** Como responsable de costos, quiero eliminar el secreto huérfano de Secrets Manager, para no pagar por un recurso que no se usa.

**Trazabilidad:** Limpieza de la cuenta, sin RF ni CA en la fuente · Tareas: tarea manual (sin T-xx en la fuente)

#### Acceptance Criteria

1. WHEN el Equipo limpia la cuenta, THE Equipo SHALL listar los secretos de Secrets Manager en us-east-2 con `aws secretsmanager list-secrets --region us-east-2` e identificar el Secreto_Huerfano.
2. WHEN el Equipo identifica el Secreto_Huerfano, THE Equipo SHALL confirmar que ningún recurso de AWS ni la aplicación lo usa, revisando su fecha de último acceso y buscando su nombre o ARN en el código, en Compose_Prod y en el archivo `.env` de la Instancia.
3. WHEN el Equipo confirma que el Secreto_Huerfano no se usa, THE Equipo SHALL programar su borrado con `aws secretsmanager delete-secret` y una ventana de recuperación de 7 a 30 días, sin la opción `--force-delete-without-recovery`.
4. IF el Equipo no puede confirmar que el Secreto_Huerfano no se usa, THEN THE Equipo SHALL conservar el secreto sin programar su borrado y registrar el motivo.

### Requirement 28: Secciones del documento de requisitos original

**User Story:** Como líder del proyecto, quiero completar las secciones faltantes del documento fuente, para que el E2 tenga alcance, plan y proceso documentados.

**Trazabilidad:** Documentación del E2, sin RF ni CA en la fuente; el criterio 1 refleja el cambio de alcance registrado en Requirement 24, criterio 9 · Tareas: tarea de documentación (sin T-xx en la fuente)

#### Acceptance Criteria

1. THE Equipo SHALL redactar en `PgGuardian - Requisitos del Entregable 2 (AWS).md` una sección de alcance del E2 que indique que el E2 es el despliegue en AWS y no el alcance multi-cliente original (registro de usuarios, entregado en el E1, y conexión a bases propias del cliente, que pasa a Mejoras futuras), según el Requirement 24, criterio 9, y que la evaluación se hace con un video que muestra el funcionamiento de la aplicación desde la URL pública.
2. THE Equipo SHALL redactar en `PgGuardian - Requisitos del Entregable 2 (AWS).md` una sección de plan de trabajo.
3. THE Equipo SHALL redactar en `PgGuardian - Requisitos del Entregable 2 (AWS).md` una sección de proceso estándar.

### Requirement 29: Infraestructura como código con CloudFormation

**User Story:** Como integrante del equipo, quiero crear la infraestructura AWS con una plantilla de CloudFormation, para crearla y borrarla de forma reproducible en un solo stack.

**Trazabilidad:** Documento de cambios de la fuente (Debería) · Registro: Requirement 24, criterio 8 · Tareas: T-11 a T-15 y T-19 a T-21 (sus recursos pasan a la Plantilla_CFN), más las tareas de la plantilla, su despliegue y su borrado (sin T-xx en la fuente) · Criterios: los recursos se verifican con los criterios de R10, R12, R13, R14, R16, R17, R19.1, R20, R21 y R22

#### Acceptance Criteria

1. THE Plantilla_CFN SHALL crear en el Stack `pgguardian` el Rol_EC2 con su perfil de instancia, el Security_Group, la Instancia, el Volumen_Sandbox con un attachment en `/dev/sdf`, la Elastic_IP asociada a la Instancia, el Presupuesto, la Alarma_Recover y el monitor y la suscripción de Anomaly_Detection.
2. THE Plantilla_CFN SHALL recibir la AMI de Ubuntu 24.04 en el parámetro `AmiId` (tipo `AWS::EC2::Image::Id`, sin valor por defecto) y SHALL NOT resolverla dentro de la plantilla. Antes del primer despliegue, THE Equipo SHALL obtener el ID con `aws ssm get-parameter --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id --query Parameter.Value --output text` y pasarlo como `AmiId`; en cada actualización SHALL pasar `AmiId` con `UsePreviousValue=true`. THE Plantilla_CFN SHALL crear el Volumen_Sandbox en la misma zona de disponibilidad que la Instancia y SHALL NOT definir `UserData` en la Instancia, de modo que la configuración del host quede en `scripts/aws/bootstrap_host.sh`.
3. THE Plantilla_CFN SHALL declarar los parámetros `VpcId`, `SubnetId`, `AmiId` (sin valor por defecto), `Owner` (cadena de 1 a 256 caracteres), `AlertEmail` y `MonthlyBudgetUsd` (valor por defecto 30), y los outputs `InstanceId`, `PublicIp`, `AppDomain` (la dirección de la Elastic_IP con los octetos separados por guiones, seguida de `.sslip.io`) y `SandboxVolumeId`.
4. THE Plantilla_CFN SHALL asignar las etiquetas `Project=PgGuardian`, `Env=prod` y `Owner` a la Instancia, al disco raíz (mediante `PropagateTagsToVolumeOnCreation: true`), al Volumen_Sandbox y a la Elastic_IP.
5. THE Plantilla_CFN SHALL NOT crear los Usuario_IAM, el Grupo_Admins, la Politica_Force_MFA ni los Snapshot_Manual. Esos elementos, la configuración del host, el `.env`, el despliegue de la aplicación, el Secreto_Huerfano, ZAP y `nmap` siguen fuera de la plantilla.
6. WHEN el Equipo crea o modifica la Plantilla_CFN, THE Plantilla_CFN SHALL pasar `cfn-lint` sin errores y `aws cloudformation validate-template` sin errores antes de desplegarse.
7. WHEN el Equipo crea o actualiza el Stack, THE Equipo SHALL hacerlo con un change set (`aws cloudformation create-change-set`), revisar con `aws cloudformation describe-change-set` los recursos que se agregan, modifican o reemplazan, y ejecutarlo con `aws cloudformation execute-change-set` solo después de esa revisión.
8. WHEN el Stack queda en estado `CREATE_COMPLETE`, THE Stack SHALL tener activada la protección contra terminación (`EnableTerminationProtection=true`), verificable con `aws cloudformation describe-stacks --stack-name pgguardian`.
9. THE Equipo SHALL documentar en `docs/aws/runbook.md` el borrado del Stack en este orden: desactivar la protección contra terminación del Stack, desactivar `DisableApiTermination` de la Instancia, tomar un Snapshot_Manual del disco raíz y uno del Volumen_Sandbox hasta que estén en estado `completed`, y ejecutar `aws cloudformation delete-stack --stack-name pgguardian`.
10. IF el despliegue del Stack falla en el monitor o en la suscripción de Anomaly_Detection, THEN THE Equipo SHALL quitar esos dos recursos de la Plantilla_CFN, volver a desplegar el Stack y crearlos con `scripts/aws/create_anomaly_detection.sh`, de modo que el Requirement 21 se siga cumpliendo.

## Matriz de trazabilidad RF → T → CA

| RF | Prioridad | Requirement | Tareas | Criterios |
| --- | --- | --- | --- | --- |
| RF-04.1 | Debe | 1 | T-01, T-17 | CA-09 |
| RF-04.2 | Debe | 2 | T-02 | CA-10 |
| RF-04.3 | Debe | 3 | T-03 | CA-11 |
| RF-04.4 | Debe | 4 | T-04, T-14 | CA-12 |
| RF-04.5 | Debe | 5 | T-05, T-06 | CA-13 |
| RF-04.6 | Debe | 6 | T-07 | CA-14 |
| (Fase 1, RNF-05) | Debe | 7 | T-08 | CA-09 a CA-14 en local |
| RF-05.1 | Debe | 8 | T-09 | CA-15 |
| RF-05.2 | Debe | 9 | T-10 | CA-15, CA-16 |
| RF-05.3 | Debe | 9 (desviación: 24) | T-10 | CA-16 (desviación: 24) |
| RF-05.4 | Debe | 10 | T-11, T-13 | CA-17 |
| RF-05.5 | Debe | 11 | T-16 | CA-17, CA-18 |
| RF-06.1 | Debe | 12 | T-12 | CA-18 |
| RF-06.2 | Debe | 13 | T-13 | CA-19 |
| RF-06.3 | Debe | 4, 14 | T-13, T-14 | CA-20 |
| RF-06.4 | Debe | 15 | T-16 | CA-20 |
| RF-06.5 | Debe | 16 | T-13 | CA-20 |
| RF-06.6 | Debería | 17 | T-13 | CA-21 |
| RF-06.7 | Debería | 18 | T-16 | CA-22 |
| RF-06.8 | Podría | 19 | T-18 | CA-23 |
| RF-03.1, RF-03.4, RF-03.5 (E1) | Debe | 19 | T-15, T-17, T-18 | CA-23 |
| RF-03.6 (E1, sustituido) | n/a | 24 (criterio 3), 19 (criterio 8), 20 | T-26, T-19, sección «Encender y detener» del runbook (sin T-xx) | CA-23, CA-24, CA-27 |
| RF-07.1 | Debe | 20 | T-19 | CA-24 |
| RF-07.2 | Debería | 21 (desviación de 21.2: 24) | T-20 | CA-24 |
| RF-07.3 | Debería | 22 | T-21 | CA-25 |
| RF-07.4 | Debe | 23 (desviación: 24) | T-22, T-27 | CA-26 |
| RF-08.1 | Debe | 24 | T-26 | CA-27 |
| RF-08.2 | Debe | 25 | T-23, T-24, T-25 | CA-27 |
| Hallazgo del despliegue | n/a | 26 (registro: 24) | Fase 1 (sin T-xx) | n/a |
| Limpieza de la cuenta | n/a | 27 | Manual (sin T-xx) | n/a |
| Documentación del E2 | n/a | 28 | Documentación (sin T-xx) | n/a |
| Alcance del E2 (práctica de definición de requisitos) | n/a | 24 (criterio 9), 28 (criterio 1), Mejoras futuras | T-26, documentación (sin T-xx) | n/a |
| Infraestructura como código (documento de cambios) | Debería | 29 (registro: 24) | T-11 a T-15, T-19 a T-21 (recursos de la plantilla); plantilla, despliegue y borrado (sin T-xx) | Los de R10, R12 a R14, R16, R17, R19.1 y R20 a R22 |
| Sección 6 (pendientes) | n/a | Mejoras futuras | n/a | n/a |

Cobertura: las 27 tareas (T-01 a T-27) y los 19 criterios (CA-09 a CA-27) aparecen al menos una vez en la matriz.

## Mejoras futuras

Elementos de la fuente que se retiraron de esta versión. Cada uno podría retomarse si el Equipo dispone de tiempo o si cambian las condiciones del proyecto.

- **Conexión a bases propias del cliente:** registrar una base PostgreSQL del cliente con una credencial de solo lectura y auditarla de forma continua, en lugar de analizar scripts en el sandbox. Era el alcance original del E2 (R24.9).
- **Grupo de operadores (sección 6 de la fuente):** grupo IAM con permisos limitados a reiniciar la Instancia e iniciar sesiones de Session Manager sobre recursos con `Project=PgGuardian`, con verificación de que otras acciones se deniegan y quedan en CloudTrail. Podría retomarse si se suman integrantes que no deban ser administradores.
- **`pg_dump` periódico de App_DB (sección 6 de la fuente):** copia lógica cada 24 horas con retención de 7 días y aviso de fallo en 15 minutos. Podría retomarse para tener respaldos de App_DB independientes del disco raíz, ya que `app_db` guarda sus datos en el volumen `pgguardian_app_data` dentro del disco raíz y no tiene volumen propio.
- **Prueba de restauración del snapshot del Volumen_Sandbox (antes R23.4):** restaurar el snapshot de 8 GB en un volumen nuevo, levantar un PostgreSQL temporal y comparar el conteo de filas de una tabla marcador. Podría retomarse para demostrar que los snapshots son restaurables, no solo que están en `completed`.
- **Restauración de `pg_dump` de App_DB (antes R23.6):** restaurar un `pg_dump` en una base temporal y comparar conteos de filas. Depende del `pg_dump` periódico y se retomaría junto con él.
- **Unidad systemd de respaldo (antes R4.9):** unidad con `ConditionPathIsMountPoint=/srv/sandbox` que impide ejecutar `docker compose up` sin el Volumen_Sandbox montado. Es redundante con `create_host_path: false`, pero podría retomarse como segunda barrera.
- **Prueba de usuario sin MFA con `PgG-MFA-Test` (antes R9.6 a R9.8):** Usuario_IAM temporal sin MFA en un grupo temporal con `ec2:DescribeInstances` para comprobar el `AccessDenied`, y su borrado posterior. Podría retomarse para verificar CA-16 con una prueba de comportamiento en lugar de revisar la política.
- **Política DLM con snapshots diarios y verificación de costo (antes R23):** Amazon Data Lifecycle Manager con un snapshot diario de ambos discos, retención de 7 y selección por etiqueta, junto con la verificación en Cost Explorer de si los 22 USD al mes estimados incluyen el costo de esos snapshots. Podría retomarse si se necesita un punto de recuperación diario.
