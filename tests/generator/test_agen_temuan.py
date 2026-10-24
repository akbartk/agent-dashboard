"""Uji daftar agen ditemukan otomatis (brief CTO 22 Okt 2026, keputusan D1–D11) + agen Uci.

Agen hadir = ajeng + setiap folder profil `<id>/profile.yaml` (dipindai ulang tiap siklus); atribut dari `agen` di conf/tim.json
(dibaca tiap siklus), tanpa entri → bawaan (nama id berhuruf awal kapital, induk ajeng, peran dari `description`).
Semua data fiktif; detail/text/sid memuat KANARI dan tidak boleh muncul di keluaran (dicek tearDown Dasar).
Jalankan dari root project: python3 -m unittest discover -s tests/generator -v
"""
import ast
import json
import os
import re
import shutil
import subprocess
import sys
from unittest import mock

from bantu_tim import tulis_tim
from test_generator import HERMES, ROOT, SKR, Dasar, agen, ajeng_tool, teks, tim, tugas

import generator  # noqa: E402  (path script/ disiapkan test_generator)

GALAT_AGEN = "Config agen tidak terbaca"
GALAT_PROFIL = "Folder profil tidak terbaca"
CFG = {
    "ajeng": {"nama": "Ajeng", "peran": "Koordinator", "induk": ["dicky", "jati"], "ruang": "koordinasi"},
    "desy": {"nama": "Desy", "peran": "CTO", "induk": ["ajeng"], "ruang": "teknik"},
    "via": {"nama": "Via", "peran": "Riset dan peraturan", "induk": ["ajeng"], "ruang": "riset"},
    "uci": {"nama": "Uci", "peran": "QA/QC", "induk": ["ajeng"], "ruang": "qa"},
    "alfa": {"nama": "Alfa", "peran": "Tech Lead", "induk": ["desy"], "ruang": "teknik"},
    "beta": {"nama": "Beta", "peran": "Tech Lead", "induk": ["desy"], "ruang": "teknik"},
    "carli": {"nama": "Carli", "peran": "Tech Lead", "induk": ["desy"], "ruang": "teknik"},
}
LAMA = ("alfa", "beta", "carli", "desy", "via")
YAML = {  # bentuk dump Hermes (kutip tunggal, bisa terlipat)
    "alfa": "description: 'Tech Lead Alfa tim kantor BSK, di bawah CTO Desy: pengembangan aplikasi BSK di bskdev.'\n"
            "description_auto: false\n",
    "beta": "description: 'Tech Lead Beta tim kantor BSK.'\ndescription_auto: false\n",
    "carli": "description: 'Tech Lead Carli tim kantor BSK.'\ndescription_auto: false\n",
    "desy": "description: 'Tech Lead + System Architect tim kantor BSK: sysadmin, arsitektur sistem/aplikasi,\n"
            "  development web dan mobile, diagnosis aplikasi BSK di bskdev.'\ndescription_auto: false\n",
    "uci": "description: 'QA/QC Utama tim kantor BSK Hukum: QC independen.'\ndescription_auto: false\n",
    "via": "description: 'Researcher tim kantor BSK: riset, kajian kebijakan, pemahaman peraturan\n"
           "  dan undang-undang, cek fakta.'\ndescription_auto: false\n",
}
H_UCI = ("# Brief QC — 2026-10-16 — QC rilis contoh", "Peminta: Pak Akbar lewat Ajeng, 16 Okt 2026 14.40 WIB")
PANGGIL_UCI = 'HOME=/opt/data /opt/hermes/.venv/bin/hermes -p uci -z "$(cat /workspace/brief/KANARI-qc.md)"'


def p1(i):
    return f"Profil {i} belum ada di conf/tim.json"


def p2(i):
    return f"Profil {i} bentrok dengan id tetap, diabaikan"


def ids(h):
    return [a["id"] for a in h["agen"]]


