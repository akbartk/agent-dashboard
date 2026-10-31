"""Uji alur tim "P1.5" (31 Okt 2026): hirarki `tl`/`sembunyikan`, brief tanpa H1, status dari jalan-*.json/lock/handoff,
riwayat lock permanen, langkah handoff, verdict QC, guard blok, panggilan TL, card misi koordinator.
Fixture: tests/fixtures/p15 (dibangun bangun_p15.py). Registri nomor + keluaran di TMPDIR (bukan storage/ live)."""
import contextlib
import copy
import io
import json
import re
import shutil
import time
import unittest
import unittest.mock
from datetime import datetime
from pathlib import Path

from bantu_misi import ROOT, DasarMisi, Misi1, misi, riwayat
from bantu_tim import muat
import generator

FIX = ROOT / "tests" / "fixtures" / "p15"


class P15(Misi1):
    FIXTURE = FIX


class Dasar(DasarMisi):
    def buat(self, **kw):
        d = P15(Path(self.tmp) / f"m{len(self.dunia)}", **kw)
        self.dunia.append(d)
        return d

    def mulai(self):
        d = self.buat()
        return d, d.siklus()["akbar"]

    @staticmethod
    def cari(h, **kv):
        return next((m for m in h["misi"] if all(m.get(k) == v for k, v in kv.items())), None)

    def kartu(self, h, jam, **kv):
        """Card permintaan menurut jam mulai (HH:MM); judul card seragam, tidak bisa dipakai membedakan."""
        m = self.cari(h, jenis="permintaan", mulai=f"2026-10-31T{jam}:00+07:00", **kv)
        assert m is not None, jam
        return m


class TestConfig(unittest.TestCase):
    def cfg(self, **ubah):
        d = muat(FIX / "tim.json")
        d.update(ubah)
        return d

    def test_tl_sembunyikan_sah_dan_cto_opsional(self):
        c = generator.validasi_tim(self.cfg())
        self.assertEqual(["alfa", "beta"], c["tl"])
        self.assertEqual(["gamma"], c["sembunyikan"])
        self.assertIsNone(c["cto"])

    def test_tanpa_tl_aturan_lama(self):
        d = muat(FIX / "tim.json")
        del d["tl"], d["sembunyikan"]
        c = generator.validasi_tim(d)
        self.assertIsNone(c["tl"])
        self.assertEqual([], c["sembunyikan"])

    def test_tidak_sah_ditolak(self):
        for k, v in (("tl", "alfa"), ("tl", ["alfa", "alfa"]), ("tl", ["Alfa Besar"]), ("tl", [1]), ("sembunyikan", "gamma"),
                     ("sembunyikan", ["gamma", "gamma"]), ("sembunyikan", [""]), ("tl", ["ajeng"]), ("sembunyikan", ["ajeng"])):
            with self.subTest(k=k, v=v), self.assertRaises(ValueError):
                generator.validasi_tim(self.cfg(**{k: v}))

    def test_sumber_verdict_guard(self):
        for kunci, v in (("verdict", 5), ("verdict", ""), ("guard", "x"), ("guard", [1]), ("guard", [""])):
            d = self.cfg()
            d["sumber"][kunci] = v
            with self.subTest(kunci=kunci, v=v), self.assertRaises(ValueError):
                generator.validasi_tim(d)

    def test_cto_tetap_divalidasi_bila_ada(self):
        with self.assertRaises(ValueError):
            generator.validasi_tim(self.cfg(cto=5))


class TestHirarki(Dasar):
    def test_agen_tersembunyi_dan_tl_daftar(self):
        d, h = self.mulai()
        self.assertEqual({"alfa", "beta"}, d.g.tl)
        ids = [a["id"] for a in h["agen"]]
        self.assertNotIn("gamma", ids)
        self.assertEqual({"ajeng", "via", "uci", "alfa", "beta"}, set(ids))
        self.assertEqual([], [p for p in h["peringatan"] if "gamma" in p])
        self.assertEqual([], h["galat"])


