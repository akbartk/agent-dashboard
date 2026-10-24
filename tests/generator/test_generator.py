"""Uji tambahan generator (S1) — melengkapi test_kontrak.py. Kontrak: docs/skema-ringkasan.md versi skema "1".

Semua data fiktif, dibuat di direktori sementara. Setiap `text`/`detail`/sid/argv/isi brief/`oleh=` memuat KANARI;
setiap uji (lewat tearDown) memastikan KANARI tidak muncul di berkas keluaran maupun stdout/stderr.
Jalankan dari root project: python3 -m unittest discover -s tests/generator -v
"""
import contextlib
import hashlib
import io
import json
import os
import re
import shutil
import signal
import stat
import subprocess
import sys
import tempfile
import time
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "script"))
import generator  # noqa: E402
from bantu_tim import muat as muat_tim, tulis_tim  # noqa: E402

WIB = timezone(timedelta(hours=7))
BTIME = int(datetime(2026, 10, 16, 6, 0, 0, tzinfo=WIB).timestamp())
SKR = "2026-10-16T15:00:00+07:00"
PENONTON = tuple(muat_tim()["penonton"])  # DATA uji: config tim fixture
PROYEK = {"searchenginebsk": "Search Engine BSK", "policytrack": "PolicyTrack", "absensimeeting": "Absensi Meeting",
          "jdih-v3": "JDIH", "ebook-v2": "eBook", "pemahaman-asn": "Pemahaman ASN", "survei3as": "Survei 3AS"}
HERMES = ["/opt/hermes/.venv/bin/python", "-P", "-c",
          "import sys; sys.argv[0]='hermes'; from hermes_cli.main import main; main()"]
MULAI_LOCK = "2026-10-16T09:00:00+07:00"
GALAT_LOG = "Log aktivitas tidak terbaca"
GALAT_PROSES = "Daftar proses tidak terbaca"
GALAT_LOCK = "Lock tidak terbaca"
GALAT_PETA = "Peta project tidak terbaca"
PROFIL_LAMA = ("alfa", "beta", "carli", "desy", "via")  # folder profil uji; atribut dari config tim fixture


def ts(jam, hari="2026-10-16"):
    return f"{hari}T{jam}"


def ajeng_msg(waktu, nama="Pak Akbar"):
    return {"type": "msg", "role": "owner", "name": nama, "text": "KANARI-teks", "ts": waktu}


def ajeng_tool(waktu, nama, tool, detail="KANARI-detail"):
    return {"type": "tool", "role": "owner", "name": nama, "tool": tool, "detail": detail, "blocked": False, "ts": waktu}


def tim(waktu, profil, tool=None, detail="KANARI-detail", sid="KANARI-SID"):
    d = {"role": "tim", "name": profil.capitalize(), "profile": profil, "sid": sid}
    if tool is None:
        d.update(type="msg", text="KANARI-teks")
    else:
        d.update(type="tool", tool=tool, detail=detail, blocked=False)
    d["ts"] = waktu
    return d


def tugas(h, id):
    return next((t for t in h["tugas_aktif"] if t["id"] == id), None)


def agen(h, id):
    return next(a for a in h["agen"] if a["id"] == id)


def teks(h):
    return [r["teks"] for r in h["riwayat_hari_ini"]]


def kode_r(nama):
    return "ajeng-x" + hashlib.sha256(nama.encode("utf-8")).hexdigest()[:8]


