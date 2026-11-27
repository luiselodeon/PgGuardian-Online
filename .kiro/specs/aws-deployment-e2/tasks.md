# Implementation Plan: Despliegue de PgGuardian en AWS (Entregable 2)

## Overview

Este plan convierte el diseño (componentes C1 a C15) en tareas de código, scripts y documentos versionados. Conserva la numeración T-01 a T-27 de la fuente y la cadena de trazabilidad RF → T → CA. Cada sub-tarea indica su T-xx, y cada línea `_Requirements_` cita los Requirement (R1 a R29) de `requirements.md`, junto con los RF y CA que cubre. Las tareas sin T-xx en la fuente (R26 a R29) se indican como tales.

La infraestructura AWS se define en la plantilla de CloudFormation `infra/cloudformation/pgguardian.yaml` (C15), desplegada desde CloudShell como el stack `pgguardian`. Los usuarios IAM se crean en la consola siguiendo la sección raíz/IAM del runbook (tarea 4.2). El resto de lo que la plantilla no cubre (host, `.env`, despliegue de la aplicación y snapshots) sigue en los scripts de `scripts/aws/` (lista de C14). Las verificaciones no son scripts: son comandos dentro de un único documento, `docs/aws/runbook.md`, con las secciones raíz/IAM, stack, instancia, host, despliegue, encender y detener, costos y snapshots. La tarea 4.1 crea ese documento con sus ocho secciones y las demás tareas lo amplían en olas distintas. El despliegue y el borrado del stack, la ejecución de los scripts en la cuenta AWS y la captura de evidencia manual (capturas, video, MFA físico) los hace el Equipo con esos artefactos.

Lenguajes: Python (FastAPI, unittest), JavaScript (React/Vite), YAML (Compose y CloudFormation), Caddyfile, Bash y PowerShell, JSON (políticas IAM, CLI de AWS), Markdown.

## Tasks

