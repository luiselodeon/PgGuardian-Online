# Paquete_Evidencia del Entregable 2

Trazabilidad: RF-08.2 · T-23, T-24, T-25 · CA-27 y CA-01 a CA-08 (E1) · Requirements 25.1 a 25.6.

Este índice lista lo que exige R25.6 y dónde está cada archivo. CA-27 se aprueba cuando todas las filas de la sección 1 están completas: reporte de ZAP sin hallazgos de riesgo medio o alto sin justificar, salida de `nmap`, justificaciones (si las hay) y el resultado de CA-01 a CA-08 desde la URL pública.

## Datos del despliegue

| Dato | Valor | Fuente |
| --- | --- | --- |
| URL pública | `https://3-14-31-64.sslip.io` | Output `AppDomain` del stack, `stack/outputs-20261126T0255Z.json` |
| Elastic IP | `3.14.31.64` | Output `PublicIp` del stack, mismo archivo |
| Video de la demostración | `<enlace al video>` | Se anota al publicarlo; las marcas de tiempo de `ca-01/` a `ca-08/` se refieren a este video |

Si la URL o la IP cambian, se actualizan aquí y en el registro de cada criterio antes de repetir las pruebas.

## 1. Contenido exigido por R25.6

| Artefacto | Archivo | Cómo se genera | Requisito | Estado |
| --- | --- | --- | --- | --- |
| Reporte de ZAP baseline (HTML completo, con fecha, hora y URL analizada) | `zap-baseline-20261127T0321Z.html`, con `.json` del mismo nombre (`zap.yaml` es el plan de Automation Framework que generó ZAP) | `bash scripts/aws/run_zap.sh` | R25.1, R25.2 | Final: ejecución 2026-11-27T03:22:00Z contra https://3-14-31-64.sslip.io. 0 FAIL, 8 WARN (2 reglas de riesgo medio, 3 alertas, justificadas en `justificaciones.md`; 2 reglas bajas y 4 informativas documentadas sin acción), 60 PASS |
| Salida de `nmap` (TCP 1 a 65535 contra la Elastic IP, con fecha y hora) | `nmap-<AAAAMMDDTHHMMZ>.txt` | `bash scripts/aws/run_nmap.sh` | R25.3, R25.4 | `<pendiente o archivo final>` |
| Justificaciones de hallazgos de ZAP medios o altos y de puertos distintos de 80 y 443 | [`justificaciones.md`](justificaciones.md) | Se llena a mano después de cada ejecución de ZAP y `nmap` | R25.2, R25.4 | 3 entradas de ZAP (Z-1 a Z-3), sin entradas de puertos |
| Resultados de CA-01 a CA-08 desde la URL pública | [`ca-01/`](ca-01/README.md) a [`ca-08/`](ca-08/README.md) | Registro por criterio (tabla de la sección 2) | R25.5 | Ver sección 2 |

Si se ejecuta ZAP o `nmap` más de una vez, la fila apunta al archivo de la última ejecución y los anteriores se conservan como historial.

## 2. Resultados de CA-01 a CA-08 (R25.5)

Cada carpeta tiene un `README.md` con el registro del criterio: URL pública usada, fecha y hora, resultado (`aprobado` o `fallido`) y evidencia. La evidencia es una captura guardada en la misma carpeta o la marca de tiempo del fragmento del video en que se ejecuta el criterio; en ambos casos la URL pública debe verse en pantalla. No se exigen capturas por separado si el video cubre el criterio.

| Criterio | Enunciado (E1) | Registro | Resultado | Evidencia |
| --- | --- | --- | --- | --- |
| CA-01 | Al subir `init/01_schema.sql`, el usuario ve score y hallazgos en menos de 60 s. | [ca-01](ca-01/README.md) | `pendiente` | `<captura o mm:ss>` |
| CA-02 | Un script con `ALTER SYSTEM` se rechaza antes de ejecutarse. | [ca-02](ca-02/README.md) | `pendiente` | `<captura o mm:ss>` |
| CA-03 | El usuario B recibe `404` al pedir un análisis del usuario A. | [ca-03](ca-03/README.md) | `pendiente` | `<captura o mm:ss>` |
| CA-04 | `password_hash` inicia con `$argon2id$` y no contiene la contraseña. | [ca-04](ca-04/README.md) | `pendiente` | `<captura o mm:ss>` |
| CA-05 | Tras 5 intentos fallidos, el sexto se bloquea 15 min. | [ca-05](ca-05/README.md) | `pendiente` | `<captura o mm:ss>` |
| CA-06 | `/api/full-scan` sin cookie responde `401`. | [ca-06](ca-06/README.md) | `pendiente` | `<captura o mm:ss>` |
| CA-07 | El link público abre el login y solo responden los puertos 80 y 443. | [ca-07](ca-07/README.md) | `pendiente` | `<captura o mm:ss>` y `nmap-<fecha>.txt` |
| CA-08 | En la instancia funcionan registro, login, análisis y cierre de sesión. | [ca-08](ca-08/README.md) | `pendiente` | `<capturas o mm:ss>` |

Regla: el resultado de esta tabla copia el del `README.md` de cada carpeta. Un criterio `fallido` se corrige y se repite; la fila conserva la fecha de la ejecución que vale.

Nombre de las capturas: `ca-0N-<paso opcional>-<AAAAMMDDTHHMMZ>.png`, en la carpeta del criterio.

## 3. Otra evidencia del despliegue

Estos archivos sustentan otros criterios del E2 (CA-09 a CA-26). No forman parte del contenido mínimo de R25.6, pero se citan desde el runbook y el registro de decisiones.

| Carpeta | Contenido | Criterios |
| --- | --- | --- |
| [`fase2/`](fase2/) | `verificacion-iam.jsonl`: una línea JSON por comprobación (IAM, MFA, Security Group, IMDSv2, protección de terminación, cifrado, etiquetas, Elastic IP, certificado, cabeceras, swap, Volumen_Sandbox, costos, alarma y snapshots) | CA-12, CA-13, CA-15 a CA-26 |
| [`stack/`](stack/) | Change sets revisados, outputs del stack, AMI usada, eventos fallidos del primer intento y monitores y suscripciones de anomalías antes y después del despliegue | R29, CA-24 |
| [`instancia/`](instancia/) | Reglas de entrada del Security Group, volúmenes, etiquetas, snapshots previos a la prueba 4.9 y el primer `nmap` (`nmap-20261126T1928Z.txt`, solo 80 y 443 abiertos) | CA-12, CA-18, CA-20, CA-21 |
| [`despliegue/`](despliegue/) | `cert-navegador-20261126.png`: certificado de Let's Encrypt visto en el navegador | CA-23 |
| [`snapshots/`](snapshots/) | `verificacion-snapshots.jsonl`, registros de `manual_snapshot.sh` (estabilización y video), listados de snapshots, alarma de recuperación y prueba de recuperación de EC2 | CA-25, CA-26 |
| [`costos/`](costos/) | `verificacion-costos.jsonl`, presupuesto, notificaciones y destinatarios, monitores y suscripciones de anomalías, y la lista de secretos de Secrets Manager (R27) | CA-24, R27 |
| [`r26-3/`](r26-3/) | Verificación en navegador de R26.3 (HAR sin cookies, lista de solicitudes `/api/` y capturas) | R26.3 |
