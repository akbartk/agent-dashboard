"""Uji koreksi header Kantor Agen — B1' (H1 brief ganda dibedakan header), J-1 (awalan slug berbatas kata), J-2 (judul
dari nama berkas brief TL). Keputusan CTO brief 2026-10-24-beta-agent-dashboard-koreksi-header (TL Beta). Semua data fiktif.

Kasus (a)–(g) = kriteria T1 brief; (h) = tests/generator/test_judul_brief_x.py lama, tidak diubah.
B1': H1 baris 1 dimiliki >1 brief → kandidat = brief ber-H1 itu yang header gabungannya (H1 s.d. baris Peminta, `\\r`
akhir baris dibuang dua sisi) sama dengan `text` pada min(len) karakter pertama; tepat 1 kandidat → brief itu, else bukan misi.
"""
import json
import unittest

from bantu_misi import DasarMisi, agen, misi, riwayat, t
from test_generator import Dasar, generator, tugas

PEM_A = "Peminta asal: Pak Akbar lewat Ajeng, 24 Okt 2026 ±14.40 WIB."
PEM_D = "Peminta asal: Mas Dicky lewat Ajeng, 24 Okt 2026 ±16.20 WIB."
DARI = "Dari: Desy (CTO). Untuk: Carli."
H1_G = "# Brief TL — policytrack — 2026-10-24 — Rapikan Kanari-Akbar-Opal"
KONTEKS = "Konteks: KANARI-konteks " + "baris konteks panjang " * 14


def gabung(baris, sep="\n"):
    return sep.join(baris)


class DasarKoreksi(DasarMisi):
    def tulis_brief(self, d, nama, baris):
        (d.akar / "workspace" / "brief" / nama).write_text(gabung(baris) + "\nKANARI-isi brief\n", encoding="utf-8")

    def sesi(self, d, profil, sid, teks, hms):
        d.tambah_baris({"type": "msg", "role": "tim", "name": profil.capitalize(), "profile": profil, "sid": sid,
                        "text": teks, "ts": f"2026-10-24T{hms}"})

    def reg(self, d):
        return json.loads(d.nomor.read_text(encoding="utf-8"))["nomor"]


