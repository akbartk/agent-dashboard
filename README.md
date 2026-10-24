# agent-dashboard

Dashboard satu halaman untuk melihat hirarki tim agent, status tiap agent, tugas aktif beserta pemberi order, riwayat hari ini,
dan misi per agen. Dua bagian:

- **Generator** (`script/generator.py`, Python 3 stdlib): membaca sumber aktivitas secara baca-saja (log aktivitas, lock, header brief,
  `/proc`, profil agen) dan menulis satu ringkasan JSON per penonton ke `storage/ringkasan/`.
- **Web** (`apps/`, Go + aset statis, satu container): login, lalu mengirim ringkasan milik penonton yang login lewat SSE. Container web
  tidak pernah membaca log mentah.

Identitas tim, daftar agen, jalur sumber data, dan pola nama dibaca dari satu berkas config `conf/tim.json`, tanpa nilai tetap di kode
(`docs/config.md`). Project ini adalah hasil port ke host g7; dokumen di `docs/` diturunkan dari dokumen tim sumber dan disamarkan.

> Status: kode dan dokumen disiapkan; **pemasangan belum dijalankan** (`docs/pasang-g7.md` hanya rencana).

## Struktur folder

```
<AKAR>/                       # di host g7: /data/agent-dashboard
├─ apps/                      # web: Go (server, sesi, akun, SSE) dan aset statis di apps/web/
├─ conf/                      # tim.example.json (contoh), proyek.json (peta slug → nama), unit systemd templat; tim.json = config pemasangan
├─ docker/                    # Dockerfile image web
├─ db/{data,migrations,seeds} # data akun (db/data/akun.json, 0600)
├─ docs/                      # dokumentasi (daftar di bawah)
├─ hooks/                     # hook aktivitas (tidak dipasang oleh repo ini)
├─ logs/
├─ script/                    # generator.py, pasang-generator.sh, akun.sh
├─ storage/                   # ringkasan/ (keluaran generator), misi/ (registri nomor misi)
├─ tests/                     # generator/, hooks/, ui/, fixtures/
├─ tmp/test/                  # sisa uji; dibersihkan, hanya .gitkeep
├─ .env  .env.example  .gitignore  docker-compose.yml
```

`.env` (mode 600) dan `conf/tim.json` adalah config per pemasangan dan tidak di-commit; yang masuk git adalah `.env.example` dan
`conf/tim.example.json`. Aturan folder mengikuti standar aplikasi: bind mount relatif, tanpa named volume, uji di `tmp/test`.

## Cara uji

Dari root project (tanpa menyentuh storage live; arahkan keluaran uji ke `tmp/test/`):

```
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/generator    # generator + kontrak (fixture tests/fixtures)
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s tests/hooks        # hook aktivitas
python3 script/generator.py --sekali --keluaran tmp/test/uji/ringkasan --nomor tmp/test/uji/nomor.json
docker-compose --env-file .env.example config -q                              # compose sah (host g7: docker-compose v1)
# Go (versi sesuai apps/go.mod), dari apps/:
GOTOOLCHAIN=local go test -count=1 ./...
```

Fixture tes generator memakai data tim sumber sebagai DATA uji (di `tests/fixtures/`), bukan di `conf/`.

## Dokumentasi

| Berkas | Isi |
|---|---|
| [docs/config.md](./docs/config.md) | semua kunci `conf/tim.json`, env `AD_*` dan `TEAM_ACTIVITY_LOG`, privasi log (`aktivitas`), nilai pemasangan g7 |
| [docs/pasang-g7.md](./docs/pasang-g7.md) | rencana pasang di g7 (belum dijalankan), uji pasca-pasang, keputusan terbuka, rollback |
| [docs/operasi.md](./docs/operasi.md) | operasi harian: komponen, status, akun, restart, rollback, pengerasan |
| [docs/skema-ringkasan.md](./docs/skema-ringkasan.md) | kontrak JSON ringkasan per penonton dan aturan generator |
| [docs/misi.md](./docs/misi.md) | aturan misi "Kantor Agen" (nomor misi, status, isolasi) |
| [docs/requirement.md](./docs/requirement.md) | requirement, keputusan, keamanan, dan pertanyaan terbuka (dokumen tim sumber, disamarkan) |
