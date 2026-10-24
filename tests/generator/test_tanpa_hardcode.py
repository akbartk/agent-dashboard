"""Uji tanpa hardcode: `script/generator.py` tidak memuat identitas tim/orang/host/path (KONTRAK agent-dashboard-g7).
Daftar nama di uji ini diturunkan dari DATA uji (fixture tim sumber + config g7), bukan dari kode.
Jalankan dari root project: python3 -m unittest discover -s tests/generator -v
"""
import json
import re
import unittest

from bantu_tim import FIXTURE, ROOT

SUMBER = ROOT / "script" / "generator.py"
GENERIK = {"default", "pak", "mas", "bu", "tim", "agen", "peran", "lead", "tech", "qa", "qc", "riset", "dan", "regulasi",
           "koordinator", "cto", "pemilik", "pemberi", "order"}


def nama_dari(tim):
    """Id dan kata-kata nama orang/agen sebuah config tim."""
    kata = set()
    for o in tim["orang"]:
        kata |= {o["id"]} | set(re.findall(r"[A-Za-z0-9]+", o["nama"]))
    for i, a in tim["agen"].items():
        kata |= {i} | set(re.findall(r"[A-Za-z0-9]+", a["nama"]))
    kata |= {tim["koordinator"], tim["cto"]}
    return {k.lower() for k in kata} - GENERIK


def muat(p):
    return json.loads(p.read_text(encoding="utf-8"))


class UjiTanpaHardcode(unittest.TestCase):
    def setUp(self):
        self.teks = SUMBER.read_text(encoding="utf-8")

    def cari(self, pola, flags=0):
        return [(n, b.strip()[:90]) for n, b in enumerate(self.teks.split("\n"), 1) if re.search(pola, b, flags)]

    def test_tanpa_nama_tim_sumber_dan_g7(self):
        nama = nama_dari(muat(FIXTURE / "skenario1" / "tim.json")) | nama_dari(muat(ROOT / "conf" / "tim.json"))
        self.assertTrue({"akbar", "ajeng", "desy", "alfa", "uci", "arsa", "lala"} <= nama, sorted(nama))
        for n in sorted(nama):
            with self.subTest(n=n):
                self.assertEqual([], self.cari(rf"(?<![A-Za-z0-9]){re.escape(n)}(?![A-Za-z0-9])", re.I))

    def test_tanpa_host_path_dan_ip(self):
        for pola in (r"bskdev", r"net-bsk", r"(?<![\w.])/workspace/", r"/data/", r"obsidian", r"hermes-agent",
                     r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b"):
            with self.subTest(pola=pola):
                self.assertEqual([], self.cari(pola, re.I))

    def test_tanpa_konstanta_identitas_lama(self):
        for n in ("PENONTON", "ORANG", "PEMBERI", "NAMA_ORANG", "CATAT", "SETOR", "RE_SSH", "RE_R1", "RE_SLUG",
                  "RE_PEMINTA"):
            with self.subTest(n=n):
                self.assertEqual([], self.cari(rf"^{n}\s*="))


if __name__ == "__main__":
    unittest.main()
