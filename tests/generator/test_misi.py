"""Uji misi "Kantor Agen" — definisi misi B1–B8 + riwayat C3–C5 (TL Beta, 24 Okt 2026).

Kontrak: /workspace/agent-dashboard/kantor-agen/KONTRAK-kantor-agen.md bagian B/C; aturan tertulis di docs/misi.md.
Fixture: tests/fixtures/misi1 (dibangun ulang: python3 tests/fixtures/bangun_misi1.py). Semua data fiktif.
Jalankan dari root project: PYTHONDONTWRITEBYTECODE=1 TMPDIR=$PWD/tmp/test python3 -m unittest discover -s tests/generator
"""
import json
import os
import re
import sqlite3
import stat
import subprocess
import sys
import unittest
from datetime import datetime
from unittest import mock

from bantu_misi import (B, GALAT_NOMOR, GALAT_SESI, ID, PENONTON, ROOT, DasarMisi, agen, generator, misi,
                        riwayat, t)


class UjiB1Misi(DasarMisi):
    def test_misi_hanya_dari_baris_msg_pertama_sesi_utama_yang_sama_dengan_h1_unik(self):
        d = self.buat()
        h = d.siklus()
        # tujuh brief menjadi misi (enam dimuat hari ini; T-001 selesai kemarin); H1 ganda, bukan-H1, sub, Ajeng,
        # sid kosong, dan text beda satu karakter tidak pernah menjadi misi
        reg = json.loads(d.nomor.read_text(encoding="utf-8"))
        self.assertEqual({B[k]: int(ID[k][2:]) for k in "GABCDEF"}, reg["nomor"])
        self.assertEqual(["T-002", "T-003", "T-004", "T-005", "T-006", "T-007"],
                         sorted(m["id"] for m in h["akbar"]["misi"]))

    def test_sesi_tanpa_kecocokan_tetap_mulai_bekerja(self):
        h = self.buat().siklus()["akbar"]
        mulai = [(p, x) for p, x, m in riwayat(h) if x.endswith("mulai bekerja")]
        # H1 ganda (desy 10:52), text beda (desy 10:53), sid kosong (alfa 10:54), brief bukan H1 (via 10:55)
        self.assertEqual([("desy", "Desy mulai bekerja"), ("desy", "Desy mulai bekerja"), ("alfa", "Alfa mulai bekerja"),
                          ("via", "Via mulai bekerja")], mulai)
        self.assertTrue(all(m is None for p, x, m in riwayat(h) if x.endswith("mulai bekerja")))

    def test_baris_tool_sebelum_msg_pertama_mulai_bekerja_diganti_k3(self):
        d = self.buat()
        d.siklus()
        h1 = "# Brief QA — 2026-10-24 — Uji Kanari-Jati-Intan"
        d.tambah_baris({"type": "tool", "role": "tim", "name": "Uci", "profile": "uci", "sid": "KANARI-SID-F3",
                        "tool": "read_file", "detail": "KANARI", "blocked": False, "ts": "2026-10-24T11:31:00"})
        h = d.siklus(t("11:31:05"))["akbar"]
        self.assertIn(("uci", "Uci mulai bekerja", None), riwayat(h))
        d.tambah_baris({"type": "msg", "role": "tim", "name": "Uci", "profile": "uci", "sid": "KANARI-SID-F3",
                        "text": h1 + "\nKANARI-t", "ts": "2026-10-24T11:31:10"})
        r = riwayat(d.siklus(t("11:31:15"))["akbar"])
        self.assertEqual(4, sum(1 for x in r if x[1].endswith("mulai bekerja")))  # yang dari sesi F3 dibuang (C4)
        self.assertIn(("uci", "Uci melanjutkan T-007", "T-007"), r)

    def test_beberapa_sesi_brief_sama_satu_misi_dan_kecocokan_dibekukan(self):
        d = self.buat()
        d.siklus()
        # brief B diganti H1-nya sesudah siklus 1: sesi lama tetap misi B (dibekukan)
        p = d.akar / "workspace" / "brief" / B["B"]
        p.write_text("# Brief TL — agent-dashboard — 2026-10-24 — Judul baru Kanari-Akbar-Berlian\n"
                     "Peminta asal: Pak Akbar lewat Ajeng.\nKANARI-ISI\n", encoding="utf-8")
        h = d.siklus(t("11:31:00"))["akbar"]
        m = misi(h, "T-003")
        self.assertEqual("Judul baru Kanari-Akbar-Berlian", m["judul"])
        self.assertEqual("beta", m["pelaksana_id"])
        self.assertEqual(1, sum(1 for x in h["misi"] if x["pelaksana_id"] == "beta"))


