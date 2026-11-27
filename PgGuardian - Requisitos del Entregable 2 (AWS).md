# PgGuardian — Requisitos del Entregable 2 (despliegue en AWS)

Nov 24, 2026

## 1. Introducción

Este documento convierte la propuesta «Cambios para el Entregable 2» en requisitos, tareas y criterios de aceptación. Continúa la numeración de la [especificación del E1](PgGuardian%20-%20Especificación%20de%20requisitos%20de%20nuevas%20funcionalidades.md): los requisitos nuevos van de RF-04 a RF-08 y los criterios de aceptación siguen desde CA-09. Las prioridades usan MoSCoW: Debe, Debería, Podría.

El diseño base no cambia: una instancia EC2 **t3.small** con Ubuntu 24.04 en **us-east-2**, Docker Compose con cinco contenedores, solo Caddy expuesto a internet, Elastic IP y `sslip.io`. El presupuesto es de 100 USD en créditos, que vencen el 11 de mayo de 2027, y el costo estimado 24/7 es de unos 22 USD al mes.

## 2. Requisitos

### RF-04 · Endurecimiento del código y la configuración

Se hacen en local, antes del primer despliegue.

| ID | Requisito | Archivo | Prioridad |
| --- | --- | --- | --- |
| RF-04.1 | El despliegue falla si `JWT_SECRET` no está definido (`${JWT_SECRET:?falta JWT_SECRET}`); nunca se usa la clave de desarrollo de `sessions.py`. | `docker-compose.prod.yml` | Debe |
| RF-04.2 | Todos los servicios rotan sus logs con el driver `json-file`, `max-size: 10m` y `max-file: 3`. | `docker-compose.prod.yml` | Debe |
| RF-04.3 | Límite de memoria por contenedor: `sandbox_db` 512m, `app_db` 384m y `api` 512m. | `docker-compose.prod.yml` | Debe |
| RF-04.4 | Los datos de `sandbox_db` viven en un volumen EBS propio montado en `/srv/sandbox`, separado del disco raíz. | `docker-compose.prod.yml` | Debe |
| RF-04.5 | Caddy envía HSTS, `X-Content-Type-Options: nosniff`, `X-Frame-Options`, `Referrer-Policy` y CSP, y no envía la cabecera `Server`. | `Caddyfile` | Debe |
| RF-04.6 | `/api/health-check` responde solo `{"status": ...}`, sin mensajes de error ni versión de PostgreSQL. | `backend/api/main.py` | Debe |

CSP de partida: `default-src 'self'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; frame-ancestors 'none'`. Se ajusta después de probarla con el build real del frontend.

### RF-05 · Cuenta, IAM y acceso al servidor

| ID | Requisito | Prioridad |
| --- | --- | --- |
| RF-05.1 | La cuenta raíz tiene MFA, no tiene access keys y no se usa para operar. El acceso de usuarios IAM a la facturación está activado. | Debe |
| RF-05.2 | Hay un usuario IAM por integrante, con MFA obligatorio mediante la política *Force MFA* y sin access keys. La CLI se usa desde CloudShell. | Debe |
| RF-05.3 | El grupo `PgG-Admins` tiene `AdministratorAccess` (condicionado a MFA) y exactamente dos integrantes. | Debe |
| RF-05.4 | La instancia usa el rol `PgGuardian-EC2-Role` con la política `AmazonSSMManagedInstanceCore` y no guarda credenciales en disco. | Debe |
| RF-05.5 | El servidor se administra solo con SSM Session Manager. El puerto 22 queda cerrado y no se reparten llaves `.pem`. | Debe |

### RF-06 · Infraestructura en EC2