class AgenDasar(Dasar):
    def dunia_agen(self, profil=LAMA + ("uci",), cfg=CFG):
        """Dunia uji dengan folder profil + config sendiri; Generator dibuat ulang dengan agen=/profil=."""
        d = self.buat()
        d.profil_uji = d.akar / "profil-uji"
        d.profil_uji.mkdir()
        for i in profil:
            self.profil(d, i)
        d.agen_uji = d.akar / "tim-uji.json"
        if cfg is not None:
            self.config(d, cfg)
        d.g = generator.Generator(activity=d.activity, workspace=d.workspace, proc=d.proc, proyek=d.proyek,
                                  keluaran=d.keluaran, tim=d.agen_uji, profil=d.profil_uji)
        return d

    def profil(self, d, i, yaml=None):
        (d.profil_uji / i).mkdir()
        (d.profil_uji / i / "profile.yaml").write_text(YAML.get(i, "description: ''\n") if yaml is None else yaml,
                                                      encoding="utf-8")

    def config(self, d, cfg):
        """cfg dict = isi `agen` pada tim.json sah; str = isi mentah (JSON objek dibungkus sebagai `agen`)."""
        if isinstance(cfg, str):
            try:
                cfg = json.loads(cfg) if isinstance(json.loads(cfg), dict) else cfg
            except ValueError:
                pass
        if isinstance(cfg, str):
            d.agen_uji.write_text(cfg, encoding="utf-8")
        else:
            tulis_tim(d.agen_uji, d.akar, agen=cfg)

    def cli(self, d, *tambahan):
        return subprocess.run([sys.executable, str(ROOT / "script" / "generator.py"), "--activity", str(d.activity),
                               "--workspace", str(d.workspace), "--proc", str(d.proc), "--proyek", str(d.proyek),
                               "--keluaran", str(d.keluaran), "--tim", str(d.agen_uji), "--profil", str(d.profil_uji),
                               "--sekali", "--sekarang", SKR, *tambahan],
                              capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL,
                              env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))

    def uci_bekerja(self, d, pemberi="Pak Akbar", proses=True):
        h = (H_UCI[0], H_UCI[1].replace("Pak Akbar", pemberi))
        d.brief("qc-uci.md", *h)
        if proses:
            d.proses(7001, HERMES + ["-p", "uci", "-z", "\n".join(h) + "\n\nKANARI-z"], "2026-10-16T14:41:00+07:00")
        d.tambah(ajeng_tool("2026-10-16T14:41:00", pemberi, "terminal", PANGGIL_UCI),
                 tim("2026-10-16T14:41:05", "uci", sid="KANARI-U1"),
                 tim("2026-10-16T14:42:00", "uci", "read_file", sid="KANARI-U1"))


class UjiTemuan(AgenDasar):
    """(a)(b) agen baru muncul / agen dihapus hilang pada siklus berikut, tanpa Generator baru."""

    def test_profil_baru_tanpa_entri_muncul_di_siklus_berikut(self):
        d = self.dunia_agen(profil=LAMA)
        h1 = d.siklus()["akbar"]
        self.assertEqual(["ajeng", "desy", "via", "alfa", "beta", "carli"], ids(h1))
        self.assertEqual([], h1["peringatan"])
        self.profil(d, "zeta", "description: 'Agen uji baru: contoh.'\ndescription_auto: false\n")
        hasil = d.siklus("2026-10-16T15:00:03+07:00")
        for p in ("akbar", "dicky", "jati"):
            h = hasil[p]
            self.assertEqual(["ajeng", "desy", "via", "alfa", "beta", "carli", "zeta"], ids(h))
            self.assertEqual({"id": "zeta", "nama": "Zeta", "peran": "Agen uji baru: contoh.", "induk": ["ajeng"],
                              "status": "bebas", "terakhir_aktif": None, "ruang": "lain", "keadaan": "bebas",
                              "misi_aktif": []}, agen(h, "zeta"))
            self.assertEqual([p1("zeta")], h["peringatan"])
            self.assertEqual([], h["galat"])
            self.assertEqual(["versi_skema", "penonton", "pemilik", "koordinator", "cakupan", "dibuat_pada", "galat", "peringatan", "orang", "agen",
                              "tugas_aktif", "riwayat_hari_ini", "ringkasan", "misi"], list(h))

    def test_profil_dihapus_hilang_di_siklus_berikut(self):
        d = self.dunia_agen()
        self.uci_bekerja(d)
        self.assertIn("uci", ids(d.siklus()["akbar"]))
        shutil.rmtree(d.profil_uji / "uci")
        os.remove(d.profil_uji / "carli" / "profile.yaml")  # folder tanpa profile.yaml = bukan agen
        d.tambah(tim("2026-10-16T14:59:00", "uci", "write_file", sid="KANARI-U9"))
        hasil = d.siklus("2026-10-16T15:00:03+07:00")
        for p in ("akbar", "dicky", "jati"):
            h = hasil[p]
            self.assertEqual(["ajeng", "desy", "via", "alfa", "beta"], ids(h))
            self.assertEqual([], [t for t in h["tugas_aktif"] if t["pengerja_id"] == "uci"])  # proses -p uci tetap ada
            self.assertEqual([], h["peringatan"])
        # proses -p uci bukan lagi anggota → Ajeng tidak jalan karenanya (baris Ajeng terakhir 14:41)
        self.assertEqual("bebas", agen(hasil["akbar"], "ajeng")["status"])


