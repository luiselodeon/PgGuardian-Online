# Runbook de despliegue y verificación en AWS (Entregable 2)

Trazabilidad: componente C14 del diseño · Requirements 8 a 23 y 29 · Tareas T-09 a T-22 y T-27.

Este documento reúne, en un solo lugar, los pasos manuales y los comandos de verificación del despliegue de PgGuardian en AWS. Cada sección indica qué criterio verifica, qué comandos ejecutar y qué resultado se espera. La infraestructura la crea la plantilla `infra/cloudformation/pgguardian.yaml` (stack `pgguardian`); lo que la plantilla no cubre lo hacen los scripts de `scripts/aws/`.

## 0. Uso del runbook

### 0.1 Dónde se ejecutan los comandos

- Todos los comandos `aws` se ejecutan desde **AWS CloudShell**, con la sesión de un Usuario_IAM autenticado con MFA. No se crean ni se guardan access keys en ningún equipo (R9.4).
- Los comandos que deben correr dentro de la instancia (secciones host y despliegue) se ejecutan en una sesión de **Session Manager**, nunca por SSH.
- Las verificaciones solo leen el estado de la cuenta y de los recursos. Si un comando modifica algo (p. ej. una prueba de reinicio), la sección lo indica de forma explícita.

### 0.2 Formato «Resultado de verificación»

Cada verificación se anota con el mismo formato que usa `scripts/verify_phase1` en la Fase 1: una línea JSON por criterio, que se guarda en el paquete de evidencia (`docs/aws/evidencia/`, R25).

```json
{ "criterio": "CA-15", "requisito": "R8", "estado": "aprobado|no_aprobado|no_verificable", "detalle": "..." }
```

| Campo | Contenido |
| --- | --- |
| `criterio` | Criterio de aceptación verificado (`CA-15`, `CA-16`, ...) |
| `requisito` | Requirement de `requirements.md` (`R8`, `R9`, ...) |
| `estado` | `aprobado`: se cumplen todas las condiciones. `no_aprobado`: el comando respondió y al menos una condición no se cumple. `no_verificable`: el comando falló o no devolvió algún valor necesario. |
| `detalle` | Valores observados; en `no_aprobado`, la condición que falló; en `no_verificable`, la causa del error |

Reglas comunes:

- Un criterio solo se anota como `aprobado` si se observaron **todos** los valores esperados. Un valor ausente nunca cuenta como cumplido.
- Ante `no_aprobado` o `no_verificable`, se corrige la causa y se repite la verificación completa de esa sección; la línea anterior se conserva en la evidencia.
- Junto a cada línea se guarda la salida del comando (o una captura de pantalla en los pasos manuales), con fecha y nombre de quien la ejecutó.

## 1. Raíz/IAM

### 1.1 Cuenta raíz (T-09 · RF-05.1 · CA-15 · R8)

Condiciones que debe cumplir la Cuenta_Raiz mientras la cuenta esté en operación:

| Condición | Requisito | Cómo se verifica |
| --- | --- | --- |
| Al menos 1 dispositivo MFA activo en la cuenta raíz | R8.1, R8.4 | `AccountMFAEnabled=1` en `get-account-summary` (1.1.3) |
| 0 access keys de la cuenta raíz, activas o inactivas | R8.2, R8.4 | `AccountAccessKeysPresent=0` en `get-account-summary` (1.1.3) |
| Acceso de usuarios y roles IAM a la información de facturación activado | R8.3 | Revisión manual en la consola (1.1.2) |

#### 1.1.1 Paso manual: MFA de la cuenta raíz

Lo hace el responsable de la cuenta, una sola vez, iniciando sesión como usuario raíz.

1. Iniciar sesión en <https://console.aws.amazon.com/> con **Root user** (correo de la cuenta y contraseña).
2. Abrir el menú de la cuenta (arriba a la derecha) → **Security credentials**.
3. En **Multi-factor authentication (MFA)**, elegir **Assign MFA device**.
4. Escribir un nombre para el dispositivo (p. ej. `root-pgguardian`), elegir el tipo (aplicación autenticadora, llave de seguridad o token físico) y seguir el asistente. Con una aplicación autenticadora: escanear el código QR e introducir dos códigos consecutivos.
5. Confirmar que el dispositivo aparece en la lista de MFA.
6. En la misma página, en **Access keys**, confirmar que la lista está vacía. Si hay alguna clave (activa o inactiva), desactivarla y eliminarla; la cuenta raíz no debe tener access keys.
7. Cerrar sesión y volver a entrar como usuario raíz para comprobar que la consola pide el segundo factor.
8. Guardar en la evidencia una captura de **Security credentials** con el dispositivo MFA asignado y la lista de access keys vacía (sin mostrar el código QR ni la clave secreta del MFA).

Los pasos 6 y 7 son la corrección de la cuenta. La verificación de 1.1.3 no los ejecuta.

#### 1.1.2 Paso manual: acceso IAM a la información de facturación

Por defecto, solo el usuario raíz ve la facturación, aunque un Usuario_IAM tenga `AdministratorAccess`. El Equipo necesita este acceso para revisar el presupuesto y Cost Anomaly Detection (sección 7).

1. Iniciar sesión como usuario raíz (con MFA, paso 1.1.1).
2. Abrir el menú de la cuenta → **Account**.
3. Ir a **IAM user and role access to Billing information** y elegir **Edit**.
4. Marcar **Activate IAM Access** y elegir **Update**.
5. Comprobar que la sección muestra **IAM user/role access to billing information is activated**.
6. Guardar una captura de esa sección en la evidencia.

Verificación (R8.3): con un Usuario_IAM del grupo `PgG-Admins` y MFA autenticado, abrir **Billing and Cost Management**. Se aprueba si la página carga los datos de facturación sin aviso de acceso denegado. Esta condición no tiene comando de consulta en la CLI, así que se registra a partir de la captura del paso 5 y de esta comprobación:

```json
{ "criterio": "CA-15", "requisito": "R8.3", "estado": "aprobado", "detalle": "IAM access to billing activado (captura <archivo>); <usuario> abre Billing and Cost Management sin acceso denegado" }
```

#### 1.1.3 Verificación con `aws iam get-account-summary`

Se ejecuta en CloudShell. Solo usa `iam:GetAccountSummary`, que es de lectura: la verificación no modifica la cuenta (R8.5). Si el resultado es `no_aprobado`, la corrección se hace a mano con el paso 1.1.1, nunca desde este bloque.

Consulta directa, para guardar la salida en la evidencia:

```bash
aws iam get-account-summary \
  --query 'SummaryMap.{AccountMFAEnabled: AccountMFAEnabled, AccountAccessKeysPresent: AccountAccessKeysPresent}' \
  --output json
```

Resultado esperado:

```json
{
    "AccountMFAEnabled": 1,
    "AccountAccessKeysPresent": 0
}
```

Evaluación automática del criterio. Pegar el bloque completo en CloudShell; imprime una línea con el formato «Resultado de verificación» (usa `jq`, que CloudShell trae instalado):

```bash
(
  criterio="CA-15"; requisito="R8"
  if ! salida=$(aws iam get-account-summary \
        --query 'SummaryMap.[AccountMFAEnabled, AccountAccessKeysPresent]' \
        --output text 2>&1); then
    estado="no_verificable"
    detalle="falló aws iam get-account-summary: $(echo "$salida" | tr '\n' ' ')"
  else
    read -r mfa claves <<< "$salida"
    entero='^[0-9]+$'
    if ! [[ "$mfa" =~ $entero ]] || ! [[ "$claves" =~ $entero ]]; then
      estado="no_verificable"
      detalle="la respuesta no trae ambos valores: AccountMFAEnabled=${mfa:-ausente}, AccountAccessKeysPresent=${claves:-ausente}"
    else
      fallos=()
      [ "$mfa" -ne 1 ] && fallos+=("AccountMFAEnabled=$mfa (se esperaba 1)")
      [ "$claves" -ne 0 ] && fallos+=("AccountAccessKeysPresent=$claves (se esperaba 0)")
      if [ ${#fallos[@]} -eq 0 ]; then
        estado="aprobado"
        detalle="AccountMFAEnabled=1, AccountAccessKeysPresent=0"
      else
        estado="no_aprobado"
        detalle="no conforme: ${fallos[0]}${fallos[1]:+; ${fallos[1]}}"
      fi
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Cómo se interpreta:

| Salida de la consulta | `estado` | `detalle` | Requisito |
| --- | --- | --- | --- |
| `AccountMFAEnabled=1` y `AccountAccessKeysPresent=0` | `aprobado` | Ambos valores observados | R8.4 |
| `AccountMFAEnabled=0` | `no_aprobado` | `AccountMFAEnabled=0 (se esperaba 1)` | R8.5 |
| `AccountAccessKeysPresent` distinto de 0 | `no_aprobado` | `AccountAccessKeysPresent=<n> (se esperaba 0)` | R8.5 |
| Ambas condiciones fallan | `no_aprobado` | Las dos condiciones, separadas por `;` | R8.5 |
| El comando falla (p. ej. `AccessDenied`, sin red, sesión expirada) | `no_verificable` | El mensaje de error de la CLI | R8.6 |
| Falta alguno de los dos valores (la CLI devuelve `None`) | `no_verificable` | Qué valor faltó | R8.6 |

Ejemplos de líneas:

```json
{"criterio":"CA-15","requisito":"R8","estado":"aprobado","detalle":"AccountMFAEnabled=1, AccountAccessKeysPresent=0"}
{"criterio":"CA-15","requisito":"R8","estado":"no_aprobado","detalle":"no conforme: AccountMFAEnabled=0 (se esperaba 1)"}
{"criterio":"CA-15","requisito":"R8","estado":"no_verificable","detalle":"falló aws iam get-account-summary: An error occurred (AccessDenied) when calling the GetAccountSummary operation: ..."}
```

CA-15 queda aprobado para la cuenta raíz solo si 1.1.2 y 1.1.3 están en `aprobado`. Un `no_aprobado` o `no_verificable` nunca se da por aprobado: se corrige con el paso manual o se resuelve la causa del error y se repite 1.1.3.

### 1.2 Usuarios IAM, grupo `PgG-Admins` y `Force_MFA` (T-10 · CA-15, CA-16 · R9)

Condiciones que deben cumplir los Usuario_IAM, el grupo `PgG-Admins` y la política `Force_MFA`:

| Condición | Requisito | Cómo se verifica |
| --- | --- | --- |
| Un Usuario_IAM por integrante del Equipo, con MFA activo y 0 access keys (activas o inactivas) | R9.1, R9.4, R9.5 | Reporte de credenciales (1.2.3) |
| Sin MFA autenticado, `Force_MFA` deniega todo salvo la autogestión de contraseña y MFA | R9.2 | Revisión de la definición de `Force_MFA` (1.2.4) |
| `PgG-Admins` tiene `AdministratorAccess` y `Force_MFA`, y todos los Usuario_IAM son miembros | R9.3 | `list-attached-group-policies`, `get-policy-version` y `get-group` (1.2.4) |
| Con MFA autenticado, una acción permitida por el grupo no responde `AccessDenied` | R9.6 | Acción de lectura desde CloudShell (1.2.5) |

La política está versionada en `docs/aws/iam/force-mfa-policy.json`. Tiene dos sentencias:

- `AllowSelfManagePasswordAndMFA` (`Allow`): permite al usuario cambiar su contraseña, leer su usuario y crear, activar, listar, consultar y sincronizar su propio MFA. Los recursos se limitan a `user/${aws:username}` y a los dispositivos MFA cuyo nombre empieza por `${aws:username}`.
- `DenyAllExceptSelfServiceWithoutMFA` (`Deny`): con `NotAction` y la condición `BoolIfExists: aws:MultiFactorAuthPresent = false`, deniega toda acción que no sea `iam:CreateVirtualMFADevice`, `iam:EnableMFADevice`, `iam:ListMFADevices`, `iam:GetMFADevice`, `iam:ListVirtualMFADevices`, `iam:ResyncMFADevice`, `iam:GetUser`, `iam:ChangePassword`, `iam:GetAccountPasswordPolicy` o `sts:GetSessionToken`. Con MFA autenticado, la condición no aplica y rigen los permisos de `AdministratorAccess`.

`iam:ChangePassword` e `iam:GetAccountPasswordPolicy` quedan fuera del `Deny` porque el usuario cambia su contraseña en el primer inicio de sesión, antes de tener MFA.

#### 1.2.1 Paso manual: política, grupo y usuarios (como raíz, una sola vez)

Lo hace el responsable de la cuenta, iniciando sesión como usuario raíz con MFA (paso 1.1.1). No hay script: la plantilla no crea estos elementos (R29.5).

1. **Crear la política administrada `Force_MFA`.**
   1. Abrir **IAM** → **Policies** → **Create policy**.
   2. Elegir la pestaña **JSON**, borrar el contenido de ejemplo y pegar el contenido completo de `docs/aws/iam/force-mfa-policy.json`.
   3. Confirmar que el editor no muestra errores de sintaxis ni avisos de seguridad y elegir **Next**.
   4. En **Policy name**, escribir `Force_MFA` (descripción sugerida: «Deniega todo a sesiones sin MFA, salvo autogestión de contraseña y MFA») y elegir **Create policy**.
2. **Crear el grupo `PgG-Admins`.**
   1. Abrir **IAM** → **User groups** → **Create group**.
   2. En **User group name**, escribir `PgG-Admins`.
   3. En **Attach permissions policies**, marcar `AdministratorAccess` y `Force_MFA` (para encontrar `Force_MFA`, filtrar por tipo **Customer managed**).
   4. Elegir **Create user group** y confirmar que el grupo muestra las dos políticas en la pestaña **Permissions**.
3. **Crear un usuario por integrante del Equipo.** Repetir para cada integrante:
   1. Abrir **IAM** → **Users** → **Create user**.
   2. Escribir el nombre del usuario (uno por persona, p. ej. `nombre.apellido`; no se comparten usuarios).
   3. Marcar **Provide user access to the AWS Management Console** y elegir **I want to create an IAM user**.
   4. En **Console password**, elegir **Autogenerated password** y dejar marcado **Users must create a new password at next sign-in**. La consola adjunta al usuario la política `IAMUserChangePassword`; se deja así.
   5. Elegir **Next**, después **Add user to group** y marcar `PgG-Admins`. No adjuntar políticas directas al usuario.
   6. Elegir **Next** → **Create user**.
   7. En la pantalla final, elegir **Show** o **Download .csv** y entregar la contraseña temporal y la URL de inicio de sesión (`https://<id-de-cuenta>.signin.aws.amazon.com/console`) al integrante por un canal privado. La contraseña no se guarda en el repositorio, en la evidencia ni en capturas de pantalla.
   8. No crear access keys: en la pestaña **Security credentials** del usuario, la sección **Access keys** debe quedar vacía (R9.1, R9.4).
4. **Cada integrante inicia sesión, cambia su contraseña y registra su MFA.**
   1. Entrar con la URL de inicio de sesión, el nombre de usuario y la contraseña temporal.
   2. Escribir una contraseña nueva cuando la consola la pida.
   3. Abrir el menú de la cuenta → **Security credentials** → **Assign MFA device**. Mientras no haya MFA, el resto de la consola muestra acceso denegado; es el efecto esperado de `Force_MFA`.
   4. Nombrar el dispositivo empezando por el propio nombre de usuario (p. ej. `nombre.apellido-app`), para que lo cubra la sentencia `Allow` de `Force_MFA`, y seguir el asistente (con una aplicación autenticadora: escanear el código QR e introducir dos códigos consecutivos).
   5. Cerrar sesión y volver a entrar: la consola debe pedir el código MFA y, tras introducirlo, mostrar los servicios sin acceso denegado.
   6. Guardar en la evidencia una captura de **Security credentials** con el dispositivo MFA asignado y la lista de access keys vacía (sin mostrar el código QR ni la clave secreta del MFA).
5. **A partir de aquí, la raíz no se usa para operar.** Toda la operación (stack, instancia, costos, snapshots) y todas las verificaciones se hacen con un Usuario_IAM autenticado con MFA, desde la consola o CloudShell. La raíz solo se usa para las tareas que AWS reserva a ella.

#### 1.2.2 Verificación: dónde y con quién

Los bloques de 1.2.3 a 1.2.5 se ejecutan en CloudShell, abierto desde la consola por un Usuario_IAM de `PgG-Admins` que inició sesión con MFA. Ningún bloque cambia usuarios, grupos, políticas ni credenciales. `generate-credential-report` solo genera el reporte de credenciales, que AWS guarda hasta 4 horas; no modifica la cuenta. Ningún comando lleva contraseñas.

CA-16 se verifica sin crear un usuario de prueba sin MFA: se revisa la definición de `Force_MFA` adjunta a `PgG-Admins` (1.2.4) y se comprueba que una acción permitida funciona con MFA (1.2.5). Esta desviación está registrada en el Registro_Decisiones (R24.6).

#### 1.2.3 Verificación con el reporte de credenciales (CA-15 · R9.1, R9.4, R9.5)

Consulta directa, para guardar la salida en la evidencia. El primer comando se repite hasta que devuelva `COMPLETE`:

```bash
aws iam generate-credential-report --query State --output text
aws iam get-credential-report --query Content --output text | base64 -d \
  | cut -d, -f1,4,8,9,10,14,15
```

Las columnas que muestra son `user`, `password_enabled`, `mfa_active`, `access_key_1_active`, `access_key_1_last_rotated`, `access_key_2_active` y `access_key_2_last_rotated`. Resultado esperado: en cada fila de Usuario_IAM, `mfa_active=true`, `access_key_1_active=false`, `access_key_2_active=false` y `N/A` en las dos columnas `last_rotated` (no existe ninguna clave, ni siquiera inactiva). La fila `<root_account>` se verifica en 1.1.3 y aquí se omite.

Evaluación automática del criterio. Pegar el bloque completo en CloudShell:

```bash
(
  criterio="CA-15"; requisito="R9.1, R9.4, R9.5"
  estado=""; detalle=""; est=""
  for intento in 1 2 3 4 5 6 7 8 9 10; do
    if ! est=$(aws iam generate-credential-report --query State --output text 2>&1); then
      estado="no_verificable"
      detalle="falló aws iam generate-credential-report: $(echo "$est" | tr '\n' ' ')"
      break
    fi
    [ "$est" = "COMPLETE" ] && break
    sleep 3
  done
  if [ -z "$estado" ] && [ "$est" != "COMPLETE" ]; then
    estado="no_verificable"
    detalle="el reporte de credenciales no llegó a COMPLETE (último estado: $est)"
  fi
  if [ -z "$estado" ]; then
    if ! b64=$(aws iam get-credential-report --query Content --output text 2>&1); then
      estado="no_verificable"
      detalle="falló aws iam get-credential-report: $(echo "$b64" | tr '\n' ' ')"
    elif ! csv=$(printf '%s' "$b64" | base64 -d 2>/dev/null) || [ -z "$csv" ]; then
      estado="no_verificable"
      detalle="no se pudo decodificar el reporte de credenciales"
    else
      resultado=$(printf '%s\n' "$csv" | awk -F, '
        { sub(/\r$/, "") }
        NR == 1 {
          for (i = 1; i <= NF; i++) col[$i] = i
          split("user mfa_active access_key_1_active access_key_2_active access_key_1_last_rotated access_key_2_last_rotated", req, " ")
          for (k in req) if (!(req[k] in col)) faltan = faltan " " req[k]
          next
        }
        faltan != "" { next }
        $col["user"] == "<root_account>" { next }
        {
          n++; f = ""
          if ($col["mfa_active"] != "true") f = f " mfa_active=" $col["mfa_active"]
          if ($col["access_key_1_active"] != "false") f = f " access_key_1_active=" $col["access_key_1_active"]
          if ($col["access_key_2_active"] != "false") f = f " access_key_2_active=" $col["access_key_2_active"]
          if ($col["access_key_1_last_rotated"] != "N/A") f = f " access_key_1 existe"
          if ($col["access_key_2_last_rotated"] != "N/A") f = f " access_key_2 existe"
          usuarios = usuarios (usuarios == "" ? "" : ",") $col["user"]
          if (f != "") { m++; malos = malos (malos == "" ? "" : ";") " " $col["user"] ":" f }
        }
        END {
          if (faltan != "") { print "COLUMNAS|" faltan; exit }
          printf "OK|%d|%d|%s|%s\n", n, m, usuarios, malos
        }')
      IFS='|' read -r tipo n m usuarios malos <<< "$resultado"
      if [ "$tipo" = "COLUMNAS" ]; then
        estado="no_verificable"
        detalle="el reporte no trae las columnas:${n}"
      elif [ "$tipo" != "OK" ]; then
        estado="no_verificable"
        detalle="no se pudo leer el reporte de credenciales"
      elif [ "$n" -eq 0 ]; then
        estado="no_aprobado"
        detalle="no conforme: el reporte no tiene ningún Usuario_IAM"
      elif [ "$m" -eq 0 ]; then
        estado="aprobado"
        detalle="$n de $n usuarios ($usuarios) con mfa_active=true, access_key_1_active=false, access_key_2_active=false y sin claves inactivas"
      else
        estado="no_aprobado"
        detalle="no conforme: $m de $n usuarios:$malos"
      fi
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Además del bloque, el responsable compara la lista de usuarios del `detalle` con la lista de integrantes del Equipo: debe haber exactamente un usuario por integrante, sin usuarios compartidos ni sobrantes (R9.1). Si no coincide, se anota `no_aprobado` con la diferencia en el `detalle`.

Cómo se interpreta:

| Salida del reporte | `estado` | `detalle` | Requisito |
| --- | --- | --- | --- |
| Todos los Usuario_IAM con `mfa_active=true`, ambas claves `false` y `N/A` en `last_rotated` | `aprobado` | Número y nombres de los usuarios | R9.1, R9.5 |
| Algún usuario con `mfa_active=false` | `no_aprobado` | Usuario y `mfa_active=false` | R9.5 |
| Algún usuario con una clave activa | `no_aprobado` | Usuario y `access_key_<n>_active=true` | R9.1, R9.4 |
| Algún usuario con una clave inactiva (`last_rotated` distinto de `N/A`) | `no_aprobado` | Usuario y `access_key_<n> existe` | R9.1 |
| El reporte no tiene Usuario_IAM | `no_aprobado` | Sin usuarios | R9.1 |
| Falla la generación o la descarga, o faltan columnas | `no_verificable` | El mensaje de error o las columnas que faltan | — |

Ejemplos de líneas:

```json
{"criterio":"CA-15","requisito":"R9.1, R9.4, R9.5","estado":"aprobado","detalle":"3 de 3 usuarios (ana.lopez,beto.ruiz,carla.diaz) con mfa_active=true, access_key_1_active=false, access_key_2_active=false y sin claves inactivas"}
{"criterio":"CA-15","requisito":"R9.1, R9.4, R9.5","estado":"no_aprobado","detalle":"no conforme: 1 de 3 usuarios: beto.ruiz: mfa_active=false"}
```

Corrección ante `no_aprobado`: el integrante afectado registra su MFA (paso 1.2.1, punto 4) o el responsable desactiva y elimina la access key desde **IAM** → **Users** → **Security credentials**. Después se repite 1.2.3 completa.

#### 1.2.4 Verificación de `PgG-Admins` y de la definición de `Force_MFA` (CA-16 · R9.2, R9.3)

Consulta directa, para guardar la salida en la evidencia:

```bash
aws iam list-attached-group-policies --group-name PgG-Admins --output table
FORCE_MFA_ARN=$(aws iam list-attached-group-policies --group-name PgG-Admins \
  --query "AttachedPolicies[?PolicyName=='Force_MFA'].PolicyArn" --output text)
aws iam get-policy-version --policy-arn "$FORCE_MFA_ARN" \
  --version-id "$(aws iam get-policy --policy-arn "$FORCE_MFA_ARN" --query Policy.DefaultVersionId --output text)" \
  --query PolicyVersion.Document --output json