class TestPencocokan(Dasar):
    def test_semua_jalur(self):
        d, h = self.mulai()
        a = self.cari(h, project="tahap-satu")          # jalan-*.json + prefix isi
        self.assertEqual("alfa", a["pelaksana_id"])      # pelaksana dari baris `Kunci: tl=`
        self.assertEqual("Tahap Satu — a", a["judul"])    # tanpa H1: project + topik nama berkas
        self.assertEqual("beta", self.cari(h, project="tahap-dua")["pelaksana_id"])
        self.assertIsNotNone(self.cari(h, project="tahap-tiga"))
        self.assertIsNotNone(self.cari(h, project="tahap-empat"))   # teks pesan "Mulai." -> hanya lewat jalan-*.json
        self.assertIsNotNone(self.cari(h, project="tahap-lima"))    # tanpa run -> hanya lewat prefix isi brief

    def test_ambigu_ditolak(self):
        d, h = self.mulai()
        self.assertIsNone(self.cari(h, project="ulang"))
        self.assertEqual(0, len([m for m in h["misi"] if "ulang" in (m["judul"] or "").lower()]))

    def test_pelaksana_tidak_cocok_ditolak(self):
        d = self.buat()
        d.tambah_baris({"type": "msg", "role": "tim", "name": "Via", "profile": "via", "sid": "V1",
                        "text": (FIX / "workspace/brief/2026-10-31-tahap-dua-b.md").read_text()[:300], "ts": "2026-10-31T08:58:00"})
        h = d.siklus()["akbar"]
        self.assertEqual(["beta"], [m["pelaksana_id"] for m in h["misi"] if m["project"] == "tahap-dua"])


class TestStatus(Dasar):
    def test_status_dari_run_lock(self):
        d, h = self.mulai()
        a, b, c = (self.cari(h, project=p) for p in ("tahap-satu", "tahap-dua", "tahap-tiga"))
        dd, e = self.cari(h, project="tahap-empat"), self.cari(h, project="tahap-lima")
        self.assertEqual(("selesai", None, "2026-10-31T08:20:00+07:00"), (a["status"], a["alasan"], a["selesai"]))
        self.assertEqual({"status": "selesai", "rc": 0, "durasi_detik": 60.0, "laporan": True}, a["jalan"])
        self.assertEqual(("berakhir", "gagal", "2026-10-31T08:10:00+07:00"), (b["status"], b["alasan"], b["selesai"]))
        self.assertEqual({"status": "gagal", "rc": 1, "durasi_detik": 60.0, "laporan": False}, b["jalan"])
        self.assertEqual("jalan", c["status"])
        self.assertEqual("berjalan", c["jalan"]["status"])
        self.assertEqual(("menunggu", "review"), (dd["status"], dd["alasan"]))
        self.assertEqual(("menunggu", "gantung", None), (e["status"], e["alasan"], e["jalan"]))

    def test_snapshot_basi_tidak_dianggap_jalan(self):
        d = self.buat()
        shutil.rmtree(d.akar / "proc" / "4001")
        c = self.cari(d.siklus()["akbar"], project="tahap-tiga")
        self.assertEqual(("menunggu", "gantung"), (c["status"], c["alasan"]))
        (d.akar / "workspace/locks/tahap-tiga.lock").unlink()
        c = self.cari(d.siklus()["akbar"], project="tahap-tiga")
        self.assertEqual("berakhir", c["status"])

    def test_lock_selesai_menjadi_review(self):
        d = self.buat()
        with open(d.akar / "workspace/locks/tahap-lima.lock", "a") as f:
            f.write("selesai=2026-10-31T08:59:00+07:00\nrc=0\n")
        self.assertEqual("review", self.cari(d.siklus()["akbar"], project="tahap-lima")["alasan"])

    def test_laporan_lama_tetap_jadi_fallback(self):
        d = self.buat()
        (d.akar / "workspace/brief/2026-10-31-tahap-lima-e.laporan.txt").write_text("isi")
        (d.akar / "workspace/locks/tahap-lima.lock").unlink()
        e = self.cari(d.siklus()["akbar"], project="tahap-lima")
        self.assertEqual("selesai", e["status"])
        self.assertIsNone(e["jalan"])


