#!/usr/bin/env python3
"""bangun_fixture_kantor.py - fixture ringkasan "Kantor Agen" untuk uji web (KONTRAK-kantor-agen.md bagian C).

SEMUA ISI = KARANGAN UJI (TL Alfa, 24 Okt 2026), bukan data asli: judul, jam, nomor misi, PID, dan peristiwa dikarang
agar tiap status/alasan, sub-agen aktif + selesai, spawn_kuota null, kanari XSS, agen ruang `lain`, dan misi tertahan yang
menunggu 2 misi anak (koreksi 1, keputusan CTO 6a) muncul. Tiap berkas
membawa kunci `_fixture` sebagai penanda. akbar.json dibangun dari spesifikasi di bawah; dicky.json/jati.json diturunkan
dari akbar dengan saringan C7 (misi pemilik V saja) + aturan isolasi skema 1 §5 (status/terakhir_aktif agen).

Pakai: python3 bangun_fixture_kantor.py <dir keluaran> [--geser-ke ISO]   (--geser-ke: semua waktu digeser sehingga
dibuat_pada = ISO itu; dipakai harness uji peramban agar "hari ini" dan durasi tetap masuk akal). Stdlib saja.
"""
import datetime as dt
import json
import os
import sys

TGL = "2026-10-24"
PENANDA = "KARANGAN UJI TL Alfa 24 Okt 2026 untuk uji web Kantor Agen - bukan data asli"
ORANG = [{"id": "akbar", "nama": "Pak Akbar", "peran": "Pemilik tim", "induk": []},
         {"id": "dicky", "nama": "Mas Dicky", "peran": "Pemberi order", "induk": ["akbar"]},
         {"id": "jati", "nama": "Mas Jati", "peran": "Pemberi order", "induk": ["akbar"]}]
NAMA_ORANG = {o["id"]: o["nama"] for o in ORANG}
# id, nama, peran, induk, status global, terakhir_aktif (jam), ruang
AGEN = [("ajeng", "Ajeng", "Koordinator", ["dicky", "jati"], "jalan", "10:59:58", "koordinasi"),
        ("desy", "Desy", "CTO", ["ajeng"], "jalan", "10:58:40", "teknik"),
        ("via", "Via", "Riset dan peraturan", ["ajeng"], "jalan", "10:59:30", "riset"),
        ("uci", "Uci", "QA/QC", ["ajeng"], "bebas", "09:40:15", "qa"),
        ("alfa", "Alfa", "Tech Lead", ["desy"], "jalan", "10:59:55", "teknik"),
        ("beta", "Beta", "Tech Lead", ["desy"], "jalan", "10:59:50", "teknik"),
        ("carli", "Carli", "Tech Lead", ["desy"], "menunggu", "10:35:30", "teknik"),
        ("eko", "Eko", "Agen uji tanpa ruang", ["ajeng"], "bebas", None, "lain")]
NAMA_AGEN = {a[0]: a[1] for a in AGEN}
TL = {"alfa", "beta", "carli"}

