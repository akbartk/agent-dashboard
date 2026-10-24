# Requirement agent-dashboard

Status dokumen: **versi 7** (versi 1–3 = draf fase 1) · dokumen hidup tim sumber, disamarkan untuk project ini (25 Okt 2026) · penyusun: TL tim sumber · disetujui sebagai dokumen utuh: **belum**; keputusan per butir ada di bagian 3 (K-xx) dan bagian 8 (Q-xx). Ringkasan riwayat revisi versi 2–7 ada di bagian 1. <!-- tinjau: rujukan ke arsip tim sumber (path cadangan, sha256 cadangan, jam percakapan, nama file brief) tidak disalin; riwayat revisi diringkas, bukan dihapus -->

> Catatan project ini: dokumen ini adalah requirement milik tim sumber (keputusan K-xx diambil Pemilik tim sumber untuk instalasi sumber). Nilai pemasangan di host ini (bind, uid, path sumber data, akun) ditetapkan di `docs/config.md` dan `docs/pasang-g7.md`; bila berbeda dengan K-03 atau K-09 di sini, nilai config itu yang berlaku untuk pemasangan ini dan perbedaannya perlu keputusan Pemilik.

Penanda: **K-xx** = keputusan final Pemilik, bunyi dipertahankan (bagian 3). **F-xx** = fungsional (bagian 4). **N-xx** = non-fungsional (bagian 5). **usulan** / "usulan CTO, belum diputuskan Pemilik" = bukan keputusan, belum mengikat. Semua nama dan angka contoh adalah **DATA CONTOH (FIKTIF)**; nama orang hanya nama peran tim. Sejak versi 4, F-xx, N-xx, dan butir bagian 6 yang merujuk Q-xx yang sudah **final** (bagian 8) mengikuti status Q-xx itu, walaupun kolom sumbernya masih tertulis "usulan CTO, belum diputuskan"; kolom itu tidak diedit satu per satu.

Fakta di dokumen ini berasal dari brief TL dan brief koreksi tim sumber, data contoh fiktif, kontrak v1, brief mockup v2, satu catatan risiko Tailscale dari skill server tim sumber, dan hasil `stat` path sumber generator (bagian 7a; diukur tim sumber 16 Okt 2026 14.10 WIB, isi berkas tidak dibaca); sumber-sumber itu tidak disalin ke project ini. Arah arsitektur mengacu pada **ADR-001** dan **ADR-002** CTO (milik tim sumber, tidak disalin). ADR-001: Diterima untuk inti = keputusan Pemilik, butir TERBUKA belum diputuskan, **sebagian digantikan ADR-002** (lokasi generator, lokasi ringkasan, mount). ADR-002: Diterima = keputusan Pemilik ±13.3x; rinciannya usulan CTO. Bila berbeda, ADR yang menjadi acuan arsitektur. Yang tidak ditemukan di sana menjadi pertanyaan terbuka (bagian 8), bukan ditebak.

## 1. Ringkasan, tujuan, dan status dokumen

**Ringkasan.** agent-dashboard adalah satu halaman web (semua perangkat) yang menampilkan hirarki tim agent, status tiap agent, tugas aktif beserta pemberi order, dan riwayat ringkas hari ini, termasuk aktivitas Koordinator sendiri. Tiga akun (Pemilik, Pemberi-1, Pemberi-2) masuk lewat login; Pemilik melihat semuanya, Pemberi-1 dan Pemberi-2 hanya detail order miliknya. Data diperbarui tanpa reload lewat Server-Sent Events (SSE).

**Tujuan** (brief): "Satu halaman (semua device) yang menampilkan status + aktivitas semua agent, hirarki, dan pemberi order — fase 1 hanya mockup statis untuk disetujui Pemilik, plus requirement tertulis." Permintaan asal: Pemilik lewat Koordinator, 16 Okt 2026 sekitar 12.58 WIB, diteruskan CTO ke TL.

**Status:** **versi 7** (versi 1–3 = draf fase 1) · penyusun TL tim sumber · disetujui sebagai dokumen utuh: belum. Bagian 8: Q-01 s.d. Q-07, Q-09 s.d. Q-18, Q-21, dan Q-22 **final**; Q-08 digantikan ACC v3 Pemilik (17 Okt 2026 18.02); Q-20 selesai (K-09); Q-19 masih terbuka.

**Riwayat revisi** (diringkas dari "Alasan versi 2–7" dokumen sumber):

- **Versi 2** (keputusan Pemilik 16 Okt 2026 ±13.3x, K-09): generator pindah ke host (service systemd user, skrip di `./script/`), ringkasan ditulis ke `./storage/ringkasan/`, compose tanpa mount di luar folder project. Bagian yang diubah: kepala, 1, 2, 3 (catatan di K-08, K-09 baru), F-19, 6 (butir 3 dan 6, STRIDE), 7 (gambaran dan 7a), 8 (Q-16, Q-20, Q-21 baru), Lampiran A, 10. Bunyi K-01 sampai K-08 tidak diubah.
- **Versi 3** (mockup v2): Pemilik menilai mockup v1 "masih ada AI SLOP" (16 Okt 2026 ±13.45). Koordinator menulis 11 temuan dari tangkapan layar, CTO menetapkan keputusan desain D1–D8, mockup dibuat ulang menjadi dua berkas (tampilan pemilik dan tampilan terbatas). Bagian tampilan diselaraskan: kepala, 1, 2, F-01, F-02, F-18, "Pedoman tampilan v2", N-06, Q-17, Q-21 (butir c dan g), Q-22 baru, Lampiran A, 10. Bagian arsitektur tidak diubah.
- **Versi 4** (jawaban Pemilik 16 Okt 2026 ±18.25–18.27 atas pertanyaan review fase 2): **Q1 (b)** HTTP polos di LAN + Tailscale, TLS tidak dipasang (Pemilik sempat memilih (a) TLS self-signed lalu meralat ke (b); = Q-06 = ADR-001 Q1 = ADR-003 butir 2); **Q2 (b)** generator tetap service systemd user, tidak dipindah ke unit sistem; **Q3 (a)** semua keputusan sementara CTO atas Q-01 s.d. Q-22 (ADR-003 butir 8) disetujui. HTTP polos dicatat sebagai keputusan sadar dengan risiko yang diterima, bukan *technical debt*. Q-21 dinyatakan final lewat rentang Q3 (a) (tafsir CTO); Q-19 tetap terbuka. Bagian yang diubah: kepala, 1, 6 (STRIDE Spoofing, Tampering, Elevation of privilege), 7a (paragraf "Unit systemd"), 8.
- **Versi 5** (ACC tampilan v3, Pemilik 17 Okt 2026 18.02): tema terang + gelap (tema gelap atas permintaan Pemilik: "jangan ada warna yang saru"); pertanyaan V3-P2 dijawab ya (17 Okt 2026 20.55), menggantikan Q-08 dan pedoman tampilan v2 tentang tema dan jarak. Nilai warna dan jarak diambil dari berkas live `apps/web/app.css`, `apps/web/app.js`, dan uji kontras tim sumber. Bunyi K-05 tidak diubah; hubungan K-05 dengan ACC v3 (tema gelap, jarak di luar kelipatan 8) ditanyakan sebagai **U2-P1** dan belum diputuskan. Bagian yang diubah: kepala, 1, 4 (F-18; pedoman butir 1, 9, 11), 8 (Q-08).
- **Versi 6** (permintaan Pemilik 22 Okt 2026): daftar agen ditemukan otomatis, yaitu koordinator (akar) ditambah setiap folder profil Hermes yang memuat `profile.yaml`; nama tampilan, peran singkat, dan induk dibaca dari config agen (di project ini: kunci `agen` di `conf/tim.json`); TL = agen yang induknya CTO. Profil tanpa entri tetap tampil di bawah koordinator (nama = id berhuruf awal kapital, peran = `description` profil) dan dicatat di field `peringatan` (`docs/skema-ringkasan.md`). Bagian yang diubah: kepala, 1, 4 (F-01). Bunyi K-06 tidak diubah.
- **Versi 7** (izin dokumen Pemilik 24 Okt 2026): font tampilan Inter diganti **Public Sans self-host** (SIL OFL 1.1) sejak tampilan Kantor Agen: `apps/web/font/PublicSans-{Regular,Medium,SemiBold,Bold}.woff2` + `PublicSans-OFL.txt`, `@font-face` di `apps/web/app.css` baris 4–7. Bobot: baris itu mendeklarasikan 4 bobot (400/500/600/700), aturan CSS hanya memakai 400/600/700 dan uji peramban integrasi tim sumber mencatat tiga bobot itu termuat; karena itu pedoman butir 11 menjadi Public Sans 400/600/700 dan angka N-03 (≤ 3 bobot) tetap. Berkas `PublicSans-Medium.woff2` (500) ikut di image tetapi tidak dimuat = debt **KAD-D1** (pemilik: TL web; dibayar pada perubahan kode web berikutnya, butuh izin kode). Yang sengaja tidak diubah: bunyi K-05; bagian 2 dan 10 (sejarah mockup fase 1, termasuk font Inter 4.1). Bagian yang diubah: kepala, 1, 3 (catatan sesudah K-05), 4 (F-18 dan pedoman butir 11), 5 (N-03).

## 2. Batas Fase 1 vs Fase 2

**Fase 1** hanya terdiri dari:

- Folder `<AKAR>` struktur standar: `apps/ conf/ docs/ docker/ db/{data,migrations,seeds} logs/ script/ tmp/test storage/ tests/ .env .env.example .gitignore`. `.env` kosong/komentar mode 600; `.env.example` tanpa nilai rahasia; `.gitignore` memuat minimal `.env`, `db/data/`, `logs/`, `tmp/`, `storage/`.
- `docs/requirement.md` (dokumen ini; ditempatkan di `docs/` oleh TL).
- `docs/mockup/index.html` (penonton Pemilik, semua detail) dan `docs/mockup/terbatas.html` (penonton Pemberi-1, aturan F-07): dua berkas HTML statis tanpa JS, CSS inline yang sama, data fiktif (keterangan fiktif hanya di komentar HTML), koneksi tampil "Tersambung". Font Inter 4.1 (rilis resmi, SIL OFL 1.1), 2 bobot woff2 (400 dan 600) disematkan sebagai data: URI; versi, sha256, dan teks lisensi lengkap ada di komentar CSS tiap berkas. **Berkas mockup, sumber rakitnya, salinan, dan PNG tidak disalin ke project ini** (riwayat desain tim sumber; `docs/mockup/` sengaja tidak ada).
- PNG mockup v2 di arsip tim sumber: tampilan pemilik dan tampilan terbatas, desktop (viewport 1366×768, full page, DSF 1) dan HP (viewport 390×844, full page, DSF 2), ditangkap dari berkas hasil rakit dengan skrip tangkap layar tim sumber (tidak disalin).
- Mockup v1 (satu HTML, 3 PNG, sumber rakit, KONTRAK v1, dan skrip cek beserta keluarannya) diarsipkan di tim sumber dan tidak berlaku untuk mockup v2 (tidak disalin).
- Skrip dan keluaran uji Fase 1 (7b, bagian 10) ada di arsip tim sumber dan tidak disalin.

