#!/bin/bash
# Pasang agent-dashboard di host ini (docs/pasang-g7.md Langkah A sisa, C, E). Jalankan sebagai user pemilik project:
#   script/pasang.sh cek|pasang|rollback
# Semua nilai per pemasangan dibaca dari .env (dibuat manual dari .env.example, mode 600): AD_BIND, AD_PORT, dan
# opsional AD_BIND2 (alamat kedua, mis. Tailscale; dirender ke docker-compose.override.yml yang tidak di-commit).
# Akun web (Langkah D) tidak di sini: dibuat Pemilik dengan script/akun.sh (password awal tercetak sekali).
set -euo pipefail
AKAR=$(dirname "$(dirname "$(readlink -f "$0")")")
UNIT=agent-dashboard-generator.service
cd "$AKAR"

nilai() { sed -n "s/^$1=//p" .env | tail -1; }  # baca satu kunci .env tanpa mencetak isi berkas

uji() {  # uji pasca-pasang (docs/pasang-g7.md bagian 4 dan 9); keluar 1 bila ada yang gagal
  local gagal=0 bind port ip c
  ok() { echo "LULUS  $1"; }
  no() { echo "GAGAL  $1"; gagal=1; }
  if [ "$(stat -c %a .env 2>/dev/null)" = 600 ]; then ok ".env 600"; else no ".env 600"; fi
  if git check-ignore -q .env && git check-ignore -q docker-compose.override.yml && git check-ignore -q conf/tim.json
  then ok ".env, override, tim.json diabaikan git"; else no ".env, override, tim.json diabaikan git"; fi
  if docker-compose --env-file .env config --format json 2>/dev/null | python3 -c '
import json, sys
c = json.load(sys.stdin)
v = [m.get("source", "") for s in c["services"].values() for m in s.get("volumes", [])]
sys.exit(1 if c.get("volumes") or any(m.get("type") != "bind" for s in c["services"].values() for m in s.get("volumes", []))
         or not all(x.startswith(sys.argv[1] + "/") for x in v) else 0)' "$AKAR"
  then ok "volume bind di dalam project, tanpa named volume"; else no "volume bind di dalam project"; fi
  bind=$(nilai AD_BIND 2>/dev/null || true); port=$(nilai AD_PORT 2>/dev/null || true)
  if docker-compose --env-file .env config -q 2>/dev/null; then ok "compose sah"; else no "compose sah"; fi
  if [ -n "$(nilai AD_BIND2 2>/dev/null || true)" ]; then
    if [ -f docker-compose.override.yml ]; then ok "override bind kedua ada"; else no "override bind kedua ada"; fi
  fi
  if [ "$(docker-compose ps -q web 2>/dev/null | xargs -r docker inspect -f '{{.State.Running}}' 2>/dev/null)" = true ]
  then ok "container web jalan"; else no "container web jalan"; fi
  for ip in $bind $(nilai AD_BIND2 2>/dev/null || true); do
    c=$(curl -s -o /dev/null -m 5 -w '%{http_code}' "http://$ip:$port/login" || true)
    if [ "$c" = 200 ]; then ok "http://$ip:$port/login = 200"; else no "http://$ip:$port/login = $c"; fi
  done
  if [ "$(loginctl show-user "$(id -un)" -p Linger --value 2>/dev/null)" = yes ]; then ok "linger"; else no "linger"; fi
  if systemctl --user is-active -q "$UNIT" 2>/dev/null; then ok "generator aktif"; else no "generator aktif"; fi
  if python3 - 2>/dev/null <<'PY'
import json, re, sys
t = json.load(open("conf/tim.json", encoding="utf-8"))
s = open(f"storage/ringkasan/{t['pemilik']}.json", encoding="utf-8").read()
json.loads(s)
d = json.loads(s)
sys.exit(1 if ("@" in s or re.search(r"\d{10,}", s) or d.get("galat")) else 0)
PY
  then ok "ringkasan pemilik sah, galat kosong, tanpa @/10 digit"; else no "ringkasan pemilik"; fi
  if [ "$(stat -c %a storage/ringkasan 2>/dev/null)" = 750 ]; then ok "storage/ringkasan 750"; else no "storage/ringkasan 750"; fi
  if [ "$(ls -A tmp/test)" = .gitkeep ]; then ok "tmp/test bersih"; else no "tmp/test bersih"; fi
  return $gagal
}

case "${1:-cek}" in
  cek) uji ;;
  pasang)
    test -f .env || { echo ".env belum ada: salin dari .env.example (chmod 600) lalu isi" >&2; exit 1; }
    chmod 600 .env
    python3 -m json.tool conf/tim.json >/dev/null
    b2=$(nilai AD_BIND2)
    if [ -n "$b2" ]; then  # bind kedua = override per pemasangan (di .gitignore)
      printf '%s\n' "# Dibuat script/pasang.sh dari AD_BIND2 di .env. Per pemasangan, tidak di-commit." \
        "services:" "  web:" "    ports:" "      - \"\${AD_BIND2}:\${AD_PORT}:8080\"" > docker-compose.override.yml
    else
      rm -f docker-compose.override.yml
    fi
    docker-compose --env-file .env config -q
    trap 'rm -rf "$AKAR/tmp/test/pasang"' EXIT
    docker-compose up -d --build
    rm -rf tmp/test/pasang
    python3 script/generator.py --sekali --keluaran tmp/test/pasang/ringkasan --nomor tmp/test/pasang/nomor.json
    rm -rf tmp/test/pasang
    [ "$(loginctl show-user "$(id -un)" -p Linger --value)" = yes ] || sudo -n loginctl enable-linger "$(id -un)"
    script/pasang-generator.sh
    sleep 8
    uji
    ;;
  rollback)  # urutan dibalik: generator -> container -> override. .env, db/data, storage/misi tidak disentuh.
    systemctl --user disable --now "$UNIT" 2>/dev/null || true
    rm -f "$HOME/.config/systemd/user/$UNIT"
    systemctl --user daemon-reload
    docker-compose down
    rm -f docker-compose.override.yml
    if ! sisa=$(docker-compose ps -q) || [ -n "$sisa" ] || systemctl --user is-active -q "$UNIT" 2>/dev/null; then
      echo "rollback BELUM bersih: container atau generator masih jalan" >&2; exit 1
    fi
    echo "rollback selesai (.env dan linger dibiarkan; linger: sudo loginctl disable-linger $(id -un))"
    ;;
  *) echo "pemakaian: script/pasang.sh cek|pasang|rollback" >&2; exit 2 ;;
esac
