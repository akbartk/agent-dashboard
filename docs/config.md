# Config agent-dashboard

Dokumen ini memuat semua kunci `conf/tim.json` (skema versi 1), semua variabel env (`AD_*`, `TEAM_ACTIVITY_LOG`), opsi CLI
generator, dan nilai pemasangan untuk host g7. Sumber: KONTRAK port ke g7 (25 Okt 2026, revisi 2) §2, §5, §6, §6a dan kode final
`script/generator.py`. Hal yang belum bisa diverifikasi ditandai "belum diverifikasi".

> Penulisan: `<pemilik>`, `<koordinator>`, `<cto>`, `<tl-1>`, `<host-app>`, `<AKAR>` adalah placeholder. Di bagian "Nilai
> pemasangan g7" semua nilai nyata untuk host ini.

## 1. Urutan prioritas

Berlaku untuk setiap nilai yang punya tiga sumber: **opsi CLI > variabel env > berkas config**.

| Yang dicari | CLI | Env | Berkas |
|---|---|---|---|
| Lokasi `tim.json` | `--tim` | `AD_TIM` | `<AKAR>/conf/tim.json` (generator); web: `AD_TIM`, bawaan `/srv/conf/tim.json` (path di dalam container) |
| Log aktivitas | `--activity` | – | `sumber.activity` |
| Workspace | `--workspace` | – | `sumber.workspace` |
| Folder profil | `--profil` | – | `sumber.profil` |
| `/proc` | `--proc` | – | `sumber.proc` |

Opsi CLI lain (`--keluaran`, `--nomor`, `--proyek`, `--interval`, `--sekali`, `--sekarang`) tidak punya padanan di config.
`--agen` sudah dihapus: daftar agen ada di kunci `agen`. Kunci yang namanya diawali `_` adalah komentar dan diabaikan pembaca.

Kegagalan: JSON tidak sah atau kunci wajib hilang = galat terlihat. Generator menulis galat di keluaran dan memakai config sah
terakhir; web **gagal start** (keluar ≠ 0 dengan pesan jelas, gagal tertutup); subperintah `akun` memakai aturan yang sama.

Generator, bila `tim.json` tidak sah dan **belum pernah ada config sah di proses itu** (mis. baru start dengan berkas rusak):
siklus gagal dengan `ConfigTimTidakSah` (stdout `siklus gagal: ConfigTimTidakSah`; hanya nama kelas yang dicetak). Siklus itu tidak
menulis berkas keluaran apa pun. `--sekali` keluar dengan kode 1; mode terus-menerus tidak berhenti dan mengulang siklus tiap `--interval`.
Bila sebelumnya pernah sah, galat tampil dan config sah terakhir tetap dipakai (KONTRAK revisi 2 butir b; `generator.py:437–446`).
## 2. Kunci `conf/tim.json`

Kolom "Wajib" sudah dicocokkan dengan `_validasi_tim` di `script/generator.py` (uji TL5, 25 Okt 2026; dicocokkan ulang saat
koreksi docs ini). Validasi tambahan dari kode ada di bawah tabel (bagian 2.1). Sisi web (Go) tidak dibaca dalam koreksi ini:
belum diverifikasi.

