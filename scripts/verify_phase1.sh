#!/usr/bin/env bash
# =====================================================================
# PgGuardian - Verificación local de la Fase 1 (T-08 / RNF-05 / Requirement 7)
#
#  1. Precondiciones: .env local con JWT_SECRET no vacío (R7.1).
#  2. Crea el directorio de datos de sandbox_db (./.data/sandbox o SANDBOX_DATA_DIR)
#     porque create_host_path: false impide que Docker lo cree (R7.2, R7.3).
#  3. docker compose -f docker-compose.prod.yml up -d --build y espera hasta 120 s
#     a que los cinco servicios estén running/healthy (R7.4).
#  4. Llama al health-check con timeout de 5 s (R7.5).
#  5. Evalúa CA-09 a CA-14 e imprime una línea JSON por criterio (R7.6).
#  6. Sale con código distinto de 0 si algo falla (R7.7). El resumen Markdown del
#     final se pega en la plantilla de PR (.github/PULL_REQUEST_TEMPLATE/fase1.md, R7.8).
#
# Equivalente funcional de scripts/verify_phase1.ps1. No modifica el archivo .env.
# Requiere: docker (con el plugin compose) y curl.
#
# Notas de entorno local:
#  - Se usa el nombre de proyecto "pgguardian-prod" para no recrear los
#    contenedores del compose de desarrollo, que comparte nombres de servicio.
#  - APP_DOMAIN se fuerza a ":80" solo en el entorno de este proceso: en local no
#    hay certificado de Let's Encrypt y las comprobaciones van por http://localhost.
#
# Uso: bash scripts/verify_phase1.sh
# =====================================================================

set -uo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="docker-compose.prod.yml"
PROJECT="pgguardian-prod"
BASE_URL="http://localhost"
SERVICES=(proxy frontend api app_db sandbox_db)
WAIT_SECONDS=120

cd "$ROOT" || exit 1

TMPDIR_V="$(mktemp -d)"
trap 'rm -rf "$TMPDIR_V"' EXIT

# ---------------------------------------------------------------- utilidades
RESULTS=()   # cada elemento: criterio<TAB>requisito<TAB>estado<TAB>detalle
FAILED=()

json_escape() {
  local s="$1"
  s="${s//\\/\\\\}"
  s="${s//\"/\\\"}"
  s="${s//$'\n'/\\n}"
  s="${s//$'\r'/\\r}"
  s="${s//$'\t'/\\t}"
  printf '%s' "$s"
}

add_result() {  # criterio requisito ok(0|1) detalle
  local estado="no_aprobado"
  [ "$3" -eq 0 ] && estado="aprobado"
  [ "$estado" != "aprobado" ] && FAILED+=("$1")
  RESULTS+=("$1"$'\t'"$2"$'\t'"$estado"$'\t'"$4")
  printf '{"criterio":"%s","requisito":"%s","estado":"%s","detalle":"%s"}\n' \
    "$(json_escape "$1")" "$(json_escape "$2")" "$estado" "$(json_escape "$4")"
}

