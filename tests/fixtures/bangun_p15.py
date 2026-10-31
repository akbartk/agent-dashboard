#!/usr/bin/env python3
"""Pembangun fixture uji alur tim "P1.5" (31 Okt 2026) -> tests/fixtures/p15/.

Hirarki baru: koordinator (Ajeng) memanggil pengerja langsung; pemegang lock = `tl` (alfa, beta); `gamma` disembunyikan.
Brief TANPA H1 dan tanpa `Peminta`; peluncur menulis handoff/jalan-*.json; riwayat lock, handoff md, verdict QC,
dan dua jsonl guard dibaca generator. Semua data fiktif. Penanda KANARI-… ada di: isi brief (sesudah 300 karakter
pertama), argumen perintah koordinator, field guard selain profil/kategori/keputusan, brief/oleh verdict, isi laporan,
teks pesan sesudah 80 karakter pertama; uji memastikan 0 kemunculan di keluaran. Jalankan ulang: python3 tests/fixtures/bangun_p15.py
"""
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DIR = Path(__file__).resolve().parent / "p15"
sys.path.insert(0, str(DIR.parent))
from tim_dasar import tim_fixture  # noqa: E402
WIB = timezone(timedelta(hours=7))
BTIME = int(datetime(2026, 10, 24, 6, 0, 0, tzinfo=WIB).timestamp())
HERMES = ["/opt/hermes/.venv/bin/python", "-P", "-c",
          "import sys; sys.argv[0]='hermes'; from hermes_cli.main import main; main()"]
PROYEK = {"tahap-satu": "Tahap Satu", "tahap-dua": "Tahap Dua", "tahap-tiga": "Tahap Tiga", "tahap-empat": "Tahap Empat",
          "tahap-lima": "Tahap Lima", "ulang": "Ulang"}
AGEN = {
    "ajeng": {"nama": "Ajeng", "peran": "Koordinator", "induk": ["dicky", "akbar"], "ruang": "koordinasi"},
    "via": {"nama": "Via", "peran": "Riset", "induk": ["ajeng"], "ruang": "riset"},
    "uci": {"nama": "Uci", "peran": "QA/QC", "induk": ["ajeng"], "ruang": "qa"},
    "alfa": {"nama": "Alfa", "peran": "Tech Lead", "induk": ["ajeng"], "ruang": "teknik"},
    "beta": {"nama": "Beta", "peran": "Tech Lead", "induk": ["ajeng"], "ruang": "teknik"},
    "gamma": {"nama": "Gamma", "peran": "Tech Lead", "induk": ["ajeng"], "ruang": "teknik"},
}
# nama berkas -> (project, pelaksana, ekor pembeda sesudah 300 karakter pertama)
BRIEF = {
    "2026-10-31-tahap-satu-a.md": ("tahap-satu", "alfa", ""),
    "2026-10-31-tahap-dua-b.md": ("tahap-dua", "beta", ""),
    "2026-10-31-tahap-tiga-c.md": ("tahap-tiga", "beta", ""),
    "2026-10-31-tahap-empat-d.md": ("tahap-empat", "alfa", ""),
    "2026-10-31-tahap-lima-e.md": ("tahap-lima", "beta", ""),
    "2026-10-31-ulang-f.md": ("ulang", "beta", "versi pertama"),
    "2026-10-31-ulang-f-r2.md": ("ulang", "beta", "versi kedua"),
}
A, B, C, D, E, F, F2 = list(BRIEF)


def isi_brief(nama):
    proj, pel, ekor = BRIEF[nama]
    kepala = (f"Dari: Lala\nUntuk: {pel}\nProject: {proj}\nKunci: tl={pel}\nHandoff: /workspace/handoff/{proj}.md\n"
              + "x" * 200 + "\n")
    isi = "".join(f"Baris isi {i}\n" for i in range(1, 6)) + f"{ekor}\nKANARI-isi-brief\n"
    return kepala + isi


def awal(nama):
    return isi_brief(nama)[:300]


def ts(hms):
    return f"2026-10-31T{hms}"


def iso(hms):
    return f"2026-10-31T{hms}+07:00"


