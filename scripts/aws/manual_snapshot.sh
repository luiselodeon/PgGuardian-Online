#!/usr/bin/env bash
# =====================================================================
# PgGuardian - Snapshot manual de un disco de la Instancia (T-22, T-27)
#
# Trazabilidad: componente C11 del diseño · RF-07.4 · CA-26 ·
# Requirements 23.1, 23.2, 23.3, 23.4 y 29.9.
#
# Pasos (un mensaje por paso):
#  1. Precondiciones: argumentos, aws y jq disponibles, región us-east-2 e
#     identidad de la sesión (sts get-caller-identity).
#  2. Volumen: lee los outputs InstanceId y SandboxVolumeId del stack
#     pgguardian; el disco raíz se obtiene con describe-instances
#     (RootDeviceName de la Instancia). El volumen pedido debe ser uno de los
#     dos; si no, el script se detiene sin crear nada.
#  3. Etiquetas: Project=PgGuardian, Env=prod y el Owner del propio volumen
#     (o, si falta, el de la Instancia), de 1 a 256 caracteres (R17).
#  4. aws ec2 create-snapshot con esas tres etiquetas y la descripción
#     "PgGuardian: snapshot manual (<motivo>) del disco <raiz|sandbox> ...".
#  5. Espera con aws ec2 wait snapshot-completed (cada wait consulta cada
#     15 s durante 10 min; se repite hasta MAX_ESPERAS veces mientras siga en
#     pending). Si el snapshot termina en error, lo informa y sale con 3.
#  6. Verificación con describe-snapshots: estado completed, volumen de
#     origen y etiquetas. No se restaura nada (R23.3).
#  7. Resumen y línea final "RESULTADO: <inicio> <disco> <volumen>
#     <snapshot> <estado> <motivo>".
#
# El snapshot no es un recurso del stack: sobrevive a su borrado (R29.9).
# Con la aplicación en marcha el snapshot es consistente ante caídas: cada
# base de datos está entera en un solo volumen (app_db en el disco raíz,
# sandbox_db en el Volumen_Sandbox) y PostgreSQL se recupera con su WAL.
#
# Uso (en CloudShell, us-east-2, Usuario_IAM con MFA, desde la raíz del repo):
#   bash scripts/aws/manual_snapshot.sh <raiz|sandbox|vol-...> [--motivo <motivo>]
#   (p. ej. bash scripts/aws/manual_snapshot.sh raiz --motivo estabilizacion)
#   <raiz|sandbox|vol-...>  "raiz" (disco raíz, desde el output InstanceId),
#                           "sandbox" (output SandboxVolumeId) o el ID de uno
#                           de esos dos volúmenes.
#   --motivo  estabilizacion (T-22), video (T-27), borrado (runbook 2.5.4)...;
#             minúsculas, dígitos y guiones. Por defecto: manual.
#
# Variables de entorno opcionales: STACK_NAME (pgguardian) y MAX_ESPERAS (6,
# es decir, hasta 60 min de espera).
#
# Códigos de salida:
#   0  snapshot en completed y con las etiquetas correctas
#   1  precondición o fallo de la CLI (si ya se creó el snapshot, se indica)
#   2  uso incorrecto
#   3  el snapshot terminó en error: repetir el del mismo volumen (R23.4)
#   4  sigue en pending tras MAX_ESPERAS esperas: no crear otro, esperar con
#      aws ec2 wait snapshot-completed --snapshot-ids <id>
# =====================================================================

set -euo pipefail

STACK_NAME="${STACK_NAME:-pgguardian}"
MAX_ESPERAS="${MAX_ESPERAS:-6}"
REGION_ESPERADA="us-east-2"
TAG_PROJECT="PgGuardian"
TAG_ENV="prod"
DESC_PREFIJO="PgGuardian: snapshot manual"

PASO=0
paso() { PASO=$((PASO + 1)); printf '\n==> [%d] %s\n' "$PASO" "$*"; }
info() { printf '    %s\n' "$*"; }
fallo() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
una_linea() { printf '%s' "$*" | tr '\n' ' '; }

uso() {
  cat >&2 <<'TXT'
Uso: bash scripts/aws/manual_snapshot.sh <raiz|sandbox|vol-...> [--motivo <motivo>]
  raiz       Disco raíz de la Instancia (output InstanceId del stack + describe-instances).
  sandbox    Volumen_Sandbox (output SandboxVolumeId del stack).
  vol-...    ID de uno de esos dos volúmenes.
  --motivo   estabilizacion, video, borrado... (minúsculas, dígitos y guiones; por defecto manual).
TXT
  exit 2
}