# Misi: nomor, pelaksana, pemberi_id (None = tak dikenal -> pemilik akbar), judul, project, project_nama, status, alasan,
# menunggu_misi, induk_misi, mulai, selesai, langkah [(jam, label)], langkah_sekarang, langkah_waktu,
# subagen [(mulai, selesai|None)] atau None, spawn_kuota, tugas (id tugas_aktif skema 1 atau None)
MISI = [
    dict(n=277, p="beta", pb="jati", j="Grafik rekap triwulan", pr="rekap-wilayah-tw", pn="Rekap Wilayah", st="selesai",
         mulai="08:05:10", sel="09:15:40", lk=[("08:06:00", "Mulai"), ("08:40:00", "Langkah"), ("09:14:30", "Selesai")],
         ls="menulis berkas · Rekap Wilayah", lw="09:15:02", sub=[], kuota=10),
    dict(n=278, p="desy", pb=None, j=None, pr=None, pn=None, st="selesai", mulai="08:20:00", sel="08:50:30",
         lk=[("08:21:00", "Mulai"), ("08:49:10", "Selesai")], ls="membaca berkas", lw="08:50:01", sub=[], kuota=10),
    dict(n=279, p="uci", pb="dicky", j="QA kertas kebijakan PBJ", pr=None, pn=None, st="selesai", mulai="08:30:00",
         sel="09:40:15", lk=[("08:31:00", "Mulai"), ("09:02:00", "Langkah"), ("09:39:00", "Selesai")],
         ls="membaca bank dokumen", lw="09:39:50", sub=[("08:45:00", "09:05:00"), ("09:10:00", "09:30:00")], kuota=5),
    dict(n=280, p="via", pb="akbar", j="Cek status Perpres 95/2018", pr=None, pn=None, st="berakhir", mulai="09:20:00",
         sel="10:05:20", lk=[("09:21:00", "Mulai")], ls="mencari di web", lw="10:05:20", sub=[], kuota=10),
    dict(n=281, p="desy", pb="akbar", j="Kantor Agen — rencana dan kontrak", pr="agent-dashboard", pn="Agent Dashboard",
         st="menunggu", al="misi-lain", mm=["T-283"], mulai="10:31:00", lk=[("10:49:12", "Mulai")],
         ls="menunggu proses · Agent Dashboard", lw="10:58:40", sub=[], kuota=10, tugas="proses-41002"),
    dict(n=282, p="beta", pb="jati", j="Rekap layanan <img src=x onerror=alert(3)> per wilayah", pr="rekap-wilayah",
         pn="Rekap Wilayah", st="jalan", mulai="10:20:00", lk=[("10:21:00", "Mulai")],
         ls="menjalankan perintah di bskdev · Rekap Wilayah", lw="10:59:50", sub=[("10:30:00", None)], kuota=10,
         tugas="lock-rekap-wilayah"),
    dict(n=283, p="alfa", pb="akbar", j="Kantor Agen — tampilan <img src=x onerror=alert(1)>", pr="agent-dashboard-ui",
         pn="Agent Dashboard", st="jalan", im="T-281", mulai="10:52:00", lk=[("10:55:39", "Mulai"), ("10:58:00", "Langkah")],
         ls="menulis berkas · Agent Dashboard", lw="10:59:55", sub=[("10:53:00", "10:56:00"), ("10:57:00", None)], kuota=10,
         tugas="lock-agent-dashboard-ui"),
    dict(n=284, p="via", pb="dicky", j='Ringkasan putusan "><script>alert(2)</script> MK', pr=None, pn=None, st="jalan",
         mulai="10:10:00", lk=[("10:11:00", "Mulai"), ("10:40:00", "Langkah")], ls="mencari di web", lw="10:59:30",
         sub=[("10:45:00", None)], kuota=None, tugas="proses-41001"),
    dict(n=285, p="carli", pb="dicky", j="Uji beban API pencarian", pr="searchenginebsk", pn="Search Engine BSK",
         st="menunggu", al="review", mulai="09:30:00",
         lk=[("09:31:00", "Mulai"), ("09:58:00", "Langkah"), ("10:35:00", "Selesai")],
         ls="mencatat kemajuan · Search Engine BSK", lw="10:35:30", sub=[("09:40:00", "10:00:00"), ("10:02:00", "10:20:00")],
         kuota=10, tugas="lock-searchenginebsk"),
    dict(n=286, p="carli", pb="akbar", j="Audit indeks campuran", pr="searchenginebsk-indeks", pn="Search Engine BSK",
         st="menunggu", al="gantung", mulai="08:40:00", lk=[("08:41:00", "Mulai"), ("09:50:00", "Hambatan")],
         ls="menjalankan perintah di bskdev · Search Engine BSK", lw="09:52:10", sub=[], kuota=10,
         tugas="lock-searchenginebsk-indeks"),
    # koreksi 1 (keputusan CTO 6a): misi tertahan yang menunggu 2 misi anak aktif dengan pelaksana berbeda; mulai paling
    # awal di antara misi-lain sehingga menjadi banner (D7) dan pilihan awal detail (callout D9)
    dict(n=287, p="desy", pb="akbar", j="Kantor Agen — integrasi generator dan web", pr="agent-dashboard",
         pn="Agent Dashboard", st="menunggu", al="misi-lain", mm=["T-288", "T-289"], mulai="10:12:00",
         lk=[("10:13:00", "Mulai")], ls="menunggu proses · Agent Dashboard", lw="10:40:00", sub=[], kuota=10,
         tugas="proses-41003"),
    dict(n=288, p="alfa", pb="akbar", j="Kantor Agen — uji peramban integrasi", pr="agent-dashboard-uji",
         pn="Agent Dashboard", st="jalan", im="T-287", mulai="10:14:00", lk=[("10:15:00", "Mulai"), ("10:30:00", "Langkah")],
         ls="menjalankan perintah di bskdev · Agent Dashboard", lw="10:59:40", sub=[], kuota=10,
         tugas="lock-agent-dashboard-uji"),
    dict(n=289, p="beta", pb="akbar", j="Kantor Agen — uji generator <img src=x onerror=alert(4)>", pr="agent-dashboard-gen",
         pn="Agent Dashboard", st="jalan", im="T-287", mulai="10:16:30", lk=[("10:17:10", "Mulai")],
         ls="menulis berkas · Agent Dashboard", lw="10:59:45", sub=[("10:20:00", None)], kuota=10,
         tugas="lock-agent-dashboard-gen"),
]
# Baris riwayat tanpa misi: (jam, pelaku, teks, pemilik)
RIWAYAT_LAIN = [("08:00:05", "ajeng", "Pak Akbar mengirim pesan ke Ajeng", "akbar"),
                ("08:02:00", "ajeng", "Mas Jati mengirim pesan ke Ajeng", "jati"),
                ("08:25:00", "ajeng", "Mas Dicky mengirim pesan ke Ajeng", "dicky"),
                ("10:24:50", "ajeng", "Pak Akbar mengirim pesan ke Ajeng", "akbar"),
                ("10:25:30", "ajeng", "Ajeng membalas Pak Akbar", "akbar"),
                ("10:30:10", "ajeng", "Ajeng memanggil Desy", "akbar")]


