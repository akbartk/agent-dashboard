# Skema ringkasan agent-dashboard — versi skema "1"

Status: kontrak Fase 2 (TL, 16 Okt 2026), diselaraskan dengan KONTRAK port g7 (25 Okt 2026: identitas tim dibaca dari `conf/tim.json`).
Turunan Lampiran A `docs/requirement.md` + ADR-001/002/003 tim sumber + brief fase 2. Aturan yang bukan dari ADR/brief ditandai
**[lokal]** (keputusan lokal TL, dapat dibatalkan). Uji kontrak: `tests/generator/test_kontrak.py` + `tests/fixtures/`.

> Penulisan: `<koordinator>`, `<cto>`, `<pemilik>`, `<pemberi-1>`, `<anggota-1>`, `<tl-1>` … adalah id yang diisi dari `conf/tim.json`
> (`docs/config.md`), bukan nilai tetap di kode; "Koordinator", "CTO", "Pemilik" di teks contoh = nama tampilan dari config.
> Nama project contoh (`proyek-a`) fiktif.

## 1. Berkas

- Ditulis generator host `script/generator.py` (user `<user-app>`) ke `./storage/ringkasan/<penonton>.json`, penonton
  `<pemilik>`, `<pemberi-1>`, `<pemberi-2>`. Container web membaca `/srv/ringkasan/<penonton>.json` (mount `:ro`).
- Direktori `0750`, berkas `0640` (ditetapkan eksplisit dengan `chmod`/`fchmod`, tidak bergantung umask).
- Tulis atomik: `<penonton>.json.tmp` di direktori yang sama → `os.replace`. Satu baris JSON (UTF-8, `ensure_ascii=False`,
  tanpa spasi) + `\n`. Ditulis ulang setiap siklus (interval bawaan 3 dtk) walau isi lain sama, karena `dibuat_pada` maju.
- Semua waktu ISO 8601 detik dengan zona `+07:00` (WIB), mis. `2026-10-16T14:59:58+07:00`. `ts` di `activity.jsonl`
  (tanpa zona) dibaca sebagai WIB.

## 2. Bentuk JSON

```json
{
  "versi_skema": "1",
  "penonton": "pemilik",
  "cakupan": "semua",
  "pemilik": "pemilik",
  "koordinator": "koordinator",
  "dibuat_pada": "2026-10-16T15:00:00+07:00",
  "galat": [],
  "peringatan": [],
  "orang": [{"id": "pemilik", "nama": "Pemilik", "peran": "Pemilik tim", "induk": []}],
  "agen": [{"id": "koordinator", "nama": "Koordinator", "peran": "Koordinator", "induk": ["pemilik"],
            "status": "jalan", "terakhir_aktif": "2026-10-16T14:59:59+07:00"}],
  "tugas_aktif": [{"id": "lock-proyek-a", "judul": "Audit indeks campuran", "project": "proyek-a",
                   "project_nama": "Proyek A", "pemberi": "Pemilik", "pemberi_id": "pemilik",
                   "pengerja": "TL-1", "pengerja_id": "tl-1", "mulai": "2026-10-16T13:00:00+07:00",
                   "langkah_terakhir": "menjalankan perintah di host-app · Proyek A",
                   "langkah_waktu": "2026-10-16T14:59:58+07:00", "status": "jalan"}],
  "riwayat_hari_ini": [{"waktu": "2026-10-16T14:52:00+07:00", "pelaku": "koordinator", "teks": "Pemilik mengirim pesan ke Koordinator"}]
}
```