aws iam get-group --group-name PgG-Admins --query 'Users[].UserName' --output table
```

Resultado esperado: el grupo tiene adjuntas `AdministratorAccess` (`arn:aws:iam::aws:policy/AdministratorAccess`) y `Force_MFA`; la versión por defecto de `Force_MFA` coincide con `docs/aws/iam/force-mfa-policy.json`; y todos los Usuario_IAM son miembros del grupo.

Evaluación automática del criterio. Pegar el bloque completo en CloudShell:

```bash
(
  criterio="CA-16"; requisito="R9.2, R9.3"
  grupo="PgG-Admins"
  esperadas='["iam:ChangePassword","iam:CreateVirtualMFADevice","iam:EnableMFADevice","iam:GetAccountPasswordPolicy","iam:GetMFADevice","iam:GetUser","iam:ListMFADevices","iam:ListVirtualMFADevices","iam:ResyncMFADevice","sts:GetSessionToken"]'
  estado=""; detalle=""; fallos=()
  err() { estado="no_verificable"; detalle="falló $1: $(echo "$2" | tr '\n' ' ')"; }
  if ! adjuntas=$(aws iam list-attached-group-policies --group-name "$grupo" --output json 2>&1); then
    err "aws iam list-attached-group-policies" "$adjuntas"
  else
    admin_arn=$(jq -r '.AttachedPolicies[] | select(.PolicyName == "AdministratorAccess") | .PolicyArn' <<< "$adjuntas")
    mfa_arn=$(jq -r '.AttachedPolicies[] | select(.PolicyName == "Force_MFA") | .PolicyArn' <<< "$adjuntas")
    [ "$admin_arn" = "arn:aws:iam::aws:policy/AdministratorAccess" ] || fallos+=("AdministratorAccess no adjunta a $grupo")
    if [ -z "$mfa_arn" ]; then
      fallos+=("Force_MFA no adjunta a $grupo")
    elif ! version=$(aws iam get-policy --policy-arn "$mfa_arn" --query Policy.DefaultVersionId --output text 2>&1); then
      err "aws iam get-policy" "$version"
    elif ! doc=$(aws iam get-policy-version --policy-arn "$mfa_arn" --version-id "$version" \
          --query PolicyVersion.Document --output json 2>&1); then
      err "aws iam get-policy-version" "$doc"
    elif ! revision=$(jq -r --argjson esp "$esperadas" '
        def lista: if type == "array" then . elif . == null then [] else [.] end;
        (.Statement | lista) as $s
        | [$s[] | select(.Effect == "Deny" and has("NotAction"))] as $deny
        | [$s[] | select(.Effect == "Allow")
                | select([.Resource | lista | .[] | select(contains("${aws:username}"))] | length > 0)] as $allow
        | (if ($deny | length) != 1 then "Force_MFA debe tener una sentencia Deny con NotAction (tiene \($deny | length))"
           else
             $deny[0]
             | (if (.NotAction | lista | sort) != ($esp | sort)
                  then "NotAction distinto del esperado: \(.NotAction | lista | sort | join(","))" else empty end),
               (if (.Resource | lista) != ["*"] then "Resource del Deny distinto de *" else empty end),
               (if (.Condition.BoolIfExists["aws:MultiFactorAuthPresent"] | tostring) != "false"
                  then "falta la condición BoolIfExists aws:MultiFactorAuthPresent=false" else empty end)
           end),
          (if ($allow | length) == 0 then "falta la sentencia Allow de autogestión limitada a ${aws:username}" else empty end)
      ' <<< "$doc" 2>&1); then
      err "la revisión con jq del documento de Force_MFA" "$revision"
    elif [ -n "$revision" ]; then
      mapfile -t fallos_doc <<< "$revision"
      fallos+=("${fallos_doc[@]}")
    fi
  fi
  if [ -z "$estado" ]; then
    if ! miembros=$(aws iam get-group --group-name "$grupo" --query 'Users[].UserName' --output text 2>&1); then
      err "aws iam get-group" "$miembros"
    elif ! usuarios=$(aws iam list-users --query 'Users[].UserName' --output text 2>&1); then
      err "aws iam list-users" "$usuarios"
    else
      fuera=$(comm -23 <(tr -s '\t ' '\n\n' <<< "$usuarios" | sed '/^$/d' | sort) \
                       <(tr -s '\t ' '\n\n' <<< "$miembros" | sed '/^$/d' | sort) | paste -sd, -)
      [ -n "$fuera" ] && fallos+=("usuarios fuera de $grupo: $fuera")
      [ -z "$(tr -d '[:space:]' <<< "$miembros")" ] && fallos+=("$grupo no tiene miembros")
    fi
  fi
  if [ -z "$estado" ]; then
    if [ ${#fallos[@]} -eq 0 ]; then
      estado="aprobado"
      detalle="$grupo con AdministratorAccess y Force_MFA ($mfa_arn, versión $version); Deny con NotAction de 10 acciones de autogestión y BoolIfExists aws:MultiFactorAuthPresent=false; Allow limitado a \${aws:username}; miembros: $(echo $miembros | tr ' ' ',')"
    else
      estado="no_aprobado"
      detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Cómo se interpreta:

| Salida de las consultas | `estado` | `detalle` | Requisito |
| --- | --- | --- | --- |
| Ambas políticas adjuntas, definición de `Force_MFA` conforme y todos los usuarios en el grupo | `aprobado` | ARN y versión de `Force_MFA`, miembros del grupo | R9.2, R9.3 |
| Falta `AdministratorAccess` o `Force_MFA` en el grupo | `no_aprobado` | La política que falta | R9.3 |
| El `NotAction` no es exactamente la lista de 10 acciones | `no_aprobado` | Las acciones encontradas | R9.2 |
| Falta la condición `BoolIfExists`, el `Resource` del `Deny` no es `*` o falta el `Allow` limitado a `${aws:username}` | `no_aprobado` | La condición que falló | R9.2 |
| Algún Usuario_IAM no es miembro de `PgG-Admins`, o el grupo está vacío | `no_aprobado` | Los usuarios fuera del grupo | R9.3 |
| Falla algún comando (p. ej. `AccessDenied`, sesión expirada) | `no_verificable` | El mensaje de error de la CLI | — |

Ejemplos de líneas:

```json
{"criterio":"CA-16","requisito":"R9.2, R9.3","estado":"aprobado","detalle":"PgG-Admins con AdministratorAccess y Force_MFA (arn:aws:iam::<cuenta>:policy/Force_MFA, versión v1); Deny con NotAction de 10 acciones de autogestión y BoolIfExists aws:MultiFactorAuthPresent=false; Allow limitado a ${aws:username}; miembros: ana.lopez,beto.ruiz,carla.diaz"}
{"criterio":"CA-16","requisito":"R9.2, R9.3","estado":"no_aprobado","detalle":"no conforme: NotAction distinto del esperado: iam:ChangePassword,iam:CreateVirtualMFADevice,iam:EnableMFADevice,iam:GetUser,iam:ListMFADevices,iam:ListVirtualMFADevices,iam:ResyncMFADevice,sts:GetSessionToken"}
```

Corrección ante `no_aprobado`: con un Usuario_IAM autenticado con MFA, en la consola, adjuntar la política que falta al grupo, agregar el usuario al grupo o crear una nueva versión de `Force_MFA` pegando de nuevo `docs/aws/iam/force-mfa-policy.json` (**Policies** → `Force_MFA` → **Edit** → **JSON** → **Save changes**). Después se repite 1.2.4 completa.

#### 1.2.5 Verificación de una acción permitida con MFA (CA-16 · R9.6)

Se ejecuta con cada Usuario_IAM, una vez, desde su propia sesión de CloudShell abierta tras iniciar sesión con MFA. Usa `sts:GetCallerIdentity` para registrar quién la ejecuta y `ec2:DescribeRegions`, una acción de lectura que `AdministratorAccess` permite y que `Force_MFA` deniega a una sesión sin MFA.

Consulta directa:

```bash
aws sts get-caller-identity --query Arn --output text
aws ec2 describe-regions --query 'length(Regions)' --output text
```

Resultado esperado: el ARN es de un usuario (`arn:aws:iam::<cuenta>:user/<usuario>`) y el segundo comando devuelve un número mayor que 0, sin `AccessDenied` ni `UnauthorizedOperation`.

Evaluación automática del criterio:

```bash
(
  criterio="CA-16"; requisito="R9.6"
  if ! quien=$(aws sts get-caller-identity --query Arn --output text 2>&1); then
    estado="no_verificable"
    detalle="falló aws sts get-caller-identity: $(echo "$quien" | tr '\n' ' ')"
  elif [[ "$quien" != arn:aws:iam::*:user/* ]]; then
    estado="no_verificable"
    detalle="la sesión no es de un Usuario_IAM: $quien"
  elif salida=$(aws ec2 describe-regions --query 'length(Regions)' --output text 2>&1) \
       && [[ "$salida" =~ ^[0-9]+$ ]] && [ "$salida" -gt 0 ]; then
    estado="aprobado"
    detalle="$quien ejecutó ec2:DescribeRegions con MFA sin AccessDenied ($salida regiones)"
  elif grep -qE 'AccessDenied|UnauthorizedOperation' <<< "$salida"; then
    estado="no_aprobado"
    detalle="no conforme: $quien recibió acceso denegado en ec2:DescribeRegions: $(echo "$salida" | tr '\n' ' ')"
  else
    estado="no_verificable"
    detalle="falló aws ec2 describe-regions: $(echo "$salida" | tr '\n' ' ')"
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Cómo se interpreta:

| Salida | `estado` | `detalle` | Requisito |
| --- | --- | --- | --- |
| `describe-regions` devuelve regiones | `aprobado` | ARN del usuario y número de regiones | R9.6 |
| `AccessDenied` o `UnauthorizedOperation` | `no_aprobado` | ARN del usuario y mensaje de error | R9.6 |
| La sesión no es de un Usuario_IAM (p. ej. raíz) o el comando falla por otra causa | `no_verificable` | La causa | — |

Un `no_aprobado` aquí indica casi siempre que la sesión no tiene MFA autenticado: cerrar sesión, volver a entrar con el código MFA, abrir CloudShell de nuevo y repetir 1.2.5.

CA-16 queda aprobado solo si 1.2.4 y 1.2.5 (para todos los usuarios) están en `aprobado`. CA-15 queda aprobado solo si 1.1 y 1.2.3 están en `aprobado`.

## 2. Stack

Trazabilidad: componente C15 del diseño · R29.2, R29.3, R29.6, R29.7, R29.8, R29.9, R29.10, R21.1 y R23.3 · Recursos de T-11 a T-15 y T-19 a T-21.

Esta sección crea y actualiza el stack `pgguardian` a partir de `infra/cloudformation/pgguardian.yaml`. Todo se ejecuta en CloudShell (`us-east-2`) con un Usuario_IAM de `PgG-Admins` autenticado con MFA. A diferencia de las demás secciones, varios pasos **modifican la cuenta**, y cada uno lo indica: 2.1.3 borra el monitor de anomalías por defecto, 2.1.6 crea el stack, 2.1.7 activa su protección, 2.3 lo actualiza, 2.4 lo borra tras un despliegue fallido y 2.5 lo borra cuando se retira el despliegue.

Condiciones que deben cumplirse:

| Condición | Requisito | Verificación |
| --- | --- | --- |
| La plantilla pasa `cfn-lint` y `validate-template` sin errores antes de cada despliegue | R29.6 | 2.1.1 |
| La AMI se obtiene una sola vez, antes del primer despliegue, y las actualizaciones la conservan con `UsePreviousValue=true` | R29.2 | 2.1.2, 2.3 |
| Antes del primer despliegue no queda ningún monitor de anomalías `DIMENSIONAL` en la cuenta | R21.1 | 2.1.3 |
| El stack se crea y se actualiza solo con un change set revisado antes de ejecutarlo | R29.7 | 2.1.5, 2.3 |
| El stack queda en `CREATE_COMPLETE` con `EnableTerminationProtection=true` | R29.8 | 2.1.7 |
| El stack publica los outputs `InstanceId`, `PublicIp`, `AppDomain` y `SandboxVolumeId` | R29.3 | 2.2 |
| Si fallan los recursos de Cost Anomaly Detection, se aplica el plan B | R29.10 | 2.4 |
| El borrado sigue el orden: protección del stack, `DisableApiTermination`, snapshots de ambos discos en `completed` y `delete-stack` | R29.9, R23.3 | 2.5 |

R29 no tiene un criterio CA propio. En las líneas «Resultado de verificación» de esta sección, `criterio` lleva `sin CA` y el número exacto va en `requisito`. Los recursos del stack se verifican después con los criterios de sus Requirements, en las secciones 3, 7 y 8.

Nombres que usan los comandos, tomados de la plantilla:

| Tipo | Nombres |
| --- | --- |
| Parámetros obligatorios | `VpcId`, `SubnetId`, `AmiId`, `Owner`, `AlertEmail` |
| Parámetro con valor por defecto | `MonthlyBudgetUsd` (30; no se pasa en el primer despliegue, porque R20.1 exige 30) |
| Recursos lógicos (11) | `Ec2Role`, `Ec2InstanceProfile`, `AppSecurityGroup`, `Instance`, `SandboxVolume`, `SandboxVolumeAttachment`, `ElasticIp`, `MonthlyBudget`, `RecoverAlarm`, `CostAnomalyMonitor`, `CostAnomalySubscription` |
| Outputs | `InstanceId`, `PublicIp`, `AppDomain`, `SandboxVolumeId` |

### 2.0 Preparación de CloudShell

Se abre CloudShell desde la consola, en la región `us-east-2`, y se trae el repositorio para tener la plantilla a mano:

```bash
echo "$AWS_REGION"                       # debe mostrar us-east-2
git clone <url-del-repositorio> PgGuardian-Online
cd PgGuardian-Online
mkdir -p docs/aws/evidencia/stack
FECHA=$(date -u +%Y%m%dT%H%MZ)
```

Si el repositorio no es accesible desde CloudShell, se sube `infra/cloudformation/pgguardian.yaml` con **Actions** → **Upload file** y se crea a mano la misma ruta. Los archivos de evidencia que se generan en `docs/aws/evidencia/stack/` se bajan al final con **Actions** → **Download file** y se versionan en el repositorio. Las variables de shell (`AMI_ID`, `CS_NAME`, etc.) solo duran mientras dura la sesión de CloudShell; si la sesión se reinicia, se vuelven a definir.

### 2.1 Primer despliegue

Orden: 2.1.1 → 2.1.2 → 2.1.3 → 2.1.4 → 2.1.5 → 2.1.6 → 2.1.7 → 2.2. No se salta ningún paso. Si un paso no queda en `aprobado`, no se sigue con el siguiente.

#### 2.1.1 Validación de la plantilla (R29.6)

`cfn-lint` no viene en CloudShell; se instala para el usuario:

```bash
pip3 install --user --quiet cfn-lint
export PATH="$HOME/.local/bin:$PATH"
cfn-lint infra/cloudformation/pgguardian.yaml
aws cloudformation validate-template --template-body file://infra/cloudformation/pgguardian.yaml
```

Resultado esperado: `cfn-lint` termina sin mensajes y con código 0, y `validate-template` devuelve los seis parámetros y `"Capabilities": ["CAPABILITY_NAMED_IAM"]`. El código de salida de `cfn-lint` es una suma de bits: 2 indica errores, 4 advertencias y 8 mensajes informativos. Solo los errores bloquean el despliegue; las advertencias se revisan y se anotan en el `detalle`.

Evaluación automática del criterio:

```bash
(
  criterio="sin CA"; requisito="R29.6"
  plantilla="infra/cloudformation/pgguardian.yaml"
  lint=$(cfn-lint "$plantilla" 2>&1); rc=$?
  val=$(aws cloudformation validate-template --template-body "file://$plantilla" \
        --query 'length(Parameters)' --output text 2>&1); rv=$?
  if [ $((rc & ~14)) -ne 0 ]; then
    estado="no_verificable"
    detalle="cfn-lint no se ejecutó (código $rc): $(echo "$lint" | tr '\n' ' ')"
  elif [ $((rc & 2)) -ne 0 ]; then
    estado="no_aprobado"
    detalle="no conforme: cfn-lint con errores (código $rc): $(echo "$lint" | tr '\n' ' ')"
  elif [ $rv -ne 0 ] && grep -q 'ValidationError' <<< "$val"; then
    estado="no_aprobado"
    detalle="no conforme: validate-template con errores: $(echo "$val" | tr '\n' ' ')"
  elif [ $rv -ne 0 ]; then
    estado="no_verificable"
    detalle="falló aws cloudformation validate-template: $(echo "$val" | tr '\n' ' ')"
  else
    estado="aprobado"
    detalle="cfn-lint código $rc sin errores$([ $((rc & 4)) -ne 0 ] && echo " (con advertencias: $(echo "$lint" | tr '\n' ' '))"); validate-template sin errores, $val parámetros"
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Corrección ante `no_aprobado`: se corrige la plantilla en el repositorio y se repite 2.1.1. No se crea ningún change set mientras haya errores.

#### 2.1.2 ID de la AMI de Ubuntu 24.04 (R29.2, solo antes del primer despliegue)

La plantilla no resuelve la AMI: la recibe en `AmiId`. El ID se obtiene una sola vez, aquí, y no se vuelve a consultar en las actualizaciones (2.3), que lo conservan con `UsePreviousValue=true`. Así, una AMI nueva publicada por Canonical no reemplaza la instancia ni borra el disco raíz con `app_db`.

```bash
AMI_ID=$(aws ssm get-parameter \
  --name /aws/service/canonical/ubuntu/server/24.04/stable/current/amd64/hvm/ebs-gp3/ami-id \
  --query Parameter.Value --output text)
echo "$AMI_ID"
aws ec2 describe-images --image-ids "$AMI_ID" \
  --query 'Images[0].[ImageId,Name,CreationDate]' --output text \
  | tee "docs/aws/evidencia/stack/ami-id-$FECHA.txt"
```

Resultado esperado: un ID `ami-...` cuyo nombre empieza por `ubuntu/images/hvm-ssd-gp3/ubuntu-noble-24.04-amd64-server-`. El archivo de evidencia deja registrado qué AMI usa el stack.

#### 2.1.3 Comprobación previa: monitor de anomalías por defecto (R21.1, modifica la cuenta)

AWS permite un solo monitor de anomalías de servicios (`DIMENSIONAL`, `SERVICE`) por cuenta. Si el monitor por defecto sigue existiendo, `CostAnomalyMonitor` falla y el stack entero se revierte. En esta cuenta existe `Default-Services-Monitor`, con la suscripción `Default-Services-Subscription` (umbral de 100 USD y 40 %). Se guarda su configuración como evidencia y después se borra. La decisión está en `docs/aws/decision-log.md` («Monitor de anomalías por defecto reemplazado por el del stack»).

Este paso solo se hace antes del primer despliegue. Si la consulta del punto 1 muestra `PgGuardian-Services`, el stack o el script del plan B ya creó su monitor: no se borra nada y no se trata de un primer despliegue.

Los comandos `aws ce` llevan `--region us-east-1` porque la API de Cost Explorer solo tiene endpoint en esa región. Los monitores son globales de la cuenta, así que el resultado es el mismo que verá el stack desde `us-east-2`.

1. Consultar los monitores `DIMENSIONAL` y guardar la salida:

   ```bash
   aws ce get-anomaly-monitors --region us-east-1 \
     --query "AnomalyMonitors[?MonitorType=='DIMENSIONAL']" --output json \
     | tee "docs/aws/evidencia/stack/anomaly-monitors-antes-$FECHA.json"
   ```

   Resultado esperado en esta cuenta: una lista con un elemento, `"MonitorName": "Default-Services-Monitor"` y `"MonitorDimension": "SERVICE"`. Si la lista está vacía (`[]`), se anota y se pasa al punto 5.

2. Guardar las suscripciones del monitor:

   ```bash
   MONITOR_ARN=$(aws ce get-anomaly-monitors --region us-east-1 \
     --query "AnomalyMonitors[?MonitorType=='DIMENSIONAL' && MonitorName=='Default-Services-Monitor'].MonitorArn | [0]" \
     --output text)
   echo "$MONITOR_ARN"
   aws ce get-anomaly-subscriptions --region us-east-1 --monitor-arn "$MONITOR_ARN" --output json \
     | tee "docs/aws/evidencia/stack/anomaly-subscriptions-antes-$FECHA.json"
   ```

   Resultado esperado: `Default-Services-Subscription`, con su `ThresholdExpression` (100 USD y 40 %), su frecuencia y sus suscriptores. Si alguna suscripción lista en `MonitorArnList` más de un monitor, se detiene el paso y se consulta al Equipo, porque borrarla quitaría también los avisos de los otros monitores.

3. Bajar los dos archivos de evidencia (**Actions** → **Download file**) y comprobar que no están vacíos **antes** de borrar nada. Sin evidencia guardada, no se sigue.

4. Borrar primero las suscripciones y al final el monitor:

   ```bash
   for SUB_ARN in $(aws ce get-anomaly-subscriptions --region us-east-1 --monitor-arn "$MONITOR_ARN" \
       --query 'AnomalySubscriptions[].SubscriptionArn' --output text); do
     echo "Borrando suscripción $SUB_ARN"
     aws ce delete-anomaly-subscription --region us-east-1 --subscription-arn "$SUB_ARN"
   done
   aws ce delete-anomaly-monitor --region us-east-1 --monitor-arn "$MONITOR_ARN"
   ```

5. Repetir la consulta del punto 1 y confirmar que devuelve una lista vacía:

   ```bash
   aws ce get-anomaly-monitors --region us-east-1 \
     --query "AnomalyMonitors[?MonitorType=='DIMENSIONAL']" --output json \
     | tee "docs/aws/evidencia/stack/anomaly-monitors-despues-$FECHA.json"
   ```

   Resultado esperado: `[]`.

Evaluación automática del criterio (solo lee):

```bash
(
  criterio="sin CA"; requisito="R21.1 (comprobación previa al primer despliegue)"
  if ! salida=$(aws ce get-anomaly-monitors --region us-east-1 \
       --query "AnomalyMonitors[?MonitorType=='DIMENSIONAL'].MonitorName" --output json 2>&1); then
    estado="no_verificable"
    detalle="falló aws ce get-anomaly-monitors: $(echo "$salida" | tr '\n' ' ')"
  elif [ "$(jq 'length' <<< "$salida")" -eq 0 ]; then
    estado="aprobado"
    detalle="la cuenta no tiene monitores DIMENSIONAL; el stack puede crear CostAnomalyMonitor"
  else
    estado="no_aprobado"
    detalle="no conforme: quedan monitores DIMENSIONAL: $(jq -c . <<< "$salida")"
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Al borrar el monitor por defecto, la cuenta queda sin detección de anomalías hasta que el stack cree `CostAnomalyMonitor` (2.1.6). Por eso 2.1.4 a 2.1.6 se hacen justo después de este paso, en la misma sesión.

#### 2.1.4 Creación del change set (R29.7, crea el stack en `REVIEW_IN_PROGRESS` sin recursos)

Valores de los parámetros. La VPC y la subred son las públicas por defecto de `us-east-2`; la subred fija la zona de disponibilidad de la instancia y del Volumen_Sandbox:

```bash
VPC_ID=$(aws ec2 describe-vpcs --filters Name=is-default,Values=true \
  --query 'Vpcs[0].VpcId' --output text)
aws ec2 describe-subnets \
  --filters Name=vpc-id,Values="$VPC_ID" Name=map-public-ip-on-launch,Values=true \
  --query 'Subnets[].[SubnetId,AvailabilityZone]' --output table
SUBNET_ID=<subnet-id elegida de la tabla>
OWNER="<responsable del despliegue, 1 a 256 caracteres>"
ALERT_EMAIL="<correo del Equipo>"
CS_NAME="pgguardian-$(date -u +%Y%m%d-%H%M)"
echo "$VPC_ID $SUBNET_ID $AMI_ID $OWNER $ALERT_EMAIL $CS_NAME"
```

Creación del change set, con los cinco parámetros obligatorios y el ID de 2.1.2 como `AmiId`. `CAPABILITY_NAMED_IAM` es obligatorio porque el rol tiene un nombre fijo (`PgGuardian-EC2-Role`):

```bash
aws cloudformation create-change-set --stack-name pgguardian \
  --change-set-name "$CS_NAME" --change-set-type CREATE \
  --template-body file://infra/cloudformation/pgguardian.yaml \
  --capabilities CAPABILITY_NAMED_IAM \
  --parameters \
    ParameterKey=VpcId,ParameterValue="$VPC_ID" \
    ParameterKey=SubnetId,ParameterValue="$SUBNET_ID" \
    ParameterKey=AmiId,ParameterValue="$AMI_ID" \
    ParameterKey=Owner,ParameterValue="$OWNER" \
    ParameterKey=AlertEmail,ParameterValue="$ALERT_EMAIL"
aws cloudformation wait change-set-create-complete \
  --stack-name pgguardian --change-set-name "$CS_NAME"
```

Si el `wait` falla, se lee el motivo:

```bash
aws cloudformation describe-change-set --stack-name pgguardian --change-set-name "$CS_NAME" \
  --query '[Status,StatusReason]' --output text
```

Un `Owner` vacío o de más de 256 caracteres, o un `AlertEmail` sin forma de correo, hacen fallar el change set antes de crear ningún recurso (R17.3).

#### 2.1.5 Revisión del change set (R29.7)

El Equipo lee la tabla antes de ejecutar nada:

```bash
aws cloudformation describe-change-set --stack-name pgguardian --change-set-name "$CS_NAME" \
  --query "Changes[].ResourceChange.[Action,LogicalResourceId,ResourceType,Replacement]" --output table \
  | tee "docs/aws/evidencia/stack/change-set-$CS_NAME.txt"
```

Resultado esperado en el primer despliegue: 11 filas, todas con `Action=Add` y `Replacement` vacío (`None`):

| `LogicalResourceId` | `ResourceType` |
| --- | --- |
| `Ec2Role` | `AWS::IAM::Role` |
| `Ec2InstanceProfile` | `AWS::IAM::InstanceProfile` |
| `AppSecurityGroup` | `AWS::EC2::SecurityGroup` |
| `Instance` | `AWS::EC2::Instance` |
| `SandboxVolume` | `AWS::EC2::Volume` |
| `SandboxVolumeAttachment` | `AWS::EC2::VolumeAttachment` |
| `ElasticIp` | `AWS::EC2::EIP` |
| `MonthlyBudget` | `AWS::Budgets::Budget` |
| `RecoverAlarm` | `AWS::CloudWatch::Alarm` |
| `CostAnomalyMonitor` | `AWS::CE::AnomalyMonitor` |
| `CostAnomalySubscription` | `AWS::CE::AnomalySubscription` |

Evaluación automática del criterio. Si se aplicó el plan B (2.4), se quitan `CostAnomalyMonitor` y `CostAnomalySubscription` de `esperados`:

```bash
(
  criterio="sin CA"; requisito="R29.7 (change set CREATE)"
  esperados='["AppSecurityGroup","CostAnomalyMonitor","CostAnomalySubscription","Ec2InstanceProfile","Ec2Role","ElasticIp","Instance","MonthlyBudget","RecoverAlarm","SandboxVolume","SandboxVolumeAttachment"]'
  if ! cs=$(aws cloudformation describe-change-set --stack-name pgguardian \
       --change-set-name "$CS_NAME" --output json 2>&1); then
    estado="no_verificable"
    detalle="falló aws cloudformation describe-change-set: $(echo "$cs" | tr '\n' ' ')"
  else
    st=$(jq -r '.Status' <<< "$cs"); ex=$(jq -r '.ExecutionStatus' <<< "$cs")
    ids=$(jq -c '[.Changes[].ResourceChange.LogicalResourceId] | sort' <<< "$cs")
    no_add=$(jq -c '[.Changes[].ResourceChange | select(.Action != "Add") | "\(.LogicalResourceId)=\(.Action)"]' <<< "$cs")
    if [ "$st" != "CREATE_COMPLETE" ] || [ "$ex" != "AVAILABLE" ]; then
      estado="no_aprobado"
      detalle="no conforme: change set $CS_NAME con Status=$st, ExecutionStatus=$ex: $(jq -r '.StatusReason // ""' <<< "$cs")"
    elif [ "$ids" != "$(jq -c 'sort' <<< "$esperados")" ]; then
      estado="no_aprobado"
      detalle="no conforme: recursos distintos de los esperados: $ids"
    elif [ "$no_add" != "[]" ]; then
      estado="no_aprobado"
      detalle="no conforme: acciones distintas de Add: $no_add"
    else
      estado="aprobado"
      detalle="change set $CS_NAME: $(jq 'length' <<< "$ids") recursos, todos Add: $ids; revisado por <nombre>"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

En el `detalle` se reemplaza `<nombre>` por quien revisó la tabla. Corrección ante `no_aprobado`: no se ejecuta el change set. Se borra con `aws cloudformation delete-change-set --stack-name pgguardian --change-set-name "$CS_NAME"`, se corrige la plantilla o los parámetros y se repite desde 2.1.1. El stack queda en `REVIEW_IN_PROGRESS` sin recursos, y el nuevo change set se crea con el mismo nombre de stack y `--change-set-type CREATE`.

#### 2.1.6 Ejecución del change set (crea los recursos)

Solo después de 2.1.5 en `aprobado`:

```bash
aws cloudformation execute-change-set --stack-name pgguardian --change-set-name "$CS_NAME"
aws cloudformation wait stack-create-complete --stack-name pgguardian
aws cloudformation describe-stacks --stack-name pgguardian --query 'Stacks[0].StackStatus' --output text
```

Resultado esperado: `CREATE_COMPLETE`. Si el `wait` falla, se listan los eventos fallidos y se sigue en 2.4:

```bash
aws cloudformation describe-stack-events --stack-name pgguardian \
  --query "StackEvents[?contains(ResourceStatus, 'FAILED')].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]" \
  --output table | tee "docs/aws/evidencia/stack/eventos-fallidos-$FECHA.txt"
```

#### 2.1.7 Protección contra terminación del stack (R29.8, modifica el stack)

`create-change-set` no acepta la protección contra terminación, así que se activa después de `CREATE_COMPLETE`:

```bash
aws cloudformation update-termination-protection --enable-termination-protection --stack-name pgguardian
aws cloudformation describe-stacks --stack-name pgguardian \
  --query 'Stacks[0].[StackStatus,EnableTerminationProtection]' --output text
```

Resultado esperado: `CREATE_COMPLETE	True` (después de una actualización, `UPDATE_COMPLETE	True`).

Evaluación automática del criterio:

```bash
(
  criterio="sin CA"; requisito="R29.8"
  if ! salida=$(aws cloudformation describe-stacks --stack-name pgguardian \
       --query 'Stacks[0].[StackStatus,EnableTerminationProtection]' --output text 2>&1); then
    estado="no_verificable"
    detalle="falló aws cloudformation describe-stacks: $(echo "$salida" | tr '\n' ' ')"
  else
    read -r st prot <<< "$salida"
    fallos=()
    [[ "$st" =~ ^(CREATE_COMPLETE|UPDATE_COMPLETE)$ ]] || fallos+=("StackStatus=$st (se esperaba CREATE_COMPLETE o UPDATE_COMPLETE)")
    [ "$prot" = "True" ] || fallos+=("EnableTerminationProtection=${prot:-ausente} (se esperaba True)")
    if [ ${#fallos[@]} -eq 0 ]; then
      estado="aprobado"
      detalle="StackStatus=$st, EnableTerminationProtection=True"
    else
      estado="no_aprobado"
      detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Con la protección activa, `delete-stack` falla hasta que se desactive. El orden completo del borrado está en 2.5.

### 2.2 Lectura de outputs (R29.3)

```bash
aws cloudformation describe-stacks --stack-name pgguardian --query "Stacks[0].Outputs" \
  | tee "docs/aws/evidencia/stack/outputs-$FECHA.json"
```

Resultado esperado (valores de ejemplo):

```json
[
  { "OutputKey": "InstanceId",      "OutputValue": "i-0123456789abcdef0" },
  { "OutputKey": "PublicIp",        "OutputValue": "203.0.113.10" },
  { "OutputKey": "AppDomain",       "OutputValue": "203-0-113-10.sslip.io" },
  { "OutputKey": "SandboxVolumeId", "OutputValue": "vol-0123456789abcdef0" }
]
```

La salida real también trae el campo `Description` de cada output. Quién usa cada uno:

| Output | Lo usan |
| --- | --- |
| `InstanceId` | Tarea 5.3 (verificaciones de la sección 3), tarea 6.4 (encender y detener, sección 6) y tarea 7.4 (`manual_snapshot.sh`, para obtener el disco raíz) |
| `PublicIp` | Tarea 5.3 (`nmap` y comprobación de la Elastic IP) |
| `AppDomain` | Tarea 6.2 (`make_env.sh` lo recibe como argumento y lo escribe en `APP_DOMAIN`; el rol de la instancia no tiene permisos de CloudFormation) |
| `SandboxVolumeId` | Tarea 6.1 (`bootstrap_host.sh` localiza con él el dispositivo NVMe) y tarea 7.4 (`manual_snapshot.sh`) |

Para cargarlos en variables de la sesión de CloudShell:

```bash
output_stack() {
  aws cloudformation describe-stacks --stack-name pgguardian \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
INSTANCE_ID=$(output_stack InstanceId)
PUBLIC_IP=$(output_stack PublicIp)
APP_DOMAIN=$(output_stack AppDomain)
SANDBOX_VOLUME_ID=$(output_stack SandboxVolumeId)
echo "$INSTANCE_ID $PUBLIC_IP $APP_DOMAIN $SANDBOX_VOLUME_ID"
```

Evaluación automática del criterio:

```bash
(
  criterio="sin CA"; requisito="R29.3"
  if ! outs=$(aws cloudformation describe-stacks --stack-name pgguardian \
       --query 'Stacks[0].Outputs' --output json 2>&1); then
    estado="no_verificable"
    detalle="falló aws cloudformation describe-stacks: $(echo "$outs" | tr '\n' ' ')"
  else
    v() { jq -r --arg k "$1" '(map(select(.OutputKey == $k)) | .[0].OutputValue) // ""' <<< "$outs"; }
    iid=$(v InstanceId); ip=$(v PublicIp); dom=$(v AppDomain); vol=$(v SandboxVolumeId)
    fallos=()
    [[ "$iid" =~ ^i-[0-9a-f]+$ ]] || fallos+=("InstanceId=${iid:-ausente}")
    [[ "$ip" =~ ^([0-9]{1,3}\.){3}[0-9]{1,3}$ ]] || fallos+=("PublicIp=${ip:-ausente}")
    [ -n "$ip" ] && [ "$dom" = "${ip//./-}.sslip.io" ] || fallos+=("AppDomain=${dom:-ausente} (se esperaba ${ip//./-}.sslip.io)")
    [[ "$vol" =~ ^vol-[0-9a-f]+$ ]] || fallos+=("SandboxVolumeId=${vol:-ausente}")
    if [ ${#fallos[@]} -eq 0 ]; then
      estado="aprobado"
      detalle="InstanceId=$iid, PublicIp=$ip, AppDomain=$dom, SandboxVolumeId=$vol"
    else
      estado="no_aprobado"
      detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

### 2.3 Actualizaciones del stack (R29.2, R29.7, modifica el stack)

Cualquier cambio de la plantilla o de un parámetro sigue el mismo procedimiento con change set, con tres diferencias: no se consulta la AMI (2.1.2), no se repite la comprobación de anomalías (2.1.3) y todos los parámetros que no cambian se pasan con `UsePreviousValue=true`. Los cambios hechos fuera de CloudFormation (consola o CLI) generan *drift* y no se hacen; la única excepción es `--no-disable-api-termination` justo antes de un borrado (2.4 y 2.5).

1. Validar la plantilla (2.1.1).
2. Crear el change set de actualización. Ejemplo sin cambios de parámetros (solo de plantilla):

   ```bash
   CS_NAME="pgguardian-$(date -u +%Y%m%d-%H%M)"
   aws cloudformation create-change-set --stack-name pgguardian \
     --change-set-name "$CS_NAME" --change-set-type UPDATE \
     --template-body file://infra/cloudformation/pgguardian.yaml \
     --capabilities CAPABILITY_NAMED_IAM \
     --parameters \
       ParameterKey=VpcId,UsePreviousValue=true \
       ParameterKey=SubnetId,UsePreviousValue=true \
       ParameterKey=AmiId,UsePreviousValue=true \
       ParameterKey=Owner,UsePreviousValue=true \
       ParameterKey=AlertEmail,UsePreviousValue=true \
       ParameterKey=MonthlyBudgetUsd,UsePreviousValue=true
   aws cloudformation wait change-set-create-complete \
     --stack-name pgguardian --change-set-name "$CS_NAME"
   ```

   Para cambiar un parámetro, se sustituye solo su línea por `ParameterKey=<nombre>,ParameterValue=<valor nuevo>` (p. ej. `Owner` para corregir la etiqueta, R17.3). `AmiId` siempre lleva `UsePreviousValue=true`. Si el change set queda en `FAILED` con un motivo que indica que no contiene cambios, no hay nada que actualizar: se borra con `delete-change-set`.

3. Revisar la tabla, igual que en 2.1.5, y guardarla en la evidencia:

   ```bash
   aws cloudformation describe-change-set --stack-name pgguardian --change-set-name "$CS_NAME" \
     --query "Changes[].ResourceChange.[Action,LogicalResourceId,ResourceType,Replacement]" --output table \
     | tee "docs/aws/evidencia/stack/change-set-$CS_NAME.txt"
   ```

   Segunda barrera: **no se ejecuta el change set si `Instance` aparece con `Replacement=True`**. Reemplazar la instancia borraría el disco raíz con los datos de `app_db`. `Replacement=Conditional` en `Instance` tampoco se ejecuta sin revisar antes los `Details` del cambio con el Equipo. Un reemplazo de `SandboxVolume` (pérdida de los datos del sandbox) o de `ElasticIp` (cambio de IP, de `AppDomain` y del certificado) también se discute antes de ejecutar.

4. Evaluación automática de la barrera:

   ```bash
   (
     criterio="sin CA"; requisito="R29.2, R29.7 (change set UPDATE)"
     if ! cs=$(aws cloudformation describe-change-set --stack-name pgguardian \
          --change-set-name "$CS_NAME" --output json 2>&1); then
       estado="no_verificable"
       detalle="falló aws cloudformation describe-change-set: $(echo "$cs" | tr '\n' ' ')"
     elif ! actual=$(aws cloudformation describe-stacks --stack-name pgguardian \
          --query "Stacks[0].Parameters[?ParameterKey=='AmiId'].ParameterValue | [0]" --output text 2>&1); then
       estado="no_verificable"
       detalle="falló aws cloudformation describe-stacks: $(echo "$actual" | tr '\n' ' ')"
     else
       st=$(jq -r '.Status' <<< "$cs")
       ami_cs=$(jq -r --arg prev "$actual" '(.Parameters[] | select(.ParameterKey == "AmiId")
                | if .UsePreviousValue == true then $prev else .ParameterValue end) // ""' <<< "$cs")
       inst=$(jq -r '[.Changes[].ResourceChange | select(.LogicalResourceId == "Instance") | .Replacement // "None"] | .[0] // "sin cambios"' <<< "$cs")
       otros=$(jq -c '[.Changes[].ResourceChange | select(.LogicalResourceId != "Instance" and (.Replacement == "True" or .Replacement == "Conditional")) | "\(.LogicalResourceId)=\(.Replacement)"]' <<< "$cs")
       resumen=$(jq -c '[.Changes[].ResourceChange | "\(.Action) \(.LogicalResourceId)"]' <<< "$cs")
       if [ "$st" != "CREATE_COMPLETE" ]; then
         estado="no_aprobado"
         detalle="no conforme: change set $CS_NAME con Status=$st: $(jq -r '.StatusReason // ""' <<< "$cs")"
       elif [ "$ami_cs" != "$actual" ]; then
         estado="no_aprobado"
         detalle="no conforme: AmiId cambia de $actual a $ami_cs; se esperaba UsePreviousValue=true"
       elif [ "$inst" = "True" ] || [ "$inst" = "Conditional" ]; then
         estado="no_aprobado"
         detalle="no ejecutar: Instance con Replacement=$inst; cambios: $resumen"
       else
         estado="aprobado"
         detalle="change set $CS_NAME: AmiId sin cambios ($actual); Instance: Replacement=$inst; otros reemplazos a revisar: $otros; cambios: $resumen; revisado por <nombre>"
       fi
     fi
     jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
       '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
   )
   ```

   Si el resultado es `no_aprobado`, se borra el change set con `aws cloudformation delete-change-set --stack-name pgguardian --change-set-name "$CS_NAME"` y se revisan la plantilla o los parámetros. Si `otros` no está vacío, el Equipo decide antes de ejecutar y anota la decisión en el `detalle`.

5. Ejecutar y esperar, solo con el punto 4 en `aprobado`:

   ```bash
   aws cloudformation execute-change-set --stack-name pgguardian --change-set-name "$CS_NAME"
   aws cloudformation wait stack-update-complete --stack-name pgguardian
   ```

6. Repetir la evaluación de 2.1.7 (debe dar `UPDATE_COMPLETE` y `EnableTerminationProtection=True`; la protección no se pierde con las actualizaciones) y la de 2.2.

Si la actualización falla, CloudFormation vuelve a la configuración anterior (`UPDATE_ROLLBACK_COMPLETE`). Se leen los eventos fallidos con el comando de 2.1.6, se corrige y se repite desde el punto 1.

### 2.4 Plan B: fallo en Cost Anomaly Detection o rollback bloqueado (R29.10, modifica la cuenta)

No se pudo probar antes el despliegue de `AWS::CE::AnomalyMonitor` y `AWS::CE::AnomalySubscription` desde `us-east-2`. Si el primer despliegue falla en `CostAnomalyMonitor` o `CostAnomalySubscription`, esos dos recursos salen de la plantilla y se crean aparte con `scripts/aws/create_anomaly_detection.sh` (tarea 7.2), de modo que R21 se sigue cumpliendo.

1. **Identificar el recurso que falló.** Con los eventos de 2.1.6, se busca el primer evento `CREATE_FAILED` por orden de `Timestamp`. Los demás recursos suelen mostrar `Resource creation cancelled` como consecuencia, no como causa. El plan B aplica solo si el primero es `CostAnomalyMonitor` o `CostAnomalySubscription`. Si es otro recurso, se corrige su causa y se siguen igualmente los puntos 2 y 3 para limpiar el stack antes de repetir.

2. **Ver el estado del stack:**

   ```bash
   aws cloudformation describe-stacks --stack-name pgguardian --query 'Stacks[0].StackStatus' --output text
   ```

   - `ROLLBACK_COMPLETE`: el rollback borró todo; se pasa al punto 3.
   - `ROLLBACK_FAILED`: lo habitual es que `DisableApiTermination: true` impida a CloudFormation terminar la instancia (`Instance` en `DELETE_FAILED`). Se obtiene su ID físico y se desactiva la protección de la instancia:

     ```bash
     IID=$(aws cloudformation describe-stack-resources --stack-name pgguardian \
       --logical-resource-id Instance --query 'StackResources[0].PhysicalResourceId' --output text)
     echo "$IID"
     aws ec2 modify-instance-attribute --instance-id "$IID" --no-disable-api-termination
     ```

3. **Borrar el stack fallido.** La protección contra terminación del stack todavía no está activa, porque 2.1.7 solo se ejecuta tras `CREATE_COMPLETE`. El stack fallido no llegó a guardar datos, así que no se toman snapshots; el borrado ordinario de un stack en uso (2.5) sí los exige.

   ```bash
   aws cloudformation delete-stack --stack-name pgguardian
   aws cloudformation wait stack-delete-complete --stack-name pgguardian
   aws ec2 describe-instances --filters Name=tag:Project,Values=PgGuardian \
     Name=instance-state-name,Values=pending,running,stopping,stopped \
     --query 'Reservations[].Instances[].InstanceId' --output text
   aws ec2 describe-addresses --filters Name=tag:Project,Values=PgGuardian \
     --query 'Addresses[].PublicIp' --output text
   ```

   Resultado esperado: el `wait` termina sin error y las dos últimas consultas no devuelven nada (no quedan instancias ni Elastic IP del stack que sigan cobrando).

4. **Quitar los dos recursos de la plantilla** (solo si aplica el plan B). En el repositorio, se borran de `infra/cloudformation/pgguardian.yaml` los bloques `CostAnomalyMonitor` y `CostAnomalySubscription` (con su comentario `T-20 / R21`), se hace commit con el motivo y se vuelve a traer el cambio a CloudShell. En la evaluación de 2.1.5 se quitan esos dos nombres de `esperados`, de modo que el change set debe tener 9 recursos.

5. **Volver a desplegar.** Se repiten 2.1.1, el punto 5 de 2.1.3 (la lista de monitores `DIMENSIONAL` debe seguir vacía; el rollback borra el monitor del stack si llegó a crearse) y 2.1.4 a 2.1.7 y 2.2. Se usa el mismo `AMI_ID` registrado en `docs/aws/evidencia/stack/ami-id-<fecha>.txt`; no se vuelve a consultar el parámetro de SSM.

6. **Crear la detección de anomalías fuera del stack** con `scripts/aws/create_anomaly_detection.sh` (tarea 7.2) y anotar en la sección 7 que el monitor y la suscripción no pertenecen al stack. Al borrar el stack (2.5), esos dos recursos no se borran con él.

Resultado de verificación del plan B, anotado a mano:

```json
{ "criterio": "sin CA", "requisito": "R29.10", "estado": "aprobado", "detalle": "falló <recurso> (<motivo>); stack fallido borrado (estado previo <ROLLBACK_COMPLETE|ROLLBACK_FAILED>); plantilla sin CostAnomalyMonitor ni CostAnomalySubscription (commit <hash>); nuevo stack en CREATE_COMPLETE; monitor y suscripción creados con create_anomaly_detection.sh" }
```

La sección 2 queda completa para el primer despliegue cuando 2.1.1, 2.1.3, 2.1.5, 2.1.7 y 2.2 están en `aprobado` (y, si se aplicó, también el plan B). Cada actualización posterior añade las líneas de 2.1.1, del punto 4 de 2.3, de 2.1.7 y de 2.2.

### 2.5 Borrado del stack (R29.8, R29.9, R23.3, modifica y borra recursos)

> **Atención.** Este procedimiento borra la Instancia, los dos discos (con los datos de `app_db` y del sandbox) y la Elastic IP. La URL `<ip-con-guiones>.sslip.io` deja de existir y no se puede recuperar la misma IP. Solo se ejecuta cuando el Equipo decide retirar el despliegue, y se avisa antes a todos los integrantes. Para una pausa basta con detener la Instancia (sección 6).

El orden es fijo (R29.9) y no se salta ningún paso: 2.5.1 → 2.5.2 → 2.5.3 → 2.5.4 → 2.5.5 → 2.5.6. Si un paso no queda en `aprobado`, no se sigue con el siguiente. Todo se ejecuta en CloudShell (`us-east-2`) con un Usuario_IAM de `PgG-Admins` autenticado con MFA, desde la raíz del repositorio clonado (2.0).

Este borrado es el de un stack en uso. El borrado de un stack fallido en el primer despliegue, sin snapshots, está en el punto 3 de 2.4.

Qué borra `delete-stack` y qué conserva:

| Se borra con el stack | Se conserva |
| --- | --- |
| `Instance` (la Instancia) | Snapshots manuales de los dos discos (no pertenecen al stack) |
| Disco raíz (`DeleteOnTermination: true`) | Usuario_IAM, `PgG-Admins` y `Force_MFA` (fuera de la plantilla, R29.5) |
| `SandboxVolume` y `SandboxVolumeAttachment` | Monitor y suscripción de anomalías creados con `create_anomaly_detection.sh`, solo si se aplicó el plan B (2.4) |
| `ElasticIp` | Evidencia en `docs/aws/evidencia/` y el repositorio |
| `Ec2Role` y `Ec2InstanceProfile` | |
| `AppSecurityGroup` | |
| `MonthlyBudget` | |
| `RecoverAlarm` | |
| `CostAnomalyMonitor` y `CostAnomalySubscription` | |

La plantilla no declara `DeletionPolicy` en ningún recurso, así que CloudFormation borra todos los recursos del stack (11, o 9 con el plan B). Los snapshots siguen cobrando almacenamiento (unos 0.05 USD por GB-mes) hasta que el Equipo los borre a mano.

#### 2.5.1 Preparación: outputs y volúmenes

```bash
mkdir -p docs/aws/evidencia/stack
FECHA=$(date -u +%Y%m%dT%H%MZ)
output_stack() {
  aws cloudformation describe-stacks --stack-name pgguardian \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
INSTANCE_ID=$(output_stack InstanceId)
SANDBOX_VOLUME_ID=$(output_stack SandboxVolumeId)
ROOT_VOLUME_ID=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --output json \
  | jq -r '.Reservations[0].Instances[0] as $i | $i.BlockDeviceMappings[]
           | select(.DeviceName == $i.RootDeviceName) | .Ebs.VolumeId')
echo "instancia=$INSTANCE_ID raiz=$ROOT_VOLUME_ID sandbox=$SANDBOX_VOLUME_ID"
aws cloudformation describe-stack-resources --stack-name pgguardian \
  --query 'StackResources[].[LogicalResourceId,ResourceType,PhysicalResourceId,ResourceStatus]' --output table \
  | tee "docs/aws/evidencia/stack/recursos-antes-de-borrar-$FECHA.txt"
```

Resultado esperado: los tres identificadores (`i-...` y dos `vol-...`), ninguno vacío ni `None`, y la tabla con los recursos del stack (11, o 9 si se aplicó el plan B). El disco raíz no es un recurso del stack: se obtiene de `describe-instances` (campo `BlockDeviceMappings`), como en 3.2. Si falta algún identificador, no se sigue: sin el ID de un disco no se puede tomar su snapshot.

#### 2.5.2 Desactivar la protección contra terminación del stack (R29.8, R29.9, modifica el stack)

```bash
aws cloudformation update-termination-protection --no-enable-termination-protection --stack-name pgguardian
aws cloudformation describe-stacks --stack-name pgguardian \
  --query 'Stacks[0].EnableTerminationProtection' --output text
```

Resultado esperado: `False`. Mientras valga `True`, `delete-stack` falla con un error que indica que el stack tiene la protección activa (R29.8).

#### 2.5.3 Desactivar `DisableApiTermination` de la Instancia (R29.9, modifica la Instancia)

Este cambio se hace fuera de CloudFormation y genera *drift*; es la única excepción permitida (2.3), porque el stack se borra justo después. Sin él, CloudFormation no puede terminar la Instancia y el borrado queda en `DELETE_FAILED`.

```bash
aws ec2 modify-instance-attribute --instance-id "$INSTANCE_ID" --no-disable-api-termination
aws ec2 describe-instance-attribute --instance-id "$INSTANCE_ID" \
  --attribute disableApiTermination --query 'DisableApiTermination.Value' --output text
```

Resultado esperado: `False`.

Evaluación automática de 2.5.2 y 2.5.3:

```bash
(
  criterio="sin CA"; requisito="R29.8, R29.9 (protecciones desactivadas antes del borrado)"
  if [ -z "$INSTANCE_ID" ]; then
    estado="no_verificable"; detalle="falta INSTANCE_ID; ejecutar 2.5.1"
  elif ! pst=$(aws cloudformation describe-stacks --stack-name pgguardian \
       --query 'Stacks[0].EnableTerminationProtection' --output text 2>&1); then
    estado="no_verificable"; detalle="falló aws cloudformation describe-stacks: $(echo "$pst" | tr '\n' ' ')"
  elif ! pin=$(aws ec2 describe-instance-attribute --instance-id "$INSTANCE_ID" \
       --attribute disableApiTermination --query 'DisableApiTermination.Value' --output text 2>&1); then
    estado="no_verificable"; detalle="falló aws ec2 describe-instance-attribute: $(echo "$pin" | tr '\n' ' ')"
  else
    fallos=()
    [ "$pst" = "False" ] || fallos+=("EnableTerminationProtection=${pst:-ausente} (se esperaba False)")
    [ "$pin" = "False" ] || fallos+=("disableApiTermination=${pin:-ausente} (se esperaba False)")
    if [ ${#fallos[@]} -eq 0 ]; then
      estado="aprobado"; detalle="stack pgguardian con EnableTerminationProtection=False; $INSTANCE_ID con disableApiTermination=False"
    else
      estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Si el Equipo decide no seguir con el borrado después de este punto, vuelve a activar ambas protecciones (`update-termination-protection --enable-termination-protection` y `modify-instance-attribute --disable-api-termination`) y repite 2.1.7 y 3.4.2.

#### 2.5.4 Snapshots del disco raíz y del Volumen_Sandbox (R29.9, R23.3)

Se toma un Snapshot_Manual de cada disco con `scripts/aws/manual_snapshot.sh` (tarea 7.4), que crea el snapshot con las etiquetas `Project`, `Env` y `Owner`, espera con `aws ec2 wait snapshot-completed` e informa si termina en `error`. El disco raíz contiene los datos de `app_db` (volumen `pgguardian_app_data`), así que su snapshot es el único respaldo de la aplicación después del borrado.

Para que los datos de PostgreSQL queden coherentes, primero se detiene la aplicación desde una sesión de Session Manager en la Instancia (`sudo docker compose -f docker-compose.prod.yml stop` en el directorio del despliegue). Si la Instancia no responde, se toma el snapshot igualmente y se anota en el `detalle` que no se detuvo la aplicación.

```bash
scripts/aws/manual_snapshot.sh "$ROOT_VOLUME_ID"      # espera hasta completed
scripts/aws/manual_snapshot.sh "$SANDBOX_VOLUME_ID"   # espera hasta completed
```

Si `manual_snapshot.sh` todavía no existe (tarea 7.4 pendiente), se usan los comandos equivalentes. `aws ec2 wait snapshot-completed` consulta cada 15 s durante un máximo de 10 min; si se agota antes de `completed`, se vuelve a ejecutar el `wait` con el mismo ID:

```bash
OWNER=$(aws ec2 describe-tags --filters "Name=resource-id,Values=$INSTANCE_ID" Name=key,Values=Owner \
  --query 'Tags[0].Value' --output text)
for VOL in "$ROOT_VOLUME_ID" "$SANDBOX_VOLUME_ID"; do
  SNAP=$(aws ec2 create-snapshot --volume-id "$VOL" \
    --description "PgGuardian: snapshot previo al borrado del stack ($FECHA)" \
    --tag-specifications "ResourceType=snapshot,Tags=[{Key=Project,Value=PgGuardian},{Key=Env,Value=prod},{Key=Owner,Value=$OWNER}]" \
    --query SnapshotId --output text)
  echo "$VOL -> $SNAP"
  aws ec2 wait snapshot-completed --snapshot-ids "$SNAP"
done
```

Evaluación automática del criterio. Busca, para cada disco, el snapshot más reciente con la etiqueta `Project=PgGuardian` y exige que esté en `completed`:

```bash
(
  criterio="CA-26"; requisito="R23.3, R29.9 (snapshots previos al borrado)"
  if [ -z "$ROOT_VOLUME_ID" ] || [ -z "$SANDBOX_VOLUME_ID" ]; then
    estado="no_verificable"; detalle="faltan ROOT_VOLUME_ID o SANDBOX_VOLUME_ID; ejecutar 2.5.1"
  elif ! snaps=$(aws ec2 describe-snapshots --owner-ids self \
       --filters "Name=volume-id,Values=$ROOT_VOLUME_ID,$SANDBOX_VOLUME_ID" Name=tag:Project,Values=PgGuardian \
       --output json 2>&1); then
    estado="no_verificable"; detalle="falló aws ec2 describe-snapshots: $(echo "$snaps" | tr '\n' ' ')"
  else
    ultimo() { jq -c --arg v "$1" '[.Snapshots[] | select(.VolumeId == $v)] | sort_by(.StartTime) | last
                 // {} | {id: .SnapshotId, estado: .State, inicio: .StartTime}' <<< "$snaps"; }
    raiz=$(ultimo "$ROOT_VOLUME_ID"); sb=$(ultimo "$SANDBOX_VOLUME_ID")
    fallos=()
    jq -e '.estado == "completed"' <<< "$raiz" >/dev/null || fallos+=("disco raíz $ROOT_VOLUME_ID: último snapshot $raiz")
    jq -e '.estado == "completed"' <<< "$sb" >/dev/null || fallos+=("Volumen_Sandbox $SANDBOX_VOLUME_ID: último snapshot $sb")
    if [ ${#fallos[@]} -eq 0 ]; then
      estado="aprobado"; detalle="raíz $(jq -r '"\(.id) completed (\(.inicio))"' <<< "$raiz"); sandbox $(jq -r '"\(.id) completed (\(.inicio))"' <<< "$sb")"
    else
      estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

El responsable comprueba en el `detalle` que la fecha de inicio de ambos snapshots es la de hoy: un snapshot antiguo en `completed` (p. ej. el de estabilización de la sección 8) no sustituye al previo al borrado. Ante `no_aprobado`: si un snapshot está en `pending`, se espera y se repite la evaluación; si está en `error`, se repite el snapshot del mismo volumen hasta obtener uno en `completed` (R23.4). **No se ejecuta `delete-stack` sin los dos snapshots en `completed`.**

#### 2.5.5 Borrado del stack (borra recursos)

Solo con 2.5.3 y 2.5.4 en `aprobado`:

```bash
aws cloudformation delete-stack --stack-name pgguardian
aws cloudformation wait stack-delete-complete --stack-name pgguardian
```

El `wait` consulta cada 30 s durante un máximo de 60 min; lo normal son de 3 a 8 minutos. Si falla, se leen los eventos:

```bash
aws cloudformation describe-stack-events --stack-name pgguardian \
  --query "StackEvents[?contains(ResourceStatus, 'FAILED')].[Timestamp,LogicalResourceId,ResourceStatus,ResourceStatusReason]" \
  --output table | tee "docs/aws/evidencia/stack/eventos-borrado-fallido-$FECHA.txt"
```

Con `Instance` en `DELETE_FAILED` por la protección, se repite 2.5.3. Con otro recurso, se corrige la causa que indica `ResourceStatusReason` y se vuelve a ejecutar `delete-stack`, que reintenta solo lo que quedó sin borrar. No se borran recursos a mano mientras el stack exista.

#### 2.5.6 Comprobación posterior al borrado

Evaluación automática del criterio (solo lee):

```bash
(
  criterio="sin CA"; requisito="R29.9 (stack borrado, snapshots conservados)"
  fallos=(); errores=()
  if salida=$(aws cloudformation describe-stacks --stack-name pgguardian \
       --query 'Stacks[0].StackStatus' --output text 2>&1); then
    fallos+=("el stack pgguardian sigue existiendo con estado $salida")
  elif ! grep -q 'does not exist' <<< "$salida"; then
    errores+=("describe-stacks: $(echo "$salida" | tr '\n' ' ')")
  fi
  if inst=$(aws ec2 describe-instances --filters Name=tag:Project,Values=PgGuardian \
       Name=instance-state-name,Values=pending,running,stopping,stopped,shutting-down \
       --query 'Reservations[].Instances[].InstanceId' --output text 2>&1); then
    [ -z "$inst" ] || fallos+=("instancias PgGuardian sin terminar: $inst")
  else errores+=("describe-instances: $(echo "$inst" | tr '\n' ' ')"); fi
  if vols=$(aws ec2 describe-volumes --volume-ids "$ROOT_VOLUME_ID" "$SANDBOX_VOLUME_ID" \
       --query 'Volumes[].[VolumeId,State]' --output text 2>&1); then
    [ -z "$vols" ] || fallos+=("volúmenes que siguen existiendo: $(echo "$vols" | tr '\n\t' '; ')")
  elif ! grep -q 'InvalidVolume.NotFound' <<< "$vols"; then
    errores+=("describe-volumes: $(echo "$vols" | tr '\n' ' ')")
  fi
  if eips=$(aws ec2 describe-addresses --filters Name=tag:Project,Values=PgGuardian \
       --query 'Addresses[].PublicIp' --output text 2>&1); then
    [ -z "$eips" ] || fallos+=("Elastic IP que sigue cobrando: $eips")
  else errores+=("describe-addresses: $(echo "$eips" | tr '\n' ' ')"); fi
  if snaps=$(aws ec2 describe-snapshots --owner-ids self --filters Name=tag:Project,Values=PgGuardian \
       Name=status,Values=completed --query 'Snapshots[].[SnapshotId,VolumeId]' --output text 2>&1); then
    nsnap=$(grep -c . <<< "$snaps")
    [ "$nsnap" -ge 2 ] || fallos+=("solo $nsnap snapshots completed con Project=PgGuardian (se esperaban al menos 2)")
  else errores+=("describe-snapshots: $(echo "$snaps" | tr '\n' ' ')"); fi
  if [ ${#errores[@]} -gt 0 ]; then
    estado="no_verificable"; detalle="falló: $(printf '%s; ' "${errores[@]}" | sed 's/; $//')"
  elif [ ${#fallos[@]} -eq 0 ]; then
    estado="aprobado"; detalle="stack pgguardian borrado; 0 instancias, 0 volúmenes y 0 Elastic IP del stack; $nsnap snapshots completed conservados"
  else
    estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Resultado esperado: `aprobado`. Ante `no_aprobado` por un recurso que sigue existiendo después de `DELETE_COMPLETE`, se identifica (puede ser ajeno al stack, por ejemplo una Elastic IP creada a mano con la etiqueta) y el Equipo decide si borrarlo; una Elastic IP sin asociar sigue cobrando.

#### 2.5.7 Detección de anomalías después del borrado

Al borrar el stack, la cuenta queda **sin ningún monitor de anomalías**: `CostAnomalyMonitor` y `CostAnomalySubscription` se borran con el stack, y el monitor por defecto (`Default-Services-Monitor`, con `Default-Services-Subscription`) se borró en la comprobación previa de 2.1.3. Su configuración original quedó como evidencia en `docs/aws/evidencia/stack/anomaly-monitors-antes-<fecha>.json` y `anomaly-subscriptions-antes-<fecha>.json`.

Si la cuenta sigue en uso, se vuelve a crear un monitor de servicios desde la consola: **Billing and Cost Management** → **Cost Anomaly Detection** → **Create monitor** → tipo **AWS services**, con una suscripción de alertas por correo (se puede tomar el umbral de la evidencia: 100 USD y 40 %). Se comprueba con:

```bash
aws ce get-anomaly-monitors --region us-east-1 \
  --query "AnomalyMonitors[?MonitorType=='DIMENSIONAL'].[MonitorName,MonitorDimension]" --output table
```

Si se aplicó el plan B (2.4), el monitor y la suscripción de `create_anomaly_detection.sh` no pertenecen al stack y siguen activos después del borrado; no hace falta crear otro.

El presupuesto `MonthlyBudget` también se borra con el stack. Si la cuenta sigue en uso, el Equipo decide si crea otro desde **Billing and Cost Management** → **Budgets**.

La sección 2.5 queda completa cuando 2.5.3, 2.5.4 y 2.5.6 están en `aprobado`. Las líneas se guardan en `docs/aws/evidencia/stack/` junto con las tablas de 2.5.1 y 2.5.5.

## 3. Instancia

### 3.1 Rol `PgGuardian-EC2-Role` y perfil de instancia (T-11 · RF-05.4 · CA-17 · R10.1, R10.2)

Condiciones que deben cumplir el Rol_EC2 y la Instancia:

| Condición | Requisito | Verificación |
| --- | --- | --- |
| `PgGuardian-EC2-Role` tiene adjunta `AmazonSSMManagedInstanceCore` | R10.1 | 3.1.1 |
| La Instancia usa el perfil de instancia asociado a `PgGuardian-EC2-Role` | R10.2 | 3.1.2 |
| Las credenciales de la Instancia vienen del rol, por IMDS, y no hay claves de acceso en el disco | R10.2 | 3.1.3 |

El rol (`Ec2Role`) y su perfil de instancia (`Ec2InstanceProfile`) los crea la plantilla (stack `pgguardian`); no hay paso manual ni script. El nombre del perfil lo genera CloudFormation, por eso 3.1.2 compara ARN en lugar de nombres. Ningún bloque de esta sección modifica el rol, el perfil ni la Instancia.

#### 3.1.1 Verificación de la política adjunta (R10.1)

Se ejecuta en CloudShell con un Usuario_IAM autenticado con MFA.

Consulta directa:

```bash
aws iam list-attached-role-policies --role-name PgGuardian-EC2-Role
```

Resultado esperado: `AttachedPolicies` incluye

```json
{
  "PolicyName": "AmazonSSMManagedInstanceCore",
  "PolicyArn": "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}
```

Evaluación automática del criterio:

```bash
(
  criterio="CA-17"; requisito="R10.1"
  if ! salida=$(aws iam list-attached-role-policies --role-name PgGuardian-EC2-Role \
       --query 'AttachedPolicies[].PolicyArn' --output json 2>&1); then
    estado="no_verificable"
    detalle="falló aws iam list-attached-role-policies: $(echo "$salida" | tr '\n' ' ')"
  elif jq -e 'index("arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore") != null' <<< "$salida" >/dev/null; then
    estado="aprobado"
    detalle="PgGuardian-EC2-Role tiene adjuntas: $(jq -c . <<< "$salida")"
  else
    estado="no_aprobado"
    detalle="no conforme: falta AmazonSSMManagedInstanceCore; adjuntas: $(jq -c . <<< "$salida")"
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Un `NoSuchEntity` (el rol no existe) da `no_verificable`: el stack no está desplegado o falló; se revisa la sección 2.

#### 3.1.2 Verificación del perfil de la Instancia (R10.2)

Se ejecuta en CloudShell. El ID de la Instancia se toma del output `InstanceId` del stack:

```bash
aws cloudformation describe-stacks --stack-name pgguardian --query "Stacks[0].Outputs"
INSTANCE_ID=$(aws cloudformation describe-stacks --stack-name pgguardian \
  --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue" --output text)
```

Consulta directa:

```bash
aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].IamInstanceProfile'
aws iam list-instance-profiles-for-role --role-name PgGuardian-EC2-Role \
  --query 'InstanceProfiles[].Arn'
```

Resultado esperado: el primer comando devuelve un objeto con `Arn` (`arn:aws:iam::<cuenta>:instance-profile/<nombre generado por el stack>`) e `Id`, no `null`; ese `Arn` aparece en la lista del segundo comando, que es la de los perfiles asociados a `PgGuardian-EC2-Role`.

Evaluación automática del criterio:

```bash
(
  criterio="CA-17"; requisito="R10.2"
  if ! iid=$(aws cloudformation describe-stacks --stack-name pgguardian \
       --query "Stacks[0].Outputs[?OutputKey=='InstanceId'].OutputValue" --output text 2>&1) \
     || [[ "$iid" != i-* ]]; then
    estado="no_verificable"
    detalle="no se obtuvo el output InstanceId del stack pgguardian: $(echo "$iid" | tr '\n' ' ')"
  elif ! perfil=$(aws ec2 describe-instances --instance-ids "$iid" \
       --query 'Reservations[0].Instances[0].IamInstanceProfile.Arn' --output text 2>&1); then
    estado="no_verificable"
    detalle="falló aws ec2 describe-instances: $(echo "$perfil" | tr '\n' ' ')"
  elif ! perfiles=$(aws iam list-instance-profiles-for-role --role-name PgGuardian-EC2-Role \
       --query 'InstanceProfiles[].Arn' --output json 2>&1); then
    estado="no_verificable"
    detalle="falló aws iam list-instance-profiles-for-role: $(echo "$perfiles" | tr '\n' ' ')"
  elif [ "$perfil" = "None" ] || [ -z "$perfil" ]; then
    estado="no_aprobado"
    detalle="no conforme: la instancia $iid no tiene perfil de instancia"
  elif jq -e --arg p "$perfil" 'index($p) != null' <<< "$perfiles" >/dev/null; then
    estado="aprobado"
    detalle="la instancia $iid usa $perfil, asociado a PgGuardian-EC2-Role"
  else
    estado="no_aprobado"
    detalle="no conforme: la instancia $iid usa $perfil, que no está en los perfiles de PgGuardian-EC2-Role: $(jq -c . <<< "$perfiles")"
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

#### 3.1.3 Verificación en la Instancia: credenciales del rol y sin claves en disco (R10.2)

Se ejecuta dentro de la Instancia, en una sesión de Session Manager (acceso descrito en la tarea 6.1). La AMI de Ubuntu no trae AWS CLI, así que se consulta IMDSv2 con `curl`. El bloque solo lee: no imprime las credenciales temporales, solo el nombre del rol, el tipo y la fecha de expiración.

```bash
(
  criterio="CA-17"; requisito="R10.2"
  TOKEN=$(curl -sf -X PUT http://169.254.169.254/latest/api/token \
    -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')
  rol=$(curl -sf -H "X-aws-ec2-metadata-token: $TOKEN" \
    http://169.254.169.254/latest/meta-data/iam/security-credentials/)
  tipo=$(curl -sf -H "X-aws-ec2-metadata-token: $TOKEN" \
    "http://169.254.169.254/latest/meta-data/iam/security-credentials/$rol" \
    | jq -r '"\(.Type) expira \(.Expiration)"' 2>/dev/null)
  claves=$(sudo grep -rIlE 'AKIA[0-9A-Z]{16}|aws_secret_access_key|AWS_SECRET_ACCESS_KEY' \
    /etc /root /home /opt /srv 2>/dev/null | tr '\n' ' ')
  if [ -z "$TOKEN" ] || [ -z "$rol" ]; then
    estado="no_verificable"
    detalle="IMDS no devolvió token o rol"
  elif [ "$rol" != "PgGuardian-EC2-Role" ]; then
    estado="no_aprobado"
    detalle="no conforme: IMDS entrega credenciales del rol $rol"
  elif [ -n "$claves" ]; then
    estado="no_aprobado"
    detalle="no conforme: posibles claves de acceso en disco: $claves"
  else
    estado="aprobado"
    detalle="credenciales temporales de $rol por IMDS ($tipo); sin claves de acceso en /etc /root /home /opt /srv"
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Resultado esperado: `estado` `aprobado`, con `PgGuardian-EC2-Role` y tipo `AWS-HMAC`. Si `jq` no está instalado en la Instancia, se instala con `sudo apt-get install -y jq` o se anota la salida de los `curl` a mano. Ante `no_aprobado` por claves en disco, se borra el archivo indicado, se desactiva la clave en IAM y se repite 3.1.3.

Cómo se interpreta 3.1:

| Salida | `estado` | Requisito |
| --- | --- | --- |
| `AmazonSSMManagedInstanceCore` en las políticas adjuntas | `aprobado` | R10.1 |
| El `IamInstanceProfile.Arn` de la Instancia está entre los perfiles de `PgGuardian-EC2-Role` | `aprobado` | R10.2 |
| IMDS entrega credenciales de `PgGuardian-EC2-Role` y no hay claves en disco | `aprobado` | R10.2 |
| Falta la política, la Instancia no tiene perfil o tiene otro, o hay claves en disco | `no_aprobado` | R10.1 / R10.2 |
| El stack, el rol o IMDS no responden | `no_verificable` | — |

CA-17 queda aprobado para el rol solo si 3.1.1, 3.1.2 y 3.1.3 están en `aprobado`. La parte de CA-17 sobre el registro `Online` en Systems Manager (R10.3, R10.4) se verifica en 3.4.3.

### 3.2 Preparación: outputs del stack e identificadores (T-12 a T-15)

Las verificaciones de 3.3 a 3.8 usan los outputs `InstanceId`, `PublicIp` y `SandboxVolumeId` del stack (lectura descrita en 2.2) y tres identificadores que se derivan de ellos. Se cargan una vez por sesión de CloudShell (`us-east-2`, Usuario_IAM con MFA). Los bloques de evaluación son subshells `( ... )` y heredan estas variables y funciones; si la sesión de CloudShell se reinicia, se vuelve a ejecutar este bloque.

```bash
cd PgGuardian-Online
mkdir -p docs/aws/evidencia/instancia
FECHA=$(date -u +%Y%m%dT%H%MZ)
output_stack() {
  aws cloudformation describe-stacks --stack-name pgguardian \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
INSTANCE_ID=$(output_stack InstanceId)
PUBLIC_IP=$(output_stack PublicIp)
SANDBOX_VOLUME_ID=$(output_stack SandboxVolumeId)
ROOT_VOLUME_ID=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --output json \
  | jq -r '.Reservations[0].Instances[0] as $i | $i.BlockDeviceMappings[]
           | select(.DeviceName == $i.RootDeviceName) | .Ebs.VolumeId')
SG_ID=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].SecurityGroups[0].GroupId' --output text)
EIP_ALLOC_ID=$(aws ec2 describe-addresses --public-ips "$PUBLIC_IP" \
  --query 'Addresses[0].AllocationId' --output text)
echo "instancia=$INSTANCE_ID ip=$PUBLIC_IP raiz=$ROOT_VOLUME_ID sandbox=$SANDBOX_VOLUME_ID sg=$SG_ID eip=$EIP_ALLOC_ID"

# Ejecuta un comando en la Instancia por Run Command (lo usa 3.6.3) y devuelve su salida.
# Falla si el comando no termina en Success.
ssm_run() {
  local cid st
  cid=$(aws ssm send-command --instance-ids "$INSTANCE_ID" --document-name AWS-RunShellScript \
    --parameters "$(jq -cn --arg c "$1" '{commands: [$c]}')" \
    --query Command.CommandId --output text 2>/dev/null) || return 1
  aws ssm wait command-executed --command-id "$cid" --instance-id "$INSTANCE_ID" 2>/dev/null
  st=$(aws ssm get-command-invocation --command-id "$cid" --instance-id "$INSTANCE_ID" \
    --query Status --output text 2>/dev/null) || return 1
  [ "$st" = "Success" ] || return 1
  aws ssm get-command-invocation --command-id "$cid" --instance-id "$INSTANCE_ID" \
    --query StandardOutputContent --output text
}
```

Resultado esperado: la línea `echo` muestra los seis valores (`i-...`, una IPv4, dos `vol-...`, `sg-...` y `eipalloc-...`), ninguno vacío ni `None`. Si falta alguno, el stack no está en `CREATE_COMPLETE` o `UPDATE_COMPLETE`; se revisa la sección 2 antes de seguir. Cada bloque de evaluación comprueba de nuevo las variables que usa y da `no_verificable` si falta alguna.

Las líneas «Resultado de verificación» de esta sección se agregan a `docs/aws/evidencia/instancia/verificacion-instancia.jsonl` (p. ej. terminando el bloque con `| tee -a docs/aws/evidencia/instancia/verificacion-instancia.jsonl`). Los bloques que se ejecutan dentro de la Instancia (3.5 y 3.6.2) se copian de la sesión de Session Manager al mismo archivo.

Orden y momento de cada verificación:

| Bloque | Dónde | Cuándo | Modifica algo |
| --- | --- | --- | --- |
| 3.3.1, 3.3.3, 3.4, 3.6.1, 3.7, 3.8.1 | CloudShell | Tras 2.2 | No (3.4.2 envía una solicitud de terminación que debe ser rechazada) |
| 3.5.1 | Instancia (Session Manager) | Tras 2.2 | No |
| 3.5.2, 3.6.2 | Instancia (Session Manager) | Tras `bootstrap_host.sh` (tarea 6.1, sección 4) | No |
| 3.6.3 | CloudShell | Tras la tarea 6.1 | Sí: reinicia la Instancia |
| 3.3.2 | CloudShell | Tras el despliegue (sección 5): sin Caddy escuchando, 80 y 443 aparecen `closed` y no `open` | No |
| 3.8.2 | CloudShell | Cuando el Equipo acepte una caída de unos minutos | Sí: detiene e inicia la Instancia |
| 3.9.1 | CloudShell | Tras 2.2 | No |
| 3.9.2, 3.9.3 | Consola (Session Manager) y CloudShell | Tras 2.2 | No (abre y cierra una sesión) |

### 3.3 Security Group (T-12 · RF-06.1 · CA-18 · R11.1, R12)

Condiciones:

| Condición | Requisito | Verificación |
| --- | --- | --- |
| La Instancia tiene un único Security Group, con exactamente 2 reglas de entrada: TCP/80 y TCP/443 desde `0.0.0.0/0` | R12.1, R12.2 | 3.3.1 |
| 0 reglas de entrada que cubran TCP/22 y 0 reglas IPv6 (`::/0`) | R11.1, R12.2 | 3.3.1 |
| Desde fuera de la VPC, `nmap -Pn -p-` muestra solo 80 y 443 `open`; los 65533 restantes `filtered` o `closed` | R12.3 | 3.3.2 |
| Una conexión TCP a otro puerto agota el tiempo o es rechazada, sin sesión | R12.4 | 3.3.3 |

El Security Group (`AppSecurityGroup`) lo crea la plantilla. Si alguna verificación da `no_aprobado`, la corrección se hace en la plantilla y se aplica con un change set (2.3), nunca editando las reglas en la consola (eso genera *drift*).

#### 3.3.1 Reglas del Security Group (R11.1, R12.1, R12.2)

Consulta directa:

```bash
aws ec2 describe-security-groups --group-ids "$SG_ID" \
  --query 'SecurityGroups[0].IpPermissions' --output json \
  | tee "docs/aws/evidencia/instancia/sg-ingress-$FECHA.json"
aws ec2 describe-security-group-rules --filters Name=group-id,Values="$SG_ID" \
  --query 'SecurityGroupRules[?IsEgress==`false`].[IpProtocol,FromPort,ToPort,CidrIpv4,CidrIpv6]' --output table
```

Resultado esperado: dos filas, `tcp 80 80 0.0.0.0/0 None` y `tcp 443 443 0.0.0.0/0 None`, y en `IpPermissions` ningún `Ipv6Ranges` con contenido.

Evaluación automática del criterio:

```bash
(
  criterio="CA-18"; requisito="R11.1, R12.1, R12.2"
  esperadas='[{"p":"tcp","d":80,"h":80,"v4":"0.0.0.0/0","v6":null,"pl":null,"sg":null},
              {"p":"tcp","d":443,"h":443,"v4":"0.0.0.0/0","v6":null,"pl":null,"sg":null}]'
  if [ -z "$INSTANCE_ID" ] || [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
    estado="no_verificable"; detalle="faltan INSTANCE_ID o SG_ID; ejecutar 3.2"
  elif ! nsg=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
       --query 'length(Reservations[0].Instances[0].SecurityGroups)' --output text 2>&1); then
    estado="no_verificable"; detalle="falló aws ec2 describe-instances: $(echo "$nsg" | tr '\n' ' ')"
  elif ! reglas=$(aws ec2 describe-security-group-rules \
       --filters Name=group-id,Values="$SG_ID" --output json 2>&1); then
    estado="no_verificable"; detalle="falló aws ec2 describe-security-group-rules: $(echo "$reglas" | tr '\n' ' ')"
  else
    entrada=$(jq -c '[.SecurityGroupRules[] | select(.IsEgress == false)
      | {p: .IpProtocol, d: .FromPort, h: .ToPort, v4: (.CidrIpv4 // null), v6: (.CidrIpv6 // null),
         pl: (.PrefixListId // null), sg: (.ReferencedGroupInfo.GroupId // null)}] | sort_by(.d)' <<< "$reglas")
    n=$(jq 'length' <<< "$entrada")
    p22=$(jq '[.[] | select(.p == "-1" or ((.p == "tcp" or .p == "6") and .d <= 22 and .h >= 22))] | length' <<< "$entrada")
    v6=$(jq '[.[] | select(.v6 != null)] | length' <<< "$entrada")
    fallos=()
    [ "$nsg" = "1" ] || fallos+=("la instancia tiene $nsg security groups (se esperaba 1)")
    [ "$n" -eq 2 ] || fallos+=("$n reglas de entrada (se esperaban 2)")
    [ "$p22" -eq 0 ] || fallos+=("$p22 reglas de entrada cubren TCP/22")
    [ "$v6" -eq 0 ] || fallos+=("$v6 reglas de entrada IPv6")
    jq -e --argjson e "$esperadas" '. == ($e | sort_by(.d))' <<< "$entrada" >/dev/null \
      || fallos+=("reglas distintas de TCP/80 y TCP/443 desde 0.0.0.0/0: $entrada")
    if [ ${#fallos[@]} -eq 0 ]; then
      estado="aprobado"
      detalle="$SG_ID: 2 reglas de entrada (tcp/80 y tcp/443 desde 0.0.0.0/0); 0 para TCP/22; 0 IPv6"
    else
      estado="no_aprobado"
      detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

#### 3.3.2 Escaneo de puertos con `nmap` (R12.3)

Se ejecuta después del despliegue (sección 5), porque sin Caddy escuchando la Instancia responde con RST y 80/443 aparecen `closed`. CloudShell (entorno sin VPC) sale a internet por la red de AWS, fuera de la VPC del stack, así que cuenta como red externa; también puede ejecutarse desde el equipo de un integrante con `nmap` instalado. La evidencia formal del Paquete_Evidencia se genera con `scripts/aws/run_nmap.sh` (tarea 9.2); este paso es la verificación de CA-18.

```bash
command -v nmap || sudo dnf install -y nmap
nmap -Pn -p- -T4 --min-rate 1000 -oN "docs/aws/evidencia/instancia/nmap-$FECHA.txt" "$PUBLIC_IP"
```

Resultado esperado (tarda de 1 a 5 minutos):

```text
PORT    STATE SERVICE
80/tcp  open  http
443/tcp open  https
```

con una línea `Not shown: 65533 filtered tcp ports (no-response)` (o `closed`) y `# Nmap done ... (1 host up)` al final del archivo.

Evaluación automática del criterio, sobre el archivo generado:

```bash
(
  criterio="CA-18"; requisito="R12.3"
  f="docs/aws/evidencia/instancia/nmap-$FECHA.txt"
  if [ ! -s "$f" ] || ! grep -q 'Nmap done.*1 host up' "$f"; then
    estado="no_verificable"; detalle="falta la salida completa de nmap en $f o el escaneo no terminó"
  else
    abiertos=$(awk '$1 ~ /^[0-9]+\/tcp$/ && $2 == "open" {split($1, a, "/"); print a[1]}' "$f" | sort -n | paste -sd, -)
    otros=$(awk '$1 ~ /^[0-9]+\/tcp$/ && $2 != "open" && $2 != "closed" && $2 != "filtered" {print $1 "=" $2}' "$f" | paste -sd, -)
    oculto=$(grep -m1 '^Not shown' "$f")
    if [ "$abiertos" = "80,443" ] && [ -z "$otros" ]; then
      estado="aprobado"; detalle="$PUBLIC_IP: abiertos 80,443; ${oculto:-sin línea Not shown}; archivo $f"
    else
      estado="no_aprobado"
      detalle="no conforme: abiertos=${abiertos:-ninguno} (se esperaba 80,443); otros estados=${otros:-ninguno}; archivo $f"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Si 80 o 443 aparecen `closed`, la causa habitual es que la aplicación no está desplegada o Caddy no arrancó (sección 5), no el Security Group. Si aparece otro puerto `open`, se revisa 3.3.1: con las reglas conformes, ningún otro puerto puede quedar abierto desde fuera.

#### 3.3.3 Conexión a un puerto no permitido (R12.4)

Prueba con los puertos de SSH, PostgreSQL, la API interna y RDP. Cada intento espera como máximo 6 segundos:

```bash
(
  criterio="CA-18"; requisito="R12.4"
  if [ -z "$PUBLIC_IP" ]; then
    estado="no_verificable"; detalle="falta PUBLIC_IP; ejecutar 3.2"
  else
    abiertos=(); cerrados=()
    for p in 22 5432 8000 3389; do
      if timeout 6 bash -c "exec 3<>/dev/tcp/$PUBLIC_IP/$p" 2>/dev/null; then
        abiertos+=("$p")
      else
        cerrados+=("$p")
      fi
    done
    if [ ${#abiertos[@]} -eq 0 ]; then
      estado="aprobado"; detalle="$PUBLIC_IP: sin conexión (tiempo agotado o rechazo) en TCP ${cerrados[*]}"
    else
      estado="no_aprobado"; detalle="no conforme: se estableció conexión TCP en ${abiertos[*]}"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Resultado esperado: `aprobado`; cada intento termina por tiempo agotado (el Security Group descarta el paquete). El intento al puerto 22 es la verificación de R11.5; el resto del acceso sin SSH está en 3.9.

Cómo se interpreta 3.3:

| Salida | `estado` | Requisito |
| --- | --- | --- |
| 2 reglas TCP/80 y TCP/443 desde `0.0.0.0/0`, sin TCP/22 ni IPv6 | `aprobado` | R11.1, R12.1, R12.2 |
| `nmap` con solo 80 y 443 `open` | `aprobado` | R12.3 |
| Ninguna conexión a 22, 5432, 8000 ni 3389 | `aprobado` | R12.4 |
| Regla de más, regla para 22, regla IPv6, otro puerto abierto o conexión establecida | `no_aprobado` | R11.1, R12 |
| Falta un identificador, falla la CLI o el escaneo no terminó | `no_verificable` | — |

### 3.4 Instancia: metadatos, protección contra terminación y Systems Manager (T-13 · CA-17, CA-19, CA-20 · R10.3, R10.4, R13.1, R16)

Condiciones:

| Condición | Requisito | Verificación |
| --- | --- | --- |
| `HttpTokens=required`, `HttpEndpoint=enabled` y `HttpPutResponseHopLimit=1` | R13.1 | 3.4.1 |
| `disableApiTermination=true` tras el aprovisionamiento | R16.1, R16.4 | 3.4.2 |
| `terminate-instances` es rechazado con un error que indica la protección y la Instancia sigue en su estado | R16.3 | 3.4.2 |
| La protección se conserva tras un reinicio | R16.2 | 3.6.3 |
| La Instancia aparece `Online` en Systems Manager en un máximo de 300 s desde `running`; si no, se reporta el fallo sin modificar el Rol_EC2 ni los recursos | R10.3, R10.4 | 3.4.3 |

El cifrado de los discos se verifica en 3.6.

#### 3.4.1 Opciones de metadatos (R13.1)

Consulta directa:

```bash
aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].MetadataOptions'
```

Resultado esperado: `"State": "applied"`, `"HttpTokens": "required"`, `"HttpPutResponseHopLimit": 1` y `"HttpEndpoint": "enabled"`.

Evaluación automática del criterio:

```bash
(
  criterio="CA-19"; requisito="R13.1"
  if [ -z "$INSTANCE_ID" ]; then
    estado="no_verificable"; detalle="falta INSTANCE_ID; ejecutar 3.2"
  elif ! md=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
       --query 'Reservations[0].Instances[0].MetadataOptions.[HttpTokens,HttpEndpoint,HttpPutResponseHopLimit,State]' \
       --output text 2>&1); then
    estado="no_verificable"; detalle="falló aws ec2 describe-instances: $(echo "$md" | tr '\n' ' ')"
  else
    read -r tok ep hop st <<< "$md"
    fallos=()
    [ "$tok" = "required" ] || fallos+=("HttpTokens=${tok:-ausente} (se esperaba required)")
    [ "$ep" = "enabled" ] || fallos+=("HttpEndpoint=${ep:-ausente} (se esperaba enabled)")
    [ "$hop" = "1" ] || fallos+=("HttpPutResponseHopLimit=${hop:-ausente} (se esperaba 1)")
    [ "$st" = "applied" ] || fallos+=("State=${st:-ausente} (se esperaba applied)")
    if [ ${#fallos[@]} -eq 0 ]; then
      estado="aprobado"; detalle="$INSTANCE_ID: HttpTokens=required, HttpEndpoint=enabled, HttpPutResponseHopLimit=1"
    else
      estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

#### 3.4.2 Protección contra terminación (R16.1, R16.3, R16.4)

> **Atención.** Este bloque envía una solicitud real de `terminate-instances`. Solo es seguro porque antes comprueba que `disableApiTermination` vale `true` y, si no, no la envía. No se ejecuta `terminate-instances` a mano fuera de este bloque, y no se usa `--dry-run`: `--dry-run` solo comprueba permisos IAM y no prueba la protección.

Consulta directa (solo lectura):

```bash
aws ec2 describe-instance-attribute --instance-id "$INSTANCE_ID" --attribute disableApiTermination
```

Resultado esperado: `"DisableApiTermination": { "Value": true }`.

Evaluación automática del criterio:

```bash
(
  criterio="CA-20"; requisito="R16.1, R16.3, R16.4"
  if [ -z "$INSTANCE_ID" ]; then
    estado="no_verificable"; detalle="falta INSTANCE_ID; ejecutar 3.2"
  elif ! prot=$(aws ec2 describe-instance-attribute --instance-id "$INSTANCE_ID" \
       --attribute disableApiTermination --query 'DisableApiTermination.Value' --output text 2>&1); then
    estado="no_verificable"; detalle="falló aws ec2 describe-instance-attribute: $(echo "$prot" | tr '\n' ' ')"
  elif [ "$prot" != "True" ]; then
    estado="no_aprobado"
    detalle="no conforme: disableApiTermination=${prot:-ausente} (se esperaba true); no se envió terminate-instances"
  else
    antes=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
      --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null)
    if salida=$(aws ec2 terminate-instances --instance-ids "$INSTANCE_ID" 2>&1); then
      estado="no_aprobado"
      detalle="CRÍTICO: terminate-instances fue aceptado: $(echo "$salida" | tr '\n' ' ')"
    elif ! grep -q 'OperationNotPermitted' <<< "$salida"; then
      estado="no_verificable"
      detalle="terminate-instances falló por otra causa (no prueba la protección): $(echo "$salida" | tr '\n' ' ')"
    else
      sleep 10
      despues=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
        --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null)
      if [ -n "$antes" ] && [ "$despues" = "$antes" ]; then
        estado="aprobado"
        detalle="disableApiTermination=true; terminate-instances rechazado con OperationNotPermitted; estado $antes -> $despues"
      else
        estado="no_aprobado"
        detalle="no conforme: terminate-instances rechazado, pero el estado cambió de ${antes:-?} a ${despues:-?}"
      fi
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Resultado esperado: `aprobado`. El error que devuelve AWS tiene la forma `An error occurred (OperationNotPermitted) when calling the TerminateInstances operation: The instance '<id>' may not be terminated. Modify its 'disableApiTermination' instance attribute and try again.`, y la Instancia sigue `running`.

Ante `no_aprobado` por `disableApiTermination` distinto de `true` (R16.4): se reporta la Instancia como no conforme con CA-20 y se revisa la plantilla (`DisableApiTermination: true`) y el *drift* del stack (`aws cloudformation detect-stack-drift --stack-name pgguardian`); el valor se restablece con un change set (2.3). Si el resultado es «CRÍTICO», la Instancia se está terminando: se avisa al Equipo de inmediato, se restaura desde el último Snapshot_Manual (sección 8) y se registra el incidente.

#### 3.4.3 Registro `Online` en Systems Manager en 300 s (R10.3, R10.4)

La medida es válida cuando el bloque se ejecuta justo después de que la Instancia pasa a `running`: tras 2.1.6 en el primer despliegue, o tras `start-instances` (3.8.2 y sección 6). Si la Instancia lleva tiempo encendida, el bloque solo confirma que sigue `Online`.

Consulta directa:

```bash
aws ssm describe-instance-information \
  --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
  --query 'InstanceInformationList[0].[InstanceId,PingStatus,LastPingDateTime,AgentVersion,PlatformName]' --output table
```

Resultado esperado: `PingStatus` igual a `Online`.

Evaluación automática del criterio (espera hasta 300 s):

```bash
(
  criterio="CA-17"; requisito="R10.3, R10.4"
  if [ -z "$INSTANCE_ID" ]; then
    estado="no_verificable"; detalle="falta INSTANCE_ID; ejecutar 3.2"
  elif ! aws ec2 wait instance-running --instance-ids "$INSTANCE_ID" 2>/dev/null; then
    estado="no_verificable"; detalle="la instancia $INSTANCE_ID no llegó a running; revisar la sección 2 o 6"
  else
    SECONDS=0; ping=""
    while :; do
      ping=$(aws ssm describe-instance-information --filters "Key=InstanceIds,Values=$INSTANCE_ID" \
        --query 'InstanceInformationList[0].PingStatus' --output text 2>/dev/null)
      [ "$ping" = "Online" ] && break
      [ "$SECONDS" -ge 300 ] && break
      sleep 10
    done
    if [ "$ping" = "Online" ]; then
      estado="aprobado"; detalle="$INSTANCE_ID Online en Systems Manager a los ${SECONDS} s de comprobar running"
    else
      estado="no_aprobado"
      detalle="no conforme: la instancia $INSTANCE_ID no es administrable por SSM: PingStatus=${ping:-sin registro} tras 300 s; no se modificó el Rol_EC2 ni los recursos"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Ante `no_aprobado` (R10.4) se reporta el fallo y **no** se modifica el Rol_EC2, el perfil ni la Instancia. Se diagnostica solo leyendo: 3.1.1 y 3.1.2 (rol y perfil), la regla de salida del Security Group (`describe-security-groups`, debe permitir todo el tráfico de salida para llegar a los endpoints de SSM), `HttpTokens`/`HttpPutResponseHopLimit` (3.4.1; el agente corre en el host y no se ve afectado) y la salida de consola (`aws ec2 get-console-output --instance-id "$INSTANCE_ID" --latest --output text`). Cualquier corrección se decide con el Equipo y se aplica por change set.

### 3.5 IMDSv2 desde la Instancia y desde un contenedor (T-13 · RF-06.2 · CA-19 · R13.2 a R13.5)

Condiciones:

| Condición | Requisito | Verificación |
| --- | --- | --- |
| `GET /latest/meta-data/` sin token responde 401 sin metadatos | R13.2 | 3.5.1 |
| `PUT /latest/api/token` y `GET` con el token responden 200 con la lista de categorías | R13.3 | 3.5.1 |
| `GET` con un token inválido o expirado responde 401 sin metadatos | R13.4 | 3.5.1 |
| Desde un contenedor en la red bridge, `PUT /latest/api/token` falla o agota el tiempo en ≤ 5 s, y el agente SSM del host sigue `Online` | R13.5 | 3.5.2 y 3.4.3 |

#### 3.5.1 Pruebas 401/200/401 desde la Instancia (R13.2, R13.3, R13.4)

Se ejecuta dentro de la Instancia, en una sesión de Session Manager. Solo lee; no imprime el token. Para el token expirado se pide uno con TTL de 1 s y se usa 3 s después.

```bash
(
  criterio="CA-19"; requisito="R13.2, R13.3, R13.4"
  url=http://169.254.169.254/latest
  tmp=$(mktemp -d); fallos=()
  c1=$(curl -s -m 5 -o "$tmp/1" -w '%{http_code}' "$url/meta-data/")
  tok=$(curl -s -m 5 -X PUT "$url/api/token" -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')
  c2=$(curl -s -m 5 -o "$tmp/2" -w '%{http_code}' -H "X-aws-ec2-metadata-token: $tok" "$url/meta-data/")
  c3=$(curl -s -m 5 -o "$tmp/3" -w '%{http_code}' -H "X-aws-ec2-metadata-token: token-invalido-$RANDOM" "$url/meta-data/")
  tok1=$(curl -s -m 5 -X PUT "$url/api/token" -H 'X-aws-ec2-metadata-token-ttl-seconds: 1')
  sleep 3
  c4=$(curl -s -m 5 -o "$tmp/4" -w '%{http_code}' -H "X-aws-ec2-metadata-token: $tok1" "$url/meta-data/")
  if [ "$c1$c2$c3$c4" = "000000000000" ]; then
    estado="no_verificable"; detalle="IMDS no respondió a ninguna solicitud (HTTP 000)"
  else
    [ "$c1" = "401" ] || fallos+=("sin token: HTTP $c1 (se esperaba 401)")
    grep -q 'ami-id' "$tmp/1" && fallos+=("sin token: el cuerpo trae metadatos")
    { [ -n "$tok" ] && [ "$c2" = "200" ] && grep -qx 'ami-id' "$tmp/2"; } \
      || fallos+=("con token: HTTP $c2 o sin lista de categorías (se esperaba 200 con ami-id)")
    [ "$c3" = "401" ] || fallos+=("token inválido: HTTP $c3 (se esperaba 401)")
    grep -q 'ami-id' "$tmp/3" && fallos+=("token inválido: el cuerpo trae metadatos")
    [ "$c4" = "401" ] || fallos+=("token expirado: HTTP $c4 (se esperaba 401)")
    grep -q 'ami-id' "$tmp/4" && fallos+=("token expirado: el cuerpo trae metadatos")
    if [ ${#fallos[@]} -eq 0 ]; then
      estado="aprobado"; detalle="sin token 401; token válido 200 ($(wc -l < "$tmp/2") categorías); token inválido 401; token expirado 401; sin metadatos en las respuestas 401"
    else
      estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
    fi
  fi
  rm -rf "$tmp"
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Resultado esperado: `aprobado`. Si `jq` no está en la Instancia, se instala con `sudo apt-get install -y jq` (igual que en 3.1.3). Un 200 sin token indica `HttpTokens=optional`: se repite 3.4.1.

#### 3.5.2 IMDS desde un contenedor (R13.5)

Se ejecuta dentro de la Instancia, en Session Manager, después de instalar Docker con `bootstrap_host.sh` (tarea 6.1). La imagen se descarga antes, para que la medida de tiempo no incluya la descarga. El contenedor usa la red bridge por defecto, que añade un salto; con `HttpPutResponseHopLimit=1` la respuesta del `PUT` no llega.

```bash
IMG=curlimages/curl:latest
sudo docker pull "$IMG"
(
  criterio="CA-19"; requisito="R13.5"
  if ! command -v docker >/dev/null; then
    estado="no_verificable"; detalle="Docker no está instalado; repetir tras bootstrap_host.sh (tarea 6.1)"
  else
    SECONDS=0
    codigo=$(sudo docker run --rm "$IMG" -s -m 5 -o /dev/null -w '%{http_code}' -X PUT \
      http://169.254.169.254/latest/api/token -H 'X-aws-ec2-metadata-token-ttl-seconds: 60' 2>/dev/null)
    rc=$?; seg=$SECONDS
    if [ "$rc" -eq 125 ] || [ "$rc" -eq 126 ] || [ "$rc" -eq 127 ]; then
      estado="no_verificable"; detalle="docker run no pudo iniciar el contenedor (código $rc)"
    elif [ "$rc" -ne 0 ] && [ "${codigo:-000}" = "000" ]; then
      estado="aprobado"
      detalle="PUT /latest/api/token desde un contenedor bridge falló (curl código $rc, 28 = tiempo agotado) en ${seg} s con curl -m 5; sin token"
    else
      estado="no_aprobado"
      detalle="no conforme: el contenedor obtuvo respuesta HTTP $codigo (curl código $rc); revisar HttpPutResponseHopLimit en 3.4.1"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Resultado esperado: `aprobado` con curl código 28 (tiempo agotado). `curl -m 5` limita la solicitud a 5 s; los segundos del `detalle` incluyen además el arranque del contenedor (1 o 2 s). Justo después, en CloudShell, se repite 3.4.3: el agente SSM corre en el host, no en un contenedor, y debe seguir `Online`. R13.5 queda aprobado solo con las dos líneas en `aprobado`.

### 3.6 Volúmenes cifrados y montaje del Volumen_Sandbox (T-13, T-14 · RF-06.3, RF-04.4 · CA-20, CA-12 · R4.6, R14)

Condiciones:

| Condición | Requisito | Verificación |
| --- | --- | --- |
| Disco raíz gp3 de 20 GB con `Encrypted=true` | R14.1 | 3.6.1 |
| Volumen_Sandbox gp3 de 8 GB con `Encrypted=true`, adjunto en `/dev/sdf` | R14.2 | 3.6.1 |
| Ningún volumen sin cifrar adjunto a la Instancia | R14.5 | 3.6.1 |
| `df -h /srv/sandbox` muestra un dispositivo distinto de `df -h /`, y es el Volumen_Sandbox | R4.6, R14.2 | 3.6.2 |
| Tras un reinicio, la Instancia vuelve en ≤ 300 s con ambos volúmenes cifrados, `/srv/sandbox` montado y `disableApiTermination=true` | R14.3, R16.2 | 3.6.3 |
| Si no vuelve en 300 s o `/srv/sandbox` no está montado, los datos de ambos volúmenes se conservan sin tocarlos y R14.3 se da por fallido | R14.4 | 3.6.3 |

#### 3.6.1 Tipo, tamaño y cifrado (R14.1, R14.2, R14.5)

Consulta directa:

```bash
aws ec2 describe-volumes --filters Name=attachment.instance-id,Values="$INSTANCE_ID" \
  --query 'Volumes[].[VolumeId,VolumeType,Size,Encrypted,Attachments[0].Device,Attachments[0].State]' --output table \
  | tee "docs/aws/evidencia/instancia/volumes-$FECHA.txt"
```

Resultado esperado: dos filas, `<ROOT_VOLUME_ID> gp3 20 True /dev/sda1 attached` y `<SANDBOX_VOLUME_ID> gp3 8 True /dev/sdf attached`.

Evaluación automática del criterio:

```bash
(
  criterio="CA-20"; requisito="R14.1, R14.2, R14.5"
  if [ -z "$INSTANCE_ID" ] || [ -z "$ROOT_VOLUME_ID" ] || [ -z "$SANDBOX_VOLUME_ID" ]; then
    estado="no_verificable"; detalle="faltan INSTANCE_ID, ROOT_VOLUME_ID o SANDBOX_VOLUME_ID; ejecutar 3.2"
  elif ! vols=$(aws ec2 describe-volumes --filters Name=attachment.instance-id,Values="$INSTANCE_ID" \
       --output json 2>&1); then
    estado="no_verificable"; detalle="falló aws ec2 describe-volumes: $(echo "$vols" | tr '\n' ' ')"
  else
    resumen=$(jq -c '[.Volumes[] | {id: .VolumeId, tipo: .VolumeType, gb: .Size, cifrado: .Encrypted,
                     dev: .Attachments[0].Device, estado: .Attachments[0].State}]' <<< "$vols")
    raiz=$(jq -c --arg v "$ROOT_VOLUME_ID" '(map(select(.id == $v)) | .[0]) // {}' <<< "$resumen")
    sb=$(jq -c --arg v "$SANDBOX_VOLUME_ID" '(map(select(.id == $v)) | .[0]) // {}' <<< "$resumen")
    n=$(jq 'length' <<< "$resumen")
    sin_cifrar=$(jq -c '[.[] | select(.cifrado != true) | .id]' <<< "$resumen")
    fallos=()
    jq -e '.tipo == "gp3" and .gb == 20 and .cifrado == true' <<< "$raiz" >/dev/null \
      || fallos+=("disco raíz $raiz (se esperaba gp3, 20 GB, cifrado)")
    jq -e '.tipo == "gp3" and .gb == 8 and .cifrado == true and .dev == "/dev/sdf" and .estado == "attached"' <<< "$sb" >/dev/null \
      || fallos+=("Volumen_Sandbox $sb (se esperaba gp3, 8 GB, cifrado, /dev/sdf, attached)")
    [ "$sin_cifrar" = "[]" ] || fallos+=("volúmenes sin cifrar adjuntos: $sin_cifrar")
    [ "$n" -eq 2 ] || fallos+=("$n volúmenes adjuntos (se esperaban 2): $resumen")
    if [ ${#fallos[@]} -eq 0 ]; then
      estado="aprobado"; detalle="raíz $ROOT_VOLUME_ID gp3 20 GB cifrado; sandbox $SANDBOX_VOLUME_ID gp3 8 GB cifrado en /dev/sdf; 0 volúmenes sin cifrar"
    else
      estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Un volumen con `Encrypted=false` adjunto a la Instancia hace que la Instancia sea no conforme (R14.5). El cifrado de un volumen EBS no se puede activar en el sitio: se informa al Equipo, se desadjunta el volumen ajeno al stack o, si es uno de los dos del stack, se corrige la plantilla y se recrea con un change set revisado (con snapshot previo, sección 8).

#### 3.6.2 Montaje del Volumen_Sandbox en un dispositivo propio (R4.6, R14.2)

Se ejecuta dentro de la Instancia, en Session Manager, después de `bootstrap_host.sh` (tarea 6.1), que formatea y monta el volumen. Antes de pegar el bloque se define el ID del Volumen_Sandbox copiándolo de CloudShell (`echo $SANDBOX_VOLUME_ID`). En una t3.small (Nitro), el attachment `/dev/sdf` aparece como un dispositivo NVMe; se identifica por su enlace en `/dev/disk/by-id/`.

Consulta directa:

```bash
df -h /srv/sandbox
df -h /
findmnt /srv/sandbox
```

Resultado esperado: `/srv/sandbox` en un dispositivo NVMe (p. ej. `/dev/nvme1n1`) de unos 8 GB, y `/` en otro (p. ej. `/dev/nvme0n1p1` o `/dev/root`) de unos 20 GB.

Evaluación automática del criterio:

```bash
SANDBOX_VOLUME_ID=vol-xxxxxxxxxxxxxxxxx   # valor copiado de CloudShell
(
  criterio="CA-12"; requisito="R4.6, R14.2"
  enlace="/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_${SANDBOX_VOLUME_ID//-/}"
  disp=$(readlink -f "$enlace" 2>/dev/null)
  mnt=$(findmnt -n -o SOURCE /srv/sandbox 2>/dev/null)
  raiz=$(findmnt -n -o SOURCE / 2>/dev/null)
  if [[ "$SANDBOX_VOLUME_ID" != vol-* ]] || [[ "$SANDBOX_VOLUME_ID" == *x* ]]; then
    estado="no_verificable"; detalle="SANDBOX_VOLUME_ID no está definido con el valor real"
  elif [ -z "$disp" ] || [ ! -b "$disp" ]; then
    estado="no_aprobado"; detalle="no conforme: no se encontró el dispositivo del Volumen_Sandbox ($enlace)"
  elif [ -z "$mnt" ]; then
    estado="no_aprobado"; detalle="no conforme: /srv/sandbox no es un punto de montaje (¿se ejecutó bootstrap_host.sh?)"
  elif [ "$(readlink -f "$mnt")" != "$disp" ]; then
    estado="no_aprobado"; detalle="no conforme: /srv/sandbox está montado desde $mnt, no desde el Volumen_Sandbox ($disp)"
  elif [ "$(readlink -f "$mnt")" = "$(readlink -f "$raiz")" ]; then
    estado="no_aprobado"; detalle="no conforme: /srv/sandbox y / están en el mismo dispositivo ($mnt)"
  else
    estado="aprobado"
    detalle="/srv/sandbox en $mnt (Volumen_Sandbox $SANDBOX_VOLUME_ID, $(df -h --output=size /srv/sandbox | tail -n1 | tr -d ' ')); / en $raiz"
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

El resto de CA-12 (`SANDBOX_DATA_DIR`, `findmnt` por UUID tras reinicio, volumen ausente y prueba de llenado) se verifica en la sección 4 (tarea 6.1).

#### 3.6.3 Reinicio: cifrado, montaje y protección (R14.3, R14.4, R16.2, modifica: reinicia la Instancia)

> **Atención.** Este bloque reinicia la Instancia; la aplicación deja de responder uno o dos minutos. Se avisa al Equipo antes. Se ejecuta después de la tarea 6.1, para que `/srv/sandbox` esté en `/etc/fstab`.

El reinicio equivale a `sudo reboot` dentro de la Instancia: el bloque usa `aws ec2 reboot-instances`, que reinicia el sistema operativo sin cambiar el estado EC2 (`running`). Para saber cuándo volvió, compara el `boot_id` del kernel antes y después, leído por Run Command con la función `ssm_run` de 3.2. Si se prefiere `sudo reboot` desde Session Manager, se lee el `boot_id` antes (`cat /proc/sys/kernel/random/boot_id`), se reinicia y se ejecuta el mismo bloque saltando el `reboot-instances`.

```bash
(
  criterio="CA-20"; requisito="R14.3, R14.4, R16.2"
  if [ -z "$INSTANCE_ID" ] || ! declare -F ssm_run >/dev/null; then
    estado="no_verificable"; detalle="faltan INSTANCE_ID o ssm_run; ejecutar 3.2"
  elif ! boot0=$(ssm_run 'cat /proc/sys/kernel/random/boot_id') || [ -z "$boot0" ]; then
    estado="no_verificable"; detalle="no se pudo leer boot_id por Run Command antes del reinicio; revisar 3.4.3"
  elif ! err=$(aws ec2 reboot-instances --instance-ids "$INSTANCE_ID" 2>&1); then
    estado="no_verificable"; detalle="falló aws ec2 reboot-instances: $(echo "$err" | tr '\n' ' ')"
  else
    SECONDS=0; boot1=""; volvio=""
    sleep 20
    while [ "$SECONDS" -lt 300 ]; do
      if boot1=$(ssm_run 'cat /proc/sys/kernel/random/boot_id' 2>/dev/null) \
         && [ -n "$boot1" ] && [ "$boot1" != "$boot0" ]; then
        volvio="si"; break
      fi
      sleep 10
    done
    seg=$SECONDS
    st=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
      --query 'Reservations[0].Instances[0].State.Name' --output text 2>/dev/null)
    if [ -z "$volvio" ] || [ "$seg" -gt 300 ]; then
      estado="no_aprobado"
      detalle="no conforme: la instancia no volvió en 300 s (estado EC2 ${st:-?}, ${seg} s); no se tocaron los volúmenes (R14.4)"
    else
      fallos=()
      mnt=$(ssm_run 'findmnt -n -o SOURCE /srv/sandbox; findmnt -n -o SOURCE /' 2>/dev/null)
      m_sb=$(sed -n 1p <<< "$mnt"); m_raiz=$(sed -n 2p <<< "$mnt")
      cifr=$(aws ec2 describe-volumes --filters Name=attachment.instance-id,Values="$INSTANCE_ID" \
        --query 'Volumes[].Encrypted' --output text 2>/dev/null)
      prot=$(aws ec2 describe-instance-attribute --instance-id "$INSTANCE_ID" \
        --attribute disableApiTermination --query 'DisableApiTermination.Value' --output text 2>/dev/null)
      [ "$st" = "running" ] || fallos+=("estado EC2 $st (se esperaba running)")
      { [ -n "$m_sb" ] && [ "$m_sb" != "$m_raiz" ]; } || fallos+=("/srv/sandbox no montado tras el reinicio (findmnt: ${m_sb:-vacío}) (R14.4)")
      { [ -n "$cifr" ] && ! grep -qw False <<< "$cifr"; } || fallos+=("Encrypted tras el reinicio: ${cifr:-sin datos}")
      [ "$prot" = "True" ] || fallos+=("disableApiTermination=${prot:-ausente} tras el reinicio (R16.2)")
      if [ ${#fallos[@]} -eq 0 ]; then
        estado="aprobado"
        detalle="reinicio completado en ${seg} s; running; /srv/sandbox montado desde $m_sb (/ en $m_raiz); volúmenes cifrados; disableApiTermination=true"
      else
        estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
      fi
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Resultado esperado: `aprobado`, normalmente con 40 a 120 s. Cada intento de `ssm_run` mientras la Instancia arranca puede tardar hasta unos 100 s en fallar, por eso el bloque puede terminar algo después de los 300 s; en ese caso el `detalle` lo indica y el criterio queda `no_aprobado`, y se repite una vez para descartar el retraso de Run Command.

Ante `no_aprobado` (R14.4): R14.3 se da por fallido y los volúmenes **no se tocan**: no se desadjuntan, no se formatean, no se fuerza la detención (`stop-instances --force`) ni se termina la Instancia. Se diagnostica leyendo la salida de consola (`aws ec2 get-console-output --instance-id "$INSTANCE_ID" --latest --output text`) y, cuando la Instancia responda, `findmnt /srv/sandbox` y `/etc/fstab` en Session Manager. La entrada `nofail` de `/etc/fstab` (tarea 6.1) permite que el sistema arranque aunque el volumen falte. Se registra la causa en el `detalle` y se repite 3.6.3 tras corregirla.

### 3.7 Etiquetas (T-13, T-14, T-15 · RF-06.6 · CA-21 · R17)

Condiciones:

| Condición | Requisito | Verificación |
| --- | --- | --- |
| La Instancia tiene `Project=PgGuardian`, `Env=prod` y `Owner` de 1 a 256 caracteres | R17.1 | 3.7.1 |
| El disco raíz, el Volumen_Sandbox y la Elastic IP tienen las mismas tres etiquetas | R17.2 | 3.7.1 |
| Un `Owner` vacío, ausente o de más de 256 caracteres se trata como no conforme y se corrige solo esa etiqueta | R17.3 | 3.7.1 |

La plantilla asigna las etiquetas a la Instancia, al Volumen_Sandbox y a la Elastic IP, y el disco raíz las hereda al crearse (`PropagateTagsToVolumeOnCreation: true`).

#### 3.7.1 Etiquetas de los cuatro recursos (R17.1, R17.2, R17.3)

Consulta directa:

```bash
aws ec2 describe-tags \
  --filters "Name=resource-id,Values=$INSTANCE_ID,$ROOT_VOLUME_ID,$SANDBOX_VOLUME_ID,$EIP_ALLOC_ID" \
            "Name=key,Values=Project,Env,Owner" \
  --query 'Tags[].[ResourceType,ResourceId,Key,Value]' --output table \
  | tee "docs/aws/evidencia/instancia/tags-$FECHA.txt"
```

Resultado esperado: 12 filas, tres por recurso (`instance`, dos `volume` y `elastic-ip`), con `Project=PgGuardian`, `Env=prod` y el mismo `Owner`.

Evaluación automática del criterio:

```bash
(
  criterio="CA-21"; requisito="R17.1, R17.2, R17.3"
  ids=("$INSTANCE_ID" "$ROOT_VOLUME_ID" "$SANDBOX_VOLUME_ID" "$EIP_ALLOC_ID")
  nombres=("instancia" "disco raíz" "Volumen_Sandbox" "Elastic IP")
  vacios=""
  for i in 0 1 2 3; do { [ -z "${ids[$i]}" ] || [ "${ids[$i]}" = "None" ]; } && vacios="$vacios ${nombres[$i]}"; done
  if [ -n "$vacios" ]; then
    estado="no_verificable"; detalle="faltan identificadores:$vacios; ejecutar 3.2"
  elif ! tags=$(aws ec2 describe-tags \
       --filters "Name=resource-id,Values=$(IFS=,; echo "${ids[*]}")" --output json 2>&1); then
    estado="no_verificable"; detalle="falló aws ec2 describe-tags: $(echo "$tags" | tr '\n' ' ')"
  else
    fallos=()
    t() { jq -r --arg r "$1" --arg k "$2" '[.Tags[] | select(.ResourceId == $r and .Key == $k) | .Value][0] // ""' <<< "$tags"; }
    for i in 0 1 2 3; do
      r=${ids[$i]}; nom=${nombres[$i]}
      p=$(t "$r" Project); e=$(t "$r" Env); o=$(t "$r" Owner)
      [ "$p" = "PgGuardian" ] || fallos+=("$nom $r: Project=${p:-ausente}")
      [ "$e" = "prod" ] || fallos+=("$nom $r: Env=${e:-ausente}")
      if [ ${#o} -lt 1 ] || [ ${#o} -gt 256 ]; then
        fallos+=("$nom $r: etiqueta Owner inválida (longitud ${#o}, se esperaba de 1 a 256)")
      fi
    done
    if [ ${#fallos[@]} -eq 0 ]; then
      estado="aprobado"; detalle="instancia, disco raíz, Volumen_Sandbox y Elastic IP con Project=PgGuardian, Env=prod y Owner=$(t "$INSTANCE_ID" Owner)"
    else
      estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Corrección ante `no_aprobado` (R17.3), cambiando solo la etiqueta:

- Instancia, Volumen_Sandbox o Elastic IP: se cambia el parámetro `Owner` con un change set de actualización (2.3, `ParameterKey=Owner,ParameterValue=<valor>` y el resto con `UsePreviousValue=true`). Cambiar solo etiquetas no reemplaza recursos; si la tabla del change set muestra `Replacement=True`, no se ejecuta. No se usa `create-tags` sobre estos tres recursos, porque generaría *drift*.
- Disco raíz: no es un recurso propio del stack y `PropagateTagsToVolumeOnCreation` solo actúa al crear la Instancia, así que un cambio posterior de `Owner` no le llega. Se corrige solo esa etiqueta con `aws ec2 create-tags --resources "$ROOT_VOLUME_ID" --tags Key=Owner,Value=<valor>` (y `Project`/`Env` si faltan).

Después se repite 3.7.1.

### 3.8 Elastic IP (T-15 · RF-06.8, RF-03.1 · CA-23 · R19.1)

Condición: la IP pública de la Instancia es la Elastic IP del output `PublicIp`, que sigue asociada a la Instancia, antes y después de detener e iniciar la Instancia (R19.1). La recuperación completa de la aplicación tras encender (R19.8) se verifica en la sección 6.

#### 3.8.1 Comprobación de la asociación (R19.1)

Consulta directa:

```bash
aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].[State.Name,PublicIpAddress]' --output text
aws ec2 describe-addresses --public-ips "$PUBLIC_IP" \
  --query 'Addresses[0].[PublicIp,AllocationId,AssociationId,InstanceId]' --output text
```

Resultado esperado: `running <PublicIp>` y, en la segunda línea, la misma IP con `eipalloc-...`, `eipassoc-...` y el `InstanceId` del stack.

Evaluación automática del criterio. `MOMENTO` vale `antes` o `despues` según se ejecute antes o después de 3.8.2:

```bash
MOMENTO=antes   # en 3.8.2 se vuelve a ejecutar con MOMENTO=despues
(
  criterio="CA-23"; requisito="R19.1 ($MOMENTO de detener e iniciar)"
  if [ -z "$INSTANCE_ID" ] || [ -z "$PUBLIC_IP" ]; then
    estado="no_verificable"; detalle="faltan INSTANCE_ID o PUBLIC_IP; ejecutar 3.2"
  elif ! inst=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
       --query 'Reservations[0].Instances[0].[State.Name,PublicIpAddress]' --output text 2>&1); then
    estado="no_verificable"; detalle="falló aws ec2 describe-instances: $(echo "$inst" | tr '\n' ' ')"
  elif ! addr=$(aws ec2 describe-addresses --public-ips "$PUBLIC_IP" \
       --query 'Addresses[0].[InstanceId,AllocationId]' --output text 2>&1); then
    estado="no_verificable"; detalle="falló aws ec2 describe-addresses (¿se liberó la Elastic IP?): $(echo "$addr" | tr '\n' ' ')"
  else
    read -r st ip <<< "$inst"; read -r asoc alloc <<< "$addr"
    fallos=()
    [ "$st" = "running" ] || fallos+=("estado $st (se esperaba running)")
    [ "$ip" = "$PUBLIC_IP" ] || fallos+=("IP pública de la instancia ${ip:-ninguna} distinta de PublicIp $PUBLIC_IP")
    [ "$asoc" = "$INSTANCE_ID" ] || fallos+=("la Elastic IP $PUBLIC_IP está asociada a ${asoc:-ninguna instancia}")
    if [ ${#fallos[@]} -eq 0 ]; then
      estado="aprobado"; detalle="$INSTANCE_ID running con IP pública $PUBLIC_IP = Elastic IP $alloc asociada a la instancia"
    else
      estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

#### 3.8.2 Detener e iniciar (R19.1, modifica: detiene la Instancia)

> **Atención.** La aplicación no responde mientras la Instancia está detenida (unos 2 a 4 minutos). Se avisa al Equipo antes. No se usa `--force`.

```bash
aws ec2 stop-instances --instance-ids "$INSTANCE_ID"
aws ec2 wait instance-stopped --instance-ids "$INSTANCE_ID"
aws ec2 describe-addresses --public-ips "$PUBLIC_IP" --query 'Addresses[0].InstanceId' --output text
aws ec2 start-instances --instance-ids "$INSTANCE_ID"
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
```

Resultado esperado: con la Instancia detenida, la tercera línea sigue mostrando el `InstanceId` (la Elastic IP no se desasocia al detener). Después de `instance-running` se repite 3.8.1 con `MOMENTO=despues` y, como la Instancia acaba de pasar a `running`, también 3.4.3 (R10.3). R19.1 queda aprobado solo con las líneas `antes` y `despues` en `aprobado`. Si la IP cambia, se revisa que la Elastic IP no se haya liberado ni desasociado (`describe-addresses`) y se restablece la asociación con un change set del stack, no a mano.

### 3.9 Acceso sin SSH y Session Manager (T-16 · RF-05.5 · CA-17, CA-18 · R11)

Condiciones:

| Condición | Requisito | Verificación |
| --- | --- | --- |
| La Instancia no tiene par de llaves: `KeyName` vacío o ausente en `describe-instances` | R11.2, R11.4 | 3.9.1 |
| El Security Group no tiene ninguna regla de entrada que cubra TCP/22 (ni IPv4, ni IPv6, ni otro origen) | R11.1, R11.4 | 3.9.1 (y 3.3.1) |
| Un intento de SSH al puerto 22 no establece sesión | R11.5 | 3.3.3 (puerto 22) |
| Un Usuario_IAM abre una consola interactiva por Session Manager en ≤ 30 s | R11.3 | 3.9.2 |
| CloudTrail registra `StartSession` con ese Usuario_IAM y la Instancia en ≤ 15 min | R11.3 | 3.9.3 |

No hay llave `.pem` que repartir ni puerto 22 que abrir: toda la administración de la Instancia (secciones 4 y 5) pasa por Session Manager. Si alguna verificación da `no_aprobado`, la corrección va en la plantilla y se aplica con un change set (2.3).

#### 3.9.1 Sin par de llaves y sin TCP/22 (R11.1, R11.2, R11.4)

Consulta directa:

```bash
aws ec2 describe-instances --instance-ids "$INSTANCE_ID" \
  --query 'Reservations[0].Instances[0].KeyName' --output text
aws ec2 describe-security-groups --group-ids "$SG_ID" \
  --query 'SecurityGroups[0].IpPermissions[].[IpProtocol,FromPort,ToPort]' --output text
```

Resultado esperado: el primer comando imprime `None` (el campo `KeyName` no existe); el segundo, solo `tcp 80 80` y `tcp 443 443`.

Evaluación automática del criterio:

```bash
(
  criterio="CA-18"; requisito="R11.1, R11.2, R11.4"
  if [ -z "$INSTANCE_ID" ] || [ -z "$SG_ID" ] || [ "$SG_ID" = "None" ]; then
    estado="no_verificable"; detalle="faltan INSTANCE_ID o SG_ID; ejecutar 3.2"
  elif ! inst=$(aws ec2 describe-instances --instance-ids "$INSTANCE_ID" --output json 2>&1); then
    estado="no_verificable"; detalle="falló aws ec2 describe-instances: $(echo "$inst" | tr '\n' ' ')"
  elif ! sg=$(aws ec2 describe-security-groups --group-ids "$SG_ID" --output json 2>&1); then
    estado="no_verificable"; detalle="falló aws ec2 describe-security-groups: $(echo "$sg" | tr '\n' ' ')"
  else
    llave=$(jq -r '.Reservations[0].Instances[0].KeyName // ""' <<< "$inst")
    p22=$(jq -c '[.SecurityGroups[0].IpPermissions[]
                  | select(.IpProtocol == "-1" or ((.IpProtocol == "tcp" or .IpProtocol == "6")
                           and .FromPort <= 22 and .ToPort >= 22))]' <<< "$sg")
    fallos=()
    [ -z "$llave" ] || fallos+=("la instancia tiene el par de llaves '$llave'")
    [ "$p22" = "[]" ] || fallos+=("reglas de entrada que cubren TCP/22: $p22")
    if [ ${#fallos[@]} -eq 0 ]; then
      estado="aprobado"; detalle="$INSTANCE_ID sin KeyName; $SG_ID sin reglas de entrada para TCP/22"
    else
      estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

El par de llaves no se puede quitar de una instancia existente. Si apareciera un `KeyName`, se revisa la plantilla (la propiedad `KeyName` no debe existir en `Instance`); el cambio reemplaza la Instancia, así que se decide con el Equipo y se toma antes un snapshot de ambos discos (sección 8).

#### 3.9.2 Sesión de Session Manager (R11.3, paso manual)

Lo hace un Usuario_IAM de `PgG-Admins` con MFA. Antes de abrir la sesión, en CloudShell se guarda la hora de inicio y el ARN del usuario, que usa 3.9.3:

```bash
INICIO_SESION=$(date -u +%Y-%m-%dT%H:%M:%SZ)
USUARIO_ARN=$(aws sts get-caller-identity --query Arn --output text)
echo "inicio=$INICIO_SESION usuario=$USUARIO_ARN instancia=$INSTANCE_ID"
```

1. En la consola, abrir **EC2** → **Instances**, seleccionar la Instancia (`InstanceId` del stack) → **Connect** → pestaña **Session Manager** → **Connect**. También sirve **Systems Manager** → **Session Manager** → **Start session**.
2. Medir con un cronómetro desde el clic en **Connect** hasta que aparece el prompt (`$`). Debe ser ≤ 30 s.
3. Session Manager abre `sh` como `ssm-user`. Para trabajar como en el resto del runbook:

   ```sh
   sudo -iu ubuntu bash
   whoami; hostname; cat /proc/sys/kernel/random/boot_id
   ```

4. Guardar una captura con la URL de la consola, el `InstanceId` y la salida de `whoami` (`ubuntu`). Cerrar la sesión con **Terminate**.

Línea de resultado (a mano):

```json
{"criterio":"CA-17","requisito":"R11.3","estado":"aprobado","detalle":"<usuario> abrió Session Manager en <i-...> en <n> s (≤ 30 s); captura <archivo>"}
```

Si tarda más de 30 s o no abre, se anota `no_aprobado` y se revisa 3.4.3 (la Instancia debe estar `Online` en Systems Manager).

#### 3.9.3 Evento `StartSession` en CloudTrail (R11.3)

CloudTrail registra `StartSession` sin configuración adicional, con hasta 15 minutos de retraso. El bloque consulta cada 60 s durante 15 min como máximo; usa `INICIO_SESION` y `USUARIO_ARN` de 3.9.2 (misma sesión de CloudShell):

```bash
(
  criterio="CA-17"; requisito="R11.3"
  if [ -z "$INSTANCE_ID" ] || [ -z "$INICIO_SESION" ] || [ -z "$USUARIO_ARN" ]; then
    estado="no_verificable"; detalle="faltan INSTANCE_ID, INICIO_SESION o USUARIO_ARN; ejecutar 3.2 y 3.9.2"
  else
    estado=""; evento=""; SECONDS=0
    while [ "$SECONDS" -le 900 ]; do
      if ! ev=$(aws cloudtrail lookup-events --region us-east-2 \
           --lookup-attributes AttributeKey=EventName,AttributeValue=StartSession \
           --start-time "$INICIO_SESION" --output json 2>&1); then
        estado="no_verificable"; detalle="falló aws cloudtrail lookup-events: $(echo "$ev" | tr '\n' ' ')"
        break
      fi
      evento=$(jq -c --arg i "$INSTANCE_ID" --arg u "$USUARIO_ARN" '
        [.Events[] | .CloudTrailEvent | fromjson
         | select(.requestParameters.target == $i and .userIdentity.arn == $u)
         | {hora: .eventTime, usuario: .userIdentity.arn, instancia: .requestParameters.target,
            sesion: (.responseElements.sessionId // "")}] | first // empty' <<< "$ev")
      [ -n "$evento" ] && break
      sleep 60
    done
    if [ -z "$estado" ]; then
      if [ -n "$evento" ]; then
        estado="aprobado"; detalle="StartSession en CloudTrail tras ${SECONDS} s de consulta: $evento"
      else
        estado="no_aprobado"
        detalle="no conforme: ningún StartSession de $USUARIO_ARN hacia $INSTANCE_ID desde $INICIO_SESION en 15 min"
      fi
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Resultado esperado: `aprobado`, con la hora del evento, el ARN del Usuario_IAM, el `InstanceId` y el ID de la sesión. El `detalle` cuenta el tiempo de consulta, no el retraso real de CloudTrail; el criterio exige que el evento aparezca en ≤ 15 min.

Cómo se interpreta 3.9:

| Salida | `estado` | Requisito |
| --- | --- | --- |
| Sin `KeyName` y sin reglas para TCP/22 | `aprobado` | R11.1, R11.2, R11.4 |
| Sesión abierta en ≤ 30 s | `aprobado` | R11.3 |
| Evento `StartSession` del usuario hacia la Instancia en ≤ 15 min | `aprobado` | R11.3 |
| Par de llaves presente, regla para TCP/22, sesión en más de 30 s o sin evento en 15 min | `no_aprobado` | R11 |
| Falta una variable o falla la CLI | `no_verificable` | — |

### 3.10 Resumen de la sección 3

| Criterio | Bloques de esta sección que deben estar en `aprobado` | Partes que se verifican en otras secciones |
| --- | --- | --- |
| CA-12 | 3.6.2 | `SANDBOX_DATA_DIR`, `findmnt` por UUID tras reinicio, volumen ausente y llenado (sección 4) |
| CA-17 | 3.1.1, 3.1.2, 3.1.3, 3.4.3 (y su repetición en 3.5.2 y 3.8.2), 3.9.2, 3.9.3 | — |
| CA-18 | 3.3.1, 3.3.2, 3.3.3, 3.9.1 | — |
| CA-19 | 3.4.1, 3.5.1, 3.5.2 | — |
| CA-20 | 3.4.2, 3.6.1, 3.6.3 | Swap (sección 4) |
| CA-21 | 3.7.1 | — |
| CA-23 | 3.8.1 (`antes` y `despues`) | Certificado, redirección y HTTPS (sección 5); aplicación tras encender (sección 6) |

Un criterio nunca se da por aprobado con un bloque en `no_aprobado` o `no_verificable`: se corrige la causa y se repite el bloque, conservando la línea anterior en la evidencia.

## 4. Host

Trazabilidad: componente C9 del diseño · T-16 · RF-04.4, RF-06.3, RF-06.4, RF-06.7 · CA-12, CA-20, CA-22 · R4.2, R4.4 a R4.10, R15, R18 y R19.8.

La plantilla no lleva `UserData`. El host se configura a mano con `scripts/aws/bootstrap_host.sh`, ejecutado por Session Manager. El script es idempotente: se puede repetir sin formatear el disco, sin duplicar entradas en `/etc/fstab` y sin crear un segundo swap.

Condiciones:

| Condición | Requisito | Verificación |
| --- | --- | --- |
| Volumen_Sandbox con ext4, montado en `/srv/sandbox` por UUID desde `/etc/fstab` con `nofail`, también tras reiniciar | R4.5, R4.7 | 4.3 |
| `/srv/sandbox/pgdata` existe, es de `999:999` y está en el Volumen_Sandbox (no en `/`); `lost+found` queda en `/srv/sandbox` | R4.2, R4.9 | 4.3, 4.4 |
| `SANDBOX_DATA_DIR=/srv/sandbox/pgdata` en el `.env` del servidor y `sandbox_db` montado desde esa ruta | R4.4 | 4.4 |
| Exactamente un swap de 2 GiB (±1 MiB), activo sin intervención tras 3 reinicios | R15.1 a R15.3 | 4.5, 4.6 |
| `unattended-upgrades` instalado, `active` y `enabled`, solo con el origen `-security`, y `20auto-upgrades` con `"1"` y `"1"` | R18.1 a R18.4 | 4.7.1 |
| Servicio `docker` habilitado al arranque | R19.8 | 4.7.2 |
| Con el Volumen_Sandbox lleno al 100 %, login e historial responden en ≤ 3 s y `/` varía ≤ 1 punto porcentual | R4.10 | 4.8 |
| Sin el Volumen_Sandbox, el SO arranca, `sandbox_db` no arranca y `/srv/sandbox/pgdata` no aparece en el disco raíz | R4.8 | 4.9 |

Orden y momento:

| Bloque | Dónde | Cuándo | Modifica algo |
| --- | --- | --- | --- |
| 4.1, 4.2 | Instancia (Session Manager) | Tras 2.2 y 3.9 | Sí: configura el host |
| 4.3, 4.5, 4.7 | Instancia (Session Manager) | Tras 4.1; 4.3 se repite tras el reinicio de 3.6.3 | No |
| 4.6 | CloudShell | Tras 4.1 | Sí: reinicia la Instancia 3 veces |
| 4.4 | Instancia (Session Manager) | Tras `make_env.sh` (tarea 6.2) y el despliegue (sección 5) | No |
| 4.8 | Instancia (Session Manager) | Tras el despliegue (sección 5) | Sí: llena y vacía el Volumen_Sandbox |
| 4.9 | CloudShell e Instancia | Tras 4.8, cuando el Equipo acepte una caída de unos minutos | Sí: detiene la Instancia y desadjunta y vuelve a adjuntar el Volumen_Sandbox |

Las líneas «Resultado de verificación» de esta sección se guardan en `docs/aws/evidencia/host/verificacion-host.jsonl`. Los bloques que corren en la Instancia se copian de la sesión de Session Manager a ese archivo. Los bloques de la Instancia usan `jq`, que instala `bootstrap_host.sh`.

### 4.1 Ejecución de `bootstrap_host.sh` (T-16, modifica: configura el host)

1. En CloudShell, leer el ID del Volumen_Sandbox (output `SandboxVolumeId`, 2.2):

   ```bash
   aws cloudformation describe-stacks --stack-name pgguardian \
     --query "Stacks[0].Outputs[?OutputKey=='SandboxVolumeId'].OutputValue" --output text
   ```

2. Abrir una sesión de Session Manager hacia la Instancia (3.9.2). Session Manager abre `sh` como `ssm-user`; se cambia a `ubuntu` con bash:

   ```sh
   sudo -iu ubuntu bash
   ```

3. Llevar el script a la Instancia, de una de estas dos formas:

   - **Heredoc** (funciona con el repositorio privado). Abrir `scripts/aws/bootstrap_host.sh` en el equipo, copiar su contenido completo y pegarlo entre las dos líneas siguientes. El delimitador va entre comillas (`'EOF'`) para que bash no expanda `$` ni comillas del script:

     ```bash
     cat > ~/bootstrap_host.sh <<'EOF'
     # ... contenido completo de scripts/aws/bootstrap_host.sh ...
     EOF
     ```

   - **`curl` del archivo raw** (solo si el repositorio es público):

     ```bash
     curl -fsSL -o ~/bootstrap_host.sh \
       https://raw.githubusercontent.com/<usuario>/<repositorio>/<rama>/scripts/aws/bootstrap_host.sh
     ```

   Comprobar que llegó completo: `bash -n ~/bootstrap_host.sh` no imprime nada y `tail -n1 ~/bootstrap_host.sh` muestra la línea `printf '\nbootstrap_host.sh terminó sin errores.\n'`.

4. Ejecutarlo con el ID del paso 1:

   ```bash
   sudo bash ~/bootstrap_host.sh <SandboxVolumeId>
   ```

Resultado esperado: ocho pasos `==> [1]` a `==> [8]` y, al final, `bootstrap_host.sh terminó sin errores.` El resumen muestra `/srv/sandbox` montado desde un `/dev/nvme1n1` (o similar) con su UUID, `pgdata 999:999 700`, `swap: /swapfile 2147479552` (2 GiB menos la página de cabecera), `unattended-upgrades active/enabled` y `docker active/enabled`. Se guarda la salida completa en `docs/aws/evidencia/host/bootstrap-<fecha>.txt`.

Si el script se detiene con `ERROR:`, el mensaje indica la causa y el estado:

| Mensaje | Qué pasó | Qué hacer |
| --- | --- | --- |
| `no existe /dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_vol...` | El volumen no está adjunto o el ID no es el del output. No se modificó nada. | Revisar el ID con el paso 1 y 3.6.1. |
| `tiene un sistema de archivos <tipo> (se esperaba ext4)` | El volumen tiene otro sistema de archivos; el script no lo formatea. | Revisar a mano con el Equipo; nunca formatear sin snapshot (sección 8). |
| `/etc/fstab ya monta /srv/sandbox desde otro origen` o `varias entradas` | Hay una entrada previa que no coincide con el UUID del volumen. | Corregir `/etc/fstab` (hay copia `/etc/fstab.bak-bootstrap-*` si el script lo modificó) y repetir. |
| `no está montado y contiene archivos en el disco raíz` | Alguien creó archivos en `/srv/sandbox` antes del montaje. | Revisar y mover esos archivos; montarlos encima los ocultaría. |
| `findmnt: ... No se crea /srv/sandbox/pgdata` | `/srv/sandbox` no es el punto de montaje del Volumen_Sandbox. | El directorio de datos no se crea (R4.9). Revisar 4.3 y repetir. |
| `hay otras áreas de swap activas` | La Instancia ya tenía otro swap. | Desactivarlo (`swapoff`) y quitarlo de `/etc/fstab`; se exige una sola área (R15.1). |

### 4.2 Idempotencia (segunda ejecución)

Justo después de 4.1, en la misma sesión:

```bash
antes=$(sudo sha256sum /etc/fstab); uuid_antes=$(findmnt -n -o UUID --mountpoint /srv/sandbox)
sudo bash ~/bootstrap_host.sh <SandboxVolumeId> | tee /tmp/bootstrap-2.txt
(
  criterio="CA-20"; requisito="R4.5, R15.3 (idempotencia de T-16)"
  despues=$(sudo sha256sum /etc/fstab); uuid_despues=$(findmnt -n -o UUID --mountpoint /srv/sandbox)
  nswap=$(swapon --show=NAME --noheadings | awk 'NF' | wc -l)
  fallos=()
  [ "$antes" = "$despues" ] || fallos+=("/etc/fstab cambió en la segunda ejecución")
  [ -n "$uuid_antes" ] && [ "$uuid_antes" = "$uuid_despues" ] || fallos+=("UUID de /srv/sandbox cambió: ${uuid_antes:-vacío} -> ${uuid_despues:-vacío} (¿se formateó?)")
  grep -q 'ya tiene ext4: no se formatea' /tmp/bootstrap-2.txt || fallos+=("la segunda ejecución no informó 'no se formatea'")
  [ "$nswap" -eq 1 ] || fallos+=("$nswap áreas de swap activas")
  grep -q 'terminó sin errores' /tmp/bootstrap-2.txt || fallos+=("la segunda ejecución no terminó sin errores")
  if [ ${#fallos[@]} -eq 0 ]; then
    estado="aprobado"; detalle="segunda ejecución sin cambios: /etc/fstab idéntico, UUID $uuid_despues sin formatear, 1 área de swap"
  else
    estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

### 4.3 Montaje por UUID, `nofail` y directorio de datos (R4.5, R4.7, R4.9)

Se ejecuta en la Instancia tras 4.1 y se repite después del reinicio de 3.6.3 (R4.7: montado sin intervención manual). Se define antes el ID del Volumen_Sandbox, como en 3.6.2.

Consulta directa:

```bash
SANDBOX_VOLUME_ID=vol-xxxxxxxxxxxxxxxxx   # valor copiado de CloudShell
findmnt /srv/sandbox
grep /srv/sandbox /etc/fstab
sudo blkid "$(readlink -f "/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_${SANDBOX_VOLUME_ID//-/}")"
sudo stat -c '%n %u:%g %a' /srv/sandbox/pgdata
ls -a /srv/sandbox
```

Resultado esperado: `findmnt` muestra `/srv/sandbox` con `ext4` desde el dispositivo NVMe del Volumen_Sandbox; `/etc/fstab` tiene una sola línea `UUID=<uuid> /srv/sandbox ext4 defaults,nofail,x-systemd.device-timeout=10s 0 2`, con el mismo UUID que `blkid`; `pgdata` es `999:999 700`; y `ls -a /srv/sandbox` muestra `lost+found` y `pgdata`.

Evaluación automática del criterio (usa el `SANDBOX_VOLUME_ID` definido arriba):

```bash
(
  criterio="CA-12"; requisito="R4.2, R4.5, R4.7, R4.9"
  enlace="/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_${SANDBOX_VOLUME_ID//-/}"
  if [[ "$SANDBOX_VOLUME_ID" != vol-* ]] || [[ "$SANDBOX_VOLUME_ID" == *x* ]]; then
    estado="no_verificable"; detalle="SANDBOX_VOLUME_ID no está definido con el valor real"
  elif ! disp=$(readlink -e "$enlace"); then
    estado="no_aprobado"; detalle="no conforme: no existe $enlace (volumen no adjunto)"
  else
    uuid=$(sudo blkid -o value -s UUID "$disp")
    tipo=$(sudo blkid -o value -s TYPE "$disp")
    lineas=$(awk '$1 !~ /^#/ && $2 == "/srv/sandbox"' /etc/fstab)
    nlineas=$(awk 'NF' <<< "$lineas" | wc -l)
    m_uuid=$(findmnt -n -o UUID --mountpoint /srv/sandbox)
    m_src=$(findmnt -n -o SOURCE --mountpoint /srv/sandbox)
    duenio=$(sudo stat -c '%u:%g' /srv/sandbox/pgdata 2>/dev/null)
    fallos=()
    [ "$tipo" = "ext4" ] || fallos+=("sistema de archivos ${tipo:-ninguno} (se esperaba ext4)")
    [ "$nlineas" -eq 1 ] || fallos+=("$nlineas entradas de /srv/sandbox en /etc/fstab (se esperaba 1)")
    [ "$(awk '{print $1}' <<< "$lineas")" = "UUID=$uuid" ] || fallos+=("la entrada de /etc/fstab no usa UUID=$uuid: $lineas")
    awk '{print $4}' <<< "$lineas" | tr ',' '\n' | grep -qx nofail || fallos+=("la entrada de /etc/fstab no tiene nofail")
    { [ "$m_uuid" = "$uuid" ] && [ "$(readlink -f "$m_src")" = "$disp" ]; } \
      || fallos+=("/srv/sandbox no está montado desde el Volumen_Sandbox (findmnt: ${m_src:-sin montar})")
    [ "$duenio" = "999:999" ] || fallos+=("/srv/sandbox/pgdata con dueño ${duenio:-inexistente} (se esperaba 999:999)")
    [ -d /srv/sandbox/lost+found ] || fallos+=("falta lost+found en la raíz del volumen")
    if [ ${#fallos[@]} -eq 0 ]; then
      estado="aprobado"
      detalle="/srv/sandbox ext4 desde $m_src (UUID $uuid) con nofail en /etc/fstab; pgdata 999:999; lost+found en /srv/sandbox; arranque $(cut -c1-8 /proc/sys/kernel/random/boot_id)"
    else
      estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

El `detalle` incluye el inicio del `boot_id`, para distinguir la línea anterior y la posterior al reinicio de 3.6.3. R4.7 queda aprobado solo con la línea posterior al reinicio en `aprobado`.

### 4.4 `SANDBOX_DATA_DIR` y datos de `sandbox_db` en el Volumen_Sandbox (R4.2, R4.4)

Se ejecuta en la Instancia después de generar el `.env` con `make_env.sh` (tarea 6.2) y de desplegar (sección 5). `APP_DIR` es el directorio del repositorio en la Instancia, el mismo de las secciones 5 y 6.

Consulta directa:

```bash
APP_DIR=/home/ubuntu/PgGuardian-Online   # ajustar si el repositorio está en otra ruta
grep '^SANDBOX_DATA_DIR=' "$APP_DIR/.env"
df -h /srv/sandbox/pgdata
df -h /
sudo docker inspect pgguardian_sandboxdb_prod \
  -f '{{range .Mounts}}{{.Type}} {{.Source}} -> {{.Destination}}{{"\n"}}{{end}}'
```

Resultado esperado: `SANDBOX_DATA_DIR=/srv/sandbox/pgdata`; `df -h /srv/sandbox/pgdata` muestra el dispositivo NVMe del Volumen_Sandbox (unos 8 GB) y `df -h /` otro dispositivo (unos 20 GB); el contenedor tiene `bind /srv/sandbox/pgdata -> /var/lib/postgresql/data`.

Evaluación automática del criterio:

```bash
APP_DIR=/home/ubuntu/PgGuardian-Online
(
  criterio="CA-12"; requisito="R4.2, R4.4"
  envf="$APP_DIR/.env"
  if [ ! -r "$envf" ]; then
    estado="no_verificable"; detalle="no se puede leer $envf; ¿se ejecutó make_env.sh (tarea 6.2)?"
  else
    valores=$(sed -n 's/^SANDBOX_DATA_DIR=//p' "$envf")
    nval=$(awk 'NF' <<< "$valores" | wc -l)
    src_pg=$(df --output=source /srv/sandbox/pgdata 2>/dev/null | tail -n1)
    src_sb=$(findmnt -n -o SOURCE --mountpoint /srv/sandbox)
    src_raiz=$(df --output=source / | tail -n1)
    montaje=$(sudo docker inspect pgguardian_sandboxdb_prod \
      -f '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Type}} {{.Source}}{{end}}{{end}}' 2>/dev/null)
    fallos=()
    { [ "$nval" -eq 1 ] && [ "$valores" = "/srv/sandbox/pgdata" ]; } \
      || fallos+=("SANDBOX_DATA_DIR en .env: '${valores:-ausente}' (se esperaba exactamente /srv/sandbox/pgdata)")
    { [ -n "$src_pg" ] && [ "$src_pg" = "$src_sb" ] && [ "$src_pg" != "$src_raiz" ]; } \
      || fallos+=("/srv/sandbox/pgdata está en ${src_pg:-?}; Volumen_Sandbox ${src_sb:-sin montar}; / en $src_raiz")
    [ "$montaje" = "bind /srv/sandbox/pgdata" ] || fallos+=("sandbox_db monta '${montaje:-nada}' en /var/lib/postgresql/data")
    sudo test -e /srv/sandbox/pgdata/lost+found && fallos+=("hay lost+found dentro de pgdata")
    if [ ${#fallos[@]} -eq 0 ]; then
      estado="aprobado"
      detalle="SANDBOX_DATA_DIR=/srv/sandbox/pgdata; pgdata en $src_pg (Volumen_Sandbox), / en $src_raiz; sandbox_db: bind /srv/sandbox/pgdata; sin lost+found en pgdata"
    else
      estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Si `SANDBOX_DATA_DIR` falta, el compose usa `./.data/sandbox` y los datos de `sandbox_db` quedan en el disco raíz sin aviso. Corrección: `docker compose -f docker-compose.prod.yml down`, volver a generar el `.env` con `make_env.sh` (tarea 6.2), desplegar con `deploy.sh` (que falla si el valor falta o difiere) y repetir 4.4. Después se borra `$APP_DIR/.data/sandbox`, que quedó en el disco raíz.

### 4.5 Swap (R15.1)

Consulta directa:

```bash
swapon --show
swapon --show=NAME,SIZE --bytes --noheadings
grep swap /etc/fstab
```

Resultado esperado: una sola fila `/swapfile file 2G`; en bytes, `2147479552` (2 GiB menos la página de cabecera de 4 KiB, dentro de ±1 MiB); y una línea `/swapfile none swap sw 0 0` en `/etc/fstab`.

Evaluación automática del criterio:

```bash
(
  criterio="CA-20"; requisito="R15.1"
  esperado=2147483648; tol=1048576
  areas=$(swapon --show=NAME,SIZE --bytes --noheadings)
  n=$(awk 'NF' <<< "$areas" | wc -l)
  nombre=$(awk 'NR == 1 {print $1}' <<< "$areas"); tam=$(awk 'NR == 1 {print $2}' <<< "$areas")
  nfstab=$(awk '$1 !~ /^#/ && $1 == "/swapfile" && $3 == "swap"' /etc/fstab | wc -l)
  fallos=()
  [ "$n" -eq 1 ] || fallos+=("$n áreas de swap activas (se esperaba 1): $(tr '\n' ';' <<< "$areas")")
  [ "$nombre" = "/swapfile" ] || fallos+=("el área activa es ${nombre:-ninguna}, no /swapfile")
  if [[ "$tam" =~ ^[0-9]+$ ]]; then
    d=$(( tam - esperado )); d=${d#-}
    [ "$d" -le "$tol" ] || fallos+=("tamaño $tam bytes, fuera de 2 GiB ±1 MiB")
  else
    fallos+=("no se pudo leer el tamaño del swap")
  fi
  [ "$nfstab" -eq 1 ] || fallos+=("$nfstab entradas de /swapfile en /etc/fstab (se esperaba 1)")
  if [ ${#fallos[@]} -eq 0 ]; then
    estado="aprobado"; detalle="1 área: /swapfile $tam bytes (2 GiB ±1 MiB); 1 entrada en /etc/fstab"
  else
    estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Si el swap no se activa durante un arranque (R15.4), systemd no detiene el arranque: la unidad `swapfile.swap` queda en estado fallido, `swapon --show` no muestra áreas y el error queda en el registro del sistema. Se consulta con `systemctl status swapfile.swap` y `journalctl -b -u swapfile.swap`, se anota la causa y se repite `sudo bash ~/bootstrap_host.sh <SandboxVolumeId>`, que vuelve a activarlo sin duplicarlo.

### 4.6 Swap tras 3 reinicios (R15.2, R15.3, modifica: reinicia la Instancia 3 veces)

> **Atención.** Este bloque reinicia la Instancia tres veces seguidas; la aplicación deja de responder unos minutos en total. Se avisa al Equipo antes.

Se ejecuta en CloudShell con las variables y la función `ssm_run` de 3.2. En cada reinicio espera el nuevo `boot_id` (como 3.6.3), espera a que el sistema lleve al menos 60 s arrancado y lee `swapon`:

```bash
(
  criterio="CA-20"; requisito="R15.2, R15.3"
  esperado=2147483648; tol=1048576
  estado=""; ok=(); fallos=()
  if [ -z "$INSTANCE_ID" ] || ! declare -F ssm_run >/dev/null; then
    estado="no_verificable"; detalle="faltan INSTANCE_ID o ssm_run; ejecutar 3.2"
  else
    for i in 1 2 3; do
      if ! boot0=$(ssm_run 'cat /proc/sys/kernel/random/boot_id') || [ -z "$boot0" ]; then
        estado="no_verificable"; detalle="reinicio $i: no se pudo leer boot_id por Run Command; revisar 3.4.3"; break
      fi
      if ! err=$(aws ec2 reboot-instances --instance-ids "$INSTANCE_ID" 2>&1); then
        estado="no_verificable"; detalle="reinicio $i: falló aws ec2 reboot-instances: $(echo "$err" | tr '\n' ' ')"; break
      fi
      SECONDS=0; volvio=""; sleep 20
      while [ "$SECONDS" -lt 300 ]; do
        if boot1=$(ssm_run 'cat /proc/sys/kernel/random/boot_id' 2>/dev/null) \
           && [ -n "$boot1" ] && [ "$boot1" != "$boot0" ]; then volvio="si"; break; fi
        sleep 10
      done
      if [ -z "$volvio" ]; then fallos+=("reinicio $i: la instancia no volvió en 300 s"); break; fi
      up=$(ssm_run 'cut -d" " -f1 /proc/uptime' 2>/dev/null); up=${up%%.*}
      [[ "$up" =~ ^[0-9]+$ ]] && [ "$up" -lt 60 ] && sleep $(( 60 - up ))
      sw=$(ssm_run 'swapon --show=NAME,SIZE --bytes --noheadings' 2>/dev/null)
      n=$(awk 'NF' <<< "$sw" | wc -l)
      nombre=$(awk 'NR == 1 {print $1}' <<< "$sw"); tam=$(awk 'NR == 1 {print $2}' <<< "$sw")
      d=$(( ${tam:-0} - esperado )); d=${d#-}
      if [ "$n" -eq 1 ] && [ "$nombre" = "/swapfile" ] && [ "$d" -le "$tol" ]; then
        ok+=("reinicio $i: /swapfile $tam bytes")
      else
        fallos+=("reinicio $i: $n áreas activas ($(tr '\n' ';' <<< "$sw"))")
      fi
    done
  fi
  if [ -z "$estado" ]; then
    if [ ${#fallos[@]} -eq 0 ] && [ ${#ok[@]} -eq 3 ]; then
      estado="aprobado"; detalle="tras 3 reinicios, 1 área de swap de 2 GiB ±1 MiB a los ≥ 60 s del arranque: $(printf '%s; ' "${ok[@]}" | sed 's/; $//')"
    else
      estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" "${ok[@]}" | sed 's/; $//')"
    fi
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Resultado esperado: `aprobado`, con tres entradas `/swapfile 2147479552 bytes`. El tiempo de 60 s se mide con `/proc/uptime`, desde el arranque del kernel. Después del bloque se repite 4.3 en la Instancia (montaje tras reinicio, R4.7).

### 4.7 Parches automáticos y Docker al arranque (R18, R19.8)

#### 4.7.1 `unattended-upgrades` (CA-22 · R18.1 a R18.4)

Consulta directa, en la Instancia:

```bash
systemctl is-active unattended-upgrades; systemctl is-enabled unattended-upgrades
cat /etc/apt/apt.conf.d/20auto-upgrades
apt-config dump Unattended-Upgrade::Allowed-Origins Unattended-Upgrade::Origins-Pattern
sudo unattended-upgrade --dry-run --debug 2>&1 | grep -i 'allowed origins'
```

Resultado esperado: `active` y `enabled`; `20auto-upgrades` con exactamente `APT::Periodic::Update-Package-Lists "1";` y `APT::Periodic::Unattended-Upgrade "1";`; un solo origen permitido, `${distro_id}:${distro_codename}-security`, sin `Origins-Pattern`; y `Allowed origins are: o=Ubuntu,a=noble-security`.

Evaluación automática del criterio:

```bash
(
  criterio="CA-22"; requisito="R18.1, R18.2, R18.3, R18.4"
  act=$(systemctl is-active unattended-upgrades); rc_act=$?
  ena=$(systemctl is-enabled unattended-upgrades); rc_ena=$?
  upl=""; uu=""
  eval "$(apt-config shell upl APT::Periodic::Update-Package-Lists uu APT::Periodic::Unattended-Upgrade)"
  origenes=$(apt-config dump Unattended-Upgrade::Allowed-Origins \
    | sed -n 's/^Unattended-Upgrade::Allowed-Origins:: "\(.*\)";$/\1/p' | paste -sd, -)
  patrones=$(apt-config dump Unattended-Upgrade::Origins-Pattern | grep -c '^Unattended-Upgrade::Origins-Pattern:: ')
  fallos=()
  dpkg -s unattended-upgrades >/dev/null 2>&1 || fallos+=("paquete unattended-upgrades no instalado")
  { [ "$act" = "active" ] && [ "$rc_act" -eq 0 ]; } || fallos+=("is-active=$act (código $rc_act)")
  { [ "$ena" = "enabled" ] && [ "$rc_ena" -eq 0 ]; } || fallos+=("is-enabled=$ena (código $rc_ena)")
  grep -qx 'APT::Periodic::Update-Package-Lists "1";' /etc/apt/apt.conf.d/20auto-upgrades \
    && grep -qx 'APT::Periodic::Unattended-Upgrade "1";' /etc/apt/apt.conf.d/20auto-upgrades \
    || fallos+=("20auto-upgrades sin las dos líneas \"1\"")
  { [ "$upl" = "1" ] && [ "$uu" = "1" ]; } || fallos+=("valores efectivos Update-Package-Lists=$upl, Unattended-Upgrade=$uu")
  [ "$origenes" = '${distro_id}:${distro_codename}-security' ] || fallos+=("orígenes permitidos: ${origenes:-ninguno}")
  [ "$patrones" -eq 0 ] || fallos+=("$patrones Origins-Pattern definidos")
  if [ ${#fallos[@]} -eq 0 ]; then
    estado="aprobado"
    detalle="unattended-upgrades active/enabled; 20auto-upgrades 1/1; solo origen $origenes"
  else
    estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

R18.5 es el comportamiento de `unattended-upgrades`: si un parche falla, el error queda en `/var/log/unattended-upgrades/unattended-upgrades.log` (y la salida de `dpkg` en `unattended-upgrades-dpkg.log`), y los paquetes ya instalados no se revierten. Se revisa con `sudo tail -n 50 /var/log/unattended-upgrades/unattended-upgrades.log` al día siguiente de la configuración; si hay errores, se anotan en la evidencia con la fecha.

#### 4.7.2 Docker habilitado al arranque (R19.8)

```bash
(
  criterio="CA-23"; requisito="R19.8 (Docker al arranque)"
  ena=$(systemctl is-enabled docker 2>&1); act=$(systemctl is-active docker 2>&1)
  if [ "$ena" = "enabled" ] && [ "$act" = "active" ] && docker compose version >/dev/null 2>&1; then
    estado="aprobado"; detalle="docker enabled/active; $(docker --version); $(docker compose version)"
  else
    estado="no_aprobado"; detalle="no conforme: docker is-enabled=$ena, is-active=$act, compose $(docker compose version 2>&1 | head -n1)"
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

La recuperación completa de la aplicación tras detener e iniciar la Instancia (R19.8) se verifica en la sección 6.

### 4.8 Prueba de llenado del Volumen_Sandbox (R4.10, modifica: llena y vacía el Volumen_Sandbox)

> **Atención.** La prueba llena el Volumen_Sandbox al 100 %. Mientras dura, los análisis nuevos fallan en el sandbox; el login y el historial (en `app_db`, disco raíz) deben seguir respondiendo. Se avisa al Equipo y no se ejecutan análisis durante la prueba.

Requisitos previos: la aplicación desplegada (sección 5) y una cuenta de prueba registrada en la aplicación. La contraseña se escribe con `read -s`: no queda en el historial ni en la línea de comandos. Si se equivoca la contraseña 5 veces, la cuenta se bloquea 15 min.

Se ejecuta en la Instancia como `ubuntu`, en una sola sesión:

```bash
APP_DIR=/home/ubuntu/PgGuardian-Online
cd "$APP_DIR"
envval() { sed -n "s/^$1=//p" .env | tail -n1; }
SB_USER=$(envval SANDBOX_DB_ADMIN_USER); SB_DB=$(envval SANDBOX_DB_NAME); DOMINIO=$(envval APP_DOMAIN)
SB=pgguardian_sandboxdb_prod
read -rp "Correo de la cuenta de prueba: " PRUEBA_EMAIL
read -rsp "Contraseña: " PRUEBA_PASS; echo

psql_sb() { sudo docker exec -i "$SB" psql -U "$SB_USER" -d "$SB_DB" -v ON_ERROR_STOP=1 -qAt "$@"; }
pct() { df --output=pcent "$1" | tail -n1 | tr -dc '0-9'; }
# Imprime: código_login segundos_login código_historial segundos_historial
medir() {
  local jar l h; jar=$(mktemp)
  l=$(jq -cn --arg e "$PRUEBA_EMAIL" --arg p "$PRUEBA_PASS" '{email: $e, password: $p}' \
      | curl -s -o /dev/null -w '%{http_code} %{time_total}' -m 10 -c "$jar" \
          -H 'Content-Type: application/json' --data @- "https://$DOMINIO/api/auth/login")
  h=$(curl -s -o /dev/null -w '%{http_code} %{time_total}' -m 10 -b "$jar" "https://$DOMINIO/api/analyses")
  rm -f "$jar"; echo "$l $h"
}

echo "antes: / $(pct /)%  /srv/sandbox $(pct /srv/sandbox)%  medida: $(medir)"
RAIZ_ANTES=$(pct /)

# Llenado: lotes de 500 000 filas de ~1 KB (≈ 0.5 GB + WAL) hasta que el disco se llena.
psql_sb -c "CREATE TABLE IF NOT EXISTS pgg_relleno (g bigint, relleno text)"
lote=0
while [ "$(pct /srv/sandbox)" -lt 100 ] && [ "$lote" -lt 40 ]; do
  lote=$((lote + 1))
  if ! psql_sb -c "INSERT INTO pgg_relleno SELECT g, repeat(md5(random()::text), 32) FROM generate_series(1, 500000) g" 2>/tmp/relleno.err; then
    echo "lote $lote: $(tail -n1 /tmp/relleno.err)"; break
  fi
  echo "lote $lote: /srv/sandbox $(pct /srv/sandbox)%"
done
df -h /srv/sandbox /
```

Resultado esperado del llenado: el último lote termina con un error `could not extend file ...: No space left on device` (o el contenedor se reinicia por falta de espacio para el WAL) y `df -h /srv/sandbox` muestra `100%`. Las filas de 1 KB no se comprimen (PostgreSQL solo comprime filas de más de unos 2 KB), así que ocupan su tamaño real.

Con el volumen lleno, en la misma sesión:

```bash
(
  criterio="CA-12"; requisito="R4.10"
  uso_sb=$(pct /srv/sandbox); raiz_despues=$(pct /)
  medidas=(); fallos=()
  for i in 1 2 3; do
    read -r cl tl ch th <<< "$(medir)"
    medidas+=("login $cl ${tl}s, historial $ch ${th}s")
    [[ "$cl" =~ ^2 ]] && awk -v t="$tl" 'BEGIN { exit !(t <= 3) }' || fallos+=("intento $i: login $cl en ${tl}s")
    [[ "$ch" =~ ^2 ]] && awk -v t="$th" 'BEGIN { exit !(t <= 3) }' || fallos+=("intento $i: historial $ch en ${th}s")
  done
  var=$(( raiz_despues - RAIZ_ANTES )); var=${var#-}
  [ "$uso_sb" -eq 100 ] || fallos+=("/srv/sandbox al ${uso_sb}% (se esperaba 100%)")
  [ "$var" -le 1 ] || fallos+=("/ pasó de ${RAIZ_ANTES}% a ${raiz_despues}% (variación > 1 pp)")
  if [ ${#fallos[@]} -eq 0 ]; then
    estado="aprobado"
    detalle="/srv/sandbox 100%; / ${RAIZ_ANTES}% -> ${raiz_despues}%; $(printf '%s; ' "${medidas[@]}" | sed 's/; $//')"
  else
    estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
  fi
  jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
    '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
)
```

Resultado esperado: `aprobado`, con 3 logins y 3 consultas de historial con código 200 en ≤ 3 s cada uno, y `/` sin variar más de 1 punto porcentual. El uso de 100 % se mide con `df`, que no cuenta el 5 % que ext4 reserva para root; `sandbox_db` corre como UID 999 y no puede usar esa reserva.

Limpieza (obligatoria al terminar):

```bash
psql_sb -c "DROP TABLE IF EXISTS pgg_relleno" && psql_sb -c "CHECKPOINT"
unset PRUEBA_PASS
df -h /srv/sandbox
sudo docker ps --filter name=pgguardian_sandboxdb_prod --format '{{.Names}} {{.Status}}'
```

Resultado esperado: `/srv/sandbox` vuelve a un uso bajo y `sandbox_db` queda `Up (healthy)`. Si PostgreSQL no arranca porque no tiene espacio ni para el WAL (el contenedor aparece `Restarting`), se reinicia el sandbox desde cero. Sus datos son desechables: cada análisis crea sus bases y roles temporales, y el historial vive en `app_db`. El directorio `pgdata` se conserva con su dueño `999:999`:

```bash
cd "$APP_DIR"
sudo docker compose -f docker-compose.prod.yml stop sandbox_db
sudo find /srv/sandbox/pgdata -mindepth 1 -delete
sudo docker compose -f docker-compose.prod.yml up -d sandbox_db
```

Después se comprueba que `sandbox_db` llega a `healthy` y que un análisis de prueba termina bien.

### 4.9 Prueba manual de volumen ausente (R4.8, modifica: detiene la Instancia y desadjunta el Volumen_Sandbox)

> **Atención.** La prueba detiene la Instancia dos veces y desadjunta el Volumen_Sandbox fuera de CloudFormation. Al final se vuelve a adjuntar el mismo volumen en el mismo dispositivo (`/dev/sdf`), así que el stack queda como lo define la plantilla. Es la única excepción documentada, junto con la de 2.5, a la regla de no cambiar recursos fuera de un change set. Se avisa al Equipo y se toma antes un snapshot de ambos discos (sección 8).

1. En CloudShell (variables de 3.2), detener la Instancia y desadjuntar el volumen:

   ```bash
   aws ec2 stop-instances --instance-ids "$INSTANCE_ID" >/dev/null
   aws ec2 wait instance-stopped --instance-ids "$INSTANCE_ID"
   aws ec2 detach-volume --volume-id "$SANDBOX_VOLUME_ID" >/dev/null
   aws ec2 wait volume-available --volume-ids "$SANDBOX_VOLUME_ID"
   aws ec2 start-instances --instance-ids "$INSTANCE_ID" >/dev/null
   aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
   ```

2. Esperar a que la Instancia aparezca `Online` en Systems Manager (3.4.3). Que la sesión de Session Manager abra ya demuestra que el SO terminó de arrancar sin entrar en modo de emergencia (`nofail`).

3. En la Instancia (`sudo -iu ubuntu bash`), esperar 2 minutos para que Docker intente levantar los contenedores y ejecutar:

   Consulta directa:

   ```bash
   systemctl is-system-running
   findmnt /srv/sandbox; ls -a /srv/sandbox; ls /srv/sandbox/pgdata
   df /srv/sandbox; df /
   sudo docker ps -a --filter name=pgguardian_sandboxdb_prod --format '{{.Names}} {{.Status}}'
   sudo docker inspect pgguardian_sandboxdb_prod -f '{{.State.Status}} {{.State.Error}}'
   ```

   Resultado esperado: el sistema `running` o `degraded` (no `emergency` ni `maintenance`); `findmnt` no imprime nada; `/srv/sandbox` vacío; `ls /srv/sandbox/pgdata` falla con `No such file or directory`; `df /srv/sandbox` muestra el mismo dispositivo que `df /`; y `sandbox_db` no está en ejecución, con un error del tipo `invalid mount config for type "bind": bind source path does not exist: /srv/sandbox/pgdata`.

   Evaluación automática del criterio:

   ```bash
   (
     criterio="CA-12"; requisito="R4.8"
     sistema=$(systemctl is-system-running 2>/dev/null)
     mnt=$(findmnt -n --mountpoint /srv/sandbox)
     src_sb=$(df --output=source /srv/sandbox | tail -n1); src_raiz=$(df --output=source / | tail -n1)
     cont=$(sudo docker inspect pgguardian_sandboxdb_prod -f '{{.State.Running}}|{{.State.Error}}' 2>&1)
     fallos=()
     case "$sistema" in running|degraded) ;; *) fallos+=("systemctl is-system-running=$sistema") ;; esac
     [ -z "$mnt" ] || fallos+=("/srv/sandbox está montado ($mnt); el volumen sigue adjunto")
     ls /srv/sandbox/pgdata >/dev/null 2>&1 && fallos+=("/srv/sandbox/pgdata existe en el disco raíz")
     [ "$src_sb" = "$src_raiz" ] || fallos+=("df /srv/sandbox muestra $src_sb, no el dispositivo raíz $src_raiz")
     [[ "$cont" == false\|* ]] || fallos+=("sandbox_db en ejecución o sin datos: $cont")
     if [ ${#fallos[@]} -eq 0 ]; then
       estado="aprobado"
       detalle="sin Volumen_Sandbox: sistema $sistema; /srv/sandbox sin montar en $src_raiz; /srv/sandbox/pgdata no existe; sandbox_db detenido (${cont#false|})"
     else
       estado="no_aprobado"; detalle="no conforme: $(printf '%s; ' "${fallos[@]}" | sed 's/; $//')"
     fi
     jq -cn --arg c "$criterio" --arg r "$requisito" --arg e "$estado" --arg d "$detalle" \
       '{criterio: $c, requisito: $r, estado: $e, detalle: $d}'
   )
   ```

   No se ejecuta `bootstrap_host.sh` en este estado: abortaría en el paso 1 sin cambiar nada, pero no hace falta. Tampoco se crea `/srv/sandbox/pgdata` a mano.

4. Restaurar, en CloudShell:

   ```bash
   aws ec2 stop-instances --instance-ids "$INSTANCE_ID" >/dev/null
   aws ec2 wait instance-stopped --instance-ids "$INSTANCE_ID"
   aws ec2 attach-volume --volume-id "$SANDBOX_VOLUME_ID" --instance-id "$INSTANCE_ID" --device /dev/sdf >/dev/null
   aws ec2 wait volume-in-use --volume-ids "$SANDBOX_VOLUME_ID"
   aws ec2 start-instances --instance-ids "$INSTANCE_ID" >/dev/null
   aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"
   ```

5. Comprobar la vuelta: 3.6.1 (volumen en `/dev/sdf`), 4.3 en la Instancia y `sudo docker ps` con `sandbox_db` `Up (healthy)`. Docker lo vuelve a levantar solo al arrancar (`restart: unless-stopped`); si no, `cd "$APP_DIR" && sudo docker compose -f docker-compose.prod.yml up -d sandbox_db`.

### 4.10 Resumen de la sección 4

| Criterio | Bloques que deben estar en `aprobado` | Partes en otras secciones |
| --- | --- | --- |
| CA-12 | 4.3 (antes y después del reinicio), 4.4, 4.8, 4.9 | 3.6.2 |
| CA-20 | 4.2, 4.5, 4.6 | 3.4.2, 3.6.1, 3.6.3 |
| CA-22 | 4.7.1 | — |
| CA-23 | 4.7.2 (apoyo a R19.8) | 3.8, secciones 5 y 6 |

Un criterio nunca se da por aprobado con un bloque en `no_aprobado` o `no_verificable`: se corrige la causa y se repite el bloque, conservando la línea anterior en la evidencia.

## 5. Despliegue

Pendiente: tarea 6.3 (certificado de Let's Encrypt, redirección HTTP→HTTPS y cabeceras de seguridad).

## 6. Encender y detener

Pendiente: tarea 6.4 (`stop-instances`/`start-instances` y verificación tras encender).

## 7. Costos

Pendiente: tarea 7.1 (presupuesto mensual), tarea 7.2 (Cost Anomaly Detection) y tarea 7.6 (secreto huérfano de Secrets Manager).

## 8. Snapshots

Pendiente: tarea 7.3 (alarma de recuperación automática), tarea 7.4 (snapshots de estabilización) y tarea 7.5 (snapshots previos a la grabación del video).