def iso(jam):
    return "%sT%s+07:00" % (TGL, jam) if jam else None


def tid(n):
    return "T-%03d" % n


def nama(i):
    return NAMA_ORANG.get(i) or NAMA_AGEN.get(i) or i


def rantai(m):
    jalur = {"ajeng": [], "desy": ["desy"], "via": ["via"], "uci": ["uci"]}.get(m["p"], ["desy", m["p"]])
    return ([m["pb"]] if m["pb"] else []) + ["ajeng"] + jalur


def bangun_akbar():
    misi, riwayat = [], []
    urut = 0

    def rw(jam, pelaku, teks, pemilik, mid):
        nonlocal urut
        urut += 1
        riwayat.append((iso(jam), urut, {"waktu": iso(jam), "pelaku": pelaku, "teks": teks, "misi": mid}, pemilik))

    for m in MISI:
        t = tid(m["n"])
        pemilik = m["pb"] or "akbar"
        r = rantai(m)
        sub = None if m["sub"] is None else [{"ke": i + 1, "mulai": iso(a), "selesai": iso(b)} for i, (a, b) in enumerate(m["sub"])]
        misi.append({"id": t, "nomor": m["n"], "judul": m["j"], "project": m["pr"], "project_nama": m["pn"],
                     "pemberi": NAMA_ORANG.get(m["pb"]) if m["pb"] else None, "pemberi_id": m["pb"],
                     "pelaksana_id": m["p"], "pelaksana": NAMA_AGEN[m["p"]], "rantai": r, "status": m["st"],
                     "alasan": m.get("al"), "menunggu_misi": list(m.get("mm", [])), "induk_misi": m.get("im"),
                     "mulai": iso(m["mulai"]), "selesai": iso(m.get("sel")),
                     "langkah": [{"waktu": iso(a), "label": b} for a, b in m["lk"]], "langkah_total": None,
                     "langkah_sekarang": m["ls"], "langkah_waktu": iso(m["lw"]), "subagen": sub, "spawn_kuota": m["kuota"]})
        lewat = " → ".join(nama(x) for x in r if x != m["pb"])
        pelaku = NAMA_AGEN[m["p"]]
        if m["p"] in TL:  # lock misi: "<TL> mulai <project_nama>" sedikit sebelum sesi pertama
            jl = (dt.datetime.fromisoformat(iso(m["mulai"])) - dt.timedelta(minutes=1)).strftime("%H:%M:%S")
            rw(jl, m["p"], "%s mulai %s" % (pelaku, m["pn"]), pemilik, t)
        rw(m["mulai"], m["pb"] or "ajeng", ("%s memberi order %s lewat %s" % (nama(m["pb"]), t, lewat)) if m["pb"]
           else "Order %s masuk lewat %s" % (t, lewat), pemilik, t)
        for jam, _ in m["lk"]:
            rw(jam, m["p"], "%s mencatat kemajuan%s" % (pelaku, " · " + m["pn"] if m["pn"] else ""), pemilik, t)
        for i, (a, b) in enumerate(m["sub"] or []):
            rw(a, m["p"], "%s men-spawn sub-agen ke-%d · %s" % (pelaku, i + 1, t), pemilik, t)
            if b:
                rw(b, m["p"], "Sub-agen ke-%d %s selesai · %s" % (i + 1, pelaku, t), pemilik, t)
        if m["st"] == "selesai":
            rw(m["sel"], m["p"], "%s menyelesaikan %s" % (pelaku, t), pemilik, t)
        elif m["st"] == "berakhir":
            rw(m["sel"], m["p"], "%s berakhir tanpa laporan" % t, pemilik, t)
    rw("10:51:55", "desy", "Desy memanggil Alfa", "akbar", "T-281")
    for jam, pelaku, teks, pemilik in RIWAYAT_LAIN:
        rw(jam, pelaku, teks, pemilik, None)
    riwayat.sort(key=lambda x: (x[0], x[1]))

    aktif = sorted([m for m in misi if m["status"] in ("jalan", "menunggu")],
                   key=lambda m: (0 if m["status"] == "menunggu" else 1, m["mulai"]))
    misi = aktif + sorted([m for m in misi if m not in aktif], key=lambda m: m["selesai"], reverse=True)  # C8

    tugas = []
    for m in MISI:
        if not m.get("tugas"):
            continue
        tl = m["p"] in TL
        tugas.append({"id": m["tugas"], "judul": m["j"], "project": m["pr"] if tl else None,
                      "project_nama": m["pn"] if tl else None, "pemberi": NAMA_ORANG.get(m["pb"]) if m["pb"] else None,
                      "pemberi_id": m["pb"], "pengerja": NAMA_AGEN[m["p"]], "pengerja_id": m["p"],
                      "mulai": iso(m["mulai"]) if not tl else (dt.datetime.fromisoformat(iso(m["mulai"])) - dt.timedelta(minutes=1)).isoformat(),
                      "langkah_terakhir": m["ls"], "langkah_waktu": iso(m["lw"]),
                      "status": "jalan" if m["st"] == "jalan" or m["p"] in ("desy", "via") else "menunggu"})
    tugas.append({"id": "ajeng-akbar", "judul": "Permintaan lewat Telegram", "project": None, "project_nama": None,
                  "pemberi": "Pak Akbar", "pemberi_id": "akbar", "pengerja": "Ajeng", "pengerja_id": "ajeng",
                  "mulai": iso("10:24:50"), "langkah_terakhir": "membaca pesan", "langkah_waktu": iso("10:59:58"), "status": "jalan"})
    tugas.sort(key=lambda t: (0 if t["status"] == "menunggu" else 1, t["mulai"] or "~", t["id"]))

    agen = [{"id": i, "nama": n, "peran": p, "induk": ind, "status": st, "terakhir_aktif": iso(ta), "ruang": ru}
            for i, n, p, ind, st, ta, ru in AGEN]
    return {"versi_skema": "1", "penonton": "akbar", "cakupan": "semua", "pemilik": "akbar", "koordinator": "ajeng", "dibuat_pada": iso("11:00:00"), "galat": [],
            "peringatan": ["Profil eko belum ada di conf/agen.json"], "orang": ORANG, "agen": agen,
            "tugas_aktif": tugas, "riwayat_hari_ini": [x[2] for x in riwayat],
            "_pemilik_riwayat": [x[3] for x in riwayat], "misi": misi}


