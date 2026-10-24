"""Uji KONTRAK B4 revisi — judul dari H1 `# Brief <X>: <judul>` (CTO 24 Okt 2026 14.2x; koreksi 2 KB5, TL Beta).

B4 revisi: bagian judul pertama yang diawali `Brief` dan memuat `:` → teks sesudah `:` pertama (strip) menjadi bagian judul
dan diproses seperti bagian lain (awalan tanggal, awalan slug untuk pelaksana TL, kurung); tanpa `:` → dibuang seperti
semula. Berlaku untuk `misi[].judul` dan `tugas_aktif[].judul`. Aturan tertulis di docs/misi.md B4. Semua data fiktif.
Kasus (a)–(e) = kriteria terima KB5 brief koreksi 2; (b) dan (c) adalah penjaga perilaku lama (lulus juga pada kode lama).
"""
import unittest

from bantu_misi import DasarMisi, misi, t
from test_generator import Dasar, generator, tugas


def judul_lama(h, slug=None):
    """Salinan beku `judul_dari` SEBELUM koreksi 2 (generator.py a680096c…, baris 215–235) = oracle karakterisasi (b)."""
    if not h or not h[0].startswith("# "):
        return None
    bagian = [b.strip() for b in h[0][2:].split(" — ")]
    for i, b in enumerate(bagian):
        if b.startswith("Brief"):
            del bagian[i]
            break
    hasil = []
    for b in bagian:
        m = generator.RE_TANGGAL.match(b)
        if m:
            b = b[m.end():].strip()
        if slug and b.startswith(slug):
            b = b[len(slug):].strip()
        m = generator.RE_KURUNG.fullmatch(b)
        if m:
            b = m.group(1).strip()
        if b:
            hasil.append(b)
    return generator.saring(" — ".join(hasil))[:200] if hasil else None


H1_A = "# Brief Desy: agent-dashboard tampilan baru X (24 Okt 2026, 10.3x WIB)"
JUDUL_A = "agent-dashboard tampilan baru X (24 Okt 2026, 10.3x WIB)"

# H1 yang bagian `Brief` pertamanya TIDAK memuat ':' (atau tanpa bagian Brief) → hasil wajib sama persis dengan kode lama
KORPUS_LAMA = [
    ("# Brief TL — proj — 2026-10-24 — Judul (Alfa)", "proj"),
    ("# Brief TL — agent-dashboard — 2026-10-24 — Kantor Agen: koreksi 2 generator (judul \"Brief X:\" + uji sandbox unit "
     "penuh) (Beta)", "agent-dashboard"),
    ("# Brief TL — sdmo-v1 (FASE B: eksekusi) — 2026-10-16", "sdmo-v1"),
    ("# Brief TL — searchenginebsk — 2026-10-16 — Audit indeks campuran", "searchenginebsk"),
    ("# Brief TL — jdih-v3 — A — B", "jdih-v3"),
    ("# Brief TL — jdih-v3 — 2026-10-16 laporan akhir", "jdih-v3"),
    ("# Brief TL — jdih-v3 — jdih-v3 perbaikan tautan", "jdih-v3"),
    ("# Brief TL — jdih-v3 — (Rapi)", "jdih-v3"),
    ("# Brief TL — jdih-v3 — ()", "jdih-v3"),
    ("# Brief TL — Brief Via: X", None),  # hanya bagian Brief PERTAMA yang ditinjau; yang kedua apa adanya
    ("# Brief untuk Desy (CTO) — Perbaikan urutan hasil pencarian", None),
    ("# Brief untuk Desy (CTO) — Perbaikan: urutan", None),  # ':' di bagian lain tidak berpengaruh
    ("# Brief untuk Via — Ringkasan regulasi", None),
    ("# Brief untuk Desy (CTO)", None),
    ("# Briefing TL — A", None),  # diawali `Brief` tanpa ':' → dibuang seperti semula
    ("# Judul biasa — (Dalam kurung)", None),
    ("# Rapat — Kesimpulan: final", None),
    ("# Brief", None),
    ("# Brief TL", "jdih-v3"),
    ("## Brief Desy: bukan H1", None),
    ("Brief Desy: bukan H1", None),
    ("#Brief Desy: bukan H1", None),
    ("", None),
]