| Kunci | Tipe | Wajib | Contoh placeholder | Arti |
|---|---|---|---|---|
| `versi` | int | wajib, harus `1` | `1` | versi skema config |
| `orang` | list objek `{id, nama, peran, induk[]}` | wajib | `[{"id":"pemilik","nama":"<Nama Pemilik>","peran":"Pemilik tim","induk":[]}]` | manusia di organisasi; `id` dipakai sebagai nama akun web dan nama berkas ringkasan |
| `penonton` | list id orang | wajib | `["pemilik"]` | siapa dibuatkan `<id>.json` dan boleh punya akun web (akun sah web = isi `penonton`) |
| `pemilik` | id orang, wajib termasuk `penonton` | wajib | `"pemilik"` | penonton yang melihat semua (`cakupan: "semua"`); pemilik bawaan peristiwa/tugas tanpa pemberi |
| `koordinator` | id agen | wajib | `"koordinator"` | akar organisasi agen; selalu dianggap hadir tanpa folder profil |
| `cto` | id agen | wajib | `"cto"` | TL = agen yang `induk`-nya memuat `cto`, kecuali `cto` dan `koordinator` |
| `agen` | objek `id → {nama, peran, induk[], ruang}` | wajib | `{"tl-1":{"nama":"<TL 1>","peran":"Tech Lead","induk":["cto"],"ruang":"teknik"}}` | daftar agen (menggantikan berkas `conf/agen.json` yang dihapus); `ruang` ∈ `koordinasi`, `riset`, `qa`, `teknik` (opsional; tanpa `ruang` → `lain`) |
| `sumber.activity` | path host | wajib | `/<jalur-host>/activity.jsonl` | log aktivitas jsonl |
| `sumber.profil` | dir host | wajib | `/<jalur-host>/profiles` | folder profil Hermes: `<id>/profile.yaml`, `config.yaml`, `state.db` |
| `sumber.workspace` | dir host | wajib | `/<jalur-host>/workspace` | padanan host dari `sumber.workspace_kontainer` |
| `sumber.workspace_kontainer` | path | wajib | `/workspace` | awalan path di lock `brief=` yang diterjemahkan ke `sumber.workspace` |
| `sumber.brief` | dir host | wajib | `/<jalur-host>/workspace/brief` | folder brief |
| `sumber.lock` | dir host | wajib | `/<jalur-host>/workspace/locks` | folder lock |
| `sumber.handoff` | dir host atau `null` | boleh `null` | `/<jalur-host>/workspace/handoff` | folder handoff; **belum dibaca generator** (celah, bagian 5 `docs/pasang-g7.md`) |
| `sumber.proc` | dir | wajib | `/proc` | `/proc` |
| `pola.brief_nama` | regex; memuat `{pelaksana}` dan grup `sisa` | wajib | `<regex>` | konvensi nama brief |
| `pola.lock_nama` | regex (fullmatch nama lock tanpa `.lock`) | wajib | `<regex>` | nama lock yang sah |
| `pola.lock_pemisah_subtugas` | string atau `null` | boleh `null` | `"--"` | bila ada: slug project = bagian nama lock sebelum pemisah; `null` = nama lock = slug |
| `pola.peminta` | regex (`re.match` per baris header) | wajib | `<regex>` | baris akhir header brief yang memuat pemberi |
| `kategori_perintah` | list `{pola, teks, sesudah_panggil?}` | wajib (kunci harus ada; list boleh kosong) | `[{"pola":"<regex>","teks":"menjalankan perintah di <host>"}]` | dicocokkan berurutan terhadap detail terminal/execute_code; `teks` entri pertama yang cocok menjadi langkah. `sesudah_panggil` (boolean, opsional, bawaan `false`; bukan boolean = config ditolak): entri tanpa kunci itu (atau `false`) dicocokkan **sebelum** deteksi pemanggilan agen (TL/anggota), jadi menang atas "memanggil …"; entri `true` dicocokkan **sesudahnya**, hanya bila perintah bukan pemanggilan agen. Nilai g7 tidak memakainya (KONTRAK revisi 2 butir a; `generator.py:107–109,211`) |
| `tool.awalan_bank_dokumen` | string atau `null` | boleh `null` | `"mcp__<bank>__"` | awalan nama tool bank dokumen; sufiks `cari`/`baca`/`status` → "membaca bank dokumen", `setor`/`terbitkan`/`hapus` → "mengelola bank dokumen" |
| `tool.catat_progres` | nama tool atau `null` | boleh `null` | `null` | `null` = sumber langkah misi belum tersedia |
| `tool.setor` | nama tool atau `null` | boleh `null` | `"mcp__<bank>__setor"` | tool setor dokumen (peristiwa "menyetor dokumen") |
| `aktivitas` | objek `{catat_teks, teks_maks, catat_detail, detail_maks}` | **opsional** | lihat bagian 3 | privasi log hook; dibaca hook saja, generator mengabaikan |

### 2.1 Validasi tambahan oleh generator (dari kode, `_validasi_tim`)

Satu pelanggaran = seluruh berkas ditolak (aturan Kegagalan, bagian 1). Selain kolom Wajib di atas:

- Akar berupa objek; `versi` harus int sungguhan (boolean ditolak) bernilai 1. Berkas dibaca paling banyak 1 MiB dan harus berkas biasa.
- `orang`: list tak kosong; tiap `id` cocok `[a-z0-9][a-z0-9_-]{0,63}`, `nama` string tak kosong, `peran` string, `induk` list string tak kosong;
  `id` unik dan `nama` unik.
- `penonton`: list tak kosong, setiap anggota string yang ada di `orang[].id`, tanpa duplikat. `pemilik`: string yang ada di `penonton`.
- `koordinator` dan `cto`: string yang cocok pola id yang sama. Kode tidak memeriksa apakah keduanya ada di `agen`.
- `agen`: objek; tiap kunci cocok pola id; tiap nilai objek dengan `nama` string tak kosong, `peran` string, `induk` list string tak kosong,
  dan `ruang` (bila ada) ∈ `koordinasi, riset, qa, teknik`. Nilai `ruang` lain menolak seluruh berkas.