def msg(hms, sid, text, nama="Pak Akbar", profil=None, **ekstra):
    d = {"type": "msg", "role": "owner" if profil is None else "tim", "name": nama, "sid": sid, "text": text, "ts": ts(hms)}
    if profil:
        d["profile"] = profil
    d.update(ekstra)
    return d


def alat(hms, sid, detail="KANARI-detail", nama="Pak Akbar", profil=None, tool="terminal"):
    d = {"type": "tool", "role": "owner" if profil is None else "tim", "name": nama, "sid": sid, "tool": tool,
         "detail": detail, "blocked": False, "ts": ts(hms)}
    if profil:
        d["profile"] = profil
    return d


def balas(hms, sid, nama="Pak Akbar"):
    return {"type": "reply", "role": "owner", "name": nama, "sid": sid, "ts": ts(hms)}


def jalankan(*tugas):
    cmd = "/usr/bin/python3 /opt/data/scripts/tim_jalankan.py --batas-menit 20"
    for kunci, tl, nama in tugas:
        cmd += f" --tugas {kunci} {tl} /workspace/brief/{nama}"
    return cmd + " KANARI-argumen"


def log():
    n = "Mas Dicky"
    return [
        # S1 (akbar): memanggil alfa+beta lewat peluncur; balasan 08:40; semua anak berakhir -> selesai
        msg("08:00:00", "S1", "Tolong jalankan tahap satu dan tahap dua sekarang juga ya, lalu kabari hasilnya. KANARI-teks-lanjut"),
        alat("08:00:05", "S1", jalankan(("tahap-satu", "alfa", A), ("tahap-dua", "beta", B))),
        # pengerja alfa (A: cocok lewat prefix isi), beta (B: prefix isi)
        msg("08:00:15", "A1", awal(A), nama="Alfa", profil="alfa"),
        msg("08:00:30", "B1", awal(B), nama="Beta", profil="beta"),
        alat("08:20:00", "A1", nama="Alfa", profil="alfa", tool="read_file"),
        balas("08:40:00", "S1"),
        # S2 (akbar): memanggil beta untuk C (berjalan, snapshot final=false); sesi diam -> menunggu anak
        msg("08:30:00", "S2", "Lanjutkan tahap tiga untuk saya dan pantau sampai selesai, jangan lupa kabari hasil akhirnya segera. KANARI-teks-lanjut"),
        alat("08:30:02", "S2", jalankan(("tahap-tiga", "beta", C))),
        msg("08:30:10", "C1", awal(C), nama="Beta", profil="beta"),
        alat("08:32:00", "S2"),
        # D: teks pesan tak berguna, hanya cocok lewat jalan-*.json (tugas D, alfa, 08:35:00)
        msg("08:35:03", "D1", "Mulai.", nama="Alfa", profil="alfa"),
        # E: lock tanpa run -> gantung; cocok lewat prefix isi
        msg("08:40:00", "E1", awal(E), nama="Beta", profil="beta"),
        # F: dua brief berawalan sama (r2) -> ambigu, tidak boleh menjadi misi
        msg("08:45:00", "F1", awal(F), nama="Beta", profil="beta"),
        # S3 (dicky): masih aktif, tanpa balasan
        msg("08:55:00", "S3", "Cek status tahap empat dan tahap lima ya.", nama=n),
        alat("08:58:00", "S3", nama=n),
        # S4 pesan sistem saja, S5 hanya baris tool, S7 ditinggalkan (tanpa balasan, lama diam)
        {"type": "msg", "role": "owner", "name": "Pak Akbar", "sid": "S4", "text": "[INTERNAL NOTIFICATION] KANARI-sistem",
         "ts": ts("08:50:00")},
        alat("08:51:00", "S5"),
        msg("06:00:00", "S7", "Pertanyaan lama yang tidak pernah dibalas."), alat("06:05:00", "S7"),
    ]


