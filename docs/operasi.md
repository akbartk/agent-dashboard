# Operasi agent-dashboard

Dashboard satu halaman: hirarki tim agent, status, tugas aktif + pemberi order, riwayat hari ini, dan (tampilan Kantor Agen)
misi per agen. Kontrak data: `docs/skema-ringkasan.md`; aturan misi: `docs/misi.md`; semua kunci config: `docs/config.md`;
rencana pasang di host ini: `docs/pasang-g7.md` (belum dijalankan). Dokumen ini diturunkan dari runbook tim sumber dan
disamarkan; angka bertanda "tim sumber" diukur di instalasi sumber dan **belum diukur** di host ini.

> Penulisan: `<AKAR>` = folder project (di host ini `/data/agent-dashboard`), `<user-app>` = user OS yang menjalankan generator
> dan memiliki folder project, `<uid-app>` = uid-nya (`AD_UID`), `<host-app>` = host tempat aplikasi jalan, `<ip-bind>` = nilai
> `AD_BIND`, `<koordinator>`, `<pemilik>`, `<pemberi-1>` = id dari `conf/tim.json`. Perintah `docker compose` ditulis dalam bentuk
> plugin v2; host yang hanya punya `docker-compose` v1 memakai `docker-compose` dengan argumen yang sama, kecuali opsi yang
> hanya ada di v2 (`--dry-run`, `--pull never`), yang dicatat di tempatnya.

## Komponen

| Komponen | Di mana | Jalan sebagai |
|---|---|---|
| Generator ringkasan (Python 3 stdlib) | `script/generator.py`, unit `conf/agent-dashboard-generator.service` (templat `@AKAR@`) | service systemd (jenis user atau sistem: lihat `docs/pasang-g7.md`), interval 3 dtk |
| Web (Go 1.25, biner statis di image `scratch`) | `apps/`, `docker/Dockerfile`, `docker-compose.yml` | container `agent-dashboard-web-1`, uid `<uid-app>`:gid dari `.env` |
| Ringkasan per penonton | `storage/ringkasan/<penonton>.json` (dir 0750, berkas 0640) | ditulis generator (atomik), dibaca web `:ro` |
| Registri nomor misi | `storage/misi/nomor.json` (dir 0750, berkas 0640, state satu arah; lihat bagian Kantor Agen) | ditulis generator (atomik), tidak di-mount ke web |
| Akun | `db/data/akun.json` (0600, hash bcrypt cost 12) | ditulis web / CLI akun |
| Config tim | `conf/tim.json` (identitas tim, daftar agen, sumber data, pola; `docs/config.md`) | dibaca generator tiap siklus dan web saat start |
| Peta nama project | `conf/proyek.json` (slug → nama tampil; slug tanpa entri tampil apa adanya) | dibaca generator tiap siklus |
| Daftar agen | koordinator + setiap `<sumber.profil>/<id>/profile.yaml` (tanpa hardcode; skema §3.0), atribut dari `agen` di `conf/tim.json` | dipindai generator tiap siklus |

Generator hanya MEMBACA: log aktivitas (`sumber.activity`), folder lock (`sumber.lock`), header brief di `sumber.brief`
(baris pertama s.d. baris Peminta, maks 10 baris), `sumber.proc`, daftar folder + `description` di `sumber.profil`, dan
`conf/tim.json`. Isi `text`/`detail`, argv, dan isi brief tidak pernah ditulis ke ringkasan maupun log.

Alamat: `http://<ip-bind>:<AD_PORT>/` (nilai dari `.env`). HTTP polos adalah keputusan sadar Pemilik tim sumber (Q1 (b), 16 Okt 2026;
ADR-003 butir 2), bukan debt. Risiko yang diterima: password dan cookie sesi lewat HTTP; lewat Tailscale terenkripsi, lewat LAN tidak
terenkripsi; cookie tanpa `Secure`. Login dan ganti password sebaiknya lewat alamat Tailscale bila ada. Bind kedua (alamat
Tailscale) adalah override compose, bukan bawaan (`docs/config.md`, bagian env).

## Pasang dari nol

Rencana langkah di host ini ada di `docs/pasang-g7.md` (belum dijalankan; tiap langkah butuh izin eksplisit Pemilik). Ringkasan
urutan generik:

```
ss -ltnH '( sport = :<AD_PORT> )'             # harus kosong
docker compose config -q && docker compose up -d --build
script/pasang-generator.sh                    # idempoten: ganti @AKAR@, salin unit, daemon-reload, enable --now
```

