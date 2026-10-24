"""Uji kontrak generator (milik TL Beta; jangan diubah subagent). Kontrak: docs/skema-ringkasan.md versi skema "1".

Jalankan dari root project: python3 -m unittest discover -s tests/generator -v
Fixture dibangun ulang dengan: python3 tests/fixtures/bangun_fixture.py
"""
import contextlib
import io
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "script"))
from bantu_tim import muat as muat_tim, tulis_tim  # noqa: E402
FIXTURE = ROOT / "tests" / "fixtures"
PENONTON = tuple(muat_tim()["penonton"])  # DATA uji: config tim fixture


def jalankan_skenario(nama, tmp):
    """Salin fixture ke tmp, jalankan siklus1 → perubahan → siklus2. Kembalikan (keluaran, teks stdout+stderr)."""
    import generator  # noqa: E402  (diimpor di sini agar kegagalan impor = kegagalan uji, bukan galat modul)

    src = FIXTURE / nama
    kerja = Path(tmp) / nama
    shutil.copytree(src, kerja, symlinks=True)
    langkah = json.loads((kerja / "langkah.json").read_text(encoding="utf-8"))
    keluaran = kerja / "keluaran"
    g = generator.Generator(activity=kerja / "activity.jsonl", workspace=kerja / "workspace", proc=kerja / "proc",
                            proyek=kerja / "proyek.json", keluaran=keluaran, tim=tulis_tim(kerja / "tim.json", kerja, dasar=kerja / "tim.json"),
                            profil=kerja / "profiles")
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
        g.siklus(datetime.fromisoformat(langkah["siklus1"]))
        siklus1 = {p: json.loads((keluaran / f"{p}.json").read_text(encoding="utf-8")) for p in PENONTON}
        ubah = langkah["perubahan"]
        if "tambah_activity" in ubah:
            with open(kerja / "activity.jsonl", "a", encoding="utf-8") as f:
                f.write((kerja / ubah["tambah_activity"]).read_text(encoding="utf-8"))
        if "ganti_activity" in ubah:
            with open(kerja / "activity.jsonl", "w", encoding="utf-8") as f:   # inode tetap, ukuran mengecil
                f.write((kerja / ubah["ganti_activity"]).read_text(encoding="utf-8"))
        for n in ubah.get("hapus_lock", []):
            (kerja / "workspace" / "locks" / n).unlink()
        g.siklus(datetime.fromisoformat(langkah["siklus2"]))
    return kerja, keluaran, siklus1, langkah, buf.getvalue()


class UjiKontrak(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="uji-kontrak-")
        self.addCleanup(shutil.rmtree, self.tmp, True)

    def periksa(self, nama):
        kerja, keluaran, siklus1, langkah, log = jalankan_skenario(nama, self.tmp)
        for p in PENONTON:
            with self.subTest(skenario=nama, penonton=p):
                aktual = json.loads((keluaran / f"{p}.json").read_text(encoding="utf-8"))
                harapan = json.loads((kerja / "harapan" / f"{p}.json").read_text(encoding="utf-8"))
                self.maxDiff = None
                self.assertEqual(harapan, aktual)
        semua = "".join((keluaran / n).read_text(encoding="utf-8") for n in os.listdir(keluaran))
        self.assertEqual(0, semua.count("KANARI"), "kanari bocor ke ringkasan")
        self.assertEqual(0, log.count("KANARI"), "kanari bocor ke stdout/stderr")
        self.assertEqual(sorted(f"{p}.json" for p in PENONTON), sorted(os.listdir(keluaran)), "sisa .tmp / berkas lain")
        self.assertEqual(0o750, stat.S_IMODE(os.stat(keluaran).st_mode))
        for p in PENONTON:
            self.assertEqual(0o640, stat.S_IMODE(os.stat(keluaran / f"{p}.json").st_mode))
        return siklus1, langkah

    def test_skenario1_q10_pemberi_ganda_brief_ganda_lock_hilang(self):
        self.periksa("skenario1")

    def test_skenario2_traversal_tanpa_peminta_internal_log_rusak_dan_mengecil(self):
        siklus1, langkah = self.periksa("skenario2")
        teks = [r["teks"] for r in siklus1["akbar"]["riwayat_hari_ini"]]
        self.assertIn(langkah["cek_siklus1"]["akbar_riwayat_memuat"], teks)
        self.assertEqual([], siklus1["akbar"]["galat"])

    def test_cli_sekali_dengan_umask_longgar(self):
        kerja = Path(self.tmp) / "skenario1"
        shutil.copytree(FIXTURE / "skenario1", kerja, symlinks=True)
        keluaran = kerja / "keluaran-cli"
        hasil = subprocess.run(
            [sys.executable, str(ROOT / "script" / "generator.py"), "--activity", str(kerja / "activity.jsonl"),
             "--workspace", str(kerja / "workspace"), "--proc", str(kerja / "proc"), "--proyek", str(kerja / "proyek.json"),
             "--tim", str(tulis_tim(kerja / "tim.json", kerja, dasar=kerja / "tim.json")), "--profil", str(kerja / "profiles"),
             "--keluaran", str(keluaran), "--sekali", "--sekarang", "2026-10-16T14:59:57+07:00"],
            capture_output=True, text=True, timeout=60, preexec_fn=lambda: os.umask(0o002))
        self.assertEqual(0, hasil.returncode, hasil.stderr[-500:])
        self.assertEqual(0, (hasil.stdout + hasil.stderr).count("KANARI"))
        for p in PENONTON:
            d = json.loads((keluaran / f"{p}.json").read_text(encoding="utf-8"))
            self.assertEqual(("1", p, "2026-10-16T14:59:57+07:00"), (d["versi_skema"], d["penonton"], d["dibuat_pada"]))
            self.assertEqual(0o640, stat.S_IMODE(os.stat(keluaran / f"{p}.json").st_mode))
        self.assertEqual(0o750, stat.S_IMODE(os.stat(keluaran).st_mode))


if __name__ == "__main__":
    unittest.main()
