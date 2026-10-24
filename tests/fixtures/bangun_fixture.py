#!/usr/bin/env python3
"""Pembangun fixture uji kontrak generator agent-dashboard (TL Beta, 16 Okt 2026).

Menulis tests/fixtures/skenario{1,2}/ : activity.jsonl (+ tambahan/pengganti), workspace/{locks,brief}, proc/,
proyek.json, langkah.json, dan harapan/{akbar,dicky,jati}.json (ringkasan yang WAJIB dihasilkan generator).
Semua data fiktif. Setiap isi `text`/`detail`/sid/argv di luar header/isi brief di luar header/`oleh=` memuat
penanda KANARI-…; uji kontrak memastikan 0 kemunculan "KANARI" di keluaran. Jalankan ulang: python3 bangun_fixture.py
"""
import json
import os
import shutil
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(DIR))
from tim_dasar import AGEN_SUMBER, tim_fixture  # noqa: E402
WIB = timezone(timedelta(hours=7))
BTIME = int(datetime(2026, 10, 16, 6, 0, 0, tzinfo=WIB).timestamp())
CLK = 100
HERMES = ["/opt/hermes/.venv/bin/python", "-P", "-c",
          "import sys; sys.argv[0]='hermes'; from hermes_cli.main import main; main()"]
PROYEK = {"searchenginebsk": "Search Engine BSK", "policytrack": "PolicyTrack", "absensimeeting": "Absensi Meeting",
          "jdih-v3": "JDIH", "ebook-v2": "eBook", "pemahaman-asn": "Pemahaman ASN", "survei3as": "Survei 3AS"}
ORANG = [{"id": "akbar", "nama": "Pak Akbar", "peran": "Pemilik tim", "induk": []},
         {"id": "dicky", "nama": "Mas Dicky", "peran": "Pemberi order", "induk": ["akbar"]},
         {"id": "jati", "nama": "Mas Jati", "peran": "Pemberi order", "induk": ["akbar"]}]
AGEN = [("ajeng", "Ajeng", "Koordinator", ["dicky", "jati"], "koordinasi"), ("desy", "Desy", "CTO", ["ajeng"], "teknik"),
        ("via", "Via", "Riset dan peraturan", ["ajeng"], "riset"), ("alfa", "Alfa", "Tech Lead", ["desy"], "teknik"),
        ("beta", "Beta", "Tech Lead", ["desy"], "teknik"), ("carli", "Carli", "Tech Lead", ["desy"], "teknik")]
PROFIL = ("alfa", "beta", "carli", "desy", "via")  # folder profil fixture (5 profil lama, tanpa uci); atribut dari tim.json fixture


def t(hms, tanggal="2026-10-16"):
    return f"{tanggal}T{hms}+07:00"


def ajeng(ts, jenis, nama, isi, tool=None, role=None):
    role = role or {"Pak Akbar": "owner", "Mas Dicky": "operator", "Mas Jati": "operator"}.get(nama, "bot")
    if jenis == "msg":
        return {"type": "msg", "role": role, "name": nama, "text": isi, "ts": ts}
    return {"type": "tool", "role": role, "name": nama, "tool": tool, "detail": isi, "blocked": False, "ts": ts}


def tim(ts, profil, sid, jenis, isi, tool=None):
    d = {"role": "tim", "name": profil.capitalize(), "profile": profil, "sid": sid}
    if jenis == "msg":
        d.update(type="msg", text=isi)
    else:
        d.update(type="tool", tool=tool, detail=isi, blocked=False)
    d["ts"] = ts
    return d


def jsonl(baris):
    return "".join((b if isinstance(b, str) else json.dumps(b, ensure_ascii=False)) + "\n" for b in baris)


def proses(akar, pid, argv, mulai_hms, comm="python"):
    d = akar / "proc" / str(pid)
    d.mkdir(parents=True)
    (d / "cmdline").write_bytes(b"\0".join(a.encode() for a in argv) + b"\0")
    mulai = int(datetime.fromisoformat(t(mulai_hms)).timestamp())
    ticks = (mulai - BTIME) * CLK
    sisa = ["S", "1", str(pid), str(pid), "0", "-1", "4194560"] + ["0"] * 12 + [str(ticks)] + ["0"] * 6
    (d / "stat").write_text(f"{pid} ({comm}) " + " ".join(sisa) + "\n")