class TestRiwayatLock(Dasar):
    def test_peristiwa_permanen_dan_tanpa_duplikat(self):
        d, h = self.mulai()
        r = [x[1] for x in riwayat(h)]
        for t in ("Alfa mulai Tahap Satu", "Alfa selesai Tahap Satu", "Ajeng melepas Tahap Satu",
                  "Tahap Lima dialihkan ke Alfa"):
            self.assertIn(t, r)
        self.assertEqual(1, r.count("Alfa mulai Tahap Empat"))   # lock in-memory + riwayat = satu
        self.assertFalse([t for t in r if "kemarin" in t.lower()])

    def test_inkremental(self):
        d = self.buat()
        d.siklus()
        with open(d.akar / "workspace/locks/.tim_kunci.riwayat.jsonl", "a") as f:
            f.write(json.dumps({"ts": "2026-10-31T08:59:00+07:00", "perintah": "kunci", "kunci": "tahap-dua", "tl": "beta",
                                "oleh": "ajeng", "pid": 9}) + "\n")
        r = [x[1] for x in riwayat(d.siklus("2026-10-31T09:01:00+07:00")["akbar"])]
        self.assertEqual(1, r.count("Beta mulai Tahap Dua"))
        self.assertEqual(1, r.count("Alfa selesai Tahap Satu"))


class TestLangkahHandoff(Dasar):
    def test_langkah_dari_handoff(self):
        d, h = self.mulai()
        a = self.cari(h, project="tahap-satu")
        self.assertEqual([("2026-10-31T08:01:00+07:00", "Mulai"), ("2026-10-31T08:10:00+07:00", "Keputusan"),
                          ("2026-10-31T08:19:00+07:00", "Selesai")], [(x["waktu"], x["label"]) for x in a["langkah"]])

    def test_label_baru(self):
        self.assertEqual("Sebagian", generator.LABEL["sebagian"])
        self.assertEqual("Koreksi", generator.LABEL["koreksi"])


class TestQC(Dasar):
    def test_qc_tertaut_pasti(self):
        d, h = self.mulai()
        self.assertEqual({"hasil": "lulus bersyarat", "waktu": "2026-10-31T08:45:00+07:00"},
                         self.cari(h, project="tahap-satu")["qc"])
        for p in ("tahap-dua", "tahap-tiga", "tahap-empat", "tahap-lima"):   # verdict ambigu / tak terkait diabaikan
            self.assertIsNone(self.cari(h, project=p)["qc"])
        a = self.cari(h, project="tahap-satu")
        self.assertIn(("uci", f"QC: lulus bersyarat {a['id']}"), [(x[0], x[1]) for x in riwayat(h)])


class TestGuard(Dasar):
    def test_blok_masuk_riwayat_tanpa_argumen(self):
        d, h = self.mulai()
        r = [x[1] for x in riwayat(h)]
        self.assertIn("Alfa diblok g7-tim-guard (rahasia)", r)
        self.assertIn("Alfa diblok g7-tim-guard", r)           # kategori tak aman dibuang
        self.assertIn("Uci diblok qc-gate-g7 (hermes-container)", r)
        self.assertEqual(3, len([t for t in r if "diblok" in t]))   # keputusan izin tidak muncul

    def test_pemilik_peristiwa_ikut_misi_aktif(self):
        d = self.buat()
        h = d.siklus()
        self.assertTrue([t for t in riwayat(h["akbar"]) if "diblok" in t[1]])
        self.assertFalse([t for t in riwayat(h["dicky"]) if "diblok" in t[1]])


class TestPanggilTL(Dasar):
    def test_koordinator_memanggil_tl(self):
        d, h = self.mulai()
        r = [x[1] for x in riwayat(h)]
        self.assertEqual(2, r.count("Ajeng memanggil Beta"))
        self.assertEqual(1, r.count("Ajeng memanggil Alfa"))

    def test_hermes_p_langsung(self):
        d = self.buat()
        d.siklus()
        d.tambah_baris({"type": "tool", "role": "owner", "name": "Pak Akbar", "sid": "S3", "tool": "terminal",
                        "detail": "HOME=/opt/data hermes -p alfa -z 'KANARI-x'", "ts": "2026-10-31T08:59:00"})
        r = [x[1] for x in riwayat(d.siklus("2026-10-31T09:00:30+07:00")["akbar"])]
        self.assertEqual(2, r.count("Ajeng memanggil Alfa"))