class UjiUci(AgenDasar):
    """(c) Uci tampil seperti Desy/Via: status dari proses, terakhir aktif dari log, riwayat, tugas dari proses."""

    def test_uci_jalan_dari_proses_riwayat_dan_tugas(self):
        d = self.dunia_agen()
        self.uci_bekerja(d)
        d.tambah(tim("2026-10-16T14:43:00", "uci", "mcp__obsidian_bsk__catat_progres", sid="KANARI-U1"),
                 tim("2026-10-16T14:44:00", "uci", "mcp__obsidian_bsk__setor", sid="KANARI-U1"))
        h = d.siklus()["akbar"]
        self.assertEqual(["ajeng", "desy", "via", "uci", "alfa", "beta", "carli"], ids(h))
        self.assertEqual({"id": "uci", "nama": "Uci", "peran": "QA/QC", "induk": ["ajeng"], "status": "jalan",
                          "terakhir_aktif": "2026-10-16T14:44:00+07:00", "ruang": "qa", "keadaan": "bekerja",
                          "misi_aktif": []}, agen(h, "uci"))
        self.assertEqual("jalan", agen(h, "ajeng")["status"])  # proses anggota non-TL (uci) hidup
        r = [(x["waktu"], x["pelaku"], x["teks"]) for x in h["riwayat_hari_ini"]]
        for e in (("2026-10-16T14:41:00+07:00", "ajeng", "Ajeng memanggil Uci"),
                  ("2026-10-16T14:41:05+07:00", "uci", "Uci mulai bekerja"),
                  ("2026-10-16T14:43:00+07:00", "uci", "Uci mencatat kemajuan"),
                  ("2026-10-16T14:44:00+07:00", "uci", "Uci menyetor dokumen ke bank dokumen")):
            self.assertIn(e, r)
        self.assertEqual(1, teks(h).count("Uci mulai bekerja"))
        self.assertEqual({"id": "proses-7001", "judul": "QC rilis contoh", "project": None, "project_nama": None,
                          "pemberi": "Pak Akbar", "pemberi_id": "akbar", "pengerja": "Uci", "pengerja_id": "uci",
                          "mulai": "2026-10-16T14:41:00+07:00", "langkah_terakhir": "mengelola bank dokumen",
                          "langkah_waktu": "2026-10-16T14:44:00+07:00", "status": "jalan"}, tugas(h, "proses-7001"))
        self.assertEqual("memanggil Uci", tugas(h, "ajeng-akbar")["langkah_terakhir"])

    def test_uci_bebas_tanpa_proses(self):
        d = self.dunia_agen()
        self.uci_bekerja(d, proses=False)
        h = d.siklus()["akbar"]
        self.assertEqual(("bebas", "2026-10-16T14:42:00+07:00"), (agen(h, "uci")["status"], agen(h, "uci")["terakhir_aktif"]))
        self.assertEqual("bebas", agen(h, "ajeng")["status"])
        self.assertEqual([], [t for t in h["tugas_aktif"] if t["pengerja_id"] == "uci"])
        self.assertIn("Ajeng memanggil Uci", teks(h))

    def test_baris_profile_ajeng_atau_tak_hadir_diabaikan(self):
        d = self.dunia_agen(profil=LAMA)  # uci ada di config, tetapi profilnya tidak ada
        d.tambah(tim("2026-10-16T14:59:00", "uci", "write_file"), tim("2026-10-16T14:59:01", "ajeng", "write_file"),
                 tim("2026-10-16T14:59:02", "zeta"))
        h = d.siklus()["akbar"]
        self.assertEqual(([], []), (h["tugas_aktif"], h["riwayat_hari_ini"]))
        self.assertNotIn("uci", ids(h))
        self.assertIsNone(agen(h, "ajeng")["terakhir_aktif"])