| ID | Requisito | Prioridad |
| --- | --- | --- |
| RF-06.1 | El Security Group abre solo 80 y 443 a `0.0.0.0/0`. No hay ninguna otra regla de entrada. | Debe |
| RF-06.2 | La instancia exige IMDSv2 (`HttpTokens=required`). | Debe |
| RF-06.3 | El disco raíz es de 20 GB gp3 cifrado y hay un segundo volumen de 8 GB gp3 cifrado para el sandbox. | Debe |
| RF-06.4 | Hay 2 GB de swap que persisten tras reiniciar. | Debe |
| RF-06.5 | La protección contra terminación está activada. | Debe |
| RF-06.6 | La instancia, los volúmenes y la Elastic IP llevan las etiquetas `Project=PgGuardian`, `Env=prod` y `Owner`. | Debería |
| RF-06.7 | `unattended-upgrades` instala los parches de seguridad del sistema operativo automáticamente. | Debería |
| RF-06.8 | Si Let's Encrypt falla con `sslip.io`, se usa un subdominio de DuckDNS. | Podría |

### RF-07 · Operación, costos y respaldos

| ID | Requisito | Prioridad |
| --- | --- | --- |
| RF-07.1 | AWS Budgets tiene un presupuesto de 30 USD al mes con alertas al 50, 80 y 100 % del gasto real y una alerta por pronóstico. | Debe |
| RF-07.2 | Cost Anomaly Detection está activo y envía avisos al correo del equipo. | Debería |
| RF-07.3 | Una alarma de CloudWatch sobre `StatusCheckFailed_System` ejecuta la acción *recover*. | Debería |
| RF-07.4 | Data Lifecycle Manager toma snapshots de EBS. Hay al menos uno al estabilizar el sistema y otro antes de la demo. | Debe |

### RF-08 · Documentación y evidencia

| ID | Requisito | Prioridad |
| --- | --- | --- |
| RF-08.1 | Cada desviación de un requisito del E1 queda registrada como decisión, con su justificación y la aprobación del equipo (ver sección 3). | Debe |
| RF-08.2 | La entrega incluye el reporte de ZAP baseline, un `nmap` contra la IP pública y los resultados de CA-01 a CA-08 ejecutados desde la URL pública. | Debe |

## 3. Cambios a requisitos del E1

| Requisito original | Cambio | Motivo |
| --- | --- | --- |
| RF-01.4 (aislamiento del sandbox) | Se refuerza: el sandbox tiene un disco propio (RF-04.4). | Un script que llena el disco no puede tumbar `app_db`. |
| RF-03.3 («22 solo al equipo») | Se reemplaza por SSM Session Manager con el 22 cerrado (RF-05.5). | Las IP de casa cambian, y en la práctica el 22 terminaría abierto a todo internet. |
| RF-03.6 («instancia detenida fuera de las demos») | La instancia puede quedar encendida 24/7 y el control de gasto pasa a Budgets con alertas (RF-07.1). | El costo 24/7 (~22 USD/mes) cabe en los créditos, y detenerla no ahorra la Elastic IP ni los discos. |

## 4. Tareas

Las fases van en orden; dentro de cada fase, las tareas pueden repartirse entre integrantes.

### Fase 1 · Código (local)

- [ ] **T-01** Cambiar `JWT_SECRET` en `docker-compose.prod.yml` a `${JWT_SECRET:?falta JWT_SECRET}`. *(RF-04.1)*
- [ ] **T-02** Agregar un bloque `logging` común (ancla YAML `x-logging`) y aplicarlo a los cinco servicios. *(RF-04.2)*
- [ ] **T-03** Agregar `mem_limit` a `sandbox_db`, `app_db` y `api`. *(RF-04.3)*
- [ ] **T-04** Cambiar el volumen `sandbox_data` por un bind mount a `/srv/sandbox/pgdata`. PostgreSQL necesita un subdirectorio, porque la raíz de un disco recién formateado trae `lost+found`. *(RF-04.4)*
- [ ] **T-05** Agregar al `Caddyfile` un bloque `header` con las cinco cabeceras y `-Server`. *(RF-04.5)*
- [ ] **T-06** Probar la CSP con el build de producción del frontend y revisar en la consola del navegador que no haya recursos bloqueados. *(RF-04.5)*
- [ ] **T-07** Cambiar `/api/health-check` para que devuelva solo `status` y registre el detalle del error en el log del servidor. *(RF-04.6)*
- [ ] **T-08** Verificar que `docker compose up` en local siga funcionando (RNF-05) y abrir el PR.