| Field | Isi |
|---|---|
| `versi_skema` | `"1"` |
| `penonton` | salah satu id di `penonton` pada `conf/tim.json` (mis. `<pemilik>`, `<pemberi-1>`, `<pemberi-2>`); diisi generator, web memilih berkas dari sesi, bukan dari klien |
| `pemilik`, `koordinator` | (tambahan aditif, KONTRAK §3) selalu ada: id orang `pemilik` dan id agen `koordinator` dari `conf/tim.json`. `versi_skema` tetap `"1"` |
| `cakupan` | `"semua"` bila `penonton` = `pemilik`, selain itu `"order-sendiri"` |
| `dibuat_pada` | waktu siklus generator; dasar label "Diperbarui" dan umur data |
| `galat` | daftar teks tetap (urut abjad, unik), sama di 3 berkas: `Config agen tidak terbaca`, `Daftar proses tidak terbaca`, `Data sesi tidak terbaca`, `Folder profil tidak terbaca`, `Handoff tim tidak terbaca`, `Lock tidak terbaca`, `Log aktivitas tidak terbaca`, `Log guard tidak terbaca`, `Nomor misi tidak terbaca`, `Peta project tidak terbaca`, `Riwayat lock tidak terbaca`, `Verdict QC tidak terbaca` (daftar lengkap = konstanta `GALAT_*` di `script/generator.py`; `Handoff`/`Riwayat lock`/`Verdict QC`/`Log guard` sejak 31 Okt 2026, lihat §7). Kosong = normal |
| `peringatan` | (sejak 22 Okt 2026) daftar teks (urut abjad, unik, lewat penyaring §3.7), sama di 3 berkas, selalu ada, tepat sesudah `galat`: `Profil <id> belum ada di conf/tim.json` (agen hadir, termasuk `<koordinator>`, tanpa entri di config yang berlaku) dan `Profil <id> bentrok dengan id tetap, diabaikan` (folder profil bernama sama dengan `koordinator` atau id di `orang`). Bukan galat: tidak masuk `galat`, tidak memicu banner. Penambahan field ini kompatibel; `versi_skema` tetap `"1"` |
| `orang` | `orang` dari `conf/tim.json` apa adanya (`id`, `nama`, `peran`, `induk`); contoh: `<pemilik>` "Pemilik" "Pemilik tim" `[]`; `<pemberi-1>`, `<pemberi-2>` "Pemberi order" `["<pemilik>"]` |
| `agen` | agen hadir siklus itu (§3.0), bukan daftar tetap: `<koordinator>` + setiap profil Hermes yang punya `profile.yaml`. Urutan = urutan kunci `agen` di `conf/tim.json` (hanya yang hadir), lalu agen tanpa entri (`<koordinator>` dulu bila tak ber-entri, sisanya urut id). Contoh: `<koordinator>`, `<cto>`, `<anggota-1>`, `<anggota-2>`, `<tl-1>`, `<tl-2>`, `<tl-3>`; peran Koordinator / CTO / Riset / QA / Tech Lead ×3; induk `<koordinator>` = `["<pemilik>"]` (atau pemberi order), `<cto>` dan anggota non-TL `["<koordinator>"]`, TL `["<cto>"]` |
| `agen[].status` | `bebas`, `jalan` (label "sedang jalan"), `menunggu` (label "menunggu keputusan"), `sibuk` (hanya `order-sendiri`) |
| `agen[].terakhir_aktif` | ts baris terakhir agent itu di log; `null` bila tidak ada atau tidak boleh dilihat (§5) |
| `tugas_aktif[]` | 12 field di contoh di atas. `judul`, `project`, `project_nama`, `pemberi`, `pemberi_id`, `mulai`, `langkah_terakhir`, `langkah_waktu` boleh `null`. `status` `jalan`/`menunggu` |
| `riwayat_hari_ini[]` | `waktu`, `pelaku` (id agent), `teks`; hanya tanggal hari ini (WIB, sejak 00.00); urut `waktu` naik lalu urutan terjadinya; maks 300 terbaru per berkas |

Beda dengan Lampiran A (`0.1-usulan`) **[lokal]**: `tingkat`, `kegiatan`, `sejak`, `agen[].tugas`, `riwayat[].tugas`
dihapus (tidak ditampilkan UI v2; data minim); tambah `galat`, `agen[].terakhir_aktif`, `project_nama`, `pemberi_id`,
`pengerja_id` (Q-18, Q-22); waktu `HH:MM` diganti ISO lengkap (Q-18 opsi 1: tanggal ikut).

## 3. Sumber dan aturan generator

