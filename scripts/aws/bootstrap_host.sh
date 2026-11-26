#!/usr/bin/env bash
# =====================================================================
# PgGuardian - Configuración del host Ubuntu 24.04 de la Instancia (T-16)
#
# Trazabilidad: componente C9 del diseño · RF-04.4, RF-05.5, RF-06.3,
# RF-06.4, RF-06.7 · CA-12, CA-17, CA-18, CA-20, CA-22 · Requirements 4.5 a
# 4.9, 11, 15, 18 y 19.8.
#
# Pasos (un mensaje por paso):
#  1. Precondiciones: root, argumento <SandboxVolumeId> válido y enlace
#     /dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_vol<id sin guion>.
#     Si el enlace no existe, aborta sin modificar nada.
#  2. Sistema de archivos del Volumen_Sandbox: mkfs.ext4 solo si blkid no
#     encuentra ninguno (nunca reformatea).
#  3. Entrada en /etc/fstab por UUID con nofail (sin duplicarla) y montaje en
#     /srv/sandbox.
#  4. Comprueba con findmnt que /srv/sandbox es el punto de montaje del
#     Volumen_Sandbox y solo entonces crea /srv/sandbox/pgdata (999:999).
#     Si la comprobación falla, aborta sin crear el directorio: uno creado en el
#     disco raíz anularía la protección create_host_path: false del compose.
#  5. Swap /swapfile de 2 GiB persistente, sin duplicar áreas.
#  6. unattended-upgrades solo con el origen -security y 20auto-upgrades "1"/"1".
#  7. Docker Engine y el plugin Compose desde el repositorio oficial de Docker;
#     systemctl enable docker para que los contenedores con
#     restart: unless-stopped vuelvan tras detener e iniciar la Instancia.
#  8. Resumen del estado final.
#
# Idempotente: una segunda ejecución no formatea el disco, no duplica entradas
# en /etc/fstab, no crea un segundo swap ni reinstala Docker.
#
# La plantilla de CloudFormation no lleva UserData: el script se ejecuta a
# mano por Session Manager (docs/aws/runbook.md, sección 4).
#
# Uso: sudo bash ~/bootstrap_host.sh <SandboxVolumeId>
#      (p. ej. sudo bash ~/bootstrap_host.sh vol-0123456789abcdef0)
# =====================================================================

set -euo pipefail

MOUNT_POINT="/srv/sandbox"
PGDATA_DIR="${MOUNT_POINT}/pgdata"
PG_UID=999            # usuario postgres de la imagen postgres:16
PG_GID=999
SWAPFILE="/swapfile"
SWAP_BYTES=2147483648 # 2 GiB (R15.1)
FS_LABEL="pgg-sandbox"
UU_FILE="/etc/apt/apt.conf.d/52pgguardian-security-only"
AUTO_FILE="/etc/apt/apt.conf.d/20auto-upgrades"
APT_OPTS=(-y -q -o DPkg::Lock::Timeout=300)

export DEBIAN_FRONTEND=noninteractive

PASO=0
paso() { PASO=$((PASO + 1)); printf '\n==> [%d] %s\n' "$PASO" "$*"; }
info() { printf '    %s\n' "$*"; }
fallo() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

uso() {
  cat >&2 <<'TXT'
Uso: sudo bash bootstrap_host.sh <SandboxVolumeId>
  <SandboxVolumeId>  Output SandboxVolumeId del stack pgguardian (vol-...).
TXT
  exit 2
}

# ------------------------------------------------------------------ 1
paso "Precondiciones (root, argumento y dispositivo del Volumen_Sandbox)"

[ "$#" -eq 1 ] || uso
VOLUME_ID="$1"
[[ "$VOLUME_ID" =~ ^vol-[0-9a-f]{8,17}$ ]] \
  || fallo "'$VOLUME_ID' no es un ID de volumen EBS válido (vol-...)."
[ "$(id -u)" -eq 0 ] || fallo "ejecutar como root: sudo bash $0 $VOLUME_ID"
if ! command -v findmnt >/dev/null || ! command -v blkid >/dev/null; then
  fallo "faltan findmnt o blkid (paquete util-linux)."