class UjiIsolasi(AgenDasar):
    """(d) §5 berlaku sama untuk agen hasil temuan."""

    def test_order_pak_akbar_dicky_jati_melihat_uci_sibuk_tanpa_detail(self):
        d = self.dunia_agen()
        self.uci_bekerja(d)
        hasil = d.siklus()
        for p in ("dicky", "jati"):
            h = hasil[p]
            self.assertEqual({"id": "uci", "nama": "Uci", "peran": "QA/QC", "induk": ["ajeng"], "status": "sibuk",
                              "terakhir_aktif": None, "ruang": "qa", "keadaan": "sibuk", "misi_aktif": []}, agen(h, "uci"))
            self.assertEqual([], [t for t in h["tugas_aktif"] if t["pengerja_id"] == "uci"])
            self.assertEqual([], [r for r in h["riwayat_hari_ini"] if r["pelaku"] == "uci" or "Uci" in r["teks"]])

    def test_order_mas_dicky_hanya_dicky_melihat_tugas_uci(self):
        d = self.dunia_agen()
        self.uci_bekerja(d, pemberi="Mas Dicky")
        d.siklus()
        d.tambah(tim("2026-10-16T14:59:00", "uci", "mcp__obsidian_bsk__catat_progres", sid="KANARI-U2"))
        hasil = d.siklus("2026-10-16T15:00:03+07:00")
        dk, jt = hasil["dicky"], hasil["jati"]
        self.assertEqual(["proses-7001"], [t["id"] for t in dk["tugas_aktif"] if t["pengerja_id"] == "uci"])
        self.assertEqual("mencatat kemajuan", tugas(dk, "proses-7001")["langkah_terakhir"])
        self.assertEqual(("jalan", "2026-10-16T14:59:00+07:00"), (agen(dk, "uci")["status"], agen(dk, "uci")["terakhir_aktif"]))
        self.assertIn("Ajeng memanggil Uci", teks(dk))
        self.assertIn("Uci mulai bekerja", teks(dk))  # sid baru di siklus live → milik pemberi tunggal tugas Uci
        self.assertIn("Uci mencatat kemajuan", teks(dk))
        self.assertEqual([], [t for t in jt["tugas_aktif"] if t["pengerja_id"] == "uci"])
        self.assertEqual(("sibuk", None), (agen(jt, "uci")["status"], agen(jt, "uci")["terakhir_aktif"]))
        self.assertEqual([], [r for r in jt["riwayat_hari_ini"] if r["pelaku"] == "uci" or "Uci" in r["teks"]])


class UjiConfig(AgenDasar):
    """(e) conf/agen.json: hilang/tidak sah → galat + config sah terakhir; urutan; kunci lain; entri tak hadir."""

    def test_agen_kosong_di_config_atribut_bawaan(self):
        d = self.dunia_agen(cfg={})
        h = d.siklus()["akbar"]
        self.assertEqual([], h["galat"])
        self.assertEqual(["ajeng", "alfa", "beta", "carli", "desy", "uci", "via"], ids(h))
        self.assertEqual(("Ajeng", "", []), (agen(h, "ajeng")["nama"], agen(h, "ajeng")["peran"], agen(h, "ajeng")["induk"]))
        self.assertEqual(("Desy", ("Tech Lead + System Architect tim kantor BSK: sysadmin, arsitektur sistem/aplikasi, "
                                   "development web dan mobile, diagnosis aplikasi BSK di bskdev.")[:120], ["ajeng"]),
                         (agen(h, "desy")["nama"], agen(h, "desy")["peran"], agen(h, "desy")["induk"]))
        self.assertEqual("Researcher tim kantor BSK: riset, kajian kebijakan, pemahaman peraturan dan undang-undang, cek fakta.",
                         agen(h, "via")["peran"])
        self.assertEqual(sorted(p1(i) for i in ("ajeng", "alfa", "beta", "carli", "desy", "uci", "via")), h["peringatan"])

    def test_config_tidak_sah_pakai_config_sah_terakhir(self):
        d = self.dunia_agen()
        h0 = d.siklus()["akbar"]
        self.assertEqual(([], []), (h0["galat"], h0["peringatan"]))
        rusak = ["{", "[]", '"x"', json.dumps({"Uci": CFG["uci"]}), json.dumps({".x": CFG["uci"]}),
                 json.dumps({"uci": {"nama": "", "peran": "x", "induk": []}}),
                 json.dumps({"uci": {"nama": 5, "peran": "x", "induk": []}}),
                 json.dumps({"uci": {"nama": "U", "induk": []}}),
                 json.dumps({"uci": {"nama": "U", "peran": None, "induk": []}}),
                 json.dumps({"uci": {"nama": "U", "peran": "x", "induk": "ajeng"}}),
                 json.dumps({"uci": {"nama": "U", "peran": "x", "induk": [""]}}),
                 json.dumps({"uci": {"nama": "U", "peran": "x", "induk": [5]}}),
                 json.dumps({"uci": ["U"]}), json.dumps(dict(CFG, beta={"nama": "B", "peran": "x", "induk": [None]}))]
        for n, isi in enumerate(rusak):
            with self.subTest(isi=isi):
                self.config(d, isi)
                h = d.siklus(f"2026-10-16T15:00:{n + 1:02d}+07:00")["akbar"]
                self.assertEqual([GALAT_AGEN], h["galat"])
                self.assertEqual([], h["peringatan"])
                self.assertEqual(("Uci", "QA/QC"), (agen(h, "uci")["nama"], agen(h, "uci")["peran"]))
                self.assertEqual(["ajeng", "desy", "via", "uci", "alfa", "beta", "carli"], ids(h))
        os.remove(d.agen_uji)
        h = d.siklus("2026-10-16T15:00:30+07:00")["akbar"]
        self.assertEqual(([GALAT_AGEN], "QA/QC"), (h["galat"], agen(h, "uci")["peran"]))
        self.config(d, dict(CFG, uci={"nama": "Uci", "peran": "QC baru", "induk": ["ajeng"]}))
        h = d.siklus("2026-10-16T15:00:33+07:00")["akbar"]
        self.assertEqual(([], "QC baru"), (h["galat"], agen(h, "uci")["peran"]))

    def test_urutan_config_lalu_ajeng_lalu_urut_id_kunci_lain_dan_entri_tak_hadir(self):
        cfg = {"via": dict(CFG["via"], warna="biru"), "zeta": {"nama": "Zeta", "peran": "x", "induk": ["ajeng"]},
               "carli": {"nama": "Carli", "peran": "kontak 0812345678901", "induk": ["via"]}}
        d = self.dunia_agen(profil=LAMA, cfg=cfg)
        h = d.siklus()["akbar"]
        self.assertEqual(["via", "carli", "ajeng", "alfa", "beta", "desy"], ids(h))
        self.assertEqual({"id": "via", "nama": "Via", "peran": "Riset dan peraturan", "induk": ["ajeng"], "status": "bebas",
                          "terakhir_aktif": None, "ruang": "riset", "keadaan": "bebas", "misi_aktif": []}, agen(h, "via"))
        self.assertEqual(("(disaring)", ["via"]), (agen(h, "carli")["peran"], agen(h, "carli")["induk"]))
        self.assertEqual(sorted(p1(i) for i in ("ajeng", "alfa", "beta", "desy")), h["peringatan"])
        self.assertEqual([], h["galat"])

