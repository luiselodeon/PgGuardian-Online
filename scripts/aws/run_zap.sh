#!/usr/bin/env bash
# =====================================================================
# PgGuardian - ZAP baseline contra la URL pública (T-23)
#
# Trazabilidad: componente C12 del diseño (Paquete_Evidencia) · RF-08.2 ·
# CA-27 · Requirements 25.1, 25.2 y 25.6.
#
# Pasos (un mensaje por paso):
#  1. Precondiciones: argumento <AppDomain|URL> válido (se normaliza a
#     https://<dominio>), docker, curl y jq disponibles, y carpeta de
#     evidencia existente. No sobrescribe un reporte con la misma fecha.
#  2. La URL pública responde con HTTP 2xx (curl, siguiendo redirecciones).
#     Si no, el script se detiene sin ejecutar ZAP (R25.1).
#  3. docker pull de ghcr.io/zaproxy/zaproxy:stable y registro del digest.
#  4. zap-baseline.py -t <URL> -r <html> -J <json> (spider de ZAP_MINUTOS
#     minutos y reglas pasivas; no ataca la aplicación).
#  5. Copia a docs/aws/evidencia/ de:
#       zap-baseline-<AAAAMMDDTHHMMZ>.html  reporte completo (R25.1)
#       zap-baseline-<AAAAMMDDTHHMMZ>.json  mismo reporte en JSON
#       zap-baseline-<AAAAMMDDTHHMMZ>.txt   fecha y hora UTC, URL analizada,
#                                           imagen, código de salida y
#                                           salida completa de ZAP
#  6. Conteo de hallazgos por riesgo con jq. Los de riesgo medio o alto se
#     listan: corregirlos y repetir el script, o justificar cada uno en
#     docs/aws/evidencia/justificaciones.md (R25.2).
#  7. Resumen y línea final "RESULTADO: <fecha> <url> altos=<n> medios=<n>
#     bajos=<n> informativos=<n> <reporte>".
#
# El nombre de los archivos lleva la fecha y hora UTC de la ejecución; el
# reporte HTML de ZAP muestra además la URL analizada ("Site") y la fecha de
# generación. El .txt deja las dos cosas por escrito junto al reporte.
#
# Uso (en CloudShell o en un equipo Linux con Docker, desde cualquier
# directorio del repositorio clonado):
#   bash scripts/aws/run_zap.sh <AppDomain|URL>
#   (p. ej. bash scripts/aws/run_zap.sh 3-14-31-64.sslip.io)
#   El dominio es el output AppDomain del stack:
#     aws cloudformation describe-stacks --stack-name pgguardian \
#       --query "Stacks[0].Outputs[?OutputKey=='AppDomain'].OutputValue" --output text
#   Si se usó el respaldo de DuckDNS (R19.4): <nombre>.duckdns.org.
#
# Variables de entorno opcionales: ZAP_IMAGE (ghcr.io/zaproxy/zaproxy:stable),
# ZAP_MINUTOS (1, duración del spider) y EVIDENCIA_DIR (docs/aws/evidencia
# del repositorio).
#
# Códigos de salida:
#   0  reporte guardado, sin hallazgos de riesgo medio ni alto
#   1  precondición o fallo (URL sin HTTP 2xx, docker, copia de archivos)
#   2  uso incorrecto
#   3  reporte guardado con hallazgos de riesgo medio o alto: corregir y
#      repetir, o justificarlos en justificaciones.md (R25.2)
#   4  ZAP no terminó el análisis (código 3 de zap-baseline.py o sin reporte)
# =====================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ZAP_IMAGE="${ZAP_IMAGE:-ghcr.io/zaproxy/zaproxy:stable}"
ZAP_MINUTOS="${ZAP_MINUTOS:-1}"
EVIDENCIA_DIR="${EVIDENCIA_DIR:-$REPO_ROOT/docs/aws/evidencia}"
JUSTIFICACIONES="docs/aws/evidencia/justificaciones.md"

PASO=0
paso() { PASO=$((PASO + 1)); printf '\n==> [%d] %s\n' "$PASO" "$*"; }
info() { printf '    %s\n' "$*"; }
fallo() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

