"""Uji config tim `conf/tim.json` (KONTRAK agent-dashboard-g7 §2–3, §6a). Semua data fiktif; nama di fixture = DATA uji.
Jalankan dari root project: python3 -m unittest discover -s tests/generator -v
"""
import contextlib
import copy
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from bantu_tim import FIXTURE, ROOT, muat, tulis_tim

sys.path.insert(0, str(ROOT / "script"))
import generator  # noqa: E402

LAIN = FIXTURE / "tim-lain" / "tim.json"  # koordinator `kepala`, cto `teknis`, pemilik `bos`, penonton `bos` + `wakil`
SKR = "2026-10-16T15:00:00+07:00"
NAMA_LAMA = ("akbar", "dicky", "jati", "ajeng", "desy", "alfa", "beta", "carli", "delta", "echo", "uci", "via")
GALAT_AGEN = "Config agen tidak terbaca"


class Dunia:
    def __init__(self, akar, dasar=LAIN, **kw):
        self.akar = Path(akar)
        for d in ("workspace/brief", "workspace/locks", "proc", "profiles"):
            (self.akar / d).mkdir(parents=True)
        for i in ("teknis", "t1", "t2", "kualitas"):
            (self.akar / "profiles" / i).mkdir()
            (self.akar / "profiles" / i / "profile.yaml").write_text(f"description: 'Profil uji {i}.'\n", encoding="utf-8")
        (self.akar / "proc" / "stat").write_text("cpu  1 2 3 4\nbtime 1792000000\nprocesses 9\n")
        (self.akar / "activity.jsonl").write_bytes(b"")
        (self.akar / "proyek.json").write_text(json.dumps({"proj-a": "Proyek A"}), encoding="utf-8")
        self.tim = tulis_tim(self.akar / "tim.json", self.akar, dasar=dasar, **kw)
        self.keluaran = self.akar / "keluaran"
        self.g = generator.Generator(tim=self.tim, proyek=self.akar / "proyek.json", keluaran=self.keluaran)

    def siklus(self, iso=SKR):
        buf = io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(buf):
            self.g.siklus(datetime.fromisoformat(iso))
        return self.baca()

    def baca(self):
        return {p.stem: json.loads(p.read_text(encoding="utf-8")) for p in sorted(self.keluaran.glob("*.json"))}

    def log(self, *baris):
        with open(self.akar / "activity.jsonl", "a", encoding="utf-8") as f:
            for b in baris:
                f.write(json.dumps(b, ensure_ascii=False) + "\n")


class DasarTim(unittest.TestCase):
    def buat(self, **kw):
        tmp = tempfile.mkdtemp(prefix="uji-tim-")
        self.addCleanup(shutil.rmtree, tmp, True)
        return Dunia(tmp, **kw)