Sumber (baca saja): config tim `conf/tim.json` (urutan: `--tim` > env `AD_TIM` > `<AKAR>/conf/tim.json`; daftar `agen`, `orang`, `sumber.*`, `pola.*`; `docs/config.md`),
`--profil` (bawaan `sumber.profil`, berkas `<profil>/<id>/profile.yaml`) untuk daftar agen (§3.0), `--activity` (bawaan `sumber.activity`),
`--workspace` (bawaan `sumber.workspace`; lock = `sumber.lock`/`*.lock`, brief = `sumber.brief`/`*.md`), `--proc` (bawaan `sumber.proc`),
`--proyek` (bawaan `<project>/conf/proyek.json`, peta `slug → nama tampilan`, Q-22). Keluaran `--keluaran` (bawaan `<project>/storage/ringkasan`). Tidak ada isi `text`/`detail`/argv/isi brief yang ditulis ke
ringkasan, log, atau stdout.

### 3.0 Daftar agen (sejak 22 Okt 2026, keputusan CTO D1–D9)
- **Agen hadir** dihitung ulang tiap siklus = `<koordinator>` (akar, selalu ada) + setiap entri langsung `<profil>/<id>/` dengan `id`
  `^[a-z0-9][a-z0-9_-]{0,63}$` dan `<profil>/<id>/profile.yaml` berkas biasa (dibaca maks 64 KiB tanpa memblokir FIFO).
  `.deleted`, folder tanpa `profile.yaml`, dan FIFO bukan agen (diam). Profil baru muncul dan profil dihapus hilang pada
  siklus berikutnya tanpa restart. Folder bernama sama dengan `koordinator` atau id di `orang` → diabaikan + peringatan. Folder profil tidak
  terbaca → galat `Folder profil tidak terbaca` + daftar profil terakhir yang terbaca (belum pernah → hanya `<koordinator>`).
- **`agen` di `conf/tim.json`** (dibaca tiap siklus; daftar agen tidak lagi berkas terpisah) = objek `id → {"nama": str tak kosong, "peran": str, "induk": [str tak kosong, …]}`;
  kunci entri lain diabaikan. Tidak terbaca / bukan JSON / kunci bukan id sah / satu entri melanggar tipe → **seluruh berkas**
  ditolak: galat `Config agen tidak terbaca` + config sah terakhir. Bila belum pernah ada config sah di proses generator itu, siklus gagal dengan `ConfigTimTidakSah`
  (stdout `siklus gagal: ConfigTimTidakSah`, bukan `{}`): siklus itu tidak menulis berkas keluaran; `--sekali` keluar dengan kode 1, mode terus-menerus
  mengulang siklus tiap `--interval` (`generator.py:437–446`; teks galat `Config agen tidak terbaca` = konstanta `GALAT_AGEN` di kode). Entri untuk id yang tidak hadir
  diabaikan.
- **Atribut efektif:** ber-entri → nilai entri (nama/peran lewat §3.7). Tanpa entri → nama = id berhuruf awal kapital,
  induk `["<koordinator>"]` (`<koordinator>` sendiri `[]`), peran = `description` profile.yaml (parser minimal: kutip tunggal dengan `''`,
  kutip ganda dengan `\"`/`\\`, blok `|`/`>`, atau polos + baris lanjutan berindentasi; baris dilipat jadi spasi, spasi
  beruntun jadi satu; kutip tak tertutup / tanpa `description` → kosong) → §3.7 → dipotong 120 karakter (`<koordinator>`: kosong).
- **Golongan:** TL = agen hadir selain `<cto>` yang induk efektifnya memuat `<cto>`; **sejak 31 Okt 2026 (alur P1.5)**: bila
  `conf/tim.json` punya kunci `tl` (daftar id), TL = daftar itu ∩ agen yang ada di `agen` (id tak dikenal diabaikan diam-diam), dan
  aturan induk di atas tidak dipakai. `cto` boleh `null`/tidak ada; tanpa `tl` dan tanpa `cto` tidak ada TL. Anggota non-TL = agen hadir selain `<koordinator>`
  dan TL (contoh: `<cto>`, `<anggota-1>`, `<anggota-2>`).
- **`sembunyikan`** (kunci `conf/tim.json`, opsional, sejak 31 Okt 2026): id profil yang tidak tampil di `agen` dan peta
  (tidak masuk daftar agen, tidak memicu `Profil … belum ada di conf/tim.json`). Profil itu tetap dibaca: lock, tugas, dan misi
  miliknya tetap masuk berkas bila aktif, dan namanya tetap dipakai di teks peristiwa. Regex panggil (§3.2) dibangun dari golongan ini tiap siklus (id terpanjang dulu;
  golongan kosong → tidak pernah cocok). Teks tampil memakai nama efektif; id dibawa terpisah.