class UjiB2Nomor(DasarMisi):
    def test_registri_ditulis_atomik_0640_hanya_bila_berubah(self):
        d = self.buat()
        d.siklus()
        self.assertEqual(0o640, stat.S_IMODE(os.stat(d.nomor).st_mode))
        reg = json.loads(d.nomor.read_text(encoding="utf-8"))
        self.assertEqual(1, reg["versi"])
        self.assertEqual(sorted(os.listdir(d.nomor.parent)), ["nomor.json"])
        ino, mt = os.stat(d.nomor).st_ino, os.stat(d.nomor).st_mtime_ns
        d.siklus(t("11:30:03"))
        self.assertEqual((ino, mt), (os.stat(d.nomor).st_ino, os.stat(d.nomor).st_mtime_ns), "ditulis ulang tanpa perubahan")

    def test_nomor_stabil_antar_siklus_dan_antar_instance_baru(self):
        d = self.buat()
        h1 = d.siklus()["akbar"]
        h2 = d.siklus(t("11:30:03"))["akbar"]
        g2 = d.generator(nomor=d.nomor)  # instance baru, registri sama
        h3 = d.siklus(g=g2)["akbar"]
        peta = lambda h: {m["judul"]: m["id"] for m in h["misi"]}
        self.assertEqual(peta(h1), peta(h2))
        self.assertEqual(peta(h1), peta(h3))
        self.assertEqual("T-003", peta(h1)["Generator Kanari-Akbar-Berlian (Beta)"])

    def test_registri_ada_dihormati_dan_brief_baru_dapat_maks_plus_1(self):
        d = self.buat()
        d.nomor.parent.mkdir(parents=True)
        d.nomor.write_text(json.dumps({"versi": 1, "nomor": {"lama-sekali.md": 40, B["C"]: 12}}), encoding="utf-8")
        h = d.siklus()["akbar"]
        reg = json.loads(d.nomor.read_text(encoding="utf-8"))["nomor"]
        # C tetap 12; sisanya urut baris log mulai 41 (G, A, B, D, E, F)
        self.assertEqual({"lama-sekali.md": 40, B["C"]: 12, B["G"]: 41, B["A"]: 42, B["B"]: 43, B["D"]: 44, B["E"]: 45,
                          B["F"]: 46}, reg)
        self.assertEqual("Audit Kanari-Jati-Zamrud", misi(h, "T-012")["judul"])
        self.assertEqual(43, misi(h, "T-043")["nomor"])

    def test_format_id_tiga_digit_nol_di_depan_dan_lebih(self):
        d = self.buat()
        d.nomor.parent.mkdir(parents=True)
        d.nomor.write_text(json.dumps({"versi": 1, "nomor": {"x.md": 999, B["A"]: 7}}), encoding="utf-8")
        h = d.siklus()["akbar"]
        self.assertIsNotNone(misi(h, "T-007"))
        self.assertIsNotNone(misi(h, "T-1001"))  # B = 999 + 2 (G=1000, B=1001)
        self.assertTrue(all(m["id"] == "T-%03d" % m["nomor"] for m in h["misi"]))

    def test_registri_tidak_ada_dibangun_dari_backfill_dan_dibuat_direktorinya(self):
        d = self.buat()
        self.assertFalse(d.nomor.parent.exists())
        d.siklus()
        self.assertTrue(d.nomor.is_file())

    def test_registri_rusak_galat_tidak_ditimpa_misi_kosong_lalu_pulih(self):
        rusak = [b"{bukan json", json.dumps({"versi": 2, "nomor": {}}).encode(), json.dumps({"versi": 1}).encode(),
                 json.dumps({"versi": 1, "nomor": {"a.md": 1, "b.md": 1}}).encode(),
                 json.dumps({"versi": 1, "nomor": {"a.md": True}}).encode(),
                 json.dumps({"versi": 1, "nomor": {"a.md": 0}}).encode(),
                 json.dumps({"versi": 1, "nomor": {"a.md": "3"}}).encode(), json.dumps([1]).encode()]
        for isi in rusak:
            with self.subTest(isi=isi[:30]):
                d = self.buat()
                d.nomor.parent.mkdir(parents=True)
                d.nomor.write_bytes(isi)
                h = d.siklus()
                for p in PENONTON:
                    self.assertIn(GALAT_NOMOR, h[p]["galat"])
                    self.assertEqual([], h[p]["misi"])
                    self.assertTrue(all(r["misi"] is None for r in h[p]["riwayat_hari_ini"]))
                    self.assertTrue(all(a["misi_aktif"] == [] for a in h[p]["agen"]))
                    self.assertFalse(any(re.search(r"\bT-\d{3,}\b", r["teks"]) for r in h[p]["riwayat_hari_ini"]))
                self.assertEqual(isi, d.nomor.read_bytes(), "registri rusak ditimpa")
                d.nomor.write_text(json.dumps({"versi": 1, "nomor": {}}), encoding="utf-8")
                h = d.siklus(t("11:30:03"))
                self.assertNotIn(GALAT_NOMOR, h["akbar"]["galat"])
                self.assertEqual(6, len(h["akbar"]["misi"]))

    def test_registri_berupa_direktori_adalah_galat(self):
        d = self.buat()
        d.nomor.mkdir(parents=True)
        h = d.siklus()
        self.assertIn(GALAT_NOMOR, h["akbar"]["galat"])
        self.assertTrue(d.nomor.is_dir())

    def test_registri_gagal_ditulis_adalah_galat_dan_misi_kosong(self):
        d = self.buat()
        d.nomor.parent.mkdir(parents=True)
        os.chmod(d.nomor.parent, 0o500)
        self.addCleanup(os.chmod, d.nomor.parent, 0o750)
        h = d.siklus()
        self.assertIn(GALAT_NOMOR, h["akbar"]["galat"])
        self.assertEqual([], h["akbar"]["misi"])
        self.assertEqual([], os.listdir(d.nomor.parent))

    def test_tanpa_path_registri_nomor_tetap_di_memori(self):
        d = self.buat(nomor=False)
        h1 = d.siklus()["akbar"]
        h2 = d.siklus(t("11:30:03"))["akbar"]
        self.assertEqual([m["id"] for m in h1["misi"]], [m["id"] for m in h2["misi"]])
        self.assertFalse(d.nomor.exists())


