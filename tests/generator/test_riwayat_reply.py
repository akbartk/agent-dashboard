"""Uji riwayat: notifikasi sistem gateway diabaikan (D1) dan balasan Ajeng (`reply`) tampil di riwayat (D2).

Brief /workspace/brief/2026-10-16-beta-agent-dashboard-riwayat-reply.md (keputusan CTO D1-D4). Data fiktif; setiap
`text`/`detail`/sid memuat KANARI (tearDown kelas Dasar memastikan KANARI tidak bocor ke keluaran/stdout).
Pola sistem = SYSTEM_NOTE hook Ajeng: r"^\\s*\\[IMPORTANT: Background process|\\[INTERNAL NOTIFICATION" (search).
Jalankan dari root project: python3 -m unittest discover -s tests/generator -v
"""
import unittest

from test_generator import Dasar, PENONTON, agen, ajeng_msg, ajeng_tool, teks, tim, tugas


def ajeng_reply(waktu, nama, role="owner"):
    """Bentuk baris hook on_reply: {type, role, name} + ts (tanpa isi balasan)."""
    return {"type": "reply", "role": role, "name": nama, "ts": waktu}


def sistem(waktu, nama="Pak Akbar", text="[IMPORTANT: Background process proc_KANARI0001 selesai. KANARI-isi]", **lain):
    return dict({"type": "msg", "role": "owner", "name": nama, "text": text}, **lain, ts=waktu)


# Bentuk baris 19:00:48 (activity.jsonl no. 6989): kunci {type, role, name, text, ts}; teks asli TIDAK disalin.
BARIS_1900 = {"type": "msg", "role": "owner", "name": "Pak Akbar",
              "text": "[IMPORTANT: Background process proc_KANARI0001 has finished. KANARI-isi-notifikasi]",
              "ts": "2026-10-16T19:00:48"}
SKR_1901 = "2026-10-16T19:01:00+07:00"


def dasar_l():
    """Log L sebelum 19:00:48: Ajeng terakhir clarify ke Mas Dicky (status menunggu), pesan Pak Akbar 21 menit lalu."""
    return [ajeng_msg("2026-10-16T18:40:00", "Pak Akbar"),
            ajeng_tool("2026-10-16T18:41:00", "Pak Akbar", "terminal", "hermes -p desy -z 'KANARI'"),
            ajeng_msg("2026-10-16T18:55:00", "Mas Dicky"),
            ajeng_tool("2026-10-16T18:56:00", "Mas Dicky", "clarify"),
            tim("2026-10-16T18:59:00", "desy", "read_file", sid="KANARI-S1")]


def sisip(baris, tambahan):
    """Gabungkan dan urutkan menurut ts (urutan berkas = urutan waktu, seperti log nyata)."""
    return sorted(baris + tambahan, key=lambda b: b["ts"])


def entri(h):
    return [(r["waktu"], r["pelaku"], r["teks"]) for r in h["riwayat_hari_ini"]]


def wib(ts):
    return ts + "+07:00"