class UjiIdLain(DasarTim):
    """(a) tim.json ber-id lain → keluaran memakai id itu, termasuk `pemilik`/`koordinator` di JSON."""

    def test_keluaran_memakai_id_config(self):
        d = self.buat()
        d.log({"type": "msg", "role": "owner", "name": "Bu Bos", "text": "KANARI", "ts": "2026-10-16T14:00:00"},
              {"type": "reply", "role": "owner", "name": "Bu Bos", "ts": "2026-10-16T14:00:30"},
              {"type": "tool", "role": "tim", "name": "Teknis", "profile": "teknis", "sid": "S1", "tool": "terminal",
               "detail": "hermes -p t1 -z KANARI", "blocked": False, "ts": "2026-10-16T14:01:00"})
        (d.akar / "workspace" / "brief" / "2026-10-16-t1-proj-a.md").write_text(
            "# Brief TL — proj-a — Cek\nPeminta: Pak Wakil lewat Kepala Kantor\n", encoding="utf-8")
        (d.akar / "workspace" / "locks" / "proj-a.lock").write_text(
            "tl=t1\nmulai=2026-10-16T09:00:00+07:00\nbrief=/workspace/brief/2026-10-16-t1-proj-a.md\n", encoding="utf-8")
        hasil = d.siklus()
        self.assertEqual(["bos", "wakil"], sorted(hasil))
        for p, h in hasil.items():
            self.assertEqual(("bos", "kepala", p), (h["pemilik"], h["koordinator"], h["penonton"]))
            self.assertEqual([{"id": "bos", "nama": "Bu Bos", "peran": "Pemilik tim", "induk": []},
                              {"id": "wakil", "nama": "Pak Wakil", "peran": "Pemberi order", "induk": ["bos"]}], h["orang"])
            self.assertEqual(["kepala", "teknis", "t1", "t2", "kualitas"], [a["id"] for a in h["agen"]])
        self.assertEqual(("semua", "order-sendiri"), (hasil["bos"]["cakupan"], hasil["wakil"]["cakupan"]))
        teks = [r["teks"] for r in hasil["bos"]["riwayat_hari_ini"]]
        self.assertIn("Kepala Kantor membalas Bu Bos", teks)
        self.assertIn("Teknis Utama memanggil Satu", teks)
        lock = next(t for t in hasil["bos"]["tugas_aktif"] if t["id"] == "lock-proj-a")
        self.assertEqual(("t1", "wakil"), (lock["pengerja_id"], lock["pemberi_id"]))
        self.assertEqual(["lock-proj-a"], [t["id"] for t in hasil["wakil"]["tugas_aktif"] if t["id"].startswith("lock-")])
        isi = json.dumps(hasil, ensure_ascii=False)
        for n in NAMA_LAMA:
            self.assertNotRegex(isi.lower(), rf"(?<![a-z0-9]){n}(?![a-z0-9])", n)

    def test_pemilik_bawaan_tanpa_pemberi_dan_tool_tanpa_awalan(self):
        d = self.buat()
        d.log({"type": "msg", "role": "owner", "name": "Orang Asing", "text": "KANARI", "ts": "2026-10-16T14:58:00"},
              {"type": "tool", "role": "owner", "name": "Bu Bos", "tool": "mcp__obsidian_bsk__setor", "detail": "KANARI",
               "blocked": False, "ts": "2026-10-16T14:59:00"})
        h = d.siklus()["bos"]
        self.assertEqual("bekerja", next(t for t in h["tugas_aktif"] if t["pemberi_id"] == "bos")["langkah_terakhir"])
        self.assertEqual(["Orang Asing mengirim pesan ke Kepala Kantor"], [r["teks"] for r in h["riwayat_hari_ini"]][:1])


class UjiTimTidakSah(DasarTim):
    """(c) tim.json tidak sah → galat terlihat + config sah terakhir (perilaku D2 lama)."""

    def test_rusak_pakai_config_sah_terakhir(self):
        d = self.buat()
        h0 = d.siklus()["bos"]
        self.assertEqual([], h0["galat"])
        sah = json.loads(d.tim.read_text(encoding="utf-8"))
        kasus = ["{", "[]", '"x"', "", json.dumps({"versi": 1})]
        kasus += [lambda c: c.update(versi=2), lambda c: c.pop("pemilik"), lambda c: c.update(pemilik="wakil2"),
                  lambda c: c.update(penonton=["bos", "tak-ada"]), lambda c: c.update(koordinator=5),
                  lambda c: c["pola"].update(peminta="("), lambda c: c["pola"].update(brief_nama="tanpa-penanda"),
                  lambda c: c["agen"]["t1"].update(ruang="dapur"), lambda c: c["sumber"].pop("brief"),
                  lambda c: c["kategori_perintah"].append({"pola": "x"}), lambda c: c.update(tool={"setor": 5})]
        for n, k in enumerate(kasus):
            with self.subTest(n=n):
                if callable(k):
                    cfg = copy.deepcopy(sah)
                    k(cfg)
                    d.tim.write_text(json.dumps(cfg), encoding="utf-8")
                else:
                    d.tim.write_text(k, encoding="utf-8")
                h = d.siklus(f"2026-10-16T15:00:{n + 1:02d}+07:00")["bos"]
                self.assertEqual([GALAT_AGEN], h["galat"])
                self.assertEqual("Satu", next(a for a in h["agen"] if a["id"] == "t1")["nama"])
                self.assertEqual(("bos", "kepala"), (h["pemilik"], h["koordinator"]))
        os.remove(d.tim)
        self.assertEqual([GALAT_AGEN], d.siklus("2026-10-16T15:01:00+07:00")["bos"]["galat"])
        sah["agen"]["t1"]["nama"] = "Satu Baru"
        d.tim.write_text(json.dumps(sah), encoding="utf-8")
        h = d.siklus("2026-10-16T15:01:03+07:00")["bos"]
        self.assertEqual(([], "Satu Baru"), (h["galat"], next(a for a in h["agen"] if a["id"] == "t1")["nama"]))

    def test_tidak_sah_sejak_awal_tidak_menulis_apa_pun_dan_terlihat(self):
        tmp = tempfile.mkdtemp(prefix="uji-tim-")
        self.addCleanup(shutil.rmtree, tmp, True)
        tim = Path(tmp) / "tim.json"
        tim.write_text("{", encoding="utf-8")
        r = subprocess.run([sys.executable, str(ROOT / "script" / "generator.py"), "--tim", str(tim), "--sekali",
                            "--proyek", str(Path(tmp) / "p.json"), "--keluaran", str(Path(tmp) / "k"),
                            "--nomor", str(Path(tmp) / "n.json")],
                           capture_output=True, text=True, timeout=30, stdin=subprocess.DEVNULL)
        self.assertEqual(1, r.returncode, r.stderr[-300:])
        self.assertIn("siklus gagal: ConfigTimTidakSah", r.stdout)
        self.assertFalse((Path(tmp) / "k").exists())