class UjiB1HeaderGanda(DasarKoreksi):
    X, Y = "2026-10-24-carli-policytrack-opal-satu.md", "2026-10-24-carli-policytrack-opal-dua.md"

    def test_a_text_terpotong_300_header_panjang_misi_benar(self):
        d = self.buat()
        d.siklus()
        hx = [H1_G, "", DARI, KONTEKS, PEM_A]
        hy = [H1_G, "", DARI, PEM_D]
        self.assertGreater(len(gabung(hx)), 300)
        self.tulis_brief(d, self.X, hx)
        self.tulis_brief(d, self.Y, hy)
        teks = gabung(hx)[:300]  # hook mencatat text maksimal 300 karakter
        self.sesi(d, "carli", "KANARI-SID-OPAL-A", teks, "11:31:00")
        h = d.siklus(t("11:31:05"))
        r = self.reg(d)
        self.assertEqual(8, r.get(self.X))
        self.assertNotIn(self.Y, r)
        m = misi(h["akbar"], "T-008")
        self.assertEqual(("carli", "akbar", "Rapikan Kanari-Akbar-Opal"), (m["pelaksana_id"], m["pemberi_id"], m["judul"]))
        self.assertIsNone(misi(h["dicky"], "T-008"))
        self.assertFalse(any(p == "carli" and x.startswith("Carli mulai bekerja") for p, x, _ in riwayat(h["akbar"])))

    def test_a_header_muat_utuh_baris_crlf_misi_benar(self):
        d = self.buat()
        d.siklus()
        hx, hy = [H1_G, "", DARI, PEM_D], [H1_G, "", DARI, PEM_A]
        self.tulis_brief(d, self.X, hx)
        self.tulis_brief(d, self.Y, hy)
        self.sesi(d, "carli", "KANARI-SID-OPAL-CR", gabung(hx, "\r\n") + "\r\nKANARI-t lanjutan pesan", "11:31:00")
        h = d.siklus(t("11:31:05"))
        self.assertEqual({self.X: 8}, {k: v for k, v in self.reg(d).items() if v > 7})
        self.assertEqual("dicky", misi(h["akbar"], "T-008")["pemberi_id"])
        self.assertEqual(["T-008"], [x["id"] for x in h["dicky"]["misi"] if x["id"] == "T-008"])

    def test_b_header_identik_bukan_misi(self):
        d = self.buat()
        d.siklus()
        hx = [H1_G, "", DARI, PEM_A]
        self.tulis_brief(d, self.X, hx)
        self.tulis_brief(d, self.Y, hx)
        self.sesi(d, "carli", "KANARI-SID-OPAL-B", gabung(hx) + "\nKANARI-t lanjutan pesan", "11:31:00")
        h = d.siklus(t("11:31:05"))
        self.assertEqual(7, len(self.reg(d)))
        self.assertIsNone(misi(h["akbar"], "T-008"))
        self.assertTrue(any(p == "carli" and x.startswith("Carli mulai bekerja") and m is None for p, x, m in riwayat(h["akbar"])))

    def test_b_beda_header_sesudah_300_karakter_bukan_misi(self):
        d = self.buat()
        d.siklus()
        hx, hy = [H1_G, "", DARI, KONTEKS, PEM_A], [H1_G, "", DARI, KONTEKS, PEM_D]
        self.assertGreater(len(gabung(hx[:4])), 300)
        self.tulis_brief(d, self.X, hx)
        self.tulis_brief(d, self.Y, hy)
        self.sesi(d, "carli", "KANARI-SID-OPAL-B3", gabung(hx)[:300], "11:31:00")
        h = d.siklus(t("11:31:05"))
        self.assertEqual(7, len(self.reg(d)))
        self.assertIsNone(misi(h["akbar"], "T-008"))

    def test_c_h1_unik_tetap_cukup_baris_pertama(self):
        d = self.buat()
        d.siklus()
        self.tulis_brief(d, self.X, [H1_G, "", DARI, PEM_A])
        self.sesi(d, "carli", "KANARI-SID-OPAL-C", H1_G + "\nKANARI-t baris lain beda dari header", "11:31:00")
        h = d.siklus(t("11:31:05"))
        self.assertEqual(8, self.reg(d).get(self.X))
        self.assertEqual("carli", misi(h["akbar"], "T-008")["pelaksana_id"])

    def test_c_h1_ganda_hanya_baris_pertama_bukan_misi(self):
        d = self.buat()
        d.siklus()
        self.tulis_brief(d, self.X, [H1_G, "", DARI, PEM_A])
        self.tulis_brief(d, self.Y, [H1_G, "", DARI, PEM_D])
        self.sesi(d, "carli", "KANARI-SID-OPAL-C2", H1_G + "\nKANARI-t baris lain beda dari header", "11:31:00")
        h = d.siklus(t("11:31:05"))
        self.assertEqual(7, len(self.reg(d)))
        self.assertIsNone(misi(h["akbar"], "T-008"))

    def test_d_backfill_sesudah_brief_kedua_ber_h1_sama_misi_pertama_tetap(self):
        d = self.buat()
        d.siklus()
        hx = [H1_G, "", DARI, PEM_A]
        self.tulis_brief(d, self.X, hx)
        self.sesi(d, "carli", "KANARI-SID-OPAL-D", gabung(hx) + "\nKANARI-t lanjutan pesan", "11:31:00")
        h = d.siklus(t("11:31:05"))
        self.assertEqual("carli", misi(h["akbar"], "T-008")["pelaksana_id"])
        self.tulis_brief(d, self.Y, [H1_G, "", "Dari: Desy (CTO). Untuk: Alfa.", PEM_A])  # brief kedua ber-H1 sama muncul
        h_live = d.siklus(t("11:31:10"))
        h_ulang = d.siklus(t("11:31:10"), g=d.generator(nomor=d.nomor))  # generator restart = backfill ulang seluruh log
        for h in (h_live, h_ulang):
            m = misi(h["akbar"], "T-008")
            self.assertIsNotNone(m)
            self.assertEqual(("carli", "akbar"), (m["pelaksana_id"], m["pemberi_id"]))
        self.assertEqual(8, self.reg(d)[self.X])
        self.assertEqual(8, len(self.reg(d)))

    def test_e_isolasi_dua_brief_h1_sama_pemberi_beda(self):
        d = self.buat()
        d.siklus()
        hx, hy = [H1_G, "", DARI, PEM_D], [H1_G, "", "Dari: Desy (CTO). Untuk: Alfa.", PEM_A]
        self.tulis_brief(d, self.X, hx)
        self.tulis_brief(d, self.Y, hy)
        self.sesi(d, "carli", "KANARI-SID-OPAL-E1", gabung(hx) + "\nKANARI-t", "11:31:00")
        self.sesi(d, "alfa", "KANARI-SID-OPAL-E2", gabung(hy) + "\nKANARI-t", "11:31:01")
        h = d.siklus(t("11:31:05"))
        r = self.reg(d)
        ix, iy = "T-%03d" % r[self.X], "T-%03d" % r[self.Y]
        self.assertEqual(("dicky", "akbar"), (misi(h["akbar"], ix)["pemberi_id"], misi(h["akbar"], iy)["pemberi_id"]))
        self.assertEqual([ix], [x["id"] for x in h["dicky"]["misi"] if x["id"] in (ix, iy)])
        self.assertEqual([], [x["id"] for x in h["jati"]["misi"] if x["id"] in (ix, iy)])
        self.assertFalse(any(m == iy for _, _, m in riwayat(h["dicky"])))
        self.assertNotIn(iy, json.dumps(h["dicky"]))
        self.assertNotIn(iy, agen(h["dicky"], "alfa").get("misi_aktif") or [])


