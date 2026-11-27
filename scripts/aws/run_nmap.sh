#!/usr/bin/env bash
# =====================================================================
# PgGuardian - Escaneo nmap de la Elastic IP para el Paquete_Evidencia (T-24)
#
# Trazabilidad: componente C12 del diseño (Paquete_Evidencia) · RF-08.2 ·
# CA-27 · Requirements 25.3, 25.4 y 25.6 (y la verificación de R12.3).
#
# Pasos (un mensaje por paso):
#  1. Precondiciones: argumentos, nmap disponible y Elastic IP. Si no se pasa
#     la IP, se lee el output PublicIp del stack pgguardian (requiere aws).
#  2. Archivo de salida: docs/aws/evidencia/nmap-<AAAAMMDDTHHMMZ>.txt, con una
#     cabecera de fecha y hora UTC de inicio, IP y comando ejecutado.
#  3. Escaneo: nmap -Pn -p 1-65535 <eip>; la salida completa se guarda en el
#     archivo y se muestra en pantalla.
#  4. Análisis: lista los puertos TCP en estado open. Avisa si hay alguno
#     distinto de 80 y 443 (R25.4: cerrar el puerto o justificarlo en
#     docs/aws/evidencia/justificaciones.md) y si 80 o 443 no están open
#     (R12.3).
#  5. Resumen y línea final "RESULTADO: <fecha> <eip> <puertos open> <archivo>".
#
# Debe ejecutarse desde una red externa a la VPC (p. ej. el equipo de un
# integrante), no desde la Instancia: el escaneo valida el Security_Group.
# Un escaneo de los 65535 puertos con la mayoría en filtered puede tardar
# varios minutos; NMAP_OPCIONES permite añadir, p. ej., -T4.
#
# Uso (desde la raíz del repo):
#   bash scripts/aws/run_nmap.sh [<elastic-ip>]
#   (p. ej. bash scripts/aws/run_nmap.sh 3.140.10.20)
#
# Variables de entorno opcionales: STACK_NAME (pgguardian, solo si no se pasa
# la IP), EVIDENCIA_DIR (docs/aws/evidencia) y NMAP_OPCIONES (vacío).
#
# Códigos de salida:
#   0  solo 80 y 443 abiertos
#   1  precondición o fallo de nmap
#   2  uso incorrecto
#   3  hay puertos abiertos distintos de 80 y 443: cerrar o justificar (R25.4)
#   4  sin puertos extra, pero 80 o 443 no aparecen open (revisar Caddy/SG)
# =====================================================================

set -euo pipefail

STACK_NAME="${STACK_NAME:-pgguardian}"
EVIDENCIA_DIR="${EVIDENCIA_DIR:-docs/aws/evidencia}"
NMAP_OPCIONES="${NMAP_OPCIONES:-}"
JUSTIFICACIONES="docs/aws/evidencia/justificaciones.md"
PUERTOS_PERMITIDOS=(80 443)

PASO=0
paso() { PASO=$((PASO + 1)); printf '\n==> [%d] %s\n' "$PASO" "$*"; }
info() { printf '    %s\n' "$*"; }
aviso() { printf 'AVISO: %s\n' "$*" >&2; }
fallo() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }
una_linea() { printf '%s' "$*" | tr '\n' ' '; }

uso() {
  cat >&2 <<'TXT'
Uso: bash scripts/aws/run_nmap.sh [<elastic-ip>]
  <elastic-ip>  IPv4 pública de la Instancia. Si se omite, se lee el output
                PublicIp del stack (STACK_NAME, por defecto pgguardian).
TXT
  exit 2
}

ipv4_valida() {
  local ip="$1" octeto
  local -a octetos
  [[ "$ip" =~ ^[0-9]{1,3}(\.[0-9]{1,3}){3}$ ]] || return 1
  IFS=. read -r -a octetos <<< "$ip"
  for octeto in "${octetos[@]}"; do
    [ "$((10#$octeto))" -le 255 ] || return 1
  done
}

# ------------------------------------------------------------------ 1
paso "Precondiciones (argumentos, nmap y Elastic IP)"

EIP=""
while [ $# -gt 0 ]; do
  case "$1" in
    -h|--help) uso ;;
    -*) printf 'ERROR: opción desconocida: %s\n' "$1" >&2; uso ;;
    *) [ -z "$EIP" ] || uso; EIP="$1"; shift ;;
  esac
done
command -v nmap >/dev/null || fallo "falta nmap (instalarlo en el equipo desde el que se escanea)."