class UjiRingkasanAktivitas(DasarTim):
    """§6a: log metadata-saja (tanpa text/detail) tetap diproses; kunci `aktivitas` diabaikan generator."""

    # bentuk baris = keluaran hooks/team-activity.py (TL3) default §6a: koordinator `role` owner, `name` = nama pemilik,
    # TANPA kunci `profile`; agen lain `role` tim + `profile` = id; tanpa `text`/`detail`; `reply` hanya koordinator
    BARIS = [{"role": "owner", "name": "Bu Bos", "sid": "SK", "type": "msg", "ts": "2026-10-16T14:00:00"},
             {"role": "owner", "name": "Bu Bos", "sid": "SK", "type": "tool", "tool": "terminal", "blocked": False,
              "ts": "2026-10-16T14:00:10"},
             {"role": "tim", "name": "Teknis Utama", "profile": "teknis", "sid": "S1", "type": "msg", "ts": "2026-10-16T14:01:00"},
             {"role": "tim", "name": "Teknis Utama", "profile": "teknis", "sid": "S1", "type": "tool", "tool": "terminal",
              "blocked": False, "ts": "2026-10-16T14:01:30"},
             {"role": "tim", "name": "Satu", "profile": "t1", "sid": "S2", "type": "msg", "sub": True, "ts": "2026-10-16T14:02:00"},
             {"role": "owner", "name": "Bu Bos", "sid": "SK", "type": "msg", "sistem": True, "ts": "2026-10-16T14:03:00"},
             {"role": "owner", "name": "Bu Bos", "sid": "SK", "type": "reply", "ts": "2026-10-16T14:03:30"}]

    def test_log_metadata_saja_selesai_dan_json_sah(self):
        d = self.buat()
        d.log(*self.BARIS)
        hasil = d.siklus()
        for p in ("bos", "wakil"):
            self.assertEqual([], hasil[p]["galat"])
            json.loads((d.keluaran / f"{p}.json").read_text(encoding="utf-8"))
        teks = [r["teks"] for r in hasil["bos"]["riwayat_hari_ini"]]
        self.assertIn("Teknis Utama mulai bekerja", teks)

    def test_kunci_aktivitas_diabaikan(self):
        keluaran = []
        for akt in (None, {"catat_teks": True, "teks_maks": 2000, "catat_detail": True, "detail_maks": 4000}, {"catat_teks": 5}):
            d = self.buat(**({"aktivitas": akt} if akt is not None else {}))
            d.log(*self.BARIS)
            h = d.siklus()
            for v in h.values():
                self.assertEqual([], v["galat"])
            keluaran.append(json.dumps(h, sort_keys=True))
        self.assertEqual(1, len(set(keluaran)))