fi

BY_ID_LINK="/dev/disk/by-id/nvme-Amazon_Elastic_Block_Store_${VOLUME_ID//-/}"
if [ ! -e "$BY_ID_LINK" ]; then
  fallo "no existe $BY_ID_LINK. El Volumen_Sandbox $VOLUME_ID no está adjunto a esta instancia o el ID no es el del output SandboxVolumeId. No se modificó nada."
fi
DEVICE="$(readlink -f "$BY_ID_LINK")"
[ -b "$DEVICE" ] || fallo "$BY_ID_LINK no apunta a un dispositivo de bloques ($DEVICE). No se modificó nada."

ROOT_SOURCE="$(findmnt -n -o SOURCE /)"
ROOT_DISK="$(lsblk -n -d -o PKNAME "$(readlink -f "$ROOT_SOURCE")" 2>/dev/null || true)"
if [ "$(readlink -f "$ROOT_SOURCE")" = "$DEVICE" ] || [ "/dev/${ROOT_DISK}" = "$DEVICE" ]; then
  fallo "$DEVICE es el disco raíz, no el Volumen_Sandbox. No se modificó nada."
fi
if [ "$(lsblk -n -o NAME "$DEVICE" | wc -l)" -gt 1 ]; then
  fallo "$DEVICE tiene particiones; se esperaba un disco sin particionar. No se modificó nada."
fi
info "Volumen_Sandbox $VOLUME_ID -> $DEVICE (raíz en $ROOT_SOURCE)"

# ------------------------------------------------------------------ 2
paso "Sistema de archivos del Volumen_Sandbox"

# blkid sale con código 2 si no encuentra ningún sistema de archivos.
FS_TYPE="$(blkid -o value -s TYPE "$DEVICE" || true)"
if [ -z "$FS_TYPE" ]; then
  info "$DEVICE no tiene sistema de archivos: se formatea con ext4."
  mkfs.ext4 -q -L "$FS_LABEL" "$DEVICE"
  udevadm settle || true
  FS_TYPE="$(blkid -o value -s TYPE "$DEVICE" || true)"
  [ "$FS_TYPE" = "ext4" ] || fallo "mkfs.ext4 terminó pero blkid no ve ext4 en $DEVICE."
elif [ "$FS_TYPE" = "ext4" ]; then
  info "$DEVICE ya tiene ext4: no se formatea."
else
  fallo "$DEVICE tiene un sistema de archivos $FS_TYPE (se esperaba ext4). No se formatea para no perder datos; revisar a mano."
fi

FS_UUID="$(blkid -o value -s UUID "$DEVICE")"
[ -n "$FS_UUID" ] || fallo "no se pudo leer el UUID de $DEVICE."
info "UUID=$FS_UUID"

# ------------------------------------------------------------------ 3
paso "Entrada en /etc/fstab (UUID, nofail) y montaje en $MOUNT_POINT"

FSTAB_LINE="UUID=${FS_UUID} ${MOUNT_POINT} ext4 defaults,nofail,x-systemd.device-timeout=10s 0 2"
EXISTING="$(awk -v mp="$MOUNT_POINT" '$1 !~ /^#/ && $2 == mp' /etc/fstab)"
if [ -z "$EXISTING" ]; then
  cp -p /etc/fstab "/etc/fstab.bak-bootstrap-$(date -u +%Y%m%dT%H%M%SZ)"
  printf '%s\n' "$FSTAB_LINE" >> /etc/fstab
  info "agregada: $FSTAB_LINE"
elif [ "$(printf '%s\n' "$EXISTING" | wc -l)" -ne 1 ]; then
  fallo "/etc/fstab tiene varias entradas para $MOUNT_POINT; dejar solo una y repetir."
elif [ "$(awk '{print $1}' <<< "$EXISTING")" != "UUID=${FS_UUID}" ]; then
  fallo "/etc/fstab ya monta $MOUNT_POINT desde otro origen ($EXISTING); revisar a mano."
elif ! awk '{print $4}' <<< "$EXISTING" | tr ',' '\n' | grep -qx nofail; then
  fallo "la entrada de /etc/fstab para $MOUNT_POINT no tiene nofail ($EXISTING); corregirla y repetir."