### Fase 2 · Cuenta e IAM

- [ ] **T-09** Proteger la cuenta raíz: MFA, borrar cualquier access key y activar el acceso de IAM a la facturación. *(RF-05.1)*
- [ ] **T-10** Crear la política *Force MFA*, el grupo `PgG-Admins` y un usuario IAM por integrante. Cada quien activa su MFA. *(RF-05.2, RF-05.3)*
- [ ] **T-11** Crear el rol `PgGuardian-EC2-Role` con `AmazonSSMManagedInstanceCore`. *(RF-05.4)*

### Fase 3 · Infraestructura

- [ ] **T-12** Crear el Security Group con solo 80 y 443. *(RF-06.1)*
- [ ] **T-13** Lanzar la t3.small con Ubuntu 24.04, el rol, IMDSv2 obligatorio, disco raíz de 20 GB gp3 cifrado, protección contra terminación y etiquetas. *(RF-06.2, RF-06.3, RF-06.5, RF-06.6)*
- [ ] **T-14** Crear el volumen de 8 GB gp3 cifrado, adjuntarlo, formatearlo y montarlo en `/srv/sandbox` por UUID en `/etc/fstab` con `nofail`. *(RF-04.4, RF-06.3)*
- [ ] **T-15** Asignar y asociar la Elastic IP. *(RF-03.1)*
- [ ] **T-16** Desde Session Manager: crear 2 GB de swap, activar `unattended-upgrades` e instalar Docker. *(RF-05.5, RF-06.4, RF-06.7)*

### Fase 4 · Despliegue

- [ ] **T-17** Clonar el repo y crear `.env` con permisos `600`, un `JWT_SECRET` aleatorio de al menos 32 bytes y `APP_DOMAIN=<ip-con-guiones>.sslip.io`. *(RF-03.5, RF-04.1)*
- [ ] **T-18** Levantar con `docker compose -f docker-compose.prod.yml up -d --build` y confirmar que Caddy obtuvo el certificado. Si falla, pasar a DuckDNS. *(RF-03.4, RF-06.8)*

### Fase 5 · Operación

- [ ] **T-19** Configurar el presupuesto de 30 USD y sus cuatro alertas en Budgets. *(RF-07.1)*
- [ ] **T-20** Activar Cost Anomaly Detection con suscripción por correo. *(RF-07.2)*
- [ ] **T-21** Crear la alarma `StatusCheckFailed_System` con la acción *recover*. *(RF-07.3)*
- [ ] **T-22** Crear la política de Data Lifecycle Manager por etiqueta, tomar el primer snapshot y probar restaurarlo en un volumen nuevo. *(RF-07.4)*

### Fase 6 · Evidencia y documentación

- [ ] **T-23** Correr ZAP baseline contra la URL pública y corregir los hallazgos de nivel medio o mayor. *(RF-08.2)*
- [ ] **T-24** Correr `nmap` contra la Elastic IP y guardar la salida. *(RF-08.2)*
- [ ] **T-25** Repetir CA-01 a CA-08 desde la URL pública y guardar capturas. *(RF-08.2)*
- [ ] **T-26** Registrar las decisiones de la sección 3 en la especificación y conseguir la aprobación del equipo. *(RF-08.1)*
- [ ] **T-27** Tomar el snapshot previo a la demo. *(RF-07.4)*

## 5. Criterios de aceptación

