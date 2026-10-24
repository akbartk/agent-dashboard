#!/usr/bin/env python3
"""Generator ringkasan agent-dashboard (skema "1"). Kontrak: docs/skema-ringkasan.md. Python 3.14, stdlib saja.

Membaca log aktivitas, lock, brief, dan /proc (hanya baca), lalu menulis <keluaran>/<penonton>.json tiap siklus.
Tidak pernah menulis isi text/detail/argv/sid/brief (di luar judul & baris Peminta)/lock (di luar field dipakai).
Misi "Kantor Agen" (sejak 24 Okt 2026): docs/misi.md; registri nomor `--nomor`, state.db profil (4 kolom, mode=ro).
"""
import argparse
import hashlib
import json
import os
import re
import signal
import sqlite3
import stat
import sys
import time
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import quote

WIB = timezone(timedelta(hours=7))
GALAT_LOG = "Log aktivitas tidak terbaca"
GALAT_PROSES = "Daftar proses tidak terbaca"
GALAT_LOCK = "Lock tidak terbaca"
GALAT_PETA = "Peta project tidak terbaca"
GALAT_AGEN = "Config agen tidak terbaca"  # teks tetap (antarmuka JSON ringkasan tidak berubah); sumbernya kini conf/tim.json
GALAT_PROFIL = "Folder profil tidak terbaca"
GALAT_NOMOR = "Nomor misi tidak terbaca"
GALAT_SESI = "Data sesi tidak terbaca"
RUANG = ("koordinasi", "riset", "qa", "teknik")


class ConfigTimTidakSah(Exception):
    """conf/tim.json belum pernah terbaca sah: tanpa daftar penonton tidak ada berkas yang bisa ditulis."""


def _teks(x):
    return isinstance(x, str) and x != ""


def _opsi(x):
    return x is None or _teks(x)


def validasi_tim(d):
    """KONTRAK §2 (skema versi 1) → config ternormalisasi; tidak sah apa pun → ValueError. Kunci berawalan `_` diabaikan;
    `aktivitas` dibaca hook saja, tidak dibaca di sini."""
    try:
        return _validasi_tim(d)
    except (re.error, TypeError, KeyError, AttributeError, RecursionError) as e:
        raise ValueError("tim.json tidak sah") from e


def _validasi_tim(d):
    if not (isinstance(d, dict) and type(d.get("versi")) is int and d["versi"] == 1):
        raise ValueError
    orang, ids = [], []
    if not (isinstance(d["orang"], list) and d["orang"]):
        raise ValueError
    for o in d["orang"]:
        if not (isinstance(o, dict) and _teks(o["id"]) and RE_ID.fullmatch(o["id"]) and _teks(o["nama"])
                and isinstance(o["peran"], str) and isinstance(o["induk"], list) and all(_teks(x) for x in o["induk"])):
            raise ValueError
        ids.append(o["id"])
        orang.append({"id": o["id"], "nama": o["nama"], "peran": o["peran"], "induk": list(o["induk"])})
    if len(set(ids)) != len(ids) or len({o["nama"] for o in orang}) != len(orang):
        raise ValueError
    pen = d["penonton"]
    if not (isinstance(pen, list) and pen and all(isinstance(x, str) and x in ids for x in pen) and len(set(pen)) == len(pen)):
        raise ValueError
    if not (isinstance(d["pemilik"], str) and d["pemilik"] in pen):
        raise ValueError
    for k in ("koordinator", "cto"):
        if not (isinstance(d[k], str) and RE_ID.fullmatch(d[k])):
            raise ValueError
    if not isinstance(d["agen"], dict):
        raise ValueError
    agen = {}
    for i, e in d["agen"].items():
        if not (RE_ID.fullmatch(i) and isinstance(e, dict) and isinstance(e.get("nama"), str) and e["nama"]
                and isinstance(e.get("peran"), str) and isinstance(e.get("induk"), list)
                and all(isinstance(x, str) and x for x in e["induk"])
                and ("ruang" not in e or e["ruang"] in RUANG)):  # C1: ruang opsional, nilai lain = berkas ditolak
            raise ValueError
        agen[i] = {"nama": e["nama"], "peran": e["peran"], "induk": list(e["induk"]), "ruang": e.get("ruang", "lain")}
    s = d["sumber"]
    if not (isinstance(s, dict) and all(_teks(s[k]) for k in ("activity", "profil", "workspace", "workspace_kontainer",
                                                                 "brief", "lock", "proc")) and _opsi(s.get("handoff"))):
        raise ValueError
    sumber = {k: s[k] for k in ("activity", "profil", "workspace", "workspace_kontainer", "brief", "lock", "proc")}
    po = d["pola"]
    if not (isinstance(po, dict) and _teks(po["brief_nama"]) and "{pelaksana}" in po["brief_nama"]
            and "(?P<sisa>" in po["brief_nama"] and _teks(po["lock_nama"]) and _teks(po["peminta"])
            and _opsi(po.get("lock_pemisah_subtugas"))):
        raise ValueError
    re.compile(po["brief_nama"].replace("{pelaksana}", "x"))
    pola = {"brief_nama": po["brief_nama"], "lock_nama": re.compile(po["lock_nama"]), "peminta": re.compile(po["peminta"]),
            "pemisah": po.get("lock_pemisah_subtugas")}
    kat = d["kategori_perintah"]
    if not isinstance(kat, list):
        raise ValueError
    sebelum, sesudah = [], []
    for e in kat:
        if not (isinstance(e, dict) and _teks(e["pola"]) and _teks(e["teks"])
                and type(e.get("sesudah_panggil", False)) is bool):
            raise ValueError
        (sesudah if e.get("sesudah_panggil") else sebelum).append((re.compile(e["pola"]), e["teks"]))
    t = d["tool"]
    if not (isinstance(t, dict) and all(_opsi(t.get(k)) for k in ("awalan_bank_dokumen", "catat_progres", "setor"))):
        raise ValueError
    tool = {k: t.get(k) for k in ("awalan_bank_dokumen", "catat_progres", "setor")}
    return {"orang": orang, "penonton": list(pen), "pemilik": d["pemilik"], "koordinator": d["koordinator"], "cto": d["cto"],
            "agen": agen, "sumber": sumber, "pola": pola, "sebelum": sebelum, "sesudah": sesudah,
            "tool": tool}
# B8 + A2: hanya 4 kolom ini yang dibaca dari state.db (source hanya penyaring WHERE, tidak dibaca keluar)
KUERI_SESI = ("SELECT id, parent_session_id, started_at, ended_at FROM sessions "
              "WHERE source = 'subagent' AND parent_session_id IN ({})")
LABEL = {"mulai": "Mulai", "langkah": "Langkah", "selesai": "Selesai", "hambatan": "Hambatan", "berhenti": "Berhenti",
         "antre": "Antre"}
TERMINAL = ("terminal", "execute_code")
TANPA_PENGIRIM = "Pengirim tak dikenal"
KUNCI_TUGAS = ("id", "judul", "project", "project_nama", "pemberi", "pemberi_id", "pengerja", "pengerja_id", "mulai",
               "langkah_terakhir", "langkah_waktu", "status")

# tool bank dokumen / catat progres / setor ditambahkan dari `tool` di config tim (Generator._terapkan)
KATEGORI_TOOL = {
    "read_file": "membaca berkas", "search_files": "membaca berkas", "write_file": "menulis berkas", "patch": "menulis berkas",
    "delegate_task": "membagi tugas ke worker",
    "process_manage": "menunggu proses", "web_search": "mencari di web", "web_extract": "mencari di web",
    "browser_exec": "mencari di web", "skill_view": "membaca skill", "skills_list": "membaca skill",
    "skill_manage": "memperbarui skill", "vision_analyze": "memeriksa gambar", "memory": "mencatat memori",
    "cronjob_manage": "mengatur jadwal"}

RE_TS = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}")
RE_PRIBADI = re.compile(r"\d(?:[ .-]?\d){9,}")
RE_ID = re.compile(r"[a-z0-9][a-z0-9_-]{0,63}")  # id agen = nama folder profil / kunci `agen` di conf/tim.json (D1)
RE_TANGGAL = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
RE_KURUNG = re.compile(r"\((.*)\)")
RE_SISTEM = re.compile(r"^\s*\[IMPORTANT: Background process|\[INTERNAL NOTIFICATION")  # notifikasi gateway yang disisipkan hook ke sesi
RE_STATUS = re.compile(r"Status\W{0,6}([A-Za-z]+)", re.I)  # B7: label langkah dari detail catat_progres (hanya dicocokkan)
RE_KUOTA = re.compile(r"\s+oneshot_max_children:\s*([0-9]+)\s*(?:#.*)?")


def saring(s):
    """§3.7: string tampil yang memuat '@' atau ≥ 10 digit berurutan diganti seluruhnya."""
    return "(disaring)" if "@" in s or RE_PRIBADI.search(s) else s


def program_hermes(argv):
    return any(os.path.basename(a) == "hermes" or "hermes_cli.main" in a for a in argv[:4])


def profil_hermes(argv):
    return [argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "-p"] if program_hermes(argv) else []