class UjiB3B5Atribut(DasarMisi):
    def test_judul_pemberi_project_pelaksana_rantai(self):
        h = self.buat().siklus()["akbar"]
        harapan = {
            "T-002": ("Induk Kanari-Akbar-Safir", None, None, "Pak Akbar", "akbar", "desy", "Desy", ["akbar", "ajeng", "desy"]),
            "T-003": ("Generator Kanari-Akbar-Berlian (Beta)", "agent-dashboard", "Agent Dashboard", "Pak Akbar", "akbar",
                      "beta", "Beta", ["akbar", "ajeng", "desy", "beta"]),
            "T-004": ("Audit Kanari-Jati-Zamrud", "searchenginebsk", "Search Engine BSK", "Mas Jati", "jati", "alfa", "Alfa",
                      ["jati", "ajeng", "desy", "alfa"]),
            "T-005": ("Rapikan Kanari-Dicky-Rubi", "policytrack", "PolicyTrack", "Mas Dicky", "dicky", "carli", "Carli",
                      ["dicky", "ajeng", "desy", "carli"]),
            # project dari nama berkas: kunci terpanjang (pemahaman-asn, bukan pemahaman) yang diikuti '-'
            "T-006": ("Kajian Kanari-Akbar-Mutiara", "pemahaman-asn", "Pemahaman ASN", "Pak Akbar", "akbar", "via", "Via",
                      ["akbar", "ajeng", "via"]),
            "T-007": ("Uji Kanari-Jati-Intan", None, None, "Mas Jati", "jati", "uci", "Uci", ["jati", "ajeng", "uci"]),
        }
        kunci = ("judul", "project", "project_nama", "pemberi", "pemberi_id", "pelaksana_id", "pelaksana", "rantai")
        for id, nilai in harapan.items():
            with self.subTest(id=id):
                m = misi(h, id)
                self.assertEqual(dict(zip(kunci, nilai)), {k: m[k] for k in kunci})
                self.assertIsNone(m["langkah_total"])

    def test_mulai_dari_baris_msg_pertama_sesi_pertama_dan_pelaksana_sesi_terakhir(self):
        d = self.buat()
        d.siklus()
        # sesi baru brief C oleh carli (profil lain) → pelaksana = carli (sesi terakhir), mulai tetap
        d.tambah_baris({"type": "msg", "role": "tim", "name": "Carli", "profile": "carli", "sid": "KANARI-SID-X",
                        "text": "# Brief TL — searchenginebsk — 2026-10-24 — Audit Kanari-Jati-Zamrud\nKANARI-t",
                        "ts": "2026-10-24T11:31:00"})
        m = misi(d.siklus(t("11:31:30"))["akbar"], "T-004")
        self.assertEqual(("carli", t("10:11:00")), (m["pelaksana_id"], m["mulai"]))

    def test_rantai_tanpa_pemberi_dan_pemberi_null(self):
        d = self.buat()
        p = d.akar / "workspace" / "brief" / B["F"]
        p.write_text("# Brief QA — 2026-10-24 — Uji Kanari-Jati-Intan\nTanpa baris peminta KANARI-ISI\n", encoding="utf-8")
        h = d.siklus()["akbar"]
        m = misi(h, "T-007")
        self.assertEqual((None, None, ["ajeng", "uci"]), (m["pemberi"], m["pemberi_id"], m["rantai"]))
        self.assertIn(("ajeng", "Order T-007 masuk lewat Ajeng → Uci", "T-007"), riwayat(h))


