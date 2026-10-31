# Pasang agent-dashboard di g7 — SUDAH DIPASANG (31 Okt 2026)

> **Status (31 Okt 2026): sudah terpasang dan berjalan di g7.** Container web berjalan, generator berjalan sebagai unit user,
> dan hook aktivitas terpasang di semua profil Hermes (laporan implementer; dokumen ini tidak menjalankan ulang uji).
> Rincian per langkah di bawah. Hasil uji pasca-pasang tidak dicatat ulang di sini; bentuk otomatisnya adalah
> `script/pasang.sh cek` (`docs/operasi.md`). Konfigurasi live (`conf/tim.json`, `.env`) tidak ada di repo dan tidak diubah
> oleh dokumen ini.
>
> Bagian di bawah dipertahankan sebagai catatan rencana dan keputusan. Setiap langkah bertanda **[butuh izin eksplisit Pak Akbar]**: izin diminta per pekerjaan dengan cakupan
> persis, tidak berlaku untuk langkah berikutnya. Langkah bertanda **[QC G7-QC]** tergolong Tier A dan memerlukan verdict LULUS
> G7-QC yang cocok sebelum dieksekusi. `git push` hanya atas perintah eksplisit Pak Akbar (di luar rencana ini).

Dokumen terkait: nilai config `docs/config.md` (bagian "Nilai pemasangan g7"), operasi harian `docs/operasi.md`, kontrak data
`docs/skema-ringkasan.md`. Hal yang belum diverifikasi ditandai "belum diverifikasi"; keputusan yang bukan milik penyusun ada di
bagian 5 dan 6.

> Penulisan: `<AKAR>` = `/data/agent-dashboard` di host g7. `<user-app>` = user host g7 pemilik `<AKAR>`.

## 1. Prasyarat (semua cek baca-saja; tidak mengubah apa pun)

| # | Cek | Perintah / sumber | Harapan |
|---|---|---|---|
| 1 | Folder project ada, isi sesuai kontrak | `ls <AKAR>` ; `ls <AKAR>/conf <AKAR>/script <AKAR>/hooks` | ada `conf/tim.example.json`, `script/generator.py`, `script/pasang-generator.sh`, `docker-compose.yml`, `.env.example`, `hooks/team-activity.py` (dibuat TL lain; belum diverifikasi pada saat dokumen ini ditulis) |
| 2 | `.env` belum ada | `test ! -e <AKAR>/.env && echo belum-ada` | `belum-ada` (kontrak: `.env` tidak dibuat sebelum pasang) |
| 3 | uid/gid pemilik folder | `stat -c '%u %g' <AKAR>` | dipakai untuk `AD_UID`/`AD_GID`; terukur di g7 per 25 Okt 2026: uid/gid `1000`/`1000` (user `akbar`). Cek ulang saat pasang |
| 4 | Versi Python host | `python3 --version` | 3.13.x (kontrak: 3.13.2 = interpreter generator di systemd) |
| 5 | Docker Compose | `docker-compose version` | terukur di g7 per 25 Okt 2026: `docker-compose version --short` = `2.33.1` (binary standalone `docker-compose`); plugin `docker compose` tidak ada (`docker compose version` → `docker: unknown command: docker compose`). Semua perintah compose di bawah memakai `docker-compose` |
| 6 | Port bebas | `ss -ltnH '( sport = :24130 )'` | kosong; belum diverifikasi di g7 |
| 7 | Akses tulis ke `<AKAR>` | `test -w <AKAR> && echo bisa` | `bisa` untuk user yang menjalankan langkah |
| 8 | Jalur data sumber terbaca | `test -r` pada tiap path `sumber.*` di `docs/config.md` bagian 6.2 | semua terbaca oleh user generator; hak baca atas state Hermes **belum diverifikasi** (di tim sumber pemilik path sama dengan user generator; di g7 belum tentu) |

Catatan gerbang: gerbang teks pada perintah `ssh g7 '…'` memblok `docker … rm|build|pull|exec|up|down|…` dan teks
`/data/hermes-agent`. Langkah docker di bawah karena itu dijalankan lewat sesi yang diizinkan dan di-QC, tidak diakali dengan
memecah perintah.

## 2. Langkah pasang (urutan)

Urutan: A `.env` → B `tim.json` → C build + compose → D akun web → E generator → F (opsional, terpisah) hook aktivitas.
Langkah C dan E juga dibungkus `script/pasang.sh` (`cek`, `pasang`, `rollback`; sejak 31 Okt 2026). Langkah D tetap lewat `script/akun.sh`.
Status per langkah di g7 (31 Okt 2026, laporan implementer): C dan E berjalan (container web dan generator aktif), F terpasang;
A dan B tersirat oleh container yang berjalan tetapi tidak dicatat eksplisit di dokumen ini; D tidak dicatat di dokumen ini.