def lengkapi(d):
    """keadaan/misi_aktif (C2), ringkasan (C6) dari isi berkas."""
    M = d["misi"]
    for a in d["agen"]:
        aktif = [m for m in M if m["pelaksana_id"] == a["id"] and m["status"] in ("jalan", "menunggu")]
        a["misi_aktif"] = sorted([m["id"] for m in aktif], key=lambda x: int(x[2:]))
        if aktif:  # C2 revisi CTO 24 Okt 12.3x: misi aktif terlihat menentukan keadaan lebih dulu
            a["keadaan"] = "menunggu" if all(m["status"] == "menunggu" for m in aktif) else "bekerja"
        elif a["status"] in ("sibuk", "bebas"):
            a["keadaan"] = a["status"]
        elif a["status"] == "menunggu":
            a["keadaan"] = "menunggu"
        else:
            a["keadaan"] = "bekerja"
    akt = [m for m in M if m["status"] in ("jalan", "menunggu")]
    sub = None if any(m["subagen"] is None for m in akt) else sum(1 for m in akt for s in m["subagen"] if s["selesai"] is None)
    d["ringkasan"] = {"agen": {k: sum(1 for a in d["agen"] if a["keadaan"] == k) for k in ("bekerja", "menunggu", "bebas", "sibuk")},
                      "misi": {"aktif": len(akt), "selesai_hari_ini": len(M) - len(akt)}, "subagen_aktif": sub}
    return d


