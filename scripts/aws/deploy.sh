#!/usr/bin/env bash
# =====================================================================
# PgGuardian - Despliegue de producción con HTTPS válido (T-18)
#
# Trazabilidad: componentes C2 y C8 del diseño · RF-06.8, RF-03.4 (E1),
# RF-04.5 · CA-13, CA-23 · Requirements 4.4, 19.3, 19.4, 19.5, 19.6 y 19.7.
#
# Pasos (un mensaje por paso):
#  1. Precondiciones: .env legible con permisos 600, SANDBOX_DATA_DIR
#     exactamente una vez e igual a /srv/sandbox/pgdata (R4.4; el valor por
#     defecto ./.data/sandbox dejaría los datos de sandbox_db en el disco raíz),
#     /srv/sandbox montado con pgdata, APP_DOMAIN válido, docker disponible y,
#     si se pidió el respaldo, DUCKDNS_TOKEN definido.
#  2. docker compose config -q con el .env.
#  3. docker compose -f docker-compose.prod.yml up -d --build.
#  4. Espera del certificado hasta 120 s (R19.3): curl con verificación TLS
#     contra 127.0.0.1:443 con el nombre del dominio y emisor Let's Encrypt.
#  5. Solo si el paso 4 falla y se pasó --duckdns (R19.4): actualiza el registro
#     de DuckDNS a la Elastic IP, espera a que el nombre resuelva, cambia
#     APP_DOMAIN, VITE_API_URL y CORS_ORIGINS en el .env (copia previa) y
#     repite up -d --build, con otros 120 s de espera.
#     --build hace falta porque VITE_API_URL se compila en el frontend.
#  6. Si no hay certificado: muestra docker logs del proxy (R19.7), comprueba
#     que HTTP no sirve la aplicación en claro y sale con código 1.
#  7. Resumen: emisor, vencimiento, redirección HTTP->HTTPS y health-check.
#
# Las verificaciones formales (CA-13, CA-23) están en docs/aws/runbook.md,
# sección 5.3 (la ejecución está en la 5.2). El script no muestra secretos ni los guarda en el código: el
# token de DuckDNS se lee de la variable de entorno DUCKDNS_TOKEN y se pasa a
# curl por la entrada estándar, no en la línea de comandos.
#
# Uso (como ubuntu, desde cualquier directorio):
#   bash scripts/aws/deploy.sh
#   DUCKDNS_TOKEN=<token> bash scripts/aws/deploy.sh --duckdns <nombre>.duckdns.org
#     (para no dejar el token en el historial: read -rs DUCKDNS_TOKEN; export DUCKDNS_TOKEN)
# =====================================================================

set -euo pipefail

SANDBOX_DATA_DIR_PROD="/srv/sandbox/pgdata"
MOUNT_POINT="/srv/sandbox"
PROXY_CONTAINER="pgguardian_proxy"
CERT_TIMEOUT=120   # segundos (R19.3)
POLL=5
DNS_TIMEOUT=120
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_FILE="$REPO_DIR/.env"
COMPOSE_FILE="$REPO_DIR/docker-compose.prod.yml"

OCTETO='(25[0-5]|2[0-4][0-9]|1[0-9]{2}|[1-9]?[0-9])'
SSLIP_RE="^${OCTETO}-${OCTETO}-${OCTETO}-${OCTETO}\.sslip\.io$"
DUCKDNS_RE='^[a-z0-9]([a-z0-9-]{0,61}[a-z0-9])?\.duckdns\.org$'
IPV4_RE="^${OCTETO}\.${OCTETO}\.${OCTETO}\.${OCTETO}$"

PASO=0
paso() { PASO=$((PASO + 1)); printf '\n==> [%d] %s\n' "$PASO" "$*"; }
info() { printf '    %s\n' "$*"; }
fallo() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

uso() {
  cat >&2 <<'TXT'
Uso: bash scripts/aws/deploy.sh [--duckdns <nombre>.duckdns.org]
  --duckdns <dominio>  Respaldo (R19.4) si Let's Encrypt no emite para sslip.io
                       en 120 s. Requiere la variable de entorno DUCKDNS_TOKEN.
TXT
  exit 2
}

env_valor() { sed -n "s/^$1=//p" "$ENV_FILE"; }

# Ejecuta docker compose con el .env del repositorio.
compose() { "${DOCKER[@]}" compose -f "$COMPOSE_FILE" --env-file "$ENV_FILE" "$@"; }