Service user systemd membutuhkan linger agar jalan tanpa sesi login (`loginctl enable-linger <user-app>`, butuh hak admin).

## Cek status

```
docker compose ps
curl -s -o /dev/null -w '%{http_code}\n' http://<ip-bind>:<AD_PORT>/login           # 200
systemctl --user is-active agent-dashboard-generator                              # active (unit user)
journalctl --user -u agent-dashboard-generator -n 20 --no-pager                   # hanya jumlah/durasi/galat
python3 -c 'import json;d=json.load(open("storage/ringkasan/<pemilik>.json"));print(d["dibuat_pada"],d["galat"])'
docker logs --tail 20 agent-dashboard-web-1                                       # login: waktu, akun, ip, hasil
```

`dibuat_pada` harus maju tiap ±3 dtk. Bila halaman menampilkan banner "Data basi", generator berhenti memperbarui: cek
`systemctl --user status agent-dashboard-generator`. Pemeriksaan tambahan sejak Kantor Agen (lewat SSH, `systemctl --user` butuh
`XDG_RUNTIME_DIR=/run/user/<uid-app>`):

```
XDG_RUNTIME_DIR=/run/user/<uid-app> systemctl --user show -p ActiveState -p MainPID -p NRestarts -p MemoryPeak agent-dashboard-generator
#   harap: ActiveState=active, NRestarts=0, MemoryPeak jauh di bawah MemoryMax 64M (67108864); acuan tim sumber: 18112512 dan 18747392 byte
cat /sys/fs/cgroup$(XDG_RUNTIME_DIR=/run/user/<uid-app> systemctl --user show -p ControlGroup --value agent-dashboard-generator)/memory.events   # harap: oom_kill 0
python3 -c 'import json;d=json.load(open("storage/ringkasan/<pemilik>.json"));print("misi" in d, d["galat"])'   # harap: True []
stat -c '%a %U %n' storage/misi storage/misi/nomor.json      # harap: 750 <user-app> storage/misi ; 640 <user-app> storage/misi/nomor.json
docker inspect -f '{{.Image}}' agent-dashboard-web-1         # catat sebagai acuan rollback
```

## Akun (dibuat Pemilik di host; TL tidak membuat akun)

Nama akun yang sah = isi `penonton` di `conf/tim.json` (penonton ditentukan dari akun sesi, bukan dari URL; akun lain ditolak).

```
script/akun.sh tambah <pemilik>      # password awal dicetak SEKALI di terminal ini; wajib diganti saat login pertama
script/akun.sh reset <pemberi-1>     # password acak baru + wajib ganti lagi
script/akun.sh daftar                # nama, wajib_ganti, waktu ubah (tanpa hash)
```

Password baru: ≥ 12 karakter, ≤ 72 byte, beda dari password awal. Setelah 5 kali gagal login, percobaan berikutnya ditahan
1, 2, 4, … maks 300 dtk per (akun, IP). Sesi berakhir setelah 12 jam tidak aktif atau 7 hari sejak login; sesi disimpan di
memori, sehingga restart container = semua orang login ulang.

Reset (`script/akun.sh reset`) maupun ganti password lewat web **tidak** mencabut sesi akun itu yang sudah login: sesi lama tetap
sah sampai `docker compose restart web` (semua orang login ulang). `akun.sh reset` mencetak pengingat ini ke stderr. Bila
password dicurigai bocor: reset, lalu `docker compose restart web` (debt sesi, lihat bagian debt).

## Menambah / menghapus agen

Daftar agen tidak di-hardcode di `script/generator.py`. Agen baru = buat profil Hermes (folder `<sumber.profil>/<id>/` berisi
`profile.yaml`); dashboard menampilkannya pada siklus berikutnya (≤ 3 dtk), tanpa restart. Entri di kunci `agen` pada
`conf/tim.json` **opsional**: tanpa entri, agen tampil di bawah koordinator dengan nama = id berhuruf awal kapital dan peran =
`description` profil, dan field `peringatan` di ringkasan memuat `Profil <id> belum ada di conf/tim.json`. Untuk
nama/peran/induk yang rapi, tambahkan entri:

```
"<id>": {"nama": "<Nama>", "peran": "<peran singkat>", "induk": ["<koordinator>"], "ruang": "teknik"}
```