### Langkah A — isi `.env` dari `.env.example` **[butuh izin eksplisit Pak Akbar]**

```
cd <AKAR>
cp .env.example .env && chmod 600 .env
# edit .env: AD_UID dan AD_GID = hasil `stat -c '%u %g' <AKAR>` ; AD_BIND dan AD_PORT lihat bagian 3
stat -c '%a %U' .env                       # harap: 600
grep -c '^\.env$' .gitignore               # harap: 1
```

Verifikasi tanpa mencetak isi `.env`: `docker-compose --env-file .env config -q` (tanpa `-q` compose mencetak isi `.env`). Isi `.env`
tidak boleh dicetak ke log atau laporan.
Rollback: `rm <AKAR>/.env`.

### Langkah B — `conf/tim.json` dari `conf/tim.example.json` **[butuh izin eksplisit Pak Akbar]**

Keadaan g7 (terukur 25 Okt 2026): `conf/tim.json` **sudah ada di `<AKAR>`** (mtime 25 Okt 05:48) dan terdaftar di `.gitignore`
(tidak masuk git). Langkah `cp` di bawah hanya untuk salinan baru yang belum punya `conf/tim.json` (mis. hasil clone);
di `<AKAR>` g7 yang sekarang lewati `cp` dan cukup periksa isinya dengan `json.tool` serta cek tambahan di bawah.

```
cd <AKAR>
cp conf/tim.example.json conf/tim.json     # hanya bila conf/tim.json belum ada; JANGAN menimpa yang sudah ada
# isi dengan nilai g7 (docs/config.md bagian 6): orang, penonton, pemilik, koordinator, cto, agen, sumber.*, pola.*,
#   kategori_perintah, tool.*, aktivitas (empat kunci, nilai bawaan = tanpa isi)
python3 -m json.tool conf/tim.json >/dev/null && echo json-sah
```

Cek tambahan: `pemilik` termasuk `penonton`; `cto` dan `koordinator` ada di `agen`; `aktivitas.catat_teks` dan `catat_detail` tetap
`false` kecuali Pemilik memutuskan lain (bagian 5, Q4). `conf/tim.json` di-`.gitignore`.
Rollback: `rm <AKAR>/conf/tim.json`.

### Langkah C — build image dan jalankan compose **[butuh izin eksplisit Pak Akbar]** **[QC G7-QC]**

```
cd <AKAR>
docker-compose --env-file .env config -q && echo compose-sah
docker-compose up -d --build              # satu service web; port ${AD_BIND}:${AD_PORT} -> 8080
docker-compose ps
```

Syarat: Langkah A dan B selesai; port bebas (prasyarat 6); bind sesuai bagian 3. Web gagal start bila `conf/tim.json` tidak sah
(gagal tertutup): itu perilaku yang diharapkan, bukan galat pasang. Image uji/cadangan yang tidak dipakai dihapus sesudahnya.
Rollback: `docker-compose down` ; opsional `docker image rm <AD_IMAGE>:<AD_TAG>`. Data akun di `db/data` tidak ikut terhapus.

### Langkah D — akun web **[butuh izin eksplisit Pak Akbar]**

Akun dibuat oleh Pemilik (atau yang Pemilik tunjuk), bukan oleh TL:

```
cd <AKAR>
script/akun.sh tambah <pemilik>           # password awal dicetak SEKALI di terminal; wajib diganti saat login pertama
script/akun.sh daftar                     # nama, wajib_ganti, waktu ubah (tanpa hash)
```

Akun yang sah hanya id di `penonton`. `script/akun.sh` memilih `docker compose` bila plugin ada, selain itu `docker-compose`
(dibaca di g7, 25 Okt 2026: baris pemilihan `DC=` di berkas itu); karena plugin tidak ada di g7, yang dipakai `docker-compose`.
Status akun di g7 tidak dicatat di dokumen ini. Rollback: hapus `db/data/akun.json` (atas keputusan Pemilik) lalu `docker-compose restart web`.

### Langkah E — unit systemd generator lewat `script/pasang-generator.sh` **[butuh izin eksplisit Pak Akbar]**

```
cd <AKAR>
# 1. uji sekali ke tmp/test, tanpa menyentuh storage live:
python3 script/generator.py --sekali --keluaran tmp/test/pasang/ringkasan --nomor tmp/test/pasang/nomor.json
# 2. pasang unit (idempoten): mengganti penanda @AKAR@, menyalin unit, daemon-reload, enable --now
script/pasang-generator.sh
```