def tugas(id, judul, project, pemberi, pengerja, mulai, langkah, waktu, status):
    pid = {"Pak Akbar": "akbar", "Mas Dicky": "dicky", "Mas Jati": "jati"}.get(pemberi)
    return {"id": id, "judul": judul, "project": project, "project_nama": PROYEK.get(project) if project else None,
            "pemberi": pemberi, "pemberi_id": pid, "pengerja": pengerja, "pengerja_id": pengerja.lower(),
            "mulai": mulai, "langkah_terakhir": langkah, "langkah_waktu": waktu, "status": status}


def ringkasan(penonton, status, aktif, tugas_aktif, riwayat):
    # field tambahan Kantor Agen (A1, 24 Okt 2026): skenario ini tanpa misi → misi [], misi_aktif [], riwayat misi null;
    # keadaan C2 (akbar: jalan→bekerja) / C7 (dicky, jati: agen tanpa misi V → bebas bila status bebas, else sibuk)
    def keadaan(s):
        if penonton != "akbar":
            return "bebas" if s == "bebas" else "sibuk"
        return {"jalan": "bekerja"}.get(s, s)
    agen = [{"id": i, "nama": n, "peran": p, "induk": ind, "status": status[i], "terakhir_aktif": aktif.get(i), "ruang": r,
             "keadaan": keadaan(status[i]), "misi_aktif": []}
            for i, n, p, ind, r in AGEN]
    hit = {k: sum(1 for a in agen if a["keadaan"] == k) for k in ("bekerja", "menunggu", "bebas", "sibuk")}
    return {"versi_skema": "1", "penonton": penonton, "pemilik": "akbar", "koordinator": "ajeng", "cakupan": "semua" if penonton == "akbar" else "order-sendiri",
            "dibuat_pada": t("15:00:00"), "galat": [], "peringatan": [], "orang": ORANG, "agen": agen, "tugas_aktif": tugas_aktif,
            "riwayat_hari_ini": [{"waktu": w, "pelaku": p, "teks": x, "misi": None} for w, p, x in riwayat],
            "ringkasan": {"agen": hit, "misi": {"aktif": 0, "selesai_hari_ini": 0}, "subagen_aktif": 0}, "misi": []}


def tulis(akar, nama, isi):
    p = akar / nama
    p.parent.mkdir(parents=True, exist_ok=True)
    if isinstance(isi, (dict, list)):
        isi = json.dumps(isi, ensure_ascii=False, indent=1) + "\n"
    p.write_text(isi, encoding="utf-8")


def profil(akar):
    for i in PROFIL:
        tulis(akar, f"profiles/{i}/profile.yaml", f"description: 'Profil fixture {i}.'\ndescription_auto: false\n")