class UjiB6Status(DasarMisi):
    def test_semua_status_alasan_dan_rantai_ppid(self):
        h = self.buat().siklus()["akbar"]
        harapan = {"T-002": ("menunggu", "misi-lain", ["T-003"], None, None),
                   "T-003": ("jalan", None, [], "T-002", None),
                   "T-004": ("menunggu", "review", [], None, None),
                   "T-005": ("menunggu", "gantung", [], None, None),
                   "T-006": ("selesai", None, [], None, t("10:45:00")),
                   "T-007": ("berakhir", None, [], None, t("10:35:30"))}
        for id, (st, al, mm, ind, sel) in harapan.items():
            with self.subTest(id=id):
                m = misi(h, id)
                self.assertEqual((st, al, mm, ind, sel),
                                 (m["status"], m["alasan"], m["menunggu_misi"], m["induk_misi"], m["selesai"]))
        self.assertEqual(t("10:00:00"), misi(h, "T-002")["mulai"])

    def test_selesai_berakhir_hanya_bila_hari_ini_aktif_selalu(self):
        d = self.buat()
        h = d.siklus("2026-10-25T08:00:00+07:00")["akbar"]
        # hari berganti: selesai/berakhir 24 Okt hilang; aktif (proses/lock) tetap
        self.assertEqual(["T-002", "T-003", "T-004", "T-005"], sorted(m["id"] for m in h["misi"]))

    def test_transisi_proses_hilang_lock_hilang_laporan_ada(self):
        d = self.buat()
        d.siklus()
        # proses Beta (dan bash perantara) berhenti → Beta gantung (lock, tanpa laporan), Desy jalan, induk null
        for pid in ("3101", "3050"):
            for f in ("cmdline", "stat"):
                (d.akar / "proc" / pid / f).unlink()
            (d.akar / "proc" / pid).rmdir()
        h = d.siklus(t("11:31:00"))["akbar"]
        self.assertEqual(("menunggu", "gantung", None), (misi(h, "T-003")["status"], misi(h, "T-003")["alasan"],
                                                         misi(h, "T-003")["induk_misi"]))
        self.assertEqual(("jalan", None, []), (misi(h, "T-002")["status"], misi(h, "T-002")["alasan"],
                                               misi(h, "T-002")["menunggu_misi"]))
        lap = d.akar / "workspace" / "brief" / (B["B"][:-3] + ".laporan.txt")
        lap.write_text("", encoding="utf-8")
        self.assertEqual("gantung", misi(d.siklus(t("11:31:10"))["akbar"], "T-003")["alasan"])  # 0 byte = belum lapor
        lap.write_text("KANARI-laporan\n", encoding="utf-8")
        s = datetime.fromisoformat(t("11:31:15")).timestamp()
        os.utime(lap, (s, s))
        self.assertEqual("review", misi(d.siklus(t("11:31:20"))["akbar"], "T-003")["alasan"])
        (d.akar / "workspace" / "locks" / "agent-dashboard.lock").unlink()
        m = misi(d.siklus(t("11:31:30"))["akbar"], "T-003")
        self.assertEqual(("selesai", None, t("11:31:15")), (m["status"], m["alasan"], m["selesai"]))

    def test_laporan_bukan_berkas_biasa_dianggap_tidak_ada(self):
        d = self.buat()
        lap = d.akar / "workspace" / "brief" / (B["E"][:-3] + ".laporan.txt")
        lap.unlink()
        lap.mkdir()
        m = misi(d.siklus()["akbar"], "T-006")
        self.assertEqual(("berakhir", t("10:44:00")), (m["status"], m["selesai"]))

    def test_proses_header_tidak_unik_bukan_proses_misi(self):
        d = self.buat()
        d.siklus()
        # sesudah misi B tercocokkan (dibekukan), muncul salinan brief B dengan header sama → header -z proses Beta
        # cocok 2 berkas → bukan proses misi
        src = d.akar / "workspace" / "brief" / B["B"]
        (d.akar / "workspace" / "brief" / "2026-10-24-beta-salinan.md").write_bytes(src.read_bytes())
        h = d.siklus(t("11:30:03"))["akbar"]
        self.assertEqual(("menunggu", "gantung"), (misi(h, "T-003")["status"], misi(h, "T-003")["alasan"]))
        self.assertEqual("jalan", misi(h, "T-002")["status"])