class UjiJ1AwalanSlug(unittest.TestCase):
    def test_f_bagian_slug_berimbuhan_dibuang_utuh(self):
        for s in ("fkk-v2", {"fkk-v2"}, {"fkk-v2", None}):
            with self.subTest(s=s):
                self.assertIsNone(generator.judul_dari(("# Brief TL — fkk-v2-ops — 2026-10-24",), s))
                self.assertEqual("Backup image", generator.judul_dari(("# Brief TL — fkk-v2-ops — 2026-10-24 — Backup image",), s))

    def test_f_slug_diikuti_spasi_atau_kurung_tetap_dibuang(self):
        self.assertEqual("data", generator.judul_dari(("# Brief TL — portal-dev (data) — 2026-10-24",), "portal-dev"))
        self.assertEqual("data", generator.judul_dari(("# Brief TL — portal-dev(data) — 2026-10-24",), {"portal-dev"}))
        self.assertEqual("perbaikan tautan", generator.judul_dari(("# Brief TL — jdih-v3 perbaikan tautan",), "jdih-v3"))

    def test_f_bagian_lain_tidak_dipotong(self):
        kasus = [("# Brief TL — agent-dashboardx — Audit", "agent-dashboardx — Audit"),
                 ("# Brief TL — agent-dashboard: catatan — Audit", "agent-dashboard: catatan — Audit"),
                 ("# Brief TL — agent-dashboard-Ops — Audit", "agent-dashboard-Ops — Audit")]
        for h1, harap in kasus:
            with self.subTest(h1=h1):
                self.assertEqual(harap, generator.judul_dari((h1,), "agent-dashboard"))

    def test_f_himpunan_slug_lock_dan_berkas(self):
        h = ("# Brief TL — fkk-v2-ops — 2026-10-24 — fkk-v2 catatan",)
        self.assertEqual("catatan", generator.judul_dari(h, {"fkk-v2-ops", "fkk-v2"}))
        self.assertEqual("fkk-v2-ops — fkk-v2 catatan", generator.judul_dari(h))  # tanpa slug (non-TL): tidak berubah


