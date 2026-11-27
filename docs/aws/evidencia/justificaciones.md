# Justificaciones del Paquete_Evidencia

Trazabilidad: RF-08.2 · CA-27 · Requirements 25.2, 25.4 y 25.6.

Este archivo reúne las justificaciones escritas que exige el Paquete_Evidencia:

- **Sección 1:** cada hallazgo de riesgo medio o alto que siga en el último reporte de ZAP baseline (`scripts/aws/run_zap.sh`) y no se haya corregido (R25.2).
- **Sección 2:** cada puerto abierto distinto de 80 y 443 que muestre la salida de `nmap` (`scripts/aws/run_nmap.sh`) y no se haya cerrado (R25.4).

Reglas:

1. Primero se intenta corregir: un hallazgo corregido se comprueba con un nuevo reporte de ZAP, y un puerto cerrado con una nueva salida de `nmap`. Lo corregido no se justifica aquí.
2. Cada entrada cita el archivo de evidencia exacto (`zap-baseline-<AAAAMMDDTHHMMZ>.html` o `nmap-<fecha>.txt`) en el que aparece.
3. Cada entrada indica la **causa** y la **razón de aceptación del riesgo**. Una entrada sin alguno de los dos campos no cuenta como justificada.
4. Si una sección no tiene entradas, se deja la línea «Sin entradas» con el archivo de evidencia revisado.
5. Al copiar la plantilla de una entrada, se reemplaza todo el texto entre `<...>`.

## Reportes revisados

| Herramienta | Archivo de evidencia | Fecha y hora (UTC) | Objetivo | Resultado |
| --- | --- | --- | --- | --- |
| ZAP baseline | `zap-baseline-20261127T0321Z.html` (y `.json`) | 2026-11-27T03:22:00Z | https://3-14-31-64.sslip.io | altos=0 medios=3 bajos=4 informativos=4 (11 alertas en 8 reglas: 0 FAIL, 8 WARN, 60 PASS) |
| nmap | `<nmap-fecha.txt>` | `<AAAA-MM-DDTHH:MM:SSZ>` | `<Elastic IP>` | `<puertos abiertos>` |

## 1. Hallazgos de ZAP de riesgo medio o alto (R25.2)

Reporte revisado: `zap-baseline-20261127T0321Z.html`. Resultado: 0 FAIL, 8 WARN, 60 PASS. Los hallazgos de riesgo medio quedan justificados abajo; los de riesgo bajo e informativo no exigen justificación (R25.2) y se listan al final como «documentados sin acción».

### Z-1. CSP: Failure to Define Directive with No Fallback (pluginid 10055)
| Campo | Valor |
| --- | --- |
| Riesgo | Medio (confianza Alta) |
| Reporte | `zap-baseline-20261127T0321Z.html` |
| URL afectadas | https://3-14-31-64.sslip.io, `/robots.txt`, `/sitemap.xml` y `/api%60,er=null;function` (4 instancias) |
| Causa | La CSP del `Caddyfile` no define `form-action` ni `base-uri`, y estas directivas no heredan de `default-src`. |
| Intento de corrección | No se aplicó. Corregirlo exige cambiar el `Caddyfile` y volver a verificar CA-13, que compara la CSP exacta. |
| Razón de aceptación del riesgo | La app es una SPA que no envía formularios HTML a otros orígenes (todo va por `fetch` a `/api` del mismo origen) y no hay contenido de usuario que pueda insertar una etiqueta `<base>`. |
| Mitigación existente | `default-src 'self'` y `frame-ancestors 'none'`. Mejora futura: añadir `form-action 'self'; base-uri 'self'`. |
| Aprobado por | Chus Avila, 2026-11-26 |

### Z-2. Sub Resource Integrity Attribute Missing (pluginid 90003)
| Campo | Valor |
| --- | --- |
| Riesgo | Medio (confianza Alta) |
| Reporte | `zap-baseline-20261127T0321Z.html` |
| URL afectadas | https://3-14-31-64.sslip.io, `/robots.txt`, `/sitemap.xml` y `/api%60,er=null;function` (4 instancias; todas cargan `frontend/index.html`) |
| Causa | El recurso sin atributo `integrity` es la hoja de estilos de Google Fonts (`https://fonts.googleapis.com/css2?family=Inter...`) en `frontend/index.html`. Google sirve un CSS distinto según el user-agent, así que un hash SRI fijo no es viable. |
| Intento de corrección | No aplicado: un hash fijo rompería la carga de las fuentes en algunos navegadores. |
| Razón de aceptación del riesgo | El origen es Google Fonts y la CSP limita `style-src` a `'self'`, `'unsafe-inline'` y `https://fonts.googleapis.com`, y `font-src` a `'self'` y `https://fonts.gstatic.com`. Ningún otro origen externo puede cargar estilos ni fuentes. |
| Mitigación existente | CSP con `style-src` y `font-src` restringidos. Mejora futura: autoalojar las fuentes. |
| Aprobado por | Chus Avila, 2026-11-26 |