class UjiB7Langkah(DasarMisi):
    def test_label_langkah_dari_catat_progres_sesi_utama_saja(self):
        h = self.buat().siklus()["akbar"]
        self.assertEqual([{"waktu": t("10:07:00"), "label": "Mulai"}, {"waktu": t("10:30:00"), "label": "Langkah"},
                          {"waktu": t("10:50:00"), "label": "Hambatan"},
                          {"waktu": t("11:01:00"), "label": "Kemajuan dicatat"},
                          {"waktu": t("11:05:00"), "label": "Kemajuan dicatat"}], misi(h, "T-003")["langkah"])
        self.assertEqual([{"waktu": t("10:40:00"), "label": "Selesai"}], misi(h, "T-004")["langkah"])
        self.assertEqual([{"waktu": t("10:44:00"), "label": "Selesai"}], misi(h, "T-006")["langkah"])
        self.assertEqual([], misi(h, "T-005")["langkah"])

    def test_langkah_sekarang_kategori_baris_terakhir_sesi_utama(self):
        h = self.buat().siklus()["akbar"]
        harapan = {"T-002": ("memanggil TL Beta", t("10:04:00")),
                   "T-003": ("menjalankan perintah di bskdev · Agent Dashboard", t("11:20:00")),
                   "T-005": ("membaca berkas · PolicyTrack", t("10:16:00")),
                   "T-007": ("menulis berkas", t("10:35:30"))}
        for id, nilai in harapan.items():
            with self.subTest(id=id):
                m = misi(h, id)
                self.assertEqual(nilai, (m["langkah_sekarang"], m["langkah_waktu"]))

    def test_baris_sid_sub_agen_mode_live_bukan_langkah_misi(self):
        d = self.buat()
        d.siklus()
        d.tambah_baris({"type": "tool", "role": "tim", "name": "Beta", "profile": "beta", "sid": "KANARI-SUB-2",
                        "tool": "mcp__obsidian_bsk__catat_progres", "detail": "Status: selesai KANARI", "blocked": False,
                        "ts": "2026-10-24T11:31:00"})
        h = d.siklus(t("11:31:05"))["akbar"]
        m = misi(h, "T-003")
        self.assertEqual(5, len(m["langkah"]))
        self.assertEqual(("menjalankan perintah di bskdev · Agent Dashboard", t("11:20:00")),
                         (m["langkah_sekarang"], m["langkah_waktu"]))
        self.assertEqual(("beta", "Beta mencatat kemajuan · Agent Dashboard", "T-003"), riwayat(h)[-1])  # C3: tetap ber-misi

    def test_label_berhenti_antre_dan_mode_live(self):
        d = self.buat()
        d.siklus()
        d.tambah()  # alfa sesi kedua 11:31 + catat antre 11:32
        d.tambah_baris({"type": "tool", "role": "tim", "name": "Alfa", "profile": "alfa", "sid": "KANARI-SID-C2",
                        "tool": "mcp__obsidian_bsk__catat_progres", "detail": "{\"entri\": \"**STATUS**: Berhenti KANARI\"}",
                        "blocked": False, "ts": "2026-10-24T11:32:30"})
        m = misi(d.siklus(d.langkah["siklus2"])["akbar"], "T-004")
        self.assertEqual(["Selesai", "Antre", "Berhenti"], [x["label"] for x in m["langkah"]])
        self.assertEqual(("mencatat kemajuan · Search Engine BSK", t("11:32:30")), (m["langkah_sekarang"], m["langkah_waktu"]))


class UjiB8SubAgen(DasarMisi):
    def test_subagen_dari_state_db_dan_kuota(self):
        h = self.buat().siklus()["akbar"]
        self.assertEqual([{"ke": 1, "mulai": t("10:20:00"), "selesai": t("10:40:00")},
                          {"ke": 2, "mulai": t("11:10:00"), "selesai": None}], misi(h, "T-003")["subagen"])
        self.assertEqual([{"ke": 1, "mulai": t("10:21:00"), "selesai": t("10:22:00")}], misi(h, "T-006")["subagen"])
        self.assertEqual([], misi(h, "T-002")["subagen"])
        kuota = {m["id"]: m["spawn_kuota"] for m in h["misi"]}
        self.assertEqual({"T-002": 10, "T-003": 10, "T-004": 10, "T-005": None, "T-006": 10, "T-007": 5}, kuota)
        self.assertNotIn(GALAT_SESI, h["galat"])

    def test_db_tak_terbaca_galat_dan_subagen_null_profil_itu_saja(self):
        for rusak in ("hapus", "bukan-db", "tanpa-tabel"):
            with self.subTest(rusak=rusak):
                d = self.buat()
                db = d.akar / "profiles" / "beta" / "state.db"
                db.unlink()
                if rusak == "bukan-db":
                    db.write_bytes(b"KANARI bukan sqlite " * 100)
                elif rusak == "tanpa-tabel":
                    sqlite3.connect(db).close()
                h = d.siklus()
                for p in PENONTON:
                    self.assertIn(GALAT_SESI, h[p]["galat"])
                a = h["akbar"]
                self.assertIsNone(misi(a, "T-003")["subagen"])
                self.assertEqual(1, len(misi(a, "T-006")["subagen"]))
                self.assertIsNone(a["ringkasan"]["subagen_aktif"])
                self.assertFalse(any("sub-agen" in r["teks"] and r["misi"] == "T-003" for r in a["riwayat_hari_ini"]))

    def test_kueri_state_db_hanya_empat_kolom_tanpa_bintang(self):
        d = self.buat()
        kueri = []
        asli = sqlite3.connect

        class Rekam:
            def __init__(self, con):
                self.con = con

            def execute(self, sql, *a):
                kueri.append(sql)
                return self.con.execute(sql, *a)

            def __getattr__(self, n):
                return getattr(self.con, n)

        def connect(*a, **kw):
            self.assertIn("mode=ro", str(a[0]))
            self.assertTrue(kw.get("uri"))
            self.assertLessEqual(kw.get("timeout", 5.0), 1.0)
            return Rekam(asli(*a, **kw))

        with mock.patch.object(generator.sqlite3, "connect", connect):
            d.siklus()
        self.assertTrue(kueri)
        for q in kueri:
            self.assertNotIn("*", q)
            m = re.fullmatch(r"\s*SELECT\s+(.*?)\s+FROM\s+sessions\s+WHERE\s+(.*)", q, re.S | re.I)
            self.assertIsNotNone(m, q)
            self.assertEqual(["id", "parent_session_id", "started_at", "ended_at"],
                             [c.strip() for c in m.group(1).split(",")])
            self.assertNotRegex(m.group(2), r"\b(title|user_id|model|end_reason)\b")