- [x] 1. Fase 1: cambios de código y configuración (T-01 a T-07 y frontend)
  - [x] 1.1 T-01: Hacer obligatorio `JWT_SECRET` en `docker-compose.prod.yml`
    - Cambiar `JWT_SECRET: ${JWT_SECRET}` del servicio `api` por `${JWT_SECRET:?falta JWT_SECRET}`.
    - _RF-04.1 · CA-09 · Requirements: 1.1, 1.2, 1.3_

  - [x] 1.2 T-02: Rotación de logs con `x-logging`
    - Definir el ancla `x-logging: &logging` (`json-file`, `max-size: "10m"`, `max-file: "3"`) y referenciarla con `logging: *logging` en los cinco servicios, sin bloques propios.
    - _RF-04.2 · CA-10 · Requirements: 2.1, 2.2, 2.4_

  - [x] 1.3 T-03: Límites de memoria
    - Añadir `mem_limit` de `512m` a `sandbox_db`, `384m` a `app_db` y `512m` a `api` (suma 1408 MiB).
    - _RF-04.3 · CA-11 · Requirements: 3.1, 3.2, 3.3, 3.6_

  - [x] 1.4 T-04: Bind mount del disco propio del sandbox
    - Reemplazar el volumen `sandbox_data` de `sandbox_db` por un bind mount en sintaxis larga: `type: bind`, `source: ${SANDBOX_DATA_DIR:-./.data/sandbox}`, `target: /var/lib/postgresql/data` y `bind: { create_host_path: false }`. Eliminar `sandbox_data` de `volumes:`. No usar la sintaxis corta ni la ruta fija `/srv/sandbox/pgdata` en el compose: esa ruta solo existe en la EC2, y en Windows con Docker Desktop terminaría dentro de la VM de Docker (T-08 corre en local).
    - Motivo de `create_host_path: false`: con la sintaxis corta, si el disco no se montó, Docker crea `/srv/sandbox/pgdata` en el disco raíz y PostgreSQL escribe allí sin aviso. Los contenedores con `restart: unless-stopped` se levantan solos sin pasar por systemd, así que esta opción es la protección real. Con ella, Docker se niega a iniciar `sandbox_db` si el directorio de origen no existe, y no lo crea.
    - Consecuencia local: Docker ya no crea `./.data/sandbox`; lo crea el script de T-08 (tarea 2.1).
    - No fijar `PGDATA`: el bind mount apunta al subdirectorio `pgdata`, por lo que `lost+found` queda en `/srv/sandbox`.
    - Agregar `.data/` al `.gitignore`.
    - Añadir `SANDBOX_DATA_DIR=/srv/sandbox/pgdata` a `.env.prod.example`, con un comentario que indique que es obligatoria en producción (sin ella los datos quedan en el disco raíz) y que en local se omite.
    - _RF-04.4 · CA-12 · Requirements: 4.1, 4.2, 4.3, 4.4, 4.8_

  - [x] 1.5 T-05: Cabeceras de seguridad en `Caddyfile`
    - Añadir en el bloque `header` HSTS, `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, la CSP inicial exacta y `-Server`.
    - Evitar duplicados con el operador de reemplazo (`>`) si el upstream repite una cabecera.
    - _RF-04.5 · CA-13 · Requirements: 5.1, 5.2, 5.3, 5.6_

  - [x] 1.6 T-06: Ajustar la CSP según el build de producción del frontend
    - Crear `docs/aws/csp-verificacion.md` con el procedimiento (login, registro, análisis, consola con 0 violaciones) y la tabla donde registrar cada directiva ampliada.
    - Ampliar la CSP del `Caddyfile` solo con las directivas de la fuente bloqueada, si se observan violaciones.
    - _RF-04.5 · CA-13 · Requirements: 5.4, 5.5_

  - [x] 1.7 T-07: Sanear el endpoint existente `/api/health-check` (sin filtración de información)
    - El endpoint `GET /api/health-check` ya existe en `backend/api/main.py` (función `health_check`, sin autenticación). Modificar ese manejador; no añadir uno nuevo.
    - En `backend/services/analysis_store.py`, cambiar la firma a `connect_app_db(connect_timeout: int = 10)` y pasar `connect_timeout` a `psycopg2.connect`. El valor por defecto preserva el comportamiento actual de los demás llamadores.
    - En `health_check`, conservar la bifurcación por `DB_HOST`. Producción (`DB_HOST` no definida): llamar a `connect_app_db(connect_timeout=2)` (ya importada en `main.py`). Local (`DB_HOST` definida): usar `get_connection()` de `backend/api/database.py`. No usar `get_connection()` en la ruta de producción, porque apunta a TiendaDB, que no existe en producción.
    - Ejecutar `SELECT 1` y cerrar la conexión en `finally` (cerrar el generador si se usó `get_connection()`).
    - Responder solo `{"status":"ok"}`, o `{"status":"error"}` con HTTP 503 ante cualquier excepción. Registrar marca de tiempo, tipo y mensaje de la excepción en el log del servidor, sin exponerlos en la respuesta.
    - Comprobar que `/api/health-check` no colisiona con el prefijo `/api/health` del router de salud (rutas distintas; basta una comprobación).
    - Actualizar el test existente `backend/tests/test_rnf.py::test_rf03_health_check_uses_app_db_without_db_host_and_tiendadb_when_set`: ya no puede afirmar `res["target"]`. Verificar la rama invocada con los mocks `mock_app_db` y `mock_tienda`, y comparar la respuesta con `{"status": "ok"}`. Esta actualización es obligatoria para que la suite no se rompa.
    - _RF-04.6 · CA-14 · Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 1.8 Escribir pruebas unitarias del health-check
    - En `backend/tests/test_health_check.py`, como métodos de una clase `unittest.TestCase` (con `unittest.mock` para las conexiones): `test_health_check_ok`, `test_health_check_db_down`, `test_health_check_timeout`, `test_health_check_unexpected`, `test_health_check_no_auth`. El repo usa `unittest` y `pytest` no está en `backend/requirements.txt`; se ejecutan con `python -m unittest` desde `backend/`.
    - `test_health_check_timeout` debe verificar que se invoca `connect_app_db(connect_timeout=2)` y que, ante un error de conexión por espera agotada, responde `{"status":"error"}` con HTTP 503.
    - Las pruebas de error deben comprobar que el cuerpo contiene solo la clave `status` y que el tipo y mensaje de la excepción se registran en el log.
    - _RF-04.6 · CA-14 · Requirements: 6.1, 6.2, 6.3, 6.4, 6.5_

  - [ ]* 1.9 Escribir pruebas de configuración de `docker-compose.prod.yml`
    - En `backend/tests/test_compose_prod.py`, como clase `unittest.TestCase` ejecutable con `python -m unittest` desde `backend/`. Decorar la clase con `@unittest.skipUnless(shutil.which("docker"), "docker no está instalado")` para que se omita en máquinas sin Docker.
    - Casos: `docker compose config` falla sin `JWT_SECRET`; los cinco servicios resuelven `json-file`, `10m`, `3`; `mem_limit` por servicio; `docker compose -f docker-compose.prod.yml config` muestra `create_host_path: false` en el bind mount de `sandbox_db` (tipo `bind`, destino `/var/lib/postgresql/data`, origen resuelto desde `SANDBOX_DATA_DIR` o `./.data/sandbox`) y no existe `sandbox_data`.
    - _RF-04.1 a RF-04.4 · CA-09 a CA-12 · Requirements: 1.2, 2.5, 3.1, 3.2, 3.3, 4.1, 4.8_

  - [x] 1.10 Frontend sin llamadas a endpoints de TiendaDB (sin T-xx; hallazgo del despliegue)
    - Revisar `frontend/src/App.jsx` y `frontend/src/api/pgguardian.js`: buscar en `frontend/src` qué funciones de `/api/full-scan`, `/api/bloat`, `/api/config`, `/api/health`, `/api/indexes` y `/api/queries` se invocan. Hecho conocido: `App.jsx` llama a `fullScan()` en el efecto inicial (línea 131) y en `runScan` (línea 114).
    - Si se ejecutan en producción, condicionarlas a la variable de build de Vite `VITE_ENABLE_TIENDADB_SCAN` (solo con `"true"` se ejecutan `fullScan()` y los detectores). El build de producción no la define. Aplicarlo al efecto inicial, a `runScan` y a cualquier otra llamada encontrada, y ocultar los controles de escaneo de la pestaña local cuando la variable no esté activa.
    - No borrar las funciones de `pgguardian.js` (el entorno de desarrollo con TiendaDB las usa). `/api/health-check` (`healthCheck`) queda fuera de esta tarea.
    - Crear `docs/aws/decision-log.md` con la entrada R24.7: `requisito_afectado` «hallazgo del despliegue, sin RF ni CA en la fuente», el resultado de la revisión (llamadas encontradas) y el cambio aplicado. T-26 (tarea 9.4) completa el resto del registro.
    - _Hallazgo del despliegue · Requirements: 26.1, 26.2, 26.3, 24.7_

  - [x] 1.11 Ocultar la pestaña local y la etiqueta TiendaDB en producción (sin T-xx; hallazgo del despliegue)
    - En `frontend/src/components/AnalysisTabs.jsx`: importar `TIENDADB_SCAN_ENABLED` de `frontend/src/config/features.js` y filtrar en el render (no en el estado) las pestañas con `kind === 'local'` cuando la bandera sea falsa (`visibleTabs`). Si no queda ninguna pestaña visible, devolver `null` para ocultar la barra completa. Usar `visibleTabs.map(...)` en lugar de `tabs.map(...)`.
    - En `frontend/src/pages/Overview.jsx`: cuando no hay sandbox activo y `TIENDADB_SCAN_ENABLED` es falso, mostrar la píldora «Sin análisis seleccionado» y un subtítulo neutral («Selecciona o crea un análisis para ver el resumen»). El `tabTitle` por defecto no debe contener «TiendaDB» (p. ej. `activeTab?.label || 'Análisis'`). Con la bandera verdadera, conservar «TiendaDB (Local · init/)», «Resumen de salud de la base de datos local» y el resto de etiquetas actuales, sin cambios.
    - NO tocar `frontend/src/App.jsx` ni quitar la pestaña local del estado: `tabs[0]` es la pestaña de respaldo de `activeTab` y `LOCAL_TAB_ID` es el valor inicial de `activeTabId`. Quitarla dejaría `activeTab` como `undefined` y rompería el Overview y las páginas por categoría (también `closeTab`, `updateLocalTab`, `resetSessionState` y el efecto de restauración del último análisis).
    - Verificar en un build de producción (sin `VITE_ENABLE_TIENDADB_SCAN`): 0 pestañas «TiendaDB (Local)», barra oculta sin análisis, solo la pestaña del sandbox al crear uno, Overview sin el texto «TiendaDB» ni «base de datos local» y sin errores en consola por `activeTab` indefinido. En desarrollo (`VITE_ENABLE_TIENDADB_SCAN=true`) todo queda igual que antes.
    - Añadir el resultado de la verificación como nota a la entrada R24.7 de `docs/aws/decision-log.md` (creada en la tarea 1.10).
    - _Hallazgo del despliegue · Requirements: 26.4, 26.5, 26.6, 26.7, 24.7_

- [x] 2. Verificación local previa al despliegue (T-08)
  - [x] 2.1 T-08: Script de verificación local de la Fase 1
    - Crear `scripts/verify_phase1.sh` y `scripts/verify_phase1.ps1`.
    - Paso 0: si no existe el `.env` local o `JWT_SECRET` falta o está vacío, detenerse antes de levantar contenedores, indicar qué falta y cómo corregirlo (p. ej. copiar `.env.prod.example` a `.env` y definir `JWT_SECRET`) y salir con código distinto de 0.
    - Antes de `up`, crear `./.data/sandbox` (o la ruta de `SANDBOX_DATA_DIR` si el `.env` la define) si no existe, porque con `create_host_path: false` Docker ya no la crea. Si no se puede crear, detenerse antes de levantar contenedores, mostrar la ruta y la causa, y salir con código distinto de 0.
    - Ejecutar `docker compose -f docker-compose.prod.yml up -d --build` (no `docker compose up -d`, que solo levanta el compose de desarrollo con TiendaDB) y esperar hasta 120 s a que los cinco servicios del compose de producción estén `running`/`healthy`.
    - Verificar que `sandbox_db` llega a `healthy` con el bind mount local `./.data/sandbox` (riesgo de permisos en Docker Desktop/NTFS). Si no, el script falla y no se abre el PR.
    - Llamar al health-check (timeout 5 s) y evaluar CA-09 a CA-14.
    - CA-09: ejecutar `docker compose -f docker-compose.prod.yml config` con `JWT_SECRET` vacío solo en el entorno del proceso, sin modificar el `.env`; aprueba solo si el código de salida es distinto de 0 y aparece «falta JWT_SECRET».
    - Imprimir una línea JSON por criterio (`criterio`, `requisito`, `estado`, `detalle`) y salir con código distinto de 0 si algo falla.
    - Añadir una plantilla de descripción de PR con el resultado de cada criterio.
    - _RNF-05 · CA-09 a CA-14 · Requirements: 7.1, 7.2, 7.3, 7.4, 7.5, 7.6, 7.7, 7.8_

- [x] 3. Checkpoint: Fase 1
  - Ensure all tests pass, ask the user if questions arise.

- [x] 4. Fase 2: cuenta e IAM (T-09, T-10, T-11)
  - [x] 4.1 T-09: Runbook y verificación de la cuenta raíz
    - Crear `docs/aws/runbook.md` con las ocho secciones (raíz/IAM, stack, instancia, host, despliegue, encender y detener, costos, snapshots) y el formato común de «Resultado de verificación» (`criterio`, `requisito`, `estado` `aprobado|no_aprobado|no_verificable`, `detalle`).
    - En la sección raíz/IAM: los pasos manuales de MFA de la cuenta raíz y de acceso IAM a facturación, y los comandos de verificación con `aws iam get-account-summary`. Aprobado solo con `AccountMFAEnabled=1` y `AccountAccessKeysPresent=0`; no conforme indicando la condición fallida; no verificable con la causa si la consulta falla o falta un valor. La verificación no modifica la cuenta.
    - _RF-05.1 · CA-15 · Requirements: 8.1, 8.2, 8.3, 8.4, 8.5, 8.6_

  - [x] 4.2 T-10: Usuarios IAM, grupo `PgG-Admins` y política `Force_MFA`
    - Crear `docs/aws/iam/force-mfa-policy.json`:
      - Una sentencia `Deny` con `NotAction` y `BoolIfExists aws:MultiFactorAuthPresent=false`.
      - El `NotAction` excluye lo que el usuario necesita antes de tener MFA: `iam:CreateVirtualMFADevice`, `iam:EnableMFADevice`, `iam:ListMFADevices`, `iam:GetMFADevice`, `iam:ListVirtualMFADevices`, `iam:ResyncMFADevice`, `iam:GetUser`, `iam:ChangePassword`, `iam:GetAccountPasswordPolicy` y `sts:GetSessionToken` (10 acciones). `iam:GetMFADevice` va también en el `Action` del `Allow`.
      - Una sentencia `Allow` de autogestión limitada a `${aws:username}`.
    - Sin script: añadir a la sección raíz/IAM de `docs/aws/runbook.md` los pasos de consola, ejecutados como raíz una sola vez:
      1. Crear la política administrada `Force_MFA` pegando el JSON.
      2. Crear el grupo `PgG-Admins` con `AdministratorAccess` y `Force_MFA`.
      3. Crear un usuario por integrante del Equipo, con acceso a la consola, contraseña autogenerada por AWS, cambio obligatorio en el primer inicio de sesión, miembro de `PgG-Admins` y sin access keys.
      4. Cada integrante inicia sesión, cambia su contraseña y registra su MFA.
      5. A partir de aquí, la raíz no se usa para operar.
    - Añadir a la misma sección los comandos de verificación, ejecutados en CloudShell con un usuario IAM:
      - El reporte de credenciales (`generate-credential-report`): 100 % de usuarios con `mfa_active=true` y claves en `false`.
      - La revisión de la definición de `Force_MFA` adjunta a `PgG-Admins` (`list-attached-group-policies` + `get-policy-version`).
      - Una acción permitida con MFA, sin `AccessDenied`.
      - CA-16 se verifica así, sin usuario de prueba sin MFA.
    - _RF-05.2, RF-05.3 · CA-15, CA-16 · Requirements: 9.1, 9.2, 9.3, 9.4, 9.5, 9.6_

  - [x] 4.3 T-11: Verificación del rol `PgGuardian-EC2-Role`
    - El rol y su perfil de instancia los crea la plantilla (tarea 5.1); esta tarea no crea scripts.
    - Añadir a la sección instancia de `docs/aws/runbook.md` el comando `aws iam list-attached-role-policies --role-name PgGuardian-EC2-Role` (debe listar `AmazonSSMManagedInstanceCore`) y la comprobación de que la instancia usa ese perfil (`aws ec2 describe-instances`, campo `IamInstanceProfile`), con el resultado esperado.
    - _RF-05.4 · CA-17 · Requirements: 10.1, 10.2_

- [x] 5. Fase 3: stack de CloudFormation `pgguardian` (recursos de T-11 a T-15 y T-19 a T-21)
  - [x] 5.1 Escribir `infra/cloudformation/pgguardian.yaml` y validarlo con `cfn-lint`
    - Recursos según C15, en un solo stack:
      - T-11: rol `PgGuardian-EC2-Role` con `AmazonSSMManagedInstanceCore` y su perfil de instancia.
      - T-12: Security Group en `VpcId` con exactamente 2 reglas de entrada, TCP 80 y 443 desde `0.0.0.0/0`.
      - T-13: instancia con `ImageId: !Ref AmiId`, `t3.small`, `SubnetId`, sin `KeyName`, `HttpTokens: required`, `HttpEndpoint: enabled`, `HttpPutResponseHopLimit: 1`, raíz gp3 de 20 GB cifrada, `DisableApiTermination: true`, `PropagateTagsToVolumeOnCreation: true` y sin `UserData`.
      - T-14: `AWS::EC2::Volume` gp3 de 8 GB cifrado en `!GetAtt Instance.AvailabilityZone` y `AWS::EC2::VolumeAttachment` en `/dev/sdf`.
      - T-15: Elastic IP asociada a la instancia.
      - T-19: presupuesto de `MonthlyBudgetUsd` USD mensuales con `CostTypes` `IncludeCredit: false` e `IncludeRefund: false` y 4 notificaciones a `AlertEmail` (real 50, 80 y 100 %; pronóstico 100 %).
      - T-21: alarma `StatusCheckFailed_System` con los parámetros de R22 y la acción `arn:aws:automate:${AWS::Region}:ec2:recover`.
      - T-20: `AWS::CE::AnomalyMonitor` (`DIMENSIONAL`, `SERVICE`) y `AWS::CE::AnomalySubscription` con `Frequency: DAILY`, suscriptor `EMAIL` a `AlertEmail` y umbral en `ThresholdExpression` (`ANOMALY_TOTAL_IMPACT_ABSOLUTE` ≥ 1 USD), no en `Threshold`.
    - Etiquetas `Project=PgGuardian`, `Env=prod` y `Owner` en la instancia, el Volumen_Sandbox y la Elastic IP; el disco raíz las hereda.
    - Parámetros `VpcId`, `SubnetId`, `AmiId` (`AWS::EC2::Image::Id`, sin `Default`), `Owner` (`MinLength: 1`, `MaxLength: 256`), `AlertEmail` y `MonthlyBudgetUsd` (`Default: 30`). Outputs `InstanceId`, `PublicIp`, `AppDomain` (IP con guiones + `.sslip.io`) y `SandboxVolumeId`.
    - Fuera de la plantilla: usuarios IAM, `PgG-Admins`, `Force_MFA`, configuración del host, `.env`, despliegue de la aplicación, snapshots, secreto huérfano, ZAP y `nmap`.
    - Validar con `cfn-lint infra/cloudformation/pgguardian.yaml` y `aws cloudformation validate-template --template-body file://infra/cloudformation/pgguardian.yaml`, ambos sin errores.
    - _RF-05.4, RF-06.1, RF-06.2, RF-06.3, RF-06.5, RF-06.6, RF-06.8, RF-07.1, RF-07.2, RF-07.3 · CA-17 a CA-21, CA-23 a CA-25 · Requirements: 4.5, 10.1, 10.2, 11.1, 11.2, 12.1, 12.2, 13.1, 14.1, 14.2, 16.1, 17.1, 17.2, 17.3, 19.1, 20.1, 20.2, 20.3, 20.4, 21.1, 21.2, 22.1, 22.2, 22.3, 29.1, 29.2, 29.3, 29.4, 29.5, 29.6_

  - [x] 5.2 Runbook: despliegue del stack con change set y lectura de outputs
    - Añadir a la sección stack de `docs/aws/runbook.md` el procedimiento de C15: `cfn-lint` y `validate-template`; solo antes del primer despliegue, `aws ssm get-parameter --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id --query Parameter.Value --output text` para obtener el ID de la AMI; `aws cloudformation create-change-set --stack-name pgguardian --change-set-type CREATE --capabilities CAPABILITY_NAMED_IAM` con los cinco parámetros obligatorios, ese ID como `AmiId`; `wait change-set-create-complete`; revisión con `describe-change-set` (acción, recurso lógico, tipo y `Replacement`); `execute-change-set` solo después de la revisión; `wait stack-create-complete`; `update-termination-protection --enable-termination-protection`; y `describe-stacks` con `EnableTerminationProtection=true`.
    - Comprobación previa al primer despliegue, antes de `create-change-set` (AWS permite un solo monitor de anomalías de servicios por cuenta): `aws ce get-anomaly-monitors --query "AnomalyMonitors[?MonitorType=='DIMENSIONAL']"`. Si existe uno (en esta cuenta, `Default-Services-Monitor`, con `Default-Services-Subscription` de umbral 100 USD y 40 %), guardar primero como evidencia en `docs/aws/evidencia/` la salida de ese comando y la de `aws ce get-anomaly-subscriptions --monitor-arn <arn>`; después borrar sus suscripciones con `aws ce delete-anomaly-subscription --subscription-arn <arn>` y, al final, el monitor con `aws ce delete-anomaly-monitor --monitor-arn <arn>`. Repetir la primera consulta y confirmar que devuelve una lista vacía. Decisión registrada en `docs/aws/decision-log.md` («Monitor de anomalías por defecto reemplazado por el del stack»).
    - Actualizaciones: mismo procedimiento con `--change-set-type UPDATE` y `ParameterKey=AmiId,UsePreviousValue=true` (y `UsePreviousValue=true` en los demás parámetros que no cambian); como segunda barrera, no ejecutar el change set si `Instance` aparece con `Replacement=True`.
    - Lectura de outputs: `aws cloudformation describe-stacks --stack-name pgguardian --query "Stacks[0].Outputs"`, con `InstanceId`, `PublicIp`, `AppDomain` y `SandboxVolumeId`, que usan las tareas 5.3, 6.1, 6.2, 6.4 y 7.4.
    - Plan B de Cost Anomaly Detection: si el despliegue falla en `CostAnomalyMonitor` o `CostAnomalySubscription`, quitar ambos recursos de la plantilla, volver a desplegar el stack y crearlos con `scripts/aws/create_anomaly_detection.sh` (tarea 7.2). Si el rollback queda en `ROLLBACK_FAILED` porque `DisableApiTermination` impide terminar la instancia, obtener su ID con `describe-stack-resources`, ejecutar `aws ec2 modify-instance-attribute --no-disable-api-termination` y borrar el stack antes de repetir.
    - _Requirements: 21.1, 29.2, 29.3, 29.6, 29.7, 29.8, 29.10_

  - [x] 5.3 Runbook: verificaciones de instancia, volúmenes, Security Group, IMDS, etiquetas y Elastic IP
    - Añadir a la sección instancia de `docs/aws/runbook.md`, con los outputs `InstanceId`, `PublicIp` y `SandboxVolumeId`, las verificaciones que antes estaban en las tareas de T-12 a T-15:
      - Security Group: `describe-security-groups` (2 reglas, 0 para el puerto 22 e `::/0`) y `nmap -Pn -p- <PublicIp>` (solo 80/443 abiertos).
      - Instancia: metadatos (`HttpTokens=required`, `HttpEndpoint=enabled`, `HttpPutResponseHopLimit=1`), cifrado, protección contra terminación (`terminate-instances` rechazado) y SSM `Online` en 300 s (`ssm describe-instance-information`).
      - IMDS desde la instancia: pruebas 401/200/401. Desde un contenedor: `docker run --rm <imagen con curl> curl -m 5 -X PUT http://169.254.169.254/latest/api/token -H "X-aws-ec2-metadata-token-ttl-seconds: 60"` debe fallar o agotar el tiempo, y el agente SSM del host sigue `Online`.
      - Volúmenes: `describe-volumes` (gp3, 20 y 8 GB, cifrados), `df -h /srv/sandbox` frente a `df -h /` y la recomprobación de cifrado y montaje tras `sudo reboot`.
      - Etiquetas: `describe-tags` sobre la instancia, el disco raíz, el Volumen_Sandbox y la Elastic IP, con `Owner` de 1 a 256 caracteres.
      - Elastic IP: la IP pública de la instancia coincide con `PublicIp` antes y después de detener e iniciar la instancia.
    - _RF-04.4, RF-05.4, RF-05.5, RF-06.1, RF-06.2, RF-06.3, RF-06.5, RF-06.6, RF-06.8 · CA-12, CA-17 a CA-21, CA-23 · Requirements: 4.6, 10.2, 10.3, 10.4, 11.1, 11.2, 12.1, 12.2, 12.3, 12.4, 13.1, 13.2, 13.3, 13.4, 13.5, 14.1, 14.2, 14.3, 14.4, 14.5, 16.1, 16.2, 16.3, 16.4, 17.1, 17.2, 17.3, 19.1_

  - [x] 5.4 Runbook: borrado del stack
    - Añadir a la sección stack de `docs/aws/runbook.md` el procedimiento de C15, en este orden: `aws cloudformation update-termination-protection --no-enable-termination-protection --stack-name pgguardian`; `aws ec2 modify-instance-attribute --instance-id <InstanceId> --no-disable-api-termination`; un snapshot del disco raíz y uno del Volumen_Sandbox con `scripts/aws/manual_snapshot.sh` (tarea 7.4), ambos en `completed`; `aws cloudformation delete-stack --stack-name pgguardian` y `aws cloudformation wait stack-delete-complete --stack-name pgguardian`.
    - Indicar que el borrado elimina la instancia, los dos discos, la Elastic IP, el rol, el Security Group, el presupuesto, la alarma y las anomalías, y que los snapshots se conservan porque no pertenecen al stack. Anotar también que, al borrar el stack, la cuenta queda sin monitor de anomalías (el por defecto se borró en la comprobación previa de la tarea 5.2) y que, si la cuenta sigue en uso, se puede volver a crear uno de servicios desde la consola de Cost Anomaly Detection.
    - _Requirements: 23.3, 29.8, 29.9_