**BELUM di Fase 1:** compose, Dockerfile, container, image, port/listener, generator (skrip maupun unit systemd), cron, login, kode Go; `git init` tidak dilakukan; state Hermes sumber, container koordinator, `/etc/systemd/system`, dan aplikasi lain tidak disentuh.

**Fase 2** (implementasi K-02 sampai K-09) menunggu persetujuan mockup oleh Pemilik. Dokumen ini tidak memberi izin apa pun untuk Fase 2; bagian 8 memuat hal yang harus diputuskan lebih dulu.

**Catatan Fase 2 (16 Okt 2026, TL):** Fase 2 dibangun atas brief CTO 16 Okt 2026 (Pemilik menyetujui mockup dan memilih "perbaiki butir 1–5 lalu bangun"), mengikuti ADR-003 (milik tim sumber, tidak disalin) untuk semua butir bagian 8 yang diputuskan CTO. Isi bagian 3 (K-01 s.d. K-09) tidak berubah. Kontrak data: `docs/skema-ringkasan.md` (versi skema "1", turunan Lampiran A); operasi, akun, dan rollback: `docs/operasi.md`.

## 3. Keputusan Pemilik (final)

Disalin dari bagian "Keputusan Pemilik yang sudah final" pada brief TL 16 Okt 2026. Bunyi dipertahankan; hanya nomor K-xx dan penanda yang ditambahkan, dan baris yang terputus di brief digabung per butir. K-09 (versi 2) disalin persis dari brief koreksi 1 (= entri handoff Koordinator 13:33:16); bunyi K-01 sampai K-08 tidak diubah, K-08 hanya diberi catatan.

**K-01** — Keputusan Pemilik 16 Okt 2026:

> Folder `<AKAR>` (baru, struktur standar; compose dengan bind mount relatif, tanpa named volume). Aplikasi lama dan container koordinator tim sumber tidak disentuh.

**K-02** — Keputusan Pemilik 16 Okt 2026:

> Compose baru + 1 container web: Go 1.25 stdlib (+ `x/crypto/bcrypt`), HTML + CSS biasa + JS kecil, tanpa framework berat; image kecil (distroless/scratch), `read_only`, `cap_drop ALL`, mem dibatasi.

**K-03** — Keputusan Pemilik 16 Okt 2026:

> Port 24130, bind hanya `<ip-bind-1>:24130` dan `<ip-bind-2>:24130` (Koordinator cek 12.50: tidak dipakai; cek ulang sebelum dipakai di fase 2).

Catatan project ini (bukan bagian bunyi keputusan): alamat bind K-03 adalah alamat host tim sumber. Di project ini bind dan port dibaca dari `AD_BIND` dan `AD_PORT` (`docs/config.md`); `.env.example` memuat `AD_BIND=127.0.0.1` dan `AD_PORT=24130`.

**K-04** — Keputusan Pemilik 16 Okt 2026:

> Realtime tanpa reload (wajib): Server-Sent Events, auto-reconnect, label "terakhir diperbarui".

**K-05** — Keputusan Pemilik 16 Okt 2026:

> UI: terang, bersih, simpel; font Inter self-host, skala 12/14/16/20/28, grid 8 px, lebar konten maks ±1100 px; 1 warna aksen + 3 warna status lembut (bebas / sedang jalan / menunggu keputusan); responsif (HP 1 kolom, laptop 3–4).

Catatan versi 7 (bukan bagian bunyi keputusan): font pada K-05 diganti Public Sans self-host (SIL OFL 1.1) sejak tampilan Kantor Agen 24 Okt 2026; sumber: mockup Kantor Agen Pemilik + izin dokumen Pemilik 24 Okt 2026 ±15.32 (bagian 1, Alasan versi 7). Bunyi K-05 di atas tidak diubah.

**K-06** — Keputusan Pemilik 16 Okt 2026:

> Isi: (1) hirarki Pemilik → Pemberi-1, Pemberi-2 → Koordinator → CTO → TL-1/TL-2/TL-3; Anggota-1 di bawah Koordinator — tiap kartu berstatus; (2) tugas aktif: judul, project, pemberi order, pengerja, mulai, langkah terakhir; (3) riwayat ringkas hari ini. Termasuk aktivitas Koordinator sendiri.

**K-07** — Keputusan Pemilik 16 Okt 2026:

> Login 3 akun (Pemilik, Pemberi-1, Pemberi-2), bcrypt, cookie sesi HttpOnly; akun dibuat dari host, ganti password saat login pertama (2a). Isolasi (1a): Pemilik melihat semua; Pemberi-1/Pemberi-2 hanya melihat detail order milik mereka sendiri, selain itu agent hanya tampil "sibuk/bebas" tanpa judul tugas dan tanpa nama pemberi order.

**K-08** — Keputusan Pemilik 16 Okt 2026:

> Data: generator di sisi Koordinator (skrip di state koordinator, tiap 3–5 dtk) membaca `activity.jsonl`, `tl_kunci`, brief, proses → menulis ringkasan per penonton ke folder dashboard di workspace koordinator (container web hanya mount itu, read-only). Container web tidak pernah membaca log mentah (log memuat isi chat + perintah lengkap). Detail perintah tidak ditampilkan.

Catatan versi 2: K-08 **digantikan sebagian oleh K-09 (16 Okt ±13.3x)**, yaitu lokasi generator, lokasi ringkasan, dan mount. Yang tetap berlaku dari K-08: frekuensi 3–5 dtk, sumber yang dibaca (`activity.jsonl`, `tl_kunci`, brief, proses), container web tidak pernah membaca log mentah, dan detail perintah tidak ditampilkan.

**K-09** — Keputusan Pemilik 16 Okt 2026 ±13.3x (dicatat Koordinator di handoff tim sumber, entri 13:33:16 WIB; berlaku untuk Fase 2; diteruskan CTO lewat brief koreksi 1; acuan arsitektur ADR-002):

> - Compose hanya boleh bind mount relatif ke folder project, tanpa named volume, TANPA pengecualian. Mount folder dashboard di workspace koordinator dibatalkan.
> - Ringkasan per penonton ditulis ke ./storage/ringkasan/ (bukan docs/, karena docs = dokumentasi statis ber-git). Container web: ./storage/ringkasan:/srv/ringkasan:ro.
> - Generator pindah ke HOST: systemd service user `<user-app>`, skrip di ./script/ project, baca log aktivitas, lock tl_kunci, dan proses agent secara read-only, tulis ke ./storage/ringkasan. Container `<koordinator>` tidak berubah.

Catatan: rujukan "(1a)" dan "(2a)" di K-07 berasal dari penomoran brief Koordinator yang tidak ada di berkas yang dibaca penyusun (Q-19).

## 4. Kebutuhan fungsional

"Sumber" menyebut butir keputusan (K-xx) atau menandai usulan. Semua F-xx berlaku untuk Fase 2; Fase 1 hanya memperagakannya di mockup.