- `sumber.activity`, `profil`, `workspace`, `workspace_kontainer`, `brief`, `lock`, `proc`: string tak kosong. `sumber.handoff`: string tak kosong,
  `null`, atau tidak ada.
- `pola.brief_nama`, `pola.lock_nama`, `pola.peminta`: string tak kosong. `brief_nama` harus memuat `{pelaksana}` dan `(?P<sisa>`.
  `pola.lock_pemisah_subtugas`: string tak kosong, `null`, atau tidak ada.
- Semua regex harus valid: `brief_nama` (setelah `{pelaksana}` diganti), `lock_nama`, `peminta`, dan tiap `kategori_perintah[].pola`.
- `kategori_perintah`: list; tiap entri objek dengan `pola` dan `teks` string tak kosong, `sesudah_panggil` boolean bila ada.
- `tool`: objek; `awalan_bank_dokumen`, `catat_progres`, `setor`: string tak kosong, `null`, atau tidak ada.
- Tidak divalidasi: `aktivitas` (dibaca hook saja), kunci berawalan `_`, dan kunci lain yang tidak dikenal (diabaikan).

Berkas acuan dengan nilai placeholder generik (tanpa nama orang/tim nyata dan tanpa path server nyata): `conf/tim.example.json`.
`conf/tim.json` adalah config per pemasangan, seperti `.env`, dan di-`.gitignore` (hanya `conf/tim.example.json` yang masuk git;
bisa dibalik dengan menghapus satu baris di `.gitignore`). `conf/proyek.json` (peta slug → nama aplikasi) tetap berkas sendiri:
katalog aplikasi, bukan identitas tim. Teks peristiwa yang dulu memuat nama koordinator memakai `agen[<koordinator>].nama`.

Ringkasan di `storage/ringkasan/<penonton>.json` ikut membawa `pemilik` dan `koordinator` dari config (`docs/skema-ringkasan.md`).

## 3. Kunci `aktivitas` (privasi log aktivitas, KONTRAK §6a)

Keputusan akhir ada pada Pemilik saat pasang (pertanyaan Q4); kontrak menetapkan **bawaan = tanpa isi**.

```json
"aktivitas": {"catat_teks": false, "teks_maks": 300, "catat_detail": false, "detail_maks": 1000}
```

| Sub-kunci | Tipe | Bawaan | Rentang | Arti |
|---|---|---|---|---|
| `catat_teks` | boolean | `false` | hanya `true` (JSON boolean) yang menyalakan | `true` → baris memuat `text` = teks pesan; rahasia disamarkan DULU, baru dipotong `teks_maks` |
| `teks_maks` | int | 300 | 1–2000; di luar rentang atau bukan int → 300 | panjang maksimum `text` |
| `catat_detail` | boolean | `false` | hanya `true` (JSON boolean) yang menyalakan | `true` → baris memuat `detail` = argumen tool (urutan kunci sumber: command, path, query, goal, url, lalu JSON); disamarkan, baru dipotong `detail_maks` |
| `detail_maks` | int | 1000 | 1–4000; di luar rentang atau bukan int → 1000 | panjang maksimum `detail` |

Aturan baca (hook):

- Bila `aktivitas` tidak ada, atau `catat_teks`/`catat_detail` bukan tepat `true`, baris hanya memuat metadata: `type`, `role`, `name`,
  `profile`, `sid`, `ts`, `tool` (untuk type tool), `blocked` (false), `sub` (true bila `extra.platform == "subagent"`), `sistem` (true
  bila pesan = notifikasi gateway; dihitung dari teks di memori, **teksnya tidak ditulis**). Kunci `text` dan `detail` **tidak ada**
  di baris (bukan string kosong). Tidak ada nilai bawaan yang mencatat isi pesan.
- `AD_TIM` tidak diset, atau `tim.json` tidak terbaca/tidak sah → hook tidak menulis apa pun (koordinator tidak diketahui) dan keluar 0.
- Nilai g7 dan `conf/tim.example.json` menulis keempat sub-kunci secara eksplisit dengan nilai bawaan di atas.
- Generator wajib tetap berjalan atas log metadata-saja (ada satu tes untuk itu).

**Konsekuensi bawaan `false`** (ditulis di sini sesuai KONTRAK §6a):

1. Nomor misi `T-nnn` tidak bisa dicocokkan dari teks pesan (pencocokan baris 1 `text` dengan header brief tidak pernah cocok), jadi
   daftar misi di tampilan Kantor Agen kosong (`docs/misi.md`).