### 3.1 Log aktivitas
- Dibaca inkremental per siklus (offset byte). Baris tanpa `\n` di akhir belum diproses sampai lengkap. Baris yang bukan
  objek JSON, tanpa `ts` berformat `YYYY-MM-DDTHH:MM:SS`, atau gagal decode → dilewati dan dihitung (log jumlah saja).
- Berkas mengecil (ukuran < offset) atau inode berganti → semua keadaan turunan log dibuang (peristiwa riwayat dari log,
  tool terakhir, sid, rangkaian Koordinator) lalu dibaca ulang dari awal sebagai *backfill* (§3.6). Peristiwa dari lock tetap.
- Baris dengan `profile` = agen hadir selain `<koordinator>` (§3.0) = agent itu. Baris tanpa `profile` = Koordinator; pengirim R = `name`
  (dicocokkan ke `orang[].nama` di `conf/tim.json`, mis. `Pemilik`→`<pemilik>`; selain itu `pemberi_id` null = milik Pemilik saja). Nama
  tampilan R = `name` tersaring (§3.7); kosong atau `?` → `Pengirim tak dikenal` **[lokal]**. Baris dengan `profile` lain
  diabaikan.

### 3.2 Kategori langkah (tabel K1; `detail` hanya dicocokkan, tidak disalin)
Bila log dibuat tanpa `detail` (bawaan hook G7, `docs/config.md` bagian `aktivitas`), pola (1)–(4) tidak pernah cocok dan semua baris terminal/execute_code jatuh ke (5) `menjalankan perintah`; tampilan aktivitas menjadi generik (nama tool).
terminal/execute_code dicek berurutan (pola (1)–(3) dicocokkan lintas baris, `re.S`, agar perintah multi-baris ikut
terhitung; keputusan CTO 16 Okt 2026): (1) pola `kategori_perintah` di `conf/tim.json` (daftar `{pola, teks}`, dicocokkan berurutan; nilai: `docs/config.md`) → `teks` entri pertama yang cocok (contoh: ssh ke host aplikasi → `menjalankan perintah di <host-app>`); (1b) **[sejak 31 Okt 2026, alur P1.5]** `tim_jalankan.py --tugas <kunci> <tl> <brief>` (peluncur koordinator): pengerja = argumen
kedua sesudah `--tugas` (harus id hadir di `agen`); `<tl>` ∈ golongan TL efektif (§3.0) → `memanggil TL <Nama>`, selain itu
`memanggil <Nama>`; (2) `\bhermes\b.*?\s-p\s+(<id TL>)\b`
→ `memanggil TL <Nama>`; (3) sama untuk id anggota non-TL (§3.0) → `memanggil <Nama>`; (4) RouterOS (di tim sumber ini juga entri `kategori_perintah`): `/ip␠`, `/interface`, `/routing`,
`/system` yang didahului awal teks/spasi/kutip/`;`/`(` **[lokal: agar `/etc/systemd/system` tidak terhitung]**, atau
kata `R1` (huruf besar), `mikrotik`/`routeros` (tanpa beda huruf) → `mengakses R1`; (5) selain itu `menjalankan perintah`.
Tool lain: read_file, search_files → `membaca berkas`; write_file, patch → `menulis berkas`;
`<tool.awalan_bank_dokumen>cari|baca|status` → `membaca bank dokumen`; `tool.catat_progres` → `mencatat kemajuan`;
`<tool.awalan_bank_dokumen>setor|terbitkan|hapus` → `mengelola bank dokumen` (awalan dan nama tool dari `conf/tim.json`, boleh `null`); delegate_task → `membagi tugas ke worker`;
process_manage → `menunggu proses`; web_search, web_extract, browser_exec → `mencari di web`; clarify → Koordinator
`meminta keputusan <nama R>`, agent lain `meminta keputusan`; skill_view, skills_list → `membaca skill`; skill_manage →
`memperbarui skill`; vision_analyze → `memeriksa gambar`; memory, `mnemosyne_*` → `mencatat memori`; cronjob_manage →
`mengatur jadwal`; baris `type: msg` → `membaca pesan`; lainnya → `bekerja`.

