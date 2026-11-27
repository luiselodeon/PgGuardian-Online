# CA-08: en la instancia funcionan registro, login, análisis y cierre de sesión

Trazabilidad: CA-08 (E1) · RF-01, RF-02, RF-03 · RF-08.2 · T-25 · Requirements 25.5 y 25.6.

**Criterio (E1):** en la instancia funcionan registro, login, análisis y cierre de sesión.

## Registro

Se llena al ejecutar el criterio desde la URL pública. Se reemplaza todo el texto entre `<...>`. Cada paso lleva su propio resultado; el criterio se aprueba solo si los cuatro pasos se aprueban.

| Campo | Valor |
| --- | --- |
| URL pública | `https://3-14-31-64.sslip.io` (output `AppDomain` del stack; confirmar antes de ejecutar) |
| Fecha y hora (UTC) | `<AAAA-MM-DDTHH:MM:SSZ>` |
| Ejecutó | `<nombre>` |
| Resultado | `pendiente` (cambiar a `aprobado` o `fallido`) |
| Tipo de evidencia | `<capturas o video>` |
| Observaciones | `<ninguna o detalle del fallo>` |

| Paso | Resultado | Evidencia (captura en esta carpeta o minuto del video) |
| --- | --- | --- |
| Registro | `<aprobado o fallido>` | `<ca-08-registro-AAAAMMDDTHHMMZ.png o mm:ss>` |
| Login | `<aprobado o fallido>` | `<ca-08-login-AAAAMMDDTHHMMZ.png o mm:ss>` |
| Análisis | `<aprobado o fallido>` | `<ca-08-analisis-AAAAMMDDTHHMMZ.png o mm:ss>` |
| Cierre de sesión | `<aprobado o fallido>` | `<ca-08-logout-AAAAMMDDTHHMMZ.png o mm:ss>` |

La URL pública debe verse en la barra de direcciones de cada captura o del fragmento del video (R25.5).

## Procedimiento

1. **Registro:** abrir la URL pública en una ventana privada y registrar una cuenta nueva. Aprobado si la aplicación entra con la cuenta nueva.
2. **Login:** cerrar sesión y volver a entrar con esa cuenta. Aprobado si se muestra la aplicación con la sesión iniciada.
3. **Análisis:** subir un script SQL válido (por ejemplo `init/01_schema.sql`). Aprobado si se muestran score y hallazgos, y el análisis aparece en el Historial.
4. **Cierre de sesión:** pulsar «Cerrar sesión» y luego abrir `https://<dominio>/api/auth/me`. Aprobado si vuelve la pantalla de login y `/api/auth/me` responde `401`.

**Aprobado** si los cuatro pasos se aprueban. **Fallido** si alguno falla.