def skenario1():
    akar = DIR / "skenario1"
    brief = {
        "2026-10-16-alfa-searchenginebsk.md": "# Brief TL — searchenginebsk — 2026-10-16 — Audit indeks campuran\n"
            "Dari: Desy (CTO). Untuk: Alfa. KANARI-HA\nPeminta asal: Pak Akbar lewat Ajeng, 16 Okt 2026.\n"
            "Project: searchenginebsk.\n\nIsi KANARI-A1: ssh bskdev-host lalu cek indeks.\n",
        "2026-10-15-beta-policytrack.md": "# Brief TL — policytrack — perbaikan statistik\nDari: Desy (CTO). KANARI-HB\n"
            "Peminta asal: Pak Akbar dan Mas Dicky lewat Ajeng.\n\nKANARI-B1 isi brief.\n",
        "2026-10-16-carli-absensimeeting.md": "# Brief TL — absensimeeting — 2026-10-16 — Rekap kehadiran ke Excel\n"
            "Dari: Desy (CTO). Untuk: Carli.\n**Peminta:** Mas Jati (operator)\n\n"
            "KANARI-C1 kontak 081234567890 surel orang@contoh.go.id\n",
        "2026-10-16-beta-jdih.md": "# Brief TL — jdih-v3 — 2026-10-16 — Periksa tautan unduhan\nDari: Desy (CTO).\n"
            "Peminta asal: Mas Dicky lewat Ajeng\n\nKANARI-D1\n",
        "2026-10-16-desy-dicky.md": "# Brief untuk Desy (CTO) — Perbaikan urutan hasil pencarian\nDari: Ajeng. KANARI-HE\n"
            "**Peminta:** Mas Dicky (operator), 16 Okt 14.38\n\nKANARI-E1 isi panjang brief Desy.\n",
        "2026-10-16-via-jati.md": "# Brief untuk Via — Ringkasan regulasi tanda tangan elektronik\nDari: Ajeng.\n"
            "**Peminta:** Mas Jati (operator)\n\nKANARI-F1\n",
        "2026-10-16-desy-ganda-1.md": "# Brief untuk Desy (CTO) — Tugas ganda\nDari: Ajeng.\n**Peminta:** Mas Jati (operator)\n\nKANARI-G1\n",
        "2026-10-16-desy-ganda-2.md": "# Brief untuk Desy (CTO) — Tugas ganda\nDari: Ajeng.\n**Peminta:** Mas Jati (operator)\n\nKANARI-G2\n",
    }
    for n, isi in brief.items():
        tulis(akar, f"workspace/brief/{n}", isi)
    lock = {
        "searchenginebsk": ("alfa", "2026-10-16T13:00:00+07:00", "2026-10-16-alfa-searchenginebsk.md", "desy KANARI-LA"),
        "policytrack": ("beta", "2026-10-15T21:40:00+07:00", "2026-10-15-beta-policytrack.md", "desy"),
        "absensimeeting": ("carli", "2026-10-16T14:05:00+07:00", "2026-10-16-carli-absensimeeting.md", "desy"),
        "jdih-v3": ("beta", "2026-10-16T09:00:00+07:00", "2026-10-16-beta-jdih.md", "desy"),
    }
    for slug, (tl, mulai, b, oleh) in lock.items():
        tulis(akar, f"workspace/locks/{slug}.lock", f"tl={tl}\nmulai={mulai}\nbrief=/workspace/brief/{b}\noleh={oleh}\n")
    tulis(akar, "workspace/locks/.koordinasi.lock.999", "tl=alfa\nmulai=2026-10-16T08:00:00+07:00\nbrief=KANARI-TMP\n")
    tulis(akar, "proc/stat", f"cpu  1 2 3 4\nbtime {BTIME}\nprocesses 99\n")
    z = lambda n: brief[n].rstrip("\n")
    proses(akar, 1000, HERMES + ["gateway", "run"], "06:01:00")
    proses(akar, 2001, HERMES + ["-p", "desy", "-z", z("2026-10-16-desy-dicky.md")], "14:40:00")
    proses(akar, 2002, HERMES + ["-p", "desy", "-z", z("2026-10-16-desy-ganda-1.md")], "14:45:00")
    proses(akar, 2003, HERMES + ["-p", "desy", "-z", "# Brief untuk Desy (CTO) — KANARI-H2003 judul tak cocok\n"
                                 "Dari: Ajeng.\n**Peminta:** Pak Akbar (owner)\n\nKANARI-2003"], "14:55:00")
    proses(akar, 3001, HERMES + ["-p", "via", "-z", z("2026-10-16-via-jati.md")], "14:30:00")
    proses(akar, 4001, HERMES + ["-p", "alfa", "-z", z("2026-10-16-alfa-searchenginebsk.md")], "13:00:30")
    proses(akar, 5001, HERMES + ["-p", "carli", "-z", z("2026-10-16-carli-absensimeeting.md")], "14:05:20", comm="we(i)rd )")
    proses(akar, 6001, ["bash", "-c", "hermes -p beta -z KANARI-6001"], "14:00:00", comm="bash")
    proses(akar, 6002, ["ssh", "-p", "22", "bskdev-host", "KANARI-6002"], "14:00:00", comm="ssh")
    tulis(akar, "proyek.json", PROYEK)
    tulis(akar, "tim.json", tim_fixture(AGEN_SUMBER))
    profil(akar)
    awal = [
        ajeng("2026-10-15T22:00:00", "msg", "Pak Akbar", "KANARI-01 kemarin"),
        tim("2026-10-16T13:00:05", "alfa", "KANARI-SID-ALFA", "msg", "KANARI-02 brief"),
        tim("2026-10-16T14:10:00", "carli", "KANARI-SID-CARLI", "tool", "KANARI-03", "mcp__obsidian_bsk__catat_progres"),
        tim("2026-10-16T14:20:00", "beta", "KANARI-SID-BETA", "tool", "/data/x/KANARI-04", "write_file"),
        ajeng("2026-10-16T14:30:00", "msg", "Lala (asisten Pak Akbar)", "KANARI-05", role="bot"),
        tim("2026-10-16T14:31:00", "via", "KANARI-SID-VIA1", "tool", "KANARI-06", "web_search"),
        tim("2026-10-16T14:41:00", "desy", "KANARI-SID-DESY1", "tool", "handoff/KANARI-07", "mcp__obsidian_bsk__baca"),
        tim("2026-10-16T14:45:10", "desy", "KANARI-SID-DESY2", "tool", "cat /workspace/brief/KANARI-08", "terminal"),
        ajeng("2026-10-16T14:50:00", "msg", "Pak Akbar", "KANARI-09"),
        ajeng("2026-10-16T14:50:30", "tool", "Pak Akbar",
              'cd /workspace && /opt/hermes/.venv/bin/hermes -p desy -z "$(cat brief/KANARI-10.md)"', "terminal"),
        ajeng("2026-10-16T14:52:00", "msg", "Mas Dicky", "KANARI-11"),
        ajeng("2026-10-16T14:53:00", "tool", "Mas Dicky", "ssh admin@10.0.0.1 '/ip address print' KANARI-12", "terminal"),
        '{"type": "tool", "role": "owner", KANARI-13',
        ajeng("2026-10-16T14:55:00", "msg", "Mas Dicky", "KANARI-14"),
        ajeng("2026-10-16T14:56:00", "tool", "Pak Akbar", "/opt/data/KANARI-15", "read_file"),
        tim("2026-10-16T14:58:00", "carli", "KANARI-SID-CARLI", "tool", "python3 -m unittest KANARI-16", "terminal"),
        '[1, 2, "KANARI-17"]',
    ]
    tambahan = [
        tim("2026-10-16T14:59:58", "alfa", "KANARI-SID-ALFA", "tool",
            "ssh -F /opt/data/.ssh/config -o BatchMode=yes bskdev-host 'KANARI-18'", "terminal"),
        tim("2026-10-16T14:59:58", "via", "KANARI-SID-VIA2", "msg", "KANARI-19"),
        ajeng("2026-10-16T14:59:58", "msg", "Pak Akbar", "KANARI-20"),
        tim("2026-10-16T14:59:58", "desy", "KANARI-SID-DESY2", "tool", "KANARI-21", "mcp__obsidian_bsk__catat_progres"),
        tim("2026-10-16T14:59:59", "desy", "KANARI-SID-DESY2", "tool",
            '/opt/hermes/.venv/bin/hermes -p carli -z "$(cat /workspace/brief/KANARI-22.md)"', "terminal"),
        ajeng("2026-10-16T14:59:59", "tool", "Mas Dicky", "KANARI-23", "clarify"),
        tim("2026-10-16T14:59:59", "carli", "KANARI-SID-CARLI", "tool", "KANARI-24", "mcp__obsidian_bsk__setor"),
    ]
    tulis(akar, "activity.jsonl", jsonl(awal))
    tulis(akar, "tambahan.jsonl", jsonl(tambahan))
    tulis(akar, "langkah.json", {"siklus1": t("14:59:57"), "perubahan": {"tambah_activity": "tambahan.jsonl",
                                 "hapus_lock": ["jdih-v3.lock"]}, "siklus2": t("15:00:00")})

    S, DY, JT = "Pak Akbar", "Mas Dicky", "Mas Jati"
    T_SEB = tugas("lock-searchenginebsk", "Audit indeks campuran", "searchenginebsk", S, "Alfa", t("13:00:00"),
                  "menjalankan perintah di bskdev · Search Engine BSK", t("14:59:58"), "jalan")
    T_POL = tugas("lock-policytrack", "perbaikan statistik", "policytrack", None, "Beta", t("21:40:00", "2026-10-15"),
                  "menulis berkas · PolicyTrack", t("14:20:00"), "menunggu")
    T_ABS = tugas("lock-absensimeeting", "Rekap kehadiran ke Excel", "absensimeeting", JT, "Carli", t("14:05:00"),
                  "mengelola bank dokumen · Absensi Meeting", t("14:59:59"), "jalan")
    T_D1 = tugas("proses-2001", "Perbaikan urutan hasil pencarian", None, DY, "Desy", t("14:40:00"),
                 "memanggil TL Carli", t("14:59:59"), "jalan")
    T_D2 = tugas("proses-2002", None, None, None, "Desy", t("14:45:00"), "memanggil TL Carli", t("14:59:59"), "jalan")
    T_D3 = tugas("proses-2003", None, None, None, "Desy", t("14:55:00"), "memanggil TL Carli", t("14:59:59"), "jalan")
    T_VIA = tugas("proses-3001", "Ringkasan regulasi tanda tangan elektronik", None, JT, "Via", t("14:30:00"),
                  "membaca pesan", t("14:59:58"), "jalan")
    TG = "Permintaan lewat Telegram"
    T_AA = tugas("ajeng-akbar", TG, None, S, "Ajeng", t("14:50:00"), "membaca pesan", t("14:59:58"), "jalan")
    T_AD = tugas("ajeng-dicky", TG, None, DY, "Ajeng", t("14:52:00"), "meminta keputusan Mas Dicky", t("14:59:59"),
                 "menunggu")
    T_AJ = tugas("ajeng-jati", TG, None, JT, "Ajeng", None, None, None, "jalan")
    riwayat_akbar = [
        (t("09:00:00"), "beta", "Beta mulai JDIH"),
        (t("13:00:00"), "alfa", "Alfa mulai Search Engine BSK"),
        (t("13:00:05"), "alfa", "Alfa mulai bekerja"),
        (t("14:05:00"), "carli", "Carli mulai Absensi Meeting"),
        (t("14:10:00"), "carli", "Carli mulai bekerja"),
        (t("14:10:00"), "carli", "Carli mencatat kemajuan"),
        (t("14:20:00"), "beta", "Beta mulai bekerja"),
        (t("14:30:00"), "ajeng", "Lala (asisten Pak Akbar) mengirim pesan ke Ajeng"),
        (t("14:31:00"), "via", "Via mulai bekerja"),
        (t("14:41:00"), "desy", "Desy mulai bekerja"),
        (t("14:45:10"), "desy", "Desy mulai bekerja"),
        (t("14:50:00"), "ajeng", "Pak Akbar mengirim pesan ke Ajeng"),
        (t("14:50:30"), "ajeng", "Ajeng memanggil Desy"),
        (t("14:52:00"), "ajeng", "Mas Dicky mengirim pesan ke Ajeng"),
        (t("14:59:58"), "via", "Via mulai bekerja"),
        (t("14:59:58"), "ajeng", "Pak Akbar mengirim pesan ke Ajeng"),
        (t("14:59:58"), "desy", "Desy mencatat kemajuan"),
        (t("14:59:59"), "desy", "Desy memanggil Carli"),
        (t("14:59:59"), "ajeng", "Ajeng meminta keputusan Mas Dicky"),
        (t("14:59:59"), "carli", "Carli menyetor dokumen ke bank dokumen"),
        (t("15:00:00"), "beta", "Beta selesai JDIH"),
    ]
    aktif = {"ajeng": t("14:59:59"), "desy": t("14:59:59"), "via": t("14:59:58"), "alfa": t("14:59:58"),
             "beta": t("14:20:00"), "carli": t("14:59:59")}
    st = {"ajeng": "menunggu", "desy": "jalan", "via": "jalan", "alfa": "jalan", "beta": "menunggu", "carli": "jalan"}
    tulis(akar, "harapan/akbar.json", ringkasan("akbar", st, aktif,
          [T_POL, T_AD, T_SEB, T_ABS, T_VIA, T_D1, T_D2, T_AA, T_D3, T_AJ], riwayat_akbar))
    d1 = dict(T_D1, langkah_terakhir=None, langkah_waktu=None)
    tulis(akar, "harapan/dicky.json", ringkasan(
        "dicky", {"ajeng": "menunggu", "desy": "jalan", "via": "sibuk", "alfa": "sibuk", "beta": "sibuk", "carli": "sibuk"},
        {"ajeng": t("14:59:59")}, [T_AD, d1],
        [r for r in riwayat_akbar if r[2] in ("Beta mulai JDIH", "Mas Dicky mengirim pesan ke Ajeng",
                                               "Ajeng meminta keputusan Mas Dicky", "Beta selesai JDIH")]))
    tulis(akar, "harapan/jati.json", ringkasan(
        "jati", {"ajeng": "jalan", "desy": "sibuk", "via": "jalan", "alfa": "sibuk", "beta": "sibuk", "carli": "jalan"},
        {"via": t("14:59:58"), "carli": t("14:59:59")}, [T_ABS, T_VIA, T_AJ],
        [(t("14:05:00"), "carli", "Carli mulai Absensi Meeting"), (t("14:59:58"), "via", "Via mulai bekerja"),
         (t("14:59:59"), "desy", "Desy memanggil Carli"), (t("14:59:59"), "carli", "Carli menyetor dokumen ke bank dokumen")]))