# Devuelve 0 si 127.0.0.1:443 presenta para $1 un certificado válido (cadena y
# nombre verificados por curl) emitido por Let's Encrypt.
certificado_valido() {
  local dominio="$1" emisor
  curl -sS -o /dev/null --max-time 10 --resolve "${dominio}:443:127.0.0.1" \
    "https://${dominio}/" 2>/dev/null || return 1
  emisor="$(certificado_campo "$dominio" -issuer)"
  [[ "$emisor" == *"Let's Encrypt"* ]] || {
    info "certificado válido pero emitido por '${emisor#issuer=}', no por Let's Encrypt (R19.3)."
    return 2
  }
}

# Imprime un campo (-issuer, -enddate, -subject) del certificado servido.
certificado_campo() {
  openssl s_client -connect 127.0.0.1:443 -servername "$1" </dev/null 2>/dev/null \
    | openssl x509 -noout "$2" 2>/dev/null || true
}

# Espera hasta CERT_TIMEOUT s el certificado de $1. 0 = emitido.
esperar_certificado() {
  local dominio="$1" inicio transcurrido rc estado
  inicio=$(date +%s)
  while :; do
    estado="$("${DOCKER[@]}" inspect -f '{{.State.Status}}' "$PROXY_CONTAINER" 2>/dev/null || echo ausente)"
    [ "$estado" = "running" ] || info "el contenedor $PROXY_CONTAINER está en estado '$estado'."
    rc=0; certificado_valido "$dominio" || rc=$?
    transcurrido=$(( $(date +%s) - inicio ))
    if [ "$rc" -eq 0 ]; then
      info "certificado obtenido para $dominio en ${transcurrido} s."
      return 0
    fi
    [ "$rc" -eq 2 ] && return 1
    if [ "$transcurrido" -ge "$CERT_TIMEOUT" ]; then
      info "sin certificado válido para $dominio tras ${transcurrido} s."
      return 1
    fi
    sleep "$POLL"
  done
}

# Elastic IP: del propio dominio sslip.io o, si no, de IMDSv2 (desde el host,
# el salto 1 alcanza el servicio de metadatos).
ip_publica() {
  local dominio="$1" token
  if [[ "$dominio" =~ $SSLIP_RE ]]; then
    printf '%s\n' "${dominio%.sslip.io}" | tr '-' '.'
    return
  fi
  token="$(curl -sS -m 5 -X PUT http://169.254.169.254/latest/api/token \
    -H 'X-aws-ec2-metadata-token-ttl-seconds: 60')" || return 1
  curl -sS -m 5 -H "X-aws-ec2-metadata-token: $token" \
    http://169.254.169.254/latest/meta-data/public-ipv4
}

# Reemplaza APP_DOMAIN, VITE_API_URL y CORS_ORIGINS en el .env (copia previa).
actualizar_env_dominio() {
  local nuevo="$1" clave backup tmp
  for clave in APP_DOMAIN VITE_API_URL CORS_ORIGINS; do
    [ "$(grep -c "^${clave}=" "$ENV_FILE")" -eq 1 ] \
      || fallo "$clave no aparece exactamente una vez en $ENV_FILE; corregirlo a mano."
  done
  backup="$ENV_FILE.bak-$(date -u +%Y%m%dT%H%M%SZ)"
  cp -p "$ENV_FILE" "$backup"
  chmod 600 "$backup"
  tmp="$(umask 077 && mktemp "$REPO_DIR/.env.tmp.XXXXXX")"
  awk -v d="$nuevo" '
    /^APP_DOMAIN=/   { print "APP_DOMAIN=" d; next }
    /^VITE_API_URL=/ { print "VITE_API_URL=https://" d "/api"; next }
    /^CORS_ORIGINS=/ { print "CORS_ORIGINS=https://" d; next }
    { print }' "$ENV_FILE" > "$tmp"
  chmod 600 "$tmp"
  mv -f "$tmp" "$ENV_FILE"
  info "copia del .env anterior en $backup (permisos 600)."
  info "APP_DOMAIN=$nuevo; VITE_API_URL=https://$nuevo/api; CORS_ORIGINS=https://$nuevo"
}

mostrar_logs_proxy() {
  printf '\n----- docker logs --tail 80 %s -----\n' "$PROXY_CONTAINER" >&2
  "${DOCKER[@]}" logs --tail 80 "$PROXY_CONTAINER" >&2 2>&1 || true
  printf '%s\n' '----- fin de los logs -----' >&2
}

# ------------------------------------------------------------------ 1
paso "Precondiciones (.env, SANDBOX_DATA_DIR, Volumen_Sandbox y docker)"

DUCKDNS_DOMAIN=""
while [ "$#" -gt 0 ]; do
  case "$1" in
    --duckdns) [ "$#" -ge 2 ] || uso; DUCKDNS_DOMAIN="$2"; shift 2 ;;
    -h|--help) uso ;;
    *) printf 'ERROR: argumento desconocido: %s\n' "$1" >&2; uso ;;
  esac