`ExecStart` dan `Documentation` pada unit memakai penanda `@AKAR@` yang diganti saat pasang; skrip tanpa cek user literal.
**Keputusan terbuka (bagian 6, T1):** apakah unit dipasang sebagai unit user (perlu linger untuk jalan tanpa sesi login, butuh hak
admin) atau unit sistem. Kontrak tidak menetapkannya; isi `script/pasang-generator.sh` hasil TL infrastruktur menentukan, dan
efektivitas direktif pengerasan di host g7 belum diukur (`docs/operasi.md`, bagian Pengerasan).
Bukti memori di tim sumber: siklus pertama pada batas `MemoryMax=64M` terukur 17,2M peak; ukur ulang di g7 (`systemctl show -p MemoryPeak`).
Rollback: `systemctl disable --now agent-dashboard-generator` (dengan `--user` bila unit user), hapus berkas unit, `daemon-reload`.

### Langkah F — hook aktivitas (opsional, terpisah dari A–E) **[butuh izin eksplisit Pak Akbar]** **[QC G7-QC]**

Hook (`hooks/team-activity.py`) **tidak dipasang** oleh pekerjaan penulisan kode; memasangnya mengubah konfigurasi profil Hermes
(state agent), jadi Tier A dan butuh verdict LULUS G7-QC yang cocok. Tanpa hook, dashboard tetap tampil tetapi log aktivitas
tidak terisi (`sumber.activity` bernilai "belum tersedia: hook belum dipasang").
**Status 31 Okt 2026:** hook terpasang di semua profil Hermes (laporan implementer). Pembaruan isi hook memakai mode `perbarui`
tanpa mengubah config dan tanpa restart (`docs/operasi.md`, bagian Hook aktivitas). Sumber: `script/pasang-hook.py`.

| Aspek | Isi |
|---|---|
| Sifat | hanya mencatat, tidak pernah memblok; error apa pun = keluar 0 tanpa output (kontrak §6) |
| Event | baris `msg` ditulis dari event `pre_llm_call` (`docs/skema-ringkasan.md` §3.6). Event untuk baris `tool` dan `reply`: belum diverifikasi, baca `hooks/team-activity.py` saat pasang |
| Env | `TEAM_ACTIVITY_LOG` (path jsonl; tidak diset = tidak menulis apa pun), `AD_TIM` (path `tim.json`; untuk id koordinator dan nama pemilik) — `docs/config.md` bagian 4.2 |
| Profil | profil koordinator (`default`): pesan masuk non-subagent → `role: "owner"`, `name` = nama pemilik; profil lain: `role: "tim"`, `name` = `agen[id].nama`. Daftar profil yang dipasangi hook: keputusan terbuka (bagian 6, T2); usulan (menurut saya): `default` lebih dulu, lalu profil lain di `agen` secara bertahap |
| Isi baris | bawaan metadata saja; `text`/`detail` hanya bila Pemilik menyalakan (bagian 5, Q4) |
| Uji | `python3 -m unittest discover -s tests/hooks` (stdlib) di host, sebelum pasang; setelah pasang cek bahwa baris baru **tidak** memuat kunci `text`/`detail` |

Path: hook berjalan di container Hermes, sedangkan `conf/tim.json` ada di host `<AKAR>` (keputusan terbuka Q6, bagian 5).
Pemetaan mount memberi padanan container untuk log (`/data/hermes-agent/data/…` di host = `/opt/data/…` di container); itu turunan
dari pemetaan mount, belum diverifikasi.
Skrip: `script/pasang-hook.py` (dijalankan di container Hermes; cara pakai di docstring berkas itu). Simpan dulu dan cocokkan
sha256-nya dengan verdict QC, lalu jalankan dengan `HERMES_HOME=<akar data Hermes>` eksplisit (bukan folder profil).
Rollback dua tahap, JANGAN menyalin balik config dari cadangan (perubahan sah sesudah pasang ikut hilang dan approval penjaga
bisa lepas): (1) `pasang-hook.py rollback` mencabut entri yang merujuk berkas hook dari config + allowlist semua profil dan
gagal bila masih ada rujukan; (2) restart gateway dan tunggu sesi `hermes -p` yang masih jalan selesai; (3) `pasang-hook.py
bersihkan` menghapus salinan hook + tim.json. Berkas hook yang hilang selagi masih terdaftar = python rc 2 = Hermes memblok
semua `pre_tool_call`, jadi urutan ini wajib. Hapus `activity.jsonl` hanya atas keputusan Pemilik (isinya log).

