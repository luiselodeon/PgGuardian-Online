# CA-04: `password_hash` inicia con `$argon2id$` y no contiene la contraseña

Trazabilidad: CA-04 (E1) · RF-02.3 · RF-08.2 · T-25 · Requirements 25.5 y 25.6.

**Criterio (E1):** `password_hash` inicia con `$argon2id$` y no contiene la contraseña.

## Registro

Se llena al ejecutar el criterio desde la URL pública. Se reemplaza todo el texto entre `<...>`.

| Campo | Valor |
| --- | --- |
| URL pública | `https://3-14-31-64.sslip.io` (output `AppDomain` del stack; confirmar antes de ejecutar) |
| Fecha y hora (UTC) | `<AAAA-MM-DDTHH:MM:SSZ>` |
| Ejecutó | `<nombre>` |
| Resultado | `pendiente` (cambiar a `aprobado` o `fallido`) |
| Tipo de evidencia | `<captura o video>` |
| Evidencia | `<ca-04-registro-AAAAMMDDTHHMMZ.png y ca-04-consulta-AAAAMMDDTHHMMZ.png en esta carpeta>` o `<video, minuto mm:ss a mm:ss>` |
| Correo de la cuenta de prueba | `<correo>` |
| Salida de la consulta | `<argon2id = t, sin_texto_plano = t>` |
| Observaciones | `<ninguna o detalle del fallo>` |

La URL pública debe verse en la captura o el fragmento del registro (R25.5). La consulta a `app_db` se hace en la Instancia y no pasa por la URL pública; su captura acompaña a la del registro.

## Procedimiento

1. Abrir la URL pública y registrar una cuenta de prueba nueva con una contraseña de prueba que no se use en ningún otro sitio. Capturar la pantalla con la barra de direcciones.
2. Abrir una sesión en la Instancia con Session Manager (`aws ssm start-session --target <InstanceId>`).
3. Ejecutar la consulta, reemplazando el correo y la contraseña de prueba. El heredoc entre comillas evita que la shell expanda `$argon2id$`:

   ```bash
   sudo docker exec -i pgguardian_appdb_prod sh -c 'psql -U "$POSTGRES_USER" -d "$POSTGRES_DB"' <<'SQL'
   SELECT email,
          left(password_hash, 10)                         AS prefijo,
          password_hash LIKE '$argon2id$%'                AS argon2id,
          position('<contraseña de prueba>' IN password_hash) = 0 AS sin_texto_plano
   FROM users
   WHERE email = '<correo de prueba>';
   SQL
   ```

4. Capturar la salida. No capturar el hash completo.

**Aprobado** si `argon2id` y `sin_texto_plano` son `t`. **Fallido** si alguno es `f` o la fila no existe.