done

[ -f "$COMPOSE_FILE" ] || fallo "no existe $COMPOSE_FILE; el script debe estar en scripts/aws/ del repositorio."
[ -r "$ENV_FILE" ] || fallo "no se puede leer $ENV_FILE. Generarlo con: bash scripts/aws/make_env.sh <AppDomain>"
PERMISOS="$(stat -c %a "$ENV_FILE")"
[ "$PERMISOS" = "600" ] || fallo "$ENV_FILE tiene permisos $PERMISOS (se esperaba 600, R19.2): chmod 600 $ENV_FILE"

VALORES="$(env_valor SANDBOX_DATA_DIR)"
if [ -z "$VALORES" ]; then
  fallo "SANDBOX_DATA_DIR falta en $ENV_FILE; los datos de sandbox_db quedarían en el disco raíz (R4.4). No se despliega."
fi
if [ "$(printf '%s\n' "$VALORES" | wc -l)" -ne 1 ]; then
  fallo "SANDBOX_DATA_DIR aparece más de una vez en $ENV_FILE. No se despliega."
fi
if [ "$VALORES" != "$SANDBOX_DATA_DIR_PROD" ]; then
  fallo "SANDBOX_DATA_DIR=$VALORES en $ENV_FILE (se esperaba $SANDBOX_DATA_DIR_PROD, R4.4). No se despliega."
fi
info "SANDBOX_DATA_DIR=$SANDBOX_DATA_DIR_PROD"

findmnt -n --mountpoint "$MOUNT_POINT" >/dev/null \
  || fallo "$MOUNT_POINT no está montado; ejecutar antes bootstrap_host.sh (runbook, sección 4.1)."
[ -d "$SANDBOX_DATA_DIR_PROD" ] \
  || fallo "no existe $SANDBOX_DATA_DIR_PROD; ejecutar antes bootstrap_host.sh (runbook, sección 4.1)."
info "$MOUNT_POINT montado desde $(findmnt -n -o SOURCE --mountpoint "$MOUNT_POINT")."

[ -n "$(env_valor JWT_SECRET)" ] || fallo "JWT_SECRET falta o está vacío en $ENV_FILE (R1)."

APP_DOMAIN="$(env_valor APP_DOMAIN)"
if [[ ! "$APP_DOMAIN" =~ $SSLIP_RE ]] && [[ ! "$APP_DOMAIN" =~ $DUCKDNS_RE ]]; then
  fallo "APP_DOMAIN='$APP_DOMAIN' en $ENV_FILE no es <a-b-c-d>.sslip.io ni <nombre>.duckdns.org."
fi
info "APP_DOMAIN=$APP_DOMAIN"

if [ -n "$DUCKDNS_DOMAIN" ]; then
  [[ "$DUCKDNS_DOMAIN" =~ $DUCKDNS_RE ]] || fallo "'$DUCKDNS_DOMAIN' no es un subdominio <nombre>.duckdns.org."
  if [ "$DUCKDNS_DOMAIN" != "$APP_DOMAIN" ]; then
    [ -n "${DUCKDNS_TOKEN:-}" ] || fallo "--duckdns requiere la variable de entorno DUCKDNS_TOKEN (read -rs DUCKDNS_TOKEN; export DUCKDNS_TOKEN)."
  fi
  info "respaldo DuckDNS preparado: $DUCKDNS_DOMAIN"
fi

for cmd in curl openssl getent; do
  command -v "$cmd" >/dev/null || fallo "falta $cmd."
done
command -v docker >/dev/null || fallo "docker no está instalado; ejecutar antes bootstrap_host.sh."
if docker info >/dev/null 2>&1; then
  DOCKER=(docker)
elif sudo -n docker info >/dev/null 2>&1; then
  DOCKER=(sudo docker)
  info "se usa sudo docker (el grupo docker se aplica en la próxima sesión)."
else
  fallo "no se puede usar docker (ni con sudo -n). Abrir una sesión nueva como ubuntu o revisar el servicio docker."
fi
"${DOCKER[@]}" compose version >/dev/null 2>&1 || fallo "falta el plugin docker compose."

# ------------------------------------------------------------------ 2
paso "docker compose config -q"

compose config -q || fallo "docker compose config rechazó $COMPOSE_FILE con $ENV_FILE."
info "configuración válida."

# ------------------------------------------------------------------ 3
paso "docker compose up -d --build"

compose up -d --build
compose ps

# ------------------------------------------------------------------ 4
paso "Certificado de Let's Encrypt para $APP_DOMAIN (hasta ${CERT_TIMEOUT} s)"