class UjiJ2JudulBerkas(DasarKoreksi):
    def misi_baru(self, nama, h1, profil="alfa"):
        d = self.buat()
        d.siklus()
        self.tulis_brief(d, nama, [h1, "", PEM_A])
        self.sesi(d, profil, "KANARI-SID-J2", h1 + "\nKANARI-t", "11:31:00")
        return misi(d.siklus(t("11:31:05"))["akbar"], "T-008")

    def test_f_slug_berimbuhan_tidak_jadi_judul_minus(self):
        m = self.misi_baru("2026-10-24-carli-policytrack-ops-rapikan.md", "# Brief TL — policytrack-ops — 2026-10-24", "carli")
        self.assertEqual(("PolicyTrack — ops rapikan", "policytrack"), (m["judul"], m["project"]))

    def test_g_judul_kosong_jadi_project_dan_topik_berkas(self):
        kasus = [("2026-10-24-alfa-policytrack-intero-review-uji.md", "# Brief TL — policytrack — 2026-10-24",
                  "PolicyTrack — intero review uji"),
                 ("2026-10-24-alfa-policytrack-intero-fix-koreksi1.md", "# Brief TL koreksi 1 — policytrack — 2026-10-24",
                  "PolicyTrack — intero fix koreksi1"),
                 ("2026-10-24-alfa-policytrack.md", "# Brief TL — policytrack — 2026-10-24", "Pekerjaan PolicyTrack"),
                 ("2026-10-24-alfa-policytrack-0812345678901.md", "# Brief TL — policytrack — 2026-10-24", "(disaring)"),
                 ("2026-10-24-alfa-lain-topik.md", "# Brief TL — lain — 2026-10-24", "lain"),
                 ("2026-10-24-alfa-policytrack-ada-judul.md", "# Brief TL — policytrack — 2026-10-24 — Judul H1", "Judul H1")]
        for nama, h1, harap in kasus:
            with self.subTest(nama=nama):
                self.assertEqual(harap, self.misi_baru(nama, h1)["judul"])

    def test_g_pelaksana_non_tl_tidak_memakai_nama_berkas(self):
        m = self.misi_baru("2026-10-24-desy-policytrack-x.md", "# Brief CTO — 2026-10-24", "desy")
        self.assertEqual(("desy", None), (m["pelaksana_id"], m["judul"]))


class UjiJ2TugasLock(Dasar):
    def tl(self, slug, nama, h1):
        d = self.buat()
        d.lock(slug, "alfa", brief=d.brief(nama, h1, "Peminta asal: Pak Akbar lewat Ajeng."))
        return tugas(d.siklus()["akbar"], f"lock-{slug}")["judul"]

    def test_g_tugas_aktif_lock_konsisten_dengan_misi(self):
        self.assertEqual("JDIH — audit tautan", self.tl("jdih-v3", "2026-10-16-alfa-jdih-v3-audit-tautan.md",
                                                         "# Brief TL — jdih-v3 — 2026-10-16"))
        self.assertEqual("JDIH — ops backup", self.tl("jdih-v3-ops", "2026-10-16-alfa-jdih-v3-ops-backup.md",
                                                      "# Brief TL — jdih-v3-ops — 2026-10-16"))
        self.assertEqual("Pekerjaan JDIH", self.tl("jdih-v3", "x.md", "# Brief TL — jdih-v3 — 2026-10-16"))
        self.assertEqual("Audit", self.tl("jdih-v3", "2026-10-16-alfa-jdih-v3-audit.md", "# Brief TL — jdih-v3 — Audit"))


if __name__ == "__main__":
    unittest.main()