| ID | Kebutuhan | Sumber |
|---|---|---|
| F-01 | Hirarki sebagai pohon berindentasi dengan garis penghubung tipis yang menghubungkan induk dan anak (tanpa kartu, tanpa label tingkat, tanpa teks "melapor ke"): Pemilik → Pemberi-1, Pemberi-2 (satu baris) → Koordinator → agen lain menurut field `induk`. Daftar agen tidak di-hardcode: Koordinator (akar) + setiap profil Hermes yang memuat `profile.yaml`; nama, peran singkat, dan induk dari kunci `agen` di `conf/tim.json` (lihat Riwayat revisi, versi 6). Contoh: CTO → TL-1/TL-2/TL-3; Anggota-1 dan Anggota-2 (riset, QA/QC) di bawah Koordinator. | K-06 butir (1); bentuk pohon: Pedoman tampilan v2; daftar agen: permintaan Pemilik 22 Okt 2026 |
| F-02 | Setiap baris agen di pohon berstatus singkat: titik 8 px + teks (bebas, sedang jalan, menunggu keputusan; "sibuk" hanya di tampilan terbatas), tanpa jam dan judul tugas (detail tugas hanya di Tugas aktif). Di mockup baris orang tidak berstatus; K-06 menulis "tiap kartu": Q-12. | K-06 butir (1); sebagian belum jelas (Q-12); bentuk: Pedoman tampilan v2 |
| F-03 | Tugas aktif menampilkan 6 field: judul, project, pemberi order, pengerja, mulai, langkah terakhir. | K-06 butir (2) |
| F-04 | Riwayat ringkas hari ini (jam, pelaku, tugas, kalimat ringkas), termasuk kejadian oleh Koordinator. Arti "hari ini": Q-09. | K-06 butir (3) |
| F-05 | Aktivitas Koordinator sendiri tampil: kartu agen berstatus, pengerja tugas aktif (T-05 pada data contoh), pelaku di riwayat. | K-06 ("Termasuk aktivitas Koordinator sendiri") |
| F-06 | Tiga status lembut (bebas, sedang jalan, menunggu keputusan), satu warna masing-masing, selalu disertai label teks. | Tiga status dan warna: K-05. Label teks: usulan CTO, belum diputuskan Pemilik (N-07) |
| F-07 | Isolasi per penonton: Pemilik melihat semua; Pemberi-1 dan Pemberi-2 hanya detail order milik sendiri; selain itu agent hanya "sibuk" atau "bebas" tanpa judul tugas dan tanpa nama pemberi order. Tampilan Pemberi-2 memakai aturan yang sama; mockup hanya memperagakan Pemberi-1. | K-07 |
| F-08 | Tampilan terbatas: riwayat hanya order milik penonton; tidak ada hitungan atau ringkasan order orang lain. | usulan CTO, belum diputuskan Pemilik (brief T3 butir b; Q-11) |
| F-09 | Isolasi ditegakkan di sumber data (satu berkas ringkasan per penonton); server mengirim hanya berkas milik penonton yang login, dengan penonton diambil dari sesi. Fail-closed (bagian 6). | usulan CTO, belum diputuskan Pemilik |
| F-10 | Realtime tanpa reload memakai Server-Sent Events (SSE). | K-04 |
| F-11 | Auto-reconnect saat SSE putus (rincian backoff dan kirim ulang data penuh: N-02). | K-04; angka: usulan CTO |
| F-12 | Label "terakhir diperbarui" selalu terlihat, ditambah indikator koneksi (tersambung, terputus/menyambung ulang) seperti di mockup. | Label: K-04. Indikator: usulan CTO, belum diputuskan Pemilik (N-02) |
| F-13 | Login 3 akun (Pemilik, Pemberi-1, Pemberi-2); password disimpan sebagai hash bcrypt. | K-07 |
| F-14 | Sesi dibawa cookie HttpOnly. | K-07 |
| F-15 | Ganti password wajib pada login pertama tiap akun. | K-07 |
| F-16 | Akun dibuat dari host, bukan lewat halaman web; prosedur dan reset: Q-15. | K-07; prosedur belum diputuskan |
| F-17 | Responsif: HP 1 kolom, laptop 3 sampai 4 kolom. | K-05 |
| F-18 | Tampilan terang, bersih, simpel; Public Sans self-host (SIL OFL 1.1; sejak tampilan Kantor Agen 24 Okt 2026, semula Inter); skala font 12/14/16/20/28; grid 8 px; lebar konten maks sekitar 1100 px; satu aksen dan tiga warna status lembut. Sejak ACC v3: tema terang + gelap; tema awal mengikuti `prefers-color-scheme` perangkat; tombol teks "Tema gelap"/"Tema terang" di kepala halaman utama mengganti tema dan pilihannya tersimpan di `localStorage` peramban; penentu tema = skrip `/aset/tema.js`, dimuat sinkron di `<head>` ketiga halaman (CSP `script-src 'self'` melarang skrip inline). Rincian tampilan: "Pedoman tampilan v2" di bawah tabel (diubah ACC v3 untuk tema dan jarak). | K-05; pedoman: kritik Koordinator 16 Okt ±13.45 + D1–D8 (bukan K-xx); tema terang/gelap: ACC v3 Pemilik 17 Okt 2026 18.02 (catatan v3 tim sumber, tidak disalin); font Public Sans: mockup Kantor Agen Pemilik + izin dokumen 24 Okt 2026 ±15.32; hubungan dengan K-05: pertanyaan U2-P1 |
| F-19 | Generator di host (service systemd user `<user-app>`, skrip di `./script/`) membaca `activity.jsonl`, `tl_kunci`, brief, dan proses agent secara read-only tiap 3 sampai 5 detik, lalu menulis ringkasan per penonton ke `./storage/ringkasan/`; container web hanya mount `./storage/ringkasan:/srv/ringkasan:ro`. Tidak ada mount di luar folder project (bagian 7a). | K-08 (sumber, frekuensi); K-09 (lokasi generator, ringkasan, mount) |
| F-20 | Container web tidak pernah membaca log mentah; detail perintah tidak ditampilkan. | K-08 |

**Pedoman tampilan v2** (sumber: kritik Koordinator atas keluhan Pemilik 16 Okt 2026 ±13.45 ("design mockup nya masih ada AI SLOP"; 11 temuan dari tangkapan layar mockup v1), dirinci keputusan desain CTO D1–D8 di brief mockup v2. Bukan K-xx; dapat dibatalkan). Berlaku untuk mockup v2 dan Fase 2:

Diubah ACC v3 Pemilik 17 Okt 2026 18.02 (V3-P2) untuk tema, warna, dan jarak: butir 1, 9, dan 11 memuat aturan v3; teks lama butir itu disimpan sebagai `Semula: …`. Nilai diambil dari berkas live (tampilan v3, deploy 17 Okt 2026 20.24). Butir lain tidak diubah.

1. Tanpa teks meta yang menjelaskan UI ("Tampilan contoh", label data fiktif, keterangan arti penanda). Tanpa pengalih tampilan di halaman: satu berkas per penonton. Pengecualian tema (ACC v3): satu tombol teks "Tema gelap"/"Tema terang" di kepala halaman utama (`apps/web/index.html` baris 17; teks dipasang `apps/web/app.js` baris 420, pilihan disimpan baris 505); tanpa pilihan tersimpan, tema mengikuti `prefers-color-scheme` (`apps/web/tema.js` baris 5). Semula: "Tanpa teks meta yang menjelaskan UI ("Tampilan contoh", label data fiktif, keterangan arti penanda). Tanpa pengalih tampilan di halaman: satu berkas per penonton."
2. Tanpa legenda status: setiap status ditulis sebagai teks di sebelah titiknya.
3. Hirarki = pohon berindentasi dengan garis penghubung 1 px yang benar-benar menghubungkan induk dan anak; tanpa label "Tingkat" dan tanpa teks "melapor ke".
4. Tanpa pill: status dan koneksi = titik 8 px + teks biasa.
5. Tanpa kartu bertepi/berbayang dan tanpa tinggi yang dipaksa sama; isi berupa daftar/baris yang dipisah spasi, ukuran mengikuti isi.
6. Satu fakta satu tempat: pohon = nama + peran + status singkat; detail tugas hanya di Tugas aktif; riwayat tidak mengulang detail tugas (menyebut peristiwa dan nama project saja).
7. Riwayat terbaru di atas, dikelompokkan per jam, tanpa garis; satu penanda halus untuk Koordinator (nama 600).
8. Teks informasi minimal 14 px dengan kontras ≥ 4,5:1 (mockup v2: teks sekunder `#63636B` = 5,95:1 di `#FFFFFF`, dihitung).
9. Dua tema; semua warna di dua blok variabel `apps/web/app.css` (`:root` baris 5–8, `:root[data-tema="gelap"]` baris 9–12). Terang: latar `#FFFFFF`, aksen netral `#18181B`; gelap: latar `#131316`, aksen netral `#F4F4F5`. Warna hanya untuk 3 titik status (terang / gelap, baris 7 / 11): sedang jalan `#159C45` / `#34D058`, menunggu keputusan `#D06F05` / `#F5A524`, bebas `#8A8A93` / `#7AA2F7`; kontras titik ≥ 3:1 terhadap latar dan baris tersorot di kedua tema (uji kontras tim sumber → "SEMUA LULUS"; tidak disalin). Semula: "Latar putih, satu aksen netral, warna hanya untuk 3 titik status (kontras titik ≥ 3:1)."
10. Nama project tampil sebagai nama manusiawi (mis. "Proyek A", bukan slug "proyek-a"), bobot lebih ringan dari nama orang (sumber nama: Q-22).
11. Public Sans 400/600/700 benar-benar termuat (`document.fonts` berstatus loaded); ukuran 14/16/20/28 (12 tidak untuk teks informasi); jarak mengikuti mockup v3 yang di-ACC. `apps/web/app.css` live memakai margin/padding/gap 2, 3, 4, 6, 7, 8, 12, 16, 20, 24, 32, 40, 48, 64 px; yang bukan kelipatan 8: 2 (baris 73), 3 dan 7 (baris 43 dan 66, tombol saring dan baris agen berbingkai 1 px), 4 (baris 27, 65, 80, 84, 89, 109), 6 (baris 92), 12 (baris 33, 41, 88), 20 (baris 76). Nilai 4 dan 12 px sudah dipakai sejak v2. Semula: "Inter 400/600 benar-benar termuat (`document.fonts` berstatus loaded); ukuran 14/16/20/28 (12 tidak untuk teks informasi); jarak kelipatan 8." Semula (sebelum versi 7): "Inter 400/600 benar-benar termuat".

Tanpa emoji, ikon dekoratif, gradien, atau bayangan.

Batasan implementasi (bukan fungsional): folder dan struktur (K-01); stack, hardening image, batas memori (K-02); port dan alamat bind (K-03, bagian 7c).

## 5. Kebutuhan non-fungsional (NFR)

Kolom "Persyaratan" disalin persis dari bagian "Arah arsitektur dari CTO" pada brief; angka tidak diubah. Semua baris: **usulan CTO, belum diputuskan Pemilik**. "Cara uji singkat" adalah usulan penyusun untuk Fase 2.

| ID | Persyaratan | Status | Cara uji singkat |
|---|---|---|---|
| N-01 | umur data di layar ≤ 10 dtk p95 saat tersambung | usulan CTO, belum diputuskan Pemilik | Klien uji mencatat selisih jam klien dan field `dibuat_pada` tiap pembaruan selama beberapa menit; p95 ≤ 10 dtk. |
| N-02 | SSE putus → indikator "terputus" tampil ≤ 5 dtk, reconnect backoff 1→2→4… maks 30 dtk, sesudah tersambung data penuh dikirim ulang | usulan CTO, belum diputuskan Pemilik | Putuskan koneksi; ukur waktu sampai "terputus" muncul, catat jeda percobaan, cek pesan pertama setelah sambung memuat ringkasan lengkap. |
| N-03 | muatan awal HTML+CSS+JS ≤ 50 KB (gzip) di luar font, font Public Sans ≤ 3 bobot woff2 (Semula: "font Inter ≤ 3 bobot woff2") | usulan CTO, belum diputuskan Pemilik — versi 7: `apps/web/app.css` baris 4–7 mendeklarasikan 4 bobot (400/500/600/700), aturan CSS hanya memakai 400/600/700 (500 hanya di `@font-face` baris 5); uji peramban integrasi tim sumber (server uji dari image build tim sumber, bukan URL live) mencatat 3 bobot termuat (400/600/700), jadi batas bobot font N-03 terpenuhi menurut uji itu; berkas `PublicSans-Medium.woff2` ikut di image tetapi tidak dimuat = debt **KAD-D1** (pemilik: TL web; dibayar pada perubahan kode web berikutnya, butuh izin kode) | Ukur transfer terkompresi muatan awal; hitung berkas woff2 yang dimuat. |
| N-04 | container mem ≤ 64 MiB, image ≤ 20 MB, non-root, read_only, cap_drop ALL, no-new-privileges | usulan CTO, belum diputuskan Pemilik | Periksa compose dan metadata container; ukur image dan mem saat N-05. |
| N-05 | 20 klien SSE serentak | usulan CTO, belum diputuskan Pemilik | 20 koneksi SSE bersamaan beberapa menit; semua menerima pembaruan, mem di bawah batas N-04. |
| N-06 | 360–1440 px tanpa scroll horizontal; 1 kolom < 640 px (urutan Tugas aktif → Tim → Riwayat hari ini); 3 kolom berdampingan Tim, Tugas aktif, Riwayat hari ini ≥ 1024 px (memenuhi K-05 "laptop 3–4") | usulan CTO, belum diputuskan Pemilik | Peramban uji di lebar 360, 390, 640, 1024, 1280, 1440: `scrollWidth` ≤ viewport, hitung kolom. Mockup v2 dicek visual di 1366 dan 390 px (lihat Q-17). |
| N-07 | kontras teks ≥ 4,5:1 (WCAG AA), status tidak hanya warna (ada label teks), bisa dipakai keyboard | usulan CTO, belum diputuskan Pemilik | Hitung kontras dari warna terkomputasi; cek tiap status berlabel teks; lewati halaman dengan Tab, fokus terlihat. |
| N-08 | payload per penonton hanya memuat field yang boleh untuk penonton itu (diuji) | usulan CTO, belum diputuskan Pemilik | Tes otomatis tiap akun: payload HTTP dan SSE dibanding daftar field yang diizinkan; tes negatif untuk berkas rusak atau pemberi tak terbaca. |

