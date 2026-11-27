# CA-05: tras 5 intentos fallidos, el sexto se bloquea 15 min

Trazabilidad: CA-05 (E1) · RF-02.4 · RF-08.2 · T-25 · Requirements 25.5 y 25.6.

**Criterio (E1):** tras 5 intentos fallidos, el sexto se bloquea 15 min.

## Registro

Se llena al ejecutar el criterio desde la URL pública. Se reemplaza todo el texto entre `<...>`.

| Campo | Valor |
| --- | --- |
| URL pública | `https://3-14-31-64.sslip.io` (output `AppDomain` del stack; confirmar antes de ejecutar) |
| Fecha y hora (UTC) | `<AAAA-MM-DDTHH:MM:SSZ>` |
| Ejecutó | `<nombre>` |
| Resultado | `pendiente` (cambiar a `aprobado` o `fallido`) |
| Tipo de evidencia | `<captura o video>` |
| Evidencia | `<ca-05-AAAAMMDDTHHMMZ.png en esta carpeta>` o `<video, minuto mm:ss a mm:ss>` |
| Mensaje del sexto intento | `<texto mostrado; código 429>` |
| Observaciones | `<ninguna o detalle del fallo>` |

La URL pública debe verse en la barra de direcciones de la captura o del fragmento del video (R25.5).

## Procedimiento

1. Usar una cuenta de prueba dedicada; queda bloqueada 15 min y no debe ser la que se usa en el resto del video.
2. Abrir la URL pública y, en el login, enviar 5 veces la contraseña incorrecta.
3. En el sexto intento, enviar la contraseña **correcta**.
4. Capturar el mensaje del sexto intento junto con la barra de direcciones, o anotar el minuto del video. En las herramientas de desarrollo (pestaña Red) se ve el `429` de `POST /api/auth/login`.

**Aprobado** si el sexto intento responde `429` con el mensaje «Cuenta bloqueada temporalmente por demasiados intentos fallidos» aunque la contraseña sea correcta. **Fallido** si el sexto intento inicia sesión o el mensaje no corresponde al bloqueo de la cuenta (por ejemplo, un `429` del límite general de solicitudes).
