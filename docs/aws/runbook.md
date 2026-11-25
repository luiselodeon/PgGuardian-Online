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

Pendiente: tarea 5.2 (despliegue con change set, lectura de outputs y plan B de Cost Anomaly Detection) y tarea 5.4 (borrado del stack).

## 3. Instancia

Pendiente: tarea 4.3 (rol `PgGuardian-EC2-Role`), tarea 5.3 (Security Group, IMDS, volúmenes, etiquetas y Elastic IP) y tarea 6.1 (acceso sin SSH).

## 4. Host

Pendiente: tarea 6.1 (swap, montaje del Volumen_Sandbox, parches automáticos, prueba de llenado y prueba de volumen ausente).

## 5. Despliegue

Pendiente: tarea 6.3 (certificado de Let's Encrypt, redirección HTTP→HTTPS y cabeceras de seguridad).

## 6. Encender y detener

Pendiente: tarea 6.4 (`stop-instances`/`start-instances` y verificación tras encender).

## 7. Costos

Pendiente: tarea 7.1 (presupuesto mensual), tarea 7.2 (Cost Anomaly Detection) y tarea 7.6 (secreto huérfano de Secrets Manager).

## 8. Snapshots

Pendiente: tarea 7.3 (alarma de recuperación automática), tarea 7.4 (snapshots de estabilización) y tarea 7.5 (snapshots previos a la grabación del video).