## 6. Keamanan dan privasi

Tiap butir menyebut sumbernya; "usulan" = belum diputuskan Pemilik.

1. **Isolasi di sumber data.** Generator membuat satu berkas ringkasan per penonton; server web hanya mengirim berkas milik penonton yang login, dan penonton diambil dari sesi, bukan dari URL atau parameter. Field terlarang tidak pernah sampai ke peramban (bukan sekadar disembunyikan lewat CSS/JS). Nama berkas per ADR-001 rincian 1: `<pemilik>.json`, `<pemberi-1>.json`, `<pemberi-2>.json`. Sumber: usulan CTO, belum diputuskan Pemilik (berpijak pada K-07; ADR-001 rincian 1).
2. **Fail-closed.** Order yang pemberinya tidak terbaca (hilang, rusak, ambigu, tak cocok dengan daftar akun) pasti dianggap "bukan milikmu" bagi Pemberi-1 dan Pemberi-2: tidak masuk ringkasan mereka, agent-nya tampil "sibuk" tanpa detail. Berkas ringkasan yang rusak tidak dikirim sebagian. **Tulis atomik** (ADR-001 rincian 2): generator menulis ke berkas sementara di direktori yang sama lalu `rename`, sehingga web tidak pernah membaca JSON setengah jadi; label "terakhir diperbarui" memakai `dibuat_pada` dari generator (bukan jam server web), sehingga generator yang mati terlihat sebagai data basi. Sumber: usulan CTO, belum diputuskan Pemilik.
3. **Tanpa log mentah di container web; detail perintah tidak ditampilkan.** Log memuat isi chat dan perintah lengkap; container web hanya mount `./storage/ringkasan:/srv/ringkasan:ro`. "Langkah terakhir", "kegiatan", dan teks riwayat adalah kalimat ringkas buatan generator. Sumber: K-08; mount: K-09.
4. **Data minim.** Judul tugas bisa memuat data pribadi karena berasal dari order bebas-teks; generator menyaring sebelum menulis ringkasan (Q-05). Hanya field yang dibutuhkan tampilan yang dikirim (Lampiran A). Sumber: usulan CTO, belum diputuskan Pemilik.
5. **UU PDP.** Data yang tampil dibatasi seperlunya dan tanpa identitas pribadi (NIP, NIK, nomor HP, email, alamat, tanggal lahir). Ketentuan rinci UU PDP (dasar pemrosesan, retensi, hak subjek data) belum ditelaah penyusun dan perlu ditelaah sebelum Fase 2. Sumber: usulan.
6. **Least privilege.** Container web non-root, `read_only`, `cap_drop ALL`, `no-new-privileges`, mem dibatasi, mount hanya `./storage/ringkasan:/srv/ringkasan:ro` ditambah `./db/data` untuk akun (butir 7), tanpa mount di luar folder project, bind hanya dua alamat (7c). Generator (service systemd di host, user `<user-app>`) membaca sumber secara read-only dan hanya menulis ke `./storage/ringkasan/` dan `./logs/`. Karena `<user-app>` punya sudo + docker (terukur `id <user-app>`: grup `sudo`, `docker`), unit dikeraskan sesuai ADR-002 butir 2 (bagian 7a). `read_only`, `cap_drop ALL`, batas mem: K-02; lokasi generator dan mount: K-09; sisanya usulan CTO (N-04, ADR-002).
7. **Secret di luar kode.** `.env` mode 600 dan tidak di-commit (`.gitignore` memuat `.env`); `.env.example` tanpa nilai rahasia; hash bcrypt akun diperlakukan sebagai secret, disimpan di luar kode dan git; menurut ADR-001 rincian 4 di bind mount `./db/data` (satu-satunya mount tulis, perlu untuk ganti password saat login pertama; `db/data/` ada di `.gitignore`), sesi di memori (restart = semua login ulang) (Q-15). Sumber: kriteria T1 brief; ADR-001; sisanya usulan.

**Tabel STRIDE singkat** (semua baris usulan, belum diputuskan Pemilik):

| Kategori | Ancaman | Mitigasi (usulan) |
|---|---|---|
| Spoofing | Menyamar sebagai Pemilik, Pemberi-1, atau Pemberi-2: tebak password, curi cookie, sadap HTTP polos di LAN. | bcrypt, batas percobaan login (Q-01), ganti password login pertama (K-07), cookie HttpOnly (K-07), kedaluwarsa sesi (Q-02). Sadap HTTP polos: risiko diterima sebagai keputusan sadar Pemilik (Q-06 final, Q1 (b)): lewat Tailscale terenkripsi, lewat LAN tidak; login dan ganti password sebaiknya lewat alamat Tailscale (`docs/operasi.md`). |
| Tampering | Berkas ringkasan diubah; POST dari situs lain atas nama pengguna yang login. | Mount read-only dan `read_only` (K-02, K-09); web tanpa jalur tulis ke data; generator hanya menulis `./storage/ringkasan/`, dibatasi kode yang sudah direview, bukan oleh unit (`ProtectSystem`/`ReadWritePaths` tidak efektif di unit user, terukur Fase 2; risiko diterima lewat keputusan Pemilik Q2 (b), bagian 7a); SameSite=Strict dan cek Origin (Q-03). |
| Repudiation | Pengguna menyangkal login atau ganti password; tidak ada jejak. | Log akses minimum (waktu, akun, hasil login/ganti password; tanpa password dan tanpa isi tugas) di `logs/`; format dan retensi diputuskan di Fase 2. |
| Information disclosure | Pemberi-1 atau Pemberi-2 melihat order orang lain; log mentah bocor; judul tugas memuat data pribadi. | Isolasi di sumber dan fail-closed (butir 1, 2); tanpa log mentah (K-08); penyaringan judul (Q-05); uji payload per penonton (N-08); respons ber-login tidak di-cache bersama. |
| Denial of service | Banjir koneksi SSE atau percobaan login menghabiskan sumber daya. | Batas memori (K-02, N-04); uji 20 klien SSE (N-05); bind hanya dua alamat (K-03); batas koneksi SSE per akun dan batas percobaan login (Q-01). |
| Elevation of privilege | Memanipulasi parameter atau path untuk membaca berkas penonton lain; container dibobol untuk naik ke host; generator di host (user `<user-app>`, punya sudo + docker) disalahgunakan lewat isi berkas sumber. | Penonton ditentukan server dari sesi, nama berkas dipetakan di server tanpa input klien; non-root, `cap_drop ALL`, `no-new-privileges`, `read_only` (K-02, N-04); unit generator (unit user, ADR-003) dikeraskan dengan direktif yang terbukti efektif (`NoNewPrivileges=yes`, `RestrictAddressFamilies=none` yang menutup `/var/run/docker.sock`, `SystemCallFilter=@system-service`); `ProtectSystem`/`ReadWritePaths` tidak efektif di unit user, jadi tanpa isolasi filesystem (risiko diterima lewat keputusan Pemilik Q2 (b), bagian 7a); generator hanya mem-parse teks sumber, tidak pernah menjalankan isinya; review kode generator ketat (ADR-002). |

## 7. Arsitektur dan aturan integritas folder

**Gambaran (K-02, K-08, K-09).** Satu container web (Go 1.25 stdlib + `x/crypto/bcrypt`) menyajikan HTML + CSS + JS kecil, memeriksa login, dan mengirim ringkasan milik penonton lewat SSE. Generator berjalan di **host** sebagai service systemd user `<user-app>` (skrip di `./script/`), membaca sumber aktivitas secara read-only, dan menulis ringkasan per penonton ke `./storage/ringkasan/`; container web me-mount `./storage/ringkasan:/srv/ringkasan:ro`. Container `<koordinator>` tidak berubah. Aliran satu arah: sumber aktivitas → generator (host) → `./storage/ringkasan/` → container web (read-only) → peramban. Rincian dan perbandingan opsi: ADR-001 (A dipilih; B mount log mentah, C API ke container `<koordinator>`, D tidak membangun apa-apa) dan ADR-002 (generator di host, ringkasan di `./storage`; menggantikan sebagian ADR-001). Catatan nama (ADR-001): container `<koordinator>` sudah punya service s6 bernama `dashboard` bawaan Hermes; itu bukan aplikasi ini.

**(a) Tanpa mount di luar folder project; path di luar folder yang DIBACA generator host (K-09, ADR-002).** Compose Fase 2 hanya memakai bind mount relatif ke folder project (`./storage/ringkasan:/srv/ringkasan:ro`, `./db/data` untuk akun), tanpa named volume dan tanpa pengecualian (K-09). Generator bukan container: ia berjalan di host dan hanya **membaca** path di luar folder project (tidak me-mount, tidak menulis). Menurut aturan integritas standar aplikasi #6, path di luar folder project wajib dijelaskan di docs. Daftarnya mengikuti ADR-002 butir 1 (usulan CTO). Kolom "Terukur" berasal dari `stat` oleh TL tim sumber 16 Okt 2026 14.10 WIB di host tim sumber; isi berkas tidak dibaca. Kolom "Path (host)" memakai nama kunci `sumber.*` di `conf/tim.json`; nilai pemasangan ini ada di `docs/config.md` (bagian "Nilai pemasangan g7") dan **belum diukur** di host pemasangan ini.

