#!/usr/bin/env python3
"""Pembangun fixture uji misi "Kantor Agen" (TL Beta, 24 Okt 2026) → tests/fixtures/misi1/.

Kontrak: /workspace/agent-dashboard/kantor-agen/KONTRAK-kantor-agen.md bagian B/C, docs/misi.md.
Semua data fiktif. Isi `text` (sesudah baris 1), `detail`, sid, argv di luar header, isi brief di luar header, `oleh=`,
kolom state.db selain 4 kolom yang boleh dibaca, dan isi laporan memuat penanda KANARI-…; uji memastikan 0 kemunculan.
Judul brief memuat kanari pemilik (Kanari-Akbar-*, Kanari-Jati-*, Kanari-Dicky-*) untuk uji isolasi per penonton.
state.db TIDAK disimpan di fixture: uji membuatnya di TMPDIR dari `state/<profil>.sql`. mtime laporan diatur uji dari
`langkah.json` (copytree tidak menjamin mtime). Jalankan ulang: python3 tests/fixtures/bangun_misi1.py
"""
import json
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DIR = Path(__file__).resolve().parent / "misi1"
sys.path.insert(0, str(DIR.parent))
from tim_dasar import tim_fixture  # noqa: E402
WIB = timezone(timedelta(hours=7))
BTIME = int(datetime(2026, 10, 24, 6, 0, 0, tzinfo=WIB).timestamp())
CLK = 100
HERMES = ["/opt/hermes/.venv/bin/python", "-P", "-c",
          "import sys; sys.argv[0]='hermes'; from hermes_cli.main import main; main()"]
PROFIL = ("alfa", "beta", "carli", "desy", "uci", "via")
PROYEK = {"agent-dashboard": "Agent Dashboard", "searchenginebsk": "Search Engine BSK", "policytrack": "PolicyTrack",
          "pemahaman-asn": "Pemahaman ASN", "pemahaman": "Pemahaman", "ilk": "ILK"}
AGEN = {
    "ajeng": {"nama": "Ajeng", "peran": "Koordinator", "induk": ["dicky", "jati"], "ruang": "koordinasi"},
    "desy": {"nama": "Desy", "peran": "CTO", "induk": ["ajeng"], "ruang": "teknik"},
    "via": {"nama": "Via", "peran": "Riset dan peraturan", "induk": ["ajeng"], "ruang": "riset"},
    "uci": {"nama": "Uci", "peran": "QA/QC", "induk": ["ajeng"], "ruang": "qa"},
    "alfa": {"nama": "Alfa", "peran": "Tech Lead", "induk": ["desy"], "ruang": "teknik"},
    "beta": {"nama": "Beta", "peran": "Tech Lead", "induk": ["desy"], "ruang": "teknik"},
    "carli": {"nama": "Carli", "peran": "Tech Lead", "induk": ["desy"], "ruang": "teknik"},
}


def w(hms, tanggal="2026-10-24"):
    return datetime.fromisoformat(f"{tanggal}T{hms}+07:00")


def ts(hms, tanggal="2026-10-24"):
    return f"{tanggal}T{hms}"


def epoch(hms, tanggal="2026-10-24"):
    return w(hms, tanggal).timestamp()