2. Perintah tidak bisa diklasifikasi memakai `kategori_perintah` (tidak ada `detail` yang dicocokkan); langkah jatuh ke
   "menjalankan perintah".
3. Pemanggilan TL tidak terdeteksi dari detail perintah.
4. Tampilan aktivitas menjadi generik (berbasis nama tool).

**Cara menyalakan:** ubah `conf/tim.json` (`catat_teks` dan/atau `catat_detail` menjadi `true`), atas keputusan Pemilik. Konsekuensi
privasi: `text` dan `detail` memuat isi percakapan dan perintah (rahasia disamarkan sebelum dipotong, tetapi penyamaran bukan
jaminan); menyalakan berarti log aktivitas mulai menyimpan isi itu. Perubahan ini bukan bagian dari dokumen ini untuk diputuskan.

## 4. Variabel env

### 4.1 Compose (`.env` di `<AKAR>`, mode 600, tidak di-commit; contoh nilai di `.env.example`)

| Variabel | Dipakai oleh | Contoh di `.env.example` | Arti |
|---|---|---|---|
| `AD_IMAGE` | compose | `agent-dashboard-web` | nama image web (`image: "${AD_IMAGE:?}:${AD_TAG:?}"`) |
| `AD_TAG` | compose | `lokal` | tag image web |
| `AD_BIND` | compose | `127.0.0.1` | alamat bind port host (`ports: ["${AD_BIND:?}:${AD_PORT:?}:8080"]`); satu bind. Bind kedua = override compose (mis. alamat Tailscale), tidak bawaan |
| `AD_PORT` | compose | `24130` | port host |
| `AD_UID` | compose | `1000` | uid proses container web (`user: "${AD_UID:?}:${AD_GID:?}"`); isi dengan `id -u` pemilik folder project |
| `AD_GID` | compose | `1000` | gid proses container web; isi dengan `id -g` pemilik folder project |

Bind kedua (mis. alamat Tailscale selain alamat di `AD_BIND`) dibuat sebagai override compose, bukan nilai bawaan. Ilustrasi
(`docker-compose.override.yml` dibuat saat pasang bila perlu; belum diuji):

```yaml
services:
  web:
    ports:
      - "<alamat-bind-kedua>:${AD_PORT:?}:8080"
```

Berkas override ini adalah config per pemasangan; sebaiknya tidak di-commit (usulan, menurut saya; `.gitignore` dikelola TL lain).

Semua bertanda `:?` di compose: variabel kosong atau tidak ada = `docker-compose config` gagal (gagal tertutup). `.env` **tidak** dibuat di
repo; dibuat saat pasang (`docs/pasang-g7.md`).

### 4.2 Proses

| Variabel | Dipakai oleh | Bawaan | Arti |
|---|---|---|---|
| `AD_TIM` | generator, web (container), hook | generator: `<AKAR>/conf/tim.json`; web: `/srv/conf/tim.json` (compose mem-mount `./conf/tim.json:/srv/conf/tim.json:ro` dan mengeset `AD_TIM=/srv/conf/tim.json`); hook: tidak ada | lokasi `tim.json`. Hook: dipakai untuk id koordinator dan nama pemilik |
| `TEAM_ACTIVITY_LOG` | hook aktivitas (`hooks/team-activity.py`, **tidak dipasang** di tahap ini) | tidak ada | path berkas jsonl tujuan. Tidak diset = hook tidak menulis apa pun. Tanpa path bawaan yang menunjuk server tertentu |

Path `AD_TIM` dan `TEAM_ACTIVITY_LOG` yang terlihat dari container Hermes tempat hook berjalan ditentukan saat pasang (keputusan
terbuka Q6, `docs/pasang-g7.md`), karena `conf/tim.json` ada di host.

## 5. Opsi CLI generator

`python3 script/generator.py [--tim P] [--activity P] [--workspace D] [--proc D] [--proyek P] [--profil D] [--keluaran D] [--nomor P] [--interval 3] [--sekali [--sekarang ISO]]`

`--activity --workspace --profil --proc` menimpa nilai config; `--tim` menimpa `AD_TIM`. Bawaan `--keluaran`
`<AKAR>/storage/ringkasan` dan `--nomor` `<AKAR>/storage/misi/nomor.json` adalah lokasi live: untuk uji arahkan keduanya ke
`tmp/test/…`.

## 6. Nilai pemasangan g7

