"""Uji U-2: sesi subagent (`delegate_task`) tidak memunculkan peristiwa "<Agen> mulai bekerja".

Brief /workspace/brief/2026-10-17-beta-agent-dashboard-u2-generator-docs.md (izin Pak Akbar 17 Okt 2026 20.55). Sejak 17 Okt
20.53 hook `team-activity.py` (U-1) menulis `"sub": true` pada baris `msg` sesi subagent (`pre_llm_call`,
`extra.platform == "subagent"`). Syarat penanda persis: `type == "msg"` dan `sub is True` (boolean); nilai lain atau `sub` di
baris `tool` = perilaku lama. Sid kosong (baris tool dari dalam `execute_code`) tetap dihitung satu sesi (di luar U-2).
Setiap kasus dijalankan dua kali: backfill (log dibaca dari awal) dan live (baris datang sesudah siklus pertama). Jumlah harapan
ditulis literal DAN dicocokkan dengan oracle `harapan_mulai` yang menghitung dari baris masukan; kasus subagent punya kontrol
"baris sama tanpa `sub`" yang wajib menghasilkan peristiwa, jadi tes tidak bisa lulus karena data uji kosong.
Data fiktif; sid/text/detail memuat KANARI (tearDown kelas Dasar memastikan tidak bocor). Regresi "log tanpa `sub` = perilaku
lama" dibuktikan oleh tes lama di folder ini.
Jalankan dari root project: python3 -m unittest discover -s tests/generator -v
"""
import unittest

from test_generator import Dasar, PENONTON, agen, ajeng_msg, ajeng_tool, muat_tim, tim

CATAT = muat_tim()["tool"]["catat_progres"]  # DATA uji: nama tool di config tim fixture

import generator  # noqa: E402  (path script/ disiapkan test_generator)

SKR = "2026-10-16T15:00:00+07:00"
SKR_AWAL = "2026-10-16T09:30:00+07:00"  # siklus pertama mode live: log masih kosong
MODE = ("backfill", "live")


def sub(waktu, profil="beta", sid="KANARI-W1", nilai=True, tool=None):
    """Baris hook ber-field `sub` (default: msg sesi subagent seperti keluaran hook U-1)."""
    return dict(tim(waktu, profil, tool, sid=sid), sub=nilai)


def tanpa_sub(baris):
    return [{k: v for k, v in b.items() if k != "sub"} for b in baris]


def harapan_mulai(baris, profil):
    """Oracle dari spesifikasi U-2: satu peristiwa per (profil, sid) baru menurut urutan berkas, kecuali bila baris
    pertama sid itu = `type` msg dengan `sub` bernilai boolean True."""
    dikenal, n = set(), 0
    for b in baris:
        if b.get("profile") != profil or b["sid"] in dikenal:
            continue
        dikenal.add(b["sid"])
        n += not (b["type"] == "msg" and b.get("sub") is True)
    return n


def mulai(h, profil="beta"):
    awal = f"{profil.capitalize()} mulai bekerja"
    return [r for r in h["riwayat_hari_ini"] if r["pelaku"] == profil and r["teks"].startswith(awal)]


def tanpa_riwayat(hasil):
    return {p: {k: v for k, v in h.items() if k != "riwayat_hari_ini"} for p, h in hasil.items()}