| Path (host) | Dibaca untuk | Alasan berada di luar folder | Terukur |
|---|---|---|---|
| `sumber.activity` | log aktivitas (`activity.jsonl`, K-08) | ditulis hook pencatat Hermes di state koordinator; container koordinator tidak berubah (K-09) | di tim sumber: berkas biasa, owner `<uid-app>` (`<user-app>`), mode 644; folder induk mode 700 |
| `sumber.lock` | lock TL (`tl_kunci`, K-08) | lock dibuat CTO di workspace koordinator | di tim sumber: direktori, owner `<uid-app>`, mode 755 |
| `sumber.brief` | brief (judul tugas, pemberi order; Q-13) | brief ditulis di workspace koordinator | di tim sumber: direktori, owner `<uid-app>`, mode 755 |
| `sumber.proc` (bawaan `/proc`) | proses agent ("proses", K-08) | proses container koordinator terlihat dari namespace PID host (catatan skill server tim sumber) | procfs host; cara memetakan proses ke agent belum diverifikasi (Fase 2) |

Generator hanya membaca path di atas dan hanya menulis `./storage/ringkasan/` (ringkasan) serta `./logs/` (jumlah, durasi, galat; tanpa isi log mentah, ADR-002 butir 4). Path baca baru harus ditambahkan ke tabel ini lebih dulu. Di tim sumber, pemilik semua path di atas adalah uid `<uid-app>` = `<user-app>`, jadi generator sebagai `<user-app>` dapat membacanya tanpa hak tambahan; di pemasangan ini hak baca harus dicek ulang (`docs/pasang-g7.md`).

**Unit systemd (ADR-003 butir 1; keputusan Pemilik Q2 (b) 16 Okt 2026 ±18.25–18.27: tetap unit user).** Sumber unit `./conf/agent-dashboard-generator.service` (templat dengan penanda `@AKAR@`), dipasang `./script/pasang-generator.sh` ke `~/.config/systemd/user/` sebagai service systemd **user** `<user-app>` (izin Fase 2 Pemilik; linger `<user-app>` aktif). Pengerasan hanya memakai direktif yang terbukti efektif di user manager host tim sumber (terukur Fase 2 di sana; tabel di `docs/operasi.md`; <!-- tinjau: belum diukur di host pemasangan ini -->): `NoNewPrivileges=yes`, `RestrictNamespaces=yes`, `RestrictAddressFamilies=none` (tanpa socket; menutup `/var/run/docker.sock`), `SystemCallFilter=@system-service`, `SystemCallArchitectures=native`, `MemoryDenyWriteExecute=yes`, `LockPersonality=yes`, `MemoryMax=64M`, `CPUQuota=20%`, `TasksMax=16`, `UMask=0027`, `Restart=always`. `ProtectSystem`, `ProtectHome`, `ReadWritePaths`, dan `PrivateTmp` diabaikan diam-diam di unit user, sehingga generator **tanpa isolasi filesystem**: penulisan hanya dibatasi kode yang sudah direview (hanya `storage/ringkasan/*.json(.tmp)`; log ke journal). Risiko ini diketahui dan diterima lewat keputusan Pemilik Q2 (b). Opsi yang ditolak lewat Q2 (b): memindah generator ke unit sistem di `/etc/systemd/system/` (`User=<user-app>` + `ProtectSystem=strict` + `ReadWritePaths`; rancangan awal ADR-002 butir 2). Generator menetapkan mode ringkasan secara eksplisit (direktori 0750, berkas 0640), tidak bergantung pada umask (umask login SSH di host tim sumber terukur 0002). Hak baca proses web dibahas di Q-16.

**(b) Alasan uji mockup di luar `tmp/test`** (riwayat Fase 1 tim sumber). Uji mockup Fase 1 dijalankan di folder kerja koordinator, bukan di `<AKAR>/tmp/test`, karena peramban uji (Patchright/chromium) hanya terpasang di container koordinator dan `<AKAR>/tmp/test` tidak terlihat dari container itu; uji dijalankan terhadap salinan mockup yang sha256-nya sama dengan `docs/mockup/index.html` milik tim sumber, sedangkan `tmp/test` project tetap kosong. Tidak berlaku untuk project ini (tanpa mockup).

**(c) Port dan alamat bind (K-03).** Port 24130, bind hanya `<ip-bind-1>:24130` dan `<ip-bind-2>:24130`; tanpa `0.0.0.0` dan tanpa alamat lain. Brief mencatat Koordinator mengecek pukul 12.50 bahwa port itu tidak dipakai; **cek ulang bebas sebelum dipakai di Fase 2** (Fase 1: tanpa listener, `ss -ltn | grep -c :24130` = 0).

**Catatan risiko (fakta dari skill server tim sumber, bagian Pitfalls, terukur 13 Okt 2026; dicek TL tim sumber):** publish port ke IP Tailscale berisiko gagal start saat boot bila IP Tailscale belum terpasang. Sudah dimitigasi di host dengan drop-in systemd `wait-tailscale.conf` (teruji reboot 15 Okt 2026). Perlu diverifikasi lagi di Fase 2, sebelum container web pertama kali dijalankan.

## 8. Pertanyaan terbuka fase 2

Sejak versi 4: Q-01 s.d. Q-18, Q-21, dan Q-22 **final**, keputusan Pemilik 16 Okt 2026 ±18.25–18.27 yang menjawab pertanyaan review fase 2 (Q3 (a): semua keputusan sementara CTO di ADR-003 butir 8 disetujui; Q-06 lewat Q1 (b)); Q-20 selesai lewat K-09; Q-19 masih terbuka. Baris "Status" tiap butir menyebut opsi yang menjadi keputusan; opsi lain dipertahankan sebagai jejak. Opsi 1 = rekomendasi (penyusun; bertanda "Rekomendasi CTO, ADR-001" bila diambil dari ADR-001 CTO); angka pada opsi bukan hasil ukur.

**Q-01 — Batas percobaan login.** Status: **final** = opsi 1 (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8).
1. (Rekomendasi) Jeda progresif per kombinasi akun dan alamat klien setelah 5 gagal berturut-turut (1→2→4 dtk dst., maks 5 menit), tanpa kunci permanen. Alasan: hanya 3 akun yang mudah diduga, jadi kunci lama per akun bisa dipakai pihak lain untuk mengunci Pemilik.
2. Kunci 15 menit per akun setelah 5 gagal. Sederhana, tetapi membuka celah penguncian akun oleh pihak lain.
3. Tanpa batas, hanya biaya bcrypt. Tebakan tidak terbatas jumlahnya.

**Q-02 — Kedaluwarsa sesi.** Status: **final** = opsi 1 (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8).
1. (Rekomendasi) Tak aktif 12 jam dan batas mutlak 7 hari; stream SSE ditutup saat sesi kedaluwarsa. Alasan: dashboard sering dibuka ulang dari HP, batas mutlak membatasi umur cookie yang tercuri.
2. Cookie sesi (hilang saat peramban ditutup), tak aktif 12 jam. Lebih ketat, sering login ulang di HP.
3. 30 hari bergulir. Paling nyaman, jendela risiko terbesar.

**Q-03 — SameSite=Strict + cek Origin untuk POST** (POST yang diperkirakan: login, logout, ganti password). Status: **final** = opsi 1 (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8).
1. (Rekomendasi) SameSite=Strict dan tolak POST bila Origin ada tetapi tidak cocok (usulan CTO). Alasan: dua lapis tanpa token di halaman. Konsekuensi: tautan dari aplikasi lain tidak membawa cookie pada navigasi pertama, halaman bisa tampak belum login sampai dimuat ulang.
2. SameSite=Lax dan token CSRF per sesi. Tahan kasus tautan, kode lebih banyak.
3. SameSite=Strict saja tanpa cek Origin. Paling sedikit kode, tanpa lapis kedua.

Rincian pelaksanaan opsi 1 sejak perbaikan Origin 16 Okt 2026 (keputusan CTO D1–D2): header `Referrer-Policy: same-origin` agar peramban mengirim Origin asli pada form POST same-origin; Origin yang ada harus sama dengan `http://<Host>`; Origin `null` selalu ditolak 403 (ke alamat HTTP LAN/Tailscale peramban tidak mengirim `Sec-Fetch-*`); permintaan tanpa Origin tetap lolos; tanpa allowlist host. Postmortem: dokumen tim sumber (tidak disalin).

**Q-04 — Panjang minimum password.** Status: **final** = opsi 1 (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8).
1. (Rekomendasi) Minimal 12 karakter tanpa aturan komposisi, berbeda dari password awal; tetapkan batas maksimum (bcrypt hanya memakai 72 byte pertama; verifikasi terhadap versi `x/crypto` yang dipakai). Alasan: panjang lebih berguna daripada komposisi; hanya 3 pengguna.
2. Minimal 8 karakter, campuran huruf dan angka. Lebih lemah.
3. Minimal 16 karakter. Terkuat, sering salah ketik di HP.

**Q-05 — Penyaringan data pribadi di judul tugas oleh generator** (telaah UU PDP belum dilakukan). Status: **final** = opsi 1 (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8).
1. (Rekomendasi) Generator menyaring judul, kegiatan, dan teks riwayat dengan pola NIP, NIK, email, nomor HP; bila terdeteksi seluruh teks diganti "(disaring)" (fail-closed), dengan tes negatif. Alasan: menolak seluruh teks lebih aman daripada memotong sebagian. Batas: pola tidak menangkap nama atau alamat.
2. Judul ringkas ditulis Koordinator atau TL per order, bukan dari teks order. Paling aman, tetapi manual.
3. Tanpa penyaringan, hanya isolasi per penonton. Tidak sejalan dengan data minim.