### 3.3 Status agent (ADR-003 butir 3)
- Semua agen selain `<koordinator>` (TL dan anggota non-TL, §3.0): `jalan` bila ada proses CLI hermes `-p <id>`; else `menunggu` bila
  memegang ≥ 1 lock sah (§3.4, hanya TL); else `bebas`. **Sejak 31 Okt 2026:** agen tim yang punya misi pengerja `jalan`
  (`docs/misi.md`) ikut dihitung sebagai `jalan`; misi `menunggu` ikut dihitung sebagai `menunggu` (prioritas: `jalan` dari proses
  atau misi › `menunggu` dari lock atau misi › `bebas`).
- `<koordinator>`: `menunggu` bila baris Koordinator terakhir (urutan berkas) = tool `clarify` dan umurnya < 30 menit; else `jalan` bila
  baris Koordinator terakhir berumur < 2 menit, ada proses anggota non-TL, atau ada card permintaan `jalan` (§7) sementara status
  sebelumnya `bebas`; else `bebas`. Umur negatif dianggap 0.
- Proses CLI hermes = salah satu dari 4 argv pertama ber-basename `hermes` atau memuat `hermes_cli.main`; profil = nilai
  sesudah argumen `-p` (sama dengan `tl_kunci.py`). Mulai proses = `btime` (`<proc>/stat`) + field 22 `<proc>/<pid>/stat`
  / `SC_CLK_TCK` (dibulatkan ke bawah, detik). argv hanya dipakai untuk profil dan header `-z`.

### 3.4 Tugas aktif
(a) **TL = lock.** `sumber.lock`/`<slug>.lock` (nama lock cocok `pola.lock_nama`; `pola.lock_pemisah_subtugas` memotong akhiran subtugas untuk mendapat slug project), berisi `tl=` ∈ TL (§3.0);
lock lain (tl=`<cto>`, tanpa tl, slug tidak sah, tak bisa dibaca) diabaikan **[lokal: lock `<cto>` diabaikan; tugas CTO dari
proses]**. `id` `lock-<nama lock>` (nama lock penuh, termasuk akhiran `--<subtugas>` bila ada; `generator.py:717`); `project` tetap slug; `mulai` = `mulai=` (ISO; tak terbaca → null); `status` `jalan` bila TL punya proses, else
`menunggu`. Brief = nilai `brief=` berawalan `sumber.workspace_kontainer` diganti `sumber.workspace`; ditolak bila tidak berawalan itu, bila
realpath di luar realpath `sumber.brief`, atau bukan berkas biasa. Brief ditolak/tidak ada → judul
`Pekerjaan <project_nama>`, pemberi null.
(b) **anggota non-TL = proses** (profil `-p` pertama yang anggota non-TL). Header `-z` (§3.5) dibandingkan dengan header setiap berkas `*.md` di `sumber.brief` (berkas biasa,
realpath di dalam direktori brief). Tepat 1 cocok → judul + pemberi dari berkas itu; 0 atau > 1 → judul null, pemberi null.
`id` `proses-<pid>`; project null; `mulai` = mulai proses; `status` `jalan`.
(c) **Koordinator = per pengirim R** yang punya baris Koordinator berumur < 10 menit, ATAU R ∈ {`<pemilik>`, `<pemberi-1>`, `<pemberi-2>`} dan ada tugas
(b) ber-`pemberi_id` R. `id` `<koordinator>-<pemberi_id>` (R tak dikenal: `<koordinator>-x` + 8 hex awal sha256 nama tampilan);
judul `Permintaan lewat Telegram` (teks tetap di kode; belum dikonfigurasi); project null; `pemberi` = nama tampilan R; `mulai` = baris pertama rangkaian terakhir
R (jeda > 10 menit memutus rangkaian), null bila R tidak punya baris **[lokal]**; `langkah_terakhir` = kategori baris
terakhir R; `status` `menunggu` bila status Koordinator `menunggu` dan baris Koordinator terakhir milik R, else `jalan`.
**Pemilik** tugas = `pemberi_id`, atau `<pemilik>` bila null (fail-closed bagi Pemberi-1/Pemberi-2).
**Langkah terakhir** tugas (a)/(b) = kategori baris terakhir agent + ` · <project_nama>` bila tugas punya project;
`langkah_waktu` = ts baris itu; null bila agent belum punya baris. **Urutan**: `menunggu` dulu, lalu `jalan`; dalam
kelompok `mulai` naik (null terakhir), lalu `id`.

