# CA-06: `/api/full-scan` sin cookie responde 401

Trazabilidad: CA-06 (E1) · RF-02.6 · RF-08.2 · T-25 · Requirements 25.5 y 25.6.

**Criterio (E1):** `/api/full-scan` sin cookie responde `401`.

Antecedente: en el despliegue este endpoint respondía `500` sin cookie; la corrección está registrada en `docs/aws/decision-log.md`, entrada «CA-06: /api/full-scan devolvía 500 sin cookie».

## Registro

Se llena al ejecutar el criterio desde la URL pública. Se reemplaza todo el texto entre `<...>`.

| Campo | Valor |
| --- | --- |
| URL pública | `https://3-14-31-64.sslip.io` (output `AppDomain` del stack; confirmar antes de ejecutar) |
| Fecha y hora (UTC) | `<AAAA-MM-DDTHH:MM:SSZ>` |
| Ejecutó | `<nombre>` |
| Resultado | `pendiente` (cambiar a `aprobado` o `fallido`) |
| Tipo de evidencia | `<captura o video>` |
| Evidencia | `<ca-06-AAAAMMDDTHHMMZ.png en esta carpeta>` o `<video, minuto mm:ss a mm:ss>` |
| Respuesta | `<código HTTP y cuerpo>` |
| Observaciones | `<ninguna o detalle del fallo>` |

La URL pública debe verse en la captura o en el fragmento del video: en la barra de direcciones o en el comando `curl` (R25.5).

## Procedimiento

Una de las dos variantes:

- **Terminal:** `curl -i https://<dominio>/api/full-scan` (sin `-b` ni cabecera `Cookie`). Capturar el comando y la respuesta.
- **Navegador:** abrir `https://<dominio>/api/full-scan` en una ventana privada sin sesión iniciada. Capturar la respuesta con la barra de direcciones.

**Aprobado** si la respuesta es `401`. **Fallido** con cualquier otro código (en particular `200` o `500`).