DOMINIO_FINAL="$APP_DOMAIN"
if ! esperar_certificado "$APP_DOMAIN"; then
  # ---------------------------------------------------------------- 5
  if [ -z "$DUCKDNS_DOMAIN" ] || [ "$DUCKDNS_DOMAIN" = "$APP_DOMAIN" ]; then
    mostrar_logs_proxy
    if [ -z "$DUCKDNS_DOMAIN" ] && [[ "$APP_DOMAIN" =~ $SSLIP_RE ]]; then
      printf '%s\n' "Respaldo (R19.4): crear un subdominio en https://www.duckdns.org y repetir:" \
        "  read -rs DUCKDNS_TOKEN; export DUCKDNS_TOKEN" \
        "  bash scripts/aws/deploy.sh --duckdns <nombre>.duckdns.org" >&2
    fi
    fallo "no se obtuvo certificado para $APP_DOMAIN. Registrar el error de los logs (R19.7)."
  fi

  paso "Respaldo DuckDNS: $DUCKDNS_DOMAIN (R19.4)"

  EIP="$(ip_publica "$APP_DOMAIN" || true)"
  [[ "$EIP" =~ $IPV4_RE ]] || fallo "no se pudo obtener la Elastic IP (valor: '${EIP:-vacío}')."
  info "Elastic IP: $EIP"

  SUB="${DUCKDNS_DOMAIN%.duckdns.org}"
  # El token va por la entrada estándar (-K -): no aparece en ps ni en el historial.
  RESP="$(printf 'url = "https://www.duckdns.org/update?domains=%s&token=%s&ip=%s"\n' \
    "$SUB" "$DUCKDNS_TOKEN" "$EIP" | curl -sS -m 15 -K -)" \
    || fallo "no se pudo contactar con www.duckdns.org."
  [ "$RESP" = "OK" ] || fallo "DuckDNS respondió '$RESP' (token o subdominio incorrectos)."
  info "DuckDNS actualizado: $DUCKDNS_DOMAIN -> $EIP"

  inicio=$(date +%s)
  until getent ahostsv4 "$DUCKDNS_DOMAIN" | awk '{print $1}' | grep -qx "$EIP"; do
    [ $(( $(date +%s) - inicio )) -lt "$DNS_TIMEOUT" ] \
      || fallo "$DUCKDNS_DOMAIN no resuelve a $EIP tras ${DNS_TIMEOUT} s."
    sleep "$POLL"
  done
  info "$DUCKDNS_DOMAIN resuelve a $EIP."

  actualizar_env_dominio "$DUCKDNS_DOMAIN"
  compose config -q || fallo "docker compose config rechazó el .env actualizado."
  compose up -d --build
  DOMINIO_FINAL="$DUCKDNS_DOMAIN"

  paso "Certificado de Let's Encrypt para $DUCKDNS_DOMAIN (hasta ${CERT_TIMEOUT} s)"

  if ! esperar_certificado "$DUCKDNS_DOMAIN"; then
    # -------------------------------------------------------------- 6
    mostrar_logs_proxy
    CODIGO_HTTP="$(curl -s -o /dev/null -w '%{http_code}' -m 10 \
      --resolve "${DUCKDNS_DOMAIN}:80:127.0.0.1" "http://${DUCKDNS_DOMAIN}/" || true)"
    info "HTTP en el puerto 80 responde $CODIGO_HTTP (se espera una redirección 3xx, no la aplicación en claro, R19.7)."
    fallo "no se obtuvo certificado tampoco para $DUCKDNS_DOMAIN. Registrar el error de los logs del proxy (R19.7)."
  fi
fi

# ------------------------------------------------------------------ 7
paso "Resumen"

EMISOR="$(certificado_campo "$DOMINIO_FINAL" -issuer)"
VENCE="$(certificado_campo "$DOMINIO_FINAL" -enddate)"
REDIR="$(curl -s -o /dev/null -w '%{http_code} %{redirect_url}' -m 10 \
  --resolve "${DOMINIO_FINAL}:80:127.0.0.1" "http://${DOMINIO_FINAL}/" || true)"
SALUD="$(curl -s -m 10 --resolve "${DOMINIO_FINAL}:443:127.0.0.1" \
  "https://${DOMINIO_FINAL}/api/health-check" || true)"

info "URL:          https://$DOMINIO_FINAL"
info "emisor:       ${EMISOR#issuer=}"
info "vence:        ${VENCE#notAfter=}"
info "HTTP -> :     $REDIR"
info "health-check: ${SALUD:-sin respuesta}"
info "Siguiente paso: verificaciones 4.4 y 5.3 de docs/aws/runbook.md (CA-12, CA-13, CA-23)."
printf '\ndeploy.sh terminó sin errores.\n'
