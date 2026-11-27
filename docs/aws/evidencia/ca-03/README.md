# CA-03: el usuario B recibe 404 al pedir un análisis del usuario A

Trazabilidad: CA-03 (E1) · RF-01.8 · RF-08.2 · T-25 · Requirements 25.5 y 25.6.

**Criterio (E1):** el usuario B recibe `404` al pedir un análisis del usuario A.

## Registro

Se llena al ejecutar el criterio desde la URL pública. Se reemplaza todo el texto entre `<...>`.

| Campo | Valor |
| --- | --- |
| URL pública | `https://3-14-31-64.sslip.io` (output `AppDomain` del stack; confirmar antes de ejecutar) |
| Fecha y hora (UTC) | `<AAAA-MM-DDTHH:MM:SSZ>` |
| Ejecutó | `<nombre>` |
| Resultado | `pendiente` (cambiar a `aprobado` o `fallido`) |
| Tipo de evidencia | `<captura o video>` |
| Evidencia | `<ca-03-AAAAMMDDTHHMMZ.png en esta carpeta>` o `<video, minuto mm:ss a mm:ss>` |
| ID del análisis de A | `<uuid>` |
| Respuesta a B | `<código HTTP y cuerpo>` |
| Observaciones | `<ninguna o detalle del fallo>` |

La URL pública debe verse en la barra de direcciones de la captura o del fragmento del video (R25.5).

## Procedimiento

1. En una ventana normal, iniciar sesión como usuario A, crear un análisis y copiar su ID (aparece en el Historial o en la respuesta de `GET /api/analyses`).
2. En una ventana privada, iniciar sesión como usuario B.
3. En la ventana de B, abrir `https://<dominio>/api/analyses/<id-de-A>`.
4. Capturar la respuesta junto con la barra de direcciones, o anotar el minuto del video.

**Aprobado** si B recibe `404` con `{"detail":"Análisis no encontrado."}`. **Fallido** si B recibe el análisis (`200`) o cualquier otro código.
