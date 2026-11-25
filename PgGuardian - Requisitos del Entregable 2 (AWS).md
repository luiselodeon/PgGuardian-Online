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