class TestKartuLala(Dasar):
    def test_status_kartu(self):
        d, h = self.mulai()
        s1, s2 = self.kartu(h, "08:00"), self.kartu(h, "08:30")
        s3, s7 = self.kartu(h, "08:55"), self.kartu(h, "06:00")
        self.assertEqual(("selesai", "2026-10-31T08:40:00+07:00"), (s1["status"], s1["selesai"]))
        self.assertEqual(("menunggu", "anak"), (s2["status"], s2["alasan"]))
        self.assertEqual(("jalan", None), (s3["status"], s3["selesai"]))
        self.assertEqual(("berakhir", "2026-10-31T06:05:00+07:00"), (s7["status"], s7["selesai"]))
        self.assertEqual(4, len([m for m in h["misi"] if m["jenis"] == "permintaan"]))   # S4 sistem, S5 tanpa msg: tidak ada

    def test_field_kartu(self):
        d, h = self.mulai()
        s1 = self.kartu(h, "08:00")
        self.assertEqual("Permintaan Pak Akbar lewat Telegram", s1["judul"])   # isi pesan tidak dikutip
        self.assertNotIn("Tolong jalankan", json.dumps(h, ensure_ascii=False))   # teks pesan tidak ada di keluaran mana pun
        self.assertEqual(("ajeng", "Ajeng", "akbar", "Pak Akbar", [], None), (
            s1["pelaksana_id"], s1["pelaksana"], s1["pemberi_id"], s1["pemberi"], s1["subagen"], s1["jalan"]))
        self.assertEqual("2026-10-31T08:00:00+07:00", s1["mulai"])
        self.assertEqual(sorted(s1["anak"]), sorted(m["id"] for m in h["misi"] if m["project"] in ("tahap-satu", "tahap-dua")))
        for m in h["misi"]:
            if m["jenis"] == "pengerja":
                self.assertEqual([], m["anak"])
                self.assertIn("qc", m)
        self.assertEqual(s1["id"], self.cari(h, project="tahap-satu")["induk_misi"])
        self.assertEqual(self.kartu(h, "08:30")["id"], self.cari(h, project="tahap-tiga")["induk_misi"])

    def test_registri_kunci_sesi(self):
        d, h = self.mulai()
        reg = json.loads(d.nomor.read_text())["nomor"]
        self.assertEqual(4, len([k for k in reg if re.fullmatch(r"sesi:[0-9a-f]{20}", k)]))   # hash, bukan sid mentah
        self.assertFalse([k for k in reg if k == "sesi:S1"])
        self.assertEqual(reg, generator.baca_registri(d.nomor.read_text(encoding="utf-8")))

    def test_filter_penonton(self):
        d = self.buat()
        h = d.siklus()
        self.assertEqual(["Permintaan Mas Dicky lewat Telegram"], [m["judul"] for m in h["dicky"]["misi"]])
        self.assertEqual(9, len(h["akbar"]["misi"]))

    def test_agen_dan_ringkasan_konsisten(self):
        d, h = self.mulai()
        ag = {a["id"]: a for a in h["agen"]}
        self.assertEqual(("jalan", "bekerja"), (ag["ajeng"]["status"], ag["ajeng"]["keadaan"]))
        self.assertEqual(("jalan", "bekerja"), (ag["beta"]["status"], ag["beta"]["keadaan"]))
        self.assertEqual("menunggu", ag["alfa"]["keadaan"])
        self.assertEqual({"aktif": 5, "selesai_hari_ini": 4}, h["ringkasan"]["misi"])
        self.assertIn(self.kartu(h, "08:55")["id"], ag["ajeng"]["misi_aktif"])

    def test_kartu_jalan_membuat_koordinator_jalan_walau_diam(self):
        d = self.buat()
        d.tambah_baris({"type": "msg", "role": "owner", "name": "Pak Akbar", "sid": "S9", "text": "Halo lagi",
                        "ts": "2026-10-31T08:50:00"})
        ag = {a["id"]: a for a in d.siklus()["akbar"]["agen"]}
        self.assertEqual("jalan", ag["ajeng"]["status"])   # baris terakhir 10 menit lalu (> 120 dtk), kartu masih jalan

    def test_tanpa_teks_judul_sama(self):
        d = self.buat()
        d.tambah_baris({"type": "msg", "role": "owner", "name": "Pak Akbar", "sid": "S8", "ts": "2026-10-31T08:59:00"})
        h = d.siklus()["akbar"]
        self.assertIsNotNone(self.cari(h, judul="Permintaan Pak Akbar lewat Telegram", mulai="2026-10-31T08:59:00+07:00"))