# ------------------------------------------------------------------ 1
paso "Precondiciones (argumentos, aws, jq, región e identidad)"

VOLUMEN=""
MOTIVO="manual"
while [ $# -gt 0 ]; do
  case "$1" in
    --motivo) [ $# -ge 2 ] || uso; MOTIVO="$2"; shift 2 ;;
    --motivo=*) MOTIVO="${1#*=}"; shift ;;
    -h|--help) uso ;;
    -*) printf 'ERROR: opción desconocida: %s\n' "$1" >&2; uso ;;
    *) [ -z "$VOLUMEN" ] || uso; VOLUMEN="$1"; shift ;;
  esac
done
[ -n "$VOLUMEN" ] || uso
[[ "$VOLUMEN" =~ ^(raiz|sandbox|vol-[0-9a-f]{8,17})$ ]] \
  || fallo "'$VOLUMEN' no es raiz, sandbox ni un ID de volumen (vol-...)."
[[ "$MOTIVO" =~ ^[a-z0-9-]{1,32}$ ]] \
  || fallo "motivo '$MOTIVO' no válido: de 1 a 32 caracteres entre minúsculas, dígitos y guiones."
[[ "$MAX_ESPERAS" =~ ^[1-9][0-9]*$ ]] || fallo "MAX_ESPERAS=$MAX_ESPERAS no es un entero positivo."
command -v aws >/dev/null || fallo "falta la AWS CLI (se ejecuta en CloudShell)."
command -v jq >/dev/null || fallo "falta jq."

REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-$(aws configure get region 2>/dev/null || true)}}"
[ "$REGION" = "$REGION_ESPERADA" ] \
  || fallo "región '${REGION:-sin definir}'; se esperaba $REGION_ESPERADA (abrir CloudShell en us-east-2)."
AWS=(aws --region "$REGION")

IDENTIDAD="$("${AWS[@]}" sts get-caller-identity --query Arn --output text 2>&1)" \
  || fallo "falló aws sts get-caller-identity: $(una_linea "$IDENTIDAD")"
info "región: $REGION"
info "identidad: $IDENTIDAD"
info "volumen pedido: $VOLUMEN; motivo: $MOTIVO"

# ------------------------------------------------------------------ 2
paso "Volumen (outputs del stack $STACK_NAME y describe-instances)"

output_stack() {
  "${AWS[@]}" cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}
INSTANCE_ID="$(output_stack InstanceId 2>&1)" \
  || fallo "no se pudo leer el output InstanceId del stack $STACK_NAME: $(una_linea "$INSTANCE_ID")"
SANDBOX_VOLUME_ID="$(output_stack SandboxVolumeId 2>&1)" \
  || fallo "no se pudo leer el output SandboxVolumeId del stack $STACK_NAME: $(una_linea "$SANDBOX_VOLUME_ID")"
[[ "$INSTANCE_ID" =~ ^i-[0-9a-f]{8,17}$ ]] \
  || fallo "output InstanceId inválido ('$INSTANCE_ID'); revisar la sección 2 del runbook."
[[ "$SANDBOX_VOLUME_ID" =~ ^vol-[0-9a-f]{8,17}$ ]] \
  || fallo "output SandboxVolumeId inválido ('$SANDBOX_VOLUME_ID'); revisar la sección 2 del runbook."

INSTANCIA_JSON="$("${AWS[@]}" ec2 describe-instances --instance-ids "$INSTANCE_ID" --output json 2>&1)" \
  || fallo "falló aws ec2 describe-instances: $(una_linea "$INSTANCIA_JSON")"
ROOT_VOLUME_ID="$(jq -r '.Reservations[0].Instances[0] as $i | [$i.BlockDeviceMappings[]
    | select(.DeviceName == $i.RootDeviceName) | .Ebs.VolumeId][0] // ""' <<< "$INSTANCIA_JSON")"
[[ "$ROOT_VOLUME_ID" =~ ^vol-[0-9a-f]{8,17}$ ]] \
  || fallo "no se encontró el disco raíz de $INSTANCE_ID ('$ROOT_VOLUME_ID')."
info "instancia: $INSTANCE_ID; disco raíz: $ROOT_VOLUME_ID; Volumen_Sandbox: $SANDBOX_VOLUME_ID"

