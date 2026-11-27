# CA-01: análisis de `init/01_schema.sql` en menos de 60 s

Trazabilidad: CA-01 (E1) · RF-01.1 a RF-01.5 · RF-08.2 · T-25 · Requirements 25.5 y 25.6.

**Criterio (E1):** al subir `init/01_schema.sql`, el usuario ve score y hallazgos en menos de 60 s.

## Registro

Se llena al ejecutar el criterio desde la URL pública. Se reemplaza todo el texto entre `<...>`.

| Campo | Valor |
| --- | --- |
| URL pública | `https://3-14-31-64.sslip.io` (output `AppDomain` del stack; confirmar antes de ejecutar) |
| Fecha y hora (UTC) | `<AAAA-MM-DDTHH:MM:SSZ>` |
| Ejecutó | `<nombre>` |
| Resultado | `pendiente` (cambiar a `aprobado` o `fallido`) |
| Tipo de evidencia | `<captura o video>` |
| Evidencia | `<ca-01-AAAAMMDDTHHMMZ.png en esta carpeta>` o `<video, minuto mm:ss a mm:ss>` |
| Dato medido | `<segundos desde «Analizar» hasta ver score y hallazgos>` |
| Observaciones | `<ninguna o detalle del fallo>` |

La URL pública debe verse en la barra de direcciones de la captura o del fragmento del video (R25.5).

## Procedimiento

1. Abrir la URL pública e iniciar sesión con una cuenta de prueba.
2. En la pantalla de análisis, subir `init/01_schema.sql` del repositorio.
3. Pulsar el botón de análisis y medir el tiempo hasta que aparecen el score y la lista de hallazgos.
4. Capturar la pantalla con el score, los hallazgos y la barra de direcciones, o anotar el minuto del video.

**Aprobado** si el score y los hallazgos aparecen en menos de 60 s. **Fallido** si tarda 60 s o más, si el análisis termina en error o si no se muestran score y hallazgos.
