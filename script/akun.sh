#!/bin/bash
# Akun dashboard (dijalankan pemilik di host, dari folder mana pun):
#   script/akun.sh tambah <akun>   buat akun; password awal dicetak SEKALI ke terminal ini
#   script/akun.sh reset  <akun>   password acak baru + wajib ganti saat login berikutnya
#   script/akun.sh daftar          nama, wajib_ganti, waktu ubah (tanpa hash)
# <akun> harus salah satu id di `penonton` pada conf/tim.json (daftar akun sah dibaca web dari berkas itu).
# Password tidak pernah disimpan di berkas/log; hanya hash bcrypt di ./db/data/akun.json (0600). Butuh container web jalan.
set -euo pipefail
AKAR=$(dirname "$(dirname "$(readlink -f "$0")")")
case "${1:-}" in
  tambah|reset) [ $# -eq 2 ] || { echo "pakai: $0 tambah|reset <akun>" >&2; exit 2; } ;;
  daftar) [ $# -eq 1 ] || { echo "pakai: $0 daftar" >&2; exit 2; } ;;
  *) echo "pakai: $0 tambah|reset <akun> | daftar" >&2; exit 2 ;;
esac
# Plugin `docker compose` tidak ada di semua host; pakai `docker-compose` bila plugin tidak ada.
if docker compose version >/dev/null 2>&1; then DC=(docker compose); else DC=(docker-compose); fi
DC+=(--project-directory "$AKAR")
if [ "$1" = reset ]; then
  "${DC[@]}" exec -T web /agent-dashboard akun "$@"
  # Debt 6.2 (docs/operasi.md): reset tidak mencabut sesi yang sudah login.
  echo "PENGINGAT: sesi lama akun '$2' tetap sah sampai web di-restart. Untuk mencabutnya: restart service web lewat" \
       "compose di folder project (semua orang harus login ulang)." >&2
  exit 0
fi
exec "${DC[@]}" exec -T web /agent-dashboard akun "$@"
