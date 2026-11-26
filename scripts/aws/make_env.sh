#!/usr/bin/env bash
# =====================================================================
# PgGuardian - Generación del .env de producción en la Instancia (T-17)
#
# Trazabilidad: componentes C1 y C8 del diseño · RF-04.1, RF-04.4,
# RF-03.4, RF-03.5 (E1) · CA-09, CA-12, CA-23 · Requirements 1.4, 4.4,
# 10.2, 19.2 y 29.3.
#
# Pasos (un mensaje por paso):
#  1. Precondiciones: argumento <AppDomain> válido (output AppDomain del
#     stack, o subdominio DuckDNS de respaldo, R19.4), openssl disponible y
#     .env inexistente (o --force, que guarda una copia del anterior).
#  2. Secretos aleatorios: JWT_SECRET con openssl rand -hex 32 (32 bytes,
#     64 hex, R1.4) y contraseñas de app_db y sandbox_db.
#  3. Escritura del .env con umask 077, en un archivo temporal que se mueve
#     al destino, y chmod 600 (R19.2).
#  4. Comprobaciones del .env generado: SANDBOX_DATA_DIR=/srv/sandbox/pgdata
#     exactamente una vez (R4.4; el valor por defecto ./.data/sandbox dejaría
#     los datos de sandbox_db en el disco raíz), JWT_SECRET de 64 hex,
#     permisos 600 y ninguna clave de AWS (R10.2). Si docker está instalado,
#     también docker compose config -q con el .env generado.
#  5. Resumen sin mostrar secretos.
#
# El argumento <AppDomain> se pasa a mano: el rol de la Instancia no tiene
# permisos de CloudFormation. Se obtiene en CloudShell con:
#   aws cloudformation describe-stacks --stack-name pgguardian \
#     --query "Stacks[0].Outputs[?OutputKey=='AppDomain'].OutputValue" --output text
#
# El .env no contiene claves de AWS: la Instancia usa el rol
# PgGuardian-EC2-Role por IMDSv2 (R10.2).
#
# Uso (como ubuntu, desde cualquier directorio):
#   bash scripts/aws/make_env.sh <AppDomain> [--force]
#   (p. ej. bash scripts/aws/make_env.sh 3-14-31-64.sslip.io)
#   --force  reemplaza un .env existente; antes lo copia a .env.bak-<fecha>
#            (genera secretos nuevos: con app_db ya inicializada, la nueva
#            APP_DB_PASSWORD no coincidirá con la del volumen existente).
# =====================================================================

set -euo pipefail

SANDBOX_DATA_DIR_PROD="/srv/sandbox/pgdata"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$REPO_DIR/.env"
COMPOSE_FILE="$REPO_DIR/docker-compose.prod.yml"

PASO=0
paso() { PASO=$((PASO + 1)); printf '\n==> [%d] %s\n' "$PASO" "$*"; }
info() { printf '    %s\n' "$*"; }
fallo() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

uso() {
  cat >&2 <<'TXT'
Uso: bash scripts/aws/make_env.sh <AppDomain> [--force]
  <AppDomain>  Output AppDomain del stack pgguardian (a-b-c-d.sslip.io) o,
               como respaldo (R19.4), un subdominio <nombre>.duckdns.org.
  --force      Reemplaza un .env existente (guarda antes una copia .env.bak-<fecha>).
TXT
  exit 2
}

# ------------------------------------------------------------------ 1
paso "Precondiciones (argumentos, openssl y .env de destino)"

APP_DOMAIN=""
FORCE=0
for arg in "$@"; do
  case "$arg" in
    --force) FORCE=1 ;;
    -h|--help) uso ;;
    -*) printf 'ERROR: opción desconocida: %s\n' "$arg" >&2; uso ;;
    *) [ -z "$APP_DOMAIN" ] || uso; APP_DOMAIN="$arg" ;;
  esac
done
[ -n "$APP_DOMAIN" ] || uso

OCTETO='(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])'
SSLIP_RE="^${OCTETO}-${OCTETO}-${OCTETO}-${OCTETO}\.sslip\.io$"
DUCKDNS_RE='^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.duckdns\.org$'
if [[ ! "$APP_DOMAIN" =~ $SSLIP_RE ]] && [[ ! "$APP_DOMAIN" =~ $DUCKDNS_RE ]]; then
  fallo "'$APP_DOMAIN' no es un dominio válido. Se espera el output AppDomain del stack (p. ej. 3-14-31-64.sslip.io) o <nombre>.duckdns.org."
fi
command -v openssl >/dev/null || fallo "falta openssl (sudo apt-get install -y openssl)."
[ -f "$COMPOSE_FILE" ] || fallo "no existe $COMPOSE_FILE; el script debe estar en scripts/aws/ del repositorio."
[ "$(id -u)" -ne 0 ] || info "aviso: se ejecuta como root; el .env quedará a nombre de root. Lo normal es ejecutarlo como ubuntu."

if [ -e "$ENV_FILE" ]; then
  if [ "$FORCE" -ne 1 ]; then
    fallo "ya existe $ENV_FILE. No se sobrescribe. Para reemplazarlo, repetir con --force (se guarda una copia)."
  fi
  BACKUP="$ENV_FILE.bak-$(date -u +%Y%m%dT%H%M%SZ)"
  cp -p "$ENV_FILE" "$BACKUP"
  chmod 600 "$BACKUP"
  info "--force: copia del .env anterior en $BACKUP (permisos 600)."
fi
info "dominio: $APP_DOMAIN"
info "destino: $ENV_FILE"