def skenario2():
    akar = DIR / "skenario2"
    tulis(akar, "workspace/brief/tanpa-peminta.md", "# Brief TL — jdih-v3 — 2026-10-16 — Audit tautan\n"
          + "".join(f"baris {i} KANARI-T{i}\n" for i in range(2, 12)) + "**Peminta:** Mas Dicky (operator)\n\nKANARI-T13\n")
    tulis(akar, "workspace/brief/internal.md", "# Brief TL — pemahaman-asn — 2026-10-16\nDari: Desy (CTO).\n"
          "Peminta asal: Ajeng (izin internal tim)\n\nKANARI-I1\n")
    tulis(akar, "workspace/rahasia/KANARI-rahasia.md", "# Brief TL — ebook-v2 — 2026-10-16 — KANARI-RHS judul rahasia\n"
          "**Peminta:** Mas Dicky (operator)\n\nKANARI-RHS isi\n")
    lock = {
        "ebook-v2": "tl=alfa\nmulai=2026-10-16T10:00:00+07:00\nbrief=/workspace/brief/../rahasia/KANARI-rahasia.md\noleh=desy\n",
        "survei3as": "tl=alfa\nmulai=2026-10-16T08:00:00+07:00\n"
                     "brief=/data/net-bsk/workspace/brief/../rahasia/KANARI-rahasia.md\noleh=desy\n",
        "jdih-v3": "tl=beta\nmulai=2026-10-16T11:00:00+07:00\nbrief=/workspace/brief/tanpa-peminta.md\noleh=desy\n",
        "pemahaman-asn": "tl=carli\nmulai=2026-10-16T12:00:00+07:00\nbrief=/workspace/brief/internal.md\noleh=desy\n",
        "koordinasi": "tl=desy\nmulai=2026-10-16T09:00:00+07:00\nbrief=/workspace/brief/internal.md\noleh=desy\npid=123\n",
        "rusak": "ini bukan lock KANARI-RL\n",
        "Bad_Slug": "tl=alfa\nmulai=2026-10-16T07:00:00+07:00\nbrief=/workspace/brief/internal.md\noleh=desy\n",
    }
    for slug, isi in lock.items():
        tulis(akar, f"workspace/locks/{slug}.lock", isi)
    tulis(akar, "proc/stat", f"cpu  1 2 3 4\nbtime {BTIME}\nprocesses 99\n")
    proses(akar, 1000, HERMES + ["gateway", "run"], "06:01:00")
    proses(akar, 6001, ["bash", "-c", "hermes -p alfa -z KANARI-6001"], "14:00:00", comm="bash")
    proses(akar, 6002, ["ssh", "-p", "22", "bskdev-host", "KANARI-6002"], "14:00:00", comm="ssh")
    tulis(akar, "proyek.json", PROYEK)
    tulis(akar, "tim.json", tim_fixture(AGEN_SUMBER))
    profil(akar)
    awal = jsonl([
        ajeng("2026-10-16T14:20:00", "tool", "Pak Akbar", "KANARI-S1", "clarify"),
        '{"ts": "2026-10-16T14:21:00", KANARI-S2',
        '"KANARI-S3"',
        {"type": "msg", "role": "owner", "name": "Pak Akbar", "text": "KANARI-S4"},
        tim("16-10-2026 14:22", "alfa", "KANARI-SID-S5", "tool", "KANARI-S5", "terminal"),
    ]) + json.dumps(ajeng("2026-10-16T14:59:56", "msg", "Pak Akbar", "KANARI-S6"))[:-1]
    tulis(akar, "activity.jsonl", awal)
    tulis(akar, "pengganti.jsonl", jsonl([ajeng("2026-10-16T14:59:59", "msg", "Mas Jati", "KANARI-S7")]))
    tulis(akar, "langkah.json", {"siklus1": t("14:59:57"),
                                 "cek_siklus1": {"akbar_riwayat_memuat": "Ajeng meminta keputusan Pak Akbar"},
                                 "perubahan": {"ganti_activity": "pengganti.jsonl"}, "siklus2": t("15:00:00")})
    TS = tugas("lock-survei3as", "Pekerjaan Survei 3AS", "survei3as", None, "Alfa", t("08:00:00"), None, None, "menunggu")
    TE = tugas("lock-ebook-v2", "Pekerjaan eBook", "ebook-v2", None, "Alfa", t("10:00:00"), None, None, "menunggu")
    TJ = tugas("lock-jdih-v3", "Audit tautan", "jdih-v3", None, "Beta", t("11:00:00"), None, None, "menunggu")
    TP = tugas("lock-pemahaman-asn", "Pekerjaan Pemahaman ASN", "pemahaman-asn", None, "Carli", t("12:00:00"),
               None, None, "menunggu")
    TA = tugas("ajeng-jati", "Permintaan lewat Telegram", None, "Mas Jati", "Ajeng", t("14:59:59"), "membaca pesan",
               t("14:59:59"), "jalan")
    pesan_jati = (t("14:59:59"), "ajeng", "Mas Jati mengirim pesan ke Ajeng")
    tulis(akar, "harapan/akbar.json", ringkasan(
        "akbar", {"ajeng": "jalan", "desy": "bebas", "via": "bebas", "alfa": "menunggu", "beta": "menunggu",
                  "carli": "menunggu"}, {"ajeng": t("14:59:59")}, [TS, TE, TJ, TP, TA],
        [(t("08:00:00"), "alfa", "Alfa mulai Survei 3AS"), (t("10:00:00"), "alfa", "Alfa mulai eBook"),
         (t("11:00:00"), "beta", "Beta mulai JDIH"), (t("12:00:00"), "carli", "Carli mulai Pemahaman ASN"), pesan_jati]))
    terbatas = {"desy": "bebas", "via": "bebas", "alfa": "sibuk", "beta": "sibuk", "carli": "sibuk"}
    tulis(akar, "harapan/dicky.json", ringkasan("dicky", dict(terbatas, ajeng="sibuk"), {}, [], []))
    tulis(akar, "harapan/jati.json", ringkasan("jati", dict(terbatas, ajeng="jalan"), {"ajeng": t("14:59:59")},
                                               [TA], [pesan_jati]))


if __name__ == "__main__":
    for n in ("skenario1", "skenario2"):
        shutil.rmtree(DIR / n, ignore_errors=True)
    skenario1()
    skenario2()
    print("fixture ditulis:", sorted(str(p.relative_to(DIR)) for p in DIR.rglob("*") if p.is_file()).__len__(), "berkas")