## 3. Port dan bind

- Bawaan `.env.example`: `AD_BIND=127.0.0.1`, `AD_PORT=24130` → hanya terjangkau dari host g7 sendiri. Itu aman sebagai awal, tetapi
  perangkat lain tidak bisa membuka dashboard.
- Agar bisa dibuka dari LAN atau Tailscale, isi `AD_BIND` dengan alamat LAN atau alamat Tailscale host g7 (satu alamat; alamat ada di
  skill server, tidak ditulis di dokumen ini). Bind kedua = override compose (`docker-compose.override.yml`), dokumentasi di `docs/config.md`.
- Pilihan alamat dan penerimaan risiko HTTP polos (password dan cookie sesi tidak terenkripsi lewat LAN) = keputusan Pemilik
  (`docs/operasi.md`, bagian Alamat). Login dan ganti password sebaiknya lewat alamat Tailscale.
- Risiko boot bila bind ke alamat Tailscale: container bisa gagal start bila alamat itu belum terpasang saat boot (catatan tim sumber,
  dimitigasi di sana dengan drop-in systemd); belum diverifikasi di g7.
- Port 24130: cek bebas sebelum Langkah C (prasyarat 6).

## 4. Uji pasca-pasang (setelah langkah yang bersangkutan; bukti dikutip apa adanya)

| # | Uji | Perintah | Lulus bila |
|---|---|---|---|
| 1 | compose sah, volume relatif | `docker-compose --env-file .env config -q` ; periksa semua volume berbentuk `./…` | exit 0; tanpa named volume |
| 2 | web hidup | `docker-compose ps` ; `curl -s -o /dev/null -w '%{http_code}\n' http://<AD_BIND>:<AD_PORT>/login` | container Up; `200` |
| 3 | web gagal tertutup | salin `tim.json` rusak ke `tmp/test`, jalankan biner/web uji tanpa port publik | keluar ≠ 0 dengan pesan jelas (jalankan hanya dengan izin dan lewat QC) |
| 4 | generator hidup | `systemctl is-active agent-dashboard-generator` (dengan `--user` bila unit user) ; `journalctl … -n 20 --no-pager` | `active`; log hanya jumlah/durasi/galat |
| 5 | ringkasan sah | `python3 -c 'import json;d=json.load(open("storage/ringkasan/<pemilik>.json"));print(d["dibuat_pada"],d["galat"],d["pemilik"],d["koordinator"])'` | `dibuat_pada` maju tiap ±3 dtk; `galat` kosong; `pemilik`/`koordinator` sesuai config |
| 6 | tanpa data pribadi di ringkasan | periksa `<pemilik>.json` | JSON sah (`python3 -m json.tool`), tanpa `@` dan tanpa deret ≥ 10 digit |
| 7 | izin berkas | `stat -c '%a %U %n' storage/ringkasan storage/ringkasan/<pemilik>.json db/data/akun.json .env` | 750 / 640 / 600 / 600 |
| 8 | log metadata-saja | (setelah Langkah F) ambil satu baris baru dari `activity.jsonl` | tanpa kunci `text` dan `detail` |
| 9 | generator atas log metadata-saja | `python3 script/generator.py --sekali --keluaran tmp/test/pasca/ringkasan --nomor tmp/test/pasca/nomor.json` | selesai tanpa crash; tampilan aktivitas generik |
| 10 | proses terlihat | `ls /proc` dari sisi generator ; cocokkan dengan proses `hermes -p <id>` yang sedang jalan | belum diverifikasi apakah proses di dalam container terlihat dari host (kontrak §7 mengasumsikan terlihat lewat lock dan proses) |
| 11 | uji unit | `python3 -m unittest discover -s tests/generator` ; `python3 -m unittest discover -s tests/hooks` | OK, tanpa skip |
| 12 | standar aplikasi | `tmp/test` hanya `.gitkeep`; `.env` 600 dan di `.gitignore`; `.env.example` tanpa nilai rahasia; tidak ada berkas nyasar di root | semua ya |

Hasil uji yang memakai `tmp/test` dibersihkan sesudahnya; simpan hanya bukti yang perlu.

## 5. Keputusan terbuka saat pasang (milik Pak Akbar / Arsa)

> Status 31 Okt 2026 (laporan implementer, belum dicek ulang di repo): **Q4** — `catat_teks` dan `catat_detail` live = `true`
> (semula untuk judul card permintaan; judul kini samaran tanpa `text`); keputusan Pemilik tidak tercatat di repo. **Q5** dan **Q6** — belum ada catatan keputusan;
> Q6 dijalankan dengan salinan `tim.json` dan hook di container (lihat `docs/operasi.md`, bagian Hook aktivitas).