# ------------------------------------------------------------------ 2
paso "Secretos aleatorios (openssl rand -hex 32)"

# Hexadecimal: sin caracteres que haya que escapar en .env, YAML, SQL o URL.
JWT_SECRET="$(openssl rand -hex 32)"
APP_DB_PASSWORD="$(openssl rand -hex 24)"
SANDBOX_DB_ADMIN_PASSWORD="$(openssl rand -hex 24)"
SANDBOX_DB_EXEC_PASSWORD="$(openssl rand -hex 24)"
info "JWT_SECRET: 32 bytes (64 hex); contraseñas de base de datos: 24 bytes (48 hex)."

# ------------------------------------------------------------------ 3
paso "Escritura del .env (umask 077, permisos 600)"

umask 077
TMP_FILE="$(mktemp "$REPO_DIR/.env.tmp.XXXXXX")"
trap 'rm -f "$TMP_FILE"' EXIT

cat > "$TMP_FILE" <<ENV
# PgGuardian - .env de producción generado por scripts/aws/make_env.sh
# Fecha (UTC): $(date -u +%Y-%m-%dT%H:%M:%SZ)
# No versionar. Permisos 600. Sin claves de AWS: la Instancia usa el rol
# PgGuardian-EC2-Role (R10.2).

# Dominio público (output AppDomain del stack pgguardian, R19.2)
APP_DOMAIN=${APP_DOMAIN}
VITE_API_URL=https://${APP_DOMAIN}/api
CORS_ORIGINS=https://${APP_DOMAIN}

# Seguridad detrás de Caddy HTTPS
COOKIE_SECURE=true
TRUST_PROXY_HEADERS=true
# Obligatorio (R1): docker compose falla con "falta JWT_SECRET" si está vacío.
JWT_SECRET=${JWT_SECRET}

# Base de datos de aplicación (app_db)
APP_DB_NAME=pgguardian_app
APP_DB_USER=pgguardian_app_user
APP_DB_PASSWORD=${APP_DB_PASSWORD}

# Servidor aislado de sandboxes (sandbox_db)
SANDBOX_DB_NAME=postgres
SANDBOX_DB_ADMIN_USER=sandbox_admin
SANDBOX_DB_ADMIN_PASSWORD=${SANDBOX_DB_ADMIN_PASSWORD}
SANDBOX_DB_EXEC_USER=sandbox_runner
SANDBOX_DB_EXEC_PASSWORD=${SANDBOX_DB_EXEC_PASSWORD}

# Datos de sandbox_db en el Volumen_Sandbox (R4.4). Obligatoria en producción.
SANDBOX_DATA_DIR=${SANDBOX_DATA_DIR_PROD}
ENV

chmod 600 "$TMP_FILE"
mv -f "$TMP_FILE" "$ENV_FILE"
trap - EXIT
info "escrito $ENV_FILE."

# ------------------------------------------------------------------ 4
paso "Comprobaciones del .env generado"

VALORES="$(sed -n 's/^SANDBOX_DATA_DIR=//p' "$ENV_FILE")"
if [ -z "$VALORES" ]; then
  fallo "SANDBOX_DATA_DIR falta en $ENV_FILE; los datos de sandbox_db quedarían en el disco raíz."
fi
if [ "$(printf '%s\n' "$VALORES" | wc -l)" -ne 1 ]; then
  fallo "SANDBOX_DATA_DIR aparece más de una vez en $ENV_FILE."
fi
if [ "$VALORES" != "$SANDBOX_DATA_DIR_PROD" ]; then
  fallo "SANDBOX_DATA_DIR=$VALORES en $ENV_FILE (se esperaba $SANDBOX_DATA_DIR_PROD)."
fi
info "SANDBOX_DATA_DIR=$SANDBOX_DATA_DIR_PROD"

[[ "$(sed -n 's/^JWT_SECRET=//p' "$ENV_FILE")" =~ ^[0-9a-f]{64}$ ]] \
  || fallo "JWT_SECRET en $ENV_FILE no tiene 64 caracteres hexadecimales."
info "JWT_SECRET: 64 hex."

PERMISOS="$(stat -c %a "$ENV_FILE")"
[ "$PERMISOS" = "600" ] || fallo "$ENV_FILE tiene permisos $PERMISOS (se esperaba 600)."
info "permisos: $PERMISOS ($(stat -c %U:%G "$ENV_FILE"))."

if grep -Eq '^[[:space:]]*AWS_|AKIA[0-9A-Z]{16}|ASIA[0-9A-Z]{16}' "$ENV_FILE"; then
  fallo "$ENV_FILE contiene variables o claves de AWS; no deben estar en el .env (R10.2)."
fi
info "sin claves de AWS."

if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
  if docker compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" config -q; then
    info "docker compose config -q: correcto."
  else
    fallo "docker compose config rechazó el .env generado."
  fi
else
  info "docker no está instalado: se omite docker compose config (lo valida deploy.sh)."
fi

# ------------------------------------------------------------------ 5
paso "Resumen"

info "APP_DOMAIN=$APP_DOMAIN"
info "CORS_ORIGINS=https://$APP_DOMAIN"
info "SANDBOX_DATA_DIR=$SANDBOX_DATA_DIR_PROD"
info "Los secretos no se muestran; están solo en $ENV_FILE."
info "Siguiente paso: despliegue con scripts/aws/deploy.sh (tarea 6.3) y verificación 4.4 del runbook."
printf '\nmake_env.sh terminó sin errores.\n'
