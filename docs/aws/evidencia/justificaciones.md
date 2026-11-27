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
| ZAP baseline | `<zap-baseline-AAAAMMDDTHHMMZ.html>` | `<AAAA-MM-DDTHH:MM:SSZ>` | `<https://a-b-c-d.sslip.io>` | `<altos=n medios=n bajos=n informativos=n>` |
| nmap | `<nmap-fecha.txt>` | `<AAAA-MM-DDTHH:MM:SSZ>` | `<Elastic IP>` | `<puertos abiertos>` |

## 1. Hallazgos de ZAP de riesgo medio o alto (R25.2)

Sin entradas. Reporte revisado: `<zap-baseline-AAAAMMDDTHHMMZ.html>`.

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