class UjiC1Ruang(DasarMisi):
    def test_ruang_dari_conf_dan_lain_bila_tanpa(self):
        d = self.buat()
        conf = json.loads((d.akar / "tim.json").read_text(encoding="utf-8"))
        del conf["agen"]["uci"]["ruang"]
        alt = d.akar / "tim2.json"
        alt.write_text(json.dumps(conf), encoding="utf-8")
        h = d.siklus(g=d.generator(nomor=d.nomor, tim=alt))["akbar"]
        self.assertEqual({"ajeng": "koordinasi", "desy": "teknik", "via": "riset", "uci": "lain", "alfa": "teknik",
                          "beta": "teknik", "carli": "teknik"}, {a["id"]: a["ruang"] for a in h["agen"]})

    def test_ruang_tidak_sah_menolak_seluruh_berkas(self):
        d = self.buat()
        h = d.siklus()
        conf = json.loads((d.akar / "tim.json").read_text(encoding="utf-8"))
        conf["agen"]["via"]["ruang"] = "dapur"
        conf["agen"]["via"]["nama"] = "Via Ganti"
        (d.akar / "tim.json").write_text(json.dumps(conf), encoding="utf-8")
        h = d.siklus(t("11:30:03"))["akbar"]
        self.assertIn("Config agen tidak terbaca", h["galat"])
        self.assertEqual(("Via", "riset"), (agen(h, "via")["nama"], agen(h, "via")["ruang"]))  # config sah terakhir

    def test_conf_tim_project_memuat_ruang_sesuai_kontrak(self):
        conf = json.loads((ROOT / "conf" / "tim.json").read_text(encoding="utf-8"))
        self.assertEqual({"default": "koordinasi", "arsa": "teknik", "sofi": "riset", "g7-qc": "qa",
                          **{f"g7-tl{i}": "teknik" for i in range(1, 6)}},
                         {i: e.get("ruang") for i, e in conf["agen"].items()})  # nilai g7 KONTRAK bagian 2