def saring(akbar, v):
    """C7 + skema 1 §5: berkas penonton v dari berkas akbar."""
    d = json.loads(json.dumps(akbar))
    d["penonton"], d["cakupan"] = v, "order-sendiri"
    milik = lambda x: (x.get("pemberi_id") or "akbar") == v
    d["misi"] = [m for m in d["misi"] if milik(m)]
    ids = {m["id"] for m in d["misi"]}
    for m in d["misi"]:
        m["menunggu_misi"] = [x for x in m["menunggu_misi"] if x in ids]
        if m["induk_misi"] not in ids:
            m["induk_misi"] = None
    semua_tugas = d["tugas_aktif"]
    d["tugas_aktif"] = [t for t in semua_tugas if milik(t)]
    for a in d["agen"]:
        punya = [t for t in semua_tugas if t["pengerja_id"] == a["id"]]
        tv = [t for t in punya if milik(t)]
        if tv:
            a["status"] = "menunggu" if any(t["status"] == "menunggu" for t in tv) else "jalan"
            if len(tv) != len(punya):
                a["terakhir_aktif"] = None
                for t in d["tugas_aktif"]:
                    if t["pengerja_id"] == a["id"]:
                        t["langkah_terakhir"] = t["langkah_waktu"] = None
        else:
            a["status"] = "bebas" if a["status"] == "bebas" else "sibuk"
            a["terakhir_aktif"] = None
    d["riwayat_hari_ini"] = [r for r, p in zip(akbar["riwayat_hari_ini"], akbar["_pemilik_riwayat"]) if p == v]
    return d


def geser(d, ke):
    """Geser semua waktu ISO +07:00 sehingga dibuat_pada = ke (harness peramban)."""
    delta = dt.datetime.fromisoformat(ke) - dt.datetime.fromisoformat(d["dibuat_pada"])

    def g(o):
        if isinstance(o, dict):
            return {k: g(v) for k, v in o.items()}
        if isinstance(o, list):
            return [g(v) for v in o]
        if isinstance(o, str) and len(o) == 25 and o[4] == "-" and o[10] == "T" and o.endswith("+07:00"):
            return (dt.datetime.fromisoformat(o) + delta).isoformat()
        return o
    return g(d)


def tulis(path, d):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(json.dumps(d, ensure_ascii=False, separators=(",", ":")) + "\n")
    os.chmod(tmp, 0o644)
    os.replace(tmp, path)


def semua(ke=None):
    """{penonton: berkas} dari spesifikasi MISI/AGEN saat ini; ke = ISO dibuat_pada tujuan (geser) atau None."""
    akbar = bangun_akbar()
    berkas = {"akbar": akbar}
    for v in ("dicky", "jati"):
        berkas[v] = saring(akbar, v)
    hasil = {}
    for p, d in berkas.items():
        d = lengkapi(d)
        d.pop("_pemilik_riwayat", None)
        d = {"_fixture": PENANDA, **d}
        hasil[p] = geser(d, ke) if ke else d
    return hasil


def main(argv):
    if not argv or argv[0].startswith("-"):
        print(__doc__)
        return 2
    out = argv[0]
    ke = argv[argv.index("--geser-ke") + 1] if "--geser-ke" in argv else None
    os.makedirs(out, exist_ok=True)
    for p, d in semua(ke).items():
        tulis(os.path.join(out, p + ".json"), d)
    print("fixture ditulis:", out, "geser" if ke else "asli")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