### 3.5 Header brief dan judul (ADR-003 butir 4–5)
Header = baris 1 s.d. baris pertama yang cocok `^\W*Peminta\b`, maksimal 10 baris pertama (tanpa baris Peminta = 10 baris
pertama); `\r` di akhir baris dibuang. Dari berkas hanya 10 baris pertama yang dibaca. Header kosong tidak pernah cocok.
Pemberi = satu-satunya dari `Pemilik`, `Pemberi-1`, `Pemberi-2` yang muncul di baris Peminta; 0 atau ≥ 2 nama / tanpa
baris → null. Judul = baris 1 tanpa `# ` (bukan H1 → null), dipecah ` — `; bagian pertama yang diawali `Brief` dibuang;
tiap bagian lain: buang awalan tanggal `YYYY-MM-DD`, dan untuk tugas TL buang awalan slug lock; bagian yang tersisa
berbentuk `( … )` dilepas kurungnya; bagian kosong dibuang; sisa digabung ` — `, dipotong 200 karakter **[lokal]**.
Kosong → null (TL: `Pekerjaan <project_nama>`). Contoh: `# Brief TL — proyek-a (FASE B: eksekusi) — 2026-10-16` →
`FASE B: eksekusi`.

### 3.6 Riwayat hari ini (tabel K2)
| sumber | teks | pemilik |
|---|---|---|
| `msg` Koordinator dari R | `<R> mengirim pesan ke Koordinator` (≤ 1 per R per 5 menit) | R |
| `clarify` Koordinator | `Koordinator meminta keputusan <R>` | R |
| terminal/execute_code Koordinator berkategori `memanggil <nama anggota non-TL>` (sejak 31 Okt 2026 juga `memanggil TL <nama>` dari `tim_jalankan.py --tugas`, §3.2 (1b)) | `Koordinator memanggil <nama>` | R |
| baris pertama `(profile, sid)` baru, kecuali baris `msg` ber-`sub: true` (boolean) = sesi subagent: sid dicatat dikenal tanpa peristiwa | `<Agent> mulai bekerja[ · <project_nama>]` | pemilik tugas agent |
| lock sah ber-`mulai=` hari ini | `<TL> mulai <project_nama>` (waktu = `mulai`) | pemilik lock |
| lock hilang / berganti `tl`/`mulai` (siklus ke-2 dst.) | `<TL> selesai <project_nama>` (waktu = siklus) | pemilik lock (cache) |
| `catat_progres` | `<Agent> mencatat kemajuan[ · <project_nama>]` | pemilik tugas agent |
| terminal/execute_code CTO berkategori `memanggil TL <X>` | `<nama CTO> memanggil <nama X>` | pemilik tugas CTO, else pemilik lock X (dari id) |
| `setor` | `<Agent> menyetor dokumen ke bank dokumen` | pemilik tugas agent |
| **[P1.5]** riwayat lock permanen `locks/.tim_kunci.riwayat.jsonl`, hanya perintah `kunci` / `selesai` / `lepas` / `alihkan` hari ini, `tl` harus ada di `agen` | `<TL> mulai <proyek>` · `<TL> selesai <proyek>` · `<Koordinator> melepas <proyek>` · `<proyek> dialihkan ke <TL>` | pemilik tim (`pemilik`) |
| **[P1.5]** `blok` di log guard (`sumber.guard`, hanya keputusan `blok`) | `<Agen> diblok <nama berkas guard>` + ` (<kategori>)` bila kategori aman (`[A-Za-z0-9_-]{1,30}`; argumen, alasan, hash, sid tidak dibaca); peristiwa sama (pelaku + teks) dalam 5 menit hanya satu | pemilik misi agen itu yang aktif **pada waktu peristiwa** (`mulai ≤ waktu ≤ selesai/sekarang`) bila tunggal, selain itu pemilik tim |
| **[P1.5]** verdict QC yang tertaut ke misi (§misi.md `qc`) | `QC: <hasil> <T-nnn>` (hasil = teks verdict, huruf kecil, ≤ 30 karakter) | pemilik misi |