def _alat(hms, sid, detail, tool="terminal", nama="Pak Akbar", profil=None):
    d = {"type": "tool", "role": "owner", "name": nama, "sid": sid, "tool": tool, "detail": detail, "ts": f"2026-10-31T{hms}"}
    if profil:
        d.update(profile=profil, name=profil)
    return d


class TestAktivitas(Dasar):
    """Field `aktivitas` per misi: baris tool sid sesi utama / jendela card; ≤50 terakhir; teks disaring & ±100 karakter."""

    def test_kartu_memuat_baris_tool_dipotong(self):
        d, h = self.mulai()
        a = self.kartu(h, "08:00")["aktivitas"]
        self.assertEqual(1, len(a))   # hanya baris tool sid S1; sid lain/msg tidak masuk
        self.assertEqual(("2026-10-31T08:00:05+07:00", "terminal"), (a[0]["waktu"], a[0]["tool"]))
        self.assertTrue(a[0]["teks"].endswith("…") and len(a[0]["teks"]) <= 101)
        self.assertNotIn("KANARI-argumen", a[0]["teks"])   # ujung perintah di luar 100 karakter tidak ikut

    def test_pengerja_hanya_sesi_utama(self):
        d = self.buat()
        d.tambah_baris(_alat("08:21:00", "SUB-A1", "bukan sesi utama", profil="alfa"))   # sid lain: bukan sesi utama misi
        h = d.siklus()["akbar"]
        a = self.cari(h, project="tahap-satu")["aktivitas"]
        self.assertEqual([{"waktu": "2026-10-31T08:20:00+07:00", "tool": "read_file", "teks": "KANARI-detail"}], a)

    def test_disaring_dan_tanpa_detail(self):
        d = self.buat()
        d.tambah_baris(_alat("09:00:00", "S3", "kirim ke a@b.id"), _alat("09:00:01", "S3", "nomor 081234567890 x"),
                       _alat("09:00:02", "S3", ""), _alat("09:00:03", "S3", "  spasi \n  rapi  "))
        a = self.kartu(d.siklus()["akbar"], "08:55")["aktivitas"]
        self.assertEqual(["(disaring)", "(disaring)", None, "spasi rapi"], [x["teks"] for x in a[1:]])

    def test_maks_50_terakhir_urut_naik(self):
        d = self.buat()
        d.tambah_baris(*[_alat(f"09:{i // 60:02d}:{i % 60:02d}", "S3", f"perintah {i}") for i in range(60)])
        a = self.kartu(d.siklus()["akbar"], "08:55")["aktivitas"]
        self.assertEqual(50, len(a))
        self.assertEqual("perintah 59", a[-1]["teks"])
        self.assertEqual("perintah 10", a[0]["teks"])
        self.assertEqual([x["waktu"] for x in a], sorted(x["waktu"] for x in a))

    def test_filter_penonton(self):
        d = self.buat()
        h = d.siklus()
        self.assertEqual(1, len(h["dicky"]["misi"]))
        self.assertEqual(1, len(h["dicky"]["misi"][0]["aktivitas"]))   # hanya card Dicky (S3)
        self.assertNotIn("tim_jalankan", json.dumps(h["dicky"]))


def _msg(hms, sid, text, nama="Pak Akbar", tgl="2026-10-31"):
    return {"type": "msg", "role": "owner", "name": nama, "sid": sid, "text": text, "ts": f"{tgl}T{hms}"}


def _tambah_jsonl(d, rel, *baris):
    with open(d.akar / rel, "a", encoding="utf-8") as f:
        for b in baris:
            f.write(json.dumps(b) + "\n")