uso() {
  cat >&2 <<'TXT'
Uso: bash scripts/aws/run_zap.sh <AppDomain|URL>
  <AppDomain>  Output AppDomain del stack pgguardian (a-b-c-d.sslip.io) o el
               subdominio de respaldo <nombre>.duckdns.org (R19.4).
  <URL>        URL pública completa, solo https (p. ej. https://3-14-31-64.sslip.io/).
TXT
  exit 2
}

TMP_DIR=""
limpiar() { [ -z "$TMP_DIR" ] || rm -rf "$TMP_DIR"; }
trap limpiar EXIT

# ------------------------------------------------------------------ 1
paso "Precondiciones (argumento, docker, curl, jq y carpeta de evidencia)"

[ $# -eq 1 ] || uso
case "$1" in
  -h|--help) uso ;;
  http://*) fallo "'$1' usa http; la URL pública se analiza por https (R25.1)." ;;
  https://*) URL="$1" ;;
  *) URL="https://$1" ;;
esac
URL_RE='^https://[A-Za-z0-9]([A-Za-z0-9.-]*[A-Za-z0-9])?(:[0-9]{1,5})?(/[^[:space:]]*)?$'
[[ "$URL" =~ $URL_RE ]] \
  || fallo "'$1' no es un dominio ni una URL https válida (p. ej. 3-14-31-64.sslip.io)."
[[ "$ZAP_MINUTOS" =~ ^[1-9][0-9]*$ ]] || fallo "ZAP_MINUTOS=$ZAP_MINUTOS no es un entero positivo."
command -v docker >/dev/null || fallo "falta docker (CloudShell lo incluye; en Ubuntu: Docker Engine)."
docker info >/dev/null 2>&1 || fallo "docker no responde (¿servicio detenido o usuario sin permisos?)."
command -v curl >/dev/null || fallo "falta curl."
command -v jq >/dev/null || fallo "falta jq."
[ -d "$EVIDENCIA_DIR" ] || fallo "no existe la carpeta de evidencia $EVIDENCIA_DIR."
[ -w "$EVIDENCIA_DIR" ] || fallo "no se puede escribir en $EVIDENCIA_DIR."

FECHA="$(date -u +%Y%m%dT%H%MZ)"
FECHA_ISO="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
BASE="zap-baseline-$FECHA"
HTML_DEST="$EVIDENCIA_DIR/$BASE.html"
JSON_DEST="$EVIDENCIA_DIR/$BASE.json"
TXT_DEST="$EVIDENCIA_DIR/$BASE.txt"
for f in "$HTML_DEST" "$JSON_DEST" "$TXT_DEST"; do
  [ ! -e "$f" ] || fallo "ya existe $f; esperar un minuto y repetir para no sobrescribir evidencia."
done
info "URL analizada: $URL"
info "fecha y hora (UTC): $FECHA_ISO"
info "destino: $EVIDENCIA_DIR/$BASE.{html,json,txt}"

# ------------------------------------------------------------------ 2
paso "La URL pública responde con HTTP 2xx (curl)"

CODIGO="$(curl -sS -L -o /dev/null -w '%{http_code}' --max-time 30 "$URL" 2>&1)" \
  || fallo "curl no pudo conectar con $URL: $(printf '%s' "$CODIGO" | tr '\n' ' ')"
[[ "$CODIGO" =~ ^2[0-9][0-9]$ ]] \
  || fallo "$URL respondió HTTP $CODIGO; ZAP baseline se ejecuta solo con HTTP exitoso (R25.1). Revisar deploy.sh y Caddy."
info "HTTP $CODIGO"

# ------------------------------------------------------------------ 3
paso "Imagen de ZAP ($ZAP_IMAGE)"

docker pull --quiet "$ZAP_IMAGE" >/dev/null || fallo "falló docker pull $ZAP_IMAGE."
DIGEST="$(docker image inspect --format '{{if .RepoDigests}}{{index .RepoDigests 0}}{{end}}' "$ZAP_IMAGE" 2>/dev/null || true)"
info "imagen: ${DIGEST:-$ZAP_IMAGE}"

# ------------------------------------------------------------------ 4
paso "ZAP baseline (zap-baseline.py, spider de $ZAP_MINUTOS min y reglas pasivas)"

TMP_DIR="$(mktemp -d)"
# El contenedor corre como el usuario zap (uid 1000) y escribe en /zap/wrk.
chmod 777 "$TMP_DIR"
LOG="$TMP_DIR/zap-salida.log"
ZAP_RC=0
docker run --rm -v "$TMP_DIR:/zap/wrk:rw" "$ZAP_IMAGE" \
  zap-baseline.py -t "$URL" -m "$ZAP_MINUTOS" -r "$BASE.html" -J "$BASE.json" 2>&1 \
  | tee "$LOG" || ZAP_RC=$?