Peristiwa lock dari riwayat permanen dibuang bila pelaku dan teksnya sama dengan peristiwa lock dari log lock dalam ±30 menit (tanpa
duplikat). Riwayat permanen dibaca inkremental (offset); berkas yang di-reset/diganti inode dibaca dari awal.
`pelaku` = `<koordinator>` untuk baris Koordinator (termasuk pesan R), id agent untuk baris tim, TL untuk peristiwa lock. Baris Koordinator
untuk catat_progres/setor → `Koordinator …`, pemilik R. **Pemilik tugas agent**: hanya pada mode *live* (baris dibaca pada
siklus ke-2 dst. sesudah log terbaca dari awal) dan bila semua tugas (a)/(b) agent itu punya pemilik yang sama; akhiran
` · <project_nama>` hanya bila agent punya tepat 1 tugas dan tugas itu ber-project. Selain itu (backfill, tanpa tugas,
pemilik campur) = `<pemilik>` tanpa akhiran. `CTO memanggil <X>`: bila pemilik tugas CTO tidak tunggal dan X memegang
tepat 1 lock → pemilik lock itu (hanya mode live); else `<pemilik>`.

**Field `sub` (U-2, 17 Okt 2026).** Ditulis hook aktivitas `hooks/team-activity.py` (dipasang di profil koordinator; U-1) pada baris `msg` dari `pre_llm_call` bila `extra.platform == "subagent"` (sesi
`delegate_task`). Penanda hanya `type` = `msg` dengan `sub` bernilai boolean `true`; `"true"`, `1`, `false`, `null`,
atau `sub` di baris `tool` diproses seperti baris tanpa `sub`. Baris ber-`sub` tetap memperbarui `terakhir_aktif` dan
langkah terakhir agent, dan peristiwa lain dari sesi subagent (`catat_progres`, `setor`) tetap muncul. Baris tanpa `sub`
(semua baris yang ditulis tanpa penanda itu) diproses seperti semula, sehingga peristiwa "mulai bekerja" palsu dari subagent
di log lama tetap terhitung. Sid kosong (baris tool dari dalam `execute_code`) tetap dihitung satu sesi per agent (di luar
U-2). Bentuk keluaran tidak berubah (`versi_skema` tetap "1"). Uji: `tests/generator/test_subagent.py`.

### 3.7 Penyaring data pribadi (Q-05 opsi 1)
Setiap string tampil (judul, nama tampilan R, `project_nama`, langkah, teks riwayat) yang memuat `@` atau ≥ 10 digit
berurutan dengan pemisah tunggal opsional spasi/titik/strip (`\d(?:[ .-]?\d){9,}`; menangkap NIP 18, NIK 16, HP) diganti
seluruhnya menjadi `(disaring)` **[lokal: pola digit + `@` dipilih karena fail-closed]**.

## 4. Galat
Sumber tak terbaca → teks galat tetap (§2) di ketiga berkas; keadaan terakhir yang diketahui tetap dipakai (termasuk
`agen` sah terakhir dan daftar profil terakhir, §3.0). Pengecualian
dalam satu siklus → berkas tidak ditulis siklus itu (web melihat data basi > 30 dtk). Log generator (stdout → journal):
hanya jumlah baris, jumlah baris dilewati, durasi, nama kelas pengecualian, dan teks galat tetap; tanpa isi sumber.

## 5. Isolasi per penonton (ADR-001 rincian 1, F-07, Q-10 opsi 1)
- `<pemilik>`: semua tugas, semua peristiwa, semua status; `terakhir_aktif` semua agent.
- `<pemberi-1>`/`<pemberi-2>` (V): `tugas_aktif` hanya pemilik V; `riwayat_hari_ini` hanya pemilik V. Agent **terlihat** bila punya ≥ 1 tugas
  pemilik V → `status` = `menunggu` bila salah satu tugas V-nya menunggu, else `jalan`. Agent lain → `bebas` bila status
  globalnya bebas, else `sibuk`; `terakhir_aktif` null.
- Agent terlihat selain Koordinator: `terakhir_aktif` dan `langkah_terakhir`/`langkah_waktu` tugasnya hanya diisi bila **semua**
  tugas agent itu milik V; bila ada tugas milik orang lain → null (fail-closed; sid ↔ proses tidak bisa dipetakan).
  Koordinator: `langkah_*` tugas R sudah per pengirim; `terakhir_aktif` = ts baris terakhir dengan R = V (null bila tidak ada).