| ID | Criterio | Cómo se verifica | Cubre |
| --- | --- | --- | --- |
| CA-09 | Sin `JWT_SECRET`, Compose se niega a arrancar. | `docker compose -f docker-compose.prod.yml config` con la variable vacía termina en error con el mensaje «falta JWT_SECRET». | RF-04.1 |
| CA-10 | Los cinco contenedores rotan logs. | `docker inspect -f '{{.HostConfig.LogConfig}}'` muestra `json-file` con `max-size:10m` y `max-file:3` en cada uno. | RF-04.2 |
| CA-11 | Los límites de memoria están aplicados. | `docker stats --no-stream` muestra 512 MiB en `sandbox_db` y `api`, y 384 MiB en `app_db`. | RF-04.3 |
| CA-12 | Si el sandbox se queda sin disco, `app_db` no se ve afectada. | `df -h /srv/sandbox` muestra un dispositivo distinto al de `/`. Un script con `generate_series` masivo llena el sandbox y, mientras tanto, login e historial siguen funcionando. | RF-04.4, RF-01.4 |
| CA-13 | Las cabeceras de seguridad están presentes y `Server` no aparece. | `curl -sI https://<dominio>` muestra HSTS, `nosniff`, `X-Frame-Options`, `Referrer-Policy` y CSP, sin `Server`. El frontend carga sin errores de CSP en la consola. | RF-04.5 |
| CA-14 | El health-check no filtra información. | `curl https://<dominio>/api/health-check` devuelve solo `{"status": ...}`, también con `app_db` detenida. | RF-04.6 |
| CA-15 | Nadie opera sin MFA ni con llaves de larga duración. | El reporte de credenciales de IAM muestra `mfa_active=true` y ninguna access key activa en todos los usuarios. El resumen de la cuenta muestra `AccountMFAEnabled=1` y `AccountAccessKeysPresent=0`. | RF-05.1, RF-05.2 |
| CA-16 | Sin MFA, un usuario no puede operar. | Un usuario que inicia sesión sin MFA recibe `AccessDenied` al intentar, por ejemplo, listar instancias. | RF-05.2, RF-05.3 |
| CA-17 | Se entra al servidor sin SSH y queda registro. | Session Manager abre una consola en la instancia. CloudTrail muestra el evento `StartSession` con el usuario IAM que la abrió. | RF-05.4, RF-05.5 |
| CA-18 | Solo responden 80 y 443. | `nmap -Pn -p- <elastic-ip>` muestra únicamente 80 y 443 abiertos. | RF-06.1, RF-05.5, CA-07 |
| CA-19 | IMDSv1 está bloqueado. | Desde la instancia, `curl http://169.254.169.254/latest/meta-data/` sin token responde `401`. | RF-06.2 |
| CA-20 | Los discos, el swap y la protección contra terminación sobreviven a un reinicio. | Después de `sudo reboot`, ambos volúmenes aparecen con `Encrypted=true`, `/srv/sandbox` está montado, `swapon --show` muestra 2 GB y el atributo `disableApiTermination` es `true`. | RF-06.3–RF-06.5 |
| CA-21 | Los recursos están etiquetados. | La instancia, ambos volúmenes y la Elastic IP tienen `Project`, `Env` y `Owner`. | RF-06.6 |
| CA-22 | Los parches de seguridad se instalan solos. | `/etc/apt/apt.conf.d/20auto-upgrades` tiene ambos valores en `1` y `unattended-upgrades` aparece activo en `systemctl`. | RF-06.7 |
| CA-23 | El HTTPS es válido. | El navegador abre la URL pública sin advertencias y el certificado lo emite Let's Encrypt. | RF-03.4, RF-06.8 |
| CA-24 | El control de gasto está configurado. | Budgets muestra el presupuesto de 30 USD con cuatro notificaciones. Cost Anomaly Detection tiene un monitor con suscripción. | RF-07.1, RF-07.2 |
| CA-25 | La recuperación automática está configurada. | La alarma existe en `us-east-2` con la acción `arn:aws:automate:us-east-2:ec2:recover`. | RF-07.3 |
| CA-26 | Los respaldos funcionan. | Hay al menos dos snapshots. Uno se restauró en un volumen nuevo y sus datos de `app_db` se pudieron leer. | RF-07.4 |
| CA-27 | La evidencia está completa. | La entrega incluye el reporte de ZAP sin hallazgos de riesgo medio o alto sin justificar, la salida de `nmap` y los resultados de CA-01 a CA-08 desde la URL pública. | RF-08.1, RF-08.2 |