# zap-baseline.py: 0 sin avisos, 1 con FAIL, 2 con WARN y sin FAIL, 3 error.
case "$ZAP_RC" in
  0|1|2) info "zap-baseline.py terminó con código $ZAP_RC (0 sin avisos, 1 FAIL, 2 WARN)." ;;
  *) printf 'ERROR: zap-baseline.py terminó con código %s; el análisis no se completó.\n' "$ZAP_RC" >&2 ;;
esac
if [ ! -s "$TMP_DIR/$BASE.html" ] || [ ! -s "$TMP_DIR/$BASE.json" ]; then
  printf 'ERROR: ZAP no generó el reporte HTML o JSON; revisar la salida anterior.\n' >&2
  exit 4
fi
[ "$ZAP_RC" -le 2 ] || exit 4

# ------------------------------------------------------------------ 5
paso "Copia del reporte a la carpeta de evidencia"

cp "$TMP_DIR/$BASE.html" "$HTML_DEST" || fallo "no se pudo copiar el reporte HTML a $HTML_DEST."
cp "$TMP_DIR/$BASE.json" "$JSON_DEST" || fallo "no se pudo copiar el reporte JSON a $JSON_DEST."
{
  printf 'Reporte ZAP baseline - PgGuardian (T-23, R25.1)\n'
  printf 'Fecha y hora de ejecución (UTC): %s\n' "$FECHA_ISO"
  printf 'URL analizada: %s\n' "$URL"
  printf 'HTTP previo: %s\n' "$CODIGO"
  printf 'Imagen: %s\n' "${DIGEST:-$ZAP_IMAGE}"
  printf 'Comando: zap-baseline.py -t %s -m %s -r %s.html -J %s.json\n' "$URL" "$ZAP_MINUTOS" "$BASE" "$BASE"
  printf 'Código de salida de zap-baseline.py: %s\n' "$ZAP_RC"
  printf '\n----- Salida completa de ZAP -----\n'
  cat "$LOG"
} > "$TXT_DEST" || fallo "no se pudo escribir $TXT_DEST."
grep -qF "${URL%/}" "$HTML_DEST" \
  || info "aviso: el HTML no contiene literalmente '${URL%/}'; la URL queda registrada en $BASE.txt."
info "$HTML_DEST"
info "$JSON_DEST"
info "$TXT_DEST"

# ------------------------------------------------------------------ 6
paso "Hallazgos por riesgo (riskcode de ZAP: 3 alto, 2 medio, 1 bajo, 0 informativo)"

contar() {
  jq --arg r "$1" '[.site[]?.alerts[]? | select((.riskcode | tostring) == $r)] | length' "$JSON_DEST"
}
ALTOS="$(contar 3)" || fallo "no se pudo leer $JSON_DEST con jq."
MEDIOS="$(contar 2)"
BAJOS="$(contar 1)"
INFORMATIVOS="$(contar 0)"
info "altos=$ALTOS medios=$MEDIOS bajos=$BAJOS informativos=$INFORMATIVOS"

if [ "$ALTOS" -gt 0 ] || [ "$MEDIOS" -gt 0 ]; then
  info "hallazgos de riesgo medio o alto:"
  jq -r '[.site[]?.alerts[]? | select((.riskcode | tostring) == "3" or (.riskcode | tostring) == "2")]
    | sort_by(.riskcode) | reverse | .[]
    | "      - [\(.riskdesc)] \(.name // .alert) (pluginid \(.pluginid), \(.count // "?") instancias)"' \
    "$JSON_DEST"
fi

# ------------------------------------------------------------------ 7
paso "Resumen"

if [ "$ALTOS" -gt 0 ] || [ "$MEDIOS" -gt 0 ]; then
  info "El reporte tiene $ALTOS hallazgos altos y $MEDIOS medios (R25.2). Para cada uno:"
  info "  corregirlo (p. ej. cabeceras en el Caddyfile) y repetir este script, o"
  info "  documentar la causa y la razón de aceptación del riesgo en $JUSTIFICACIONES,"
  info "  citando $BASE.html."
  printf '\nRESULTADO: %s %s altos=%s medios=%s bajos=%s informativos=%s %s\n' \
    "$FECHA_ISO" "$URL" "$ALTOS" "$MEDIOS" "$BAJOS" "$INFORMATIVOS" "$BASE.html"
  exit 3
fi
info "Sin hallazgos de riesgo medio ni alto; el reporte sirve para el Paquete_Evidencia (R25.6)."
printf '\nRESULTADO: %s %s altos=%s medios=%s bajos=%s informativos=%s %s\n' \
  "$FECHA_ISO" "$URL" "$ALTOS" "$MEDIOS" "$BAJOS" "$INFORMATIVOS" "$BASE.html"
printf 'run_zap.sh terminó sin errores.\n'