BRIEF = {
    # nama berkas: (H1, baris tengah, baris Peminta)
    "2026-10-23-beta-ilk-kemarin.md": ("# Brief TL — ilk — 2026-10-23 — Misi kemarin Kanari-Akbar-Opal",
                                       "Dari: Desy (CTO). Untuk: Beta.", "Peminta asal: Pak Akbar lewat Ajeng."),
    "2026-10-24-desy-induk.md": ("# Brief CTO — 2026-10-24 — Induk Kanari-Akbar-Safir",
                                 "Dari: Ajeng. Untuk: Desy.", "Peminta asal: Pak Akbar lewat Ajeng."),
    "2026-10-24-beta-agent-dashboard-generator.md": (
        "# Brief TL — agent-dashboard — 2026-10-24 — Generator Kanari-Akbar-Berlian (Beta)",
        "Dari: Desy (CTO). Untuk: Beta.", "Peminta asal: Pak Akbar lewat Ajeng."),
    "2026-10-24-alfa-searchenginebsk-zamrud.md": (
        "# Brief TL — searchenginebsk — 2026-10-24 — Audit Kanari-Jati-Zamrud",
        "Dari: Desy (CTO). Untuk: Alfa.", "Peminta asal: Mas Jati lewat Ajeng."),
    "2026-10-24-carli-policytrack-rubi.md": ("# Brief TL — policytrack — 2026-10-24 — Rapikan Kanari-Dicky-Rubi",
                                             "Dari: Desy (CTO). Untuk: Carli.", "Peminta asal: Mas Dicky lewat Ajeng."),
    "2026-10-24-via-pemahaman-asn-mutiara.md": ("# Brief Riset — 2026-10-24 — Kajian Kanari-Akbar-Mutiara",
                                                "Dari: Ajeng. Untuk: Via.", "Peminta asal: Pak Akbar lewat Ajeng."),
    "2026-10-24-uci-jati-intan.md": ("# Brief QA — 2026-10-24 — Uji Kanari-Jati-Intan",
                                     "Dari: Ajeng. Untuk: Uci.", "Peminta asal: Mas Jati lewat Ajeng."),
    # H1 ganda: tidak pernah menjadi misi
    "2026-10-24-desy-ganda-1.md": ("# Brief CTO — 2026-10-24 — Ganda Kanari-Akbar-Kuarsa",
                                   "Dari: Ajeng.", "Peminta asal: Pak Akbar lewat Ajeng."),
    "2026-10-24-desy-ganda-2.md": ("# Brief CTO — 2026-10-24 — Ganda Kanari-Akbar-Kuarsa",
                                   "Dari: Ajeng. (salinan)", "Peminta asal: Pak Akbar lewat Ajeng."),
}
BRIEF_BUKAN_H1 = ("Brief tanpa H1 Kanari-Akbar-Batu", "Peminta asal: Pak Akbar lewat Ajeng.")
NAMA = {"G": "2026-10-23-beta-ilk-kemarin.md", "A": "2026-10-24-desy-induk.md",
        "B": "2026-10-24-beta-agent-dashboard-generator.md", "C": "2026-10-24-alfa-searchenginebsk-zamrud.md",
        "D": "2026-10-24-carli-policytrack-rubi.md", "E": "2026-10-24-via-pemahaman-asn-mutiara.md",
        "F": "2026-10-24-uci-jati-intan.md", "H": "2026-10-24-desy-ganda-1.md"}


def isi_brief(nama):
    h1, tengah, peminta = BRIEF[nama]
    return f"{h1}\n{tengah}\n{peminta}\nProject: KANARI-ISI-{nama[:10]}.\n\nIsi KANARI-ISI: ssh bskdev-host lalu kerjakan.\n"


def header(nama):
    h1, tengah, peminta = BRIEF[nama]
    return [h1, tengah, peminta]


def msg(hms, profil, sid, baris1, tanggal="2026-10-24", **ekstra):
    d = {"type": "msg", "role": "tim", "name": profil.capitalize(), "profile": profil, "sid": sid,
         "text": baris1 + "\nKANARI-teks lanjutan pesan", "ts": ts(hms, tanggal)}
    d.update(ekstra)
    return d


def tool(hms, profil, sid, nama_tool, detail="KANARI-detail", tanggal="2026-10-24"):
    return {"type": "tool", "role": "tim", "name": profil.capitalize(), "profile": profil, "sid": sid,
            "tool": nama_tool, "detail": detail, "blocked": False, "ts": ts(hms, tanggal)}


CATAT = "mcp__obsidian_bsk__catat_progres"


def catat(hms, profil, sid, status_teks, tanggal="2026-10-24"):
    det = json.dumps({"project": "agent-dashboard", "oleh": "KANARI-oleh",
                      "entri": f"{status_teks}\n**Yang dikerjakan:** KANARI-entri"}, ensure_ascii=False)
    return tool(hms, profil, sid, CATAT, det, tanggal)


def h1(k):
    return BRIEF[NAMA[k]][0]