dotenv_value() {  # archivo clave -> imprime el valor; código 1 si la clave no existe
  local file="$1" key="$2" line v found=1
  while IFS= read -r line || [ -n "$line" ]; do
    line="${line%$'\r'}"
    if [[ "$line" =~ ^[[:space:]]*(export[[:space:]]+)?${key}[[:space:]]*=(.*)$ ]]; then
      v="${BASH_REMATCH[2]}"
      v="${v#"${v%%[![:space:]]*}"}"; v="${v%"${v##*[![:space:]]}"}"
      if [ "${#v}" -ge 2 ]; then
        case "$v" in \"*\"|\'*\') v="${v:1:${#v}-2}" ;; esac
      fi
      found=0
    fi
  done < "$file"
  [ "$found" -eq 0 ] && printf '%s' "$v"
  return "$found"
}

compose() { docker compose -p "$PROJECT" -f "$COMPOSE_FILE" "$@"; }

container_id() { compose ps -a -q "$1" 2>/dev/null | head -n1 | tr -d '\r'; }

# http_get URL -> define HTTP_EXIT, HTTP_ERR, HTTP_STATUS, HTTP_TIME, HTTP_HEADERS (archivo), HTTP_BODY
http_get() {
  HTTP_HEADERS="$TMPDIR_V/headers"; local body="$TMPDIR_V/body" meta
  : > "$HTTP_HEADERS"; : > "$body"
  meta="$(curl -sS --max-time 5 -D "$HTTP_HEADERS" -o "$body" -w '%{http_code} %{time_total}' "$1" 2>"$TMPDIR_V/curl_err")"
  HTTP_EXIT=$?
  HTTP_ERR="$(tr -d '\r' < "$TMPDIR_V/curl_err")"
  HTTP_STATUS="${meta%% *}"; HTTP_TIME="${meta##* }"
  HTTP_BODY="$(cat "$body")"
  sed -i 's/\r$//' "$HTTP_HEADERS" 2>/dev/null || true
}

err() { printf 'ERROR: %s\n' "$*" >&2; }

# ------------------------------------------------------- 0. precondiciones (R7.1)
echo "== PgGuardian - verificación local de la Fase 1 (T-08) =="

command -v docker >/dev/null 2>&1 || { err "no se encontró el comando docker. Instala Docker y vuelve a ejecutar."; exit 1; }
command -v curl   >/dev/null 2>&1 || { err "no se encontró curl. Instálalo y vuelve a ejecutar."; exit 1; }

ENV_FILE="$ROOT/.env"
if [ ! -f "$ENV_FILE" ]; then
  err "falta el archivo .env en $ROOT."
  echo "  Corrección: cp .env.prod.example .env, define JWT_SECRET con un valor aleatorio"
  echo "  y elimina SANDBOX_DATA_DIR para el entorno local."
  exit 1
fi

if ! JWT="$(dotenv_value "$ENV_FILE" JWT_SECRET)"; then
  err "JWT_SECRET no está definido en .env."
  echo "  Corrección: agrega en .env la línea JWT_SECRET=\$(openssl rand -hex 32)"
  exit 1
fi
if [ -z "${JWT//[[:space:]]/}" ]; then
  err "JWT_SECRET está vacío en .env."
  echo "  Corrección: asigna un valor aleatorio, por ejemplo: openssl rand -hex 32"
  exit 1
fi
unset JWT
echo "OK: .env presente y JWT_SECRET definido."

# -------------------------------------- 0b. directorio de datos del sandbox (R7.2, R7.3)
DATA_DIR="$(dotenv_value "$ENV_FILE" SANDBOX_DATA_DIR || true)"
[ -z "${DATA_DIR//[[:space:]]/}" ] && DATA_DIR="./.data/sandbox"
case "$DATA_DIR" in
  /*|[A-Za-z]:*) DATA_DIR_ABS="$DATA_DIR" ;;
  *)             DATA_DIR_ABS="$ROOT/${DATA_DIR#./}" ;;
esac

if [ ! -d "$DATA_DIR_ABS" ]; then
  if MKDIR_ERR="$(mkdir -p "$DATA_DIR_ABS" 2>&1)"; then
    echo "OK: creado el directorio de datos de sandbox_db: $DATA_DIR_ABS"
  else
    err "no se pudo crear el directorio de datos de sandbox_db: $DATA_DIR_ABS"
    echo "  Causa: $MKDIR_ERR"
    exit 1
  fi
else
  echo "OK: directorio de datos de sandbox_db existente: $DATA_DIR_ABS"
fi

# Solo para este proceso y sus hijos; el .env no se toca.
export APP_DOMAIN=":80"

# ---------------------------------------------------------- 1. arranque (R7.4)
echo "== docker compose -p $PROJECT -f $COMPOSE_FILE up -d --build =="
compose up -d --build
UP_EXIT=$?

READY=1
STATUS_LINE=""
if [ "$UP_EXIT" -eq 0 ]; then
  echo "Esperando hasta ${WAIT_SECONDS} s a que los cinco servicios estén running/healthy..."
  DEADLINE=$(( $(date +%s) + WAIT_SECONDS ))
  while :; do
    PENDING=0; STATES=()
    for svc in "${SERVICES[@]}"; do
      id="$(container_id "$svc")"
      if [ -z "$id" ]; then PENDING=1; STATES+=("$svc=sin contenedor"); continue; fi
      st="$(docker inspect -f '{{.State.Status}}|{{if .State.Health}}{{.State.Health.Status}}{{end}}' "$id" 2>/dev/null | tr -d '\r')"
      run="${st%%|*}"; health="${st#*|}"
      label="$run"; [ -n "$health" ] && label="$run/$health"
      STATES+=("$svc=$label")
      # Con healthcheck se exige healthy (sandbox_db y app_db); sin él, running.
      if [ "$run" != "running" ] || { [ -n "$health" ] && [ "$health" != "healthy" ]; }; then PENDING=1; fi
    done
    STATUS_LINE="$(IFS=,; echo "${STATES[*]}" | sed 's/,/, /g')"
    if [ "$PENDING" -eq 0 ]; then READY=0; break; fi
    [ "$(date +%s)" -ge "$DEADLINE" ] && break
    sleep 3
  done
fi

if [ "$READY" -eq 0 ]; then
  add_result "arranque" "R7" 0 "Cinco servicios listos: $STATUS_LINE"
elif [ "$UP_EXIT" -ne 0 ]; then
  add_result "arranque" "R7" 1 "docker compose up terminó con código $UP_EXIT"
else
  add_result "arranque" "R7" 1 "Servicios no listos en ${WAIT_SECONDS} s: $STATUS_LINE. Revisa: docker compose -p $PROJECT -f $COMPOSE_FILE logs <servicio>"
fi

# ------------------------------------------------------------------- CA-09 (R1)
# JWT_SECRET vacío solo en el entorno del proceso hijo; el entorno del proceso
# tiene prioridad sobre el .env, que no se modifica.
JWT_SECRET='' docker compose -p "$PROJECT" -f "$COMPOSE_FILE" config >/dev/null 2>"$TMPDIR_V/ca09_err"
CA09_EXIT=$?
if grep -q "falta JWT_SECRET" "$TMPDIR_V/ca09_err"; then MSG="presente"; else MSG="ausente"; fi
if [ "$CA09_EXIT" -ne 0 ] && [ "$MSG" = "presente" ]; then OK=0; else OK=1; fi
add_result "CA-09" "R1" "$OK" "config con JWT_SECRET vacío: código $CA09_EXIT; mensaje 'falta JWT_SECRET' $MSG"

# ------------------------------------------------------------------- CA-10 (R2)
BAD=()
for svc in "${SERVICES[@]}"; do
  id="$(container_id "$svc")"
  if [ -z "$id" ]; then BAD+=("$svc=sin contenedor"); continue; fi
  lc="$(docker inspect -f '{{.HostConfig.LogConfig.Type}} {{index .HostConfig.LogConfig.Config "max-size"}} {{index .HostConfig.LogConfig.Config "max-file"}}' "$id" 2>/dev/null | tr -d '\r')"
  [ "$lc" != "json-file 10m 3" ] && BAD+=("$svc=[$lc]")
done
if [ "${#BAD[@]}" -eq 0 ]; then
  add_result "CA-10" "R2" 0 "Los cinco contenedores usan json-file, max-size 10m, max-file 3"
else
  add_result "CA-10" "R2" 1 "Servicios no conformes: $(IFS=,; echo "${BAD[*]}" | sed 's/,/, /g')"
fi

# ------------------------------------------------------------------- CA-11 (R3)
BAD=(); GOT=()
for pair in "api:536870912" "app_db:402653184" "sandbox_db:536870912"; do
  svc="${pair%%:*}"; exp="${pair##*:}"
  id="$(container_id "$svc")"
  if [ -z "$id" ]; then BAD+=("$svc=sin contenedor"); continue; fi
  mem="$(docker inspect -f '{{.HostConfig.Memory}}' "$id" 2>/dev/null | tr -d '\r')"
  GOT+=("$svc=$(( ${mem:-0} / 1048576 ))MiB")
  [ "$mem" != "$exp" ] && BAD+=("$svc=$mem bytes")
done
if [ "${#BAD[@]}" -eq 0 ]; then
  add_result "CA-11" "R3" 0 "Límites: $(IFS=,; echo "${GOT[*]}" | sed 's/,/, /g') (suma 1408 MiB)"
else
  add_result "CA-11" "R3" 1 "Límites incorrectos: $(IFS=,; echo "${BAD[*]}" | sed 's/,/, /g'); esperado api=512, app_db=384, sandbox_db=512 MiB"
fi

# ------------------------------------------------------------------- CA-12 (R4)
PROBLEMS=()
if compose config > "$TMPDIR_V/config.yml" 2>/dev/null; then
  # Bloque del servicio sandbox_db en la configuración resuelta (YAML de Compose).
  awk '/^  sandbox_db:$/{f=1; next} f && /^  [^ ]/{f=0} f && /^[^ ]/{f=0} f' "$TMPDIR_V/config.yml" > "$TMPDIR_V/sandbox.yml"
  # Entrada de volumen cuyo target es /var/lib/postgresql/data.
  awk '/^      - type: /{if (blk ~ /target: \/var\/lib\/postgresql\/data/) print blk; blk=""} /^      [^ -]/{if (blk ~ /target: \/var\/lib\/postgresql\/data/) print blk; blk=""; next} {blk = blk $0 "\n"} END{if (blk ~ /target: \/var\/lib\/postgresql\/data/) print blk}' "$TMPDIR_V/sandbox.yml" > "$TMPDIR_V/datavol.yml"
  if ! [ -s "$TMPDIR_V/datavol.yml" ]; then
    PROBLEMS+=("sandbox_db no monta /var/lib/postgresql/data")
  else
    grep -q "type: bind" "$TMPDIR_V/datavol.yml" || PROBLEMS+=("el montaje de datos no es de tipo bind")
    # Compose omite create_host_path cuando es false; true aparecería explícito.
    grep -q "create_host_path: true" "$TMPDIR_V/datavol.yml" && PROBLEMS+=("create_host_path resuelto como true")
    src="$(grep -m1 'source:' "$TMPDIR_V/datavol.yml" | sed -E 's/^[[:space:]]*source:[[:space:]]*//; s/^"//; s/"$//')"
    norm() { printf '%s' "$1" | sed 's#\\\\#/#g; s#\\#/#g; s#/*$##' | tr '[:upper:]' '[:lower:]'; }
    # Con ruta relativa se compara el sufijo: Compose escapa en el YAML los
    # caracteres no ASCII de la ruta del proyecto (p. ej. \U0001F4BB).
    case "$DATA_DIR" in
      /*|[A-Za-z]:*) src_ok=0; [ "$(norm "$src")" = "$(norm "$DATA_DIR")" ] || src_ok=1 ;;
      *)             rel="$(norm "${DATA_DIR#./}")"; src_ok=0; [[ "$(norm "$src")" == */"$rel" ]] || src_ok=1 ;;
    esac
    [ "$src_ok" -eq 0 ] || PROBLEMS+=("origen del bind '$src' distinto de '$DATA_DIR'")
  fi
  grep -Eq '(^|[^a-z_])sandbox_data([^a-z_]|$)' "$TMPDIR_V/config.yml" && PROBLEMS+=("el volumen sandbox_data sigue declarado")
else
  PROBLEMS+=("docker compose config falló")
fi
grep -Eq 'create_host_path:[[:space:]]*false' "$COMPOSE_FILE" || PROBLEMS+=("docker-compose.prod.yml no declara create_host_path: false")

SB_ID="$(container_id sandbox_db)"
if [ -z "$SB_ID" ]; then
  PROBLEMS+=("sandbox_db sin contenedor")
else
  h="$(docker inspect -f '{{if .State.Health}}{{.State.Health.Status}}{{else}}sin healthcheck{{end}}' "$SB_ID" 2>/dev/null | tr -d '\r')"
  [ "$h" != "healthy" ] && PROBLEMS+=("sandbox_db no está healthy ($h); posible problema de permisos del bind mount en Docker Desktop/NTFS")
  mt="$(docker inspect -f '{{range .Mounts}}{{if eq .Destination "/var/lib/postgresql/data"}}{{.Type}}{{end}}{{end}}' "$SB_ID" 2>/dev/null | tr -d '\r')"
  [ "$mt" != "bind" ] && PROBLEMS+=("el contenedor monta los datos como '$mt' (se esperaba bind)")
fi
if [ "${#PROBLEMS[@]}" -eq 0 ]; then
  add_result "CA-12" "R4" 0 "sandbox_db healthy con bind mount en $DATA_DIR_ABS, create_host_path false, sin volumen sandbox_data"
else
  add_result "CA-12" "R4" 1 "$(IFS=';'; echo "${PROBLEMS[*]}" | sed 's/;/; /g')"
fi

# ------------------------------------------------------------------- CA-13 (R5)
# nombre|valor esperado (vacío = solo presencia; el valor de la CSP lo fija T-06)
EXPECTED_HEADERS=(
  "Strict-Transport-Security|max-age=31536000; includeSubDomains"
  "X-Content-Type-Options|nosniff"
  "X-Frame-Options|DENY"
  "Referrer-Policy|strict-origin-when-cross-origin"
  "Content-Security-Policy|"
)
PROBLEMS=()
for path in "/" "/api/health-check"; do
  http_get "$BASE_URL$path"
  if [ "$HTTP_EXIT" -ne 0 ]; then PROBLEMS+=("$path: sin respuesta ($HTTP_ERR)"); continue; fi
  for entry in "${EXPECTED_HEADERS[@]}"; do
    name="${entry%%|*}"; exp="${entry#*|}"
    count="$(grep -ic "^${name}:" "$HTTP_HEADERS")"
    if [ "$count" -ne 1 ]; then PROBLEMS+=("$path: $name aparece $count veces"); continue; fi
    val="$(grep -i "^${name}:" "$HTTP_HEADERS" | head -n1 | cut -d: -f2- | sed -E 's/^[[:space:]]+//; s/[[:space:]]+$//')"
    if [ -n "$exp" ] && [ "$val" != "$exp" ]; then PROBLEMS+=("$path: $name='$val'"); fi
    if [ "$name" = "Content-Security-Policy" ] && [[ "$val" != "default-src 'self'"* ]]; then PROBLEMS+=("$path: CSP inesperada '$val'"); fi
  done
  grep -iq '^Server:' "$HTTP_HEADERS" && PROBLEMS+=("$path: cabecera Server presente")
done
if [ "${#PROBLEMS[@]}" -eq 0 ]; then
  add_result "CA-13" "R5" 0 "Cinco cabeceras exactamente una vez y 0 Server en / y /api/health-check"
else
  add_result "CA-13" "R5" 1 "$(IFS=';'; echo "${PROBLEMS[*]}" | sed 's/;/; /g')"
fi

# ------------------------------------------------------------- CA-14 (R6, R7.5)
http_get "$BASE_URL/api/health-check"
if [ "$HTTP_EXIT" -ne 0 ]; then
  add_result "CA-14" "R6" 1 "health-check sin respuesta en 5 s: $HTTP_ERR"
else
  BODY_COMPACT="$(printf '%s' "$HTTP_BODY" | tr -d '[:space:]')"
  OK=1
  if [ "$HTTP_STATUS" = "200" ] && [ "$BODY_COMPACT" = '{"status":"ok"}' ] && awk -v t="$HTTP_TIME" 'BEGIN{exit !(t <= 3)}'; then OK=0; fi
  add_result "CA-14" "R6" "$OK" "GET /api/health-check -> HTTP $HTTP_STATUS en $HTTP_TIME s, cuerpo $BODY_COMPACT"
fi

# ---------------------------------------------------------- resumen (R7.7, R7.8)
echo
echo "== Resumen para la descripción del PR (pegar en .github/PULL_REQUEST_TEMPLATE/fase1.md) =="
echo "| Criterio | Requisito | Estado | Detalle |"
echo "| --- | --- | --- | --- |"
for r in "${RESULTS[@]}"; do
  IFS=$'\t' read -r c q e d <<< "$r"
  printf '| %s | %s | %s | %s |\n' "$c" "$q" "$e" "${d//|/\\|}"
done
echo
echo "Los contenedores siguen en ejecución. Para detenerlos: docker compose -p $PROJECT -f $COMPOSE_FILE down"

if [ "${#FAILED[@]}" -gt 0 ]; then
  echo "RESULTADO: NO APROBADO (${#FAILED[@]} fallo(s): $(IFS=,; echo "${FAILED[*]}" | sed 's/,/, /g')). No abras el PR; corrige y repite la verificación completa." >&2
  exit 1
fi
echo "RESULTADO: APROBADO. CA-09 a CA-14 aprobados; puedes abrir el PR de la Fase 1."
exit 0