class UjiNotifikasiSistem(Dasar):
    def jalankan(self, baris, skr=SKR_1901):
        d = self.buat()
        d.tambah(*baris)
        return d, d.siklus(skr)

    def test_a_baris_1900_tanpa_efek_di_tiga_penonton(self):
        self.assertEqual({"type", "role", "name", "text", "ts"}, set(BARIS_1900))
        self.assertTrue(BARIS_1900["text"].startswith("[IMPORTANT: Background process proc_"))
        d0, tanpa = self.jalankan(dasar_l())
        d1, dengan = self.jalankan(sisip(dasar_l(), [BARIS_1900]))
        for p in PENONTON:
            with self.subTest(p):
                self.assertEqual(tanpa[p], dengan[p])  # struktur penuh; dibuat_pada sama (siklus pada waktu yang sama)
        self.assertNotIn("2026-10-16T19:00:48+07:00", [r["waktu"] for r in dengan["akbar"]["riwayat_hari_ini"]])
        # D1: sah (tidak dihitung dilewati) tetapi tanpa efek pada keadaan turunan log
        self.assertEqual((0, 6), (d1.g.baris_dilewati, d1.g.baris_baru))
        self.assertEqual(set(d0.g.r), set(d1.g.r))
        self.assertEqual(d0.g.koord_terakhir, d1.g.koord_terakhir)
        self.assertEqual((d0.g.tim_terakhir, d0.g.sid), (d1.g.tim_terakhir, d1.g.sid))

    def test_b_varian_sistem_tanpa_efek(self):
        kasus = [
            ("sistem: true, teks biasa", sistem("2026-10-16T19:00:48", text="KANARI-teks biasa", sistem=True)),
            ("sistem: true, tanpa text", {"type": "msg", "role": "owner", "name": "Pak Akbar", "sistem": True,
                                          "ts": "2026-10-16T19:00:48"}),
            ("[INTERNAL NOTIFICATION di tengah", sistem("2026-10-16T19:00:48", text="KANARI awal [INTERNAL NOTIFICATION] KANARI")),
            ("spasi + baris baru sebelum [IMPORTANT", sistem("2026-10-16T19:00:48", text=" \n\t[IMPORTANT: Background process KANARI")),
            ("pengirim Mas Jati", sistem("2026-10-16T19:00:48", nama="Mas Jati")),
            ("pengirim Mas Dicky sesudah clarify", sistem("2026-10-16T18:57:00", nama="Mas Dicky")),
            ("pengirim tak dikenal", sistem("2026-10-16T19:00:48", nama="?")),
            ("baris tim ber-profile, sid baru", dict(tim("2026-10-16T19:00:48", "desy", sid="KANARI-S9"),
                                                     text="[IMPORTANT: Background process proc_KANARI")),
            ("baris tim ber-profile, sid sama, sebelum baris nyata", dict(tim("2026-10-16T18:58:00", "desy", sid="KANARI-S1"),
                                                                          text="[INTERNAL NOTIFICATION] KANARI")),
            ("baris tim sistem: true", dict(tim("2026-10-16T19:00:48", "via", sid="KANARI-V"), sistem=True)),
        ]
        _, tanpa = self.jalankan(dasar_l())
        for nama, b in kasus:
            with self.subTest(nama):
                d, dengan = self.jalankan(sisip(dasar_l(), [b]))
                self.assertEqual(tanpa, dengan)
                self.assertEqual(0, d.g.baris_dilewati)

    def test_c_pesan_nyata_60_detik_sesudah_notifikasi_tampil_pada_jam_pesan_nyata(self):
        nyata = ajeng_msg("2026-10-16T19:01:48", "Pak Akbar")
        _, h = self.jalankan([BARIS_1900, nyata], "2026-10-16T19:02:00+07:00")
        self.assertEqual([(wib(nyata["ts"]), "ajeng", "Pak Akbar mengirim pesan ke Ajeng")], entri(h["akbar"]))
        t = tugas(h["akbar"], "ajeng-akbar")
        self.assertEqual((wib(nyata["ts"]), wib(nyata["ts"]), "membaca pesan"), (t["mulai"], t["langkah_waktu"], t["langkah_terakhir"]))
        self.assertEqual(wib(nyata["ts"]), agen(h["akbar"], "ajeng")["terakhir_aktif"])

    def test_d_kontrol_tetap_dihitung_pesan(self):
        kasus = [
            ("[IMPORTANT bukan di awal", ajeng_msg("2026-10-16T19:00:48") | {"text": "KANARI lihat [IMPORTANT: Background process x"}),
            ("huruf kecil", ajeng_msg("2026-10-16T19:00:48") | {"text": "[important: background process KANARI"}),
            ("sistem: false", ajeng_msg("2026-10-16T19:00:48") | {"sistem": False}),
            ("sistem bukan True", ajeng_msg("2026-10-16T19:00:48") | {"sistem": "true"}),
            ("text bukan string", ajeng_msg("2026-10-16T19:00:48") | {"text": 42}),
        ]
        for nama, b in kasus:
            with self.subTest(nama):
                _, h = self.jalankan(sisip(dasar_l(), [b]))
                self.assertIn((wib(b["ts"]), "ajeng", "Pak Akbar mengirim pesan ke Ajeng"), entri(h["akbar"]))
                self.assertEqual(wib(b["ts"]), agen(h["akbar"], "ajeng")["terakhir_aktif"])
        # D1 hanya untuk type msg: baris tool ber-`sistem: true` tetap langkah biasa
        b = ajeng_tool("2026-10-16T19:00:48", "Pak Akbar", "read_file") | {"sistem": True}
        _, h = self.jalankan(sisip(dasar_l(), [b]))
        self.assertEqual("membaca berkas", tugas(h["akbar"], "ajeng-akbar")["langkah_terakhir"])