class UjiDeskripsi(AgenDasar):
    """(f) D7: parser minimal `description` profile.yaml → peran bawaan (penyaring §3.7, potong 120)."""

    def test_bentuk_description(self):
        kasus = {
            "q01": ("description: 'Satu ''dua''\n  tiga.'\ndescription_auto: false\n", "Satu 'dua' tiga."),
            "q02": ("description: Polos tanpa kutip\n  lanjut baris.\nlain: x\n  bukan lanjutan\n", "Polos tanpa kutip lanjut baris."),
            "q03": ('description: "Ganda \\"kutip\\" dan \\\\ miring\n  terlipat."\n', 'Ganda "kutip" dan \\ miring terlipat.'),
            "q04": ("description: 'kontak x@y.z'\n", "(disaring)"),
            "q05": ("description: '" + "a" * 200 + "'\n", "a" * 120),
            "q06": ("lain: 1\ndescription_auto: false\n", ""),
            "q07": ("description: 'tak tertutup\n  sama sekali\n", ""),
            "q08": ("description: |\n  baris satu\n\n  baris dua\nlain: 2\n", "baris satu baris dua"),
            "q09": ("description: >-\n  lipat   satu\n  lipat dua\n", "lipat satu lipat dua"),
            "q10": ("  description: 'menjorok bukan kolom 0'\n", ""),
            "q11": ("description_auto: false\ndescription: 'baris kedua'\n", "baris kedua"),
            "q12": ("description: 'nomor 3171234567890123'\n", "(disaring)"),
            "q13": ('description: "tak tertutup \\"\n', ""),
            "q14": ("description: '  spasi    beruntun  '\n", "spasi beruntun"),
            "q15": ("description: ''\n", ""),
            "q16": ("description: 'é" + "b" * 130 + "'\n", "é" + "b" * 119),
        }
        d = self.dunia_agen(profil=LAMA)
        for i, (y, _) in kasus.items():
            self.profil(d, i, y)
        h = d.siklus()["akbar"]
        for i, (_, harap) in kasus.items():
            with self.subTest(i):
                self.assertEqual((harap, ["ajeng"], i.capitalize()), (agen(h, i)["peran"], agen(h, i)["induk"], agen(h, i)["nama"]))
        self.assertEqual(sorted(p1(i) for i in kasus), h["peringatan"])