- [x] 6. Fase 4: host y despliegue (T-16 a T-18)
  - [x] 6.1 T-16: Script `scripts/aws/bootstrap_host.sh` (idempotente)
    - Recibe como argumento el output `SandboxVolumeId` y localiza el dispositivo NVMe en `/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_vol<id sin guion>`, no en `/dev/sdf`. La plantilla no lleva `UserData`, así que el script se ejecuta por Session Manager.
    - Formateo con `mkfs.ext4` solo si falta sistema de archivos, entrada `/etc/fstab` por UUID con `nofail` y montaje.
    - Ejecutar `mkdir -p /srv/sandbox/pgdata` y `chown 999:999 /srv/sandbox/pgdata` solo después de comprobar con `findmnt /srv/sandbox` que es un punto de montaje del Volumen_Sandbox. Si la comprobación falla, abortar el bootstrap sin crear el directorio: uno creado antes del montaje quedaría en el disco raíz y `create_host_path: false` no protegería nada.
    - Swap `/swapfile` de 2 GiB persistente sin duplicar áreas, `unattended-upgrades` solo con `-security` y `20auto-upgrades` (`"1"` y `"1"`), instalación de Docker Engine y Compose, y `systemctl enable docker` para que Docker arranque con el sistema (R19.8).
    - Añadir a la sección host de `docs/aws/runbook.md` los comandos de verificación: `swapon --show` (también tras 3 reinicios), `findmnt /srv/sandbox`, `systemctl is-active/is-enabled unattended-upgrades` y contenido de `20auto-upgrades`; `SANDBOX_DATA_DIR=/srv/sandbox/pgdata` en el `.env` del servidor y `/srv/sandbox/pgdata` en el dispositivo del Volumen_Sandbox y no en el de `/` (`df`); y la prueba de llenado con `generate_series` (login e historial ≤ 3 s, `/` varía ≤ 1 pp).
    - Añadir a la sección host la prueba manual de volumen ausente: reiniciar la instancia sin el Volumen_Sandbox adjunto y confirmar que el sistema arranca (`nofail`), que `sandbox_db` no arranca y que `/srv/sandbox/pgdata` no existe en el disco raíz (`ls` falla; `df /srv/sandbox` muestra el dispositivo raíz).
    - Añadir a la sección instancia la verificación del acceso sin SSH: `aws ec2 describe-instances` con `KeyName` vacío o ausente, `aws ec2 describe-security-groups` sin ninguna regla de entrada TCP/22, y una sesión de Session Manager con el evento `StartSession` en CloudTrail (`lookup-events`, hasta 15 min).
    - Idempotente: una segunda ejecución no formatea el disco, no duplica entradas en `/etc/fstab` ni crea un segundo swap. Antes de `mkfs.ext4`, comprobar con `blkid` que el dispositivo no tiene sistema de archivos. Si el enlace `/dev/disk/by-id/...` no existe, abortar sin modificar nada. Usar `set -euo pipefail` y un mensaje por paso. Validar con `bash -n` y `shellcheck`.
    - En la sección host del runbook: entrar con `sudo -iu ubuntu bash` (Session Manager abre `sh`); llevar el script a la instancia con un heredoc (`cat > ~/bootstrap_host.sh <<'EOF' … EOF`, funciona con el repo privado) o con `curl` del archivo raw si el repo es público; ejecutar con `sudo bash ~/bootstrap_host.sh <SandboxVolumeId>`.
    - _RF-04.4, RF-05.5, RF-06.3, RF-06.4, RF-06.7 · CA-12, CA-17, CA-18, CA-20, CA-22 · Requirements: 4.5, 4.6, 4.7, 4.8, 4.9, 4.10, 11.1, 11.3, 11.4, 11.5, 15.1, 15.2, 15.3, 15.4, 18.1, 18.2, 18.3, 18.4, 18.5, 19.8_

  - [x] 6.2 T-17: Plantilla `.env` de producción y generación de secretos
    - Actualizar `.env.prod.example` con `JWT_SECRET` documentado como obligatorio, `APP_DOMAIN`, `CORS_ORIGINS`, `COOKIE_SECURE` y `TRUST_PROXY_HEADERS`, sin claves de AWS (`SANDBOX_DATA_DIR` ya se añade en T-04).
    - Crear `scripts/aws/make_env.sh`: genera `JWT_SECRET` con `openssl rand -hex 32`, recibe `APP_DOMAIN` como argumento con el valor del output `AppDomain` del stack (el rol de la instancia no tiene permisos de CloudFormation), define `SANDBOX_DATA_DIR=/srv/sandbox/pgdata` y aplica permisos `600`.
    - Al terminar, `make_env.sh` comprueba `SANDBOX_DATA_DIR=/srv/sandbox/pgdata` en el `.env` generado y falla si falta o difiere, porque el valor por defecto dejaría los datos de `sandbox_db` en el disco raíz.
    - _RF-04.1, RF-04.4, RF-03.4, RF-03.5 (E1) · CA-09, CA-12, CA-23 · Requirements: 1.4, 4.4, 10.2, 19.2, 29.3_

  - [x] 6.3 T-18: Despliegue con HTTPS válido
    - Crear `scripts/aws/deploy.sh`: antes de `up`, falla si `SANDBOX_DATA_DIR` falta o difiere de `/srv/sandbox/pgdata` en el `.env`; ejecuta `docker compose -f docker-compose.prod.yml up -d --build`, espera el certificado hasta 120 s y, si falla, aplica el respaldo DuckDNS (actualiza `APP_DOMAIN` y repite `up -d`); si tampoco emite, muestra `docker logs` del proxy.
    - Añadir a la sección despliegue de `docs/aws/runbook.md` los comandos de verificación: certificado de Let's Encrypt vigente, redirección HTTP→HTTPS (`curl -I http://<dominio>`) y `curl -sI https://<dominio>` con las cinco cabeceras y 0 `Server`.
    - _RF-06.8, RF-03.4 (E1), RF-04.5 · CA-13, CA-23 · Requirements: 4.4, 5.6, 19.3, 19.4, 19.5, 19.6, 19.7_

  - [x] 6.4 Sección «Encender y detener» del runbook (sin T-xx; sustituye RF-03.6)
    - Añadir a `docs/aws/runbook.md` la sección «Encender y detener» con `aws ec2 stop-instances --instance-ids <InstanceId>` y `aws ec2 start-instances --instance-ids <InstanceId>`, usando el output `InstanceId` del stack (`aws cloudformation describe-stacks --stack-name pgguardian --query "Stacks[0].Outputs"`, tarea 5.2), y `aws ec2 wait instance-stopped` / `instance-running` para esperar cada estado.
    - Verificación tras encender, sin intervención manual y en ≤ 5 min desde el inicio: la Instancia aparece `Online` en SSM (`aws ssm describe-instance-information`); `docker ps` muestra los 5 contenedores en ejecución, porque los servicios tienen `restart: unless-stopped` y Docker arranca con el sistema (tarea 6.1); y `curl https://<dominio>/api/health-check` devuelve `{"status":"ok"}`. Anotar el resultado con el formato «Resultado de verificación».
    - Nota: la Elastic IP conserva la dirección y Caddy guarda el certificado en el volumen `caddy_data`, así que la URL y el HTTPS no cambian.
    - Nota de costo: detenida, la Instancia no cobra cómputo, pero se siguen cobrando los discos (20 + 8 GB gp3) y la Elastic IP, unos 5.9 USD al mes.
    - _Sustitución de RF-03.6 (R24.3), RF-06.8 · CA-23 · Requirements: 19.1, 19.8, 24.3_

