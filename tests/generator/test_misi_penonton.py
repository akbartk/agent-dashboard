"""Uji misi per penonton "Kantor Agen" — keadaan C2, ringkasan C6, isolasi C7, urutan C8 (TL Beta, 24 Okt 2026).

Kontrak: /workspace/agent-dashboard/kantor-agen/KONTRAK-kantor-agen.md bagian C; docs/misi.md.
Judul brief fixture memuat kanari pemilik: Kanari-Akbar-*, Kanari-Jati-*, Kanari-Dicky-*.
"""
import json
import re
import unittest

from bantu_misi import ID, PENONTON, DasarMisi, agen, misi, riwayat, t

KUNCI_MISI = {"id", "nomor", "judul", "project", "project_nama", "pemberi", "pemberi_id", "pelaksana_id", "pelaksana",
              "rantai", "status", "alasan", "menunggu_misi", "induk_misi", "mulai", "selesai", "langkah", "langkah_total",
              "langkah_sekarang", "langkah_waktu", "subagen", "spawn_kuota", "jenis", "anak", "jalan", "qc", "aktivitas"}  # P1.5: 4 field aditif + aktivitas perintah


class UjiBentukTambahan(DasarMisi):
    def test_field_tambahan_aditif_dan_kunci_misi_tertutup(self):
        h = self.buat().siklus()
        for p in PENONTON:
            with self.subTest(p=p):
                d = h[p]
                self.assertEqual("1", d["versi_skema"])
                self.assertTrue({"versi_skema", "penonton", "pemilik", "koordinator", "cakupan", "dibuat_pada", "galat", "peringatan", "orang",
                                 "agen",
                                 "tugas_aktif", "riwayat_hari_ini", "ringkasan", "misi"} == set(d))
                for m in d["misi"]:
                    self.assertEqual(KUNCI_MISI, set(m))
                for a in d["agen"]:
                    self.assertTrue({"id", "nama", "peran", "induk", "status", "terakhir_aktif", "ruang", "keadaan",
                                     "misi_aktif"} == set(a))
                for r in d["riwayat_hari_ini"]:
                    self.assertEqual({"waktu", "pelaku", "teks", "misi"}, set(r))
                for k in d["tugas_aktif"]:
                    self.assertEqual(12, len(k))


class UjiC2C6Akbar(DasarMisi):
    def test_keadaan_misi_aktif_dan_ringkasan_akbar(self):
        h = self.buat().siklus()["akbar"]
        harapan = {"ajeng": ("jalan", "bekerja", []), "desy": ("jalan", "menunggu", ["T-002"]),
                   "via": ("bebas", "bebas", []), "uci": ("bebas", "bebas", []),
                   "alfa": ("menunggu", "menunggu", ["T-004"]), "beta": ("jalan", "bekerja", ["T-003"]),
                   "carli": ("jalan", "menunggu", ["T-005"])}  # carli: status jalan (proses lain), semua misi menunggu
        self.assertEqual(harapan, {a["id"]: (a["status"], a["keadaan"], a["misi_aktif"]) for a in h["agen"]})
        self.assertEqual({"agen": {"bekerja": 2, "menunggu": 3, "bebas": 2, "sibuk": 0},
                          "misi": {"aktif": 4, "selesai_hari_ini": 2}, "subagen_aktif": 1}, h["ringkasan"])

    def test_c8_urutan_misi(self):
        h = self.buat().siklus()
        self.assertEqual(["T-002", "T-004", "T-005", "T-003", "T-006", "T-007"], [m["id"] for m in h["akbar"]["misi"]])
        self.assertEqual(["T-005"], [m["id"] for m in h["dicky"]["misi"]])
        self.assertEqual(["T-004", "T-007"], [m["id"] for m in h["jati"]["misi"]])