else
  info "ya existe: $EXISTING"
fi
systemctl daemon-reload

mkdir -p "$MOUNT_POINT"
if findmnt -n --mountpoint "$MOUNT_POINT" >/dev/null; then
  info "$MOUNT_POINT ya está montado."
else
  # Si el directorio del disco raíz tiene contenido, el montaje lo ocultaría.
  CONTENIDO="$(find "$MOUNT_POINT" -mindepth 1 -maxdepth 1 -printf '%f ')"
  if [ -n "$CONTENIDO" ]; then
    fallo "$MOUNT_POINT no está montado y contiene archivos en el disco raíz (${CONTENIDO% }). Revisar a mano antes de montar."
  fi
  mount "$MOUNT_POINT"
  info "montado $MOUNT_POINT."
fi

# ------------------------------------------------------------------ 4
paso "Comprobación con findmnt y directorio de datos $PGDATA_DIR"

MNT_SOURCE="$(findmnt -n -o SOURCE --mountpoint "$MOUNT_POINT" || true)"
MNT_UUID="$(findmnt -n -o UUID --mountpoint "$MOUNT_POINT" || true)"
if [ -z "$MNT_SOURCE" ]; then
  fallo "findmnt: $MOUNT_POINT no es un punto de montaje. No se crea $PGDATA_DIR."
fi
if [ "$(readlink -f "$MNT_SOURCE")" != "$DEVICE" ] || [ "$MNT_UUID" != "$FS_UUID" ]; then
  fallo "findmnt: $MOUNT_POINT está montado desde $MNT_SOURCE (UUID ${MNT_UUID:-?}), no desde el Volumen_Sandbox $DEVICE (UUID $FS_UUID). No se crea $PGDATA_DIR."
fi
info "findmnt: $MOUNT_POINT <- $MNT_SOURCE (UUID $MNT_UUID)"

mkdir -p "$PGDATA_DIR"
chown "${PG_UID}:${PG_GID}" "$PGDATA_DIR"
chmod 700 "$PGDATA_DIR"
info "$PGDATA_DIR listo ($(stat -c '%u:%g %a' "$PGDATA_DIR"))."

# ------------------------------------------------------------------ 5
paso "Swap $SWAPFILE de 2 GiB"

swap_activo() { swapon --show=NAME --noheadings | awk -v f="$1" '$1 == f' | grep -q .; }

OTROS_SWAP="$(swapon --show=NAME --noheadings | awk -v f="$SWAPFILE" '$1 != f' | paste -sd' ' -)"
[ -z "$OTROS_SWAP" ] || fallo "hay otras áreas de swap activas ($OTROS_SWAP); se espera una sola (R15.1)."

if swap_activo "$SWAPFILE"; then
  TAM="$(stat -c %s "$SWAPFILE")"
  [ "$TAM" -eq "$SWAP_BYTES" ] \
    || fallo "$SWAPFILE está activo con $TAM bytes (se esperaban $SWAP_BYTES). Desactivarlo con swapoff y repetir."
  info "$SWAPFILE ya está activo (2 GiB)."
else
  if [ -e "$SWAPFILE" ] && [ "$(stat -c %s "$SWAPFILE")" -ne "$SWAP_BYTES" ]; then
    info "$SWAPFILE existe con otro tamaño y no está activo: se recrea."
    rm -f "$SWAPFILE"
  fi
  if [ ! -e "$SWAPFILE" ]; then
    fallocate -l "$SWAP_BYTES" "$SWAPFILE"
    chmod 600 "$SWAPFILE"
    mkswap "$SWAPFILE" >/dev/null
    info "creado $SWAPFILE."
  fi
  chmod 600 "$SWAPFILE"
  if ! blkid -o value -s TYPE "$SWAPFILE" 2>/dev/null | grep -qx swap; then
    mkswap "$SWAPFILE" >/dev/null
  fi
  swapon "$SWAPFILE"
  info "activado $SWAPFILE."
fi