`induk` berisi `<cto>` = agen itu dihitung TL (lock `tl=<id>` sah, panggilan CTO tercatat `memanggil TL <Nama>`). Menghapus profil = agen
hilang pada siklus berikutnya; entrinya di `conf/tim.json` boleh tetap (diabaikan). `conf/tim.json` yang rusak (bukan JSON /
tipe salah / kunci wajib hilang) ditolak seluruhnya: galat terlihat dan generator memakai config sah terakhir sampai diperbaiki;
web gagal start. Cek: `python3 -m json.tool conf/tim.json >/dev/null && echo ok`.

## Restart

```
docker compose restart web                              # web (sesi hilang)
systemctl --user restart agent-dashboard-generator      # generator (riwayat dibangun ulang dari log hari ini)
```

Setelah ubah kode Go/aset: `docker compose up -d --build`. Setelah ubah `script/generator.py` atau `conf/tim.json` bagian yang
dibaca generator: restart generator. Setelah ubah unit di `conf/`: `script/pasang-generator.sh` lalu restart generator.
Restart generator menjalankan kode di disk dan siklus awal membaca ulang log dari awal. Terukur tim sumber (24 Okt 2026, journal
generator): siklus awal `siklus=13 baris_baru=35108 … rata_ms=2701.5`, berikutnya `siklus=21 baris_baru=6 … rata_ms=646.5`; ringkasan
pertama terbit 29 dtk sesudah start, dekat batas banner "Data basi" 30 dtk (`apps/web/app.js` baris 9), jadi banner bisa tampil
sesaat (dugaan, perlu diverifikasi di host ini).

## Tampilan (tema terang/gelap)

Penentu tema `apps/web/tema.js` disajikan di `/aset/tema.js` dan dimuat sinkron (tanpa `defer`) di `<head>` ketiga halaman
(`index.html`, `login.html`, `ganti.html`) supaya halaman tidak sempat berkedip; CSP `script-src 'self'` tidak diubah (skrip
inline tetap dilarang). Tema awal mengikuti `prefers-color-scheme`; tombol "Tema gelap"/"Tema terang" di halaman utama
menyimpan pilihan di `localStorage` (kunci `tema`). Semua warna ada di dua blok variabel `apps/web/app.css` (`:root` dan
`:root[data-tema="gelap"]`).

Routing aset (`apps/server.go` fungsi `aset()`): hanya `/aset/app.css`, `/aset/app.js`, `/aset/tema.js`, dan
`/aset/font/<berkas>`. Aset baru lain di root `/aset/` = 404 tanpa mengubah Go (dan kasus di `apps/aset_test.go`).

## Kantor Agen: keadaan acuan, rollback, peringatan

### Keadaan acuan (tim sumber)

Tampilan Kantor Agen dideploy tim sumber pada 24 Okt 2026 15.33–15.39 WIB atas izin Pemilik tim sumber. Terukur sesudah deploy di
sana (15.58): web memakai image yang dibangun dari `apps/` saat itu, generator `script/generator.py` versi Kantor Agen
(MainPID baru sejak 15:34:00, NRestarts 0), registri nomor misi dibuat siklus pertama 15.34. Image, hash, dan ID container tim
sumber tidak berlaku untuk host ini. <!-- tinjau: tabel keadaan terpasang tim sumber (digest image, Id container, MainPID, tag image cadangan, sha256 generator) tidak disalin karena nilainya spesifik instalasi sumber; di host ini diisi saat pasang (docs/pasang-g7.md) -->

### Rollback web ke image sebelumnya (butuh izin Pemilik)

Usulan praktik (menurut saya): sebelum setiap `docker compose up -d --build` yang mengganti image, beri tag cadangan image yang sedang
jalan, mis. `docker tag "${AD_IMAGE}:${AD_TAG}" "${AD_IMAGE}:pra-<tanggal>"`. Rollback hanya mengganti container web:

```bash
cd <AKAR> || exit 1
docker tag <AD_IMAGE>:pra-<tanggal> <AD_IMAGE>:<AD_TAG>
docker compose --dry-run up -d --no-deps --no-build --pull never --force-recreate web 2>&1 | grep -E 'Container|Network|Volume'   # v2: hanya web
docker compose up -d --no-deps --no-build --pull never --force-recreate web
for i in $(seq 1 30); do [ "$(curl -s -o /dev/null -w '%{http_code}' --max-time 2 http://<ip-bind>:<AD_PORT>/login)" = 200 ] && break; sleep 1; done
docker inspect -f '{{.Image}} {{.State.Status}}' agent-dashboard-web-1                 # harap: digest image cadangan, running
```

Di docker-compose v1 hilangkan `--dry-run` dan `--pull never` (belum diuji di host ini).