class UjiC7Isolasi(DasarMisi):
    def periksa_isolasi(self, h):
        teks = {p: json.dumps(h[p], ensure_ascii=False) for p in PENONTON}
        for kanari in ("Kanari-Akbar-Safir", "Kanari-Akbar-Berlian", "Kanari-Akbar-Mutiara", "Kanari-Jati-Zamrud",
                       "Kanari-Jati-Intan", "Kanari-Dicky-Rubi"):
            self.assertIn(kanari, teks["akbar"])
        self.assertNotRegex(teks["dicky"], r"Kanari-(Akbar|Jati)")
        self.assertNotRegex(teks["jati"], r"Kanari-(Akbar|Dicky)")
        milik = {"dicky": {"T-005"}, "jati": {"T-004", "T-007"}}
        for v, ids in milik.items():
            lain = {m["id"] for m in h["akbar"]["misi"]} - ids
            for i in lain:
                self.assertIsNone(re.search(r"\b" + re.escape(i) + r"\b", teks[v]), f"{v} memuat {i}")
            for m in h[v]["misi"]:
                self.assertEqual(v, m["pemberi_id"])
                self.assertTrue(all(x in ids for x in m["menunggu_misi"]))
                self.assertTrue(m["induk_misi"] is None or m["induk_misi"] in ids)
            for r in h[v]["riwayat_hari_ini"]:
                self.assertTrue(r["misi"] is None or r["misi"] in ids)

    def test_dicky_hanya_misi_dicky(self):
        h = self.buat().siklus()
        self.periksa_isolasi(h)
        d = h["dicky"]
        self.assertEqual([("carli", "Carli mulai PolicyTrack", "T-005"),
                          ("dicky", "Mas Dicky memberi order T-005 lewat Ajeng → Desy → Carli", "T-005")], riwayat(d))
        harapan = {"ajeng": ("sibuk", []), "desy": ("sibuk", []), "via": ("bebas", []), "uci": ("bebas", []),
                   "alfa": ("sibuk", []), "beta": ("sibuk", []), "carli": ("menunggu", ["T-005"])}
        self.assertEqual(harapan, {a["id"]: (a["keadaan"], a["misi_aktif"]) for a in d["agen"]})
        self.assertEqual({"agen": {"bekerja": 0, "menunggu": 1, "bebas": 2, "sibuk": 4},
                          "misi": {"aktif": 1, "selesai_hari_ini": 0}, "subagen_aktif": 0}, d["ringkasan"])

    def test_jati_hanya_misi_jati(self):
        h = self.buat().siklus()
        self.periksa_isolasi(h)
        j = h["jati"]
        self.assertEqual([("alfa", "Alfa mulai Search Engine BSK", "T-004"),
                          ("jati", "Mas Jati memberi order T-004 lewat Ajeng → Desy → Alfa", "T-004"),
                          ("jati", "Mas Jati memberi order T-007 lewat Ajeng → Uci", "T-007"),
                          ("uci", "T-007 berakhir tanpa laporan", "T-007"),
                          ("alfa", "Alfa mencatat kemajuan", "T-004")], riwayat(j))
        harapan = {"ajeng": ("sibuk", []), "desy": ("sibuk", []), "via": ("bebas", []), "uci": ("bebas", []),
                   "alfa": ("menunggu", ["T-004"]), "beta": ("sibuk", []), "carli": ("sibuk", [])}
        self.assertEqual(harapan, {a["id"]: (a["keadaan"], a["misi_aktif"]) for a in j["agen"]})
        self.assertEqual({"agen": {"bekerja": 0, "menunggu": 1, "bebas": 2, "sibuk": 4},
                          "misi": {"aktif": 1, "selesai_hari_ini": 1}, "subagen_aktif": 0}, j["ringkasan"])

    def test_akbar_memuat_semua_dan_ringkasan_v_dari_berkas_v(self):
        h = self.buat().siklus()
        self.assertEqual({ID[k] for k in "ABCDEF"}, {m["id"] for m in h["akbar"]["misi"]})
        self.assertEqual(len(h["akbar"]["riwayat_hari_ini"]),
                         33)  # 28 ber-misi + pesan Pak Akbar + 4 "mulai bekerja"

    def test_induk_dan_menunggu_misi_disaring_ke_berkas_v(self):
        d = self.buat()
        # Carli menjalankan brief T-005 (milik dicky) sebagai keturunan proses Desy (misi akbar T-002)
        brief = (d.akar / "workspace" / "brief" / "2026-10-24-carli-policytrack-rubi.md").read_text(encoding="utf-8")
        d.proses(3302, ["/bin/bash", "-c", "KANARI-argv"], 3001, comm="bash")
        d.proses(3301, d.HERMES + ["-p", "carli", "-z", brief], 3302)
        h = d.siklus()
        a = h["akbar"]
        self.assertEqual(("menunggu", "misi-lain", ["T-003", "T-005"]),
                         (misi(a, "T-002")["status"], misi(a, "T-002")["alasan"], misi(a, "T-002")["menunggu_misi"]))
        self.assertEqual(("jalan", "T-002"), (misi(a, "T-005")["status"], misi(a, "T-005")["induk_misi"]))
        m = misi(h["dicky"], "T-005")
        self.assertEqual(("jalan", None, []), (m["status"], m["induk_misi"], m["menunggu_misi"]))
        self.assertEqual(("bekerja", ["T-005"]), (agen(h["dicky"], "carli")["keadaan"], agen(h["dicky"], "carli")["misi_aktif"]))
        self.periksa_isolasi(h)

    def test_menunggu_misi_v_disaring_saat_menunggu_misi_pemilik_lain(self):
        d = self.buat()
        # Carli (misi dicky T-005) menunggu proses Via (misi akbar T-006) yang menjadi keturunannya
        b5 = (d.akar / "workspace" / "brief" / "2026-10-24-carli-policytrack-rubi.md").read_text(encoding="utf-8")
        b6 = (d.akar / "workspace" / "brief" / "2026-10-24-via-pemahaman-asn-mutiara.md").read_text(encoding="utf-8")
        d.proses(3301, d.HERMES + ["-p", "carli", "-z", b5], 1)
        d.proses(3302, ["/bin/bash", "-c", "KANARI-argv"], 3301, comm="bash")
        d.proses(3401, d.HERMES + ["-p", "via", "-z", b6], 3302)
        h = d.siklus()
        a = h["akbar"]
        self.assertEqual(("menunggu", "misi-lain", ["T-006"]),
                         (misi(a, "T-005")["status"], misi(a, "T-005")["alasan"], misi(a, "T-005")["menunggu_misi"]))
        self.assertEqual(("jalan", "T-005"), (misi(a, "T-006")["status"], misi(a, "T-006")["induk_misi"]))
        m = misi(h["dicky"], "T-005")
        self.assertEqual(("menunggu", "misi-lain", [], None), (m["status"], m["alasan"], m["menunggu_misi"], m["induk_misi"]))
        self.periksa_isolasi(h)

    def test_isolasi_tetap_saat_mode_live(self):
        d = self.buat()
        d.siklus()
        d.tambah()
        h = d.siklus(d.langkah["siklus2"])
        self.periksa_isolasi(h)
        self.assertIn(("alfa", "Alfa melanjutkan T-004", "T-004"), riwayat(h["jati"]))


if __name__ == "__main__":
    unittest.main()