**Q-06 — TLS untuk login** (= ADR-001 Q1 = review fase 2 Q1 = ADR-003 butir 2; HTTP polos di LAN mengirim password tanpa enkripsi; Tailscale terenkripsi; tidak ada reverse proxy/TLS di host). Status: **final** = opsi 2, HTTP polos di LAN + Tailscale (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q1 (b); Pemilik sempat memilih (a) TLS self-signed lalu meralat ke (b), brief TLS dibatalkan). Ini **keputusan sadar** Pemilik, **bukan technical debt**. Risiko yang diterima: password dan cookie sesi lewat HTTP; lewat Tailscale terenkripsi, lewat LAN tidak terenkripsi; cookie tanpa `Secure`. Saran operasi: login dan ganti password lewat alamat Tailscale (`docs/operasi.md`). Ditinjau ulang menurut pemicu ADR-003 (akses ke port 24130 dari jaringan selain LAN dan Tailscale, atau indikasi penyadapan/penyalahgunaan akun) atau saat reverse proxy TLS di host aplikasi dikerjakan (ADR-001). Urutan opsi mengikuti ADR-001 (rekomendasi CTO di urutan pertama).
1. (Rekomendasi CTO, ADR-001) TLS self-signed langsung di Go (`crypto/tls`), selaras keputusan 13 Okt "self-signed sementara"; peringatan browser sekali per perangkat. Tetap 1 container, LAN dan Tailscale sama-sama terenkripsi.
2. **(Dipilih, Q1 (b))** HTTP polos di LAN + Tailscale; password lewat LAN tanpa enkripsi; keputusan sadar, bukan debt. Semula: "dicatat sebagai *technical debt* (pemilik TL project, dibayar saat reverse proxy TLS di host aplikasi dikerjakan)".
3. Hanya Tailscale (terenkripsi), tanpa LAN. Mengubah sebagian K-03 dan bergantung pada apakah Pemberi-1 dan Pemberi-2 memakai Tailscale (tidak diketahui penyusun).

**Q-07 — Tampilan terbatas: kartu hirarki orang lain (Pemilik, Pemberi-2)** (i). Status: **final** = opsi 1 (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8).
1. (Rekomendasi, = mockup) Tetap tampil, nama dan peran saja tanpa angka. Alasan: hirarki utuh (K-06 butir 1), tidak membuka data order.
2. Disembunyikan. Lebih ringkas, tetapi garis hirarki ke Koordinator tidak lengkap.

**Q-08 — Warna label "sibuk"** (ii). Status: **digantikan ACC v3 Pemilik 17 Okt 2026 18.02** (V3-P2, dijawab ya lewat Koordinator 17 Okt 2026 20.55): "sedang jalan" berwarna **hijau**, terang `#159C45` dan gelap `#34D058` (`apps/web/app.css` baris 7 dan 11; sama dengan `TEMA` di uji kontras tim sumber). "sibuk" tetap tampil sama dengan "sedang jalan" (titik `.titik.jalan,.titik.sibuk{background:var(--jalan)}`, `apps/web/app.css` baris 55; label teks "sibuk", `apps/web/app.js` baris 5), jadi tetap tiga warna status, tanpa warna keempat. Semula: Status: **final** (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8) = opsi 1 sebagaimana diubah perbaikan UI #1 Fase 2 (disetujui Pemilik ±15.00): "sibuk" tampil sama dengan "sedang jalan", yang sejak perbaikan UI #1 berwarna netral (abu gelap); warna hanya untuk pengecualian (oranye "menunggu keputusan", merah untuk galat); tidak ada warna keempat.
1. (Rekomendasi, = mockup) Memakai warna "sedang jalan". Alasan: K-05 menetapkan 3 warna status.
2. Warna netral keempat. Lebih jelas, tetapi 4 warna menyimpang dari K-05.

**Q-09 — Arti "hari ini" pada riwayat** (iii). Status: **final** = opsi 1 (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8).
1. (Rekomendasi, = mockup) Sejak 00.00 WIB. Alasan: sesuai kata "hari ini" di K-06 butir (3).
2. 24 jam terakhir. Tidak kosong tepat setelah tengah malam, tetapi jam tanpa tanggal bisa membingungkan (Q-18).

**Q-10 — Agent yang mengerjakan order milik penonton terbatas DAN order orang lain sekaligus** (iv). Data contoh tidak memuat kasus ini, jadi mockup belum memperagakannya. Status: **final** = opsi 1 (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8).
1. (Rekomendasi, usulan) Tampilkan detail order milik penonton saja; status dihitung dari order milik penonton, order lain tidak muncul. Alasan: penonton melihat kemajuan ordernya tanpa kebocoran order lain.
2. Tampilkan hanya "sibuk". Paling aman, tetapi menyembunyikan info order milik penonton sendiri.

**Q-11 — Boleh melihat jumlah order orang lain?** (v). Status: **final** = opsi 1 (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8).
1. (Rekomendasi, = mockup) Tidak. Alasan: angka seperti "3 order lain" membuka beban kerja orang lain; K-07 hanya menyebut "sibuk/bebas".
2. Boleh, total tanpa rincian. Memberi konteks, tetapi di luar K-07.

**Q-12 — Kartu orang berstatus?** K-06 butir (1) menulis "tiap kartu berstatus", sedangkan KONTRAK dan data contoh membuat kartu orang tanpa status. Status: **final** = opsi 1 (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8).
1. (Rekomendasi, = mockup) Hanya kartu agen berstatus. Alasan: sumber generator di K-08 tidak diketahui memuat kegiatan orang.
2. Status turunan (mis. "menunggu keputusan" bila ada order menunggu orang itu). Informatif, tetapi butuh aturan isolasi dan field baru.

**Q-13 — Penanda pemberi order dan format ID tugas pada data nyata** (= ADR-001 Q3). Penyusun tidak membaca `activity.jsonl`, `tl_kunci`, brief, atau proses untuk data contoh (di luar izin); fail-closed bergantung pada keterbacaan pemberi order. Status: **final** = opsi 1 (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8); = ADR-001 Q3 (a), ikut final. Pelaksanaan generator: ADR-003 butir 4 (baris `Peminta`/`Peminta asal` di header brief; fail-closed).
1. (Rekomendasi CTO, ADR-001) Setiap brief Koordinator→CTO dan CTO→TL wajib memuat baris `Peminta: <Pemilik | Pemberi-1 | Pemberi-2>`; tanpa baris itu order dianggap milik Pemilik saja (fail-closed bagi Pemberi-1/Pemberi-2). Format ID tugas ditetapkan bersama aturan ini.
2. Generator menebak dari teks bebas brief/chat. Tidak direkomendasikan: tebakan salah = bocor atau hilang.

**Q-14 — Ringkasan basi atau generator berhenti.** ADR-001 rincian 2 sudah menetapkan arah (umur dihitung dari `dibuat_pada`); yang terbuka adalah ambang dan tampilannya. Status: **final** = opsi 1, ambang 30 dtk (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8).
1. (Rekomendasi) Banner "data basi" dengan umur data bila berkas lebih tua dari ambang (usulan 30 dtk). Alasan: SSE tetap tersambung walau sumber mati.
2. Kosongkan tampilan sampai ada data baru. Tidak menyesatkan, tetapi layar kosong.

**Q-15 — Penyimpanan hash akun dan reset password.** K-07 hanya menyebut "akun dibuat dari host"; ADR-001 rincian 4 mengarahkan akun (hash bcrypt) ke bind mount `./db/data`. Yang terbuka: format berkas dan prosedur buat/reset. Status: **final** = opsi 1 (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8).
1. (Rekomendasi, selaras ADR-001) Satu berkas akun di `./db/data/` (mode 600, di `.gitignore`), dibuat dan direset dari host oleh satu skrip di `script/`; web hanya menulis berkas itu saat ganti password. Alasan: tidak ada jalur reset di web.
2. Reset lewat web. Mudah, tetapi menambah permukaan serangan dan menyimpang dari "akun dibuat dari host".

**Q-16 — Hak baca berkas ringkasan di `./storage/ringkasan`** (= ADR-002 butir 3). Generator menulis sebagai uid `<uid-app>` (`<user-app>`); proses web di container (non-root, N-04) harus bisa membaca lewat mount `./storage/ringkasan:/srv/ringkasan:ro`. Terukur 16 Okt 2026 14.10: `<AKAR>/storage` owner uid `<uid-app>`, mode 755; `storage/ringkasan/` belum dibuat (Fase 2). Status: **final** = opsi 1 (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8).
1. (Rekomendasi) Web berjalan sebagai uid `<uid-app>` non-root; direktori `ringkasan/` 0750 dan berkas 0640 milik `<user-app>`. Alasan: least privilege, karena ringkasan tidak terbaca pengguna host lain; uid yang sama juga dapat menulis berkas akun di `./db/data` (Q-15). Konsekuensi: proses web memakai uid yang sama dengan `<user-app>` di host, dibatasi `cap_drop ALL`, `no-new-privileges`, `read_only`, dan hanya dua mount.
2. Web memakai uid non-root lain (mis. bawaan image), berkas 0644 dan direktori 0755. Paling sederhana, tetapi ringkasan terbaca semua pengguna host.
3. Grup bersama: berkas 0640 dengan grup khusus, web memakai `group_add`. Tanpa berbagi uid, tetapi butuh grup baru di host dengan `<user-app>` sebagai anggota (perubahan host).

**Q-17 — Ambang kolom responsif di lebar 640–1023 px.** Mockup v2 (D1): ≥ 1024 px tiga kolom berdampingan (Tim, Tugas aktif, Riwayat hari ini; lebar konten maks 1100 px); < 1024 px satu kolom dengan urutan Tugas aktif → Tim → Riwayat hari ini. N-06 tidak mengatur 640–1023 px, dan mockup v2 memakai 1 kolom di rentang itu (keputusan lokal TL). Riwayat v1: container query 1/2/3 kolom pada isi `.wadah`. Status: **final** = opsi 1 (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8).
1. (Rekomendasi, = mockup v2) 1 kolom sampai 1023 px. Alasan: paling sederhana, dan tiga bagian tidak saling berdesakan di tablet.
2. 2 kolom mulai 768 px (Tugas aktif dan Tim berdampingan, Riwayat di bawah). Lebih padat di tablet, tetapi ada aturan tata letak tambahan.

**Q-18 — Konsistensi skema pada data contoh.** (a) `pemberi` dan `pengerja` di `tugas_aktif` berisi nama tampilan, sedangkan `pelaku` dan `agen[].tugas` berisi id; (b) `mulai`, `sejak`, `waktu` berbentuk "HH:MM" tanpa tanggal. Status: **final** = opsi 1 (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8).
1. (Rekomendasi) Tambah `pemberi_id` dan `pengerja_id` (nama tetap untuk tampilan), cocokkan kepemilikan memakai id; tambahkan tanggal bila tugas dimulai di hari sebelumnya. Alasan: pencocokan lewat nama rapuh, fail-closed lebih mudah diuji dengan id.
2. Biarkan seperti data contoh. Tanpa perubahan, tetapi rawan salah cocok.