class UjiJudulDariUnit(unittest.TestCase):
    def test_a_brief_bertitik_dua_jadi_judul(self):
        j = generator.judul_dari((H1_A,))
        self.assertIsNotNone(j)
        self.assertTrue(j.startswith("agent-dashboard tampilan baru X"), j)
        self.assertEqual(JUDUL_A, j)

    def test_b_tanpa_titik_dua_di_bagian_brief_sama_persis_dengan_kode_lama(self):
        for h1, slug in KORPUS_LAMA:
            for s in {slug, None}:
                with self.subTest(h1=h1, slug=s):
                    self.assertEqual(judul_lama((h1,), s), generator.judul_dari((h1,), s))

    def test_b_contoh_brief_tl(self):
        h = ("# Brief TL — proj — 2026-10-24 — Judul (Alfa)",)
        self.assertEqual(("Judul (Alfa)", "proj — Judul (Alfa)"), (generator.judul_dari(h, "proj"), generator.judul_dari(h)))

    def test_c_brief_saja_atau_kosong_sesudah_titik_dua_null(self):
        for h1 in ("# Brief", "# Brief Desy:", "# Brief Desy:   ", "# Brief Desy: — 2026-10-24", "# Brief Desy: ()"):
            for s in (None, "jdih-v3"):
                with self.subTest(h1=h1, slug=s):
                    self.assertIsNone(generator.judul_dari((h1,), s))

    def test_d_slug_tl_tetap_dibuang_dari_teks_sesudah_titik_dua(self):
        kasus = [("# Brief Alfa: jdih-v3 perbaikan tautan", "perbaikan tautan"),
                 ("# Brief Alfa: jdih-v3 — 2026-10-24 — Audit", "Audit"),
                 ("# Brief Alfa: jdih-v3", None)]
        for h1, harapan in kasus:
            with self.subTest(h1=h1):
                self.assertEqual(harapan, generator.judul_dari((h1,), "jdih-v3"))
        self.assertEqual("jdih-v3 perbaikan tautan", generator.judul_dari(("# Brief Alfa: jdih-v3 perbaikan tautan",)))

    def test_rincian_aturan(self):
        kasus = [("# Brief Desy: A: B", "A: B"),  # ':' PERTAMA
                 ("# Brief Desy: 2026-10-24 Audit akhir", "Audit akhir"),  # awalan tanggal dibuang
                 ("# Brief Desy: (Rapi)", "Rapi"),  # kurung dilepas
                 ("# Rapat — Brief Via: Ringkasan regulasi", "Rapat — Ringkasan regulasi"),  # bagian Brief tidak di depan
                 ("# Brief Desy: X — Brief Via: Y", "X — Brief Via: Y"),  # hanya bagian Brief pertama
                 ("# Brief Desy:X", "X"),
                 ("# Brief Desy: hubungi budi@contoh.go.id", "(disaring)"),  # penyaring §3.7 tetap
                 ("# Brief Desy: " + "x" * 300, "x" * 200)]
        for h1, harapan in kasus:
            with self.subTest(h1=h1):
                self.assertEqual(harapan, generator.judul_dari((h1,)))


class UjiJudulTugasAktif(Dasar):
    """(e) tugas_aktif[].judul: proses non-TL (Desy, header -z) dan lock TL."""

    def desy_tugas(self, h1):
        d = self.buat()
        d.brief("x.md", h1, "Peminta asal: Pak Akbar lewat Ajeng.")
        d.desy(2001, "desy", h1 + "\nPeminta asal: Pak Akbar lewat Ajeng.\nKANARI-ISI")
        return tugas(d.siklus()["akbar"], "proses-2001")

    def tl_tugas(self, h1, slug="jdih-v3"):
        d = self.buat()
        d.lock(slug, "alfa", brief=d.brief("b.md", h1, "Peminta asal: Pak Akbar lewat Ajeng."))
        return tugas(d.siklus()["akbar"], f"lock-{slug}")

    def test_a_e_tugas_desy_brief_bertitik_dua(self):
        t_ = self.desy_tugas(H1_A)
        self.assertEqual((JUDUL_A, "Pak Akbar", None), (t_["judul"], t_["pemberi"], t_["project"]))

    def test_c_e_tugas_desy_kosong_sesudah_titik_dua_null(self):
        self.assertIsNone(self.desy_tugas("# Brief Desy:")["judul"])

    def test_d_e_tugas_tl_slug_dibuang(self):
        self.assertEqual("perbaikan tautan", self.tl_tugas("# Brief Alfa: jdih-v3 perbaikan tautan")["judul"])
        self.assertEqual("Pekerjaan JDIH", self.tl_tugas("# Brief Alfa: jdih-v3")["judul"])  # kosong → fallback §3.5

    def test_b_e_tugas_tl_format_baku_tetap(self):
        self.assertEqual("Judul (Alfa)", self.tl_tugas("# Brief TL — jdih-v3 — 2026-10-24 — Judul (Alfa)")["judul"])


class UjiJudulMisi(DasarMisi):
    """(e) misi[].judul: pelaksana non-TL (Desy) tanpa buang slug; pelaksana TL (Beta) buang awalan slug project."""

    def misi_baru(self, nama, h1, profil, sid):
        d = self.buat()
        d.siklus()
        (d.akar / "workspace" / "brief" / nama).write_text(f"{h1}\n\nPeminta asal: Pak Akbar lewat Ajeng.\nKANARI-isi\n",
                                                           encoding="utf-8")
        d.tambah_baris({"type": "msg", "role": "tim", "name": profil.capitalize(), "profile": profil, "sid": sid,
                        "text": h1 + "\nKANARI-t", "ts": "2026-10-24T11:31:00"})
        return misi(d.siklus(t("11:31:05"))["akbar"], "T-008")

    def test_a_e_misi_desy_brief_bertitik_dua(self):
        m = self.misi_baru("2026-10-24-desy-agent-dashboard-tampilan-x.md", H1_A, "desy", "KANARI-SID-BX1")
        self.assertEqual((JUDUL_A, "desy", "agent-dashboard", "akbar"),
                         (m["judul"], m["pelaksana_id"], m["project"], m["pemberi_id"]))

    def test_c_e_misi_desy_kosong_sesudah_titik_dua_null(self):
        m = self.misi_baru("2026-10-24-desy-kosong.md", "# Brief Desy:", "desy", "KANARI-SID-BX2")
        self.assertEqual(("desy", None), (m["pelaksana_id"], m["judul"]))

    def test_d_e_misi_tl_slug_project_dibuang(self):
        m = self.misi_baru("2026-10-24-beta-agent-dashboard-koreksi-x.md", "# Brief Beta: agent-dashboard koreksi dua",
                           "beta", "KANARI-SID-BX3")
        self.assertEqual(("koreksi dua", "beta", "agent-dashboard"), (m["judul"], m["pelaksana_id"], m["project"]))


if __name__ == "__main__":
    unittest.main()