- Generator tidak perlu ikut dikembalikan bila hanya tampilan yang diganti: tim sumber menggladi UI lama + generator Kantor Agen
  (32 kasus lulus, 0 gagal) dan UI baru + generator skema lama (UI tidak rusak, tetapi misi kosong dan ringkasan "—").
- `storage/misi/nomor.json` dibiarkan (state satu arah; UI lama tidak membacanya).
- Sesudah rollback image, kode sumber `apps/web` di disk tetap versi terbaru (build berikutnya membawanya lagi). Mengembalikan
  sumber = keputusan terpisah: simpan arsip `apps/web` dan `apps/aset_test.go` sebelum perubahan dan ekstrak kembali.

### PERINGATAN: generator lama (membaca seluruh log ke memori) tidak bisa dipakai lagi

Generator versi lama yang membaca seluruh sisa log ke memori terukur berakhir `oom-kill` pada batas `MemoryMax=64M` yang sama dengan
unit (tim sumber, 24 Okt 2026 12.35–12.36, unit transient `systemd-run --user` saat swap host 4084/4095 MB: versi lama dan versi
Kantor Agen sesi 1 sama-sama `Failed with result 'oom-kill'`, status 143, Memory peak 64M). Versi sekarang membaca log baris demi
baris (penjaga `tests/generator/test_memori_backfill.py`); terukur tim sumber pada batas unit live: siklus pertama `success`,
Memory peak 17,2M, swap 0B, ±28 dtk. Unit memuat `Restart=always`, `RestartSec=5`, dan `MemoryMax=64M`, jadi generator lama yang
dipasang lagi diperkirakan masuk restart-loop oom-kill (deduksi dari uji transient; tidak diamati di live).

Bila generator versi sekarang harus dicabut, opsinya **belum dipilih** (keputusan CTO/Pemilik):

| Opsi | Tindakan | Risiko |
|---|---|---|
| a | `systemctl --user stop agent-dashboard-generator` (sementara; lewat SSH awali `XDG_RUNTIME_DIR=/run/user/<uid-app>`) | dashboard berhenti diperbarui: banner "Data basi"; tidak ada data baru sampai start lagi |
| b | kembali ke versi antara yang hanya memuat perbaikan memori | lolos 64M di uji tim sumber (17,9M), tetapi masih skema baru dan tanpa perbaikan lanjutan; belum diuji di live; perlu restart lagi |
| c | generator lama + naikkan `MemoryMax` di unit | mengubah berkas unit (izin); swap host penuh → tekanan memori host; batas aman tidak terukur |
| d | generator lama + backport baca-log per baris | pekerjaan kode + siklus uji baru; butuh waktu |

### Registri nomor misi `storage/misi/nomor.json` (state satu arah)

- Dibuat generator pada siklus pertama; direktori 0750, berkas 0640, pemilik `<user-app>`. Ditulis atomik hanya bila ada nomor baru
  (`nomor.json.tmp` 0640 → `os.replace`).
- Nomor misi `T-nnn` stabil dan global: nomor yang sudah ada tidak diubah atau dipakai ulang, entri tidak pernah dihapus walau
  berkas brief hilang (`docs/misi.md` §3).
- Menghapus atau mengganti registri = penomoran ulang dari backfill (urutan bisa berbeda). Registri **jangan dihapus** saat rollback
  web maupun generator; pengecualian hanya "Rollback lengkap" (seluruh dashboard dibongkar).
- Bila log aktivitas dibuat tanpa `text` (bawaan hook G7, `docs/config.md` bagian `aktivitas`), tidak ada misi yang tercocokkan dan
  registri tetap kosong.

## Rollback lengkap (kembali ke keadaan sebelum pemasangan)

```
cd <AKAR>
docker compose down
systemctl --user disable --now agent-dashboard-generator
rm -f ~/.config/systemd/user/agent-dashboard-generator.service
systemctl --user daemon-reload
# hanya bila linger diaktifkan oleh pemasangan ini dan atas keputusan Pemilik:
# loginctl disable-linger <user-app>
docker image rm <AD_IMAGE>:<AD_TAG>                      # opsional; tag cadangan (pra-<tanggal>) hanya atas keputusan Pemilik
```