def main():
    if DIR.exists():
        shutil.rmtree(DIR)

    def tulis(nama, isi):
        p = DIR / nama
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(isi, ensure_ascii=False, indent=1) + "\n" if isinstance(isi, (dict, list)) else isi,
                     encoding="utf-8")

    for p in ("alfa", "beta", "gamma", "via", "uci"):
        tulis(f"profiles/{p}/profile.yaml", f"description: 'Profil fixture {p}.'\n")
    for nama in BRIEF:
        tulis(f"workspace/brief/{nama}", isi_brief(nama))
    tim = tim_fixture(AGEN)
    del tim["cto"]
    tim.update({"tl": ["alfa", "beta"], "sembunyikan": ["gamma"]})
    tim["sumber"].update({"handoff": "workspace/handoff", "verdict": "workspace/verdict",
                          "guard": ["guard/g7-tim-guard.jsonl", "guard/qc-gate-g7.jsonl"]})
    for p in ("alfa", "beta"):  # state.db kosong (tabel sessions saja) dibuat uji dari state/<profil>.sql
        tulis(f"state/{p}.sql", "CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, user_id TEXT, model TEXT, title TEXT,"
              " parent_session_id TEXT, started_at REAL NOT NULL, ended_at REAL, end_reason TEXT);\n")
    tulis("tim.json", tim)
    tulis("proyek.json", PROYEK)
    tulis("activity.jsonl", "".join(json.dumps(b, ensure_ascii=False) + "\n" for b in log()))
    tulis("langkah.json", {"siklus1": "2026-10-31T09:00:00+07:00", "mtime": {}})
    # --- jalan-*.json (peluncur): format baru (final, tandai) dan format lama (tanpa keduanya)
    def run(kunci, tl, nama, mulai, selesai, status, rc, tandai, lap):
        return {"kunci": kunci, "tl": tl, "brief": f"/workspace/brief/{nama}", "pid": 100,
                "laporan": f"/workspace/handoff/{kunci}.laporan-20261031T080000.txt", "mulai": iso(mulai),
                "selesai": iso(selesai) if selesai else None, "durasi_detik": 60.0, "rc": rc, "status": status,
                "tandai": tandai}
    tulis("workspace/handoff/jalan-20261031T080000.json", {
        "versi": 1, "final": True, "mulai": iso("08:00:10"), "selesai": iso("08:20:30"),
        "tugas": [run("tahap-satu", "alfa", A, "08:00:10", "08:20:00", "selesai", 0, "ok", True),
                  run("tahap-dua", "beta", B, "08:00:20", "08:10:00", "gagal", 1, "gagal: kode 1", False)]})
    tulis("workspace/handoff/jalan-20261031T083000.json", {
        "versi": 1, "final": False, "mulai": iso("08:30:05"), "selesai": None,
        "tugas": [run("tahap-tiga", "beta", C, "08:30:05", None, "berjalan", None, None, False),
                  run("tahap-empat", "alfa", D, "08:35:00", "08:38:00", "selesai", 0, "ok", False)]})
    tulis("workspace/handoff/jalan-20261023T100000.json", {  # format lama: tanpa final/tandai
        "versi": 1, "mulai": "2026-10-23T10:00:00+07:00", "selesai": "2026-10-23T10:05:00+07:00",
        "tugas": [{"kunci": "lama", "tl": "alfa", "brief": "/workspace/brief/lama.md", "laporan": "/workspace/handoff/lama.txt",
                   "mulai": "2026-10-23T10:00:00+07:00", "selesai": "2026-10-23T10:05:00+07:00", "durasi_detik": 300.0,
                   "rc": 0, "status": "selesai"}]})
    tulis("workspace/handoff/tahap-satu.laporan-20261031T080000.txt", "KANARI-laporan\n")
    tulis("workspace/handoff/tahap-satu.md",
          "# Handoff tahap-satu\n\n### 2026-10-31 07:00 WIB — alfa — Status: mulai\nKANARI-lama\n"
          "### 2026-10-31 08:01 WIB — alfa — Status: mulai\nKANARI-handoff\n"
          "### 2026-10-31 08:10 WIB — alfa — Status: keputusan\nKANARI-handoff\n"
          "### 2026-10-31 08:12 WIB — beta — Status: langkah\nKANARI-lain\n"
          "### 2026-10-31 08:19 WIB — alfa — Status: selesai\nKANARI-handoff\n")
    # --- lock: D (review: run selesai tapi lock ada), C (jalan), E (gantung)
    for kunci, tl, nama, mulai in (("tahap-empat", "alfa", D, "08:35:00"), ("tahap-tiga", "beta", C, "08:30:05"),
                                   ("tahap-lima", "beta", E, "08:39:00")):
        tulis(f"workspace/locks/{kunci}.lock", f"tl={tl}\nmulai={iso(mulai)}\nbrief=/workspace/brief/{nama}\noleh=ajeng KANARI-oleh\n")
    rw = [{"ts": iso("08:00:05"), "perintah": "kunci", "kunci": "tahap-satu", "tl": "alfa", "oleh": "ajeng", "pid": 1},
          {"ts": iso("08:19:55"), "perintah": "selesai", "kunci": "tahap-satu", "tl": "alfa", "oleh": "alfa", "pid": 2, "rc": 0},
          {"ts": iso("08:20:10"), "perintah": "lepas", "kunci": "tahap-satu", "tl": "alfa", "oleh": "ajeng", "pid": 3},
          {"ts": iso("08:35:00"), "perintah": "kunci", "kunci": "tahap-empat", "tl": "alfa", "oleh": "ajeng", "pid": 4},
          {"ts": iso("08:50:00"), "perintah": "alihkan", "kunci": "tahap-lima/sub", "tl": "alfa", "oleh": "ajeng", "pid": 5},
          {"ts": "2026-10-30T10:00:00+07:00", "perintah": "kunci", "kunci": "kemarin", "tl": "alfa", "oleh": "ajeng", "pid": 6}]
    tulis("workspace/locks/.tim_kunci.riwayat.jsonl", "".join(json.dumps(x) + "\n" for x in rw))
    # --- verdict QC: tertaut ke tahap-satu; ambigu (dua kunci); tak tertaut
    tulis("workspace/verdict/20261031-0845-tahap-satu-a.json",
          {"verdict": "LULUS BERSYARAT", "dibuat": iso("08:45:00"), "brief": "KANARI-brief-qc", "oleh": "uci"})
    tulis("workspace/verdict/20261031-0850-tahap-dua-b-tahap-tiga-c.json",
          {"verdict": "GAGAL", "dibuat": iso("08:50:00"), "brief": "KANARI-brief-qc", "oleh": "uci"})
    tulis("workspace/verdict/20261031-0852-tidak-terkait.json",
          {"verdict": "LULUS", "dibuat": iso("08:52:00"), "brief": "KANARI-brief-qc", "oleh": "uci"})
    tulis("guard/g7-tim-guard.jsonl", "".join(json.dumps(x) + "\n" for x in [
        {"ts": iso("08:15:00"), "profile": "alfa", "sid": "A1", "tool": "terminal", "kategori": "rahasia", "keputusan": "blok",
         "isi_panjang": 10, "isi_sha256": "KANARI-hash", "perintah": "KANARI-argumen-guard"},
        {"ts": iso("08:16:00"), "profile": "alfa", "sid": "A1", "tool": "terminal", "kategori": "KANARI kategori tidak aman!!",
         "keputusan": "blok"},
        {"ts": iso("08:17:00"), "profile": "alfa", "sid": "A1", "tool": "terminal", "kategori": "ok", "keputusan": "izin"}]))
    tulis("guard/qc-gate-g7.jsonl", "".join(json.dumps(x) + "\n" for x in [
        {"ts": iso("08:48:00"), "profile": "uci", "sid": "U1", "tool": "terminal", "jenis": "hermes-container",
         "keputusan": "blok", "alasan": "KANARI-alasan", "verdict": None}]))
    tulis("proc/stat", f"cpu  1 2 3 4\nbtime {BTIME}\nprocesses 9\n")
    pid = 4001
    d = DIR / "proc" / str(pid)
    d.mkdir(parents=True)
    argv = HERMES + ["-p", "beta", "-z", isi_brief(C)]
    (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    ticks = (int(datetime.fromisoformat(iso("08:30:06")).timestamp()) - BTIME) * 100
    sisa = ["S", "1", str(pid), str(pid), "0", "-1", "4194560"] + ["0"] * 12 + [str(ticks)] + ["0"] * 6
    (d / "stat").write_text(f"{pid} (python) " + " ".join(sisa) + "\n")


if __name__ == "__main__":
    main()