def log():
    b = []
    # T-001: misi kemarin (selesai kemarin → tidak dimuat)
    b.append(msg("15:00:00", "beta", "KANARI-SID-G", h1("G"), tanggal="2026-10-23"))
    b.append(catat("15:10:00", "beta", "KANARI-SID-G", "**Status:** selesai", tanggal="2026-10-23"))
    # Ajeng menerima order (baris Ajeng yang text-nya = H1 tidak pernah menjadi misi)
    b.append({"type": "msg", "role": "owner", "name": "Pak Akbar", "text": h1("F") + "\nKANARI-teks", "ts": ts("09:55:00")})
    # T-002: Desy (induk)
    b.append(msg("10:00:00", "desy", "KANARI-SID-A", h1("A")))
    b.append(tool("10:01:00", "desy", "KANARI-SID-A", "read_file"))
    b.append(catat("10:02:00", "desy", "KANARI-SID-A", "Status: mulai"))
    b.append(tool("10:04:00", "desy", "KANARI-SID-A", "terminal", "KANARI-detail hermes -p beta -z brief"))
    # T-003: Beta sesi pertama
    b.append(msg("10:06:00", "beta", "KANARI-SID-B1", h1("B")))
    b.append(catat("10:07:00", "beta", "KANARI-SID-B1", "**Status:** mulai"))
    # sub-agen Beta ke-1 (sid ada di state.db beta, parent = sesi utama B1)
    b.append(msg("10:20:05", "beta", "KANARI-SUB-1", "KANARI-tugas sub-agen", sub=True))
    b.append(catat("10:25:00", "beta", "KANARI-SUB-1", "**Status:** selesai"))  # bukan langkah misi (bukan sesi utama)
    # T-004: Alfa (jati), sudah lapor → menunggu review
    b.append(msg("10:11:00", "alfa", "KANARI-SID-C", h1("C")))
    b.append(catat("10:40:00", "alfa", "KANARI-SID-C", "**Status:** selesai"))
    # T-005: Carli (dicky), tanpa proses + tanpa laporan → gantung
    b.append(msg("10:15:00", "carli", "KANARI-SID-D", h1("D")))
    b.append(tool("10:16:00", "carli", "KANARI-SID-D", "read_file"))
    # sesi sub-agen ber-sub:true yang text-nya = H1 → bukan misi
    b.append(msg("10:17:00", "carli", "KANARI-SID-SUBH", h1("D"), sub=True))
    # T-006: Via, selesai (laporan 10:45)
    b.append(msg("10:20:00", "via", "KANARI-SID-E", h1("E")))
    b.append(catat("10:44:00", "via", "KANARI-SID-E", "Status — selesai"))
    # T-007: Uci (jati), berakhir tanpa laporan (baris terakhir 10:35:30)
    b.append(msg("10:30:00", "uci", "KANARI-SID-F", h1("F")))
    b.append(tool("10:35:30", "uci", "KANARI-SID-F", "write_file"))
    # langkah Beta B1
    b.append(catat("10:30:00", "beta", "KANARI-SID-B1", "status:   langkah"))
    b.append(catat("10:50:00", "beta", "KANARI-SID-B1", "Status — HAMBATAN"))
    # H1 ganda → bukan misi ("Desy mulai bekerja")
    b.append(msg("10:52:00", "desy", "KANARI-SID-H", h1("H")))
    # text beda satu karakter → bukan misi
    b.append(msg("10:53:00", "desy", "KANARI-SID-J", h1("A") + " (salinan)"))
    # sid kosong → bukan misi
    b.append(msg("10:54:00", "alfa", "", h1("C")))
    # T-003: Beta sesi kedua (melanjutkan)
    b.append(msg("11:00:00", "beta", "KANARI-SID-B2", h1("B")))
    b.append(catat("11:01:00", "beta", "KANARI-SID-B2", "Tanpa penanda KANARI"))
    b.append(catat("11:05:00", "beta", "KANARI-SID-B2", "Status: dikerjakan"))
    b.append(msg("11:10:05", "beta", "KANARI-SUB-2", "KANARI-tugas sub-agen 2", sub=True))
    b.append(tool("11:12:00", "beta", "KANARI-SUB-2", "read_file"))
    b.append(tool("11:20:00", "beta", "KANARI-SID-B2", "terminal", "ssh -F x bskdev-host 'KANARI-detail'"))
    # baris 1 text ber-spasi di tepi = H1 sesudah strip → sesi kedua misi E ("Via melanjutkan")
    b.append(msg("10:43:00", "via", "KANARI-SID-E2", "  " + h1("E") + "  "))
    # brief yang baris 1-nya bukan H1 tidak pernah menjadi misi
    b.append(msg("10:55:00", "via", "KANARI-SID-K", BRIEF_BUKAN_H1[0]))
    b.sort(key=lambda d: d["ts"])  # urutan berkas = urutan waktu (seperti log asli)
    return b