- Tidak ada hitungan/judul/project/pemberi milik orang lain di berkas V (Q-11). `orang` tetap tiga.

## 6. Antarmuka generator
`python3 script/generator.py [--tim P] [--activity P] [--workspace D] [--proc D] [--proyek P] [--profil D] [--keluaran D] [--nomor P] [--interval 3]
[--sekali [--sekarang ISO]]`. Opsi `--activity --workspace --profil --proc` menimpa nilai config (CLI menang atas env `AD_TIM`/berkas); `--agen` dihapus (isi pindah ke `agen` di `conf/tim.json`).
Tanpa `--sekali`: loop tiap `--interval` dtk (bawaan 3) sampai SIGTERM/SIGINT (keluar 0). API Python: lihat `script/generator.py` (`generator.main(argv)` mengembalikan kode keluar).

## 7. Tambahan misi "Kantor Agen" (sejak 24 Okt 2026; bentuk skema "1" di atas tetap)
Field `ringkasan`, `misi`, `agen[].ruang`/`keadaan`/`misi_aktif`, `riwayat_hari_ini[].misi`, baris riwayat K3, galat
`Nomor misi tidak terbaca`/`Data sesi tidak terbaca`, argumen `--nomor` (registri nomor misi, bawaan `storage/misi/nomor.json`),
sumber state.db/config.yaml profil, dan revisi judul §3.5 (bagian `Brief …:`, juga `tugas_aktif[].judul`): lihat `docs/misi.md`.

## 8. Tambahan alur tim "P1.5" (31 Okt 2026; bentuk skema "1" tetap, `versi_skema` tetap `"1"`)
Koordinator memanggil pengerja langsung lewat `tim_jalankan.py --tugas`; tidak ada CTO di jalur itu. Aturan lengkap: `docs/misi.md`.
- **`misi[]` field baru** (aditif; UI lama mengabaikannya): `jenis` = `"pengerja"` (misi brief) atau `"permintaan"` (card
  permintaan koordinator); `anak` = id misi yang didelegasikan (urut nomor; `[]` untuk pengerja); `jalan` = `null` atau
  `{"status", "rc", "durasi_detik", "laporan"}` (status run `berjalan`/`selesai`/`gagal`/`timeout`/`dihentikan`; `laporan` = berkas
  laporan peluncur ada dan > 0 byte, isinya tidak dibaca); `qc` = `null` atau `{"hasil", "waktu"}` (verdict QC yang tertaut); `aktivitas` = `[{"waktu","tool","teks"}]` maks 50 baris tool terakhir, `teks` = ±100 karakter pertama `detail` yang disaring (misi.md).
- **`misi[].alasan`** kosakata (sebelumnya `misi-lain`/`review`/`gantung`): `anak` (card `menunggu` karena misi anak aktif);
  `gagal`/`timeout`/`dihentikan` (`berakhir`, dari status run); `null` selain itu. `induk_misi` pengerja kini juga terisi
  dari card koordinator yang meluncurkannya bila tidak ada proses induk.
- **`misi[].status`** card permintaan: `jalan`, `menunggu`, `selesai`, `berakhir` (aturan di `docs/misi.md`, bagian card).
- **`riwayat_hari_ini[].teks`** baru: lihat §3.6 (baris `[P1.5]`: lock permanen, `diblok`, `QC:`, `memanggil TL`).
- **`langkah[].label`** baru dari entri handoff: `Keputusan`, `Sebagian`, `Koreksi` (ditambah ke label §misi.md B7).
- **Galat baru** (daftar lengkap di §2): `Handoff tim tidak terbaca`, `Riwayat lock tidak terbaca`, `Verdict QC tidak terbaca`,
  `Log guard tidak terbaca`. Setiap galat sumber hanya dicatat sebagai teks tetap; isi sumber tidak pernah ikut ke log generator.
- **Config** baru (`docs/config.md`): `tl`, `sembunyikan`, `sumber.verdict`, `sumber.guard`; `cto` opsional; `sumber.handoff` kini dibaca.
- **Hook**: field `blocked` dihapus dari baris log (Hermes tidak memberi keputusan blok ke hook); sumber blok = log guard (`sumber.guard`).