**Q-19 — Makna "(1a)" dan "(2a)" pada K-07.** Penomoran brief Koordinator tidak ada di berkas yang dibaca penyusun; dokumen ini memakai makna dari kalimatnya saja ("(2a)" = ganti password login pertama, "(1a)" = aturan isolasi). Status: belum diputuskan. Hasil pencocokan (opsi 1 dijalankan; dicek CTO 16 Okt 2026 19.0x dan TL 19.1x): brief Koordinator asli (arsip tim sumber) baris 50 memuat label "(2a)" dan "(1a)" yang sama **tanpa definisi** (satu-satunya baris berkas itu yang memuat label tersebut), jadi makna tidak bisa dicocokkan dari berkas dan hanya bisa dikonfirmasi Koordinator. Tetap **terbuka** (keputusan CTO), menunggu konfirmasi Koordinator.
1. (Rekomendasi) TL-2 atau Koordinator mencocokkan dengan brief Koordinator asli sebelum diajukan; bila beda, F-07 dan F-15 dikoreksi tanpa mengubah bunyi K-07.
2. Biarkan apa adanya. Cepat, tetapi tidak ada bukti maknanya sama.

**Q-20 — Cara generator berjalan tiap 3–5 dtk** (= ADR-001 Q2). Status: **SELESAI**, diputuskan oleh K-09 (Keputusan Pemilik 16 Okt 2026 ±13.3x; ADR-002): service systemd di host, user `<user-app>`, skrip di `./script/` project, berjalan terus (`Restart=always`, usulan ADR-002 butir 2). Pemasangan unit butuh izin Pemilik di Fase 2 (bagian 7a).

Riwayat v1: opsi sebelum keputusan adalah (1) proses diawasi di container `<koordinator>` dengan skrip di state koordinator (rekomendasi CTO ADR-001 saat itu), (2) service systemd di host dengan skrip di folder data tim sumber, dan (3) cron 1 menit dengan loop internal 12×5 dtk. K-09 memilih varian opsi 2 dengan skrip dan keluaran di folder project.

**Q-21 — Keputusan lokal TL di mockup Fase 1** (diterima CTO 16 Okt 2026 sebagai usulan). Setiap butir dapat dibatalkan tanpa mengubah K-xx. Status: **final** = pertahankan butir a–f; butir g tetap dibatalkan (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a)). Catatan: Q-21 tidak tercantum di ADR-003 butir 8; tercakup rentang Q3 (a) "Q-01..Q-22 disetujui semua" (tafsir CTO).

| No | Keputusan lokal (usulan) | Alternatif | Rujukan |
|---|---|---|---|
| a | Label "sibuk" memakai warna "sedang jalan" agar tetap 3 warna status | warna netral keempat | Q-08 |
| b | Kartu orang (Pemilik, Pemberi-1, Pemberi-2) tanpa status | status turunan | Q-12 |
| c | Abu `#CBD2D9` hanya untuk garis/border 1 px, tidak untuk teks (kontras terhadap `#FFFFFF` 1,53:1, dihitung). Mockup v2: garis pohon dan garis bawah kepala `#C4C4CC` (1,73:1, dihitung) | warna garis lain | N-07 |
| d | ID tugas (`T-xx`) dan seluruh data contoh dikarang (fiktif) | format ID ditetapkan bersama baris `Peminta:` | Q-13, Q-18 |
| e | PNG HP dibuat dengan DSF 2 (device scale factor 2, viewport 390×844) | DSF 1 atau 3 | bagian 2 |
| f | `sejak` pada agen = jam langkah/keadaan terakhir agen itu | jam mulai tugas | Lampiran A |
| g | **Dibatalkan di mockup v2** (Pedoman tampilan v2 butir 3). Semula: kartu Koordinator di tampilan Pemberi-1 bertuliskan "melapor ke pemberi order (tingkat 2)". Di v2 hubungan atasan–bawahan hanya ditunjukkan garis pohon | — | Q-07, F-07 |

**Q-22 — Sumber nama tampilan project.** UI v2 menampilkan nama project manusiawi (mis. "Proyek A"), bukan slug ("proyek-a"). Data contoh dan skema (Lampiran A, field `project`) hanya memuat slug; mockup memakai peta fiktif di kontrak v1 tim sumber (tidak disalin). Status: **final** = opsi 1 (keputusan Pemilik 16 Okt 2026 ±18.25–18.27, Q3 (a); ADR-003 butir 8).
1. (Rekomendasi) Peta slug → nama tampilan di konfigurasi generator (berkas di `./conf/`); generator menulis nama tampilan ke ringkasan, dan slug tanpa entri peta ditampilkan apa adanya. Alasan: satu tempat, tanpa mengubah format brief.
2. Nama tampilan ditulis di brief (mis. baris `Project:`). Tanpa peta, tetapi bergantung pada disiplin penulisan brief (Q-13).
3. Peta di kode web. Paling sederhana, tetapi setiap project baru butuh build ulang.

## 9. Lampiran A — draf skema JSON ringkasan per penonton

**Versi skema: `0.1-usulan`. Belum final.** Diturunkan dari berkas data contoh fiktif tim sumber (`data-contoh.json`, tidak disalin), yang seluruhnya **DATA CONTOH (FIKTIF)** (dikarang untuk mockup, bukan dibaca dari `activity.jsonl`). Satu berkas ringkasan per penonton di `./storage/ringkasan/<penonton>.json` (`<pemilik>.json`, `<pemberi-1>.json`, `<pemberi-2>.json`; nama: ADR-001 rincian 1; lokasi: K-09, ADR-002; di container web terbaca sebagai `/srv/ringkasan/<penonton>.json`), ditulis atomik (berkas sementara di direktori yang sama lalu `rename`); server hanya mengirim berkas milik penonton yang login.

| Field | Arti |
|---|---|
| `versi_skema` | Versi skema, saat ini `"0.1-usulan"`. |
| `penonton` | Id pemilik berkas (`<pemilik>`, `<pemberi-1>`, `<pemberi-2>`); diisi generator, tidak diambil dari klien. |
| `cakupan` | `"semua"` (Pemilik) atau `"order-sendiri"` (penonton terbatas); hanya dua nilai ini di data contoh. |
| `dibuat_pada` | Waktu generator membuat berkas, ISO 8601 dengan zona (mis. `2026-10-16T13:20:05+07:00`); dasar label "terakhir diperbarui" dan umur data (N-01, ADR-001 rincian 2). |
| `orang` | Pemilik tim dan pemberi order: `id`, `nama`, `peran`, `tingkat` (1 Pemilik; 2 Pemberi-1 dan Pemberi-2), `induk` (daftar id). Tanpa status. |
| `agen` | `id`, `nama`, `peran`, `tingkat` (3 sampai 5), `induk`, `status`, `tugas` (id atau `null`), `kegiatan` (kalimat ringkas atau `null`), `sejak` ("HH:MM"). UI v2 tidak menampilkan `tingkat`, `kegiatan`, dan `sejak` (pohon dibangun dari `induk`; detail tugas hanya dari `tugas_aktif`); field tetap di skema. |
| `tugas_aktif` | `id`, `judul`, `project`, `pemberi`, `pengerja`, `mulai`, `langkah_terakhir`, `langkah_waktu`, `status`. Enam field tampilan (F-03): judul, project, pemberi, pengerja, mulai, langkah_terakhir. |
| `riwayat_hari_ini` | Urut waktu naik: `waktu` ("HH:MM"), `pelaku` (id agent), `tugas` (id), `teks` (kalimat ringkas buatan generator, bukan salinan chat/perintah); termasuk kejadian oleh Koordinator. |

`koneksi_contoh` dan `_catatan` pada `data-contoh.json` hanya untuk mockup dan **bukan** bagian skema; keadaan koneksi asli dihitung di klien.

**Kode status:** `bebas`; `jalan` (label "sedang jalan"); `menunggu` (label "menunggu keputusan"); `sibuk` (label "sibuk"), **hanya** di ringkasan penonton terbatas. `sejak` pada agen = jam langkah/keadaan terakhir agen itu (sama dengan `langkah_waktu` tugasnya); agent `bebas` punya `tugas` dan `kegiatan` = `null` dan `sejak` = jam ia menjadi bebas (TL-1 11:48 = jam T-01 selesai di riwayat). Definisi ini ditetapkan TL untuk data contoh (dicatat di `_catatan` data-contoh.json), belum diputuskan.

**Field yang DIHAPUS untuk penonton terbatas** (`cakupan` = `order-sendiri`; F-07, F-08):

1. `agen`: agent yang mengerjakan order milik penonton tetap lengkap (status `jalan`/`menunggu` plus `tugas`, `kegiatan`, `sejak`). Agent lain hanya `{id, nama, peran, tingkat, induk, status}` dengan `status` `bebas` atau `sibuk` (semua status non-bebas menjadi `sibuk`).
2. `tugas_aktif`: hanya tugas yang `pemberi`-nya penonton itu.
3. `riwayat_hari_ini`: hanya kejadian yang `tugas`-nya milik penonton.
4. Tidak ada hitungan atau ringkasan order orang lain (Q-11). `orang` tetap tiga kartu, nama dan peran saja (Q-07).
5. Fail-closed: order yang `pemberi`-nya tidak terbaca diperlakukan seperti butir 1 sampai 3 (bukan milik penonton).

Pemeriksaan pada berkas lengkap: dari 5 tugas aktif `<pemilik>`, hanya T-02 dan T-06 ber-pemberi Pemberi-1, dan hanya itu di ringkasan `<pemberi-1>`; kelima kejadian riwayat `<pemberi-1>` = seluruh kejadian T-02/T-06 di riwayat `<pemilik>`.

**DATA CONTOH (FIKTIF) — penonton `<pemilik>`** (dipangkas: 4 dari 6 agent, 2 dari 5 tugas, 3 dari 16 kejadian; `koneksi_contoh` dan `_catatan` dibuang; sisanya sama dengan `data-contoh.json`):