## 6. Pendientes por definir

- **Política de operadores.** La propuesta menciona que «la política de operadores depende de las etiquetas», pero no define un grupo de operadores. Si los otros dos integrantes necesitan reiniciar la instancia o entrar por SSM sin ser administradores, hay que crear ese grupo con permisos limitados a los recursos con `Project=PgGuardian`.
- **Restauración de `app_db`.** Un snapshot de EBS con PostgreSQL encendido es consistente solo ante fallos. Si se quiere una copia lógica, conviene agregar un `pg_dump` periódico de `app_db`.

## 7. Alcance del E2

El E2 es el **despliegue de PgGuardian en AWS**. No es el alcance multi-cliente que planteaba originalmente la práctica de definición de requisitos («multi-cliente con registro de usuarios y de bases propias»). El Equipo lo decidió así: el E1 es el desarrollo y el E2 es el despliegue.

- **Registro de usuarios:** ya se entregó en el E1 (RF-01 a RF-03) y en el E2 solo se despliega y se verifica desde la URL pública (CA-01 a CA-08).
- **Conexión a bases propias del cliente:** registrar una base PostgreSQL del cliente con una credencial de solo lectura y auditarla de forma continua queda fuera del E2 y pasa a la sección «Mejoras futuras» de la especificación (`.kiro/specs/aws-deployment-e2/requirements.md`).
- **Qué incluye el E2:** el endurecimiento del código y la configuración (RF-04), la cuenta, IAM y el acceso al servidor (RF-05), la infraestructura en EC2 (RF-06), la operación, los costos y los respaldos (RF-07), y la documentación y la evidencia (RF-08).

El cambio de alcance está registrado en `docs/aws/decision-log.md` como decisión del Equipo, con el requisito afectado «alcance del E2 en la práctica de definición de requisitos».

**Evaluación.** El E2 se evalúa con un video grabado que muestra el funcionamiento de la aplicación desde la URL pública HTTPS, no con acceso en vivo. Por eso la instancia se enciende o se detiene a criterio del Equipo y no tiene que estar disponible 24/7; para la grabación se enciende y la aplicación vuelve sola por la misma URL. El video sirve también como evidencia de CA-01 a CA-08: cada criterio se identifica por su marca de tiempo, siempre que la URL pública se vea en pantalla.

## 8. Plan de trabajo

El trabajo se divide en seis fases que se ejecutan en este orden. Una fase empieza cuando la anterior terminó y sus criterios quedaron verificados; dentro de cada fase, las tareas pueden repartirse entre integrantes.

```text
Fase 1 → T-08 → Fase 2 → Fase 3 → Fase 4 → Fase 5 → Fase 6
```

