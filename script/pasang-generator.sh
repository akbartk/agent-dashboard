#!/bin/bash
# Pasang + nyalakan generator sebagai service systemd USER (idempoten). Jalankan sebagai user pemilik project di host:
#   script/pasang-generator.sh
# Unit templat conf/agent-dashboard-generator.service memuat penanda @AKAR@; skrip ini menggantinya dengan path project
# ini saat memasang. Agar jalan tanpa sesi login, linger harus aktif (sekali): sudo loginctl enable-linger "$(id -un)"
set -euo pipefail
AKAR=$(dirname "$(dirname "$(readlink -f "$0")")")
UNIT=agent-dashboard-generator.service
TUJUAN="$HOME/.config/systemd/user"
# Path masuk ke ExecStart/Documentation: hanya karakter aman (tanpa spasi atau karakter khusus sed/systemd).
case "$AKAR" in
  ""|*[!A-Za-z0-9_./-]*) echo "path project memuat karakter yang tidak didukung: $AKAR" >&2; exit 1 ;;
esac
export XDG_RUNTIME_DIR="${XDG_RUNTIME_DIR:-/run/user/$(id -u)}"
install -d -m 0755 "$TUJUAN"
install -d -m 0750 "$AKAR/storage/ringkasan"
chmod 0750 "$AKAR/storage/ringkasan"
sed "s|@AKAR@|$AKAR|g" "$AKAR/conf/$UNIT" > "$TUJUAN/$UNIT.baru"
if grep -q '@AKAR@' "$TUJUAN/$UNIT.baru"; then
  rm -f "$TUJUAN/$UNIT.baru"
  echo "penanda @AKAR@ masih tersisa setelah penggantian" >&2
  exit 1
fi
chmod 0644 "$TUJUAN/$UNIT.baru"
if cmp -s "$TUJUAN/$UNIT.baru" "$TUJUAN/$UNIT"; then
  rm -f "$TUJUAN/$UNIT.baru"
else
  mv "$TUJUAN/$UNIT.baru" "$TUJUAN/$UNIT"
  echo "unit dipasang: $TUJUAN/$UNIT"
fi
systemctl --user daemon-reload
systemctl --user enable --now "$UNIT"
systemctl --user is-active "$UNIT"