- [x] 7. Fase 5: costos y resiliencia (T-19 a T-22, T-27 y secreto huérfano)
  - [x] 7.1 T-19: Verificación del presupuesto mensual de 30 USD
    - El presupuesto lo crea la plantilla (tarea 5.1); esta tarea solo añade verificaciones.
    - Añadir a la sección costos de `docs/aws/runbook.md` los comandos `describe-budget` (incluido `CostTypes`) y `describe-notifications-for-budget` (exactamente 4 notificaciones), con la instrucción de anotar notificaciones faltantes o sobrantes.
    - _RF-07.1 · CA-24 · Requirements: 20.1, 20.2, 20.3, 20.4, 20.5, 20.6, 20.7_

  - [x] 7.2 T-20: Verificación de Cost Anomaly Detection
    - El monitor y la suscripción los crea la plantilla (tarea 5.1); esta tarea añade sus verificaciones.
    - Solo si se activa el plan B de la tarea 5.2: crear `scripts/aws/create_anomaly_detection.sh` con el mismo monitor `DIMENSIONAL` de servicio y la suscripción `DAILY` por correo con la misma `ThresholdExpression` que la plantilla, y anotar en la sección costos que esos dos recursos quedan fuera del stack. Antes de crear el monitor, el script hace la misma comprobación previa de la tarea 5.2: busca un monitor `DIMENSIONAL` con `get-anomaly-monitors`, guarda como evidencia la salida de ese comando y la de `get-anomaly-subscriptions`, borra las suscripciones y después el monitor.
    - Añadir a la sección costos de `docs/aws/runbook.md` la verificación con `get-anomaly-monitors` y `get-anomaly-subscriptions`.
    - _RF-07.2 · CA-24 · Requirements: 21.1, 21.2, 21.3, 21.4, 29.10_

  - [x] 7.3 T-21: Verificación de la alarma de recuperación automática
    - La alarma la crea la plantilla (tarea 5.1); esta tarea solo añade verificaciones.
    - Añadir a la sección snapshots de `docs/aws/runbook.md` la verificación con `describe-alarms` y la prueba con `set-alarm-state`.
    - _RF-07.3 · CA-25 · Requirements: 22.1, 22.2, 22.3, 22.4_

  - [x] 7.4 T-22: Snapshots manuales de estabilización
    - Crear `scripts/aws/manual_snapshot.sh`: recibe el volumen (raíz, obtenido con `describe-instances` a partir del output `InstanceId`, o sandbox, del output `SandboxVolumeId`), crea el snapshot con las etiquetas `Project`, `Env` y `Owner`, espera con `aws ec2 wait snapshot-completed` e informa si termina en `error`.
    - Añadir a la sección snapshots de `docs/aws/runbook.md` el procedimiento: al alcanzar el estado estable (App_DB y la aplicación pasan sus verificaciones de salud durante al menos 5 min seguidos), un snapshot del disco raíz y uno del Volumen_Sandbox; verificar solo el estado `completed` con `describe-snapshots`, sin restaurar; repetir el del mismo volumen si termina en `error`.
    - _RF-07.4 · CA-26 · Requirements: 23.1, 23.3, 23.4_

  - [x] 7.5 T-27: Snapshots manuales previos a la grabación del video
    - Añadir a la sección snapshots de `docs/aws/runbook.md` el procedimiento con `scripts/aws/manual_snapshot.sh`: 24 h o menos antes de grabar el video, un segundo snapshot del disco raíz y uno del Volumen_Sandbox, verificados por estado `completed` y repetidos si terminan en `error`. Resultado esperado: 4 snapshots `completed` (2 por disco).
    - _RF-07.4 · CA-26 · Requirements: 23.2, 23.3, 23.4_

  - [x] 7.6 Secreto huérfano de Secrets Manager (sin T-xx; ejecución manual por el Equipo)
    - Añadir a la sección costos de `docs/aws/runbook.md` el procedimiento manual: `aws secretsmanager list-secrets --region us-east-2` para identificar el Secreto_Huerfano; confirmar que no se usa (fecha de último acceso y búsqueda del nombre o ARN en el código, en `docker-compose.prod.yml` y en el `.env` de la Instancia); solo entonces `aws secretsmanager delete-secret --secret-id <arn> --recovery-window-in-days <7..30>`, nunca con `--force-delete-without-recovery`; y `describe-secret` para ver la fecha de borrado programada.
    - Incluir el caso en que no se puede confirmar el no uso: conservar el secreto y registrar el motivo.
    - _Limpieza de la cuenta · Requirements: 27.1, 27.2, 27.3, 27.4_