def re_panggil(ids):
    """D6: regex panggil `hermes -p <id>` untuk satu golongan; id terpanjang dulu; golongan kosong → tidak pernah cocok."""
    if not ids:
        return re.compile(r"(?!)")
    alt = "|".join(re.escape(i) for i in sorted(ids, key=lambda i: (-len(i), i)))
    return re.compile(r"\bhermes\b.*?\s-p\s+(" + alt + r")\b", re.S)


def deskripsi(teks):
    """D7: nilai `description` profile.yaml (parser minimal stdlib); tidak ada / kutip tak tertutup → ''."""
    baris = teks.split("\n")
    i = next((i for i, b in enumerate(baris) if b.startswith("description:")), None)
    if i is None:
        return ""
    v = baris[i][len("description:"):].strip()
    lanjut = []
    for b in baris[i + 1:]:  # baris lanjutan: berindentasi atau kosong
        if b.strip() and b[:1] not in (" ", "\t"):
            break
        lanjut.append(b)
    sumber = "\n".join([v] + lanjut)
    if v[:1] in ("'", '"'):
        q, hasil, j = v[0], [], 1
        while True:
            if j >= len(sumber):
                return ""  # kutip tak tertutup
            c = sumber[j]
            if q == "'" and c == "'":
                if sumber[j + 1:j + 2] != "'":
                    break
                hasil.append("'")
                j += 2
            elif q == '"' and c == "\\" and sumber[j + 1:j + 2] in ('"', "\\"):
                hasil.append(sumber[j + 1])
                j += 2
            elif q == '"' and c == '"':
                break
            else:
                hasil.append(c)
                j += 1
        sumber = "".join(hasil)
    elif v[:1] in ("|", ">"):
        sumber = "\n".join(lanjut)
    return " ".join(sumber.split())


def kategori(jenis, tool, detail, gol, nama_r=None):
    """Tabel K1 (§3.2) → (kategori, panggil); panggil = ("tl"|"anggota", id) bila memanggil agen, else None.
    `gol` = Generator (regex panggil + nama efektif siklus ini). `detail` hanya dicocokkan, tidak pernah disalin."""
    if jenis == "msg":
        return "membaca pesan", None
    if tool in TERMINAL:
        for pola, teks in gol.kat_sebelum:  # `kategori_perintah` berurutan; yang tanpa `sesudah_panggil` mendahului panggil agen
            if pola.search(detail):
                return teks, None
        m = gol.re_tl.search(detail)
        if m:
            return "memanggil TL " + gol.nama[m.group(1)], ("tl", m.group(1))
        m = gol.re_anggota.search(detail)
        if m:
            return "memanggil " + gol.nama[m.group(1)], ("anggota", m.group(1))
        for pola, teks in gol.kat_sesudah:
            if pola.search(detail):
                return teks, None
        return "menjalankan perintah", None
    if tool == "clarify":
        return (f"meminta keputusan {nama_r}" if nama_r else "meminta keputusan"), None
    if tool.startswith("mnemosyne_"):
        return "mencatat memori", None
    return gol.kat_tool.get(tool, "bekerja"), None


def iso(w):
    return w.isoformat(timespec="seconds")


def parse_waktu(s):
    """ISO 8601 → datetime WIB (tanpa zona dibaca WIB); tidak sah → None."""
    try:
        w = datetime.fromisoformat(s)
        return w.replace(tzinfo=WIB) if w.tzinfo is None else w.astimezone(WIB)
    except (TypeError, ValueError, OverflowError):
        return None


def baca_biasa(path, n):
    """Baca maks n byte dari berkas biasa; None bila bukan berkas biasa (tanpa memblokir pada FIFO)."""
    fd = os.open(path, os.O_RDONLY | os.O_NONBLOCK)
    try:
        return os.read(fd, n) if stat.S_ISREG(os.fstat(fd).st_mode) else None
    finally:
        os.close(fd)


def baca_baris_awal(path, n=10, batas=2000):
    """n baris pertama (tanpa newline), tiap baris dipotong `batas` byte; sisa baris panjang dibuang."""
    baris = []
    with open(path, "rb") as f:
        while len(baris) < n:
            b = f.readline(batas + 1)
            if not b:
                break
            if not b.endswith(b"\n") and len(b) > batas:
                while True:
                    s = f.readline(65536)
                    if not s or s.endswith(b"\n"):
                        break
                b = b[:batas]
            baris.append(b.decode("utf-8", "replace").rstrip("\n"))
    return baris


def header_dari(baris, re_peminta):
    """§3.5: baris 1 s.d. baris Peminta pertama (`pola.peminta`), maks 10 baris; `\\r` di akhir dibuang."""
    h = []
    for b in baris[:10]:
        b = b.rstrip("\r")
        h.append(b)
        if re_peminta.match(b):
            break
    return tuple(h)


def pemberi_dari(h, re_peminta, pemberi):
    """`pemberi` = {nama orang: id}; tepat satu nama di baris Peminta, selain itu None."""
    if not h or not re_peminta.match(h[-1]):
        return None
    ada = [n for n in pemberi if n in h[-1]]
    return ada[0] if len(ada) == 1 else None


def judul_dari(h, slug=None):
    """§3.5 + B4 revisi + J-1: `slug` = str atau himpunan slug project (lock, berkas); bagian == slug atau
    `<slug>(-[a-z0-9]+)+` dibuang utuh, bagian diawali `<slug> `/`<slug>(` kehilangan awalannya, bagian lain tidak dipotong."""
    if not h or not h[0].startswith("# "):
        return None
    slugs = sorted({s for s in ((slug,) if isinstance(slug, str) else (slug or ())) if s}, key=lambda s: (-len(s), s))
    bagian = [b.strip() for b in h[0][2:].split(" — ")]
    for i, b in enumerate(bagian):
        if b.startswith("Brief"):
            bagian[i] = b.partition(":")[2].strip()  # B4 revisi (docs/misi.md): sesudah ":" pertama; tanpa ":" → ""
            break
    hasil = []
    for b in bagian:
        m = RE_TANGGAL.match(b)
        if m:
            b = b[m.end():].strip()
        for s in slugs:
            if b == s or re.fullmatch(re.escape(s) + r"(?:-[a-z0-9]+)+", b):
                b = ""
                break
            if b.startswith(s + " ") or b.startswith(s + "("):
                b = b[len(s):].strip()
                break
        m = RE_KURUNG.fullmatch(b)
        if m:
            b = m.group(1).strip()
        if b:
            hasil.append(b)
    return saring(" — ".join(hasil))[:200] if hasil else None


class Ev:
    """Peristiwa riwayat, urut (waktu, seq). `pemilik` = id yang boleh melihat selain pemilik tim (pemilik melihat semua).
    Misi (C3–C5): `kunci` (profil, sid) baris tim dan `misi` (nama berkas brief) diselesaikan saat render; `teks` yang
    callable(m) → (pelaku, teks) butuh id misi; `suf` = akhiran heuristik ` · <project_nama>` (dibuang bila pemilik misi
    ≠ pemilik heuristik)."""
    __slots__ = ("waktu", "seq", "pelaku", "teks", "pemilik", "kunci", "misi", "suf")

    def __init__(self, waktu, seq, pelaku, teks, pemilik, kunci=None, misi=None, suf=""):
        self.waktu, self.seq, self.pelaku, self.teks, self.pemilik = waktu, seq, pelaku, teks, pemilik
        self.kunci, self.misi, self.suf = kunci, misi, suf


def id_misi(n):
    return "T-%03d" % n


def baca_registri(data):
    """B2: {"versi": 1, "nomor": {nama: int ≥ 1 unik}}; selain itu ValueError."""
    d = json.loads(data)
    if not (isinstance(d, dict) and type(d.get("versi")) is int and d["versi"] == 1 and isinstance(d.get("nomor"), dict)):
        raise ValueError
    reg = d["nomor"]
    if not all(isinstance(k, str) and k and type(v) is int and v >= 1 for k, v in reg.items()):
        raise ValueError
    if len(set(reg.values())) != len(reg):
        raise ValueError
    return dict(reg)


def kuota_dari(teks):
    """B8: `delegation:` kolom-0 → baris berindentasi `oneshot_max_children: <int>` sebelum kunci kolom-0 berikutnya."""
    dalam = False
    for b in teks.split("\n"):
        if not b.strip() or b.lstrip().startswith("#"):
            continue
        if b[:1] not in (" ", "\t"):
            dalam = b.split("#", 1)[0].rstrip() == "delegation:"
            continue
        m = RE_KUOTA.fullmatch(b.rstrip()) if dalam else None
        if m:
            return int(m.group(1))
    return None


def waktu_epoch(x):
    if isinstance(x, (int, float)) and not isinstance(x, bool):
        try:
            return datetime.fromtimestamp(int(x), WIB)
        except (OverflowError, OSError, ValueError):
            return None
    return None