| ID | Pertanyaan | Opsi | Rekomendasi (menurut saya) |
|---|---|---|---|
| Q4 | Apakah log aktivitas boleh menyimpan `text` dan/atau `detail`? | (a) tetap tanpa isi (bawaan); (b) nyalakan `catat_teks` saja; (c) nyalakan keduanya | (a) sampai ada keputusan; konsekuensi (a): misi tidak tercocokkan dan langkah generik (`docs/config.md` bagian 3) |
| Q5 | Di profil koordinator, setiap `pre_llm_call` non-subagent dianggap pesan pemilik; sesi cron/CLI profil koordinator ikut tercatat sebagai pesan pemilik (tanpa isi, bawaan). Diterima? | (a) terima asumsi (penonton tunggal); (b) saring sesi cron/CLI (perlu perubahan hook) | (a) bila hanya menampilkan metadata; tinjau lagi jika `catat_teks` dinyalakan |
| Q6 | Hook di container Hermes, `conf/tim.json` di host: bagaimana path `AD_TIM` dan `TEAM_ACTIVITY_LOG` yang terlihat dari container ditentukan? | (a) salin `tim.json` ke lokasi yang terlihat container (dua salinan harus dijaga sama, cek hash); (b) mount tambahan ke container Hermes (mengubah deployment Hermes, di luar cakupan); (c) hook tanpa `tim.json` (tidak mungkin: tanpa config hook tidak menulis apa pun) | (a), dengan cek hash dua salinan di uji pasca-pasang |

## 6. Keputusan lain yang belum ada (ditemukan saat menulis rencana)

| ID | Hal | Catatan |
|---|---|---|
| T1 | Jenis unit systemd generator: unit user atau unit sistem | kontrak tidak menetapkan; tim sumber memakai unit user (keputusan Pemilik tim sumber); keputusan g7 belum ada. Status 31 Okt 2026: generator berjalan sebagai unit user (laporan implementer); keputusan formal belum dicatat |
| T2 | Profil mana yang dipasangi hook aktivitas | lihat Langkah F. Status 31 Okt 2026: semua profil Hermes (laporan implementer) |
| T3 | Alamat `AD_BIND` (loopback, LAN, atau Tailscale) | bagian 3 |

## 7. Belum didukung (celah yang diketahui; tidak dikerjakan di tahap ini, KONTRAK §7)

Status celah per 31 Okt 2026 (alur P1.5; rincian di `docs/misi.md` dan `docs/skema-ringkasan.md` §8):

1. ~~Generator tidak membaca handoff~~ **Ditangani:** `sumber.handoff` dibaca (status dari `jalan-*.json`, langkah dari `<kunci>.md`).
   `tool.catat_progres` tetap `null` (langkah lewat handoff).
2. ~~Peluncuran TL lewat `tim_jalankan.py` tidak cocok~~ **Ditangani untuk `tim_jalankan.py --tugas`** (memanggil TL/pengerja).
   Jalur `hermes -p <tl>` tetap seperti semula.
3. Lock dengan `selesai=`: **ditangani sebagian.** Misi tetap `menunggu` sampai lock dilepas, tetapi alasannya kini `review`
   (menunggu review), bukan `gantung`.
4. `docker build` dan container web: **sudah berjalan di g7** (laporan implementer 31 Okt 2026); hasil uji gerbang
   `hermes-container` tidak dicatat di dokumen ini.

## 8. Rollback keseluruhan

Urutan dibalik: F (hook; rollback dua tahap di Langkah F) → E (unit generator) → D (akun) → C (`docker-compose down`, image
opsional) → B (`conf/tim.json`) → A (`.env`). Folder `storage/ringkasan` boleh dihapus; `storage/misi/` (registri nomor misi) hanya
bila pemasangan dibatalkan seluruhnya (`docs/operasi.md`). Perintah rinci per langkah ada di tiap langkah di atas; semuanya juga butuh
izin eksplisit Pak Akbar.

## 9. Cek standar aplikasi sebelum menyatakan pasang selesai

- `docker-compose --env-file .env config -q` valid; semua volume `./…` (tidak ada named volume).
- `tmp/test` bersih (hanya `.gitkeep`).
- `.env` mode 600 dan tercantum di `.gitignore`; `.env.example` tanpa nilai rahasia.
- Tidak ada berkas nyasar di root; tidak ada path compose yang keluar dari `<AKAR>`.