```json
{
  "versi_skema": "0.1-usulan",
  "penonton": "pemilik",
  "cakupan": "semua",
  "dibuat_pada": "2026-10-16T13:20:05+07:00",
  "orang": [
    {"id": "pemilik", "nama": "Pemilik", "peran": "Pemilik tim", "tingkat": 1, "induk": []},
    {"id": "pemberi-1", "nama": "Pemberi-1", "peran": "Pemberi order", "tingkat": 2, "induk": ["pemilik"]},
    {"id": "pemberi-2", "nama": "Pemberi-2", "peran": "Pemberi order", "tingkat": 2, "induk": ["pemilik"]}
  ],
  "agen": [
    {"id": "koordinator", "nama": "Koordinator", "peran": "Koordinator", "tingkat": 3, "induk": ["pemberi-1", "pemberi-2"], "status": "jalan", "tugas": "T-05", "kegiatan": "Mengumpulkan laporan dari CTO dan Anggota-1", "sejak": "13:15"},
    {"id": "cto", "nama": "CTO", "peran": "CTO", "tingkat": 4, "induk": ["koordinator"], "status": "jalan", "tugas": "T-06", "kegiatan": "Menyusun rencana kerja untuk TL", "sejak": "13:10"},
    {"id": "tl-1", "nama": "TL-1", "peran": "Tech Lead", "tingkat": 5, "induk": ["cto"], "status": "bebas", "tugas": null, "kegiatan": null, "sejak": "11:48"},
    {"id": "tl-3", "nama": "TL-3", "peran": "Tech Lead", "tingkat": 5, "induk": ["cto"], "status": "menunggu", "tugas": "T-02", "kegiatan": "Menunggu pilihan format kolom rekap dari Pemberi-1", "sejak": "12:10"}
  ],
  "tugas_aktif": [
    {"id": "T-02", "judul": "Rekap kehadiran rapat mingguan ke format Excel", "project": "proyek-a", "pemberi": "Pemberi-1", "pengerja": "TL-3", "mulai": "10:40", "langkah_terakhir": "Menunggu pilihan format kolom rekap dari Pemberi-1", "langkah_waktu": "12:10", "status": "menunggu"},
    {"id": "T-04", "judul": "Penyegaran tampilan halaman statistik", "project": "proyek-b", "pemberi": "Pemilik", "pengerja": "TL-2", "mulai": "09:30", "langkah_terakhir": "Mockup dikirim, menunggu persetujuan Pemilik", "langkah_waktu": "12:48", "status": "menunggu"}
  ],
  "riwayat_hari_ini": [
    {"waktu": "10:40", "pelaku": "koordinator", "tugas": "T-02", "teks": "Koordinator menerima order T-02 dari Pemberi-1"},
    {"waktu": "12:10", "pelaku": "tl-3", "tugas": "T-02", "teks": "TL-3 meminta keputusan format kolom rekap"},
    {"waktu": "12:48", "pelaku": "tl-2", "tugas": "T-04", "teks": "TL-2 mengirim mockup T-04; menunggu persetujuan Pemilik"}
  ]
}
```

**DATA CONTOH (FIKTIF) — penonton `<pemberi-1>`** (dipangkas: 3 dari 5 kejadian; `koneksi_contoh` dan `_catatan` dibuang). Koordinator, Anggota-1, TL-2 `sibuk` dan TL-1 `bebas` tanpa field lain; CTO dan TL-3 lengkap karena mengerjakan order Pemberi-1:

```json
{
  "versi_skema": "0.1-usulan",
  "penonton": "pemberi-1",
  "cakupan": "order-sendiri",
  "dibuat_pada": "2026-10-16T13:20:05+07:00",
  "orang": [
    {"id": "pemilik", "nama": "Pemilik", "peran": "Pemilik tim", "tingkat": 1, "induk": []},
    {"id": "pemberi-1", "nama": "Pemberi-1", "peran": "Pemberi order", "tingkat": 2, "induk": ["pemilik"]},
    {"id": "pemberi-2", "nama": "Pemberi-2", "peran": "Pemberi order", "tingkat": 2, "induk": ["pemilik"]}
  ],
  "agen": [
    {"id": "koordinator", "nama": "Koordinator", "peran": "Koordinator", "tingkat": 3, "induk": ["pemberi-1", "pemberi-2"], "status": "sibuk"},
    {"id": "cto", "nama": "CTO", "peran": "CTO", "tingkat": 4, "induk": ["koordinator"], "status": "jalan", "tugas": "T-06", "kegiatan": "Menyusun rencana kerja untuk TL", "sejak": "13:10"},
    {"id": "anggota-1", "nama": "Anggota-1", "peran": "Riset dan peraturan", "tingkat": 4, "induk": ["koordinator"], "status": "sibuk"},
    {"id": "tl-1", "nama": "TL-1", "peran": "Tech Lead", "tingkat": 5, "induk": ["cto"], "status": "bebas"},
    {"id": "tl-2", "nama": "TL-2", "peran": "Tech Lead", "tingkat": 5, "induk": ["cto"], "status": "sibuk"},
    {"id": "tl-3", "nama": "TL-3", "peran": "Tech Lead", "tingkat": 5, "induk": ["cto"], "status": "menunggu", "tugas": "T-02", "kegiatan": "Menunggu pilihan format kolom rekap dari Pemberi-1", "sejak": "12:10"}
  ],
  "tugas_aktif": [
    {"id": "T-02", "judul": "Rekap kehadiran rapat mingguan ke format Excel", "project": "proyek-a", "pemberi": "Pemberi-1", "pengerja": "TL-3", "mulai": "10:40", "langkah_terakhir": "Menunggu pilihan format kolom rekap dari Pemberi-1", "langkah_waktu": "12:10", "status": "menunggu"},
    {"id": "T-06", "judul": "Perbaikan urutan hasil pencarian dokumen", "project": "proyek-c", "pemberi": "Pemberi-1", "pengerja": "CTO", "mulai": "12:55", "langkah_terakhir": "Menyusun rencana kerja untuk TL", "langkah_waktu": "13:10", "status": "jalan"}
  ],
  "riwayat_hari_ini": [
    {"waktu": "10:40", "pelaku": "koordinator", "tugas": "T-02", "teks": "Koordinator menerima order T-02 dari Pemberi-1"},
    {"waktu": "12:10", "pelaku": "tl-3", "tugas": "T-02", "teks": "TL-3 meminta keputusan format kolom rekap"},
    {"waktu": "13:10", "pelaku": "cto", "tugas": "T-06", "teks": "CTO menyusun rencana kerja T-06"}
  ]
}
```

## 10. Kriteria penerimaan Fase 1

Skrip uji Fase 1 tim sumber (tidak disalin): `cek_struktur.sh` (struktur project, hanya membaca), sejak versi 2 `cek_requirement_k13.py` (konsistensi dokumen ini dengan K-09, hanya membaca), dan sejak versi 3 `tangkap_layar.py` (4 PNG mockup v2 dan fakta `document.fonts`, permintaan jaringan, `scrollWidth`; tanpa lulus/gagal). Untuk butir 1–5, bila daftar ini berbeda dengan skrip, skrip menjadi acuan; skrip harus GAGAL (RED) sebelum artefak dibuat dan LULUS (GREEN) sesudahnya. Butir 6–8 (mockup v2) dicek visual manual ditambah fakta satu kali (perintah Koordinator: tanpa alat cek otomatis baru untuk mockup). Bagian ini adalah riwayat Fase 1 tim sumber; `cek_mockup.py` v1 dan KONTRAK v1 diarsipkan dan tidak berlaku untuk mockup v2.

1. Direktori standar ada (`apps conf docs docker db/data db/migrations db/seeds logs script tmp/test storage tests`), owner `<user-app>`. (`cek_struktur.sh`)
2. `.env` mode 600, kosong/komentar; `.env.example` tanpa nilai rahasia; `.gitignore` memuat minimal `.env`, `db/data/`, `logs/`, `tmp/`, `storage/`. (`cek_struktur.sh`)
3. Tidak ada `docker-compose.yml`, `Dockerfile`, atau kode; tidak ada berkas nyasar di root; `tmp/test` kosong. (`cek_struktur.sh`)
4. Tanpa listener: `ss -ltn | grep -c :24130` = 0, hanya dibaca. (`cek_struktur.sh`)
5. `docs/requirement.md` memuat semua keputusan final (bunyi dipertahankan, berpenanda "Keputusan Pemilik 16 Okt 2026"), F-xx, N-xx (ditandai usulan), keamanan/privasi, batas fase, pertanyaan terbuka, lampiran skema, alasan uji di luar `tmp/test`, dan daftar path di luar folder yang dibaca generator host beserta alasannya (tanpa mount di luar folder, K-09); tanpa rahasia atau data pribadi. (tinjauan TL; versi 2 juga `cek_requirement_k13.py`)
6. `docs/mockup/index.html` dan `docs/mockup/terbatas.html`: masing-masing satu berkas ≤ 1 MB tanpa JS; 0 permintaan jaringan selain berkas itu sendiri dan data: URI (diamati saat tangkap layar); `document.fonts` Inter 400 dan 600 berstatus loaded; `scrollWidth` di 390 px = 390. (`tangkap_layar.py`)
7. Salinan mockup di folder kerja koordinator sha256-nya sama dengan `docs/mockup/` milik tim sumber. Empat PNG (bagian 2) ada dan dicek visual terhadap 11 butir Pedoman tampilan v2; setiap butir berstatus "sudah" dengan bukti yang terlihat. (tinjauan TL, lalu CTO dan Koordinator)
8. Fakta teks dan CSS (perintah sekali pakai; keluaran dicantumkan di laporan): teks terlihat kedua berkas memuat 0 kemunculan "contoh", "fiktif", "Tingkat", "melapor", "Garis di kiri", dan "Tampilan"; `terbatas.html` memuat 0 judul, project, atau pemberi order dari order orang lain (Pemilik dan Pemberi-2 hanya sebagai baris orang di pohon), dan status agent lain hanya "sibuk"/"bebas"; CSS memuat 0 `box-shadow`, 0 gradient, 0 border-radius pill pada elemen teks, font-size ⊂ {14, 16, 20, 28}; teks sekunder ≥ 4,5:1; pola NIP 18 digit, NIK 16 digit, email, dan HP = 0.

**Compose belum ada pada Fase 1:** `docker compose config -q` = **N/A Fase 1** dan pemeriksaan named volume = **N/A Fase 1** (K-01 dan K-09 melarang named volume; K-09: hanya bind mount relatif ke folder project; diperiksa di Fase 2). `git init` dan commit tidak dilakukan. Setelah semua kriteria lulus, Fase 1 berhenti dan Fase 2 menunggu persetujuan Pemilik (bagian 2).