case "$VOLUMEN" in
  raiz) DISCO="raiz"; VOLUME_ID="$ROOT_VOLUME_ID" ;;
  sandbox) DISCO="sandbox"; VOLUME_ID="$SANDBOX_VOLUME_ID" ;;
  "$ROOT_VOLUME_ID") DISCO="raiz"; VOLUME_ID="$VOLUMEN" ;;
  "$SANDBOX_VOLUME_ID") DISCO="sandbox"; VOLUME_ID="$VOLUMEN" ;;
  *) fallo "$VOLUMEN no es el disco raíz ($ROOT_VOLUME_ID) ni el Volumen_Sandbox ($SANDBOX_VOLUME_ID) del stack." ;;
esac

VOLUMEN_JSON="$("${AWS[@]}" ec2 describe-volumes --volume-ids "$VOLUME_ID" --output json 2>&1)" \
  || fallo "falló aws ec2 describe-volumes: $(una_linea "$VOLUMEN_JSON")"
ESTADO_VOL="$(jq -r '.Volumes[0].State // ""' <<< "$VOLUMEN_JSON")"
case "$ESTADO_VOL" in
  in-use|available) ;;
  *) fallo "el volumen $VOLUME_ID está en '${ESTADO_VOL:-desconocido}'; se esperaba in-use o available." ;;
esac
info "disco: $DISCO; volumen: $VOLUME_ID ($(jq -r '.Volumes[0] | "\(.Size) GiB \(.VolumeType), \(.AvailabilityZone)"' <<< "$VOLUMEN_JSON"), $ESTADO_VOL)"

# ------------------------------------------------------------------ 3
paso "Etiquetas del snapshot (Project, Env, Owner)"

OWNER="$(jq -r '[(.Volumes[0].Tags // [])[] | select(.Key == "Owner") | .Value][0] // ""' <<< "$VOLUMEN_JSON")"
if [ -z "$OWNER" ]; then
  OWNER="$(jq -r '[(.Reservations[0].Instances[0].Tags // [])[] | select(.Key == "Owner") | .Value][0] // ""' <<< "$INSTANCIA_JSON")"
  [ -z "$OWNER" ] || info "aviso: el volumen no tiene Owner; se usa el de la Instancia (corregir con 3.7 del runbook)."
fi
if [ ${#OWNER} -lt 1 ] || [ ${#OWNER} -gt 256 ]; then
  fallo "etiqueta Owner inválida (longitud ${#OWNER}, se esperaba de 1 a 256); corregir con 3.7 del runbook."
fi
TAGS_JSON="$(jq -cn --arg p "$TAG_PROJECT" --arg e "$TAG_ENV" --arg o "$OWNER" \
  '[{ResourceType: "snapshot", Tags: [{Key: "Project", Value: $p}, {Key: "Env", Value: $e}, {Key: "Owner", Value: $o}]}]')"
info "Project=$TAG_PROJECT Env=$TAG_ENV Owner=$OWNER"

# ------------------------------------------------------------------ 4
paso "Creación del snapshot (aws ec2 create-snapshot)"

FECHA="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
DESCRIPCION="$DESC_PREFIJO ($MOTIVO) del disco $DISCO $VOLUME_ID $FECHA"
SNAPSHOT_ID="$("${AWS[@]}" ec2 create-snapshot --volume-id "$VOLUME_ID" \
  --description "$DESCRIPCION" --tag-specifications "$TAGS_JSON" \
  --query SnapshotId --output text 2>&1)" \
  || fallo "falló aws ec2 create-snapshot: $(una_linea "$SNAPSHOT_ID")"
[[ "$SNAPSHOT_ID" =~ ^snap-[0-9a-f]{8,17}$ ]] || fallo "create-snapshot devolvió '$SNAPSHOT_ID'."
info "$VOLUME_ID -> $SNAPSHOT_ID"
info "descripción: $DESCRIPCION"

# ------------------------------------------------------------------ 5
paso "Espera hasta completed (aws ec2 wait snapshot-completed)"

campo_snapshot() {
  "${AWS[@]}" ec2 describe-snapshots --snapshot-ids "$SNAPSHOT_ID" \
    --query "Snapshots[0].$1" --output text
}
ESTADO=""
for ((i = 1; i <= MAX_ESPERAS; i++)); do
  if "${AWS[@]}" ec2 wait snapshot-completed --snapshot-ids "$SNAPSHOT_ID" 2>/dev/null; then
    ESTADO="completed"
    break
  fi
  ESTADO="$(campo_snapshot State 2>&1)" \
    || fallo "falló aws ec2 describe-snapshots para $SNAPSHOT_ID (el snapshot ya se creó): $(una_linea "$ESTADO")"
  case "$ESTADO" in
    completed|error) break ;;
    pending) info "espera $i de $MAX_ESPERAS: $SNAPSHOT_ID sigue en pending ($(campo_snapshot Progress 2>/dev/null || echo '?'))." ;;
    *) fallo "estado inesperado de $SNAPSHOT_ID: '$ESTADO'." ;;
  esac
