# CA-02: un script con `ALTER SYSTEM` se rechaza antes de ejecutarse

Trazabilidad: CA-02 (E1) · RF-01.3 · RF-08.2 · T-25 · Requirements 25.5 y 25.6.

**Criterio (E1):** un script con `ALTER SYSTEM` se rechaza antes de ejecutarse.

## Registro

Se llena al ejecutar el criterio desde la URL pública. Se reemplaza todo el texto entre `<...>`.

| Campo | Valor |
| --- | --- |
| URL pública | `https://3-14-31-64.sslip.io` (output `AppDomain` del stack; confirmar antes de ejecutar) |
| Fecha y hora (UTC) | `<AAAA-MM-DDTHH:MM:SSZ>` |
| Ejecutó | `<nombre>` |
| Resultado | `pendiente` (cambiar a `aprobado` o `fallido`) |
| Tipo de evidencia | `<captura o video>` |
| Evidencia | `<ca-02-AAAAMMDDTHHMMZ.png en esta carpeta>` o `<video, minuto mm:ss a mm:ss>` |
| Mensaje mostrado | `<texto del error de validación>` |
| Observaciones | `<ninguna o detalle del fallo>` |

La URL pública debe verse en la barra de direcciones de la captura o del fragmento del video (R25.5).

## Procedimiento

1. Crear un archivo local `alter_system.sql` con una sola línea: `ALTER SYSTEM SET work_mem = '64MB';`
2. Abrir la URL pública, iniciar sesión y subir `alter_system.sql` en la pantalla de análisis.
3. Capturar el mensaje de rechazo junto con la barra de direcciones, o anotar el minuto del video.
4. Abrir el Historial y comprobar que no se creó un análisis nuevo con ese archivo.

**Aprobado** si la aplicación rechaza el script con un error de validación y no aparece un análisis nuevo. **Fallido** si el script llega a ejecutarse o si se crea un análisis con resultados.