def _ketat(teks):
    """json.loads yang menolak NaN/Infinity (seperti JSON.parse di browser)."""
    def tolak(c):
        raise ValueError(c)
    return json.loads(teks, parse_constant=tolak)


class TestKartuPerPermintaan(Dasar):
    """Satu card per PERMINTAAN: msg pemilik membuka card baru bila card sebelumnya di sid itu sudah dibalas dan sesi diam ≥ 10 mnt."""

    def jml(self, h):
        return len([m for m in h["misi"] if m["jenis"] == "permintaan"])

    def test_msg_sesudah_dibalas_dan_diam_membuka_card_baru(self):
        d = self.buat()
        d.tambah_baris(_msg("08:55:00", "S1", "Permintaan kedua di sesi yang sama."))
        h = d.siklus()["akbar"]
        lama, baru = self.kartu(h, "08:00"), self.kartu(h, "08:55", pemberi_id="akbar")
        self.assertEqual(5, self.jml(h))
        self.assertEqual(("selesai", "2026-10-31T08:40:00+07:00"), (lama["status"], lama["selesai"]))
        self.assertEqual(("jalan", None, "2026-10-31T08:55:00+07:00"), (baru["status"], baru["selesai"], baru["mulai"]))
        self.assertNotEqual(lama["id"], baru["id"])
        self.assertEqual(2, len(lama["anak"]))
        self.assertEqual([], baru["anak"])   # peluncuran 08:00 ada di jendela card pertama

    def test_balasan_langsung_selesai_tanpa_menunggu_diam(self):
        d = self.buat()
        d.tambah_baris(_msg("08:56:00", "S9", "Permintaan singkat."),
                       {"type": "reply", "role": "owner", "name": "Pak Akbar", "sid": "S9", "ts": "2026-10-31T08:57:00"})
        k = self.kartu(d.siklus("2026-10-31T08:58:00+07:00")["akbar"], "08:56")   # baru 1 mnt sesudah balasan (< DIAM)
        self.assertEqual(("selesai", "2026-10-31T08:57:00+07:00"), (k["status"], k["selesai"]))

    def test_msg_dalam_jeda_pendek_masuk_card_sama_dan_reset_balasan(self):
        d = self.buat()
        d.tambah_baris(_msg("08:45:00", "S1", "Tambahan kecil untuk permintaan tadi."))   # 5 mnt sesudah balasan
        h = d.siklus()["akbar"]
        self.assertEqual(4, self.jml(h))
        s1 = self.kartu(h, "08:00")
        self.assertEqual(("jalan", None), (s1["status"], s1["selesai"]))   # balasan 08:40 tidak berlaku lagi

    def test_msg_tanpa_balasan_tidak_membuka_card_baru(self):
        d = self.buat()
        d.tambah_baris(_msg("08:20:00", "S2", "Msg kedua sebelum ada balasan sama sekali."))
        self.assertEqual(4, self.jml(d.siklus()["akbar"]))

    def test_sesi_cron_bukan_permintaan(self):
        d = self.buat()
        d.tambah_baris(_msg("08:50:00", "cron_ab12_20261031_085000", "[IMPORTANT: You are running as a scheduled job"))
        h = d.siklus()["akbar"]
        self.assertEqual(4, self.jml(h))
        self.assertFalse([m for m in h["misi"] if m["judul"].startswith("[IMPORTANT")])

    def test_kunci_registri_hash_dan_hanya_card_dimuat(self):
        d = self.buat()
        d.tambah_baris(_msg("10:00:00", "LAMA", "Permintaan kemarin yang sudah lewat.", tgl="2026-10-30"),
                       {"type": "reply", "role": "owner", "name": "Pak Akbar", "sid": "LAMA", "ts": "2026-10-30T10:05:00"})
        h = d.siklus()["akbar"]
        teks = d.nomor.read_text(encoding="utf-8")
        reg = json.loads(teks)["nomor"]
        kartu = [k for k in reg if k.startswith("sesi:")]
        self.assertEqual(self.jml(h), len(kartu))   # card kemarin tidak menghabiskan nomor
        self.assertTrue(all(re.fullmatch(r"sesi:[0-9a-f]{20}", k) for k in kartu))
        self.assertNotIn("S1", " ".join(kartu))
        g2 = d.generator(nomor=d.nomor)   # backfill ulang: kunci stabil, tanpa entri baru
        d.siklus(g=g2)
        self.assertEqual(teks, d.nomor.read_text(encoding="utf-8"))

    def test_registri_kunci_ketat(self):
        sah = {"x.md": 1, "sesi:" + "a" * 20: 2}
        self.assertEqual(sah, generator.baca_registri(json.dumps({"versi": 1, "nomor": sah})))
        for k in ("sesi:S1", "sesi:" + "A" * 20, "sesi:" + "a" * 21, "a/b.md", "", "sesi:x/y"):
            with self.subTest(k=k), self.assertRaises(ValueError):
                generator.baca_registri(json.dumps({"versi": 1, "nomor": {k: 1}}))

    def test_sid_lama_dibuang_dari_memori(self):
        d = self.buat()
        d.siklus()
        self.assertIn("S7", d.g.k_sesi)
        d.siklus("2026-11-03T09:00:00+07:00")
        self.assertNotIn("S7", d.g.k_sesi)
        self.assertNotIn("S1", d.g.k_sesi)


