# Misi "Kantor Agen" — aturan generator (tambahan skema "1")

Status: berlaku sejak 24 Okt 2026 (generator `script/generator.py`). Sumber keputusan: kontrak CTO "Kantor Agen" bagian A–C
(dokumen kontrak tim sumber, tidak disalin ke project ini). Semua field skema "1" (`docs/skema-ringkasan.md`) tetap
ada dengan makna sama; `versi_skema` tetap `"1"`. Yang ditambah: `ringkasan`, `misi`, `agen[].ruang`, `agen[].keadaan`,
`agen[].misi_aktif`, `riwayat_hari_ini[].misi`, dan baris riwayat K3. UI lama tetap jalan dengan generator baru, sehingga
rollback web dan generator bisa terpisah. Uji: `tests/generator/test_misi.py`, `tests/generator/test_misi_penonton.py`,
fixture `tests/fixtures/misi1/` (dibangun ulang dengan `python3 tests/fixtures/bangun_misi1.py`).

> Penulisan: `<koordinator>`, `<cto>`, `<pemilik>`, `<pemberi-1>`, `<tl-1>` … adalah id yang diisi dari `conf/tim.json`
> (kunci `koordinator`, `cto`, `pemilik`, `orang`, `agen`; lihat `docs/config.md`), bukan nilai tetap di kode. Nama tampilan
> di teks peristiwa diambil dari `agen[<koordinator>].nama` dan sejenisnya. Contoh nama project (`proyek-a`) fiktif.

> **Catatan log aktivitas (privasi; lihat `docs/config.md` bagian `aktivitas`):** hook aktivitas edisi G7 secara bawaan menulis
> baris tanpa `text` dan `detail` (`aktivitas.catat_teks` dan `catat_detail` bawaan `false`). Akibat pada aturan di dokumen ini
> bila bawaan itu dipakai: pencocokan B1 (baris 1 `text` dengan header brief) tidak pernah cocok, sehingga tidak ada misi yang
> terdeteksi dari log; kategori langkah yang membaca `detail` (K1) turun ke nama tool. Menyalakannya = keputusan Pemilik.

## 1. Sumber yang dibaca (baca saja)

| Sumber | Yang dipakai | Tidak pernah ditulis ke keluaran |
|---|---|---|
| `--activity` (log aktivitas) | `ts`, `profile`, `sid`, `type`, `tool`, `sub`; baris 1 `text` (bila H1 ganda: awalan `text` sepanjang header brief, B1) dan `detail` hanya **dicocokkan** | isi `text`/`detail`, sid |
| `--workspace`/`brief/*.md` | header (H1 s.d. baris Peminta, §3.5 skema); keberadaan, ukuran, dan mtime `<brief tanpa .md>.laporan.txt` | isi brief di luar header, isi laporan |
| `--workspace`/`locks/*.lock` | lock sah §3.4a + nilai `brief=` | field lock lain |
| `--proc` | argv proses hermes (profil `-p`, header `-z`), PPID (`/proc/<pid>/stat` kolom 4) | argv |
| `--profil`/`<p>/state.db` | tabel `sessions`, **hanya kolom `id, parent_session_id, started_at, ended_at`**; `source = 'subagent'` dipakai sebagai penyaring `WHERE` saja | id sesi, kolom lain |
| `--profil`/`<p>/config.yaml` | `delegation.oneshot_max_children` | isi lain |
| `conf/tim.json` kunci `agen` (`--tim` / `AD_TIM`) | `agen[].ruang` (opsional); daftar agen, `koordinator`, `cto`, `pemilik` | – |

Kueri state.db persis (konstanta `KUERI_SESI`): `SELECT id, parent_session_id, started_at, ended_at FROM sessions WHERE
source = 'subagent' AND parent_session_id IN (?, …)`; koneksi URI `file:<path>?mode=ro`, `timeout=1.0` detik, tidak pernah
`select *`. Uji `test_kueri_state_db_hanya_empat_kolom_tanpa_bintang` memeriksa string kuerinya.

## 2. Definisi misi (B1–B8)