Sumber nilai: KONTRAK §2 (diisi TL generator ke `conf/tim.json` host ini). Berkas `conf/tim.json` itu sendiri tidak ada di repo
(di-`.gitignore`); angka dan path di bawah adalah catatan nilai yang diisi saat pasang. Path di bawah adalah **nilai config yang sah**
(path state Hermes di host g7, mount container `hermes`: `/data/hermes-agent/workspace` → `/workspace`,
`/data/hermes-agent/data` → `/opt/data`), bukan contoh. Generator hanya membaca path itu (baca-saja); tidak ada yang diubah dari sana.

### 6.1 Identitas

| Kunci | Nilai g7 |
|---|---|
| `orang` | `[{"id":"akbar","nama":"Pak Akbar","peran":"Pemilik tim","induk":[]}]` |
| `penonton` | `["akbar"]` |
| `pemilik` | `"akbar"` |
| `koordinator` | `"default"` (Lala; nilai `profile` di payload hook profil default) |
| `cto` | `"arsa"` |

`agen`:

| id | nama | peran | induk | ruang |
|---|---|---|---|---|
| `default` | Lala | Koordinator | `["akbar"]` | `koordinasi` |
| `arsa` | Arsa | CTO | `["default"]` | `teknik` |
| `sofi` | Sofi | Riset dan regulasi | `["default"]` | `riset` |
| `g7-tl1` … `g7-tl5` | G7-TL1 … G7-TL5 | Tech Lead | `["arsa"]` | `teknik` |
| `g7-qc` | G7-QC | QA/QC | `["default"]` | `qa` |

### 6.2 Sumber data

| Kunci | Nilai g7 |
|---|---|
| `sumber.workspace` | `/data/hermes-agent/workspace` |
| `sumber.workspace_kontainer` | `/workspace` |
| `sumber.brief` | `/data/hermes-agent/workspace/tim-g7/brief` |
| `sumber.lock` | `/data/hermes-agent/workspace/tim-g7/locks` |
| `sumber.handoff` | `/data/hermes-agent/workspace/tim-g7/handoff` (belum dibaca generator) |
| `sumber.profil` | `/data/hermes-agent/data/profiles` |
| `sumber.activity` | `/data/hermes-agent/data/agent-hooks/state/activity.jsonl`, dengan `_catatan`: "belum tersedia: hook belum dipasang" |
| `sumber.proc` | `/proc` (KONTRAK tidak menyebut nilai khusus g7; bawaan) |

Asal path tim: `lockdir`, `handoff_dir`, dan `verdict_dir` dari konfigurasi tim G7 diterjemahkan ke path host di atas.

### 6.3 Pola, kategori, tool

| Kunci | Nilai g7 |
|---|---|
| `pola.lock_nama` | menerima `<project>` dan `<project>--<subtugas>` |
| `pola.lock_pemisah_subtugas` | `"--"` |
| `pola.peminta` | cocok dengan baris `Dari: … Peminta asal: …` pada brief tim G7 |
| `pola.brief_nama` | konvensi `YYYY-MM-DD-<tl>-<project>[-<subtugas>].md` |
| `kategori_perintah` | tiga entri berurutan, tanpa `sesudah_panggil` (terukur: `grep -c sesudah_panggil conf/tim.json` = 0 di g7, 25 Okt 2026): ssh ke `g7` → "menjalankan perintah di g7"; ssh ke host aplikasi sumber → "menjalankan perintah di " diikuti nama host itu; pola RouterOS/R1 lama → "mengakses R1" |
| `tool.awalan_bank_dokumen` | `"mcp__obsidian__"` |
| `tool.setor` | `"mcp__obsidian__setor"` |
| `tool.catat_progres` | `null` (tim G7 mencatat langkah di handoff; belum dibaca generator) |
| `aktivitas` | `{"catat_teks":false,"teks_maks":300,"catat_detail":false,"detail_maks":1000}` |

Ekspresi reguler persis tiap `pola.*` dan `kategori_perintah[].pola` ada di `conf/tim.json` host ini; nama host aplikasi sumber pada
entri kedua `kategori_perintah` sengaja tidak ditulis di dokumen (nilai config, bukan dokumentasi).

### 6.4 Env pemasangan g7

Nilai awal `.env.example`: `AD_IMAGE=agent-dashboard-web`, `AD_TAG=lokal`, `AD_BIND=127.0.0.1`, `AD_PORT=24130`, `AD_UID=1000`, `AD_GID=1000`.
`AD_UID`/`AD_GID` harus sama dengan `id -u`/`id -g` pemilik `<AKAR>` di host g7 (cek saat pasang, `docs/pasang-g7.md`; terukur di g7 25 Okt 2026:
pemilik `<AKAR>` uid/gid `1000`/`1000`, user `akbar`). Apakah port 24130 sudah dipakai di host g7: **belum diverifikasi** (dicek saat pasang).