class UjiRiwayatMisi(DasarMisi):
    def test_k3_c3_c4_riwayat_akbar(self):
        h = self.buat().siklus()["akbar"]
        r = riwayat(h)
        catat_b = ("beta", "Beta mencatat kemajuan", "T-003")
        harus = [
            ("akbar", "Pak Akbar memberi order T-002 lewat Ajeng → Desy", "T-002"),       # 10:00 K3-1 (ganti C4)
            ("desy", "Desy mencatat kemajuan", "T-002"),
            ("desy", "Desy memanggil Beta", "T-002"),
            ("beta", "Beta mulai Agent Dashboard", "T-003"),                              # 10:05 lock misi
            ("akbar", "Pak Akbar memberi order T-003 lewat Ajeng → Desy → Beta", "T-003"),
            catat_b,                                                                     # 10:07
            ("alfa", "Alfa mulai Search Engine BSK", "T-004"),
            ("jati", "Mas Jati memberi order T-004 lewat Ajeng → Desy → Alfa", "T-004"),
            ("carli", "Carli mulai PolicyTrack", "T-005"),
            ("dicky", "Mas Dicky memberi order T-005 lewat Ajeng → Desy → Carli", "T-005"),
            ("akbar", "Pak Akbar memberi order T-006 lewat Ajeng → Via", "T-006"),         # 10:20 (baris log)
            ("beta", "Beta men-spawn sub-agen ke-1 · T-003", "T-003"),                    # 10:20 (K3-2, sesudahnya)
            ("via", "Via men-spawn sub-agen ke-1 · T-006", "T-006"),
            ("via", "Sub-agen ke-1 Via selesai · T-006", "T-006"),
            catat_b,                                                                     # 10:25 sid sub-agen (B8)
            ("jati", "Mas Jati memberi order T-007 lewat Ajeng → Uci", "T-007"),
            catat_b,                                                                     # 10:30
            ("uci", "T-007 berakhir tanpa laporan", "T-007"),                             # 10:35:30 K3-4
            ("alfa", "Alfa mencatat kemajuan", "T-004"),
            ("beta", "Sub-agen ke-1 Beta selesai · T-003", "T-003"),                      # 10:40 K3-3
            ("via", "Via melanjutkan T-006", "T-006"),                                    # 10:43 C4 sesi ke-2
            ("via", "Via mencatat kemajuan", "T-006"),
            ("via", "Via menyelesaikan T-006", "T-006"),                                  # 10:45 K3-4
            catat_b,                                                                     # 10:50
            ("beta", "Beta melanjutkan T-003", "T-003"),                                  # 11:00
            catat_b, catat_b,                                                            # 11:01, 11:05
            ("beta", "Beta men-spawn sub-agen ke-2 · T-003", "T-003"),                    # 11:10
        ]
        self.assertEqual(harus, [x for x in r if x[2] is not None])
        self.assertEqual(len(harus) + 5, len(r))  # + pesan Pak Akbar ke Ajeng + 4 "mulai bekerja" tanpa misi
        waktu = [x["waktu"] for x in h["riwayat_hari_ini"]]
        self.assertEqual(sorted(waktu), waktu)
        k31 = next(x for x in h["riwayat_hari_ini"] if x["teks"].startswith("Pak Akbar memberi order T-003"))
        self.assertEqual(t("10:06:00"), k31["waktu"])
        self.assertEqual(t("10:20:00"), next(x for x in h["riwayat_hari_ini"]
                                             if x["teks"] == "Beta men-spawn sub-agen ke-1 · T-003")["waktu"])
        # C4: tidak ada "mulai bekerja" untuk sid sesi utama misi; T-001 (kemarin) tidak memunculkan peristiwa
        self.assertNotIn(("beta", "Beta mulai bekerja", None), r)
        self.assertFalse(any("T-001" in x[1] for x in r))

    def test_mode_live_melanjutkan_dan_pemilik_misi(self):
        d = self.buat()
        d.siklus()
        d.tambah()
        h = d.siklus(d.langkah["siklus2"])
        self.assertIn(("alfa", "Alfa melanjutkan T-004", "T-004"), riwayat(h["jati"]))
        self.assertIn(("alfa", "Alfa mencatat kemajuan · Search Engine BSK", "T-004"), riwayat(h["jati"]))
        self.assertNotIn("Alfa melanjutkan T-004", [x[1] for x in riwayat(h["dicky"])])

    def test_akhiran_project_dibuang_bila_pemilik_heuristik_beda_dengan_pemilik_misi(self):
        d = self.buat()
        d.siklus()
        # sesi Beta baru untuk brief C (milik jati) saat Beta memegang lock agent-dashboard (milik akbar)
        d.tambah_baris({"type": "msg", "role": "tim", "name": "Beta", "profile": "beta", "sid": "KANARI-SID-Y",
                        "text": "# Brief TL — searchenginebsk — 2026-10-24 — Audit Kanari-Jati-Zamrud\nKANARI-t",
                        "ts": "2026-10-24T11:31:00"},
                       {"type": "tool", "role": "tim", "name": "Beta", "profile": "beta", "sid": "KANARI-SID-Y",
                        "tool": "mcp__obsidian_bsk__catat_progres", "detail": "KANARI", "blocked": False,
                        "ts": "2026-10-24T11:31:10"})
        h = d.siklus(t("11:31:30"))
        self.assertIn(("beta", "Beta mencatat kemajuan", "T-004"), riwayat(h["jati"]))
        self.assertNotIn("Agent Dashboard", json.dumps(h["jati"], ensure_ascii=False))


