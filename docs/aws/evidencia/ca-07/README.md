# CA-07: el link público abre el login y solo responden 80 y 443

Trazabilidad: CA-07 (E1) · RF-03.1 a RF-03.4 · RF-08.2 · T-25 · Requirements 25.5 y 25.6. Relacionado con CA-18 (E2) y R25.3.

**Criterio (E1):** el link público abre el login y solo responden los puertos 80 y 443.

## Registro

Se llena al ejecutar el criterio desde la URL pública. Se reemplaza todo el texto entre `<...>`.

| Campo | Valor |
| --- | --- |
| URL pública | `https://3-14-31-64.sslip.io` (output `AppDomain` del stack; confirmar antes de ejecutar) |
| Elastic IP | `3.14.31.64` (output `PublicIp` del stack; confirmar antes de ejecutar) |
| Fecha y hora (UTC) | `<AAAA-MM-DDTHH:MM:SSZ>` |
| Ejecutó | `<nombre>` |
| Resultado | `pendiente` (cambiar a `aprobado` o `fallido`) |
| Tipo de evidencia | `<captura o video>` |
| Evidencia del login | `<ca-07-AAAAMMDDTHHMMZ.png en esta carpeta>` o `<video, minuto mm:ss a mm:ss>` |
| Evidencia de puertos | `<../nmap-AAAAMMDDTHHMMZ.txt>` (salida de `scripts/aws/run_nmap.sh`) |
| Puertos abiertos | `<lista que muestra nmap>` |
| Observaciones | `<ninguna o detalle del fallo>` |

La URL pública debe verse en la barra de direcciones de la captura o del fragmento del video (R25.5).

## Procedimiento

1. En una ventana privada, abrir la URL pública. Capturar la pantalla de login con la barra de direcciones, o anotar el minuto del video.
2. Ejecutar `bash scripts/aws/run_nmap.sh` (escanea TCP 1 a 65535 de la Elastic IP y guarda `docs/aws/evidencia/nmap-<AAAAMMDDTHHMMZ>.txt`). Anotar el archivo en el registro.
3. Si aparece un puerto abierto distinto de 80 y 443, cerrarlo y repetir el paso 2, o justificarlo en `../justificaciones.md` (R25.4).

Antecedente: `../instancia/nmap-20261126T1928Z.txt` (2026-11-26) muestra solo 80 y 443 abiertos. Ese escaneo usó `-p-` y no sustituye la salida de `run_nmap.sh` del Paquete_Evidencia.

**Aprobado** si la URL pública abre la pantalla de login sin advertencias de certificado y la salida de `nmap` muestra abiertos solo 80 y 443 (o cada puerto adicional está justificado). **Fallido** en cualquier otro caso.