class Generator:
    def __init__(self, tim, proyek, keluaran, activity=None, workspace=None, proc=None, profil=None, nomor=None):
        """`tim` = path conf/tim.json (dibaca ulang tiap siklus); activity/workspace/proc/profil bila diberikan menimpa
        `sumber.*` di config (CLI menang)."""
        self.tim_path = os.fspath(tim)
        self.ov = {k: os.fspath(v) if v is not None else None
                   for k, v in (("activity", activity), ("workspace", workspace), ("proc", proc), ("profil", profil))}
        self.proyek, self.keluaran = os.fspath(proyek), os.fspath(keluaran)
        self.tim_cfg = None     # conf/tim.json sah terakhir (D2); None = belum pernah terbaca sah
        self.nomor = os.fspath(nomor) if nomor is not None else None  # None → registri hanya di memori (API/uji)
        self.reg_mem = {}       # registri nomor bila tanpa berkas
        self.seq_k3 = {}        # kunci peristiwa K3-2..4 → seq tetap (urutan terjadinya antar-siklus)
        self.kuota_cache = {}   # profil → (mtime_ns, size, kuota)
        self.ruang = {}         # id agen → ruang (C1) dari config sah terakhir
        self.misi_rec, self.misi_pem, self.misi_id, self.sub_misi = [], {}, {}, {}
        self.misi_info, self.misi_dimuat, self.ev_k3, self.idx = {}, set(), [], None
        try:
            self.klk = os.sysconf("SC_CLK_TCK")
        except (ValueError, OSError):
            self.klk = 100
        self.baris_baru = 0
        self.baris_dilewati = 0
        self.galat = frozenset()
        self.peta = {}
        self.cfg = {}           # `agen` dari conf/tim.json sah terakhir (D2)
        self.profil_temu = ([], [])  # (hadir [(id, description)], id bentrok) terakhir yang terbaca (D1)
        self.agen = []          # agen hadir siklus ini, urut tampil (D4): {id, nama, peran, induk}
        self.peringatan = []
        self.nama, self.tl, self.anggota, self.tim = {}, set(), set(), set()
        self.re_tl = self.re_anggota = re_panggil(())
        self.proses = []        # proses hermes terakhir yang terbaca
        self.lock = {}          # nama lock -> lock sah terakhir yang terbaca (rec["slug"] = project)
        self.ev_lock = []       # peristiwa dari lock (tetap walau log di-reset)
        self.seq = 0
        self.cache_header = {}  # path -> (mtime_ns, size, header)
        self.akar_brief = ""
        self.ino = None
        self.perlu_awal = True  # log harus dibaca dari awal (siklus pertama / sesudah galat)
        self._reset_log()

    def _reset_log(self):
        self.offset = 0
        self.ev_log = []
        self.tim_terakhir = {}      # profil -> (waktu, kategori)
        self.sid = set()
        self.koord_terakhir = None  # (waktu, apakah clarify, kunci R)
        self.r = {}                 # kunci R -> {nama, id, ts, kat, awal, msg}
        self.balas = {}             # kunci R -> waktu peristiwa "membalas" terakhir yang tampil
        # misi (B1–B7): diturunkan dari log, dibuang bersama keadaan log lain; nomor tetap lewat registri
        self.sid_msg = set()        # (profil, sid) yang baris msg pertamanya sudah diproses
        self.sid_misi = {}          # (profil, sid) sesi utama → nama berkas brief (dibekukan)
        self.misi_sesi = {}         # nama brief → {sesi, mulai, pelaksana, akhir, langkah, sekarang}
        self.misi_urut = []         # nama brief urut pertama kali menjadi misi (dasar nomor baru)
        self.ev_mulai = {}          # (profil, sid) → peristiwa "mulai bekerja" yang terbit sebelum baris msg pertama

    def _ev(self, daftar, waktu, pelaku, teks, pemilik, **kw):
        self.seq += 1
        e = Ev(waktu, self.seq, pelaku, teks, pemilik, **kw)
        daftar.append(e)
        return e

    # ---- sumber: daftar agen (D1–D5), peta project, proses, brief, lock ----
    def _baca_tim(self, galat):
        """D2: conf/tim.json; tidak terbaca / tidak sah → galat + config sah terakhir; belum pernah sah → ConfigTimTidakSah."""
        try:
            data = baca_biasa(self.tim_path, 1 << 20)
            if data is None:
                raise ValueError
            cfg = validasi_tim(json.loads(data))
        except (OSError, ValueError, RecursionError):
            galat.add(GALAT_AGEN)
            if self.tim_cfg is None:
                raise ConfigTimTidakSah from None
            return
        self._terapkan(cfg)

    def _terapkan(self, cfg):
        self.tim_cfg = cfg
        s = cfg["sumber"]
        self.activity, self.workspace = self.ov["activity"] or s["activity"], self.ov["workspace"] or s["workspace"]
        self.proc, self.profil_dir = self.ov["proc"] or s["proc"], self.ov["profil"] or s["profil"]
        self.dir_brief, self.dir_lock, self.kontainer = s["brief"], s["lock"], s["workspace_kontainer"].rstrip("/")
        self.orang, self.penonton, self.pemilik = cfg["orang"], cfg["penonton"], cfg["pemilik"]
        self.koord, self.cto, self.cfg = cfg["koordinator"], cfg["cto"], cfg["agen"]
        self.pemberi = {o["nama"]: o["id"] for o in self.orang}
        self.nama_orang = {v: k for k, v in self.pemberi.items()}
        po = cfg["pola"]
        self.pola_brief, self.re_lock, self.re_peminta, self.pemisah = po["brief_nama"], po["lock_nama"], po["peminta"], po["pemisah"]
        self.kat_sebelum, self.kat_sesudah = cfg["sebelum"], cfg["sesudah"]
        t = cfg["tool"]
        self.catat, self.setor = t["catat_progres"], t["setor"]
        self.kat_tool = dict(KATEGORI_TOOL)
        if t["awalan_bank_dokumen"]:
            for x in ("cari", "baca", "status"):
                self.kat_tool[t["awalan_bank_dokumen"] + x] = "membaca bank dokumen"
            for x in ("setor", "terbitkan", "hapus"):
                self.kat_tool[t["awalan_bank_dokumen"] + x] = "mengelola bank dokumen"
        if self.catat:
            self.kat_tool[self.catat] = "mencatat kemajuan"
        if self.setor:
            self.kat_tool[self.setor] = "mengelola bank dokumen"

    def _baca_profil(self, galat):
        """D1: folder <profil>/<id>/profile.yaml (berkas biasa) = agen hadir; dipindai ulang tiap siklus."""
        try:
            nama = sorted(os.listdir(self.profil_dir))
        except OSError:
            galat.add(GALAT_PROFIL)
            return
        tetap = {self.koord} | {o["id"] for o in self.orang}
        hadir, bentrok = [], []
        for i in nama:
            if not RE_ID.fullmatch(i):
                continue
            try:
                data = baca_biasa(f"{self.profil_dir}/{i}/profile.yaml", 1 << 16)
            except OSError:
                continue
            if data is None:
                continue
            if i in tetap:
                bentrok.append(i)
            else:
                hadir.append((i, deskripsi(data.decode("utf-8", "replace"))))
        self.profil_temu = (hadir, bentrok)

    def _baca_agen(self, galat):
        """D1–D5, D9: agen hadir + atribut efektif + golongan (TL / anggota) + regex panggil + peringatan."""
        self._baca_tim(galat)
        self._baca_profil(galat)
        hadir, bentrok = self.profil_temu
        desk = dict([(self.koord, "")] + hadir)
        tanpa = sorted(i for i in desk if i not in self.cfg and i != self.koord)
        urut = [i for i in self.cfg if i in desk] + ([self.koord] if self.koord not in self.cfg else []) + tanpa
        agen = {}
        for i in urut:
            e = self.cfg.get(i)
            if e:
                agen[i] = {"id": i, "nama": saring(e["nama"]), "peran": saring(e["peran"]), "induk": e["induk"]}
            else:  # bawaan D3; akar (koordinator) tanpa induk
                agen[i] = {"id": i, "nama": i.capitalize(), "peran": saring(desk[i])[:120],
                           "induk": [] if i == self.koord else [self.koord]}
        self.agen = list(agen.values())
        self.nama = {a["id"]: a["nama"] for a in self.agen}
        self.ruang = {i: (self.cfg[i]["ruang"] if i in self.cfg else "lain") for i in agen}
        self.nama_koord = self.nama[self.koord]
        self.tl = {i for i, a in agen.items() if i not in (self.cto, self.koord) and self.cto in a["induk"]}
        self.tim = set(agen) - {self.koord}
        self.anggota = self.tim - self.tl
        self.re_tl, self.re_anggota = re_panggil(self.tl), re_panggil(self.anggota)
        self.peringatan = sorted({saring(f"Profil {i} belum ada di conf/tim.json") for i in agen if i not in self.cfg}
                                 | {saring(f"Profil {i} bentrok dengan id tetap, diabaikan") for i in bentrok})

    def _baca_peta(self, galat):
        try:
            with open(self.proyek, "rb") as f:
                d = json.loads(f.read(1 << 20))
            if not isinstance(d, dict):
                raise ValueError
            self.peta = {k: v for k, v in d.items() if isinstance(v, str)}
        except (OSError, ValueError, RecursionError):
            galat.add(GALAT_PETA)

    def _nama(self, slug):
        return saring(self.peta.get(slug, slug))

    def _baca_proses(self, galat):
        try:
            nama = os.listdir(self.proc)
        except OSError:
            galat.add(GALAT_PROSES)
            return
        btime = None
        try:
            with open(f"{self.proc}/stat", "rb") as f:
                for b in f:
                    if b.startswith(b"btime "):
                        btime = int(b.split()[1])
                        break
        except (OSError, ValueError, IndexError):
            pass
        daftar = []
        for n in nama:
            if not (n.isascii() and n.isdigit()):
                continue
            try:
                with open(f"{self.proc}/{n}/cmdline", "rb") as f:
                    data = f.read(1 << 20)
            except OSError:
                continue
            if b"hermes" not in data:
                continue
            argv = [a.decode("utf-8", "replace") for a in (data[:-1] if data.endswith(b"\0") else data).split(b"\0")]
            if not program_hermes(argv):
                continue
            mulai = ppid = None
            try:
                with open(f"{self.proc}/{n}/stat", "rb") as f:
                    s = f.read().decode("utf-8", "replace")
                kol = s[s.rindex(")") + 2:].split()
                ppid = int(kol[1])  # B6: rantai PPID
                if btime is not None:
                    mulai = datetime.fromtimestamp(btime + int(kol[19]) // self.klk, WIB)
            except (OSError, ValueError, IndexError):
                pass
            z = next((argv[i + 1] for i, a in enumerate(argv[:-1]) if a == "-z"), None)
            daftar.append({"pid": str(int(n)), "profil": profil_hermes(argv), "mulai": mulai, "ppid": ppid,
                           "header": header_dari(z.split("\n"), self.re_peminta) if z is not None else None})
        self.proses = daftar

    def _brief_aman(self, path):
        """realpath bila berkas biasa di dalam direktori brief, else None."""
        try:
            real = os.path.realpath(path)
            if not real.startswith(self.akar_brief + os.sep):
                return None
            return real if stat.S_ISREG(os.stat(real).st_mode) else None
        except (OSError, ValueError):
            return None

    def _header(self, real):
        try:
            st = os.stat(real)
            c = self.cache_header.get(real)
            if c and c[0] == st.st_mtime_ns and c[1] == st.st_size:
                return c[2]
            h = header_dari(baca_baris_awal(real), self.re_peminta)
            self.cache_header[real] = (st.st_mtime_ns, st.st_size, h)
            return h
        except OSError:
            return None

    def _real_brief_lock(self, nilai):
        awal = self.kontainer + "/"
        if not nilai.startswith(awal):
            return None
        return self._brief_aman(f"{self.workspace}/{nilai[len(awal):]}")

    def _hitung_header_brief(self):
        c = Counter()
        try:
            with os.scandir(self.akar_brief) as it:
                for e in it:
                    if e.name.endswith(".md"):
                        # berkas biasa langsung di akar brief sudah pasti di dalamnya; symlink harus diselesaikan
                        real = self._brief_aman(e.path) if e.is_symlink() else (e.path if e.is_file(follow_symlinks=False) else None)
                        h = self._header(real) if real else None
                        if h:
                            c[h] += 1
        except OSError:
            pass
        return c

    def _indeks_brief(self):
        """B1/B6 (sekali per siklus, malas): H1 → [nama], header → [nama], nama → header untuk <brief>/*.md berkas biasa."""
        if self.idx is None:
            h1, hd, per_nama = {}, {}, {}
            try:
                with os.scandir(self.akar_brief) as it:
                    for e in it:
                        if not e.name.endswith(".md"):
                            continue
                        real = self._brief_aman(e.path) if e.is_symlink() else (e.path if e.is_file(follow_symlinks=False) else None)
                        h = self._header(real) if real else None
                        if h:
                            per_nama[e.name] = h
                            hd.setdefault(h, []).append(e.name)
                            if h[0].startswith("# "):
                                h1.setdefault(h[0].strip(), []).append(e.name)
            except OSError:
                pass
            self.idx = (h1, hd, per_nama)
        return self.idx

    def _baca_lock(self, t, galat):
        d = self.dir_lock
        try:
            nama = sorted(os.listdir(d))
        except OSError:
            galat.add(GALAT_LOCK)
            return
        baru = {}
        for n in nama:
            kunci = n[:-5]  # nama lock; `pola.lock_pemisah_subtugas` memisahkan slug project dari subtugas
            if not n.endswith(".lock") or len(kunci) > 64 or not self.re_lock.fullmatch(kunci):
                continue
            slug = kunci.split(self.pemisah, 1)[0] if self.pemisah else kunci
            if not slug:
                continue
            try:
                data = baca_biasa(f"{d}/{n}", 4096)
            except OSError:
                continue
            if data is None:
                continue
            kv = {}
            for b in data.decode("utf-8", "replace").split("\n"):
                k, sep, v = b.partition("=")
                if sep:
                    kv.setdefault(k.strip(), v.strip())
            if kv.get("tl") not in self.tl:
                continue
            real = self._real_brief_lock(kv.get("brief", ""))
            h = self._header(real) if real else None
            pem = pemberi_dari(h, self.re_peminta, self.pemberi) if h else None
            nama_p = self._nama(slug)
            nb = os.path.basename(real) if real else None
            pb = self._proyek_berkas(nb, kv["tl"]) if nb else None
            baru[kunci] = {"slug": slug, "tl": kv["tl"], "pengerja": self.nama[kv["tl"]], "mulai": parse_waktu(kv.get("mulai")),
                          "nama": nama_p, "judul": ((judul_dari(h, {slug, pb}) if h else None)
                                                    or self._judul_berkas(nb, kv["tl"]) or f"Pekerjaan {nama_p}"),  # J-1/J-2
                          "pemberi": pem, "pemberi_id": self.pemberi.get(pem), "ev_mulai": None,
                          "brief": nb}  # B6 "lock misi" / C3
        for kunci, rec in baru.items():
            lama = self.lock.get(kunci)
            if lama and lama["tl"] == rec["tl"] and lama["mulai"] == rec["mulai"]:
                rec["ev_mulai"] = lama["ev_mulai"]
            else:
                if lama:
                    self._selesai(lama, t)
                if rec["mulai"]:
                    rec["ev_mulai"] = self._ev(self.ev_lock, rec["mulai"], rec["tl"],
                                               f"{rec['pengerja']} mulai {rec['nama']}", self.pemilik)
            if rec["ev_mulai"]:
                rec["ev_mulai"].pemilik = self._pemilik_tugas(rec)
                rec["ev_mulai"].misi = rec["brief"]
        for kunci, lama in self.lock.items():
            if kunci not in baru:
                self._selesai(lama, t)
        self.lock = baru

    def _selesai(self, lama, t):
        self._ev(self.ev_lock, t, lama["tl"], f"{lama['pengerja']} selesai {lama['nama']}", self._pemilik_tugas(lama),
                 misi=lama["brief"])

    def _pemilik_tugas(self, k):
        return k["pemberi_id"] or self.pemilik

    # ---- tugas (a) TL dari lock dan (b) anggota non-TL dari proses; langkah_* diisi belakangan ----
    def _kerangka(self):
        jalan = {p for pr in self.proses for p in pr["profil"]}
        hasil = []
        for kunci, rec in self.lock.items():
            hasil.append({"id": f"lock-{kunci}", "judul": rec["judul"], "project": rec["slug"], "project_nama": rec["nama"],
                          "pemberi": rec["pemberi"], "pemberi_id": rec["pemberi_id"], "pengerja": rec["pengerja"],
                          "pengerja_id": rec["tl"], "mulai": iso(rec["mulai"]) if rec["mulai"] else None,
                          "langkah_terakhir": None, "langkah_waktu": None,
                          "status": "jalan" if rec["tl"] in jalan else "menunggu"})
        hitung = None
        for pr in self.proses:
            ag = next((p for p in pr["profil"] if p in self.anggota), None)
            if ag is None:
                continue
            h = pr["header"]
            judul = pem = None
            if h:
                hitung = hitung if hitung is not None else self._hitung_header_brief()
                if hitung[h] == 1:
                    judul, pem = judul_dari(h), pemberi_dari(h, self.re_peminta, self.pemberi)
            hasil.append({"id": f"proses-{pr['pid']}", "judul": judul, "project": None, "project_nama": None,
                          "pemberi": pem, "pemberi_id": self.pemberi.get(pem), "pengerja": self.nama[ag], "pengerja_id": ag,
                          "mulai": iso(pr["mulai"]) if pr["mulai"] else None, "langkah_terakhir": None,
                          "langkah_waktu": None, "status": "jalan"})
        return hasil

    # ---- log aktivitas ----
    def _baca_log(self, galat, kerangka):
        try:
            fd = os.open(self.activity, os.O_RDONLY | os.O_NONBLOCK)
            with os.fdopen(fd, "rb") as f:
                st = os.fstat(fd)
                if not stat.S_ISREG(st.st_mode):
                    raise OSError
                live = True  # False hanya pada siklus yang membaca log dari awal (backfill)
                if self.perlu_awal or (self.ino is not None and (st.st_ino != self.ino or st.st_size < self.offset)):
                    self._reset_log()
                    self.perlu_awal = False
                    live = False
                self.ino = st.st_ino
                f.seek(self.offset)
                # baris demi baris: seluruh berkas / daftar baris tidak pernah disimpan (unit live MemoryMax=64M, log ±17 MB)
                for raw in f:
                    if not raw.endswith(b"\n"):
                        break  # baris terakhir belum lengkap: dibaca lagi siklus berikutnya
                    self.offset += len(raw)
                    self.baris_baru += 1
                    if not self._baris(raw[:-1].decode("utf-8", "replace"), live, kerangka):
                        self.baris_dilewati += 1
        except OSError:
            galat.add(GALAT_LOG)
            self.perlu_awal = True
            return

    def _pemilik_tunggal(self, kerangka, agen):
        pem = {self._pemilik_tugas(k) for k in kerangka if k["pengerja_id"] == agen}
        return pem.pop() if len(pem) == 1 else None

    def _pemilik_agen(self, kerangka, agen, live):
        """(pemilik, akhiran) peristiwa baris agen tim: hanya mode live dan bila semua tugasnya satu pemilik."""
        pem = self._pemilik_tunggal(kerangka, agen) if live else None
        if pem is None:
            return self.pemilik, ""
        ts = [k for k in kerangka if k["pengerja_id"] == agen]
        return pem, f" · {ts[0]['project_nama']}" if len(ts) == 1 and ts[0]["project"] else ""

    def _pemilik_panggil(self, kerangka, x, live):
        if not live:
            return self.pemilik
        pem = self._pemilik_tunggal(kerangka, self.cto)
        if pem:
            return pem
        kunci = [k for k in kerangka if k["pengerja_id"] == x]
        return self._pemilik_tugas(kunci[0]) if len(kunci) == 1 else self.pemilik

    def _baris(self, b, live, kerangka):
        """Proses satu baris log; False bila dilewati (bukan objek JSON / ts tidak sah)."""
        try:
            d = json.loads(b)
        except (ValueError, RecursionError):
            return False
        ts = d.get("ts") if isinstance(d, dict) else None
        if not (isinstance(ts, str) and RE_TS.fullmatch(ts)):
            return False
        try:
            w = datetime.fromisoformat(ts).replace(tzinfo=WIB)
        except ValueError:
            return False
        profil = d.get("profile")
        jenis = d.get("type")
        if jenis == "msg" and (d.get("sistem") is True or (isinstance(d.get("text"), str) and RE_SISTEM.search(d["text"]))):
            return True  # notifikasi gateway yang disisipkan ke sesi, bukan pesan orang: sah tetapi tanpa efek apa pun
        tool = d.get("tool") if isinstance(d.get("tool"), str) else ""
        detail = d.get("detail") if isinstance(d.get("detail"), str) else ""
        ev = self.ev_log
        if profil is None:  # koordinator
            nm = d.get("name").strip() if isinstance(d.get("name"), str) else ""
            rid = self.pemberi.get(nm)
            nama = nm if rid else (saring(nm) if nm not in ("", "?") else TANPA_PENGIRIM)
            kunci = rid or ("x", nama)  # pengirim tak dikenal tidak boleh bertabrakan dengan id orang
            if jenis == "reply":  # hanya peristiwa riwayat: r, koord_terakhir, tugas, status tidak berubah
                b = self.balas.get(kunci)
                if b is None or (w - b).total_seconds() >= 300:
                    self.balas[kunci] = w
                    self._ev(ev, w, self.koord, f"{self.nama_koord} membalas {nama}", rid or self.pemilik)
                return True
            kat, panggil = kategori(jenis, tool, detail, self, nama)
            r = self.r.setdefault(kunci, {"nama": nama, "id": rid, "ts": None, "kat": None, "awal": None, "msg": None})
            if r["ts"] is None or (w - r["ts"]).total_seconds() > 600:
                r["awal"] = w
            r["ts"], r["kat"] = w, kat
            self.koord_terakhir = (w, jenis != "msg" and tool == "clarify", kunci)
            pem = rid or self.pemilik
            nk = self.nama_koord
            if jenis == "msg":
                if r["msg"] is None or (w - r["msg"]).total_seconds() >= 300:
                    r["msg"] = w
                    self._ev(ev, w, self.koord, f"{nama} mengirim pesan ke {nk}", pem)
            elif tool == "clarify":
                self._ev(ev, w, self.koord, f"{nk} meminta keputusan {nama}", pem)
            elif tool in TERMINAL and panggil and panggil[0] == "anggota":
                self._ev(ev, w, self.koord, f"{nk} {kat}", pem)
            elif self.catat and tool == self.catat:
                self._ev(ev, w, self.koord, f"{nk} mencatat kemajuan", pem)
            elif self.setor and tool == self.setor:
                self._ev(ev, w, self.koord, f"{nk} menyetor dokumen ke bank dokumen", pem)
        elif isinstance(profil, str) and profil in self.tim and jenis != "reply":  # reply ber-profile diabaikan tanpa efek
            nama = self.nama[profil]
            sid = d.get("sid") if isinstance(d.get("sid"), str) else ""
            kunci = (profil, sid)
            kat, panggil = kategori(jenis, tool, detail, self)
            self.tim_terakhir[profil] = (w, kat)
            pem, suf = self._pemilik_agen(kerangka, profil, live)
            if jenis == "msg" and d.get("sub") is True:  # sesi subagent (hook U-1, 17 Okt 2026): bukan "mulai bekerja"
                self.sid.add(kunci)
            if jenis == "msg" and kunci not in self.sid_msg:  # B1: baris msg pertama sesi; `text` hanya dicocokkan
                self.sid_msg.add(kunci)
                e = self.ev_mulai.pop(kunci, None)
                nb = (self._cocok_misi(d["text"]) if sid and d.get("sub") is not True and isinstance(d.get("text"), str)
                      else None)
                if nb:
                    if e is not None and e in self.ev_log:  # C4: "mulai bekerja" yang terlanjur terbit diganti
                        self.ev_log.remove(e)
                    self._misi_baru(kunci, nb, w)
            if kunci not in self.sid:
                self.sid.add(kunci)
                if kunci not in self.sid_misi:  # C4: sesi utama misi memakai K3-1 / "melanjutkan"
                    e = self._ev(ev, w, profil, f"{nama} mulai bekerja", pem, kunci=kunci, suf=suf)
                    if sid and kunci not in self.sid_msg:
                        self.ev_mulai[kunci] = e
            m = self.misi_sesi[self.sid_misi[kunci]] if kunci in self.sid_misi else None
            if m is not None:  # B6 berakhir + B7 langkah / langkah sekarang: hanya baris sesi utama
                m["akhir"], m["sekarang"] = w, (w, kat)
                if jenis != "msg" and self.catat and tool == self.catat:
                    s = RE_STATUS.search(detail)
                    m["langkah"].append((w, LABEL.get(s.group(1).lower(), "Kemajuan dicatat") if s else "Kemajuan dicatat"))
            if jenis != "msg":
                if self.catat and tool == self.catat:
                    self._ev(ev, w, profil, f"{nama} mencatat kemajuan", pem, kunci=kunci, suf=suf)
                elif self.setor and tool == self.setor:
                    self._ev(ev, w, profil, f"{nama} menyetor dokumen ke bank dokumen", pem, kunci=kunci)
                elif profil == self.cto and tool in TERMINAL and panggil and panggil[0] == "tl":
                    self._ev(ev, w, profil, f"{nama} memanggil {self.nama[panggil[1]]}",
                             self._pemilik_panggil(kerangka, panggil[1], live), kunci=kunci)
        return True

    # ---- misi (KONTRAK Kantor Agen bagian B/C; docs/misi.md) ----
    def _cocok_misi(self, teks):
        """B1': baris 1 `text` (strip) = H1 (strip) tepat satu brief → nama berkas brief itu. H1 milik > 1 brief → brief
        ber-H1 itu yang header gabungannya (H1 s.d. baris Peminta, `\\r` akhir baris dibuang dua sisi) sama dengan `text`
        pada min(len) karakter pertama; tepat satu kandidat → brief itu, selain itu None (fail-closed). Hanya di memori."""
        b1 = teks.split("\n", 1)[0].strip()
        if not b1.startswith("#"):
            return None
        h1, _, per_nama = self._indeks_brief()
        nama = h1.get(b1)
        if not nama or len(nama) == 1:
            return nama[0] if nama else None
        t = "\n".join(x.rstrip("\r") for x in teks.split("\n"))
        gab = {n: "\n".join(per_nama[n]) for n in nama}
        cocok = [n for n, g in gab.items() if t.startswith(g) or g.startswith(t)]  # = sama pada min(len) karakter pertama
        return cocok[0] if len(cocok) == 1 else None

    def _misi_baru(self, kunci, nb, w):
        self.sid_misi[kunci] = nb
        m = self.misi_sesi.get(nb)
        if m is None:
            m = self.misi_sesi[nb] = {"sesi": [], "mulai": w, "pelaksana": kunci[0], "akhir": w, "langkah": [],
                                      "sekarang": None}
            self.misi_urut.append(nb)
            self._ev(self.ev_log, w, self.koord, self._k31, None, misi=nb)  # K3-1 (C4: sesi pertama)
        else:
            nm = self.nama[kunci[0]]
            self._ev(self.ev_log, w, kunci[0], lambda n, mid, nm=nm: (None, f"{nm} melanjutkan {mid}"), None, misi=nb)
        m["sesi"].append(kunci)
        m["pelaksana"] = kunci[0]

    def _k31(self, n, mid):
        pem, pem_id, rantai = self.misi_info[n]
        lewat = " → ".join(self.nama.get(i, i.capitalize()) for i in (rantai[1:] if pem_id else rantai))
        return pem_id or self.koord, (f"{pem} memberi order {mid} lewat {lewat}" if pem else f"Order {mid} masuk lewat {lewat}")

    def _registri(self, galat):
        """B2: registri nomor (berkas --nomor, atau memori); rusak/tak terbaca/gagal tulis → galat + None (tidak ditimpa)."""
        if self.nomor is None:
            reg = self.reg_mem
        else:
            try:
                data = baca_biasa(self.nomor, 1 << 20)
                if data is None:
                    raise ValueError
                reg = baca_registri(data)
            except FileNotFoundError:
                reg = {}
            except (OSError, ValueError, RecursionError):
                galat.add(GALAT_NOMOR)
                return None
        maks, ubah = max(reg.values(), default=0), False
        for n in self.misi_urut:
            if n not in reg:
                maks += 1
                reg[n] = maks
                ubah = True
        if ubah and self.nomor is not None:
            try:
                self._tulis_registri(reg)
            except OSError:
                galat.add(GALAT_NOMOR)
                return None
        return reg

    def _tulis_registri(self, reg):
        os.makedirs(os.path.dirname(self.nomor) or ".", mode=0o750, exist_ok=True)
        tmp = self.nomor + ".tmp"
        teks = json.dumps({"versi": 1, "nomor": dict(sorted(reg.items(), key=lambda x: x[1]))}, indent=1) + "\n"
        # ensure_ascii (bawaan): nama berkas non-UTF-8 (surrogateescape) tetap tertulis sah dan terbaca ulang sama
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
        try:
            with os.fdopen(fd, "wb") as f:
                os.fchmod(f.fileno(), 0o640)
                f.write(teks.encode("utf-8"))
            os.replace(tmp, self.nomor)
        except BaseException:
            try:
                os.unlink(tmp)
            except OSError:
                pass
            raise

    def _ppid(self, pid, cache):
        if pid not in cache:
            try:
                with open(f"{self.proc}/{pid}/stat", "rb") as f:
                    s = f.read(4096).decode("utf-8", "replace")
                cache[pid] = str(int(s[s.rindex(")") + 2:].split()[1]))
            except (OSError, ValueError, IndexError):
                cache[pid] = None
        return cache[pid]

    def _laporan(self, n):
        """B6: mtime `<brief tanpa .md>.laporan.txt` bila berkas biasa > 0 byte, else None (isi tidak dibaca)."""
        try:
            st = os.stat(os.path.join(self.akar_brief, n[:-3] + ".laporan.txt"))
        except (OSError, ValueError):
            return None
        return datetime.fromtimestamp(int(st.st_mtime), WIB) if stat.S_ISREG(st.st_mode) and st.st_size > 0 else None

    def _proyek_berkas(self, n, pel):
        """B4: kunci conf/proyek.json terpanjang yang menjadi awalan sisa nama sesudah `YYYY-MM-DD-<pelaksana>-`."""
        m = re.fullmatch(self.pola_brief.replace("{pelaksana}", re.escape(pel)), n)
        if not m:
            return None
        cocok = [k for k in self.peta if m.group("sisa") == k or m.group("sisa").startswith(k + "-")]
        return max(cocok, key=len) if cocok else None

    def _judul_berkas(self, n, pel):
        """J-2: judul kosong pelaksana TL → "<nama project berkas> — <topik>" (topik = sisa nama sesudah
        `YYYY-MM-DD-<pel>-<pb>-` tanpa `.md`, `-` → spasi); tanpa project berkas atau topik → None (perilaku lama)."""
        pb = self._proyek_berkas(n, pel) if n else None
        m = re.fullmatch(self.pola_brief.replace("{pelaksana}", re.escape(pel)), n) if pb else None
        topik = m.group("sisa")[len(pb) + 1:] if m and m.group("sisa").startswith(pb + "-") else ""
        return saring(f"{self._nama(pb)} — {topik.replace('-', ' ')}")[:200] if topik else None

    def _rantai(self, pel, pem_id):
        """B5: [pemberi_id] + jalur organisasi koordinator → pelaksana (induk efektif pertama yang hadir, maks 6 langkah)."""
        induk = {a["id"]: a["induk"] for a in self.agen}
        jalur, cur = [pel], pel
        for _ in range(6):
            if cur == self.koord:
                break
            nx = next((i for i in induk.get(cur, []) if i in induk), None)
            if nx is None:
                break
            jalur.append(nx)
            cur = nx
        if jalur[-1] != self.koord:
            jalur = [pel]
        return ([pem_id] if pem_id else []) + jalur[::-1]

    def _kuota(self, p):
        """B8: delegation.oneshot_max_children dari <profil>/<p>/config.yaml (cache mtime+ukuran); tidak ada → None."""
        path = f"{self.profil_dir}/{p}/config.yaml"
        try:
            st = os.stat(path)
            c = self.kuota_cache.get(p)
            if c and c[0] == st.st_mtime_ns and c[1] == st.st_size:
                return c[2]
            data = baca_biasa(path, 1 << 20)
            k = kuota_dari(data.decode("utf-8", "replace")) if data is not None else None
            self.kuota_cache[p] = (st.st_mtime_ns, st.st_size, k)
            return k
        except OSError:
            return None

    def _sesi_db(self, p, sids):
        """B8: baris sub-agen (4 kolom) dari state.db profil p, URI mode=ro, timeout 1 dtk; galat sqlite → None."""
        db = os.path.abspath(f"{self.profil_dir}/{p}/state.db")
        try:
            con = sqlite3.connect("file:" + quote(db) + "?mode=ro", uri=True, timeout=1.0)
            try:
                return con.execute(KUERI_SESI.format(",".join("?" * len(sids))), sids).fetchall()
            finally:
                con.close()
        except sqlite3.Error:
            return None

    def _misi(self, t, galat):
        """B2–B8 per siklus → misi_rec (dimuat, urut C8), misi_pem/misi_info/misi_id (semua misi), sub_misi, ev_k3."""
        self.misi_rec, self.misi_pem, self.misi_info, self.misi_id, self.sub_misi = [], {}, {}, {}, {}
        self.misi_dimuat, self.ev_k3 = set(), []
        reg = self._registri(galat)  # B2: dibaca tiap siklus agar registri rusak selalu menjadi galat
        if not self.misi_sesi:
            return
        _, hd, per_nama = self._indeks_brief()
        for n, m in self.misi_sesi.items():
            h = per_nama.get(n)
            pem = pemberi_dari(h, self.re_peminta, self.pemberi) if h else None
            self.misi_pem[n] = self.pemberi.get(pem) or self.pemilik
            self.misi_info[n] = (pem, self.pemberi.get(pem), self._rantai(m["pelaksana"], self.pemberi.get(pem)))
        if reg is None:
            return
        self.misi_id = {n: id_misi(reg[n]) for n in self.misi_sesi}
        # proses misi: header -z cocok tepat 1 brief (= brief misi) dan pelaksana ada di argumen -p
        cache, proses_misi = {}, {}
        for pr in self.proses:
            cache[pr["pid"]] = str(pr["ppid"]) if pr["ppid"] is not None else None
            nama = hd.get(pr["header"]) if pr["header"] else None
            if nama and len(nama) == 1 and nama[0] in self.misi_sesi and self.misi_sesi[nama[0]]["pelaksana"] in pr["profil"]:
                proses_misi[pr["pid"]] = nama[0]
        anak, induk = {}, {}
        for pid in sorted(proses_misi, key=int):
            n, cur = proses_misi[pid], self._ppid(pid, cache)
            for _ in range(64):  # rantai PPID ke atas
                if cur is None or cur in ("0", "1"):
                    break
                a = proses_misi.get(cur)
                if a is not None and a != n:
                    anak.setdefault(a, set()).add(n)
                    induk.setdefault(n, a)  # leluhur terdekat
                cur = self._ppid(cur, cache)
        lock_brief = {}
        for kunci in sorted(self.lock):
            if self.lock[kunci]["brief"]:
                lock_brief.setdefault(self.lock[kunci]["brief"], self.lock[kunci]["slug"])
        hidup = set(proses_misi.values())
        for n, m in self.misi_sesi.items():
            lap = self._laporan(n)
            if n in hidup:
                st, al, sel = ("menunggu", "misi-lain", None) if n in anak else ("jalan", None, None)
            elif n in lock_brief:
                st, al, sel = "menunggu", ("review" if lap else "gantung"), None
            else:
                st, al, sel = ("selesai", None, lap) if lap else ("berakhir", None, m["akhir"])
            if sel is not None and sel.date() != t.date():
                continue
            pel = m["pelaksana"]
            pem, pem_id, rantai = self.misi_info[n]
            h = per_nama.get(n)
            proj = lock_brief.get(n) or self._proyek_berkas(n, pel)
            nproj = self._nama(proj) if proj else None
            sk = m["sekarang"]
            tl = pel in self.tl
            self.misi_rec.append({
                "id": self.misi_id[n], "nomor": reg[n],
                "judul": ((judul_dari(h, {lock_brief.get(n), self._proyek_berkas(n, pel)}) if tl and proj else judul_dari(h))
                          if h else None)
                         or (self._judul_berkas(n, pel) if tl else None)  # J-2
                         or (f"Pekerjaan {nproj}" if tl and proj else None),  # §3.5: TL kosong → Pekerjaan
                "project": proj, "project_nama": nproj, "pemberi": pem, "pemberi_id": pem_id, "pelaksana_id": pel,
                "pelaksana": self.nama.get(pel) or pel.capitalize(), "rantai": rantai, "status": st, "alasan": al,
                "menunggu_misi": sorted((self.misi_id[x] for x in anak.get(n, ()) if al == "misi-lain"),
                                        key=lambda i: int(i[2:])),
                "induk_misi": self.misi_id[induk[n]] if n in hidup and n in induk else None,
                "mulai": iso(m["mulai"]), "selesai": iso(sel) if sel else None,
                "langkah": [{"waktu": iso(x), "label": lb} for x, lb in m["langkah"]], "langkah_total": None,
                "langkah_sekarang": (sk[1] + (f" · {nproj}" if proj else "")) if sk else None,
                "langkah_waktu": iso(sk[0]) if sk else None, "subagen": [], "spawn_kuota": self._kuota(pel), "_n": n,
                "_sel": sel})
            self.misi_dimuat.add(n)
        self._subagen(t, galat)
        aktif = lambda r: r["status"] in ("jalan", "menunggu")
        self.misi_rec.sort(key=lambda r: (0, r["status"] != "menunggu", r["mulai"], r["nomor"]) if aktif(r)
                           else (1, -r["_sel"].timestamp(), "", r["nomor"]))
        for r in self.misi_rec:
            del r["_n"], r["_sel"]

    def _subagen(self, t, galat):
        """B8 + K3-2..4: sub-agen per misi dimuat dari state.db profil pelaksana; peristiwa K3 hari ini."""
        seq_lama, self.seq_k3 = self.seq_k3, {}

        def k3(kunci, waktu, pelaku, teks, n):
            if waktu is None or waktu.date() != t.date():
                return
            s = self.seq_k3[kunci] = seq_lama.get(kunci) or self._seq_baru()
            self.ev_k3.append(Ev(waktu, s, pelaku, teks, self.misi_pem[n], misi=n))

        per_profil = {}
        for r in self.misi_rec:
            per_profil.setdefault(r["pelaksana_id"], []).append(r)
        for p in sorted(per_profil):
            sids = sorted({s for r in per_profil[p] for _, s in self.misi_sesi[r["_n"]]["sesi"]})
            baris = self._sesi_db(p, sids)
            if baris is None:
                galat.add(GALAT_SESI)
            for r in per_profil[p]:
                n = r["_n"]
                if baris is None:
                    r["subagen"] = None
                else:
                    sesi = {s for _, s in self.misi_sesi[n]["sesi"]}
                    sub = sorted(((waktu_epoch(b[2]), waktu_epoch(b[3]), str(b[0])) for b in baris
                                  if b[1] in sesi and waktu_epoch(b[2]) is not None), key=lambda x: (x[0], x[2]))
                    r["subagen"] = [{"ke": i, "mulai": iso(a), "selesai": iso(z) if z else None}
                                    for i, (a, z, _) in enumerate(sub, 1)]
                    for i, (a, z, sid) in enumerate(sub, 1):
                        self.sub_misi[(p, sid)] = n
                        k3((n, "spawn", sid), a, p, f"{r['pelaksana']} men-spawn sub-agen ke-{i} · {r['id']}", n)
                        k3((n, "akhir-sub", sid), z, p, f"Sub-agen ke-{i} {r['pelaksana']} selesai · {r['id']}", n)
                if r["status"] in ("selesai", "berakhir"):
                    k3((n, r["status"], r["selesai"]), r["_sel"], p, f"{r['pelaksana']} menyelesaikan {r['id']}"
                       if r["status"] == "selesai" else f"{r['id']} berakhir tanpa laporan", n)

    def _seq_baru(self):
        self.seq += 1
        return self.seq

    def _render(self, e):
        """Peristiwa → (waktu, pelaku, teks, pemilik, id misi tampil | None); None = tidak tampil (id misi tak ada)."""
        n = (self.sid_misi.get(e.kunci) or self.sub_misi.get(e.kunci)) if e.kunci is not None else (
            e.misi if e.misi in self.misi_sesi else None)
        if n is None:
            return None if callable(e.teks) else (e.waktu, e.pelaku, e.teks + e.suf, e.pemilik, None)
        pem, mid = self.misi_pem.get(n, self.pemilik), self.misi_id.get(n)
        if callable(e.teks):
            if mid is None:
                return None
            pelaku, teks = e.teks(n, mid)
        else:
            # C3/C7: akhiran heuristik milik pemilik lain dibuang, kecuali baris milik pemilik tim (melihat semua; teks lama, A1)
            pelaku, teks = None, e.teks + (e.suf if e.pemilik == pem or pem == self.pemilik else "")
        return e.waktu, pelaku or e.pelaku, teks, pem, mid if n in self.misi_dimuat else None

    # ---- siklus ----
    def siklus(self, sekarang):
        t = sekarang.replace(tzinfo=WIB) if sekarang.tzinfo is None else sekarang.astimezone(WIB)
        galat = set()
        self.idx = None  # indeks brief dibangun ulang (malas) tiap siklus
        self._baca_agen(galat)  # membaca conf/tim.json lebih dulu: sumber dan identitas bergantung padanya
        self.akar_brief = os.path.realpath(self.dir_brief)
        self._baca_peta(galat)
        self._baca_proses(galat)
        self._baca_lock(t, galat)
        kerangka = self._kerangka()  # tugas (a)/(b): dipakai juga untuk pemilik peristiwa baris log baru
        self._baca_log(galat, kerangka)
        self._misi(t, galat)
        self.galat = frozenset(galat)
        keadaan = self._keadaan(t, kerangka)
        # semua berkas dibangun dulu; pengecualian di sini = tidak ada berkas yang ditulis siklus ini
        isi = {p: json.dumps(self._berkas(p, t, keadaan), ensure_ascii=False, separators=(",", ":")) + "\n"
               for p in self.penonton}
        self._tulis(isi)

    def _status_koord(self, t):
        a = self.koord_terakhir
        umur = max(0.0, (t - a[0]).total_seconds()) if a else None
        if a and a[1] and umur < 1800:
            return "menunggu"
        if (a and umur < 120) or any(p in self.anggota for pr in self.proses for p in pr["profil"]):
            return "jalan"
        return "bebas"

    def _tugas_koord(self, t, kerangka, status):
        """(c): satu tugas per pengirim R yang punya baris < 10 menit, atau pemberi tugas (b) milik R."""
        ada = {kunci: r for kunci, r in self.r.items() if max(0.0, (t - r["ts"]).total_seconds()) < 600}
        for k in kerangka:
            rid = k["pemberi_id"]
            if rid and k["id"].startswith("proses-") and rid not in ada:
                ada[rid] = self.r.get(rid) or {"nama": self.nama_orang[rid], "id": rid, "ts": None, "kat": None, "awal": None}
        return [{"id": f"{self.koord}-{r['id']}" if r["id"] else f"{self.koord}-x" + hashlib.sha256(r["nama"].encode("utf-8")).hexdigest()[:8],
                 "judul": "Permintaan lewat Telegram", "project": None, "project_nama": None,
                 "pemberi": r["nama"], "pemberi_id": r["id"], "pengerja": self.nama_koord, "pengerja_id": self.koord,
                 "mulai": iso(r["awal"]) if r["awal"] else None, "langkah_terakhir": r["kat"],
                 "langkah_waktu": iso(r["ts"]) if r["ts"] else None,
                 "status": "menunggu" if status == "menunggu" and self.koord_terakhir[2] == kunci else "jalan"}
                for kunci, r in ada.items()]

    def _keadaan(self, t, kerangka):
        """Keadaan yang sama untuk semua penonton: status global, terakhir aktif, tugas terurut, riwayat hari ini."""
        for k in kerangka:
            terakhir = self.tim_terakhir.get(k["pengerja_id"])
            if terakhir:
                k["langkah_terakhir"] = terakhir[1] + (f" · {k['project_nama']}" if k["project"] else "")
                k["langkah_waktu"] = iso(terakhir[0])
        status_koord = self._status_koord(t)
        tugas = kerangka + self._tugas_koord(t, kerangka, status_koord)
        tugas.sort(key=lambda k: (k["status"] != "menunggu", k["mulai"] is None, k["mulai"] or "", k["id"]))
        tugas_agen = {a["id"]: [] for a in self.agen}
        for k in tugas:
            tugas_agen[k["pengerja_id"]].append(k)
        jalan = {p for pr in self.proses for p in pr["profil"]}
        punya_lock = {rec["tl"] for rec in self.lock.values()}
        status = {self.koord: status_koord}
        for a in self.tim:
            status[a] = "jalan" if a in jalan else ("menunggu" if a in punya_lock else "bebas")
        aktif = {a: iso(self.tim_terakhir[a][0]) if a in self.tim_terakhir else None for a in self.tim}
        aktif[self.koord] = iso(self.koord_terakhir[0]) if self.koord_terakhir else None
        awal_hari = t.replace(hour=0, minute=0, second=0, microsecond=0)
        self.ev_log = [e for e in self.ev_log if e.waktu >= awal_hari]
        self.ev_lock = [e for e in self.ev_lock if e.waktu >= awal_hari]
        riwayat = sorted((e for e in self.ev_log + self.ev_lock + self.ev_k3 if e.waktu.date() == t.date()),
                         key=lambda e: (e.waktu, e.seq))
        riwayat = [x for x in map(self._render, riwayat) if x is not None]
        return status, aktif, tugas, tugas_agen, riwayat

    def _berkas(self, p, t, keadaan):
        status, aktif, tugas, tugas_agen, riwayat = keadaan
        if p == self.pemilik:
            tugas_p = tugas
            agen_p = [(status[a["id"]], aktif[a["id"]]) for a in self.agen]
        else:
            tugas_p = []
            for k in tugas:
                if self._pemilik_tugas(k) != p:
                    continue
                if k["pengerja_id"] != self.koord and any(self._pemilik_tugas(x) != p for x in tugas_agen[k["pengerja_id"]]):
                    k = dict(k, langkah_terakhir=None, langkah_waktu=None)  # fail-closed: sid ↔ proses tak bisa dipetakan
                tugas_p.append(k)
            agen_p = []
            for a in (x["id"] for x in self.agen):
                milik = [x for x in tugas_agen[a] if self._pemilik_tugas(x) == p]
                if not milik:
                    agen_p.append(("bebas" if status[a] == "bebas" else "sibuk", None))
                    continue
                st = "menunggu" if any(x["status"] == "menunggu" for x in milik) else "jalan"
                if a == self.koord:
                    ak = iso(self.r[p]["ts"]) if p in self.r else None
                else:
                    ak = aktif[a] if len(milik) == len(tugas_agen[a]) else None
                agen_p.append((st, ak))
            riwayat = [e for e in riwayat if e[3] == p]
        misi_p, ids = self._misi_penonton(p)
        aktif_p = [r for r in misi_p if r["status"] in ("jalan", "menunggu")]
        agen_out = []
        for a, (s, ak) in zip(self.agen, agen_p):
            ma = [r for r in aktif_p if r["pelaksana_id"] == a["id"]]
            ma.sort(key=lambda r: r["nomor"])
            if ma:  # C2 (1) revisi CTO 24 Okt: misi aktif terlihat menentukan keadaan lebih dulu
                kd = "menunggu" if all(r["status"] == "menunggu" for r in ma) else "bekerja"
            elif p != self.pemilik:  # C7: agen tanpa misi V → sibuk/bebas
                kd = "bebas" if s == "bebas" else "sibuk"
            elif s in ("sibuk", "bebas"):  # C2 (2)
                kd = s
            elif s == "menunggu":  # C2 (3)
                kd = "menunggu"
            else:  # C2 (4)
                kd = "bekerja"
            agen_out.append(dict(a, status=s, terakhir_aktif=ak, ruang=self.ruang.get(a["id"], "lain"), keadaan=kd,
                                 misi_aktif=[r["id"] for r in ma]))
        hit = Counter(a["keadaan"] for a in agen_out)
        sub = (None if any(r["subagen"] is None for r in aktif_p)
               else sum(1 for r in aktif_p for x in r["subagen"] if x["selesai"] is None))
        ringkasan = {"agen": {k: hit[k] for k in ("bekerja", "menunggu", "bebas", "sibuk")},
                     "misi": {"aktif": len(aktif_p), "selesai_hari_ini": len(misi_p) - len(aktif_p)}, "subagen_aktif": sub}
        return {"versi_skema": "1", "penonton": p, "pemilik": self.pemilik, "koordinator": self.koord,
                "cakupan": "semua" if p == self.pemilik else "order-sendiri",
                "dibuat_pada": iso(t), "galat": sorted(self.galat), "peringatan": self.peringatan, "orang": self.orang,
                "agen": agen_out,
                "tugas_aktif": [{c: k[c] for c in KUNCI_TUGAS} for k in tugas_p],
                "riwayat_hari_ini": [{"waktu": iso(w), "pelaku": pl, "teks": tx, "misi": mi if mi in ids else None}
                                     for w, pl, tx, _, mi in riwayat[-300:]],
                "ringkasan": ringkasan, "misi": misi_p}

    def _misi_penonton(self, p):
        """C7: pemilik tim semua; V hanya misi pemilik V, rujukan menunggu_misi/induk_misi disaring ke id di berkas V."""
        if p == self.pemilik:
            return self.misi_rec, {r["id"] for r in self.misi_rec}
        milik = [r for r in self.misi_rec if r["pemberi_id"] == p]
        ids = {r["id"] for r in milik}
        return [dict(r, menunggu_misi=[x for x in r["menunggu_misi"] if x in ids],
                     induk_misi=r["induk_misi"] if r["induk_misi"] in ids else None) for r in milik], ids

    def _tulis(self, isi):
        os.makedirs(self.keluaran, mode=0o750, exist_ok=True)
        os.chmod(self.keluaran, 0o750)
        for p, teks in isi.items():
            dst = f"{self.keluaran}/{p}.json"
            tmp = dst + ".tmp"
            fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o640)
            try:
                with os.fdopen(fd, "wb") as f:
                    os.fchmod(f.fileno(), 0o640)
                    f.write(teks.encode("utf-8"))
                os.replace(tmp, dst)
            except BaseException:
                try:
                    os.unlink(tmp)
                except OSError:
                    pass
                raise