class TestNaN(Dasar):
    def test_nan_infinity_jalan_ditolak(self):
        d = self.buat()
        p = d.akar / "workspace/handoff/jalan-20261031T080000.json"
        p.write_text(p.read_text().replace('"rc": 0', '"rc": NaN').replace('"durasi_detik": 60.0', '"durasi_detik": Infinity'))
        h = d.siklus()["akbar"]
        self.assertEqual([], h["galat"])
        self.assertEqual({"status": "selesai", "rc": None, "durasi_detik": None, "laporan": True},
                         self.cari(h, project="tahap-satu")["jalan"])
        _ketat((d.keluaran / "akbar.json").read_text(encoding="utf-8"))

    def test_keluaran_non_finit_siklus_gagal_tanpa_menimpa(self):
        d = self.buat()
        d.siklus()
        lama = (d.keluaran / "akbar.json").read_text(encoding="utf-8")
        buf = io.StringIO()
        with unittest.mock.patch.object(generator.Generator, "_berkas", return_value={"x": float("nan")}), \
                contextlib.redirect_stdout(buf):
            ok = generator.Lapor(d.g, time.monotonic).siklus(datetime.fromisoformat("2026-10-31T09:00:00+07:00"))
        self.assertFalse(ok)   # dilaporkan sebagai siklus gagal, tidak melempar
        self.assertIn("siklus gagal: ValueError", buf.getvalue())
        self.assertEqual(lama, (d.keluaran / "akbar.json").read_text(encoding="utf-8"))