class UjiBukanAgen(AgenDasar):
    """(g) P2 (id tetap), .deleted, folder tanpa profile.yaml, FIFO, nama tidak sah, berkas biasa."""

    def test_bentrok_deleted_kosong_fifo_dan_nama_tak_sah(self):
        d = self.dunia_agen(profil=LAMA)
        for i in ("ajeng", "akbar", "dicky", "jati", "a" * 64, "ok_1", "9z"):
            self.profil(d, i, "description: 'palsu'\n")
        for i in ("Zeta", "-x", "_x", "a" * 65, "a.b", ".deleted"):
            self.profil(d, i, "description: 'tak sah'\n")
        (d.profil_uji / "kosong").mkdir()
        (d.profil_uji / "pipa").mkdir()
        os.mkfifo(d.profil_uji / "pipa" / "profile.yaml")
        (d.profil_uji / "map").mkdir()
        (d.profil_uji / "map" / "profile.yaml").mkdir()
        (d.profil_uji / "berkas").write_text("description: 'x'\n")
        os.mkfifo(d.profil_uji / "fifo-atas")
        r = self.cli(d)  # proses terpisah + timeout: FIFO tidak boleh memblokir
        self.assertEqual(0, r.returncode, r.stderr[-300:])
        for p, h in d.baca().items():
            self.assertEqual(["ajeng", "desy", "via", "alfa", "beta", "carli", "9z", "a" * 64, "ok_1"], ids(h))
            self.assertEqual(("Ajeng", "Koordinator", ["dicky", "jati"]),
                             (agen(h, "ajeng")["nama"], agen(h, "ajeng")["peran"], agen(h, "ajeng")["induk"]))
            self.assertEqual(sorted([p1("9z"), p1("a" * 64), p1("ok_1")] + [p2(i) for i in ("ajeng", "akbar", "dicky", "jati")]),
                             h["peringatan"])
            self.assertEqual([], h["galat"])
            self.assertEqual("Ok_1", agen(h, "ok_1")["nama"])

    def test_config_fifo_tidak_memblokir(self):
        d = self.dunia_agen(profil=LAMA, cfg=None)
        os.mkfifo(d.agen_uji)
        r = self.cli(d)  # timeout 30 dtk: FIFO tidak boleh memblokir; belum pernah sah, siklus gagal terlihat
        self.assertEqual(1, r.returncode, r.stderr[-300:])
        self.assertIn("siklus gagal: ConfigTimTidakSah", r.stdout)

    def test_peringatan_lewat_penyaring(self):
        d = self.dunia_agen(profil=LAMA)
        self.profil(d, "x1234567890")
        self.assertEqual(["(disaring)"], d.siklus()["akbar"]["peringatan"])