class Lapor:
    """Log stdout: ringkasan tiap 60 dtk, perubahan himpunan galat, nama kelas pengecualian. Tanpa isi sumber."""

    def __init__(self, g, jam):
        self.g, self.jam, self.galat = g, jam, frozenset()
        self._jendela()

    def _jendela(self):
        self.t0, self.n, self.ms = self.jam(), 0, 0.0
        self.baru0, self.lewat0 = self.g.baris_baru, self.g.baris_dilewati

    def siklus(self, sekarang):
        t0 = self.jam()
        try:
            self.g.siklus(sekarang)
            ok = True
        except Exception as e:  # hanya nama kelas: pesan/traceback bisa memuat isi atau path
            print(f"siklus gagal: {type(e).__name__}", flush=True)
            ok = False
        self.ms += (self.jam() - t0) * 1000
        self.n += 1
        if self.g.galat != self.galat:
            self.galat = self.g.galat
            print("galat: " + ("; ".join(sorted(self.galat)) or "(tidak ada)"), flush=True)
        if self.jam() - self.t0 >= 60:
            print(f"ringkasan siklus={self.n} baris_baru={self.g.baris_baru - self.baru0} "
                  f"dilewati={self.g.baris_dilewati - self.lewat0} rata_ms={self.ms / self.n:.1f} galat={len(self.galat)}",
                  flush=True)
            self._jendela()
        return ok