if awk -v f="$SWAPFILE" '$1 !~ /^#/ && $1 == f' /etc/fstab | grep -q .; then
  info "/etc/fstab ya tiene la entrada de $SWAPFILE."
else
  printf '%s none swap sw 0 0\n' "$SWAPFILE" >> /etc/fstab
  info "agregada a /etc/fstab: $SWAPFILE none swap sw 0 0"
fi

# ------------------------------------------------------------------ 6
paso "unattended-upgrades (solo -security) y 20auto-upgrades"

apt-get "${APT_OPTS[@]}" update
# jq lo usan los bloques de verificación del runbook que corren en la Instancia.
apt-get "${APT_OPTS[@]}" install unattended-upgrades jq

# apt lee apt.conf.d en orden léxico: este archivo va después de
# 50unattended-upgrades y vacía sus listas con #clear antes de redefinirlas.
cat > "$UU_FILE" <<'CONF'
// PgGuardian (T-16 / R18.1): solo parches de seguridad de Ubuntu.
#clear Unattended-Upgrade::Allowed-Origins;
#clear Unattended-Upgrade::Origins-Pattern;
Unattended-Upgrade::Allowed-Origins {
        "${distro_id}:${distro_codename}-security";
};
CONF
cat > "$AUTO_FILE" <<'CONF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
CONF
systemctl enable --now unattended-upgrades >/dev/null 2>&1
info "orígenes permitidos: $(apt-config dump Unattended-Upgrade::Allowed-Origins | sed -n 's/^Unattended-Upgrade::Allowed-Origins:: "\(.*\)";$/\1/p' | paste -sd' ' -)"
info "unattended-upgrades: $(systemctl is-active unattended-upgrades) / $(systemctl is-enabled unattended-upgrades)"

# ------------------------------------------------------------------ 7
paso "Docker Engine y plugin Compose"

if command -v docker >/dev/null && docker compose version >/dev/null 2>&1; then
  info "Docker ya está instalado: $(docker --version); $(docker compose version)"
else
  apt-get "${APT_OPTS[@]}" install ca-certificates curl
  install -m 0755 -d /etc/apt/keyrings
  curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
  chmod a+r /etc/apt/keyrings/docker.asc
  # shellcheck source=/dev/null
  CODENAME="$(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")"
  printf 'deb [arch=%s signed-by=/etc/apt/keyrings/docker.asc] https://download.docker.com/linux/ubuntu %s stable\n' \
    "$(dpkg --print-architecture)" "$CODENAME" > /etc/apt/sources.list.d/docker.list
  apt-get "${APT_OPTS[@]}" update
  apt-get "${APT_OPTS[@]}" install docker-ce docker-ce-cli containerd.io \
    docker-buildx-plugin docker-compose-plugin
  info "instalado: $(docker --version); $(docker compose version)"
fi
systemctl enable --now containerd docker >/dev/null 2>&1
if id ubuntu >/dev/null 2>&1 && ! id -nG ubuntu | tr ' ' '\n' | grep -qx docker; then
  usermod -aG docker ubuntu
  info "usuario ubuntu agregado al grupo docker (efectivo en la próxima sesión)."
fi
info "docker: $(systemctl is-active docker) / $(systemctl is-enabled docker)"

# ------------------------------------------------------------------ 8
paso "Resumen"

info "montaje:  $(findmnt -n -o SOURCE,UUID,FSTYPE,OPTIONS --mountpoint "$MOUNT_POINT")"
info "pgdata:   $PGDATA_DIR $(stat -c '%u:%g %a' "$PGDATA_DIR")"
info "swap:     $(swapon --show=NAME,SIZE --noheadings --bytes | paste -sd';' -)"
info "parches:  unattended-upgrades $(systemctl is-active unattended-upgrades)/$(systemctl is-enabled unattended-upgrades)"
info "docker:   $(systemctl is-active docker)/$(systemctl is-enabled docker)"
info "Siguiente paso: SANDBOX_DATA_DIR=$PGDATA_DIR en el .env (make_env.sh, tarea 6.2) y verificaciones de la sección 4 del runbook."
printf '\nbootstrap_host.sh terminó sin errores.\n'