class UjiGolongan(AgenDasar):
    """(h) TL = agen hadir (≠ desy) ber-induk desy; lock sah hanya tl= ∈ TL; teks memakai nama efektif."""

    def test_lock_tl_non_tl_diabaikan_dan_tl_dari_induk_desy(self):
        cfg = dict(CFG, zeta={"nama": "Zeta", "peran": "TL baru", "induk": ["desy"]})
        d = self.dunia_agen(profil=LAMA + ("uci", "zeta"), cfg=cfg)
        for slug, tl in (("proj-a", "alfa"), ("proj-u", "uci"), ("proj-d", "desy"), ("proj-v", "via"), ("proj-z", "zeta"),
                         ("proj-q", "qq"), ("proj-j", "ajeng")):
            d.lock(slug, tl)
        d.desy(2001)
        d.proses(2002, HERMES + ["-p", "zeta", "-z", "KANARI-z"])
        d.tambah(tim("2026-10-16T14:50:00", "desy", "terminal", '/opt/hermes/.venv/bin/hermes -p zeta -z "KANARI"'),
                 ajeng_tool("2026-10-16T14:51:00", "Pak Akbar", "terminal", "hermes -p alfa -z KANARI"))
        h = d.siklus()["akbar"]
        self.assertEqual(["lock-proj-a", "lock-proj-z", "proses-2001"], sorted(t["id"] for t in h["tugas_aktif"]
                                                                           if t["pengerja_id"] != "ajeng"))
        self.assertEqual(("Zeta", "jalan"), (tugas(h, "lock-proj-z")["pengerja"], tugas(h, "lock-proj-z")["status"]))
        self.assertEqual("memanggil TL Zeta", tugas(h, "proses-2001")["langkah_terakhir"])
        self.assertEqual("memanggil TL Alfa", tugas(h, "ajeng-akbar")["langkah_terakhir"])
        self.assertEqual({"ajeng": "jalan", "desy": "jalan", "via": "bebas", "uci": "bebas", "alfa": "menunggu",
                          "beta": "bebas", "carli": "bebas", "zeta": "jalan"}, {a["id"]: a["status"] for a in h["agen"]})
        t = teks(h)
        self.assertIn("Desy memanggil Zeta", t)
        self.assertIn("Zeta mulai proj-z", t)
        self.assertNotIn("Ajeng memanggil Alfa", t)
        self.assertEqual([], [x for x in t if "Uci" in x or "Via" in x])

    def test_teks_memakai_nama_efektif_id_terpisah(self):
        cfg = dict(CFG, uci={"nama": "Uci QC", "peran": "QA/QC", "induk": ["ajeng"]},
                   alfa={"nama": "Alfa Satu", "peran": "Tech Lead", "induk": ["desy"]})
        d = self.dunia_agen(cfg=cfg)
        d.lock("jdih-v3", "alfa", brief=d.brief("j.md", "# Brief TL — jdih-v3 — 2026-10-16 — Cek", "**Peminta:** Mas Jati"))
        self.uci_bekerja(d)
        d.desy(2001, z="# Brief untuk Desy — Satu\n**Peminta:** Mas Jati\n\nKANARI")
        d.brief("d.md", "# Brief untuk Desy — Satu", "**Peminta:** Mas Jati")
        d.siklus()
        d.tambah(tim("2026-10-16T14:58:00", "desy", "terminal", "hermes -p alfa -z KANARI", sid="KANARI-D2"),
                 tim("2026-10-16T14:58:30", "uci", "mcp__obsidian_bsk__setor", sid="KANARI-U3"))
        d.lock("policytrack", "alfa")
        os.remove(d.locks / "jdih-v3.lock")
        hasil = d.siklus("2026-10-16T15:00:03+07:00")
        h, jt = hasil["akbar"], hasil["jati"]
        t = teks(h)
        for x in ("Ajeng memanggil Uci QC", "Uci QC mulai bekerja", "Uci QC menyetor dokumen ke bank dokumen",
                  "Alfa Satu mulai JDIH", "Alfa Satu selesai JDIH", "Alfa Satu mulai PolicyTrack", "Desy memanggil Alfa Satu"):
            self.assertIn(x, t)
        self.assertEqual(("Uci QC", "uci"), (tugas(h, "proses-7001")["pengerja"], tugas(h, "proses-7001")["pengerja_id"]))
        self.assertEqual(("Alfa Satu", "alfa"), (tugas(h, "lock-policytrack")["pengerja"], tugas(h, "lock-policytrack")["pengerja_id"]))
        self.assertEqual("memanggil TL Alfa Satu", tugas(h, "proses-2001")["langkah_terakhir"])
        # pemilik "Desy memanggil <TL>" dihitung dari id (tugas Desy milik Mas Jati), bukan dari nama tampil
        self.assertIn("Desy memanggil Alfa Satu", teks(jt))

    def test_alternasi_terpanjang_dulu_dan_golongan_kosong(self):
        d = self.dunia_agen(profil=("ab", "ab-c"), cfg={})
        d.tambah(ajeng_tool("2026-10-16T14:59:00", "Pak Akbar", "terminal", "hermes -p ab-c -z KANARI"))
        h = d.siklus()["akbar"]
        self.assertEqual(["Ajeng memanggil Ab-c"], teks(h))
        self.assertEqual(["ajeng", "ab", "ab-c"], ids(h))
        d2 = self.dunia_agen(profil=(), cfg={})
        d2.tambah(ajeng_tool("2026-10-16T14:59:00", "Pak Akbar", "terminal", "hermes -p  KANARI -p x"),
                  tim("2026-10-16T14:59:01", "desy", "terminal", "hermes -p alfa"))
        h2 = d2.siklus()["akbar"]
        self.assertEqual((["ajeng"], [], [p1("ajeng")]), (ids(h2), h2["riwayat_hari_ini"], h2["peringatan"]))
        self.assertEqual("menjalankan perintah", tugas(h2, "ajeng-akbar")["langkah_terakhir"])

    def test_tanpa_tl_lock_diabaikan_dan_panggilan_jadi_anggota(self):
        d = self.dunia_agen(profil=LAMA, cfg={})
        d.lock("jdih-v3", "alfa")
        d.tambah(tim("2026-10-16T14:59:00", "desy", "terminal", "hermes -p alfa -z KANARI"),
                 ajeng_tool("2026-10-16T14:59:10", "Pak Akbar", "terminal", "hermes -p beta -z KANARI"))
        h = d.siklus()["akbar"]
        self.assertEqual([], [t for t in h["tugas_aktif"] if t["id"].startswith("lock-")])
        self.assertEqual(["Ajeng memanggil Beta"], [x for x in teks(h) if "memanggil" in x])