def loop(g, interval, berhenti, jam=time.monotonic, tidur=time.sleep):
    lapor = Lapor(g, jam)
    while not berhenti():
        t0 = jam()
        lapor.siklus(datetime.now(WIB))
        sisa = interval - (jam() - t0)
        while sisa > 0 and not berhenti():  # tidur per irisan agar SIGTERM cepat ditanggapi
            d = min(sisa, 0.25)
            tidur(d)
            sisa -= d


def _waktu_arg(s):
    w = parse_waktu(s)
    if w is None:
        raise argparse.ArgumentTypeError(f"bukan waktu ISO 8601: {s!r}")
    return w


def buat_parser():
    akar = Path(__file__).resolve().parent.parent
    p = argparse.ArgumentParser(prog="generator.py", description="Generator ringkasan agent-dashboard (skema 1)")
    p.add_argument("--tim", type=Path, default=None, help="conf/tim.json (bawaan: AD_TIM, lalu <akar>/conf/tim.json)")
    # activity/workspace/proc/profil: bawaan = `sumber.*` di tim.json; argumen menimpa
    p.add_argument("--activity", type=Path, default=None)
    p.add_argument("--workspace", type=Path, default=None)
    p.add_argument("--proc", type=Path, default=None)
    p.add_argument("--proyek", type=Path, default=akar / "conf" / "proyek.json")
    p.add_argument("--profil", type=Path, default=None)
    p.add_argument("--keluaran", type=Path, default=akar / "storage" / "ringkasan")
    p.add_argument("--nomor", type=Path, default=akar / "storage" / "misi" / "nomor.json")  # registri nomor misi (B2)
    p.add_argument("--interval", type=float, default=3.0)
    p.add_argument("--sekali", action="store_true")
    p.add_argument("--sekarang", type=_waktu_arg)
    return p