| Fase | Contenido | Tareas | Resultado para pasar a la siguiente |
| --- | --- | --- | --- |
| 1 · Código (local) | Endurecimiento de `docker-compose.prod.yml`, `Caddyfile` y `/api/health-check`, y retiro de las llamadas del frontend de producción a los endpoints que dependen de TiendaDB. | T-01 a T-07, más la tarea del frontend (sin T-xx) | Cambios hechos en local. |
| 1 → 2 · Verificación local | `docker compose up` en local sigue funcionando (RNF-05) y se abre el PR. | T-08 | PR revisado y fusionado. |
| 2 · Cuenta e IAM | Protección de la cuenta raíz, política *Force MFA*, grupo `PgG-Admins` y un usuario IAM por integrante con MFA. | T-09, T-10 | CA-15 y CA-16 verificados. |
| 3 · Stack CloudFormation | Despliegue desde CloudShell del stack `pgguardian` (plantilla `infra/cloudformation/pgguardian.yaml`): rol de la instancia, Security Group, instancia, volumen del sandbox, Elastic IP, presupuesto, Cost Anomaly Detection y alarma *recover*. | T-11 a T-15, T-19 a T-21 (recursos de la plantilla) | Stack en `CREATE_COMPLETE` con sus outputs. |
| 4 · Host y despliegue | Swap, `unattended-upgrades`, Docker y montaje de `/srv/sandbox` desde Session Manager; `.env` con permisos `600`; `docker compose up` y certificado de Let's Encrypt. | T-16, T-17, T-18 | La URL pública responde por HTTPS sin advertencias (CA-23). |
| 5 · Costos y resiliencia | Verificación del presupuesto, de Cost Anomaly Detection y de la alarma *recover*; primer snapshot manual por disco; borrado del secreto huérfano de Secrets Manager. | T-19 a T-21 (verificación), T-22, T-27, secreto huérfano (sin T-xx) | CA-24, CA-25 y CA-26 verificados. |
| 6 · Evidencia, registro y documentación | ZAP baseline, `nmap`, CA-01 a CA-08 desde la URL pública, registro de decisiones con aprobación y las secciones 7 a 9 de este documento. | T-23 a T-26, documentación (sin T-xx) | CA-27 verificado y video grabado. |

El orden responde a las dependencias: la infraestructura no se crea hasta que el código pasa la verificación local, para no llevar regresiones a la instancia; la Fase 3 necesita usuarios IAM con MFA; la Fase 4 necesita la instancia y la Elastic IP del stack; y la evidencia de la Fase 6 solo puede tomarse con el sistema desplegado. El snapshot previo a la demo (T-27) se toma antes de grabar el video.

## 9. Proceso estándar

Estas reglas aplican a todo el trabajo del E2, en cualquier fase.

1. **Cambios de código.** Todo cambio va en una rama y llega a `main` por PR, después de verificar en local que `docker compose up` sigue funcionando.
2. **Acceso a AWS.** Cada integrante opera con su usuario IAM y MFA activo. Nadie usa la cuenta raíz ni crea access keys; la CLI se usa desde CloudShell en `us-east-2`.
3. **Cambios de infraestructura.** La infraestructura solo se modifica con un change set del stack `pgguardian`, revisado antes de ejecutarlo. Si el change set marca la instancia con `Replacement=True`, no se ejecuta. La única excepción a «solo por change set» es desactivar la protección contra terminación justo antes de borrar el stack.
4. **Acceso al servidor.** El servidor se administra solo con Session Manager; el puerto 22 permanece cerrado y no se reparten llaves `.pem`.
5. **Pasos y verificaciones.** Los pasos manuales y los comandos de verificación siguen `docs/aws/runbook.md`. Cada verificación queda como `aprobado`, `no_aprobado` o `no_verificable`; un criterio solo se da por aprobado cuando todos sus bloques están en `aprobado`. Si uno falla, se corrige la causa y se repite, conservando la línea anterior.
6. **Evidencia.** La salida de cada comando, o la captura en los pasos manuales, se guarda en `docs/aws/evidencia/` con fecha, hora y nombre de quien la ejecutó. Nunca se guardan secretos (`JWT_SECRET`, contraseñas) en la evidencia ni en el repositorio.
7. **Desviaciones.** Toda desviación del E1 o de este documento se registra en `docs/aws/decision-log.md` con requisito afectado, cambio, justificación, fecha (AAAA-MM-DD) y aprobador. El Equipo anota la aprobación en un plazo de 2 días hábiles; una entrada sin algún campo o sin aprobación se considera no aprobada.
8. **Encendido y costos.** La instancia se enciende y se detiene según la sección «Encender y detener» del runbook. El presupuesto de 30 USD y Cost Anomaly Detection avisan por correo si el gasto se desvía.
9. **Respaldos.** Se toman dos snapshots manuales por disco: uno al estabilizar el sistema (T-22) y otro antes de grabar el video (T-27). Cada uno se da por bueno cuando queda en `completed`; si queda en `error`, se repite.