class UjiBerkasConf(unittest.TestCase):
    """Nilai g7 `conf/tim.json` persis KONTRAK §2 + `conf/tim.example.json` placeholder; `conf/agen.json` dihapus."""

    def test_agen_json_dihapus(self):
        self.assertFalse((ROOT / "conf" / "agen.json").exists())

    def test_tim_g7_sesuai_kontrak(self):
        c = json.loads((ROOT / "conf" / "tim.json").read_text(encoding="utf-8"))
        self.assertEqual(1, c["versi"])
        self.assertEqual([{"id": "akbar", "nama": "Pak Akbar", "peran": "Pemilik tim", "induk": []}], c["orang"])
        self.assertEqual((["akbar"], "akbar", "default", "arsa"), (c["penonton"], c["pemilik"], c["koordinator"], c["cto"]))
        ag = {"default": ("Lala", "Koordinator", ["akbar"], "koordinasi"), "arsa": ("Arsa", "CTO", ["default"], "teknik"),
              "sofi": ("Sofi", "Riset dan regulasi", ["default"], "riset"), "g7-qc": ("G7-QC", "QA/QC", ["default"], "qa")}
        ag.update({f"g7-tl{i}": (f"G7-TL{i}", "Tech Lead", ["arsa"], "teknik") for i in range(1, 6)})
        self.assertEqual(ag, {i: (e["nama"], e["peran"], e["induk"], e["ruang"]) for i, e in c["agen"].items()})
        self.assertEqual(["default", "arsa", "sofi", "g7-tl1", "g7-tl2", "g7-tl3", "g7-tl4", "g7-tl5", "g7-qc"], list(c["agen"]))  # urutan tampil
        s = c["sumber"]
        self.assertEqual(("/data/hermes-agent/workspace", "/workspace", "/data/hermes-agent/workspace/tim-g7/brief",
                          "/data/hermes-agent/workspace/tim-g7/locks", "/data/hermes-agent/workspace/tim-g7/handoff",
                          "/data/hermes-agent/data/profiles", "/data/hermes-agent/data/agent-hooks/state/activity.jsonl", "/proc"),
                         (s["workspace"], s["workspace_kontainer"], s["brief"], s["lock"], s["handoff"], s["profil"],
                          s["activity"], s["proc"]))
        self.assertIn("belum tersedia", c["sumber"].get("_catatan", ""))
        self.assertEqual(("--", "mcp__obsidian__", "mcp__obsidian__setor", None),
                         (c["pola"]["lock_pemisah_subtugas"], c["tool"]["awalan_bank_dokumen"], c["tool"]["setor"],
                          c["tool"]["catat_progres"]))
        self.assertEqual({"catat_teks": False, "teks_maks": 300, "catat_detail": False, "detail_maks": 1000}, c["aktivitas"])
        self.assertEqual(["menjalankan perintah di g7", "menjalankan perintah di bskdev", "mengakses R1"],
                         [e["teks"] for e in c["kategori_perintah"]])

    def test_config_g7_dan_contoh_lolos_validasi_generator(self):
        for n in ("tim.json", "tim.example.json"):
            with self.subTest(n=n):
                generator.validasi_tim(json.loads((ROOT / "conf" / n).read_text(encoding="utf-8")))

    def test_contoh_placeholder_tanpa_identitas_nyata(self):
        teks = (ROOT / "conf" / "tim.example.json").read_text(encoding="utf-8")
        c = json.loads(teks)
        self.assertEqual({"catat_teks": False, "teks_maks": 300, "catat_detail": False, "detail_maks": 1000}, c["aktivitas"])
        for n in NAMA_LAMA + ("arsa", "lala", "sofi", "g7", "bskdev", "hermes-agent", "obsidian"):
            self.assertNotRegex(teks.lower(), rf"(?<![a-z0-9]){n}(?![a-z0-9])", n)
        self.assertNotRegex(teks, r"\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}")


if __name__ == "__main__":
    unittest.main()