def tim_dari(arg):
    """Lokasi conf/tim.json: argumen `--tim` > variabel AD_TIM > <akar>/conf/tim.json (KONTRAK §2)."""
    return arg or os.getenv("AD_TIM") or Path(__file__).resolve().parent.parent / "conf" / "tim.json"


def main(argv=None):
    p = buat_parser()
    try:
        a = p.parse_args(argv)
        if a.sekarang is not None and not a.sekali:
            p.error("--sekarang hanya boleh bersama --sekali")
        if not a.interval > 0:
            p.error("--interval harus > 0")
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (0 if e.code is None else 2)
    g = Generator(tim=tim_dari(a.tim), activity=a.activity, workspace=a.workspace, proc=a.proc, proyek=a.proyek,
                  keluaran=a.keluaran, profil=a.profil, nomor=a.nomor)
    print(f"generator mulai interval={a.interval} keluaran={a.keluaran}", flush=True)
    if a.sekali:
        return 0 if Lapor(g, time.monotonic).siklus(a.sekarang or datetime.now(WIB)) else 1
    sinyal = []
    for s in (signal.SIGTERM, signal.SIGINT):
        signal.signal(s, lambda signum, frame: sinyal.append(signum))
    loop(g, a.interval, lambda: bool(sinyal))
    return 0


if __name__ == "__main__":
    sys.exit(main())