class TestGuardAtribusi(Dasar):
    BRIEF_G = ("Dari: Lala\nPeminta: Mas Dicky\nProject: tahap-enam\nKunci: tl=alfa\n" + "x" * 250 + "\nisi\n")

    def buat_dunia(self, *guard):
        d = self.buat()
        (d.akar / "workspace/brief/2026-10-31-tahap-enam-g.md").write_text(self.BRIEF_G)
        d.tambah_baris({"type": "msg", "role": "tim", "name": "Alfa", "profile": "alfa", "sid": "A2", "text": self.BRIEF_G[:300],
                        "ts": "2026-10-31T08:25:00"},
                       {"type": "tool", "role": "tim", "name": "Alfa", "profile": "alfa", "sid": "A2", "tool": "read_file",
                        "detail": "x", "blocked": False, "ts": "2026-10-31T08:51:00"})   # misi Dicky terbuka 08:25-08:51
        _tambah_jsonl(d, "guard/g7-tim-guard.jsonl", *[
            {"ts": f"2026-10-31T{w}+07:00", "profile": "alfa", "tool": "terminal", "kategori": k, "keputusan": "blok"}
            for w, k in guard])
        return d, d.siklus()

    def teks(self, h, p):
        return [x[1] for x in riwayat(h[p]) if "diblok" in x[1]]

    def test_pemilik_menurut_misi_pada_waktu_peristiwa(self):
        d, h = self.buat_dunia(("08:26:00", "pada-enam"), ("08:50:00", "dua-misi"), ("07:00:00", "sebelum-misi"))
        self.assertIsNotNone(self.cari(h["akbar"], pemberi_id="dicky", pelaksana_id="alfa"))
        self.assertIn("Alfa diblok g7-tim-guard (pada-enam)", self.teks(h, "dicky"))      # hanya misi Dicky aktif saat itu
        self.assertNotIn("Alfa diblok g7-tim-guard (dua-misi)", self.teks(h, "dicky"))    # 2 pemilik -> pemilik tim
        self.assertNotIn("Alfa diblok g7-tim-guard (sebelum-misi)", self.teks(h, "dicky"))
        for k in ("pada-enam", "dua-misi", "sebelum-misi"):
            self.assertIn(f"Alfa diblok g7-tim-guard ({k})", self.teks(h, "akbar"))

    def test_throttle_blok_berulang_5_menit(self):
        d = self.buat()
        _tambah_jsonl(d, "guard/qc-gate-g7.jsonl", *[
            {"ts": f"2026-10-31T{w}+07:00", "profile": "uci", "jenis": "hermes-container", "keputusan": "blok"}
            for w in ("08:49:00", "08:50:00", "08:54:30")])   # dasar: 08:48
        r = [x[1] for x in riwayat(d.siklus()["akbar"])]
        self.assertEqual(2, r.count("Uci diblok qc-gate-g7 (hermes-container)"))   # 08:48 dan 08:54:30

    def test_riwayat_lock_pemilik_menurut_misi_bila_diketahui(self):
        d = self.buat()
        (d.akar / "workspace/brief/2026-10-31-tahap-enam-g.md").write_text(self.BRIEF_G)
        d.tambah_baris({"type": "msg", "role": "tim", "name": "Alfa", "profile": "alfa", "sid": "A2", "text": self.BRIEF_G[:300],
                        "ts": "2026-10-31T08:25:00"})
        (d.akar / "workspace/locks/tahap-enam.lock").write_text(
            "tl=alfa\nmulai=2026-10-31T08:25:00+07:00\nbrief=/workspace/brief/2026-10-31-tahap-enam-g.md\noleh=ajeng\n")
        _tambah_jsonl(d, "workspace/locks/.tim_kunci.riwayat.jsonl",
                      {"ts": "2026-10-31T08:25:00+07:00", "perintah": "kunci", "kunci": "tahap-enam", "tl": "alfa", "oleh": "ajeng", "pid": 7})
        h = d.siklus()
        self.assertIn("Alfa mulai tahap-enam", [x[1] for x in riwayat(h["dicky"])])
        self.assertIn("Alfa mulai tahap-enam", [x[1] for x in riwayat(h["akbar"])])
        self.assertNotIn("Alfa mulai Tahap Satu", [x[1] for x in riwayat(h["dicky"])])   # lock tak dikenal = pemilik tim saja


class TestRentangWaktu(Dasar):
    def test_handoff_sesudah_selesai_misi_dibuang(self):
        d = self.buat()
        with open(d.akar / "workspace/handoff/tahap-satu.md", "a") as f:
            f.write("### 2026-10-31 08:30 WIB — alfa — Status: langkah\nKANARI-handoff\n")   # misi selesai 08:20
        a = self.cari(d.siklus()["akbar"], project="tahap-satu")
        self.assertEqual(["08:01:00", "08:10:00", "08:19:00"], [x["waktu"][11:19] for x in a["langkah"]])

    def test_qc_disaring_waktu_sebelum_ambigu(self):
        d = self.buat()
        (d.akar / "workspace/verdict/20261031-0815-tahap-dua-b-tahap-tiga-c.json").write_text(json.dumps(
            {"verdict": "LULUS", "dibuat": "2026-10-31T08:15:00+07:00", "brief": "KANARI-brief-qc", "oleh": "uci"}))
        h = d.siklus()["akbar"]   # tahap-tiga baru mulai 08:30, jadi verdict 08:15 hanya cocok dengan tahap-dua
        self.assertEqual({"hasil": "lulus", "waktu": "2026-10-31T08:15:00+07:00"}, self.cari(h, project="tahap-dua")["qc"])
        self.assertIsNone(self.cari(h, project="tahap-tiga")["qc"])