class UjiBalasanAjeng(Dasar):
    def jalankan(self, baris, skr=SKR_1901):
        d = self.buat()
        d.tambah(*baris)
        return d, d.siklus(skr)

    def test_e_teks_dan_isolasi_per_penonton(self):
        masukan = [("2026-10-16T14:50:00", "Pak Akbar", "owner", "Pak Akbar"),
                   ("2026-10-16T14:50:10", "Mas Dicky", "operator", "Mas Dicky"),
                   ("2026-10-16T14:50:20", "Mas Jati", "operator", "Mas Jati"),
                   ("2026-10-16T14:50:30", "?", "unknown", "Pengirim tak dikenal"),
                   ("2026-10-16T14:50:35", "  ", "unknown", "Pengirim tak dikenal"),
                   ("2026-10-16T14:50:40", "Lala", "bot", "Lala"),
                   ("2026-10-16T14:50:50", "ani@contoh.go.id", "unknown", "(disaring)")]
        d, h = self.jalankan([ajeng_reply(w, n, r) for w, n, r, _ in masukan], "2026-10-16T15:00:00+07:00")
        harapan = {p: [(wib(w), "ajeng", f"Ajeng membalas {tampil}") for w, n, _, tampil in masukan
                       if p == "akbar" or n == {"dicky": "Mas Dicky", "jati": "Mas Jati"}[p]]
                   for p in PENONTON}
        # "  " dan "?" = pengirim tak dikenal yang sama → digabung (5 menit) seperti msg
        harapan["akbar"].remove((wib("2026-10-16T14:50:35"), "ajeng", "Ajeng membalas Pengirim tak dikenal"))
        for p in PENONTON:
            with self.subTest(p):
                self.assertEqual(harapan[p], entri(h[p]))
        self.assertEqual(0, d.g.baris_dilewati)

    def test_f_reply_hanya_menambah_riwayat(self):
        balasan = [ajeng_reply("2026-10-16T18:56:30", "Mas Dicky", "operator"),   # sesudah clarify: status tetap menunggu
                   ajeng_reply("2026-10-16T18:57:00", "Pak Akbar"),               # pesan 18:40 → tanpa tugas Pak Akbar
                   ajeng_reply("2026-10-16T18:58:00", "Mas Jati", "operator"),    # Mas Jati belum pernah menulis
                   ajeng_reply("2026-10-16T19:00:59", "Lala", "bot")]
        d0, tanpa = self.jalankan(dasar_l())
        d1, dengan = self.jalankan(sisip(dasar_l(), balasan))
        tambahan = {(wib(b["ts"]), "ajeng", f"Ajeng membalas {b['name']}") for b in balasan}
        for p in PENONTON:
            with self.subTest(p):
                self.assertEqual({k: v for k, v in tanpa[p].items() if k != "riwayat_hari_ini"},
                                 {k: v for k, v in dengan[p].items() if k != "riwayat_hari_ini"})
                self.assertEqual(entri(tanpa[p]), [e for e in entri(dengan[p]) if e not in tambahan])
        self.assertEqual(sorted(tambahan), sorted(e for e in entri(dengan["akbar"]) if e in tambahan))
        self.assertEqual([(wib("2026-10-16T18:56:30"), "ajeng", "Ajeng membalas Mas Dicky")],
                         [e for e in entri(dengan["dicky"]) if e in tambahan])
        self.assertEqual([(wib("2026-10-16T18:58:00"), "ajeng", "Ajeng membalas Mas Jati")],
                         [e for e in entri(dengan["jati"]) if e in tambahan])
        # eksplisit (D2): tugas/status/terakhir_aktif Ajeng tidak berubah; tidak ada entri baru di self.r
        self.assertEqual("menunggu", agen(dengan["akbar"], "ajeng")["status"])
        self.assertEqual(wib("2026-10-16T18:56:00"), agen(dengan["akbar"], "ajeng")["terakhir_aktif"])
        self.assertEqual(["ajeng-dicky"], [t["id"] for t in dengan["akbar"]["tugas_aktif"] if t["pengerja_id"] == "ajeng"])
        t = tugas(dengan["akbar"], "ajeng-dicky")
        self.assertEqual((wib("2026-10-16T18:55:00"), "meminta keputusan Mas Dicky", wib("2026-10-16T18:56:00"), "menunggu"),
                         (t["mulai"], t["langkah_terakhir"], t["langkah_waktu"], t["status"]))
        self.assertEqual(set(d0.g.r), set(d1.g.r))
        self.assertEqual(d0.g.koord_terakhir, d1.g.koord_terakhir)
        self.assertEqual(0, d1.g.baris_dilewati)

    def test_f_reply_ber_profile_tim_tanpa_efek(self):
        kasus = [("sid baru", {"type": "reply", "role": "tim", "name": "Desy", "profile": "desy", "sid": "KANARI-S9",
                               "ts": "2026-10-16T19:00:30"}),
                 ("sid sama, sebelum baris nyata", {"type": "reply", "role": "tim", "name": "Desy", "profile": "desy",
                                                    "sid": "KANARI-S1", "ts": "2026-10-16T18:58:00"})]
        _, tanpa = self.jalankan(dasar_l())
        for nama, b in kasus:
            with self.subTest(nama):
                d, dengan = self.jalankan(sisip(dasar_l(), [b]))
                self.assertEqual(tanpa, dengan)
                self.assertEqual(0, d.g.baris_dilewati)

    def test_g_gabung_5_menit_per_r_dengan_timer_sendiri(self):
        _, h = self.jalankan([ajeng_reply("2026-10-16T10:00:00", "Pak Akbar"), ajeng_reply("2026-10-16T10:01:00", "Mas Dicky"),
                              ajeng_reply("2026-10-16T10:02:00", "Pak Akbar"), ajeng_reply("2026-10-16T10:03:00", "Mas Dicky"),
                              ajeng_reply("2026-10-16T10:04:59", "Pak Akbar"), ajeng_reply("2026-10-16T10:05:00", "Pak Akbar"),
                              ajeng_reply("2026-10-16T10:09:59", "Pak Akbar"), ajeng_reply("2026-10-16T10:10:00", "Pak Akbar")])
        self.assertEqual([(wib("2026-10-16T10:00:00"), "Ajeng membalas Pak Akbar"), (wib("2026-10-16T10:01:00"), "Ajeng membalas Mas Dicky"),
                          (wib("2026-10-16T10:05:00"), "Ajeng membalas Pak Akbar"), (wib("2026-10-16T10:10:00"), "Ajeng membalas Pak Akbar")],
                         [(w, t) for w, _, t in entri(h["akbar"])])
        # pesan + balasan ke R pada menit yang sama: keduanya tampil; timer pesan dan timer balasan terpisah
        _, h = self.jalankan([ajeng_msg("2026-10-16T11:00:00"), ajeng_reply("2026-10-16T11:00:20", "Pak Akbar"),
                              ajeng_msg("2026-10-16T11:00:40"), ajeng_reply("2026-10-16T11:00:50", "Pak Akbar"),
                              ajeng_reply("2026-10-16T11:03:00", "Pak Akbar"), ajeng_msg("2026-10-16T11:05:10"),
                              ajeng_reply("2026-10-16T11:05:30", "Pak Akbar")])
        self.assertEqual([(wib("2026-10-16T11:00:00"), "Pak Akbar mengirim pesan ke Ajeng"),
                          (wib("2026-10-16T11:00:20"), "Ajeng membalas Pak Akbar"),
                          (wib("2026-10-16T11:05:10"), "Pak Akbar mengirim pesan ke Ajeng"),
                          (wib("2026-10-16T11:05:30"), "Ajeng membalas Pak Akbar")],
                         [(w, t) for w, _, t in entri(h["akbar"])])

    def test_g_gabung_juga_antar_siklus(self):
        d = self.buat()
        d.tambah(ajeng_reply("2026-10-16T12:00:00", "Mas Jati", "operator"))
        d.siklus("2026-10-16T12:00:03+07:00")
        d.tambah(ajeng_reply("2026-10-16T12:01:00", "Mas Jati", "operator"))
        h = d.siklus("2026-10-16T12:01:03+07:00")
        self.assertEqual(["Ajeng membalas Mas Jati"], teks(h["akbar"]))
        self.assertEqual(["Ajeng membalas Mas Jati"], teks(h["jati"]))
        self.assertEqual([], teks(h["dicky"]))

    def test_reply_dibangun_ulang_saat_log_direset(self):
        d = self.buat()
        d.tambah(ajeng_msg("2026-10-16T09:00:00", "Mas Dicky"), ajeng_reply("2026-10-16T10:00:00", "Pak Akbar"))
        d.siklus("2026-10-16T10:00:03+07:00")
        d.tulis_log(ajeng_reply("2026-10-16T10:00:00", "Pak Akbar"))  # log mengecil → baca ulang dari awal
        self.assertEqual([(wib("2026-10-16T10:00:00"), "ajeng", "Ajeng membalas Pak Akbar")],
                         entri(d.siklus("2026-10-16T10:00:06+07:00")["akbar"]))


if __name__ == "__main__":
    unittest.main()
