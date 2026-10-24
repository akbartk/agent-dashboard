"""Uji TL Delta & Echo di generator dashboard (paket tim-tl-baru, 24 Okt 2026). Data fiktif.

Delta/echo harus diperlakukan SAMA dengan alfa: golongan TL (induk desy), "memanggil TL <Nama>", pemegang lock,
status dari proses `hermes -p <id>`. Atribut dari `agen` di config tim fixture (tests/fixtures/skenario1/tim.json).
Letakkan di tests/generator/ lalu: python3 -m unittest discover -s tests/generator -p 'test_tl_baru.py'
"""
import json
import os
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_generator as tg  # noqa: E402
from test_generator import Dasar, agen, tim, teks, tugas  # noqa: E402

generator = tg.generator
TL5 = ("alfa", "beta", "carli", "delta", "echo")
BARU = ("delta", "echo")


class UjiTLBaru(Dasar):
    def bangun(self):
        d = self.buat()
        for i in BARU:
            (d.profil / i).mkdir()
            (d.profil / i / "profile.yaml").write_text(f"description: 'Profil uji {i}.'\n", encoding="utf-8")
        return d

    def test_lima_tl_dimuat_sebagai_tech_lead_di_bawah_desy(self):
        h = self.bangun().siklus()["akbar"]
        self.assertEqual([], h["galat"])
        self.assertEqual([], h["peringatan"])
        got = [(a["id"], a["nama"], a["peran"], a["induk"], a["ruang"]) for a in h["agen"] if a["id"] in TL5]
        self.assertEqual([(i, i.capitalize(), "Tech Lead", ["desy"], "teknik") for i in TL5], got)
        self.assertEqual(["ajeng", "desy", "via"] + list(TL5), [a["id"] for a in h["agen"]])

    def test_alfa_delta_echo_atribut_identik_selain_id_dan_nama(self):
        h = self.bangun().siklus()["akbar"]
        ref = {k: v for k, v in agen(h, "alfa").items() if k not in ("id", "nama")}
        for i in BARU:
            with self.subTest(i=i):
                self.assertEqual(ref, {k: v for k, v in agen(h, i).items() if k not in ("id", "nama")})

    def test_desy_memanggil_tl(self):
        for i in TL5:
            with self.subTest(i=i):
                d = self.bangun()
                d.tambah(tim("2026-10-16T14:00:00", "desy", "terminal", f"hermes -p {i} -z KANARI", sid="KANARI-A"))
                self.assertIn(f"Desy memanggil {i.capitalize()}", teks(d.siklus()["akbar"]))
                d2 = self.bangun()
                d2.tambah(tim("2026-10-16T14:00:00", "desy", "terminal", f"/opt/hermes/.venv/bin/hermes -p {i}",
                              sid="KANARI-A"))
                self.assertIn(f"Desy memanggil {i.capitalize()}", teks(d2.siklus()["akbar"]))

    def test_hanya_desy_dicatat_memanggil_tl_dan_echo_shell_bukan_panggilan(self):
        d = self.bangun()
        d.tambah(tim("2026-10-16T14:00:00", "delta", "terminal", "hermes -p echo -z KANARI", sid="KANARI-A"),
                 tim("2026-10-16T14:00:01", "desy", "terminal", "echo -p echo; echo delta alfa", sid="KANARI-B"))
        t = teks(d.siklus()["akbar"])
        self.assertEqual([], [x for x in t if "memanggil" in x], t)

    def test_pemegang_lock_delta_echo_menjadi_tugas_aktif(self):
        for i in TL5:
            with self.subTest(i=i):
                d = self.bangun()
                d.lock("jdih-v3", i, brief=d.brief("b.md", "# Brief TL — jdih-v3 — Cek", "**Peminta:** Mas Dicky (operator)"))
                d.tambah(tim("2026-10-16T14:59:00", i, "write_file"))
                t = tugas(d.siklus()["akbar"], "lock-jdih-v3")
                self.assertIsNotNone(t)
                self.assertEqual((i, i.capitalize()), (t["pengerja_id"], t["pengerja"]))

    def test_status_dari_proses_hermes_p_id(self):
        for i in TL5:
            with self.subTest(i=i):
                d = self.bangun()
                d.proses(7100, tg.HERMES + ["-p", i, "-z", "uji KANARI"], "2026-10-16T14:00:00+07:00")
                h = d.siklus()["akbar"]
                self.assertEqual("jalan", agen(h, i)["status"])
                for lain in TL5:
                    if lain != i:
                        self.assertEqual("bebas", agen(h, lain)["status"], lain)


if __name__ == "__main__":
    unittest.main()
