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

Trazabilidad: componente C15 del diseño · R29.2, R29.3, R29.6, R29.7, R29.8, R29.10 y R21.1 · Recursos de T-11 a T-15 y T-19 a T-21.

Esta sección crea y actualiza el stack `pgguardian` a partir de `infra/cloudformation/pgguardian.yaml`. Todo se ejecuta en CloudShell (`us-east-2`) con un Usuario_IAM de `PgG-Admins` autenticado con MFA. A diferencia de las demás secciones, varios pasos **modifican la cuenta**, y cada uno lo indica: 2.1.3 borra el monitor de anomalías por defecto, 2.1.6 crea el stack, 2.1.7 activa su protección, 2.3 lo actualiza y 2.4 lo borra tras un despliegue fallido.

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

### 2.5 Borrado del stack

Pendiente: tarea 5.4 (borrado del stack con snapshots previos).

## 3. Instancia

Pendiente: tarea 5.3 (Security Group, IMDS, volúmenes, etiquetas y Elastic IP) y tarea 6.1 (acceso sin SSH).

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

CA-17 queda aprobado para el rol solo si 3.1.1, 3.1.2 y 3.1.3 están en `aprobado`. La parte de CA-17 sobre el registro `Online` en Systems Manager (R10.3) se verifica aparte.

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