class UjiCli(DasarMisi):
    def test_argumen_nomor_bawaan_storage_misi_dan_dipakai(self):
        p = generator.buat_parser()
        self.assertEqual(ROOT / "storage" / "misi" / "nomor.json", p.parse_args([]).nomor)
        d = self.buat()
        nomor = d.akar / "cli" / "nomor.json"
        hasil = subprocess.run(
            [sys.executable, str(ROOT / "script" / "generator.py"), "--activity", str(d.akar / "activity.jsonl"),
             "--workspace", str(d.akar / "workspace"), "--proc", str(d.akar / "proc"), "--proyek", str(d.akar / "proyek.json"),
             "--tim", str(d.akar / "tim.json"), "--profil", str(d.akar / "profiles"), "--keluaran", str(d.keluaran),
             "--nomor", str(nomor), "--sekali", "--sekarang", d.langkah["siklus1"]],
            capture_output=True, text=True, timeout=60, env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"))
        self.assertEqual(0, hasil.returncode, hasil.stderr[-500:])
        self.assertEqual(0, (hasil.stdout + hasil.stderr).count("KANARI"))
        self.assertEqual(7, len(json.loads(nomor.read_text(encoding="utf-8"))["nomor"]))
        self.assertEqual(6, len(d.baca()["akbar"]["misi"]))


class UjiReviewLapis1(DasarMisi):
    """Temuan review lapis 1 (24 Okt 2026): jalur galat B2, judul TL B4/§3.5, akhiran heuristik A1/C3."""

    def brief_baru(self, nama, h1, peminta="Peminta asal: Pak Akbar lewat Ajeng."):
        (self.d.akar / "workspace" / "brief" / nama).write_text(f"{h1}\n\n{peminta}\nKANARI-isi\n", encoding="utf-8")

    def sesi(self, profil, sid, teks, ts):
        self.d.tambah_baris({"type": "msg", "role": "tim", "name": profil.capitalize(), "profile": profil, "sid": sid,
                             "text": teks + "\nKANARI-t", "ts": ts})

    def test_nama_brief_bukan_utf8_tidak_menjatuhkan_siklus_dan_nomor_stabil(self):
        self.d = d = self.buat()
        d.siklus()
        nama = os.fsdecode(b"2026-10-24-via-aneh-\xff.md")
        self.brief_baru(nama, "# Brief Riset — 2026-10-24 — Nama Aneh Kanari-Akbar-Giok")
        self.sesi("via", "KANARI-SID-U8", "# Brief Riset — 2026-10-24 — Nama Aneh Kanari-Akbar-Giok", "2026-10-24T11:31:00")
        h = d.siklus(t("11:31:05"))
        self.assertNotIn(GALAT_NOMOR, h["akbar"]["galat"])
        self.assertEqual("Nama Aneh Kanari-Akbar-Giok", misi(h["akbar"], "T-008")["judul"])
        h2 = d.siklus(t("11:31:10"), g=d.generator(nomor=d.nomor))
        self.assertEqual("Nama Aneh Kanari-Akbar-Giok", misi(h2["akbar"], "T-008")["judul"])

    def test_registri_rusak_galat_walau_belum_ada_misi(self):
        self.d = d = self.buat()
        (d.akar / "activity.jsonl").write_text("", encoding="utf-8")
        d.nomor.parent.mkdir(parents=True)
        d.nomor.write_bytes(b"{rusak")
        h = d.siklus()
        for p in PENONTON:
            self.assertIn(GALAT_NOMOR, h[p]["galat"])
            self.assertEqual([], h[p]["misi"])
        self.assertEqual(b"{rusak", d.nomor.read_bytes())

    def test_judul_tl_kosong_jadi_project_nama_dan_topik_berkas(self):
        # J-2 (CTO 24 Okt 2026, koreksi header): semula "Pekerjaan PolicyTrack"; topik kosong → tetap "Pekerjaan …"
        self.d = d = self.buat()
        d.siklus()
        self.brief_baru("2026-10-24-carli-policytrack-kosong.md", "# Brief TL — policytrack — 2026-10-24")
        self.sesi("carli", "KANARI-SID-JK", "# Brief TL — policytrack — 2026-10-24", "2026-10-24T11:31:00")
        m = misi(d.siklus(t("11:31:05"))["akbar"], "T-008")
        self.assertEqual(("PolicyTrack — kosong", "policytrack"), (m["judul"], m["project"]))

    def test_akhiran_heuristik_tetap_bila_pemilik_misi_akbar(self):
        self.d = d = self.buat()
        d.siklus()
        # sesi Alfa baru untuk brief B (milik akbar) saat Alfa memegang lock searchenginebsk (milik jati)
        self.sesi("alfa", "KANARI-SID-Z", "# Brief TL — agent-dashboard — 2026-10-24 — Generator Kanari-Akbar-Berlian (Beta)",
                  "2026-10-24T11:31:00")
        d.tambah_baris({"type": "tool", "role": "tim", "name": "Alfa", "profile": "alfa", "sid": "KANARI-SID-Z",
                        "tool": "mcp__obsidian_bsk__catat_progres", "detail": "KANARI", "blocked": False,
                        "ts": "2026-10-24T11:31:10"})
        h = d.siklus(t("11:31:30"))
        self.assertIn(("alfa", "Alfa mencatat kemajuan · Search Engine BSK", "T-003"), riwayat(h["akbar"]))
        self.assertNotIn(("alfa", "Alfa mencatat kemajuan · Search Engine BSK", "T-003"), riwayat(h["jati"]))
        self.assertFalse(any(r[2] == "T-003" for r in riwayat(h["jati"])))

    def test_c2_misi_campuran_jalan_dan_menunggu_adalah_bekerja(self):
        self.d = d = self.buat()
        d.siklus()
        h1 = "# Brief CTO — 2026-10-24 — Kedua Kanari-Akbar-Topas"
        self.brief_baru("2026-10-24-desy-kedua.md", h1)
        self.sesi("desy", "KANARI-SID-D2", h1, "2026-10-24T11:31:00")
        d.proses(3501, d.HERMES + ["-p", "desy", "-z", h1 + "\n\nPeminta asal: Pak Akbar lewat Ajeng."], 1)
        h = d.siklus(t("11:31:05"))["akbar"]
        self.assertEqual(("menunggu", "jalan"), (misi(h, "T-002")["status"], misi(h, "T-008")["status"]))
        self.assertEqual(("bekerja", ["T-002", "T-008"]), (agen(h, "desy")["keadaan"], agen(h, "desy")["misi_aktif"]))


if __name__ == "__main__":
    unittest.main()