if [ -z "$EIP" ]; then
  command -v aws >/dev/null \
    || fallo "no se pasó la Elastic IP y falta la AWS CLI para leer el output PublicIp; pasar la IP como argumento."
  EIP="$(aws cloudformation describe-stacks --stack-name "$STACK_NAME" \
    --query "Stacks[0].Outputs[?OutputKey=='PublicIp'].OutputValue" --output text 2>&1)" \
    || fallo "no se pudo leer el output PublicIp del stack $STACK_NAME: $(una_linea "$EIP")"
  info "Elastic IP leída del output PublicIp del stack $STACK_NAME."
fi
ipv4_valida "$EIP" || fallo "'$EIP' no es una dirección IPv4 válida."
info "Elastic IP: $EIP"
info "$(nmap --version | head -n 1)"

# ------------------------------------------------------------------ 2
paso "Archivo de salida en $EVIDENCIA_DIR"

mkdir -p "$EVIDENCIA_DIR"
FECHA="$(date -u +%Y%m%dT%H%MZ)"
SALIDA="$EVIDENCIA_DIR/nmap-$FECHA.txt"
if [ -e "$SALIDA" ]; then
  FECHA="$(date -u +%Y%m%dT%H%M%SZ)"
  SALIDA="$EVIDENCIA_DIR/nmap-$FECHA.txt"
fi
[ ! -e "$SALIDA" ] || fallo "$SALIDA ya existe; esperar un segundo y repetir."

# NMAP_OPCIONES se divide en palabras a propósito (p. ej. "-T4 --reason").
read -r -a OPCIONES_EXTRA <<< "$NMAP_OPCIONES"
NMAP_CMD=(nmap -Pn -p 1-65535 "${OPCIONES_EXTRA[@]}" "$EIP")
{
  printf '# PgGuardian - Paquete_Evidencia (R25.3)\n'
  printf '# Fecha y hora de inicio (UTC): %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  printf '# Elastic IP: %s\n' "$EIP"
  printf '# Comando: %s\n\n' "${NMAP_CMD[*]}"
} > "$SALIDA"
info "archivo: $SALIDA"

# ------------------------------------------------------------------ 3
paso "Escaneo TCP 1-65535 (${NMAP_CMD[*]})"

if ! "${NMAP_CMD[@]}" 2>&1 | tee -a "$SALIDA"; then
  fallo "nmap terminó con error; la salida parcial queda en $SALIDA."
fi
printf '\n# Fecha y hora de fin (UTC): %s\n' "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$SALIDA"

# ------------------------------------------------------------------ 4
paso "Análisis de puertos abiertos"

mapfile -t ABIERTOS < <(awk '$1 ~ /^[0-9]+\/tcp$/ && $2 == "open" { split($1, p, "/"); print p[1] }' "$SALIDA")
EXTRA=()
for puerto in "${ABIERTOS[@]}"; do
  case " ${PUERTOS_PERMITIDOS[*]} " in
    *" $puerto "*) ;;
    *) EXTRA+=("$puerto") ;;
  esac
done
FALTANTES=()
for puerto in "${PUERTOS_PERMITIDOS[@]}"; do
  case " ${ABIERTOS[*]} " in
    *" $puerto "*) ;;
    *) FALTANTES+=("$puerto") ;;
  esac
done
LISTA_ABIERTOS="$(IFS=,; printf '%s' "${ABIERTOS[*]:-ninguno}")"
info "puertos TCP open: $LISTA_ABIERTOS"

CODIGO=0
if [ ${#EXTRA[@]} -gt 0 ]; then
  aviso "puertos abiertos distintos de 80 y 443: ${EXTRA[*]}."
  aviso "R25.4: cerrar cada puerto (Security_Group o servicio) y repetir el escaneo, o documentar"
  aviso "una justificación escrita por puerto en $JUSTIFICACIONES."
  CODIGO=3
fi
if [ ${#FALTANTES[@]} -gt 0 ]; then
  aviso "no aparecen open: ${FALTANTES[*]} (R12.3 espera 80 y 443 abiertos); revisar Caddy y el Security_Group."
  [ "$CODIGO" -ne 0 ] || CODIGO=4
fi
[ "$CODIGO" -ne 0 ] || info "solo 80 y 443 abiertos; el resto, filtered o closed."

# ------------------------------------------------------------------ 5
paso "Resumen"

info "salida completa: $SALIDA"
printf '\nRESULTADO: %s %s %s %s\n' "$FECHA" "$EIP" "$LISTA_ABIERTOS" "$SALIDA"
if [ "$CODIGO" -eq 0 ]; then
  printf 'run_nmap.sh terminó sin errores.\n'
else
  printf 'run_nmap.sh terminó con avisos (código %d).\n' "$CODIGO"
fi
exit "$CODIGO"