- [x] 8. Checkpoint: infraestructura y scripts
  - Ensure all tests pass, ask the user if questions arise.

- [x] 9. Fase 6: evidencia, registro de decisiones y documentación (T-23 a T-26)
  - [x] 9.1 T-23: Script de ZAP baseline
    - Crear `scripts/aws/run_zap.sh` (`ghcr.io/zaproxy/zaproxy:stable zap-baseline.py`, reporte HTML con fecha, hora y URL en `docs/aws/evidencia/`) y la plantilla `docs/aws/evidencia/justificaciones.md` para hallazgos medios o altos y puertos extra.
    - _RF-08.2 · CA-27 · Requirements: 25.1, 25.2, 25.6_

  - [x] 9.2 T-24: Script de `nmap`
    - Crear `scripts/aws/run_nmap.sh` (`nmap -Pn -p 1-65535 <eip>`, salida con fecha en `docs/aws/evidencia/`), con aviso si hay puertos abiertos distintos de 80 y 443.
    - _RF-08.2 · CA-27 · Requirements: 25.3, 25.4, 25.6_

  - [x] 9.3 T-25: Estructura de evidencia de CA-01 a CA-08
    - Crear `docs/aws/evidencia/ca-01..ca-08/` con una plantilla por criterio (URL pública, resultado aprobado/fallido y evidencia: captura, o marca de tiempo del fragmento de la grabación del video en que se ve la URL pública) y un índice del Paquete_Evidencia (`docs/aws/evidencia/README.md`).
    - _RF-08.2 · CA-01 a CA-08, CA-27 · Requirements: 25.5, 25.6_

  - [x] 9.4 T-26: Registro de decisiones
    - Completar `docs/aws/decision-log.md` (creado en la tarea 1.10 con la entrada R24.7 y ampliado en la tarea 4.2 con la decisión de diseño de T-10) hasta tener las diez entradas de R24.1 a R24.10, además de esa decisión, con los campos `requisito_afectado`, `cambio`, `justificacion`, `fecha` AAAA-MM-DD y `aprobador`:
      - R24.1: RF-01.4, disco propio del sandbox, justificación «un script que llena el disco no puede tumbar `app_db`».
      - R24.2: RF-03.3, Session Manager con el puerto 22 cerrado, justificación «las IP domésticas cambian».
      - R24.3 (sustituye a RF-03.6): `cambio` «la instancia se enciende o se detiene a criterio del Equipo; no es requisito que esté disponible 24/7 ni que se detenga fuera de las demostraciones»; `justificacion` «el peor caso (24/7, unos 22 USD al mes) cabe en los créditos de 100 USD, y el Presupuesto (R20) avisa si el gasto se desvía. La evaluación se hace con un video grabado, no con acceso en vivo».
      - R24.4: RF-07.4 y CA-26, dos snapshots manuales por disco en lugar de DLM, sin prueba de restauración.
      - R24.5: RF-05.3, `PgG-Admins` con los integrantes del Equipo como miembros en lugar de exactamente dos usuarios.
      - R24.6: CA-16, sin prueba con usuario sin MFA; se verifica con el reporte de credenciales y la definición de `Force_MFA`.
      - R24.7: ya registrada en la tarea 1.10; revisar que tenga todos los campos.
      - R24.8: `cambio` «CloudFormation en lugar de scripts de CLI para la infraestructura»; `justificacion` «creación y borrado reproducibles en un solo stack; herramienta vista en el curso; estaba como 'Debería' en el documento de cambios».
      - R24.9: `requisito_afectado` «alcance del E2 en la práctica de definición de requisitos»; `cambio` «el E2 pasa de 'multi-cliente con registro de usuarios y de bases propias' a 'despliegue en AWS'; el registro de usuarios se entregó en el E1 y la conexión a bases propias del cliente pasa a Mejoras futuras»; `justificacion` «decisión del Equipo: E1 = desarrollo, E2 = despliegue».
      - R24.10: `requisito_afectado` «R21.2 / RF-07.2»; `cambio` «el aviso de anomalías pasa de ≤ 60 minutos a un resumen diario por correo»; `justificacion` «el correo directo de Cost Anomaly Detection solo admite frecuencia diaria o semanal; el aviso inmediato requiere SNS, y el Presupuesto (R20) ya alerta por correo».
    - Añadir una columna o lista de aprobación (nombre y fecha, en ≤ 2 días hábiles) y una lista de cierre de T-26 que marque como no aprobada toda entrada sin campo o sin aprobación.
    - _RF-08.1 · CA-27 · Requirements: 24.1, 24.2, 24.3, 24.4, 24.5, 24.6, 24.7, 24.8, 24.9, 24.10, 24.11, 24.12_

  - [x] 9.5 Secciones del documento de requisitos original (sin T-xx; documentación)
    - Redactar en `PgGuardian - Requisitos del Entregable 2 (AWS).md` las secciones de alcance del E2 (debe indicar que el E2 es el despliegue en AWS y no el alcance multi-cliente original: el registro de usuarios se entregó en el E1 y la conexión a bases propias del cliente pasa a Mejoras futuras, según R24.9; y que la evaluación es con un video que muestra el funcionamiento desde la URL pública), plan de trabajo (fases 1 a 6 y su orden) y proceso estándar.
    - _Documentación del E2 · Requirements: 28.1, 28.2, 28.3, 24.9_