### Z-3. CSP: style-src unsafe-inline (pluginid 10055)
El reporte lista esta alerta como segunda de la regla 10055, aparte de Z-1. Se justifica aquí para que ningún hallazgo medio quede sin entrada.

| Campo | Valor |
| --- | --- |
| Riesgo | Medio (confianza Alta) |
| Reporte | `zap-baseline-20261127T0321Z.html` |
| URL afectadas | https://3-14-31-64.sslip.io, `/robots.txt`, `/sitemap.xml` y `/api%60,er=null;function` (4 instancias) |
| Causa | `style-src` incluye `'unsafe-inline'` desde la CSP inicial (R5.3). Los componentes React aplican atributos `style={{...}}` (ver `docs/aws/csp-verificacion.md`). |
| Intento de corrección | No aplicado: quitarlo bloquearía los estilos en línea de la interfaz. |
| Razón de aceptación del riesgo | `'unsafe-inline'` solo está en `style-src`; `script-src` hereda `default-src 'self'` sin `'unsafe-inline'` ni `'unsafe-eval'`, así que no permite scripts en línea. |
| Mitigación existente | `default-src 'self'` sin ejecución de scripts en línea. Mejora futura: migrar a estilos con nonce o clases. |
| Aprobado por | Chus Avila, 2026-11-26 |

### Hallazgos de riesgo bajo e informativo: documentados sin acción
Archivo: `zap-baseline-20261127T0321Z.html`. No son de riesgo medio ni alto, por lo que no requieren justificación de aceptación (R25.2).

| pluginid | Nombre en el reporte | Riesgo | Instancias |
| --- | --- | --- | --- |
| 10063 | Permissions Policy Header Not Set | Bajo | 5 |
| 90004 | Cross-Origin-Embedder-Policy Header Missing or Invalid (COEP) | Bajo | 3 |
| 90004 | Cross-Origin-Opener-Policy Header Missing or Invalid (COOP) | Bajo | 3 |
| 90004 | Cross-Origin-Resource-Policy Header Missing or Invalid (CORP) | Bajo | 4 |
| 10015 | Re-examine Cache-control Directives | Informativo | 4 |
| 10027 | Information Disclosure - Suspicious Comments | Informativo | 1 |
| 10049 | Storable and Cacheable Content | Informativo | 5 |
| 10109 | Modern Web Application | Informativo | 4 |

La regla 90004 (aislamiento insuficiente frente a Spectre) agrupa tres alertas, COEP, COOP y CORP, por eso el reporte tiene 11 alertas en 8 reglas.

La URL `/api%60,er=null;function` no es un endpoint real: es un artefacto del spider de ZAP al leer el JavaScript minificado (`/assets/index-X2-sYaIb.js`).

<!--
Plantilla de una entrada (copiar por cada hallazgo restante y borrar la línea «Sin entradas»):

### Z-<n>. <nombre del hallazgo en ZAP> (pluginid <id>)

| Campo | Valor |
| --- | --- |
| Riesgo | <Alto o Medio> (confianza <Alta, Media o Baja>) |
| Reporte | `zap-baseline-<AAAAMMDDTHHMMZ>.html` |
| URL afectadas | <URL o patrón, p. ej. https://a-b-c-d.sslip.io/assets/*> |
| Causa | <por qué aparece: componente, cabecera o comportamiento que lo produce> |
| Intento de corrección | <qué se probó y por qué no se aplicó, o «no aplica»> |
| Razón de aceptación del riesgo | <por qué el riesgo es aceptable en este despliegue> |
| Mitigación existente | <control que reduce el impacto, o «ninguna»> |
| Aprobado por | <nombre>, <AAAA-MM-DD> |
-->

## 2. Puertos abiertos distintos de 80 y 443 (R25.4)

Sin entradas. Salida revisada: `<nmap-fecha.txt>`.

<!--
Plantilla de una entrada (copiar por cada puerto adicional abierto y borrar la línea «Sin entradas»):

### P-<n>. Puerto <número>/tcp (<servicio que informa nmap>)

| Campo | Valor |
| --- | --- |
| Salida de nmap | `nmap-<fecha>.txt` |
| Estado en nmap | <open> |
| Proceso o servicio que lo abre | <contenedor, demonio o regla del Security Group> |
| Causa | <por qué está abierto> |
| Intento de cierre | <qué se probó y por qué no se cerró, o «no aplica»> |
| Razón de aceptación del riesgo | <por qué mantenerlo abierto es aceptable> |
| Mitigación existente | <control que reduce el impacto, o «ninguna»> |
| Aprobado por | <nombre>, <AAAA-MM-DD> |
-->