Berkas pemasangan (`apps/ conf/ docker/ docker-compose.yml script/ tests/ docs/ storage/ringkasan/`) bisa dihapus bila pemasangan
dibatalkan seluruhnya; `db/data/akun.json` hanya berisi akun yang dibuat Pemilik. `storage/misi/` (registri nomor misi) boleh
dihapus HANYA bila pemasangan dibatalkan seluruhnya (menghapusnya = penomoran ulang `T-nnn`). Jika unit dipasang sebagai unit
sistem (bukan user), sesuaikan perintah di atas (`systemctl` tanpa `--user`, path unit sistem); jenis unit belum diputuskan
(`docs/pasang-g7.md`).

## Pengerasan generator dan debt yang disengaja

Di instalasi sumber, user manager systemd berjalan dengan `kernel.apparmor_restrict_unprivileged_userns=1`. Terukur tim sumber
16 Okt 2026 (unit uji sekali pakai `systemd-run --user`, probe baca-saja), systemd 259:

| Direktif | Efektif? | Dipakai |
|---|---|---|
| NoNewPrivileges, RestrictNamespaces, RestrictAddressFamilies=none, SystemCallFilter=@system-service, SystemCallArchitectures=native, MemoryDenyWriteExecute, LockPersonality, MemoryMax, CPUQuota, TasksMax, UMask | ya | ya |
| ProtectSystem=strict (± ReadWritePaths), ProtectHome, PrivateTmp, ProtectControlGroups, PrivateUsers, PrivateNetwork, IPAddressDeny | tidak (diabaikan diam-diam) | tidak |
| ProtectKernelTunables | hanya efek samping NNP+seccomp; /proc/sys tetap rw | tidak |
| PrivateDevices | unit gagal start (218/CAPABILITIES) | tidak |

Efektivitas direktif ini **belum diukur di host ini** <!-- tinjau: tabel di atas adalah hasil ukur host tim sumber; ulangi probe bila unit dipasang di host lain atau sebagai unit sistem -->.

`RestrictAddressFamilies=none` (semula `AF_UNIX`): bila `<user-app>` anggota grup `docker`, dengan `AF_UNIX` unit masih bisa connect ke
`/var/run/docker.sock` (= kendali penuh Docker). Terukur tim sumber dengan probe soket: unit lama → connect berhasil; `none` →
`socket()` EAFNOSUPPORT; log stdout ke journal tetap jalan. Catatan: `systemd-run -p RestrictAddressFamilies=none` ditolak systemd
259 ("Invalid argument"); di jalur transient padanannya `-p RestrictAddressFamilies=` (allow-list kosong).

Risiko yang diterima (keputusan Pemilik tim sumber Q2 (b), 16 Okt 2026: generator tetap unit user, tidak dipindah ke unit sistem):
generator bisa menulis di mana pun `<user-app>` bisa menulis (tidak ada isolasi filesystem). Mitigasi yang berlaku: kode hanya
menulis `storage/ringkasan/*.json(.tmp)` (dan `storage/misi/nomor.json`); tanpa soket sama sekali (`RestrictAddressFamilies=none`);
`NoNewPrivileges=yes` (menutup sudo); seccomp `SystemCallFilter=@system-service`. Ditinjau ulang menurut pemicu ADR-003. HTTP polos:
keputusan sadar (lihat Alamat), bukan debt.

Debt sesi (keputusan CTO 6.2 b, 16 Okt 2026): ganti/reset password tidak mencabut sesi akun itu yang sudah ada (sesi di memori,
`apps/sesi.go`, tidak memeriksa `diubah_pada` di `akun.json`). Perbaikan (6.2 a): cabut sesi bila `diubah_pada` berubah. Pemilik debt:
TL web. Dibayar: pada perubahan kode web berikutnya. Mitigasi sementara: `docker compose restart web`.

## Uji

```
python3 -m unittest discover -s tests/generator -v                          # generator + kontrak (fixture tests/fixtures)
python3 -m unittest discover -s tests/hooks -v                              # hook aktivitas (tidak dipasang)
docker run --rm -e GOTOOLCHAIN=local -v "$PWD/apps:/src:ro" -w /src golang:1.25-alpine go test -count=1 ./...
```

Uji UI otomatis tim sumber (peramban headless di container terpisah, dijalankan terhadap container uji lewat alamat non-loopback,
memakai akun uji yang dihapus sesudahnya) dan skrip probe pengerasan unit tidak disalin; uji statis tampilan:

```
python3 tests/ui/cek_statis_v3.py --web apps/web --tema-src /aset/tema.js --kontras <skrip-kontras>
#   stdlib, tanpa peramban; tidak menulis apa pun kecuali --keluaran; keluar 0 = semua lulus
```

Fixture tes generator memakai data tim sumber sebagai DATA uji (bukan `conf/`).