class Dunia:
    """Satu direktori kerja sementara berisi sumber data fiktif + Generator-nya."""

    def __init__(self, akar, proyek=PROYEK, proyek_teks=None):
        self.akar = Path(akar)
        self.activity = self.akar / "activity.jsonl"
        self.workspace = self.akar / "workspace"
        self.locks = self.workspace / "locks"
        self.brief_dir = self.workspace / "brief"
        self.proc = self.akar / "proc"
        self.proyek = self.akar / "proyek.json"
        self.keluaran = self.akar / "keluaran"
        self.profil = self.akar / "profiles"
        for d in (self.locks, self.brief_dir, self.proc):
            d.mkdir(parents=True)
        for i in PROFIL_LAMA:
            (self.profil / i).mkdir(parents=True)
            (self.profil / i / "profile.yaml").write_text(f"description: 'Profil uji {i}.'\n", encoding="utf-8")
        (self.proc / "stat").write_text(f"cpu  1 2 3 4\nbtime {BTIME}\nprocesses 9\n")
        self.proyek.write_text(json.dumps(proyek) if proyek_teks is None else proyek_teks, encoding="utf-8")
        self.activity.write_bytes(b"")
        self.stdout = ""
        self.tim = tulis_tim(self.akar / "tim.json", self.akar)
        self.g = generator.Generator(activity=self.activity, workspace=self.workspace, proc=self.proc,
                                     proyek=self.proyek, keluaran=self.keluaran, tim=self.tim, profil=self.profil)

    def siklus(self, iso=SKR):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            self.g.siklus(datetime.fromisoformat(iso))
        self.stdout += buf.getvalue()
        return self.baca()

    def baca(self):
        return {p: json.loads((self.keluaran / f"{p}.json").read_text(encoding="utf-8")) for p in PENONTON}

    def tambah(self, *baris):
        with open(self.activity, "ab") as f:
            for b in baris:
                f.write((b if isinstance(b, str) else json.dumps(b, ensure_ascii=False)).encode("utf-8") + b"\n")

    def tulis_log(self, *baris):
        self.activity.write_bytes(b"")
        self.tambah(*baris)

    def lock(self, slug, tl="alfa", mulai=MULAI_LOCK, brief=None, isi=None):
        if isi is None:
            baris = [f"tl={tl}"]
            if mulai:
                baris.append(f"mulai={mulai}")
            if brief:
                baris.append(f"brief={brief}")
            baris.append("oleh=desy KANARI-OLEH")
            isi = "\n".join(baris) + "\n"
        (self.locks / f"{slug}.lock").write_text(isi, encoding="utf-8")

    def brief(self, nama, *baris):
        (self.brief_dir / nama).write_text("\n".join(baris) + "\nKANARI-ISI\n", encoding="utf-8")
        return "/workspace/brief/" + nama

    def proses(self, pid, argv, mulai=MULAI_LOCK, comm="python", tick_ekstra=0):
        p = self.proc / str(pid)
        p.mkdir()
        (p / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
        ticks = (int(datetime.fromisoformat(mulai).timestamp()) - BTIME) * 100 + tick_ekstra
        sisa = ["S", "1", str(pid), str(pid), "0", "-1", "4194560"] + ["0"] * 12 + [str(ticks)] + ["0"] * 6
        (p / "stat").write_text(f"{pid} ({comm}) " + " ".join(sisa) + "\n")

    def desy(self, pid=2001, profil="desy", z="KANARI-z", mulai="2026-10-16T14:00:00+07:00"):
        self.proses(pid, HERMES + ["-p", profil, "-z", z], mulai)


class Dasar(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp(prefix="uji-gen-")
        self.addCleanup(shutil.rmtree, self.tmp, True)
        self.dunia = []

    def buat(self, **kw):
        d = Dunia(Path(self.tmp) / f"d{len(self.dunia)}", **kw)
        self.dunia.append(d)
        return d

    def tearDown(self):
        for d in self.dunia:
            self.assertEqual(0, d.stdout.count("KANARI"), "kanari bocor ke stdout/stderr")
            if d.keluaran.exists():
                for n in os.listdir(d.keluaran):
                    self.assertEqual(0, (d.keluaran / n).read_text(encoding="utf-8").count("KANARI"), f"kanari bocor di {n}")


class UjiBentuk(Dasar):
    def test_dunia_kosong(self):
        d = self.buat()
        hasil = d.siklus()
        for p in PENONTON:
            h = hasil[p]
            self.assertEqual(["versi_skema", "penonton", "pemilik", "koordinator", "cakupan", "dibuat_pada", "galat", "peringatan", "orang", "agen",
                              "tugas_aktif", "riwayat_hari_ini", "ringkasan", "misi"], list(h))  # + ringkasan, misi (A1)
            self.assertEqual(("1", p, "semua" if p == "akbar" else "order-sendiri", SKR, []),
                             (h["versi_skema"], h["penonton"], h["cakupan"], h["dibuat_pada"], h["galat"]))
            self.assertEqual([("akbar", "Pak Akbar", "Pemilik tim", []), ("dicky", "Mas Dicky", "Pemberi order", ["akbar"]),
                              ("jati", "Mas Jati", "Pemberi order", ["akbar"])],
                             [(o["id"], o["nama"], o["peran"], o["induk"]) for o in h["orang"]])
            self.assertEqual([("ajeng", "Ajeng", "Koordinator", ["dicky", "jati"]), ("desy", "Desy", "CTO", ["ajeng"]),
                              ("via", "Via", "Riset dan peraturan", ["ajeng"]), ("alfa", "Alfa", "Tech Lead", ["desy"]),
                              ("beta", "Beta", "Tech Lead", ["desy"]), ("carli", "Carli", "Tech Lead", ["desy"])],
                             [(a["id"], a["nama"], a["peran"], a["induk"]) for a in h["agen"]])
            self.assertEqual(["bebas"] * 6, [a["status"] for a in h["agen"]])
            self.assertEqual([None] * 6, [a["terakhir_aktif"] for a in h["agen"]])
            self.assertEqual(([], []), (h["tugas_aktif"], h["riwayat_hari_ini"]))

    def test_satu_baris_json_ringkas_utf8_dan_waktu_wib(self):
        d = self.buat()
        d.tambah(ajeng_msg("2026-10-16T14:59:00", "Ünal"))
        d.siklus("2026-10-16T08:00:00+00:00")  # UTC → WIB
        mentah = (d.keluaran / "akbar.json").read_text(encoding="utf-8")
        self.assertEqual(1, mentah.count("\n"))
        self.assertTrue(mentah.endswith("\n"))
        self.assertIn("Ünal", mentah)
        h = json.loads(mentah)
        self.assertEqual("2026-10-16T15:00:00+07:00", h["dibuat_pada"])
        self.assertEqual(json.dumps(h, ensure_ascii=False, separators=(",", ":")) + "\n", mentah)

    def test_ditulis_ulang_tiap_siklus_dan_tanpa_duplikat(self):
        d = self.buat()
        d.lock("jdih-v3", "alfa", brief=d.brief("b.md", "# Brief TL — jdih-v3 — Cek", "**Peminta:** Mas Dicky (operator)"))
        d.tambah(ajeng_msg("2026-10-16T14:59:00", "Mas Dicky"), tim("2026-10-16T14:59:10", "alfa", "write_file"))
        a = d.siklus("2026-10-16T15:00:00+07:00")
        b = d.siklus("2026-10-16T15:00:03+07:00")
        c = d.siklus("2026-10-16T15:00:06+07:00")
        self.assertEqual("2026-10-16T15:00:03+07:00", b["akbar"]["dibuat_pada"])
        for p in PENONTON:
            for k in ("tugas_aktif", "riwayat_hari_ini"):
                self.assertEqual(a[p][k], b[p][k])
                self.assertEqual(a[p][k], c[p][k])
        self.assertEqual(1, teks(a["akbar"]).count("Mas Dicky mengirim pesan ke Ajeng"))

    def test_terakhir_aktif_adalah_baris_terakhir_menurut_urutan_berkas(self):
        d = self.buat()
        d.tambah(tim("2026-10-16T14:59:00", "via"), tim("2026-10-16T14:58:00", "via"),
                 tim("2026-10-16T14:50:00", "beta", "patch"))
        h = d.siklus()["akbar"]
        self.assertEqual("2026-10-16T14:58:00+07:00", agen(h, "via")["terakhir_aktif"])
        self.assertEqual("2026-10-16T14:50:00+07:00", agen(h, "beta")["terakhir_aktif"])
        self.assertIsNone(agen(h, "carli")["terakhir_aktif"])

    def test_profile_lain_diabaikan(self):
        d = self.buat()
        d.tambah({"type": "msg", "profile": "zeta", "sid": "KANARI-Z", "text": "KANARI", "ts": "2026-10-16T14:59:00"},
                 {"type": "msg", "profile": 7, "sid": "KANARI-Z", "text": "KANARI", "ts": "2026-10-16T14:59:00"},
                 {"type": "msg", "profile": ["desy"], "sid": "KANARI-Z", "text": "KANARI", "ts": "2026-10-16T14:59:00"},
                 # keputusan lokal: hanya profile TIDAK ADA / null = Ajeng; nilai lain (termasuk "") = "profile lain" → diabaikan
                 {"type": "msg", "profile": "", "name": "Pak Akbar", "text": "KANARI", "ts": "2026-10-16T14:59:00"},
                 {"type": "msg", "profile": 0, "name": "Pak Akbar", "text": "KANARI", "ts": "2026-10-16T14:59:00"},
                 {"type": "msg", "profile": False, "name": "Pak Akbar", "text": "KANARI", "ts": "2026-10-16T14:59:00"},
                 {"type": "msg", "profile": [], "name": "Pak Akbar", "text": "KANARI", "ts": "2026-10-16T14:59:00"})
        h = d.siklus()["akbar"]
        self.assertEqual(([], []), (h["tugas_aktif"], h["riwayat_hari_ini"]))
        self.assertEqual(["bebas"] * 6, [a["status"] for a in h["agen"]])

    def test_profile_null_berarti_ajeng(self):
        d = self.buat()
        d.tambah({"type": "msg", "profile": None, "name": "Mas Jati", "text": "KANARI", "ts": "2026-10-16T14:59:00"})
        self.assertEqual(["Mas Jati mengirim pesan ke Ajeng"], teks(d.siklus()["akbar"]))


class UjiK1(Dasar):
    """Tabel K1 (§3.2)."""

    def langkah_tim(self, tool, detail="KANARI-detail"):
        d = self.buat()
        d.lock("jdih-v3", "alfa")
        d.tambah(tim("2026-10-16T14:59:00", "alfa", tool, detail))
        t = tugas(d.siklus()["akbar"], "lock-jdih-v3")
        return t["langkah_terakhir"]

    def test_terminal_dan_execute_code(self):
        kasus = [
            ("ssh bskdev-host ls", "menjalankan perintah di bskdev"),
            ("ssh -F /opt/data/.ssh/config -o BatchMode=yes bskdev-host 'KANARI'", "menjalankan perintah di bskdev"),
            ("ssh bskdev-host hermes -p alfa", "menjalankan perintah di bskdev"),  # urutan 1 mendahului 2
            ("ssh bskdev-host; hermes -p desy", "menjalankan perintah di bskdev"),
            ("ssh bskdev-hostx ls", "menjalankan perintah"),
            ("sshd bskdev-host", "menjalankan perintah"),
            ("hermes -p alfa -z x", "memanggil TL Alfa"),
            ("hermes -p beta -z x", "memanggil TL Beta"),
            ("hermes -p carli", "memanggil TL Carli"),
            ("/opt/hermes/.venv/bin/hermes -p carli", "memanggil TL Carli"),  # hermes di dalam path
            ('cd /workspace && /opt/hermes/.venv/bin/hermes -p alfa -z "$(cat brief/x.md)"', "memanggil TL Alfa"),
            ("hermes -p desy -z x", "memanggil Desy"),
            ("hermes -p via", "memanggil Via"),
            ("/opt/hermes/.venv/bin/hermes -p via -z x", "memanggil Via"),
            ("hermes -p desy lalu hermes -p beta", "memanggil TL Beta"),  # urutan 2 mendahului 3
            ("hermes -p alfa; /ip address print", "memanggil TL Alfa"),  # 2 mendahului 4
            ("hermes -p desy; echo R1", "memanggil Desy"),  # 3 mendahului 4
            ("hermes -p alfax", "menjalankan perintah"),
            ("hermes -q alfa", "menjalankan perintah"),
            ("-p alfa tanpa program", "menjalankan perintah"),
            ("/ip address print", "mengakses R1"),
            ("ssh admin@h '/ip address print'", "mengakses R1"),
            ('ssh admin@h "/interface print"', "mengakses R1"),
            ("/routing ospf print", "mengakses R1"),
            ("/system reboot", "mengakses R1"),
            ("echo x;/system reboot", "mengakses R1"),
            ("(/ip firewall print)", "mengakses R1"),
            ("echo x /interface", "mengakses R1"),
            ("ls /etc/systemd/system", "menjalankan perintah"),
            ("cat /etc/systemd/system/x.service", "menjalankan perintah"),
            ("systemctl cat x; ls /etc/systemd/system", "menjalankan perintah"),
            ("/ipv6 address print", "menjalankan perintah"),
            ("ping R1", "mengakses R1"),
            ("ping r1", "menjalankan perintah"),
            ("ping R10", "menjalankan perintah"),
            ("cek MikroTik", "mengakses R1"),
            ("cek mikrotik", "mengakses R1"),
            ("cek RouterOS", "mengakses R1"),
            ("cek routeros", "mengakses R1"),
            ("ls -la", "menjalankan perintah"),
            ("", "menjalankan perintah"),
        ]
        for tool in ("terminal", "execute_code"):
            for detail, harapan in kasus:
                with self.subTest(tool=tool, detail=detail):
                    self.assertEqual(f"{harapan} · JDIH", self.langkah_tim(tool, detail))

    def test_perintah_multibaris(self):
        """Keputusan Desy 6.3 (a), 16 Okt 2026: pola ssh/hermes dicocokkan lintas baris (re.S)."""
        kasus = [
            ("ssh -F /opt/data/.ssh/config \\\n  bskdev-host 'KANARI'", "menjalankan perintah di bskdev"),
            ("ssh -F /opt/data/.ssh/config -o BatchMode=yes \\\n    bskdev-host \\\n    'cd /data/x && KANARI'",
             "menjalankan perintah di bskdev"),
            ("ssh \\\n bskdev-host ls", "menjalankan perintah di bskdev"),
            ('/opt/hermes/.venv/bin/hermes \\\n  -p alfa \\\n  -z "$(cat brief/KANARI.md)"', "memanggil TL Alfa"),
            ("cd /workspace &&\n  hermes chat \\\n    -p carli -z KANARI", "memanggil TL Carli"),
            ("hermes \\\n  -p desy -z KANARI", "memanggil Desy"),
            ("hermes \\\n  -p via", "memanggil Via"),
            ("hermes -p desy\nhermes \\\n  -p beta", "memanggil TL Beta"),  # urutan 2 mendahului 3, lintas baris
            ("ssh bskdev-host \\\n  hermes -p alfa", "menjalankan perintah di bskdev"),  # urutan 1 mendahului 2
            ("ssh -F x \\\n  bskdev-hostx ls", "menjalankan perintah"),
            ("hermes \\\n  -p alfax", "menjalankan perintah"),
            ("hermes \\\n  -q alfa", "menjalankan perintah"),
        ]
        for tool in ("terminal", "execute_code"):
            for detail, harapan in kasus:
                with self.subTest(tool=tool, detail=detail):
                    self.assertEqual(f"{harapan} · JDIH", self.langkah_tim(tool, detail))

    def test_tool_lain_dan_pesan(self):
        kasus = [("read_file", "membaca berkas"), ("search_files", "membaca berkas"),
                 ("write_file", "menulis berkas"), ("patch", "menulis berkas"),
                 ("mcp__obsidian_bsk__cari", "membaca bank dokumen"), ("mcp__obsidian_bsk__baca", "membaca bank dokumen"),
                 ("mcp__obsidian_bsk__status", "membaca bank dokumen"),
                 ("mcp__obsidian_bsk__catat_progres", "mencatat kemajuan"),
                 ("mcp__obsidian_bsk__setor", "mengelola bank dokumen"),
                 ("mcp__obsidian_bsk__terbitkan", "mengelola bank dokumen"),
                 ("mcp__obsidian_bsk__hapus", "mengelola bank dokumen"),
                 ("delegate_task", "membagi tugas ke worker"), ("process_manage", "menunggu proses"),
                 ("web_search", "mencari di web"), ("web_extract", "mencari di web"), ("browser_exec", "mencari di web"),
                 ("clarify", "meminta keputusan"),
                 ("skill_view", "membaca skill"), ("skills_list", "membaca skill"), ("skill_manage", "memperbarui skill"),
                 ("vision_analyze", "memeriksa gambar"), ("memory", "mencatat memori"),
                 ("mnemosyne_recall", "mencatat memori"), ("mnemosyne_simpan", "mencatat memori"),
                 ("cronjob_manage", "mengatur jadwal"), ("alat_tak_dikenal", "bekerja"), ("", "bekerja")]
        for tool, harapan in kasus:
            with self.subTest(tool=tool):
                self.assertEqual(f"{harapan} · JDIH", self.langkah_tim(tool))
        with self.subTest(jenis="msg"):
            self.assertEqual("membaca pesan · JDIH", self.langkah_tim(None))

    def test_tool_tanpa_nama_atau_bukan_string_jadi_bekerja(self):
        d = self.buat()
        d.lock("jdih-v3", "alfa")
        d.tambah({"type": "tool", "profile": "alfa", "sid": "KANARI", "detail": "KANARI", "ts": "2026-10-16T14:59:00"})
        self.assertEqual("bekerja · JDIH", tugas(d.siklus()["akbar"], "lock-jdih-v3")["langkah_terakhir"])
        d.tambah({"type": "tool", "profile": "alfa", "sid": "KANARI", "tool": ["x"], "detail": 5, "ts": "2026-10-16T14:59:10"})
        self.assertEqual("bekerja · JDIH", tugas(d.siklus()["akbar"], "lock-jdih-v3")["langkah_terakhir"])

    def test_clarify_ajeng_memuat_nama_peminta_dan_tool_ajeng_lain(self):
        d = self.buat()
        d.tambah(ajeng_tool("2026-10-16T14:59:00", "Mas Dicky", "clarify"),
                 ajeng_tool("2026-10-16T14:59:00", "Mas Jati", "read_file"),
                 ajeng_tool("2026-10-16T14:59:00", "Pak Akbar", "terminal", "ls"))
        h = d.siklus()["akbar"]
        self.assertEqual("meminta keputusan Mas Dicky", tugas(h, "ajeng-dicky")["langkah_terakhir"])
        self.assertEqual("membaca berkas", tugas(h, "ajeng-jati")["langkah_terakhir"])
        self.assertEqual("menjalankan perintah", tugas(h, "ajeng-akbar")["langkah_terakhir"])


class UjiPenyaring(Dasar):
    """§3.7: ≥ 10 digit berurutan (pemisah tunggal spasi/titik/strip) atau '@' → '(disaring)'."""
    KASUS = [("198001012005011001", True), ("3201234567890123", True), ("081234567890", True),
             ("0812-3456-7890", True), ("0812 3456 7890", True), ("0812.3456.7890", True), ("+62 812-3456-7890", True),
             ("1234567890", True), ("x 12345 67890 y", True), ("budi@contoh.go.id", True), ("@", True),
             ("Audit indeks campuran", False), ("123456789", False), ("12-34-56", False), ("Rapat 2026", False),
             ("0812--3456-7890", False)]

    def test_judul_dari_brief(self):
        for nilai, disaring in self.KASUS:
            with self.subTest(nilai=nilai):
                d = self.buat()
                d.lock("jdih-v3", "alfa", brief=d.brief("b.md", f"# Brief TL — jdih-v3 — {nilai}"))
                t = tugas(d.siklus()["akbar"], "lock-jdih-v3")
                self.assertEqual("(disaring)" if disaring else nilai, t["judul"])

    def test_nama_pengirim(self):
        for nilai, disaring in self.KASUS:
            if nilai.strip() in ("", "?"):
                continue
            with self.subTest(nilai=nilai):
                d = self.buat()
                d.tambah(ajeng_msg("2026-10-16T14:59:00", nilai))
                h = d.siklus()["akbar"]
                harapan = "(disaring)" if disaring else nilai
                self.assertEqual(harapan, tugas(h, kode_r(harapan))["pemberi"])
                self.assertEqual([f"{harapan} mengirim pesan ke Ajeng"], teks(h))

    def test_project_nama_di_semua_tempat(self):
        d = self.buat(proyek={"jdih-v3": "JDIH 081234567890", "policytrack": "Poli@Track"})
        d.lock("jdih-v3", "alfa")
        d.lock("policytrack", "beta", mulai="2026-10-16T10:00:00+07:00")
        d.tambah(tim("2026-10-16T14:59:00", "alfa", "write_file"))
        h = d.siklus()["akbar"]
        t = tugas(h, "lock-jdih-v3")
        self.assertEqual(("(disaring)", "Pekerjaan (disaring)", "menulis berkas · (disaring)"),
                         (t["project_nama"], t["judul"], t["langkah_terakhir"]))
        self.assertEqual("jdih-v3", t["project"])
        self.assertIn("Alfa mulai (disaring)", teks(h))
        self.assertIn("Beta mulai (disaring)", teks(h))

    def test_digit_sembilan_dan_teks_biasa_di_project_nama_lolos(self):
        d = self.buat(proyek={"jdih-v3": "Portal 123456789"})
        d.lock("jdih-v3", "alfa")
        t = tugas(d.siklus()["akbar"], "lock-jdih-v3")
        self.assertEqual(("Portal 123456789", "Pekerjaan Portal 123456789"), (t["project_nama"], t["judul"]))

    def test_disaring_sebelum_dipotong_200(self):
        d = self.buat()
        d.lock("jdih-v3", "alfa", brief=d.brief("b.md", "# Brief TL — jdih-v3 — " + "x" * 195 + " 1234567890"))
        self.assertEqual("(disaring)", tugas(d.siklus()["akbar"], "lock-jdih-v3")["judul"])


class UjiHeaderJudul(Dasar):
    """§3.5 header & judul."""

    def tl_tugas(self, baris, slug="sdmo-v1", mentah=None):
        d = self.buat()
        if mentah is None:
            nama = d.brief("x.md", *baris)
        else:
            (d.brief_dir / "x.md").write_bytes(mentah)
            nama = "/workspace/brief/x.md"
        d.lock(slug, "alfa", brief=nama)
        return tugas(d.siklus()["akbar"], f"lock-{slug}")

    def desy_tugas(self, baris, mentah_z=None):
        d = self.buat()
        d.brief("x.md", *baris)
        z = ("\n".join(baris) + "\nKANARI-ISI") if mentah_z is None else mentah_z
        d.desy(2001, "desy", z)
        return tugas(d.siklus()["akbar"], "proses-2001")

    def test_judul_tl(self):
        kasus = [
            ("# Brief TL — sdmo-v1 (FASE B: eksekusi) — 2026-10-16", "sdmo-v1", "FASE B: eksekusi"),
            ("# Brief TL — searchenginebsk — 2026-10-16", "searchenginebsk", "Pekerjaan Search Engine BSK"),
            ("# Brief TL — sdmo-v1 — 2026-10-16", "sdmo-v1", "Pekerjaan sdmo-v1"),  # slug di luar peta: apa adanya
            ("# Brief TL — searchenginebsk — 2026-10-16 — Audit indeks campuran", "searchenginebsk", "Audit indeks campuran"),
            ("# Brief TL — policytrack — perbaikan statistik", "policytrack", "perbaikan statistik"),
            ("# Brief TL — jdih-v3 — A — B", "jdih-v3", "A — B"),
            ("# Brief TL — jdih-v3 — 2026-10-16 laporan akhir", "jdih-v3", "laporan akhir"),
            ("# Brief TL — jdih-v3 — jdih-v3 perbaikan tautan", "jdih-v3", "perbaikan tautan"),
            ("# Brief TL — jdih-v3 — (Rapi)", "jdih-v3", "Rapi"),
            ("# Brief TL — jdih-v3 — ( )", "jdih-v3", "Pekerjaan JDIH"),
            ("# Brief TL — jdih-v3 — ()", "jdih-v3", "Pekerjaan JDIH"),
            ("# Judul biasa — (Dalam kurung)", "jdih-v3", "Judul biasa — Dalam kurung"),
            ("# Brief TL", "jdih-v3", "Pekerjaan JDIH"),
            ("Brief TL — jdih-v3 — Audit", "jdih-v3", "Pekerjaan JDIH"),  # bukan H1
            ("## Brief TL — jdih-v3 — Audit", "jdih-v3", "Pekerjaan JDIH"),
            ("#Brief TL — jdih-v3 — Audit", "jdih-v3", "Pekerjaan JDIH"),
            ("", "jdih-v3", "Pekerjaan JDIH"),
        ]
        for baris1, slug, harapan in kasus:
            with self.subTest(baris1=baris1):
                self.assertEqual(harapan, self.tl_tugas([baris1], slug)["judul"])

    def test_judul_dipotong_200_karakter(self):
        j = self.tl_tugas(["# Brief TL — jdih-v3 — " + "x" * 300], "jdih-v3")["judul"]
        self.assertEqual("x" * 200, j)

    def test_judul_desy_via(self):
        kasus = [
            ("# Brief untuk Desy (CTO) — X", "X"),
            ("# Brief untuk Desy (CTO) — Perbaikan urutan hasil pencarian", "Perbaikan urutan hasil pencarian"),
            ("# Brief untuk Via — Ringkasan regulasi", "Ringkasan regulasi"),
            ("# Brief untuk Desy (CTO) — 2026-10-16 laporan", "laporan"),
            ("# Brief untuk Desy (CTO) — jdih-v3 laporan", "jdih-v3 laporan"),  # awalan slug hanya untuk tugas TL
            ("# Brief untuk Desy (CTO)", None),
            ("Brief untuk Desy (CTO) — X", None),  # bukan H1
            ("## Brief untuk Desy (CTO) — X", None),
        ]
        for baris1, harapan in kasus:
            with self.subTest(baris1=baris1):
                t = self.desy_tugas([baris1])
                self.assertEqual(harapan, t["judul"])
                self.assertIsNone(t["project"])

    def test_pemberi(self):
        kasus = [
            (["**Peminta:** Mas Jati (operator)"], "Mas Jati", "jati"),
            (["Peminta asal: Pak Akbar lewat Ajeng"], "Pak Akbar", "akbar"),
            (["- Peminta: Mas Dicky"], "Mas Dicky", "dicky"),
            (["Peminta: Mas Jati, kemudian Mas Jati lagi"], "Mas Jati", "jati"),
            (["Peminta asal: Pak Akbar dan Mas Dicky lewat Ajeng"], None, None),
            (["Peminta: Pak Akbar, Mas Dicky, Mas Jati"], None, None),
            (["Peminta asal: Ajeng (izin internal tim)"], None, None),
            (["Dari: Desy.", "Untuk: Alfa."], None, None),
            (["Dari: Ajeng. Peminta Mas Dicky"], None, None),  # 'Peminta' bukan di awal baris
            (["peminta: Mas Dicky"], None, None),  # huruf kecil
            (["Pemintaan Mas Dicky"], None, None),  # \b
            (["Catatan Mas Dicky", "Peminta: Ajeng"], None, None),  # nama di luar baris Peminta tidak dihitung
            (["Peminta: Ajeng", "Catatan: Mas Dicky"], None, None),  # header berhenti di baris Peminta
        ]
        for tambahan, nama, pid in kasus:
            with self.subTest(baris=tambahan):
                t = self.tl_tugas(["# Brief TL — jdih-v3 — Audit"] + tambahan, "jdih-v3")
                self.assertEqual((nama, pid), (t["pemberi"], t["pemberi_id"]))
                t = self.desy_tugas(["# Brief untuk Desy (CTO) — Audit"] + tambahan)
                self.assertEqual((nama, pid), (t["pemberi"], t["pemberi_id"]))

    def test_baris_peminta_ke_10_masih_masuk_header_ke_11_tidak(self):
        isi = ["# Brief TL — jdih-v3 — Audit"] + [f"baris {i}" for i in range(2, 10)]
        self.assertEqual("Mas Jati", self.tl_tugas(isi + ["Peminta: Mas Jati"], "jdih-v3")["pemberi"])
        self.assertIsNone(self.tl_tugas(isi + ["baris 10", "Peminta: Mas Jati"], "jdih-v3")["pemberi"])
        # jalur proses: header -z dan header berkas sama-sama berhenti di baris ke-10 (Peminta di baris ke-11 di luar header)
        t = self.desy_tugas(["# Brief untuk Desy (CTO) — Audit"] + [f"baris {i}" for i in range(2, 11)] + ["Peminta: Mas Jati"])
        self.assertEqual(("Audit", None), (t["judul"], t["pemberi"]))

    def test_akhir_baris_crlf_dibuang(self):
        mentah = "# Brief TL — jdih-v3 — Audit\r\nDari: Ajeng.\r\nPeminta: Mas Jati\r\nKANARI-ISI\r\n".encode("utf-8")
        t = self.tl_tugas([], "jdih-v3", mentah=mentah)
        self.assertEqual(("Audit", "Mas Jati"), (t["judul"], t["pemberi"]))

    def test_utf8_rusak_tidak_menjatuhkan_siklus(self):
        mentah = b"# Brief TL \xe2\x80\x94 jdih-v3 \xe2\x80\x94 Audit \xff\xfe\nPeminta: Mas Jati\nKANARI\n"
        t = self.tl_tugas([], "jdih-v3", mentah=mentah)
        self.assertEqual("Mas Jati", t["pemberi"])
        self.assertTrue(t["judul"].startswith("Audit"))

    def test_berkas_brief_hanya_10_baris_pertama_dibaca(self):
        # baris ke-11 dst. tidak boleh memengaruhi apa pun, termasuk baris sangat panjang
        d = self.buat()
        isi = "# Brief TL — jdih-v3 — Audit\n" + "".join(f"baris {i}\n" for i in range(2, 10)) + "baris 10\n"
        (d.brief_dir / "x.md").write_text(isi + "Peminta: Mas Dicky\n" + "KANARI-" + "y" * 200000 + "\n", encoding="utf-8")
        d.lock("jdih-v3", "alfa", brief="/workspace/brief/x.md")
        t = tugas(d.siklus()["akbar"], "lock-jdih-v3")
        self.assertEqual(("Audit", None), (t["judul"], t["pemberi"]))

    def test_baris_pertama_sangat_panjang_ditangani(self):
        d = self.buat()
        (d.brief_dir / "x.md").write_text("# Brief TL — jdih-v3 — " + "z" * 100000 + "\nPeminta: Mas Dicky\n", encoding="utf-8")
        d.lock("jdih-v3", "alfa", brief="/workspace/brief/x.md")
        t = tugas(d.siklus()["akbar"], "lock-jdih-v3")
        self.assertEqual(200, len(t["judul"]))

    def test_cocok_hanya_bila_tepat_satu_berkas(self):
        header = ["# Brief untuk Desy (CTO) — Tunggal", "Dari: Ajeng.", "**Peminta:** Mas Dicky (operator)"]
        d = self.buat()
        d.brief("a.md", *header)
        d.desy(2001, "desy", "\n".join(header) + "\nKANARI-ISI")
        d.desy(2002, "desy", "# Brief untuk Desy (CTO) — Lain\nPeminta: Mas Jati\nKANARI")
        d.desy(2003, "desy", "")  # -z kosong tidak pernah cocok
        d.proses(2004, HERMES + ["-p", "desy"], "2026-10-16T14:00:00+07:00")  # tanpa -z
        h = d.siklus()["akbar"]
        self.assertEqual(("Tunggal", "Mas Dicky"), (tugas(h, "proses-2001")["judul"], tugas(h, "proses-2001")["pemberi"]))
        for pid in ("proses-2002", "proses-2003", "proses-2004"):
            self.assertEqual((None, None, None), (tugas(h, pid)["judul"], tugas(h, pid)["pemberi"], tugas(h, pid)["pemberi_id"]))
        d.brief("b.md", *header)  # berkas kedua dengan header sama → ambigu
        h = d.siklus("2026-10-16T15:00:03+07:00")["akbar"]
        self.assertEqual((None, None), (tugas(h, "proses-2001")["judul"], tugas(h, "proses-2001")["pemberi"]))

    def test_berkas_kosong_dan_bukan_md_tidak_dipakai(self):
        d = self.buat()
        (d.brief_dir / "kosong.md").write_text("")
        (d.brief_dir / "catatan.txt").write_text("# Brief untuk Desy (CTO) — Salah\nPeminta: Mas Dicky\n")
        d.desy(2001, "desy", "# Brief untuk Desy (CTO) — Salah\nPeminta: Mas Dicky")
        d.desy(2002, "via", "")
        t = tugas(d.siklus()["akbar"], "proses-2001")
        self.assertEqual((None, None), (t["judul"], t["pemberi"]))

    def test_header_di_direktori_brief_dibaca_ulang_bila_berkas_berubah(self):
        d = self.buat()
        d.brief("a.md", "# Brief untuk Desy (CTO) — Lama", "Peminta: Mas Dicky")
        d.desy(2001, "desy", "# Brief untuk Desy (CTO) — Lama\nPeminta: Mas Dicky\nKANARI")
        self.assertEqual("Lama", tugas(d.siklus()["akbar"], "proses-2001")["judul"])
        d.brief("a.md", "# Brief untuk Desy (CTO) — Baru dan lebih panjang", "Peminta: Mas Jati")
        self.assertIsNone(tugas(d.siklus("2026-10-16T15:00:03+07:00")["akbar"], "proses-2001")["judul"])
        d.proses(2002, HERMES + ["-p", "desy", "-z", "# Brief untuk Desy (CTO) — Baru dan lebih panjang\nPeminta: Mas Jati\n"],
                 "2026-10-16T14:00:00+07:00")
        t = tugas(d.siklus("2026-10-16T15:00:06+07:00")["akbar"], "proses-2002")
        self.assertEqual(("Baru dan lebih panjang", "Mas Jati"), (t["judul"], t["pemberi"]))


class UjiBriefTraversal(Dasar):
    def siapkan(self):
        d = self.buat()
        rahasia = d.workspace / "rahasia"
        rahasia.mkdir()
        (rahasia / "KANARI-rahasia.md").write_text(
            "# Brief TL — jdih-v3 — KANARI-JUDUL-RAHASIA\n**Peminta:** Mas Dicky (operator)\nKANARI-ISI\n", encoding="utf-8")
        os.symlink("../rahasia/KANARI-rahasia.md", d.brief_dir / "link.md")
        os.symlink("../rahasia", d.brief_dir / "sub")
        (d.brief_dir / "dirx.md").mkdir()
        (d.brief_dir / "asli.md").write_text("# Brief TL — absensimeeting — Rapi\n**Peminta:** Mas Jati (operator)\n",
                                             encoding="utf-8")
        os.symlink("asli.md", d.brief_dir / "dalam.md")
        return d

    def test_lock_dengan_brief_di_luar_direktori_brief_ditolak(self):
        d = self.siapkan()
        abs_host = str(d.workspace / "rahasia" / "KANARI-rahasia.md")
        ditolak = {
            "ebook-v2": "/workspace/brief/../rahasia/KANARI-rahasia.md",
            "survei3as": abs_host,  # path absolut host: tidak berawalan /workspace/
            "jdih-v3": "/workspace/brief/link.md",  # symlink di direktori brief → di luar
            "pemahaman-asn": "/workspace/brief/sub/KANARI-rahasia.md",  # direktori symlink → di luar
            "policytrack": "/workspace/brief/dirx.md",  # bukan berkas biasa
            "searchenginebsk": "/workspace/rahasia/KANARI-rahasia.md",  # di workspace tapi bukan di brief/
            "awalan-mirip": "/workspace2/brief/asli.md",  # bukan berawalan "/workspace/"
        }
        for slug, brief in ditolak.items():
            d.lock(slug, "alfa", brief=brief)
        d.lock("absensimeeting", "alfa", brief="/workspace/brief/dalam.md")  # symlink ke dalam brief/ → sah
        hasil = d.siklus()
        for slug in ditolak:
            t = tugas(hasil["akbar"], f"lock-{slug}")
            with self.subTest(slug=slug):
                self.assertEqual((f"Pekerjaan {PROYEK.get(slug, slug)}", None, None), (t["judul"], t["pemberi"], t["pemberi_id"]))
        t = tugas(hasil["akbar"], "lock-absensimeeting")
        self.assertEqual(("Rapi", "Mas Jati"), (t["judul"], t["pemberi"]))
        self.assertEqual([], hasil["dicky"]["tugas_aktif"])
        self.assertEqual(["lock-absensimeeting"], [x["id"] for x in hasil["jati"]["tugas_aktif"]])
        self.assertTrue(all("Mas Dicky" not in x for x in teks(hasil["dicky"])))

    def test_pencocokan_header_proses_tidak_mengikuti_symlink_ke_luar(self):
        d = self.siapkan()
        z = "# Brief TL — jdih-v3 — KANARI-JUDUL-RAHASIA\n**Peminta:** Mas Dicky (operator)\nKANARI-ISI"
        d.desy(2001, "desy", z)
        hasil = d.siklus()
        t = tugas(hasil["akbar"], "proses-2001")
        self.assertEqual((None, None, None), (t["judul"], t["pemberi"], t["pemberi_id"]))
        self.assertEqual([], hasil["dicky"]["tugas_aktif"])


class UjiLock(Dasar):
    def test_slug_dan_tl(self):
        sah = ["a", "a-b", "a1-b2-c3", "x" * 64]
        tak_sah = ["x" * 65, "Bad_Slug", "-a", "a-", "a--b", "a b", "A", "a_b", ".tersembunyi"]
        d = self.buat()
        for s in sah + tak_sah:
            d.lock(s, "alfa")
        d.lock("tl-desy", "desy")
        d.lock("tl-ngawur", "Alfa")
        d.lock("tanpa-tl", isi="mulai=2026-10-16T09:00:00+07:00\nKANARI\n")
        d.lock("rusak", isi="ini bukan lock KANARI\n")
        (d.locks / "bukan-lock.txt").write_text("tl=alfa\n")
        (d.locks / ".koordinasi.lock.999").write_text("tl=alfa\n")
        (d.locks / "direktori.lock").mkdir()
        (d.locks / "ganda.lock.bak").write_text("tl=alfa\n")
        h = d.siklus()["akbar"]
        self.assertEqual(sorted(f"lock-{s}" for s in sah), sorted(t["id"] for t in h["tugas_aktif"]))
        self.assertEqual([], h["galat"])
        self.assertEqual("bebas", agen(h, "desy")["status"])

    def test_isi_lock_dibaca_maksimal_4096_byte(self):
        d = self.buat()
        d.lock("a", isi="tl=alfa\n" + "x" * 5000 + "\nmulai=2026-10-16T09:00:00+07:00\nKANARI\n")
        d.lock("b", isi="tl=beta\nmulai=2026-10-16T09:00:00+07:00\n" + "x" * 5000 + "\nKANARI\n")
        d.lock("c", isi="y" * 5000 + "\ntl=carli\n")
        h = d.siklus()["akbar"]
        self.assertIsNone(tugas(h, "lock-a")["mulai"])
        self.assertEqual("2026-10-16T09:00:00+07:00", tugas(h, "lock-b")["mulai"])
        self.assertIsNone(tugas(h, "lock-c"))

    def test_mulai_lock(self):
        d = self.buat()
        d.lock("a", "alfa", mulai="kemarin")
        d.lock("b", "alfa", mulai=None)
        d.lock("c", "alfa", mulai="2026-10-16T02:00:00+00:00")  # UTC → WIB
        d.lock("d", "alfa", mulai="2026-10-16T09:30:15")  # tanpa zona = WIB (keputusan lokal)
        h = d.siklus()["akbar"]
        self.assertEqual([None, None, "2026-10-16T09:00:00+07:00", "2026-10-16T09:30:15+07:00"],
                         [tugas(h, f"lock-{s}")["mulai"] for s in "abcd"])
        # urutan: mulai naik, null terakhir
        self.assertEqual(["lock-c", "lock-d", "lock-a", "lock-b"], [t["id"] for t in h["tugas_aktif"]])

    def test_urutan_menunggu_dulu_lalu_mulai_lalu_id(self):
        d = self.buat()
        d.lock("jalan-awal", "alfa", mulai="2026-10-16T08:00:00+07:00")
        d.lock("tunggu-akhir", "beta", mulai="2026-10-16T12:00:00+07:00")
        d.lock("tunggu-awal-b", "beta", mulai="2026-10-16T07:00:00+07:00")
        d.lock("tunggu-awal-a", "beta", mulai="2026-10-16T07:00:00+07:00")
        d.proses(100, ["hermes", "-p", "alfa"])
        h = d.siklus()["akbar"]
        self.assertEqual(["lock-tunggu-awal-a", "lock-tunggu-awal-b", "lock-tunggu-akhir", "lock-jalan-awal"],
                         [t["id"] for t in h["tugas_aktif"]])
        self.assertEqual(["menunggu"] * 3 + ["jalan"], [t["status"] for t in h["tugas_aktif"]])


class UjiLog(Dasar):
    def test_baris_belum_lengkap_diproses_tepat_sekali_setelah_lengkap(self):
        d = self.buat()
        penuh = json.dumps(ajeng_msg("2026-10-16T14:59:00", "Ünal"), ensure_ascii=False).encode("utf-8") + b"\n"
        potong = penuh.index("Ü".encode("utf-8")) + 1  # di tengah karakter 2-byte
        awal = json.dumps(ajeng_msg("2026-10-16T14:58:00", "Pak Akbar")).encode("utf-8") + b"\n"
        with open(d.activity, "ab") as f:
            f.write(awal + penuh[:potong])
        h = d.siklus()["akbar"]
        self.assertEqual(["Pak Akbar mengirim pesan ke Ajeng"], teks(h))
        with open(d.activity, "ab") as f:
            f.write(penuh[potong:])
        for i in range(3):
            h = d.siklus(f"2026-10-16T15:00:0{i}+07:00")["akbar"]
            self.assertEqual(["Pak Akbar mengirim pesan ke Ajeng", "Ünal mengirim pesan ke Ajeng"], teks(h))
        self.assertEqual(0, d.g.baris_dilewati)

    def test_baris_utuh_tanpa_newline_di_akhir_menunggu_newline(self):
        d = self.buat()
        with open(d.activity, "ab") as f:
            f.write(json.dumps(ajeng_msg("2026-10-16T14:59:00", "Pak Akbar")).encode("utf-8"))
        self.assertEqual([], teks(d.siklus()["akbar"]))
        with open(d.activity, "ab") as f:
            f.write(b"\n")
        self.assertEqual(["Pak Akbar mengirim pesan ke Ajeng"], teks(d.siklus("2026-10-16T15:00:03+07:00")["akbar"]))
        self.assertEqual(["Pak Akbar mengirim pesan ke Ajeng"], teks(d.siklus("2026-10-16T15:00:06+07:00")["akbar"]))

    def test_baris_rusak_dilewati_dan_dihitung(self):
        d = self.buat()
        d.tambah('{"type": "tool", "role": "owner", KANARI', '[1, 2, "KANARI"]', '"KANARI"', '123', 'null', '', 'KANARI bukan json',
                 {"type": "msg", "name": "Pak Akbar", "text": "KANARI"},  # tanpa ts
                 {"type": "msg", "name": "Pak Akbar", "text": "KANARI", "ts": "2026-10-16 14:59:00"},
                 {"type": "msg", "name": "Pak Akbar", "text": "KANARI", "ts": "16-10-2026T14:59:00"},
                 {"type": "msg", "name": "Pak Akbar", "text": "KANARI", "ts": "2026-10-16T14:59"},
                 {"type": "msg", "name": "Pak Akbar", "text": "KANARI", "ts": "2026-10-16T14:59:00.5"},
                 {"type": "msg", "name": "Pak Akbar", "text": "KANARI", "ts": "2026-10-16T14:59:00+07:00"},
                 {"type": "msg", "name": "Pak Akbar", "text": "KANARI", "ts": "2026-13-45T25:61:61"},
                 {"type": "msg", "name": "Pak Akbar", "text": "KANARI", "ts": 20261016145900},
                 {"type": "msg", "name": "Pak Akbar", "text": "KANARI", "ts": ["2026-10-16T14:59:00"]},
                 ajeng_msg("2026-10-16T14:59:30", "Mas Jati"))
        with open(d.activity, "ab") as f:
            f.write(b'{"type": "msg", "ts": "2026-10-16T14:59:40", "name": "Mas \xff\xfe Dicky", "text": "KANARI"}\n')
        h = d.siklus()["akbar"]
        self.assertEqual(["Mas Jati mengirim pesan ke Ajeng", "Mas \ufffd\ufffd Dicky mengirim pesan ke Ajeng"], teks(h))
        self.assertEqual(18, d.g.baris_baru)
        self.assertEqual(16, d.g.baris_dilewati)
        self.assertEqual([], h["galat"])

    def test_log_mengecil_dan_inode_berganti_membuang_keadaan_turunan_log(self):
        d = self.buat()
        d.lock("jdih-v3", "alfa", brief=d.brief("b.md", "# Brief TL — jdih-v3 — Audit", "**Peminta:** Mas Dicky (operator)"))
        d.tambah(ajeng_msg("2026-10-16T14:50:00", "Pak Akbar"), ajeng_msg("2026-10-16T14:51:00", "Mas Dicky"),
                 ajeng_msg("2026-10-16T14:51:30", "Mas Dicky"), ajeng_tool("2026-10-16T14:52:00", "Pak Akbar", "read_file"),
                 tim("2026-10-16T14:52:30", "alfa", "write_file", sid="KANARI-A"),
                 tim("2026-10-16T14:53:00", "alfa", "write_file", sid="KANARI-A"))
        h1 = d.siklus("2026-10-16T15:00:00+07:00")["akbar"]
        self.assertIn("Pak Akbar mengirim pesan ke Ajeng", teks(h1))
        self.assertIsNotNone(tugas(h1, "ajeng-akbar"))
        baru = d.akar / "baru.jsonl"  # dibuat selagi berkas lama masih ada → inode pasti berbeda
        baru.write_text(json.dumps(tim("2026-10-16T14:58:00", "alfa", "patch", sid="KANARI-B")) + "\n", encoding="utf-8")
        lama = (os.stat(d.activity).st_ino, os.stat(d.activity).st_size)
        os.replace(baru, d.activity)
        self.assertNotEqual(lama[0], os.stat(d.activity).st_ino)
        self.assertLess(os.stat(d.activity).st_size, lama[1])
        h2 = d.siklus("2026-10-16T15:00:03+07:00")
        akbar = h2["akbar"]
        self.assertEqual(["Alfa mulai JDIH", "Alfa mulai bekerja"], teks(akbar))  # lock tetap; log lama dibuang
        self.assertIsNone(tugas(akbar, "ajeng-akbar"))
        self.assertIsNone(tugas(akbar, "ajeng-dicky"))
        self.assertIsNone(agen(akbar, "ajeng")["terakhir_aktif"])
        self.assertEqual("2026-10-16T14:58:00+07:00", agen(akbar, "alfa")["terakhir_aktif"])
        # dibaca dari awal sebagai backfill: pemilik akbar, bukan pemilik tugas (Mas Dicky)
        self.assertEqual(["Alfa mulai JDIH"], teks(h2["dicky"]))
        # siklus sesudahnya: baris baru = live
        d.tambah(tim("2026-10-16T15:00:04", "alfa", "patch", sid="KANARI-C"))
        h3 = d.siklus("2026-10-16T15:00:06+07:00")
        self.assertEqual(["Alfa mulai JDIH", "Alfa mulai bekerja · JDIH"], teks(h3["dicky"]))

    def test_inode_berganti_dengan_ukuran_lebih_besar_dibaca_ulang_sebagai_backfill(self):
        d = self.buat()
        d.lock("jdih-v3", "alfa", brief=d.brief("b.md", "# Brief TL — jdih-v3 — Audit", "Peminta: Mas Dicky"))
        d.tambah(tim("2026-10-16T14:00:00", "alfa", "patch", sid="KANARI-A"))
        d.siklus("2026-10-16T15:00:00+07:00")
        baru = d.akar / "baru.jsonl"
        baru.write_text(json.dumps(tim("2026-10-16T14:00:00", "alfa", "patch", sid="KANARI-A")) + "\n" +
                        json.dumps(tim("2026-10-16T14:30:00", "alfa", "patch", sid="KANARI-B")) + "\n", encoding="utf-8")
        ino = os.stat(d.activity).st_ino
        os.replace(baru, d.activity)
        self.assertNotEqual(ino, os.stat(d.activity).st_ino)
        h = d.siklus("2026-10-16T15:00:03+07:00")
        self.assertEqual(["Alfa mulai bekerja", "Alfa mulai bekerja"], [x for x in teks(h["akbar"]) if "bekerja" in x])
        self.assertEqual(["Alfa mulai JDIH"], teks(h["dicky"]))  # backfill → tidak jadi milik Mas Dicky

    def test_log_mengecil_inode_sama_dipotong(self):
        d = self.buat()
        d.tambah(ajeng_msg("2026-10-16T14:50:00", "Pak Akbar"), ajeng_msg("2026-10-16T14:51:00", "Mas Dicky"))
        d.siklus()
        with open(d.activity, "w", encoding="utf-8") as f:  # inode tetap, ukuran mengecil
            f.write(json.dumps(ajeng_msg("2026-10-16T14:59:00", "Mas Jati")) + "\n")
        h = d.siklus("2026-10-16T15:00:03+07:00")["akbar"]
        self.assertEqual(["Mas Jati mengirim pesan ke Ajeng"], teks(h))

    def test_log_hilang_lalu_pulih(self):
        d = self.buat()
        d.lock("jdih-v3", "alfa", brief=d.brief("b.md", "# Brief TL — jdih-v3 — Audit", "Peminta: Mas Dicky"))
        d.tambah(ajeng_msg("2026-10-16T14:55:00", "Pak Akbar"), tim("2026-10-16T14:56:00", "alfa", "patch", sid="KANARI-A"))
        h1 = d.siklus("2026-10-16T15:00:00+07:00")
        os.link(d.activity, d.akar / "cadangan.jsonl")  # inode yang sama akan muncul lagi
        ino = os.stat(d.activity).st_ino
        os.remove(d.activity)
        h2 = d.siklus("2026-10-16T15:00:03+07:00")
        for p in PENONTON:
            self.assertEqual([GALAT_LOG], h2[p]["galat"])
            self.assertEqual(h1[p]["tugas_aktif"], h2[p]["tugas_aktif"])  # keadaan lama dipertahankan
            self.assertEqual(h1[p]["riwayat_hari_ini"], h2[p]["riwayat_hari_ini"])
        self.assertEqual("2026-10-16T14:56:00+07:00", agen(h2["akbar"], "alfa")["terakhir_aktif"])
        d.siklus("2026-10-16T15:00:06+07:00")
        os.link(d.akar / "cadangan.jsonl", d.activity)  # muncul lagi: inode sama, ukuran tidak lebih kecil
        self.assertEqual(ino, os.stat(d.activity).st_ino)
        d.tambah(tim("2026-10-16T14:59:00", "alfa", "patch", sid="KANARI-B"))
        h3 = d.siklus("2026-10-16T15:00:09+07:00")
        for p in PENONTON:
            self.assertEqual([], h3[p]["galat"])
        self.assertEqual(1, teks(h3["akbar"]).count("Pak Akbar mengirim pesan ke Ajeng"))  # tanpa duplikat
        self.assertEqual(2, teks(h3["akbar"]).count("Alfa mulai bekerja"))
        self.assertEqual(["Alfa mulai JDIH"], teks(h3["dicky"]))  # dibaca dari awal = backfill

    def test_log_tidak_ada_sejak_awal(self):
        d = self.buat()
        os.remove(d.activity)
        d.lock("jdih-v3", "alfa")
        h = d.siklus()["akbar"]
        self.assertEqual([GALAT_LOG], h["galat"])
        self.assertEqual(["lock-jdih-v3"], [t["id"] for t in h["tugas_aktif"]])
        d.tambah(tim("2026-10-16T14:59:00", "alfa", "patch", sid="KANARI-A"))
        h = d.siklus("2026-10-16T15:00:03+07:00")["akbar"]
        self.assertEqual([], h["galat"])
        self.assertEqual("menulis berkas · JDIH", tugas(h, "lock-jdih-v3")["langkah_terakhir"])

    def test_log_berupa_direktori_adalah_galat(self):
        d = self.buat()
        os.remove(d.activity)
        d.activity.mkdir()
        self.assertEqual([GALAT_LOG], d.siklus()["akbar"]["galat"])

    def test_pesan_dan_urutan_peristiwa(self):
        d = self.buat()
        d.tambah(ajeng_tool("2026-10-16T14:59:00", "Mas Dicky", "clarify"), ajeng_tool("2026-10-16T14:59:00", "Pak Akbar", "clarify"),
                 ajeng_tool("2026-10-16T14:59:00", "Mas Jati", "clarify"), ajeng_tool("2026-10-16T14:58:00", "Mas Jati", "clarify"))
        h = d.siklus()["akbar"]
        self.assertEqual(["2026-10-16T14:58:00+07:00", "2026-10-16T14:59:00+07:00", "2026-10-16T14:59:00+07:00",
                          "2026-10-16T14:59:00+07:00"], [r["waktu"] for r in h["riwayat_hari_ini"]])
        self.assertEqual(["Ajeng meminta keputusan Mas Jati", "Ajeng meminta keputusan Mas Dicky",
                          "Ajeng meminta keputusan Pak Akbar", "Ajeng meminta keputusan Mas Jati"], teks(h))
        self.assertEqual({"ajeng"}, {r["pelaku"] for r in h["riwayat_hari_ini"]})


class UjiGalat(Dasar):
    SEMUA = sorted([GALAT_LOG, GALAT_PROSES, GALAT_LOCK, GALAT_PETA])

    def test_peta_project_rusak_slug_apa_adanya(self):
        for isi in ("{rusak", "[]", '"teks"', "", "null"):
            with self.subTest(isi=isi):
                d = self.buat(proyek_teks=isi)
                d.lock("jdih-v3", "alfa")
                hasil = d.siklus()
                for p in PENONTON:
                    self.assertEqual([GALAT_PETA], hasil[p]["galat"])
                t = tugas(hasil["akbar"], "lock-jdih-v3")
                self.assertEqual(("jdih-v3", "Pekerjaan jdih-v3"), (t["project_nama"], t["judul"]))
                self.assertIn("Alfa mulai jdih-v3", teks(hasil["akbar"]))

    def test_peta_project_tidak_ada_pulih_dan_nilai_bukan_string(self):
        d = self.buat()
        d.lock("jdih-v3", "alfa")
        d.lock("policytrack", "alfa")
        os.remove(d.proyek)
        self.assertEqual([GALAT_PETA], d.siklus()["akbar"]["galat"])
        d.proyek.write_text(json.dumps({"jdih-v3": "JDIH", "policytrack": 7}), encoding="utf-8")
        h = d.siklus("2026-10-16T15:00:03+07:00")["akbar"]
        self.assertEqual([], h["galat"])
        self.assertEqual("JDIH", tugas(h, "lock-jdih-v3")["project_nama"])
        self.assertEqual("policytrack", tugas(h, "lock-policytrack")["project_nama"])

    def test_peta_terakhir_yang_baik_dipakai_bila_berkas_rusak_kemudian(self):  # §4 "keadaan terakhir yang diketahui"
        d = self.buat()
        d.lock("jdih-v3", "alfa")
        d.siklus()
        d.proyek.write_text("{rusak", encoding="utf-8")
        h = d.siklus("2026-10-16T15:00:03+07:00")["akbar"]
        self.assertEqual(([GALAT_PETA], "JDIH"), (h["galat"], tugas(h, "lock-jdih-v3")["project_nama"]))

    def test_direktori_proc_tidak_ada(self):
        d = self.buat()
        d.lock("jdih-v3", "alfa")
        d.proses(100, ["hermes", "-p", "alfa"])
        self.assertEqual("jalan", agen(d.siklus()["akbar"], "alfa")["status"])
        shutil.rmtree(d.proc)
        hasil = d.siklus("2026-10-16T15:00:03+07:00")
        for p in PENONTON:
            self.assertEqual([GALAT_PROSES], hasil[p]["galat"])
        self.assertEqual("jalan", agen(hasil["akbar"], "alfa")["status"])  # keadaan terakhir dipertahankan
        d2 = self.buat()
        shutil.rmtree(d2.proc)
        d2.lock("jdih-v3", "alfa")
        h = d2.siklus()["akbar"]
        self.assertEqual(([GALAT_PROSES], "menunggu"), (h["galat"], agen(h, "alfa")["status"]))
        d2.proc.mkdir()
        self.assertEqual([], d2.siklus("2026-10-16T15:00:03+07:00")["akbar"]["galat"])

    def test_direktori_locks_tidak_ada(self):
        d = self.buat()
        d.lock("jdih-v3", "alfa")
        self.assertEqual(["lock-jdih-v3"], [t["id"] for t in d.siklus()["akbar"]["tugas_aktif"]])
        shutil.rmtree(d.locks)
        hasil = d.siklus("2026-10-16T15:00:03+07:00")
        for p in PENONTON:
            self.assertEqual([GALAT_LOCK], hasil[p]["galat"])
        self.assertEqual(["lock-jdih-v3"], [t["id"] for t in hasil["akbar"]["tugas_aktif"]])  # dipertahankan
        self.assertEqual(["Alfa mulai JDIH"], teks(hasil["akbar"]))  # tanpa 'selesai' palsu
        d2 = self.buat()
        shutil.rmtree(d2.locks)
        h = d2.siklus()["akbar"]
        self.assertEqual(([GALAT_LOCK], []), (h["galat"], h["tugas_aktif"]))
        d2.locks.mkdir()
        self.assertEqual([], d2.siklus("2026-10-16T15:00:03+07:00")["akbar"]["galat"])

    def test_semua_galat_urut_abjad_unik_dan_sama_di_tiga_berkas(self):
        d = self.buat(proyek_teks="{")
        os.remove(d.activity)
        shutil.rmtree(d.proc)
        shutil.rmtree(d.locks)
        hasil = d.siklus()
        for p in PENONTON:
            self.assertEqual(self.SEMUA, hasil[p]["galat"])
        d.siklus("2026-10-16T15:00:03+07:00")
        self.assertEqual(self.SEMUA, d.baca()["akbar"]["galat"])

    def test_setiap_kombinasi_galat_urut_abjad(self):  # urutan himpunan acak per proses → coba semua kombinasi
        rusak = {GALAT_LOG: lambda d: os.remove(d.activity), GALAT_PROSES: lambda d: shutil.rmtree(d.proc),
                 GALAT_LOCK: lambda d: shutil.rmtree(d.locks), GALAT_PETA: lambda d: d.proyek.write_text("{")}
        for mask in range(1, 16):
            pilih = [teks_galat for i, teks_galat in enumerate(rusak) if mask >> i & 1]
            with self.subTest(galat=pilih):
                d = self.buat()
                for teks_galat in pilih:
                    rusak[teks_galat](d)
                for p, h in d.siklus().items():
                    self.assertEqual(sorted(pilih), h["galat"])

    def test_stdout_galat_hanya_teks_tetap_dan_berubah_saja(self):
        d = self.buat()
        os.remove(d.activity)
        n = [0]
        orig = d.g.siklus

        def hitung(sekarang):
            n[0] += 1
            if n[0] == 4:  # log muncul lagi di siklus ke-4
                d.tambah(ajeng_msg("2026-10-16T14:59:00"))
            orig(sekarang)

        d.g.siklus = hitung
        t = [0.0]
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            generator.loop(d.g, 3.0, lambda: n[0] >= 6, jam=lambda: t[0], tidur=lambda s: t.__setitem__(0, t[0] + s))
        d.stdout += buf.getvalue()
        baris = [b for b in buf.getvalue().splitlines() if b.startswith("galat")]
        self.assertEqual(2, len(baris), buf.getvalue())
        self.assertIn(GALAT_LOG, baris[0])
        self.assertNotIn(GALAT_LOG, baris[1])


class UjiRiwayat(Dasar):
    def test_maksimal_300_terbaru_urut_naik(self):
        d = self.buat()
        d.tambah(*[ajeng_msg(f"2026-10-16T08:{i // 60:02d}:{i % 60:02d}", f"Pengirim{chr(65 + i // 26)}{chr(65 + i % 26)}")
                   for i in range(350)])
        h = d.siklus()["akbar"]
        nama = [f"Pengirim{chr(65 + i // 26)}{chr(65 + i % 26)}" for i in range(350)]
        self.assertEqual([f"{n} mengirim pesan ke Ajeng" for n in nama[50:]], teks(h))
        self.assertEqual(300, len(h["riwayat_hari_ini"]))

    def test_maksimal_300_per_berkas_penonton(self):
        d = self.buat()
        d.tambah(*[ajeng_tool(f"2026-10-16T08:{i // 60:02d}:{i % 60:02d}", "Mas Dicky", "clarify") for i in range(350)])
        hasil = d.siklus()
        for p in ("akbar", "dicky"):
            self.assertEqual(300, len(hasil[p]["riwayat_hari_ini"]))
            self.assertEqual("2026-10-16T08:00:50+07:00", hasil[p]["riwayat_hari_ini"][0]["waktu"])
            self.assertEqual("2026-10-16T08:05:49+07:00", hasil[p]["riwayat_hari_ini"][-1]["waktu"])
        self.assertEqual([], hasil["jati"]["riwayat_hari_ini"])

    def test_hari_berganti_peristiwa_kemarin_tidak_tampil(self):
        d = self.buat()
        d.lock("jdih-v3", "alfa", mulai="2026-10-16T09:00:00+07:00", brief=d.brief("b.md", "# Brief TL — jdih-v3 — A", "Peminta: Mas Dicky"))
        d.tambah(ajeng_msg("2026-10-15T23:59:59", "Pak Akbar"), ajeng_tool("2026-10-16T00:00:00", "Mas Dicky", "clarify"),
                 ajeng_msg("2026-10-16T23:59:59", "Mas Jati"))
        h = d.siklus("2026-10-16T23:59:59+07:00")
        self.assertEqual(["Ajeng meminta keputusan Mas Dicky", "Alfa mulai JDIH", "Mas Jati mengirim pesan ke Ajeng"],
                         teks(h["akbar"]))
        d.tambah(ajeng_msg("2026-10-17T00:00:03", "Pak Akbar"))
        h = d.siklus("2026-10-17T00:00:05+07:00")
        self.assertEqual(["Pak Akbar mengirim pesan ke Ajeng"], teks(h["akbar"]))
        self.assertEqual([], teks(h["dicky"]))
        self.assertEqual([], teks(h["jati"]))

    def test_batas_awal_hari_00_00_00(self):
        d = self.buat()
        d.tambah(ajeng_tool("2026-10-15T23:59:59", "Pak Akbar", "clarify"), ajeng_tool("2026-10-16T00:00:00", "Pak Akbar", "clarify"),
                 ajeng_tool("2026-10-17T00:00:00", "Pak Akbar", "clarify"))
        self.assertEqual(["2026-10-16T00:00:00+07:00"], [r["waktu"] for r in d.siklus("2026-10-16T00:00:01+07:00")["akbar"]["riwayat_hari_ini"]])

    def test_dedupe_pesan_peminta_5_menit(self):
        d = self.buat()
        d.tambah(ajeng_msg("2026-10-16T10:00:00", "Pak Akbar"), ajeng_msg("2026-10-16T10:01:00", "Pak Akbar"),
                 ajeng_msg("2026-10-16T10:01:30", "Mas Dicky"), ajeng_msg("2026-10-16T10:04:00", "Pak Akbar"),
                 ajeng_msg("2026-10-16T10:04:30", "Mas Dicky"), ajeng_msg("2026-10-16T10:20:00", "Pak Akbar"),
                 ajeng_msg("2026-10-16T10:20:10", "Pak Akbar"), ajeng_msg("2026-10-16T10:20:10", "Lala"))
        h = d.siklus()["akbar"]
        self.assertEqual([("2026-10-16T10:00:00+07:00", "Pak Akbar mengirim pesan ke Ajeng"),
                          ("2026-10-16T10:01:30+07:00", "Mas Dicky mengirim pesan ke Ajeng"),
                          ("2026-10-16T10:20:00+07:00", "Pak Akbar mengirim pesan ke Ajeng"),
                          ("2026-10-16T10:20:10+07:00", "Lala mengirim pesan ke Ajeng")],
                         [(r["waktu"], r["teks"]) for r in h["riwayat_hari_ini"]])

    def test_dedupe_berjangkar_pada_peristiwa_yang_ditampilkan(self):
        # keputusan lokal: jendela 5 menit dihitung dari pesan yang TAMPIL terakhir (>= 300 dtk), bukan dari baris terakhir
        d = self.buat()
        d.tambah(ajeng_msg("2026-10-16T10:00:00"), ajeng_msg("2026-10-16T10:04:00"), ajeng_msg("2026-10-16T10:05:00"),
                 ajeng_msg("2026-10-16T10:09:59"), ajeng_msg("2026-10-16T10:10:00"))
        self.assertEqual(["2026-10-16T10:00:00+07:00", "2026-10-16T10:05:00+07:00", "2026-10-16T10:10:00+07:00"],
                         [r["waktu"] for r in d.siklus()["akbar"]["riwayat_hari_ini"]])

    def test_dedupe_juga_antar_siklus(self):
        d = self.buat()
        d.tambah(ajeng_msg("2026-10-16T10:00:00"))
        d.siklus("2026-10-16T10:00:03+07:00")
        d.tambah(ajeng_msg("2026-10-16T10:01:00"))
        self.assertEqual(1, len(d.siklus("2026-10-16T10:01:03+07:00")["akbar"]["riwayat_hari_ini"]))

    def test_pengirim_tak_dikenal(self):
        d = self.buat()
        d.tambah(ajeng_msg("2026-10-16T14:58:00", "Lala"),
                 {"type": "msg", "role": "bot", "name": "?", "text": "KANARI", "ts": "2026-10-16T14:58:10"},
                 {"type": "msg", "text": "KANARI", "ts": "2026-10-16T14:58:20"},
                 {"type": "msg", "name": "  ", "text": "KANARI", "ts": "2026-10-16T14:58:25"},
                 {"type": "msg", "name": 42, "text": "KANARI", "ts": "2026-10-16T14:58:26"},
                 ajeng_msg("2026-10-16T14:58:30", "ani@contoh.go.id"))
        hasil = d.siklus()
        h = hasil["akbar"]
        self.assertEqual(["Lala mengirim pesan ke Ajeng", "Pengirim tak dikenal mengirim pesan ke Ajeng",
                          "(disaring) mengirim pesan ke Ajeng"], teks(h))
        self.assertEqual({kode_r("Lala"), kode_r("Pengirim tak dikenal"), kode_r("(disaring)")},
                         {t["id"] for t in h["tugas_aktif"]})
        for nama in ("Lala", "Pengirim tak dikenal", "(disaring)"):
            t = tugas(h, kode_r(nama))
            self.assertEqual((nama, None, "Ajeng", "ajeng", "Permintaan lewat Telegram", None, None),
                             (t["pemberi"], t["pemberi_id"], t["pengerja"], t["pengerja_id"], t["judul"], t["project"], t["project_nama"]))
        for p in ("dicky", "jati"):  # milik Pak Akbar saja (fail-closed)
            self.assertEqual(([], []), (hasil[p]["tugas_aktif"], hasil[p]["riwayat_hari_ini"]))
            self.assertEqual("sibuk", agen(hasil[p], "ajeng")["status"])
            self.assertIsNone(agen(hasil[p], "ajeng")["terakhir_aktif"])

    def test_pengirim_bernama_seperti_id_orang_tidak_bertabrakan(self):
        d = self.buat()
        d.tambah(ajeng_msg("2026-10-16T14:58:00", "dicky"), ajeng_msg("2026-10-16T14:58:10", "Mas Dicky"),
                 ajeng_msg("2026-10-16T14:58:20", "akbar"), ajeng_msg("2026-10-16T14:58:30", "Pak Akbar"))
        hasil = d.siklus()
        h = hasil["akbar"]
        self.assertEqual({"ajeng-dicky", "ajeng-akbar", kode_r("dicky"), kode_r("akbar")}, {t["id"] for t in h["tugas_aktif"]})
        self.assertEqual(("Mas Dicky", "dicky"), (tugas(h, "ajeng-dicky")["pemberi"], tugas(h, "ajeng-dicky")["pemberi_id"]))
        self.assertEqual(("dicky", None), (tugas(h, kode_r("dicky"))["pemberi"], tugas(h, kode_r("dicky"))["pemberi_id"]))
        self.assertEqual(["ajeng-dicky"], [t["id"] for t in hasil["dicky"]["tugas_aktif"]])  # tiruan tidak ikut milik Mas Dicky
        self.assertEqual(["dicky mengirim pesan ke Ajeng", "Mas Dicky mengirim pesan ke Ajeng", "akbar mengirim pesan ke Ajeng",
                          "Pak Akbar mengirim pesan ke Ajeng"], teks(h))
        self.assertEqual(["Mas Dicky mengirim pesan ke Ajeng"], teks(hasil["dicky"]))

    def test_tugas_ajeng_hanya_bila_baris_kurang_dari_10_menit(self):
        d = self.buat()
        d.tambah(ajeng_msg("2026-10-16T14:50:01", "Pak Akbar"), ajeng_msg("2026-10-16T14:50:00", "Mas Dicky"))
        h = d.siklus("2026-10-16T15:00:00+07:00")["akbar"]
        self.assertEqual(["ajeng-akbar"], [t["id"] for t in h["tugas_aktif"]])  # umur Dicky tepat 10 menit → tidak lagi
        d2 = self.buat()
        d2.tambah(ajeng_msg("2026-10-16T14:50:01", "Pak Akbar"), ajeng_msg("2026-10-16T14:50:00", "Mas Dicky"))
        h2 = d2.siklus("2026-10-16T14:59:59+07:00")["akbar"]
        self.assertEqual(["ajeng-akbar", "ajeng-dicky"], sorted(t["id"] for t in h2["tugas_aktif"]))

    def test_rangkaian_ajeng_terputus_jeda_lebih_dari_10_menit(self):
        d = self.buat()
        d.tambah(ajeng_msg("2026-10-16T14:00:00"), ajeng_msg("2026-10-16T14:10:00"), ajeng_msg("2026-10-16T14:20:01"),
                 ajeng_msg("2026-10-16T14:30:01"), ajeng_tool("2026-10-16T14:58:00", "Pak Akbar", "read_file"))
        t = tugas(d.siklus()["akbar"], "ajeng-akbar")
        self.assertEqual("2026-10-16T14:58:00+07:00", t["mulai"])  # jeda 28 menit memutus
        d2 = self.buat()
        d2.tambah(ajeng_msg("2026-10-16T14:48:00"), ajeng_msg("2026-10-16T14:58:00"))
        self.assertEqual("2026-10-16T14:48:00+07:00", tugas(d2.siklus()["akbar"], "ajeng-akbar")["mulai"])  # jeda tepat 10 menit tidak memutus

    def test_ajeng_catat_progres_setor_dan_memanggil_via(self):
        d = self.buat()
        d.tambah(ajeng_tool("2026-10-16T14:58:00", "Mas Dicky", "mcp__obsidian_bsk__catat_progres"),
                 ajeng_tool("2026-10-16T14:58:10", "Mas Dicky", "mcp__obsidian_bsk__setor"),
                 ajeng_tool("2026-10-16T14:58:20", "Mas Jati", "terminal", "hermes -p via -z 'KANARI'"),
                 ajeng_tool("2026-10-16T14:58:30", "Mas Jati", "terminal", "hermes -p desy -z 'KANARI'"),
                 ajeng_tool("2026-10-16T14:58:40", "Mas Jati", "terminal", "hermes -p alfa -z 'KANARI'"),
                 ajeng_tool("2026-10-16T14:58:50", "Mas Jati", "execute_code", "ssh bskdev-host x"))
        hasil = d.siklus()
        self.assertEqual(["Ajeng mencatat kemajuan", "Ajeng menyetor dokumen ke bank dokumen"], teks(hasil["dicky"]))
        self.assertEqual(["Ajeng memanggil Via", "Ajeng memanggil Desy"], teks(hasil["jati"]))
        self.assertEqual(4, len(teks(hasil["akbar"])))

    def test_lock_mulai_selesai_dan_berganti(self):
        d = self.buat()
        d.lock("jdih-v3", "alfa", mulai="2026-10-16T09:00:00+07:00", brief=d.brief("b.md", "# Brief TL — jdih-v3 — A", "Peminta: Mas Dicky"))
        d.lock("policytrack", "beta", mulai="2026-10-15T09:00:00+07:00")
        d.lock("ebook-v2", "carli", mulai=None)
        h1 = d.siklus("2026-10-16T14:00:00+07:00")
        self.assertEqual([("2026-10-16T09:00:00+07:00", "alfa", "Alfa mulai JDIH")],
                         [(r["waktu"], r["pelaku"], r["teks"]) for r in h1["akbar"]["riwayat_hari_ini"]])
        self.assertEqual(h1["akbar"]["riwayat_hari_ini"], h1["dicky"]["riwayat_hari_ini"])
        (d.locks / "policytrack.lock").unlink()
        d.lock("jdih-v3", "alfa", mulai="2026-10-16T13:00:00+07:00", brief="/workspace/brief/b.md")  # mulai berganti
        d.lock("ebook-v2", "alfa", mulai=None)  # tl berganti
        h2 = d.siklus("2026-10-16T14:00:03+07:00")
        self.assertEqual(sorted([("2026-10-16T09:00:00+07:00", "alfa", "Alfa mulai JDIH"),
                                 ("2026-10-16T13:00:00+07:00", "alfa", "Alfa mulai JDIH"),
                                 ("2026-10-16T14:00:03+07:00", "alfa", "Alfa selesai JDIH"),
                                 ("2026-10-16T14:00:03+07:00", "beta", "Beta selesai PolicyTrack"),
                                 ("2026-10-16T14:00:03+07:00", "carli", "Carli selesai eBook")]),
                         sorted((r["waktu"], r["pelaku"], r["teks"]) for r in h2["akbar"]["riwayat_hari_ini"]))
        self.assertEqual(["2026-10-16T09:00:00+07:00", "2026-10-16T13:00:00+07:00"] + ["2026-10-16T14:00:03+07:00"] * 3,
                         [r["waktu"] for r in h2["akbar"]["riwayat_hari_ini"]])
        self.assertEqual(["Alfa mulai JDIH", "Alfa mulai JDIH", "Alfa selesai JDIH"], teks(h2["dicky"]))
        self.assertEqual([], teks(h2["jati"]))
        for f in d.locks.glob("*.lock"):
            f.unlink()
        h3 = d.siklus("2026-10-16T14:00:06+07:00")
        self.assertEqual(7, len(h3["akbar"]["riwayat_hari_ini"]))

    def test_lock_pertama_kali_tidak_menghasilkan_selesai(self):
        d = self.buat()
        h = d.siklus()["akbar"]
        self.assertEqual([], teks(h))

    def test_mulai_bekerja_per_pasangan_profil_dan_sid(self):
        d = self.buat()
        d.tambah(tim("2026-10-16T14:00:00", "alfa", "patch", sid="KANARI-S"), tim("2026-10-16T14:00:01", "beta", "patch", sid="KANARI-S"),
                 tim("2026-10-16T14:00:02", "alfa", "patch", sid="KANARI-S"), tim("2026-10-16T14:00:03", "alfa", "patch", sid="KANARI-T"),
                 tim("2026-10-16T14:00:04", "alfa", "patch", sid=None), tim("2026-10-16T14:00:05", "alfa", "patch", sid=None))
        self.assertEqual(["Alfa mulai bekerja", "Beta mulai bekerja", "Alfa mulai bekerja", "Alfa mulai bekerja"],
                         teks(d.siklus()["akbar"]))

    def test_pemilik_peristiwa_agen_mode_live(self):
        d = self.buat()
        d.lock("jdih-v3", "alfa", brief=d.brief("b.md", "# Brief TL — jdih-v3 — A", "Peminta: Mas Dicky"))
        d.tambah(tim("2026-10-16T14:00:00", "alfa", "patch", sid="KANARI-A"))
        h1 = d.siklus("2026-10-16T15:00:00+07:00")  # siklus pertama = backfill
        self.assertEqual(["Alfa mulai JDIH"], teks(h1["dicky"]))
        self.assertIn("Alfa mulai bekerja", teks(h1["akbar"]))
        d.tambah(tim("2026-10-16T15:00:01", "alfa", "patch", sid="KANARI-B"),  # live, satu tugas ber-project → akhiran
                 tim("2026-10-16T15:00:02", "alfa", "mcp__obsidian_bsk__catat_progres", sid="KANARI-B"),
                 tim("2026-10-16T15:00:02", "alfa", "mcp__obsidian_bsk__setor", sid="KANARI-B"))
        h2 = d.siklus("2026-10-16T15:00:03+07:00")
        self.assertEqual(["Alfa mulai JDIH", "Alfa mulai bekerja · JDIH", "Alfa mencatat kemajuan · JDIH",
                          "Alfa menyetor dokumen ke bank dokumen"], teks(h2["dicky"]))
        d.lock("absensimeeting", "alfa", brief=d.brief("c.md", "# Brief TL — absensimeeting — A", "Peminta: Mas Jati"))
        d.tambah(tim("2026-10-16T15:00:04", "alfa", "patch", sid="KANARI-C"))  # dua tugas, pemilik campur → akbar, tanpa akhiran
        h3 = d.siklus("2026-10-16T15:00:06+07:00")
        self.assertEqual("Alfa mulai bekerja", teks(h3["akbar"])[-1])
        self.assertEqual(teks(h2["dicky"]), teks(h3["dicky"]))
        self.assertEqual(["Alfa mulai Absensi Meeting"], teks(h3["jati"]))

    def test_pemilik_agen_dengan_dua_tugas_pemilik_sama_tanpa_akhiran(self):
        d = self.buat()
        d.lock("jdih-v3", "alfa", brief=d.brief("b.md", "# Brief TL — jdih-v3 — A", "Peminta: Mas Dicky"))
        d.lock("policytrack", "alfa", brief=d.brief("c.md", "# Brief TL — policytrack — A", "Peminta: Mas Dicky"))
        d.siklus("2026-10-16T15:00:00+07:00")
        d.tambah(tim("2026-10-16T15:00:01", "alfa", "patch", sid="KANARI-B"))
        h = d.siklus("2026-10-16T15:00:03+07:00")
        self.assertEqual("Alfa mulai bekerja", teks(h["dicky"])[-1])

    def test_pemilik_agen_tanpa_tugas_atau_tugas_tanpa_project_atau_pemberi_null_adalah_akbar(self):
        d = self.buat()
        d.lock("jdih-v3", "beta")  # tanpa brief → pemberi null → akbar
        d.siklus("2026-10-16T15:00:00+07:00")
        d.tambah(tim("2026-10-16T15:00:01", "alfa", "patch", sid="KANARI-A"),  # tanpa tugas
                 tim("2026-10-16T15:00:01", "beta", "patch", sid="KANARI-B"))
        h = d.siklus("2026-10-16T15:00:03+07:00")
        self.assertEqual(["Alfa mulai bekerja", "Beta mulai bekerja · JDIH"], teks(h["akbar"])[-2:])
        self.assertEqual(([], []), (teks(h["dicky"]), teks(h["jati"])))

    def test_desy_memanggil_tl(self):
        d = self.buat()
        d.lock("jdih-v3", "carli", brief=d.brief("b.md", "# Brief TL — jdih-v3 — A", "Peminta: Mas Dicky"))
        d.desy(2001, "desy", "# Brief untuk Desy (CTO) — S\nPeminta: Mas Jati\nKANARI")
        d.brief("s.md", "# Brief untuk Desy (CTO) — S", "Peminta: Mas Jati")
        d.desy(2002, "desy", "tak cocok")
        d.tambah(tim("2026-10-16T14:00:00", "desy", "terminal", "hermes -p carli -z KANARI", sid="KANARI-A"))
        h1 = d.siklus("2026-10-16T15:00:00+07:00")  # backfill → akbar
        self.assertEqual(["Desy mulai bekerja", "Desy memanggil Carli"], [x for x in teks(h1["akbar"]) if x.startswith("Desy")])
        self.assertEqual([x for x in teks(h1["dicky"]) if x.startswith("Desy")], [])
        d.tambah(tim("2026-10-16T15:00:01", "desy", "terminal", "hermes -p carli -z KANARI", sid="KANARI-A"))
        h2 = d.siklus("2026-10-16T15:00:03+07:00")
        # tugas Desy: pemilik campur (Jati, akbar) dan Carli memegang tepat 1 lock (pemilik Dicky) → Dicky
        self.assertEqual("Desy memanggil Carli", teks(h2["dicky"])[-1])
        self.assertEqual("Desy memanggil Carli", teks(h2["akbar"])[-1])
        self.assertNotIn("Desy memanggil Carli", teks(h2["jati"]))

    def test_hanya_desy_yang_dicatat_memanggil_tl(self):
        d = self.buat()
        d.tambah(tim("2026-10-16T14:00:00", "alfa", "terminal", "hermes -p beta -z KANARI", sid="KANARI-A"),
                 tim("2026-10-16T14:00:01", "via", "terminal", "hermes -p carli -z KANARI", sid="KANARI-B"),
                 tim("2026-10-16T14:00:02", "carli", "execute_code", "hermes -p desy -z KANARI", sid="KANARI-C"))
        self.assertEqual(["Alfa mulai bekerja", "Via mulai bekerja", "Carli mulai bekerja"], teks(d.siklus()["akbar"]))

    def test_desy_memanggil_tl_pemilik_tugas_desy_tunggal(self):
        d = self.buat()
        d.lock("jdih-v3", "carli", brief=d.brief("b.md", "# Brief TL — jdih-v3 — A", "Peminta: Mas Dicky"))
        d.lock("policytrack", "carli")
        d.brief("s.md", "# Brief untuk Desy (CTO) — S", "Peminta: Mas Jati")
        d.desy(2001, "desy", "# Brief untuk Desy (CTO) — S\nPeminta: Mas Jati\nKANARI")
        d.siklus("2026-10-16T15:00:00+07:00")
        d.tambah(tim("2026-10-16T15:00:01", "desy", "terminal", "hermes -p carli -z KANARI", sid="KANARI-A"))
        h = d.siklus("2026-10-16T15:00:03+07:00")
        self.assertEqual("Desy memanggil Carli", teks(h["jati"])[-1])  # pemilik tugas Desy tunggal = Jati
        self.assertNotIn("Desy memanggil Carli", teks(h["dicky"]))

    def test_desy_memanggil_tl_dengan_dua_lock_menjadi_akbar(self):
        d = self.buat()
        d.lock("jdih-v3", "carli", brief=d.brief("b.md", "# Brief TL — jdih-v3 — A", "Peminta: Mas Dicky"))
        d.lock("policytrack", "carli", brief=d.brief("c.md", "# Brief TL — policytrack — A", "Peminta: Mas Dicky"))
        d.brief("s.md", "# Brief untuk Desy (CTO) — S", "Peminta: Mas Jati")
        d.desy(2001, "desy", "# Brief untuk Desy (CTO) — S\nPeminta: Mas Jati\nKANARI")  # pemilik Jati
        d.desy(2002, "desy", "tak cocok")  # pemilik akbar → pemilik tugas Desy tidak tunggal
        d.siklus("2026-10-16T15:00:00+07:00")
        d.tambah(tim("2026-10-16T15:00:01", "desy", "terminal", "hermes -p carli -z KANARI", sid="KANARI-A"))
        h = d.siklus("2026-10-16T15:00:03+07:00")
        self.assertEqual("Desy memanggil Carli", teks(h["akbar"])[-1])  # Carli memegang 2 lock → akbar
        self.assertEqual(["Carli mulai JDIH", "Carli mulai PolicyTrack"], sorted(teks(h["dicky"])))
        self.assertEqual([], teks(h["jati"]))


class UjiStatus(Dasar):
    def status_ajeng(self, baris, proses=(), skr=SKR):
        d = self.buat()
        d.tambah(*baris)
        for i, profil in enumerate(proses):
            d.desy(3000 + i, profil)
        return agen(d.siklus(skr)["akbar"], "ajeng")["status"]

    def test_status_ajeng(self):
        kasus = [
            ("clarify 29:59 → menunggu", [ajeng_tool("2026-10-16T14:30:01", "Pak Akbar", "clarify")], (), "menunggu"),
            ("clarify 30:00 → bukan menunggu", [ajeng_tool("2026-10-16T14:30:00", "Pak Akbar", "clarify")], (), "bebas"),
            ("clarify 45 mnt → bebas", [ajeng_tool("2026-10-16T14:15:00", "Pak Akbar", "clarify")], (), "bebas"),
            ("clarify 1 mnt → menunggu (bukan jalan)", [ajeng_tool("2026-10-16T14:59:00", "Mas Dicky", "clarify")], (), "menunggu"),
            ("pesan 1:59 → jalan", [ajeng_msg("2026-10-16T14:58:01")], (), "jalan"),
            ("pesan 2:00 → bebas", [ajeng_msg("2026-10-16T14:58:00")], (), "bebas"),
            ("tool biasa 30 dtk → jalan", [ajeng_tool("2026-10-16T14:59:30", "Pak Akbar", "read_file")], (), "jalan"),
            ("clarify lalu pesan → jalan", [ajeng_tool("2026-10-16T14:40:00", "Pak Akbar", "clarify"), ajeng_msg("2026-10-16T14:59:50")], (), "jalan"),
            ("pesan lalu clarify tua (urutan berkas) → bebas",
             [ajeng_msg("2026-10-16T14:59:50"), ajeng_tool("2026-10-16T14:20:00", "Pak Akbar", "clarify")], (), "bebas"),
            ("umur negatif (pesan) → jalan", [ajeng_msg("2026-10-16T15:05:00")], (), "jalan"),
            ("umur negatif (clarify) → menunggu", [ajeng_tool("2026-10-16T15:05:00", "Pak Akbar", "clarify")], (), "menunggu"),
            ("tanpa baris, tanpa proses → bebas", [], (), "bebas"),
            ("proses desy → jalan", [], ("desy",), "jalan"),
            ("proses via → jalan", [], ("via",), "jalan"),
            ("proses TL saja → bebas", [], ("alfa", "beta", "carli"), "bebas"),
            ("clarify 31 mnt + proses desy → jalan", [ajeng_tool("2026-10-16T14:29:00", "Pak Akbar", "clarify")], ("desy",), "jalan"),
            ("clarify 5 mnt + proses desy → menunggu", [ajeng_tool("2026-10-16T14:55:00", "Pak Akbar", "clarify")], ("desy",), "menunggu"),
            ("baris tim terbaru tidak membuat Ajeng jalan", [tim("2026-10-16T14:59:59", "alfa", "patch")], (), "bebas"),
        ]
        for nama, baris, proses, harapan in kasus:
            with self.subTest(nama):
                self.assertEqual(harapan, self.status_ajeng(baris, proses))

    def test_status_tugas_ajeng_menunggu_hanya_untuk_pemilik_baris_terakhir(self):
        d = self.buat()
        d.tambah(ajeng_msg("2026-10-16T14:51:00", "Pak Akbar"), ajeng_tool("2026-10-16T14:58:00", "Mas Dicky", "clarify"))
        h = d.siklus()["akbar"]
        self.assertEqual(("jalan", "menunggu"), (tugas(h, "ajeng-akbar")["status"], tugas(h, "ajeng-dicky")["status"]))
        self.assertEqual(["ajeng-dicky", "ajeng-akbar"], [t["id"] for t in h["tugas_aktif"]])

    def test_status_tl_dan_desy_via(self):
        d = self.buat()
        d.lock("jdih-v3", "alfa")
        d.lock("policytrack", "beta")
        d.proses(100, ["hermes", "-p", "alfa"])
        d.proses(101, ["hermes", "-p", "carli"])  # carli jalan tanpa lock
        d.proses(102, ["/opt/hermes/.venv/bin/hermes", "-p", "via"])
        h = d.siklus()["akbar"]
        self.assertEqual({"ajeng": "jalan", "desy": "bebas", "via": "jalan", "alfa": "jalan", "beta": "menunggu", "carli": "jalan"},
                         {a["id"]: a["status"] for a in h["agen"]})
        self.assertEqual({"lock-jdih-v3": "jalan", "lock-policytrack": "menunggu", "proses-102": "jalan"},
                         {t["id"]: t["status"] for t in h["tugas_aktif"]})

    def test_deteksi_proses_hermes(self):
        kasus = [
            (["hermes", "-p", "alfa"], True),
            (["/opt/hermes/.venv/bin/hermes", "-p", "alfa"], True),
            (["/usr/bin/python3", "/opt/hermes/.venv/bin/hermes", "-p", "alfa"], True),
            (["/opt/hermes/.venv/bin/python", "-m", "hermes_cli.main", "-p", "alfa"], True),
            (HERMES + ["-p", "alfa"], True),
            (["hermes", "chat", "-p", "alfa", "-z", "x"], True),
            (["hermes", "-p", "beta", "-p", "alfa"], True),  # semua nilai -p
            (["a", "b", "c", "d", "hermes", "-p", "alfa"], False),  # hermes di argv ke-5
            (["bash", "-c", "hermes -p alfa -z KANARI"], False),
            (["hermes-agent", "-p", "alfa"], False),
            (["ssh", "-p", "22", "alfa"], False),
            (["python3", "x.py", "-p", "alfa"], False),
            (["hermes", "-p"], False),  # -p di akhir tanpa nilai
            (["hermes", "-P", "alfa"], False),
            (["hermes", "--profile", "alfa"], False),
        ]
        for argv, jalan in kasus:
            with self.subTest(argv=argv):
                d = self.buat()
                d.lock("jdih-v3", "alfa")
                d.proses(100, argv, comm="we(i)rd )")
                self.assertEqual("jalan" if jalan else "menunggu", agen(d.siklus()["akbar"], "alfa")["status"])

    def test_pid_hilang_atau_tak_terbaca_diabaikan_tanpa_galat(self):
        d = self.buat()
        d.lock("jdih-v3", "alfa")
        d.proses(100, ["hermes", "-p", "alfa"])
        (d.proc / "200").mkdir()  # tanpa cmdline (proses hilang di tengah siklus)
        (d.proc / "300").mkdir()
        (d.proc / "300" / "cmdline").mkdir()  # tak terbaca
        (d.proc / "400").mkdir()
        (d.proc / "400" / "cmdline").write_bytes(b"")  # kosong (thread kernel)
        (d.proc / "self").mkdir()
        (d.proc / "500").write_text("bukan direktori")
        h = d.siklus()["akbar"]
        self.assertEqual(([], "jalan"), (h["galat"], agen(h, "alfa")["status"]))

    def test_mulai_proses_dibulatkan_ke_bawah(self):
        d = self.buat()
        d.proses(2001, HERMES + ["-p", "desy", "-z", "x"], "2026-10-16T14:00:00+07:00", tick_ekstra=99)
        t = tugas(d.siklus()["akbar"], "proses-2001")
        self.assertEqual("2026-10-16T14:00:00+07:00", t["mulai"])
        self.assertEqual(("Desy", "desy", "jalan", None, None), (t["pengerja"], t["pengerja_id"], t["status"], t["project"], t["project_nama"]))

    def test_btime_tidak_terbaca_tidak_menjadi_galat(self):
        d = self.buat()
        d.proses(2001, HERMES + ["-p", "desy", "-z", "x"])
        (d.proc / "stat").unlink()
        h = d.siklus()["akbar"]
        self.assertEqual([], h["galat"])
        self.assertEqual("jalan", agen(h, "desy")["status"])
        self.assertIsNone(tugas(h, "proses-2001")["mulai"])

    def test_dua_proses_desy_dua_tugas_dan_langkah_dari_baris_desy_terakhir(self):
        d = self.buat()
        d.desy(2001, "desy", "a")
        d.desy(2002, "desy", "b")
        d.tambah(tim("2026-10-16T14:59:00", "desy", "read_file"), tim("2026-10-16T14:59:30", "desy", "web_search"))
        h = d.siklus()["akbar"]
        self.assertEqual(["proses-2001", "proses-2002"], [t["id"] for t in h["tugas_aktif"]])
        for t in h["tugas_aktif"]:
            self.assertEqual(("mencari di web", "2026-10-16T14:59:30+07:00"), (t["langkah_terakhir"], t["langkah_waktu"]))

    def test_isolasi_agen_terlihat_dan_sibuk(self):
        d = self.buat()
        d.lock("jdih-v3", "alfa", brief=d.brief("b.md", "# Brief TL — jdih-v3 — A", "Peminta: Mas Dicky"))
        d.lock("policytrack", "alfa", brief=d.brief("c.md", "# Brief TL — policytrack — A", "Peminta: Mas Jati"))
        d.lock("ebook-v2", "beta")
        d.tambah(tim("2026-10-16T14:59:00", "alfa", "patch"), tim("2026-10-16T14:59:10", "beta", "patch"))
        hasil = d.siklus()
        h = hasil["dicky"]
        self.assertEqual(["lock-jdih-v3"], [t["id"] for t in h["tugas_aktif"]])
        t = h["tugas_aktif"][0]  # Alfa memegang tugas milik orang lain juga → langkah & terakhir_aktif disembunyikan
        self.assertEqual((None, None), (t["langkah_terakhir"], t["langkah_waktu"]))
        self.assertEqual(("menunggu", None), (agen(h, "alfa")["status"], agen(h, "alfa")["terakhir_aktif"]))
        self.assertEqual(("sibuk", None), (agen(h, "beta")["status"], agen(h, "beta")["terakhir_aktif"]))
        self.assertEqual(("bebas", None), (agen(h, "carli")["status"], agen(h, "carli")["terakhir_aktif"]))
        self.assertEqual(("bebas", None), (agen(h, "ajeng")["status"], agen(h, "ajeng")["terakhir_aktif"]))
        self.assertEqual("2026-10-16T14:59:00+07:00", agen(hasil["akbar"], "alfa")["terakhir_aktif"])
        self.assertEqual(3, len(hasil["akbar"]["tugas_aktif"]))


class UjiTulis(Dasar):
    def test_mode_berkas_dan_direktori_tetap_walau_umask(self):
        for umask in (0, 0o077, 0o002, 0o027):
            with self.subTest(umask=oct(umask)):
                d = self.buat()
                d.tambah(ajeng_msg("2026-10-16T14:59:00"))
                lama = os.umask(umask)
                try:
                    d.siklus()
                    self.assertEqual(0o750, stat.S_IMODE(os.stat(d.keluaran).st_mode))
                    for p in PENONTON:
                        self.assertEqual(0o640, stat.S_IMODE(os.stat(d.keluaran / f"{p}.json").st_mode))
                    d.siklus("2026-10-16T15:00:03+07:00")
                finally:
                    os.umask(lama)
                self.assertEqual(sorted(f"{p}.json" for p in PENONTON), sorted(os.listdir(d.keluaran)))
                self.assertEqual(0o750, stat.S_IMODE(os.stat(d.keluaran).st_mode))
                for p in PENONTON:
                    self.assertEqual(0o640, stat.S_IMODE(os.stat(d.keluaran / f"{p}.json").st_mode))

    def test_direktori_longgar_dan_tmp_basi_dibereskan(self):
        d = self.buat()
        d.keluaran.mkdir()
        os.chmod(d.keluaran, 0o777)
        for p in PENONTON:
            sisa = d.keluaran / f"{p}.json.tmp"
            sisa.write_text("sisa lama")
            os.chmod(sisa, 0o666)
        (d.keluaran / "akbar.json").write_text("lama")
        os.chmod(d.keluaran / "akbar.json", 0o666)
        d.siklus()
        self.assertEqual(0o750, stat.S_IMODE(os.stat(d.keluaran).st_mode))
        self.assertEqual(sorted(f"{p}.json" for p in PENONTON), sorted(os.listdir(d.keluaran)))
        for p in PENONTON:
            self.assertEqual(0o640, stat.S_IMODE(os.stat(d.keluaran / f"{p}.json").st_mode))
            self.assertEqual("1", json.loads((d.keluaran / f"{p}.json").read_text())["versi_skema"])

    def test_direktori_keluaran_bertingkat_dibuat(self):
        d = self.buat()
        d.keluaran = d.akar / "a" / "b" / "ringkasan"
        d.g = generator.Generator(activity=d.activity, workspace=d.workspace, proc=d.proc, proyek=d.proyek, keluaran=d.keluaran,
                                  tim=d.tim, profil=d.profil)
        d.siklus()
        self.assertEqual(sorted(f"{p}.json" for p in PENONTON), sorted(os.listdir(d.keluaran)))
        self.assertEqual(0o750, stat.S_IMODE(os.stat(d.keluaran).st_mode))

    def test_pengecualian_di_tengah_siklus_tidak_menulis_berkas(self):
        d = self.buat()
        asli = json.dumps
        n = [0]

        def dumps_gagal(*a, **k):
            n[0] += 1
            if n[0] == 2:
                raise ValueError("KANARI-pesan /data/KANARI-rahasia")
            return asli(*a, **k)

        with mock.patch.object(generator.json, "dumps", dumps_gagal):
            with self.assertRaises(ValueError):
                d.siklus()
        self.assertEqual([], os.listdir(d.keluaran) if d.keluaran.exists() else [])
        d.siklus("2026-10-16T15:00:03+07:00")
        self.assertEqual(sorted(f"{p}.json" for p in PENONTON), sorted(os.listdir(d.keluaran)))


class UjiLoopDanLapor(Dasar):
    def jam_palsu(self):
        t = [0.0]
        return (lambda: t[0]), (lambda s: t.__setitem__(0, t[0] + s)), t

    def test_pengecualian_siklus_hanya_nama_kelas_dan_loop_lanjut(self):
        d = self.buat()
        d.tambah(ajeng_msg("2026-10-16T14:59:00"))
        asli = json.dumps
        n = [0]

        def dumps_gagal(*a, **k):
            n[0] += 1
            if n[0] == 1:
                raise ValueError("KANARI-pesan /data/KANARI-rahasia")
            return asli(*a, **k)

        siklus = [0]
        orig = d.g.siklus
        sesudah_pertama = {}

        def hitung(sekarang):
            siklus[0] += 1
            if siklus[0] == 2:
                sesudah_pertama["isi"] = os.listdir(d.keluaran) if d.keluaran.exists() else []
            orig(sekarang)

        d.g.siklus = hitung
        jam, tidur, _ = self.jam_palsu()
        buf = io.StringIO()
        with mock.patch.object(generator.json, "dumps", dumps_gagal), contextlib.redirect_stdout(buf), \
                contextlib.redirect_stderr(buf):
            generator.loop(d.g, 3.0, lambda: siklus[0] >= 3, jam=jam, tidur=tidur)
        d.stdout += buf.getvalue()
        self.assertEqual([], sesudah_pertama["isi"])  # siklus yang gagal tidak menulis apa pun
        self.assertEqual(sorted(f"{p}.json" for p in PENONTON), sorted(os.listdir(d.keluaran)))
        self.assertIn("ValueError", buf.getvalue())
        self.assertNotIn("pesan", buf.getvalue())
        self.assertNotIn("/data", buf.getvalue())
        self.assertNotIn("Traceback", buf.getvalue())

    def test_ringkasan_tiap_60_detik(self):
        d = self.buat()
        d.tambah('rusak {', ajeng_msg("2026-10-16T14:59:00"), '[1]')
        jam, tidur, t = self.jam_palsu()
        siklus = [0]
        orig = d.g.siklus

        def hitung(sekarang):
            siklus[0] += 1
            orig(sekarang)

        d.g.siklus = hitung
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf):
            generator.loop(d.g, 3.0, lambda: t[0] >= 130, jam=jam, tidur=tidur)
        d.stdout += buf.getvalue()
        ringkas = [b for b in buf.getvalue().splitlines() if b.startswith("ringkasan")]
        self.assertEqual(2, len(ringkas), buf.getvalue())
        m = re.fullmatch(r"ringkasan siklus=(\d+) baris_baru=(\d+) dilewati=(\d+) rata_ms=([\d.]+) galat=(\d+)", ringkas[0])
        self.assertIsNotNone(m, ringkas[0])
        self.assertGreaterEqual(int(m.group(1)), 20)
        self.assertEqual((3, 2), (int(m.group(2)), int(m.group(3))))
        m2 = re.fullmatch(r"ringkasan siklus=(\d+) baris_baru=(\d+) dilewati=(\d+) rata_ms=([\d.]+) galat=(\d+)", ringkas[1])
        self.assertEqual((0, 0), (int(m2.group(2)), int(m2.group(3))))

    def test_siklus_berikutnya_tidur_sisa_interval(self):
        d = self.buat()
        jam, tidur, t = self.jam_palsu()
        lama = []
        siklus = [0]
        orig = d.g.siklus

        def hitung(sekarang):
            siklus[0] += 1
            lama.append(t[0])
            t[0] += 1.0  # siklus memakan 1 dtk
            orig(sekarang)

        d.g.siklus = hitung
        with contextlib.redirect_stdout(io.StringIO()):
            generator.loop(d.g, 3.0, lambda: siklus[0] >= 4, jam=jam, tidur=tidur)
        self.assertEqual([0.0, 3.0, 6.0, 9.0], lama)


class UjiCLI(Dasar):
    def argumen(self, d, *tambahan):
        return ["--activity", str(d.activity), "--workspace", str(d.workspace), "--proc", str(d.proc),
                "--proyek", str(d.proyek), "--keluaran", str(d.keluaran), "--tim", str(d.tim), "--profil", str(d.profil),
                *tambahan]

    def test_bawaan_parser(self):
        a = generator.buat_parser().parse_args([])
        akar = Path(generator.__file__).resolve().parent.parent
        self.assertEqual(3.0, a.interval)
        self.assertIsInstance(a.interval, float)
        self.assertEqual((None, None, None, None, None), (a.tim, a.activity, a.workspace, a.proc, a.profil))  # bawaan = tim.json
        self.assertEqual(str(akar / "conf" / "proyek.json"), str(a.proyek))
        self.assertEqual(str(akar / "storage" / "ringkasan"), str(a.keluaran))
        self.assertFalse(a.sekali)
        self.assertIsNone(a.sekarang)

    def test_sekarang_tanpa_sekali_ditolak(self):
        d = self.buat()
        buf = io.StringIO()
        with contextlib.redirect_stderr(buf), contextlib.redirect_stdout(buf):
            rc = generator.main(self.argumen(d, "--sekarang", SKR))
        self.assertNotEqual(0, rc)
        self.assertFalse(d.keluaran.exists())
        hasil = subprocess.run([sys.executable, str(ROOT / "script" / "generator.py"), *self.argumen(d, "--sekarang", SKR)],
                               capture_output=True, text=True, timeout=30)
        self.assertNotEqual(0, hasil.returncode)
        self.assertFalse(d.keluaran.exists())

    def test_argumen_buruk_ditolak(self):
        d = self.buat()
        for tambahan in (["--sekali", "--sekarang", "kemarin"], ["--interval", "0"], ["--interval", "-1"],
                         ["--interval", "abc"], ["--tak-dikenal"]):
            with self.subTest(tambahan=tambahan):
                with contextlib.redirect_stderr(io.StringIO()), contextlib.redirect_stdout(io.StringIO()):
                    rc = generator.main(self.argumen(d, *tambahan))
                self.assertNotEqual(0, rc)
        self.assertFalse(d.keluaran.exists())

    def test_sekali_dengan_sekarang_dan_log_mulai(self):
        d = self.buat()
        d.tambah(ajeng_msg("2026-10-16T14:59:00"))
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = generator.main(self.argumen(d, "--sekali", "--sekarang", "2026-10-16T14:59:57+07:00", "--interval", "7"))
        d.stdout += buf.getvalue()
        self.assertEqual(0, rc)
        self.assertEqual("2026-10-16T14:59:57+07:00", d.baca()["jati"]["dibuat_pada"])
        self.assertIn(str(d.keluaran), buf.getvalue())
        self.assertIn("7.0", buf.getvalue())

    def test_sekarang_tanpa_zona_dibaca_wib(self):
        d = self.buat()
        with contextlib.redirect_stdout(io.StringIO()):
            rc = generator.main(self.argumen(d, "--sekali", "--sekarang", "2026-10-16T14:59:57"))
        self.assertEqual(0, rc)
        self.assertEqual("2026-10-16T14:59:57+07:00", d.baca()["akbar"]["dibuat_pada"])

    def test_sekali_tanpa_sekarang_memakai_jam_sekarang_wib(self):
        d = self.buat()
        hasil = subprocess.run([sys.executable, str(ROOT / "script" / "generator.py"), *self.argumen(d, "--sekali")],
                               capture_output=True, text=True, timeout=60)
        self.assertEqual(0, hasil.returncode, hasil.stderr[-300:])
        dp = datetime.fromisoformat(d.baca()["akbar"]["dibuat_pada"])
        self.assertTrue(d.baca()["akbar"]["dibuat_pada"].endswith("+07:00"))
        self.assertLess(abs((datetime.now(WIB) - dp).total_seconds()), 60)

    def test_sekali_dengan_pengecualian_kode_keluar_bukan_nol_tanpa_pesan(self):
        d = self.buat()
        buf = io.StringIO()
        with mock.patch.object(generator.json, "dumps", side_effect=ValueError("KANARI-pesan /data/x")), \
                contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            rc = generator.main(self.argumen(d, "--sekali", "--sekarang", SKR))
        self.assertNotEqual(0, rc)
        self.assertIn("ValueError", buf.getvalue())
        self.assertNotIn("KANARI", buf.getvalue())
        self.assertNotIn("/data/x", buf.getvalue())

    def test_fifo_tidak_memblokir_generator(self):
        d = self.buat()
        os.mkfifo(d.locks / "pipa.lock")
        os.mkfifo(d.brief_dir / "pipa.md")
        d.lock("jdih-v3", "alfa", brief="/workspace/brief/pipa.md")
        d.desy(2001, "desy", "# Brief untuk Desy (CTO) — X")
        os.remove(d.activity)
        os.mkfifo(d.activity)
        hasil = subprocess.run([sys.executable, str(ROOT / "script" / "generator.py"), *self.argumen(d, "--sekali", "--sekarang", SKR)],
                               capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual(0, hasil.returncode, hasil.stderr[-300:])
        h = d.baca()["akbar"]
        self.assertEqual([GALAT_LOG], h["galat"])
        self.assertEqual(["lock-jdih-v3", "proses-2001"], sorted(t["id"] for t in h["tugas_aktif"]))
        self.assertEqual("Pekerjaan JDIH", tugas(h, "lock-jdih-v3")["judul"])
        self.assertIsNone(tugas(h, "proses-2001")["judul"])

    def jalankan_loop(self, d, interval, sinyal):
        cmd = [sys.executable, str(ROOT / "script" / "generator.py"), *self.argumen(d, "--interval", str(interval))]
        with subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True) as p:
            try:
                batas = time.time() + 15
                while not (d.keluaran / "jati.json").exists() and time.time() < batas and p.poll() is None:
                    time.sleep(0.05)
                self.assertTrue((d.keluaran / "jati.json").exists(), "berkas keluaran tidak muncul")
                pertama = d.baca()["akbar"]["dibuat_pada"]
                if interval < 3:
                    batas = time.time() + 10
                    while d.baca()["akbar"]["dibuat_pada"] == pertama and time.time() < batas:
                        time.sleep(0.1)
                    self.assertNotEqual(pertama, d.baca()["akbar"]["dibuat_pada"], "loop tidak menulis ulang")
                t0 = time.time()
                p.send_signal(sinyal)
                rc = p.wait(timeout=interval + 10)
                lama = time.time() - t0
            except BaseException:
                p.kill()
                raise
            keluar, galat = p.communicate()
        return rc, lama, keluar, galat

    def test_sigterm_mode_loop_keluar_0_dalam_interval_plus_2(self):
        d = self.buat()
        d.tambah(ajeng_msg("2026-10-16T14:59:00"))
        rc, lama, keluar, galat = self.jalankan_loop(d, 3, signal.SIGTERM)
        self.assertEqual(0, rc, galat[-500:])
        self.assertLessEqual(lama, 3 + 2)
        self.assertEqual(0, (keluar + galat).count("KANARI"))
        self.assertIn(str(d.keluaran), keluar)
        self.assertNotIn("Traceback", galat)
        self.assertEqual(sorted(f"{p}.json" for p in PENONTON), sorted(os.listdir(d.keluaran)))

    def test_sigterm_langsung_dihentikan_walau_interval_panjang(self):
        d = self.buat()
        rc, lama, keluar, galat = self.jalankan_loop(d, 30, signal.SIGTERM)
        self.assertEqual(0, rc, galat[-500:])
        self.assertLess(lama, 3)

    def test_sigint_mode_loop_menulis_ulang_lalu_keluar_0(self):
        d = self.buat()
        rc, lama, keluar, galat = self.jalankan_loop(d, 1, signal.SIGINT)
        self.assertEqual(0, rc, galat[-500:])
        self.assertLessEqual(lama, 1 + 2)
        self.assertNotIn("Traceback", galat)


if __name__ == "__main__":
    unittest.main()