class UjiFolderProfil(AgenDasar):
    """(i) folder profil tidak terbaca → galat + daftar profil terakhir yang terbaca (belum pernah → kosong)."""

    def test_folder_profil_tidak_terbaca(self):
        d = self.dunia_agen()
        shutil.rmtree(d.profil_uji)
        h = d.siklus()["akbar"]
        self.assertEqual(([GALAT_PROFIL], ["ajeng"], []), (h["galat"], ids(h), h["peringatan"]))
        self.assertEqual("Koordinator", agen(h, "ajeng")["peran"])
        d.profil_uji.mkdir()
        for i in LAMA + ("uci", "akbar"):
            self.profil(d, i)
        h = d.siklus("2026-10-16T15:00:03+07:00")["akbar"]
        self.assertEqual(([], [p2("akbar")]), (h["galat"], h["peringatan"]))
        shutil.rmtree(d.profil_uji)
        d.profil_uji.write_text("bukan folder")
        h2 = d.siklus("2026-10-16T15:00:06+07:00")["akbar"]
        self.assertEqual([GALAT_PROFIL], h2["galat"])
        self.assertEqual((h["agen"], h["peringatan"]), (h2["agen"], h2["peringatan"]))


class UjiCLIAgen(AgenDasar):
    """(j) bawaan CLI + kata kunci konstruktor."""

    def test_bawaan_parser_tim_dan_profil(self):
        a = generator.buat_parser().parse_args([])
        akar = os.path.dirname(os.path.dirname(os.path.realpath(generator.__file__)))
        self.assertEqual((None, None), (a.tim, a.profil))  # bawaan profil = sumber.profil di tim.json
        with mock.patch.dict(os.environ, {"AD_TIM": ""}):
            self.assertEqual(os.path.join(akar, "conf", "tim.json"), str(generator.tim_dari(None)))
        with mock.patch.dict(os.environ, {"AD_TIM": "/x/dari-env.json"}):
            self.assertEqual("/x/dari-env.json", str(generator.tim_dari(None)))  # env > bawaan
            self.assertEqual("/x/arg.json", str(generator.tim_dari("/x/arg.json")))  # argumen > env

    def test_konstruktor_mewajibkan_tim(self):
        d = self.dunia_agen()
        with self.assertRaises(TypeError):
            generator.Generator(activity=d.activity, workspace=d.workspace, proc=d.proc, proyek=d.proyek, keluaran=d.keluaran)

    def test_cli_meneruskan_agen_dan_profil(self):
        d = self.dunia_agen()
        self.uci_bekerja(d)
        r = self.cli(d)
        self.assertEqual(0, r.returncode, r.stderr[-300:])
        self.assertEqual(0, (r.stdout + r.stderr).count("KANARI"))
        h = d.baca()["akbar"]
        self.assertEqual(("jalan", "QA/QC"), (agen(h, "uci")["status"], agen(h, "uci")["peran"]))


class UjiKode(AgenDasar):
    """D5: daftar agen tidak lagi konstanta di kode."""

    def test_tanpa_literal_nama_agen_dan_konstanta_lama(self):
        src = (ROOT / "script" / "generator.py").read_text(encoding="utf-8")
        pohon = ast.parse(src)
        doc = ast.get_docstring(pohon, clean=False)
        nama = re.compile(r"\b(alfa|beta|carli|via|uci)\b", re.I)
        temu = [(n.lineno, n.value[:40]) for n in ast.walk(pohon)
                if isinstance(n, ast.Constant) and isinstance(n.value, str) and n.value != doc and nama.search(n.value)]
        self.assertEqual([], temu)
        tetap = [t.id for n in pohon.body if isinstance(n, ast.Assign) for t in n.targets
                 if isinstance(t, ast.Name) and t.id in ("AGEN", "TL", "TIM", "RE_TL", "RE_DV")]
        self.assertEqual([], tetap)


if __name__ == "__main__":
    import unittest
    unittest.main()