**B1 — misi.** Misi = satu berkas brief `<workspace>/brief/*.md` (berkas biasa, realpath di dalam direktori brief, baris 1
diawali `# `) yang dijalankan sebagai sesi utama agen: sesi `(profil, sid)` dengan profil = agen hadir selain `<koordinator>`, sid
tidak kosong, baris `msg` pertamanya **bukan** `sub: true`, dan baris pertama `text`-nya (strip) sama persis dengan baris 1
brief (strip), dengan H1 itu dimiliki tepat 1 berkas. **H1 ganda (B1', CTO 24 Okt 2026):** bila H1 itu dimiliki > 1 berkas,
kandidat = berkas ber-H1 itu yang header gabungannya (H1 s.d. baris Peminta digabung `\n`, `\r` akhir baris dibuang di
kedua sisi) sama dengan `text` pada min(panjang `text`, panjang header) karakter pertama (hook mencatat `text` maksimal 300
karakter); tepat 1 kandidat → berkas itu, selain itu bukan misi (fail-closed). Perbandingan hanya di memori; isi `text`/brief
di luar header tidak pernah ditulis ke keluaran. Kecocokan diputuskan saat baris itu diproses (backfill atau live)
terhadap brief yang ada saat itu, lalu dibekukan untuk sid itu. Beberapa sesi dengan brief sama = satu misi. Baris
notifikasi sistem (`sistem: true`/pola hook) tetap diabaikan tanpa efek. Sesi tanpa kecocokan (percakapan koordinator,
perintah inline, sub-agen, H1 ganda tanpa header pembeda) bukan misi.

**B2 — nomor stabil.** Lihat bagian 3.

**B3 — pelaksana** = profil sesi terakhir misi. `mulai` = waktu baris `msg` pertama sesi pertama.

**B4 — judul, pemberi, pemilik, project.** Judul/pemberi/pemilik = aturan §3.5 skema dari header brief (judul untuk
pelaksana TL membuang awalan slug project menurut J-1 di bawah; judul kosong / brief hilang untuk pelaksana TL → J-2, lalu
`Pekerjaan <project_nama>` bila ber-project, selain itu `null`). **Project** = slug lock sah yang `brief=`-nya berkas ini (slug terkecil bila
lebih dari satu); jika tidak ada, kunci terpanjang `conf/proyek.json` yang menjadi awalan (diikuti `-` atau akhir) dari sisa
nama berkas sesudah `YYYY-MM-DD-<pelaksana>-` tanpa `.md`; tidak ada → `null`.

**J-1 — awalan slug berbatas kata (CTO 24 Okt 2026).** Himpunan slug S = {project lock, project berkas} (yang ada). Bagian H1
yang sama dengan slug s atau berbentuk `<s>(-[a-z0-9]+)+` (mis. `proyek-a-ops` untuk s = `proyek-a`) dibuang utuh; bagian yang
diawali `<s> ` atau `<s>(` kehilangan awalan s lalu aturan kurung berlaku (`portal-dev (data)` → `data`); bagian lain tidak
dipotong. Judul pelaksana non-TL (tanpa slug) tidak berubah. **J-2 — judul dari nama berkas.** Judul kosong untuk pelaksana
TL: pb = project berkas; topik = sisa nama sesudah `YYYY-MM-DD-<pelaksana>-<pb>-` tanpa `.md`, `-` → spasi; judul =
`<nama project pb> — <topik>` (contoh `2026-10-24-<tl-1>-proyek-a-review-uji.md` → `Proyek A — review uji`, bila `conf/proyek.json` memetakan `proyek-a` ke `Proyek A`); pb tidak
ada atau topik kosong → perilaku lama. Tetap disaring §3.7 dan dipotong 200 karakter. J-1/J-2 berlaku sama untuk
`tugas_aktif[].judul` dari lock. Uji: `tests/generator/test_koreksi_header.py`.

**B4 revisi judul (KONTRAK B4, CTO 24 Okt 2026).** Satu pengecualian atas §3.5 skema: bagian pertama yang diawali `Brief`
dan memuat `:` tidak dibuang; teks sesudah `:` pertama (strip) menjadi bagian judul dan diproses seperti bagian lain
(awalan tanggal, awalan slug untuk pelaksana TL, kurung, bagian kosong dibuang). Tanpa `:` → dibuang seperti semula.
Contoh: `# Brief <Nama>: proyek-a tampilan baru (24 Okt 2026)` → `proyek-a tampilan baru (24 Okt 2026)`
(pelaksana non-TL); `# Brief <Nama>: proyek-a koreksi dua` → `koreksi dua` (pelaksana TL, project `proyek-a`);
`# Brief <Nama>:` → `null`; `# Brief TL — proyek-a — 2026-10-16 — Audit` tetap `Audit`. Berlaku sama untuk
`tugas_aktif[].judul` (makna field tetap "judul"). Uji: `tests/generator/test_judul_brief_x.py`.

**B5 — rantai** = `[pemberi_id]` (bila ada) + jalur organisasi dari `<koordinator>` ke pelaksana menurut `induk` efektif (§3.0):
dari pelaksana naik ke induk pertama yang hadir, sampai `<koordinator>` (maks 6 langkah; tidak sampai → `[pelaksana]`), lalu
dibalik. Ini **rantai organisasi**, bukan jejak pengamatan siapa memanggil siapa.

**B6 — status** (dievaluasi tiap siklus):
- *proses misi* = proses CLI hermes dengan pelaksana di argumen `-p` dan header `-z` cocok tepat 1 brief, yaitu brief misi;
- *lock misi* = lock sah §3.4a ber-`brief=` berkas misi; *laporan* = `<brief tanpa .md>.laporan.txt` berkas biasa > 0 byte.

| Status | Syarat | `selesai` |
|---|---|---|
| `jalan` | ada proses misi, tanpa keturunan proses misi lain | `null` |
| `menunggu` + `alasan: "misi-lain"` | ada proses misi dan ≥ 1 keturunannya (rantai PPID, maks 64 langkah) adalah proses misi lain; `menunggu_misi` = id semua misi keturunan itu, urut nomor | `null` |
| `menunggu` + `alasan: "review"` | tanpa proses misi, ada lock misi, laporan ada | `null` |
| `menunggu` + `alasan: "gantung"` | tanpa proses misi, ada lock misi, laporan tidak ada / 0 byte | `null` |
| `selesai` | tanpa proses dan lock misi, laporan ada | mtime laporan |
| `berakhir` | tanpa proses dan lock misi, laporan tidak ada / 0 byte | ts baris log terakhir sesi utama misi |

Misi `selesai`/`berakhir` hanya dimuat bila tanggal `selesai` = hari ini (WIB); misi `jalan`/`menunggu` selalu dimuat.
`induk_misi` = id misi pemilik proses leluhur terdekat (hanya saat keduanya hidup), selain itu `null`.

**B7 — langkah.** Setiap baris tool bernama `tool.catat_progres` (`conf/tim.json`; `null` = sumber langkah belum tersedia, daftar langkah kosong; tim G7: `null`) dari sid sesi utama misi (bukan sid sub-agen) →
`{"waktu", "label"}`; label dari `detail` dengan regex `Status\W{0,6}([A-Za-z]+)` (pertama, tanpa beda huruf):
mulai→`Mulai`, langkah→`Langkah`, selesai→`Selesai`, hambatan→`Hambatan`, berhenti→`Berhenti`, antre→`Antre`; lainnya /
tidak cocok → `Kemajuan dicatat`. `langkah_total` selalu `null` (UI menampilkan "—"). `langkah_sekarang` = kategori K1
(§3.2) baris log terakhir sesi utama misi (+ ` · <project_nama>` bila ber-project), `langkah_waktu` = ts-nya.

**B8 — sub-agen dan kuota.** Sub-agen = baris `sessions` state.db profil pelaksana dengan `source = 'subagent'` dan
`parent_session_id` ∈ sid sesi utama misi, urut `started_at` → `{"ke": 1..n, "mulai", "selesai"}` (ISO WIB; `selesai`
`null` = aktif); tanpa teks tugas. state.db tak terbaca (tidak ada, bukan SQLite, tanpa tabel, terkunci > 1 dtk) → galat
tetap `Data sesi tidak terbaca` dan misi pelaksana itu `subagen: null`. **Kuota spawn** = `delegation.oneshot_max_children`
dari `<profil>/<p>/config.yaml` (parser minimal: blok kolom-0 `delegation:`, baris berindentasi `oneshot_max_children:
<int>` sebelum kunci kolom-0 berikutnya; komentar diabaikan); tidak ada / tak terbaca → `null`.

## 3. Nomor misi `T-nnn` (B2) — aturan stabil

- Registri `--nomor` (bawaan `<project>/storage/misi/nomor.json`): `{"versi": 1, "nomor": {"<nama berkas brief>": <int>}}`.
- Brief yang pertama kali menjadi misi mendapat `maks + 1` (mulai 1), urut baris log yang mencocokkannya. Nomor yang sudah
  ada di registri tidak pernah diubah atau dipakai ulang (entri tidak pernah dihapus walau berkas brief hilang).
- Registri tidak ada → dibangun dari backfill (log dibaca dari awal) lalu ditulis. Ditulis atomik (`nomor.json.tmp` →
  `rename`, mode 0640; direktori dibuat 0750 bila belum ada) **hanya bila berubah**. JSON ditulis ASCII (`\uXXXX` untuk
  karakter non-ASCII) sehingga nama berkas apa pun, termasuk yang bukan UTF-8, tersimpan dan terbaca ulang sama.
- Registri dibaca setiap siklus (juga bila belum ada misi).
- Registri tak terbaca / rusak (bukan JSON, `versi` ≠ 1, nilai bukan bilangan bulat ≥ 1, nomor ganda, bukan berkas biasa)
  → galat tetap `Nomor misi tidak terbaca`, registri **tidak ditimpa**, `misi` = `[]` siklus itu, semua `riwayat[].misi`
  `null`, dan baris riwayat yang teksnya memuat id misi (K3, "melanjutkan") tidak ditampilkan. Pulih otomatis begitu registri
  sah lagi. **[lokal]** Gagal menulis registri (mis. direktori tanpa izin tulis) diperlakukan sama (fail-closed: nomor yang
  tidak tersimpan tidak dijamin stabil).
- `id` = `"T-"` + nomor 3 digit nol di depan: `T-007`, `T-281`, `T-1000`.
- **[lokal]** API Python tanpa `nomor=` (dipakai uji) menyimpan registri di memori proses saja.
- Akibatnya nomor stabil antar-siklus, antar-restart, dan antar-instance baru selama registrinya sama. Menghapus registri =
  penomoran ulang dari backfill (urutan bisa berbeda bila brief lama sudah dihapus): jangan dihapus kecuali disengaja.

**Pemicu evaluasi ulang aturan nomor:** (a) registri tumbuh sampai pencocokan per siklus terukur > 100 ms; (b) brief
berganti nama/dipindah sehingga satu pekerjaan tercatat dua nomor; (c) format H1 brief berubah sehingga misi tidak lagi
tercocokkan; (d) log aktivitas dirotasi/dipotong (backfill tidak lagi melihat sesi lama) — nomor lama tetap, tetapi misi
lama tidak dimuat lagi.

## 4. Field tambahan per berkas penonton (C1–C8)

- **C1 `agen[].ruang`** dari kunci opsional `ruang` pada `agen[<id>]` di `conf/tim.json` ∈ {`koordinasi`, `riset`, `qa`, `teknik`}; nilai lain
  → seluruh berkas ditolak seperti aturan §3.0 (galat `Config agen tidak terbaca` + config sah terakhir); tanpa kunci / tanpa
  entri → `lain`.
- **C2 `agen[].keadaan`** (revisi CTO 24 Okt 2026), dievaluasi berurutan: (1) agen punya ≥ 1 misi aktif terlihat di berkas
  → `menunggu` bila semuanya `menunggu`, selain itu `bekerja`; (2) `status` = `sibuk`/`bebas` → nilai itu; (3) `status` =
  `menunggu` → `menunggu`; (4) selain itu `bekerja`. Jadi di berkas penonton terbatas, agen yang menjalankan misi V tanpa tugas
  milik V (`status` `sibuk`, mis. TL tanpa lock untuk brief itu) tetap tampil `bekerja`/`menunggu`. `misi_aktif` = id misi
  `jalan`/`menunggu` terlihat penonton dengan pelaksana agen itu (urut nomor). `agen[].status` tetap §3.3.
- **C3 `riwayat_hari_ini[].misi`** = id misi bila baris berasal dari sid sesi utama misi, sid sub-agen misi (B8), lock misi,
  atau K3; selain itu `null` (juga `null` bila misi itu tidak dimuat di berkas). Pemilik baris ber-misi = pemilik misi.
  **[lokal]** Akhiran heuristik ` · <project_nama>` (§3.6) dibuang dari baris ber-misi bila pemilik misi ≠ pemilik heuristik
  dan pemilik misi bukan akun pemilik tim, agar nama project tugas pemilik lain tidak masuk ke berkas penonton terbatas;
  baris ber-misi milik akun pemilik tim memakai teks lama apa adanya (A1).
- **C4** Baris "`<Agen> mulai bekerja`" untuk sid sesi utama misi diganti: sesi pertama → K3-1; sesi berikutnya →
  `<Agen> melanjutkan <T>`. Bila baris tool sesi itu tercatat sebelum baris `msg` pertamanya, baris "mulai bekerja" yang
  terlanjur terbit dibuang saat sesi tercocokkan.
- **C5 K3** (semua ber-`misi`, hanya bila waktunya hari ini, ikut batas 300): K3-1 `<Pemberi> memberi order <T> lewat <nama
  rantai tanpa pemberi, dipisah " → ">` (pemberi null: `Order <T> masuk lewat …`; pelaku = id pemberi atau ``<koordinator>``; waktu =
  baris msg pertama sesi pertama); K3-2 `<Pelaksana> men-spawn sub-agen ke-<n> · <T>` (waktu `started_at`); K3-3 `Sub-agen
  ke-<n> <Pelaksana> selesai · <T>` (waktu `ended_at`); K3-4 `<Pelaksana> menyelesaikan <T>` / `<T> berakhir tanpa laporan`
  (waktu `selesai`); pelaku K3-2..4 = pelaksana. Urutan riwayat: `waktu` naik lalu urutan terjadinya (K3-2..4 mendapat
  urutan saat pertama kali terlihat generator, sehingga pada detik yang sama berada sesudah baris log).
- **C6 `ringkasan`**: `agen` = hitungan `keadaan` semua agen di berkas; `misi.aktif` = jumlah misi `jalan`/`menunggu`;
  `misi.selesai_hari_ini` = jumlah `selesai` + `berakhir`; `subagen_aktif` = jumlah sub-agen aktif pada misi aktif (`null`
  bila ada misi aktif ber-`subagen` null).
- **C8** Urutan `misi`: aktif dulu (`menunggu` lalu `jalan`, dalam kelompok `mulai` naik), lalu `selesai`/`berakhir`
  (`selesai` turun); seri → nomor naik.

## 5. Isolasi per penonton (C7)

- Akun pemilik tim (`cakupan` = `semua`): semua misi, semua baris.
- Akun penonton terbatas V (`cakupan` = `order-sendiri`): `misi` hanya pemilik V (`pemberi_id` = V); `menunggu_misi` /
  `induk_misi` disaring ke id yang ada di berkas V (selain itu dibuang / `null`); `riwayat_hari_ini` hanya baris pemilik V;
  agen tanpa misi aktif V → `keadaan` `bebas` (bila `status` `bebas`) atau `sibuk`, `misi_aktif` `[]`. Tidak ada judul,
  rantai, project, langkah, sub-agen, peristiwa, atau hitungan milik orang lain; `ringkasan` dihitung dari isi berkas V.
- Ragu pemilik → akun pemilik tim (§5 skema, fail-closed).

## 6. Uji dan pembanding

- Unit: `PYTHONDONTWRITEBYTECODE=1 TMPDIR=$PWD/tmp/test python3 -m unittest discover -s tests/generator` (dari root project).
- Data asli tanpa menyentuh storage live: jalankan generator dengan `--keluaran` **dan** `--nomor` ke `tmp/test/…` (bawaan
  keduanya = live). Pembungkus uji dibuat per kebutuhan di `tmp/test/` (tidak disimpan di repo).
- Memori: log dibaca baris demi baris, tidak pernah seluruh berkas sekaligus (koreksi 24 Okt 2026; penjaga
  `tests/generator/test_memori_backfill.py`). Terukur 24 Okt 2026 di unit uji transient dengan batas unit live (MemoryMax=64M,
  CPUQuota=20%, data hari itu): siklus pertama (backfill) selesai `success`, Memory peak 17,2M, swap 0B, ±28 dtk (CPU ±5,7
  dtk). Versi sebelumnya, yang membaca seluruh sisa log ke memori, berakhir `oom-kill` di batas yang sama.