- [ ] 10. Checkpoint final
  - Ensure all tests pass, ask the user if questions arise.

## Notes

- Las tareas marcadas con `*` son opcionales y se pueden omitir para un MVP más rápido.
- El diseño no incluye una sección de Correctness Properties, por lo que no hay tareas de pruebas basadas en propiedades; solo pruebas unitarias y de configuración.
- Las ejecuciones en la cuenta AWS, el MFA físico, las capturas de pantalla y la grabación del video, el despliegue y el borrado del stack `pgguardian` (5.2, 5.4), el encendido y la detención de la Instancia (6.4), el borrado del secreto huérfano (7.6) y las aprobaciones del Equipo se realizan manualmente con los artefactos que producen estas tareas.
- `docs/aws/runbook.md` lo crea la tarea 4.1 y lo amplían 4.2, 4.3, 5.2 a 5.4, 6.1, 6.3, 6.4 y 7.1 a 7.6, cada una en una ola distinta. `docker-compose.prod.yml` (1.1 a 1.4), `Caddyfile` (1.5, 1.6), `.env.prod.example` (1.4, 6.2) y `docs/aws/decision-log.md` (1.10, 1.11, 9.4) también se modifican en olas distintas.
- Fuera de alcance (sección «Mejoras futuras» de `requirements.md`): grupo de operadores, `pg_dump` periódico, prueba de restauración, unidad systemd de respaldo, prueba con usuario sin MFA y política DLM.