done

if [ "$ESTADO" = "error" ]; then
  MENSAJE="$(campo_snapshot StateMessage 2>/dev/null || true)"
  printf 'ERROR: el snapshot %s del disco %s (%s) terminó en error: %s\n' \
    "$SNAPSHOT_ID" "$DISCO" "$VOLUME_ID" "${MENSAJE:-sin StateMessage}" >&2
  printf 'ERROR: repetir el snapshot del mismo volumen (R23.4): bash scripts/aws/manual_snapshot.sh %s --motivo %s\n' \
    "$DISCO" "$MOTIVO" >&2
  printf '\nRESULTADO: %s %s %s %s error %s\n' "$FECHA" "$DISCO" "$VOLUME_ID" "$SNAPSHOT_ID" "$MOTIVO"
  exit 3
fi
if [ "$ESTADO" != "completed" ]; then
  printf 'ERROR: %s sigue en %s tras %d esperas de 10 min. No crear otro: esperar con\n' \
    "$SNAPSHOT_ID" "$ESTADO" "$MAX_ESPERAS" >&2
  printf '       aws ec2 wait snapshot-completed --snapshot-ids %s\n' "$SNAPSHOT_ID" >&2
  printf '\nRESULTADO: %s %s %s %s %s %s\n' "$FECHA" "$DISCO" "$VOLUME_ID" "$SNAPSHOT_ID" "$ESTADO" "$MOTIVO"
  exit 4
fi
info "$SNAPSHOT_ID en completed."

# ------------------------------------------------------------------ 6
paso "Verificación con describe-snapshots (sin restaurar)"

SNAP_JSON="$("${AWS[@]}" ec2 describe-snapshots --snapshot-ids "$SNAPSHOT_ID" --output json 2>&1)" \
  || fallo "falló aws ec2 describe-snapshots para $SNAPSHOT_ID (el snapshot está en completed): $(una_linea "$SNAP_JSON")"
VERIFICACION="$(jq -r --arg v "$VOLUME_ID" --arg p "$TAG_PROJECT" --arg e "$TAG_ENV" --arg o "$OWNER" '
  .Snapshots[0] as $s | ($s.Tags // [] | map({(.Key): .Value}) | add // {}) as $t
  | [ (if $s.State != "completed" then "State=\($s.State)" else empty end),
      (if $s.VolumeId != $v then "VolumeId=\($s.VolumeId)" else empty end),
      (if $t.Project != $p then "Project=\($t.Project // "ausente")" else empty end),
      (if $t.Env != $e then "Env=\($t.Env // "ausente")" else empty end),
      (if $t.Owner != $o then "Owner=\($t.Owner // "ausente")" else empty end) ] | join("; ")' <<< "$SNAP_JSON")"
if [ -n "$VERIFICACION" ]; then
  fallo "$SNAPSHOT_ID no cumple: $VERIFICACION. Corregir las etiquetas con aws ec2 create-tags --resources $SNAPSHOT_ID (no hace falta otro snapshot)."
fi
INICIO="$(jq -r '.Snapshots[0].StartTime' <<< "$SNAP_JSON")"
info "$(jq -r '.Snapshots[0] | "\(.SnapshotId): \(.State) \(.Progress), \(.VolumeSize) GiB, inicio \(.StartTime), cifrado=\(.Encrypted)"' <<< "$SNAP_JSON")"
info "etiquetas: Project=$TAG_PROJECT Env=$TAG_ENV Owner=$OWNER"

# ------------------------------------------------------------------ 7
paso "Resumen"

info "disco $DISCO ($VOLUME_ID) -> $SNAPSHOT_ID, completed, motivo $MOTIVO."
info "El snapshot no pertenece al stack y se conserva si se borra el stack."
printf '\nRESULTADO: %s %s %s %s completed %s\n' "$INICIO" "$DISCO" "$VOLUME_ID" "$SNAPSHOT_ID" "$MOTIVO"
printf 'manual_snapshot.sh terminó sin errores.\n'