class UjiSubagent(Dasar):
    def jalankan(self, baris, mode, siapkan=None):
        d = self.buat()
        if siapkan:
            siapkan(d)
        if mode == "live":
            d.siklus(SKR_AWAL)
        d.tambah(*baris)
        return d, d.siklus(SKR)

    def periksa(self, baris, harapan, profil="beta"):
        """Jumlah 'mulai bekerja' = harapan literal = oracle, di dua mode; kembalikan keluaran per mode."""
        self.assertEqual(harapan, harapan_mulai(baris, profil), "harapan literal tidak cocok dengan oracle")
        keluaran = {}
        for mode in MODE:
            with self.subTest(mode=mode, sub=any("sub" in b for b in baris)):
                d, h = self.jalankan(baris, mode)
                self.assertEqual(harapan, len(mulai(h["akbar"], profil)))
                keluaran[mode] = (d, h)
        return keluaran

    def test_a_msg_sub_sid_baru_tanpa_mulai_bekerja(self):
        baris = [sub("2026-10-16T14:00:00")]
        self.periksa(tanpa_sub(baris), 1)  # kontrol: tanpa penanda = sesi baru
        self.periksa(baris, 0)

    def test_b_lima_subagent_sekaligus(self):
        # pola 17 Okt 17.29.59 (lima delegate_task dalam detik yang sama), digeser ke jam uji
        induk = [tim("2026-10-16T14:29:00", "beta", sid="KANARI-S1"),
                 tim("2026-10-16T14:29:30", "beta", "delegate_task", sid="KANARI-S1")]
        anak = [sub("2026-10-16T14:29:59", sid=f"KANARI-W{i}") for i in range(5)]
        anak += [tim(f"2026-10-16T14:30:0{i}", "beta", "read_file", sid=f"KANARI-W{i}") for i in range(5)]
        self.periksa(tanpa_sub(induk + anak), 1 + 5)  # kontrol: perilaku lama = induk + 5 subagent
        for d, h in self.periksa(induk + anak, 1).values():
            self.assertEqual(["2026-10-16T14:29:00+07:00"], [r["waktu"] for r in mulai(h["akbar"])])

    def test_c_msg_sub_lalu_tool_sid_sama(self):
        baris = [sub("2026-10-16T14:00:00", sid="KANARI-W1"),
                 tim("2026-10-16T14:00:05", "beta", "read_file", sid="KANARI-W1"),
                 tim("2026-10-16T14:00:10", "beta", CATAT, sid="KANARI-W1")]
        self.periksa(tanpa_sub(baris), 1)
        for d, h in self.periksa(baris, 0).values():
            # peristiwa lain dari sesi subagent tetap muncul
            self.assertEqual([("2026-10-16T14:00:10+07:00", "Beta mencatat kemajuan")],
                             [(r["waktu"], r["teks"]) for r in h["akbar"]["riwayat_hari_ini"]])

    def test_d_oneshot_tanpa_sub_tetap_satu(self):
        self.periksa([tim("2026-10-16T14:00:00", "beta", sid="KANARI-S1"),
                      tim("2026-10-16T14:00:05", "beta", "read_file", sid="KANARI-S1"),
                      tim("2026-10-16T14:01:00", "via", sid="KANARI-V1")], 1)

    def test_e_nilai_sub_bukan_boolean_true_perilaku_lama(self):
        for nilai in ("true", 1, False, None):
            with self.subTest(nilai=nilai):
                baris = [sub("2026-10-16T14:00:00", nilai=nilai)]
                k = self.periksa(baris, 1)
                for mode in MODE:
                    self.assertEqual(self.jalankan(tanpa_sub(baris), mode)[1], k[mode][1])

    def test_f_sub_di_baris_tool_perilaku_lama(self):
        baris = [sub("2026-10-16T14:00:00", tool="read_file")]
        k = self.periksa(baris, 1)
        for mode in MODE:
            self.assertEqual(self.jalankan(tanpa_sub(baris), mode)[1], k[mode][1])

    def test_g_sid_kosong_perilaku_lama(self):
        self.periksa([tim("2026-10-16T14:00:00", "beta", "read_file", sid="")], 1)
        # tool dari dalam execute_code sesi subagent (sid kosong) tetap memunculkan peristiwanya sendiri (di luar U-2)
        for mode in MODE:
            _, h = self.jalankan([sub("2026-10-16T14:00:00", sid="KANARI-W1"),
                                  tim("2026-10-16T14:00:05", "beta", "read_file", sid="")], mode)
            self.assertIn("2026-10-16T14:00:05+07:00", [r["waktu"] for r in mulai(h["akbar"])])

    def test_h_sid_dikenal_lalu_msg_sub(self):
        baris = [tim("2026-10-16T14:00:00", "beta", sid="KANARI-S5"), sub("2026-10-16T14:00:30", sid="KANARI-S5")]
        k = self.periksa(baris, 1)
        for mode in MODE:
            self.assertEqual(["2026-10-16T14:00:00+07:00"], [r["waktu"] for r in mulai(k[mode][1]["akbar"])])
            _, kontrol = self.jalankan(tanpa_sub(baris), mode)
            for p in PENONTON:
                self.assertEqual(kontrol[p]["riwayat_hari_ini"], k[mode][1][p]["riwayat_hari_ini"])

    def test_i_baris_ajeng_ber_sub_identik(self):
        baris = [ajeng_msg("2026-10-16T14:00:00") | {"sub": True},
                 ajeng_tool("2026-10-16T14:00:05", "Pak Akbar", "read_file") | {"sub": True},
                 ajeng_msg("2026-10-16T14:10:00", "Mas Dicky") | {"sub": True}]
        for mode in MODE:
            with self.subTest(mode=mode):
                d1, dengan = self.jalankan(baris, mode)
                d0, tanpa = self.jalankan(tanpa_sub(baris), mode)
                self.assertEqual(tanpa, dengan)
                self.assertIn("Pak Akbar mengirim pesan ke Ajeng", [r["teks"] for r in dengan["akbar"]["riwayat_hari_ini"]])
                self.assertEqual([(e.waktu, e.pelaku, e.teks, e.pemilik) for e in d0.g.ev_log],
                                 [(e.waktu, e.pelaku, e.teks, e.pemilik) for e in d1.g.ev_log])

    def test_j_sub_tetap_memperbarui_status_dan_terakhir_aktif(self):
        def siapkan(d):
            d.lock("policytrack", "beta", brief=d.brief("u2.md", "# Brief TL — policytrack — U2", "Peminta asal: Pak Akbar"))
        baris = [tim("2026-10-16T14:00:00", "beta", sid="KANARI-S1"),
                 tim("2026-10-16T14:00:05", "beta", "read_file", sid="KANARI-S1"),
                 sub("2026-10-16T14:10:00", sid="KANARI-W1")]
        terakhir = baris[-1]["ts"] + "+07:00"
        for mode in MODE:
            with self.subTest(mode=mode):
                d1, dengan = self.jalankan(baris, mode, siapkan)
                d0, tanpa = self.jalankan(tanpa_sub(baris), mode, siapkan)
                self.assertEqual(tanpa_riwayat(tanpa), tanpa_riwayat(dengan))
                self.assertEqual(d0.g.tim_terakhir, d1.g.tim_terakhir)
                self.assertEqual(terakhir, agen(dengan["akbar"], "beta")["terakhir_aktif"])
                t = [t for t in dengan["akbar"]["tugas_aktif"] if t["pengerja_id"] == "beta"]
                self.assertEqual(1, len(t))
                self.assertEqual(terakhir, t[0]["langkah_waktu"])


if __name__ == "__main__":
    unittest.main()