def tambahan():
    """Baris yang ditambahkan uji sesudah siklus 1 (mode live)."""
    return [msg("11:31:00", "alfa", "KANARI-SID-C2", h1("C")),
            catat("11:32:00", "alfa", "KANARI-SID-C2", "**Status:** antre")]


def proc_entri(akar, pid, argv, ppid, mulai_hms, comm="python"):
    d = akar / "proc" / str(pid)
    d.mkdir(parents=True)
    (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    ticks = (int(w(mulai_hms).timestamp()) - BTIME) * CLK
    sisa = ["S", str(ppid), str(pid), str(pid), "0", "-1", "4194560"] + ["0"] * 12 + [str(ticks)] + ["0"] * 6
    (d / "stat").write_text(f"{pid} ({comm}) " + " ".join(sisa) + "\n")


SQL = {
    "beta": [("KANARI-SID-G", "cli", None, epoch("15:00:00", "2026-10-23"), epoch("15:20:00", "2026-10-23")),
             ("KANARI-SID-B1", "cli", None, epoch("10:06:00"), epoch("10:58:00")),
             ("KANARI-SUB-1", "subagent", "KANARI-SID-B1", epoch("10:20:00"), epoch("10:40:00")),
             ("KANARI-KOMPRESI", "cli", "KANARI-SID-B1", epoch("10:45:00"), None),  # lanjutan kompresi: bukan sub-agen
             ("KANARI-SID-B2", "cli", None, epoch("11:00:00"), None),
             ("KANARI-SUB-2", "subagent", "KANARI-SID-B2", epoch("11:10:00"), None),
             ("KANARI-SUB-LAIN", "subagent", "KANARI-SID-LAIN", epoch("11:15:00"), None)],
    "desy": [("KANARI-SID-A", "cli", None, epoch("10:00:00"), None)],
    "alfa": [("KANARI-SID-C", "cli", None, epoch("10:11:00"), epoch("10:41:00"))],
    "carli": [("KANARI-SID-D", "cli", None, epoch("10:15:00"), epoch("10:16:30"))],
    "via": [("KANARI-SID-E", "cli", None, epoch("10:20:00"), epoch("10:44:30")),
            ("KANARI-SUB-E", "subagent", "KANARI-SID-E", epoch("10:21:00"), epoch("10:22:00"))],
    "uci": [("KANARI-SID-F", "cli", None, epoch("10:30:00"), epoch("10:35:40"))],
}
CONFIG = {
    "alfa": "model: x\ndelegation:\n  oneshot_max_children: 10\n",
    "beta": ("model: x  # KANARI-komentar\ndelegation:\n  # oneshot_max_children: 99\n  max_spawn_depth: 1\n"
             "  oneshot_max_children: 10  # batas\nterminal:\n  oneshot_max_children: 77\n"),
    "carli": "model: x\nterminal:\n  oneshot_max_children: 77\n",  # tanpa delegation → spawn_kuota null
    "desy": "delegation:\n    oneshot_max_children: 10\n",
    "uci": "delegation:\n  oneshot_max_children: 5\n",
    "via": "delegation:\n  oneshot_max_children: 10\n",
}


def tulis(akar, nama, isi):
    p = akar / nama
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(isi, (dict, list)):
        isi = json.dumps(isi, ensure_ascii=False, indent=1) + "\n"
    p.write_text(isi, encoding="utf-8")


def main():
    if DIR.exists():
        shutil.rmtree(DIR)
    akar = DIR
    for p in PROFIL:
        tulis(akar, f"profiles/{p}/profile.yaml", f"description: 'Profil fixture {p}.'\n")
        tulis(akar, f"profiles/{p}/config.yaml", CONFIG[p])
    for nama in BRIEF:
        tulis(akar, f"workspace/brief/{nama}", isi_brief(nama))
    tulis(akar, "workspace/brief/2026-10-24-via-bukan-h1.md", "\n".join(BRIEF_BUKAN_H1) + "\nKANARI-ISI\n")
    # laporan: review (C), selesai (E), kemarin (G); laporan kosong untuk D (gantung tetap)
    tulis(akar, "workspace/brief/2026-10-24-alfa-searchenginebsk-zamrud.laporan.txt", "KANARI-laporan C\n")
    tulis(akar, "workspace/brief/2026-10-24-via-pemahaman-asn-mutiara.laporan.txt", "KANARI-laporan E\n")
    tulis(akar, "workspace/brief/2026-10-23-beta-ilk-kemarin.laporan.txt", "KANARI-laporan G\n")
    tulis(akar, "workspace/brief/2026-10-24-carli-policytrack-rubi.laporan.txt", "")
    tulis(akar, "workspace/locks/agent-dashboard.lock",
          "tl=beta\nmulai=2026-10-24T10:05:00+07:00\nbrief=/workspace/brief/" + NAMA["B"] + "\noleh=desy KANARI-OLEH\n")
    tulis(akar, "workspace/locks/searchenginebsk.lock",
          "tl=alfa\nmulai=2026-10-24T10:10:00+07:00\nbrief=/workspace/brief/" + NAMA["C"] + "\noleh=desy KANARI-OLEH\n")
    tulis(akar, "workspace/locks/policytrack.lock",
          "tl=carli\nmulai=2026-10-24T10:14:00+07:00\nbrief=/workspace/brief/" + NAMA["D"] + "\noleh=desy KANARI-OLEH\n")
    tulis(akar, "proc/stat", f"cpu  1 2 3 4\nbtime {BTIME}\nprocesses 9\n")
    proc_entri(akar, 2001, HERMES + ["gateway", "run", "KANARI-argv"], 1, "08:00:00")          # Ajeng (tanpa -p)
    proc_entri(akar, 3001, HERMES + ["-p", "desy", "-z", isi_brief(NAMA["A"])], 2001, "09:59:50")
    proc_entri(akar, 3050, ["/bin/bash", "-c", "KANARI-argv hermes -p beta"], 3001, "10:05:30", comm="bash")
    proc_entri(akar, 3101, HERMES + ["-p", "beta", "-z", isi_brief(NAMA["B"])], 3050, "10:05:50")
    proc_entri(akar, 3201, HERMES + ["-p", "carli", "-z", "# Brief lain\nPeminta asal: Pak Akbar\nKANARI-z"], 1, "11:00:00")
    for p, baris in SQL.items():
        sql = ["CREATE TABLE sessions (id TEXT PRIMARY KEY, source TEXT, user_id TEXT, model TEXT, title TEXT,",
               "  parent_session_id TEXT, started_at REAL NOT NULL, ended_at REAL, end_reason TEXT);"]
        for sid, src, par, mulai, akhir in baris:
            nilai = ", ".join(["'" + sid + "'", "'" + src + "'", "'KANARI-user'", "'KANARI-model'", "'KANARI-judul'",
                               "NULL" if par is None else "'" + par + "'", repr(mulai),
                               "NULL" if akhir is None else repr(akhir), "'KANARI-alasan'"])
            sql.append(f"INSERT INTO sessions VALUES ({nilai});")
        tulis(akar, f"state/{p}.sql", "\n".join(sql) + "\n")
    tulis(akar, "proyek.json", PROYEK)
    tulis(akar, "tim.json", tim_fixture(AGEN))
    tulis(akar, "activity.jsonl", "".join(json.dumps(b, ensure_ascii=False) + "\n" for b in log()))
    tulis(akar, "tambahan.jsonl", "".join(json.dumps(b, ensure_ascii=False) + "\n" for b in tambahan()))
    tulis(akar, "langkah.json", {
        "siklus1": "2026-10-24T11:30:00+07:00", "siklus2": "2026-10-24T11:33:00+07:00",
        "mtime": {"workspace/brief/2026-10-24-alfa-searchenginebsk-zamrud.laporan.txt": "2026-10-24T10:42:00+07:00",
                  "workspace/brief/2026-10-24-via-pemahaman-asn-mutiara.laporan.txt": "2026-10-24T10:45:00+07:00",
                  "workspace/brief/2026-10-23-beta-ilk-kemarin.laporan.txt": "2026-10-23T16:00:00+07:00",
                  "workspace/brief/2026-10-24-carli-policytrack-rubi.laporan.txt": "2026-10-24T10:16:00+07:00"},
    })


if __name__ == "__main__":
    main()
