"""Uji fungsi murni script/pasang-hook.py (`ganti`, `uji_jalan`). Modul butuh ruamel/ssh/Hermes saat diimpor, jadi hanya
dua fungsi itu yang diekstrak lewat ast dan dijalankan di namespace terpisah. Keluaran uji di folder sementara."""
import ast
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from contextlib import redirect_stdout
from pathlib import Path

ASAL = Path(__file__).resolve().parent
AKAR = ASAL.parent.parent
HOOK = AKAR / "hooks" / "team-activity.py"
TIM_CONTOH = ASAL / "tim_contoh.json"


def muat():
    src = (AKAR / "script" / "pasang-hook.py").read_text(encoding="utf-8")
    pohon = ast.parse(src)
    fungsi = [n for n in pohon.body if isinstance(n, ast.FunctionDef) and n.name in ("ganti", "uji_jalan")]
    ns = {"Path": Path, "json": json, "os": os, "shutil": shutil, "stat": stat, "subprocess": subprocess, "sys": sys,
          "tempfile": tempfile, "time": time}
    exec(compile(ast.Module(fungsi, []), "pasang-hook", "exec"), ns)
    return ns


class GantiUji(unittest.TestCase):
    def setUp(self):
        self.ns = muat()
        self._d = tempfile.TemporaryDirectory()
        self.d = Path(self._d.name)

    def tearDown(self):
        self._d.cleanup()

    def jalan(self, *a):
        with redirect_stdout(io.StringIO()):
            return self.ns["ganti"](*a)

    def test_isi_sama_tanpa_cadangan(self):
        f = self.d / "h.py"
        f.write_bytes(b"x")
        self.assertFalse(self.jalan(f, b"x", "C1", 0o644))
        self.assertEqual(list(self.d.iterdir()), [f])

    def test_ganti_cadangan_bercap_dan_mode_dipertahankan(self):
        f = self.d / "h.py"
        f.write_bytes(b"lama")
        f.chmod(0o600)
        self.assertTrue(self.jalan(f, b"baru", "C1", 0o644))
        self.assertEqual(f.read_bytes(), b"baru")
        self.assertEqual(stat.S_IMODE(f.stat().st_mode), 0o600)
        self.assertEqual((self.d / "h.py.lama-C1").read_bytes(), b"lama")
        self.assertTrue(self.jalan(f, b"baru2", "C2", 0o644))  # cadangan pertama tidak tertimpa
        self.assertEqual((self.d / "h.py.lama-C1").read_bytes(), b"lama")
        self.assertEqual((self.d / "h.py.lama-C2").read_bytes(), b"baru")

    def test_gagal_membersihkan_baru(self):
        f = self.d / "h.py"
        f.write_bytes(b"lama")
        with self.assertRaises(TypeError), redirect_stdout(io.StringIO()):
            self.ns["ganti"](f, "bukan-bytes", "C1", 0o644)
        self.assertFalse((self.d / "h.py.baru").exists())
        self.assertEqual(f.read_bytes(), b"lama")

    def test_uji_jalan_hook_asli_lulus(self):
        self.ns["uji_jalan"](HOOK.read_bytes(), TIM_CONTOH.read_bytes())

    def test_uji_jalan_hook_rusak_berhenti(self):
        with self.assertRaises(SystemExit):
            self.ns["uji_jalan"](b"import sys\nsys.exit(3)\n", TIM_CONTOH.read_bytes())


if __name__ == "__main__":
    unittest.main()
