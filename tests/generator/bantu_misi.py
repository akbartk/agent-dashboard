"""Bantuan uji misi "Kantor Agen" (TL Beta, 24 Okt 2026). Bukan modul uji (tidak diawali test_).

Menyalin tests/fixtures/misi1 ke TMPDIR, membuat state.db dari state/<profil>.sql, mengatur mtime laporan dari
langkah.json, lalu menjalankan Generator dengan registri nomor di TMPDIR (bukan storage/ live).
"""
import contextlib
import io
import json
import os
import shutil
import sqlite3
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "script"))
import generator  # noqa: E402
from bantu_tim import muat, tulis_tim  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "misi1"
PENONTON = tuple(muat(FIXTURE / "tim.json")["penonton"])  # DATA uji: config tim fixture
GALAT_NOMOR = "Nomor misi tidak terbaca"
GALAT_SESI = "Data sesi tidak terbaca"
# nama berkas brief per misi fixture (lihat bangun_misi1.py); nomor = urutan baris log pertama yang cocok
B = {"G": "2026-10-23-beta-ilk-kemarin.md", "A": "2026-10-24-desy-induk.md",
     "B": "2026-10-24-beta-agent-dashboard-generator.md", "C": "2026-10-24-alfa-searchenginebsk-zamrud.md",
     "D": "2026-10-24-carli-policytrack-rubi.md", "E": "2026-10-24-via-pemahaman-asn-mutiara.md",
     "F": "2026-10-24-uci-jati-intan.md"}
ID = {"G": "T-001", "A": "T-002", "B": "T-003", "C": "T-004", "D": "T-005", "E": "T-006", "F": "T-007"}


def t(hms, tanggal="2026-10-24"):
    return f"{tanggal}T{hms}+07:00"


class Misi1:
    """Satu salinan fixture misi1 + Generator-nya."""

    FIXTURE = FIXTURE

    def __init__(self, akar, nomor=True, tim=None, buat_db=True):
        self.akar = Path(akar)
        shutil.copytree(self.FIXTURE, self.akar, symlinks=True)
        tulis_tim(self.akar / "tim.json", self.akar, dasar=self.akar / "tim.json")  # path sumber fixture jadi path dunia uji
        self.langkah = json.loads((self.akar / "langkah.json").read_text(encoding="utf-8"))
        for rel, iso in self.langkah["mtime"].items():
            s = datetime.fromisoformat(iso).timestamp()
            os.utime(self.akar / rel, (s, s))
        if buat_db:
            for sql in sorted((self.akar / "state").glob("*.sql")):
                self.buat_db(sql.stem)
        self.keluaran = self.akar / "keluaran"
        self.nomor = self.akar / "misi" / "nomor.json"
        self.stdout = ""
        self.g = self.generator(nomor=self.nomor if nomor else None, tim=tim)

    def buat_db(self, profil):
        db = self.akar / "profiles" / profil / "state.db"
        if db.exists():
            db.unlink()
        con = sqlite3.connect(db)
        try:
            con.executescript((self.akar / "state" / f"{profil}.sql").read_text(encoding="utf-8"))
            con.commit()
        finally:
            con.close()

    def generator(self, nomor=None, tim=None):
        kw = {"nomor": nomor} if nomor is not None else {}
        return generator.Generator(activity=self.akar / "activity.jsonl", workspace=self.akar / "workspace",
                                   proc=self.akar / "proc", proyek=self.akar / "proyek.json", keluaran=self.keluaran,
                                   tim=tim or (self.akar / "tim.json"), profil=self.akar / "profiles", **kw)

    def siklus(self, iso=None, g=None):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            (g or self.g).siklus(datetime.fromisoformat(iso or self.langkah["siklus1"]))
        self.stdout += buf.getvalue()
        return self.baca()

    def baca(self):
        return {p: json.loads((self.keluaran / f"{p}.json").read_text(encoding="utf-8")) for p in PENONTON}

    def tambah(self, berkas="tambahan.jsonl"):
        with open(self.akar / "activity.jsonl", "a", encoding="utf-8") as f:
            f.write((self.akar / berkas).read_text(encoding="utf-8"))

    def tambah_baris(self, *baris):
        with open(self.akar / "activity.jsonl", "a", encoding="utf-8") as f:
            for b in baris:
                f.write(json.dumps(b, ensure_ascii=False) + "\n")

    HERMES = ["/opt/hermes/.venv/bin/python", "-P", "-c",
              "import sys; sys.argv[0]='hermes'; from hermes_cli.main import main; main()"]

    def proses(self, pid, argv, ppid, mulai="2026-10-24T11:00:00+07:00", comm="python"):
        """Tambah /proc/<pid> palsu (cmdline + stat dengan PPID); btime fixture = 24 Okt 06.00 WIB, CLK 100."""
        p = self.akar / "proc" / str(pid)
        p.mkdir()
        (p / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
        btime = int(datetime.fromisoformat("2026-10-24T06:00:00+07:00").timestamp())
        ticks = (int(datetime.fromisoformat(mulai).timestamp()) - btime) * 100
        sisa = ["S", str(ppid), str(pid), str(pid), "0", "-1", "4194560"] + ["0"] * 12 + [str(ticks)] + ["0"] * 6
        (p / "stat").write_text(f"{pid} ({comm}) " + " ".join(sisa) + "\n")


def misi(h, id):
    return next((m for m in h["misi"] if m["id"] == id), None)


def agen(h, id):
    return next(a for a in h["agen"] if a["id"] == id)


def riwayat(h):
    return [(r["pelaku"], r["teks"], r["misi"]) for r in h["riwayat_hari_ini"]]


def _tanpa_aktivitas(path):
    """Isi berkas tanpa field `aktivitas` (satu-satunya tempat potongan `detail` tool sengaja dikutip, ≤100 karakter)."""
    teks = path.read_text(encoding="utf-8")
    try:
        data = json.loads(teks)
    except ValueError:
        return teks
    for m in data.get("misi", []) if isinstance(data, dict) else []:
        m.pop("aktivitas", None)
    return json.dumps(data, ensure_ascii=False)


class DasarMisi(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="uji-misi-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dunia = []

    def buat(self, **kw):
        d = Misi1(Path(self.tmp) / f"m{len(self.dunia)}", **kw)
        self.dunia.append(d)
        return d

    def tearDown(self):
        for d in self.dunia:
            self.assertEqual(0, d.stdout.count("KANARI"), "kanari bocor ke stdout/stderr")
            if d.keluaran.exists():
                for n in os.listdir(d.keluaran):
                    self.assertEqual(0, _tanpa_aktivitas(d.keluaran / n).count("KANARI"), f"kanari bocor di {n}")
            if d.nomor.is_file():
                self.assertEqual(0, d.nomor.read_text(encoding="utf-8").count("KANARI"), "kanari bocor di registri")