- Las tareas 5.3, 6.1, 6.2, 6.4 y 7.4 usan los outputs del stack, por lo que dependen de la tarea 5.2 (despliegue de la plantilla). En particular, 6.4 toma el `InstanceId` de `describe-stacks`.

### Cobertura de requisitos

| Requirement | Tareas |
| --- | --- |
| R1 | 1.1, 1.9, 6.2 |
| R2 | 1.2, 1.9 |
| R3 | 1.3, 1.9 |
| R4 | 1.4, 1.9, 5.1, 5.3, 6.1, 6.2, 6.3 |
| R5 | 1.5, 1.6, 6.3 |
| R6 | 1.7, 1.8 |
| R7 | 2.1 |
| R8 | 4.1 |
| R9 | 4.2 |
| R10 | 4.3, 5.1, 5.3, 6.2 |
| R11 | 5.1, 5.3, 6.1 |
| R12 | 5.1, 5.3 |
| R13 | 5.1, 5.3 |
| R14 | 5.1, 5.3 |
| R15 | 6.1 |
| R16 | 5.1, 5.3 |
| R17 | 5.1, 5.3 |
| R18 | 6.1 |
| R19 | 5.1, 5.3, 6.1, 6.2, 6.3, 6.4 |
| R20 | 5.1, 7.1 |
| R21 | 5.1, 5.2, 7.2 |
| R22 | 5.1, 7.3 |
| R23 | 5.4, 7.4, 7.5 |
| R24 | 1.10, 6.4, 9.4, 9.5 |
| R25 | 9.1, 9.2, 9.3 |
| R26 | 1.10, 1.11 |
| R27 | 7.6 |
| R28 | 9.5 |
| R29 | 5.1, 5.2, 5.4, 6.2, 7.2, 9.4 |

## Task Dependency Graph

```json
{
  "waves": [
    { "id": 0, "tasks": ["1.1", "1.5", "1.7", "1.10", "4.1", "5.1", "9.5"] },
    { "id": 1, "tasks": ["1.2", "1.6", "1.8", "1.11", "4.2", "9.1", "9.2", "9.3"] },
    { "id": 2, "tasks": ["1.3", "4.3", "9.4"] },
    { "id": 3, "tasks": ["1.4", "5.2"] },
    { "id": 4, "tasks": ["1.9", "2.1", "5.3", "6.2"] },
    { "id": 5, "tasks": ["5.4"] },
    { "id": 6, "tasks": ["6.1"] },
    { "id": 7, "tasks": ["6.3"] },
    { "id": 8, "tasks": ["6.4"] },
    { "id": 9, "tasks": ["7.1"] },
    { "id": 10, "tasks": ["7.2"] },
    { "id": 11, "tasks": ["7.3"] },
    { "id": 12, "tasks": ["7.4"] },
    { "id": 13, "tasks": ["7.5"] },
    { "id": 14, "tasks": ["7.6"] }
  ]
}
```
