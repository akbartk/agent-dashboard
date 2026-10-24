"""Uji hooks/team-activity.py (KONTRAK §6 dan §6a). unittest stdlib; hook dijalankan sebagai subprocess
dengan payload JSON di stdin, persis cara Hermes memanggil shell hook. Data uji netral (tim_contoh.json)."""
import json
import os
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ASAL = Path(__file__).resolve().parent
AKAR = ASAL.parent.parent
HOOK = AKAR / "hooks" / "team-activity.py"
TIM_CONTOH = ASAL / "tim_contoh.json"
KERJA = AKAR / "tmp" / "test" / "infra"  # semua keluaran uji di tmp/test (standar aplikasi), dibersihkan sesudahnya
RE_TS = re.compile(r"\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d")
_KERJA_BARU = False


def setUpModule():
    global _KERJA_BARU
    _KERJA_BARU = not KERJA.exists()
    KERJA.mkdir(parents=True, exist_ok=True)


def tearDownModule():
    if _KERJA_BARU:
        try:
            KERJA.rmdir()  # tiap uji sudah menghapus folder sementaranya sendiri; rmdir menolak bila masih ada isi
        except OSError:
            pass


def payload_tool(profile="satu", tool="terminal", args=None, sid="sid-1"):
    return {"hook_event_name": "pre_tool_call", "tool_name": tool,
            "tool_input": {"command": "ls -la"} if args is None else args,
            "session_id": sid, "cwd": "/contoh", "profile": profile, "extra": {}}


def payload_msg(profile="satu", teks="halo dunia", platform="cli", sid="sid-1"):
    return {"hook_event_name": "pre_llm_call", "session_id": sid, "cwd": "/contoh", "profile": profile,
            "extra": {"user_message": teks, "platform": platform, "sender_id": ""}}


def payload_balas(profile="koord", jawaban="oke", sid="sid-1"):
    return {"hook_event_name": "post_llm_call", "session_id": sid, "cwd": "/contoh", "profile": profile,
            "extra": {"user_message": "tanya", "assistant_response": jawaban, "platform": "cli"}}


class DasarHook(unittest.TestCase):
    def setUp(self):
        self._td = tempfile.TemporaryDirectory(dir=KERJA)
        self.dir = Path(self._td.name)
        self.log = self.dir / "activity.jsonl"
        self.addCleanup(self._td.cleanup)

    def tim(self, **aktivitas):
        """Tulis tim.json uji; tanpa argumen = tanpa kunci `aktivitas`."""
        d = json.loads(TIM_CONTOH.read_text(encoding="utf-8"))
        if aktivitas:
            d["aktivitas"] = aktivitas
        p = self.dir / "tim.json"
        p.write_text(json.dumps(d), encoding="utf-8")
        return p

    def jalan(self, payload, tim="SAMA", log="SAMA", mentah=None):
        env = {k: v for k, v in os.environ.items() if k not in ("TEAM_ACTIVITY_LOG", "AD_TIM")}
        tim = self.tim() if tim == "SAMA" else tim
        log = self.log if log == "SAMA" else log
        if tim is not None:
            env["AD_TIM"] = str(tim)
        if log is not None:
            env["TEAM_ACTIVITY_LOG"] = str(log)
        stdin = mentah if mentah is not None else json.dumps(payload)
        return subprocess.run([sys.executable, str(HOOK)], input=stdin, capture_output=True, text=True,
                              env=env, timeout=20)

    def baris(self):
        if not self.log.exists():
            return []
        return [json.loads(b) for b in self.log.read_text(encoding="utf-8").splitlines()]

    def satu_baris(self, payload, **kw):
        r = self.jalan(payload, **kw)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((r.stdout, r.stderr), ("", ""))
        b = self.baris()
        self.assertEqual(len(b), 1, b)
        return b[0]

    def tidak_menulis(self, r):
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual((r.stdout, r.stderr), ("", ""))
        self.assertFalse(self.log.exists())
        self.assertEqual([p.name for p in self.dir.iterdir() if p.name != "tim.json"], [])


class TestHookAda(unittest.TestCase):
    def test_berkas_hook_ada(self):
        self.assertTrue(HOOK.is_file(), f"{HOOK} belum ada")


class TestFormatBaris(DasarHook):
    """(a) satu baris jsonl sesuai §6; name dari tim.json."""

    def test_tool_tim_metadata_saja(self):
        b = self.satu_baris(payload_tool())
        self.assertEqual(set(b), {"type", "role", "name", "profile", "sid", "tool", "blocked", "ts"})
        self.assertEqual((b["type"], b["role"], b["name"], b["profile"], b["sid"], b["tool"], b["blocked"]),
                         ("tool", "tim", "Agen Satu", "satu", "sid-1", "terminal", False))
        self.assertRegex(b["ts"], RE_TS)

    def test_msg_tim_metadata_saja(self):
        b = self.satu_baris(payload_msg(profile="dua"))
        self.assertEqual(set(b), {"type", "role", "name", "profile", "sid", "ts"})
        self.assertEqual((b["type"], b["role"], b["name"], b["profile"]), ("msg", "tim", "Agen Dua", "dua"))

    def test_baris_ditambahkan_bukan_ditimpa(self):
        self.jalan(payload_tool())
        self.jalan(payload_msg())
        self.assertEqual([x["type"] for x in self.baris()], ["tool", "msg"])

    def test_folder_log_dibuat(self):
        dalam = self.dir / "a" / "b" / "activity.jsonl"
        r = self.jalan(payload_tool(), log=dalam)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(len(dalam.read_text(encoding="utf-8").splitlines()), 1)

    def test_event_lain_tidak_dicatat(self):
        p = payload_tool()
        p["hook_event_name"] = "post_tool_call"
        r = self.jalan(p)
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.baris(), [])

    def test_sesi_sintetis_diabaikan(self):
        r = self.jalan(payload_tool(sid="test-session"))
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.baris(), [])

    def test_balasan_agen_tim_tidak_dicatat(self):
        r = self.jalan(payload_balas(profile="satu"))
        self.assertEqual(r.returncode, 0)
        self.assertEqual(self.baris(), [])

    def test_sub_dan_sistem_tetap_ada(self):
        b = self.satu_baris(payload_msg(platform="subagent"))
        self.assertIs(b["sub"], True)
        self.assertNotIn("sistem", b)
        self.log.unlink()
        b = self.satu_baris(payload_msg(teks="[IMPORTANT: Background process 7 selesai]"))
        self.assertIs(b["sistem"], True)
        self.assertNotIn("sub", b)
        self.assertNotIn("text", b)


class TestEnvTidakSah(DasarHook):
    """(b) env log tidak diset; (c) payload rusak; (g) AD_TIM tidak diset / tim.json rusak."""

    def test_b_log_tidak_diset(self):
        self.tidak_menulis(self.jalan(payload_tool(), log=None))

    def test_b_log_kosong(self):
        self.tidak_menulis(self.jalan(payload_tool(), log=""))

    def test_c_payload_rusak(self):
        for mentah in ("{bukan json", "", "[1, 2]", "null", '"teks"', "123"):
            with self.subTest(mentah=mentah):
                self.tidak_menulis(self.jalan(None, mentah=mentah))

    def test_c_tool_input_bukan_objek(self):
        p = payload_tool()
        p["tool_input"] = "teks"
        r = self.jalan(p)
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))

    def test_g_ad_tim_tidak_diset(self):
        self.tidak_menulis(self.jalan(payload_tool(), tim=None))

    def test_g_tim_json_tidak_sah(self):
        kasus = {"rusak": "{bukan json", "kosong": "", "bukan-objek": "[1]",
                 "tanpa-koordinator": json.dumps({"pemilik": "p", "orang": [], "agen": {}}),
                 "tanpa-pemilik": json.dumps({"koordinator": "k", "orang": [], "agen": {}}),
                 "agen-bukan-objek": json.dumps({"koordinator": "k", "pemilik": "p", "orang": [], "agen": []})}
        for nama, isi in kasus.items():
            with self.subTest(nama):
                (self.dir / "tim.json").write_text(isi, encoding="utf-8")
                r = self.jalan(payload_tool(), tim=self.dir / "tim.json")
                self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
                self.assertFalse(self.log.exists())

    def test_g_tim_json_tidak_ada(self):
        r = self.jalan(payload_tool(), tim=self.dir / "tidak-ada.json")
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        self.assertFalse(self.log.exists())


class TestKoordinator(DasarHook):
    """(d) profil koordinator -> role owner, name = nama pemilik; tanpa kunci profile (jalur koordinator generator)."""

    def test_pesan_masuk(self):
        b = self.satu_baris(payload_msg(profile="koord"))
        self.assertEqual(set(b), {"type", "role", "name", "sid", "ts"})
        self.assertEqual((b["type"], b["role"], b["name"]), ("msg", "owner", "Pemilik Contoh"))

    def test_tool(self):
        b = self.satu_baris(payload_tool(profile="koord"))
        self.assertEqual(set(b), {"type", "role", "name", "sid", "tool", "blocked", "ts"})
        self.assertEqual((b["role"], b["name"], b["tool"], b["blocked"]), ("owner", "Pemilik Contoh", "terminal", False))

    def test_balasan_tanpa_isi(self):
        b = self.satu_baris(payload_balas(jawaban="isi balasan rahasia"))
        self.assertEqual(set(b), {"type", "role", "name", "sid", "ts"})
        self.assertEqual((b["type"], b["role"], b["name"]), ("reply", "owner", "Pemilik Contoh"))
        self.assertNotIn("rahasia", self.log.read_text(encoding="utf-8"))

    def test_balasan_kosong_tidak_dicatat(self):
        for kosong in ("", "   ", None):
            with self.subTest(kosong=kosong):
                self.jalan(payload_balas(jawaban=kosong))
                self.assertEqual(self.baris(), [])

    def test_subagent_koordinator_tidak_dicatat_sebagai_pemilik(self):
        r = self.jalan(payload_msg(profile="koord", platform="subagent"))
        self.assertEqual((r.returncode, r.stdout, r.stderr), (0, "", ""))
        self.assertEqual(self.baris(), [])

    def test_notifikasi_sistem(self):
        b = self.satu_baris(payload_msg(profile="koord", teks="[INTERNAL NOTIFICATION] selesai"))
        self.assertIs(b["sistem"], True)
        self.assertEqual(b["role"], "owner")
        self.assertNotIn("text", b)


class TestPrivasiDefault(DasarHook):
    """(e) §6a: default tanpa isi; kunci text/detail TIDAK ADA (bukan string kosong)."""

    def varian(self):
        yield "tanpa-aktivitas", self.tim()
        yield "kedua-false", self.tim(catat_teks=False, catat_detail=False)
        yield "hanya-batas", self.tim(teks_maks=50, detail_maks=50)

    def test_msg_dan_tool_tanpa_isi(self):
        for nama, tim in self.varian():
            for pay, tipe in ((payload_msg(teks="isi pesan penting"), "msg"),
                              (payload_tool(args={"command": "cat sesuatu"}), "tool")):
                with self.subTest(varian=nama, tipe=tipe):
                    if self.log.exists():
                        self.log.unlink()
                    b = self.satu_baris(pay, tim=tim)
                    self.assertEqual(b["type"], tipe)
                    self.assertNotIn("text", b)
                    self.assertNotIn("detail", b)
                    teks = self.log.read_text(encoding="utf-8")
                    self.assertNotIn("isi pesan penting", teks)
                    self.assertNotIn("cat sesuatu", teks)

    def test_hanya_satu_yang_dinyalakan(self):
        b = self.satu_baris(payload_msg(teks="halo"), tim=self.tim(catat_teks=False, catat_detail=True))
        self.assertNotIn("text", b)
        self.log.unlink()
        b = self.satu_baris(payload_tool(args={"command": "ls"}), tim=self.tim(catat_teks=True, catat_detail=False))
        self.assertNotIn("detail", b)

    def test_bukan_boolean_true_tetap_off(self):
        for nilai in ("true", "True", "ya", 1, 1.0, [True], {"a": 1}, None):
            with self.subTest(nilai=nilai):
                if self.log.exists():
                    self.log.unlink()
                tim = self.tim(catat_teks=nilai, catat_detail=nilai)
                self.assertNotIn("text", self.satu_baris(payload_msg(), tim=tim))
                self.log.unlink()
                self.assertNotIn("detail", self.satu_baris(payload_tool(), tim=tim))

    def test_aktivitas_bukan_objek_tetap_off(self):
        d = json.loads(TIM_CONTOH.read_text(encoding="utf-8"))
        d["aktivitas"] = "nyala"
        p = self.dir / "tim.json"
        p.write_text(json.dumps(d), encoding="utf-8")
        self.assertNotIn("text", self.satu_baris(payload_msg(), tim=p))


class TestPrivasiNyala(DasarHook):
    """(f) catat_teks/catat_detail true: samarkan DULU, potong sesudahnya; batas maks tidak sah -> 300/1000."""

    def test_teks_disamarkan_lalu_dipotong(self):
        teks = "a" * 10 + " password=hunter2rahasia"
        b = self.satu_baris(payload_msg(teks=teks), tim=self.tim(catat_teks=True, teks_maks=20))
        self.assertEqual(b["text"], "aaaaaaaaaa password=")  # potong-dulu-baru-samarkan akan menyisakan "...password=h"
        self.assertNotIn("hunter2", self.log.read_text(encoding="utf-8"))

    def test_teks_rahasia_beragam_disamarkan(self):
        teks = ("tolong pakai token: abc123XYZ dan api_key=KUNCI-9 juga PASSWORD = hunter2 "
                "header Authorization: Bearer eyJhbGciOi.payload.sig serta sk-ant-oat01-AbCdEfGh1234567890")
        b = self.satu_baris(payload_msg(teks=teks), tim=self.tim(catat_teks=True))
        for bocor in ("abc123XYZ", "KUNCI-9", "hunter2", "eyJhbGciOi", "AbCdEfGh1234567890"):
            self.assertNotIn(bocor, b["text"])
        self.assertIn("tolong pakai", b["text"])

    def test_teks_utuh_bila_tidak_ada_rahasia(self):
        b = self.satu_baris(payload_msg(teks="halo dunia\nbaris dua"), tim=self.tim(catat_teks=True))
        self.assertEqual(b["text"], "halo dunia\nbaris dua")

    def test_detail_dipotong_50(self):
        b = self.satu_baris(payload_tool(args={"command": "x" * 200}), tim=self.tim(catat_detail=True, detail_maks=50))
        self.assertEqual(b["detail"], "x" * 50)

    def test_detail_disamarkan(self):
        b = self.satu_baris(payload_tool(args={"command": "curl -H 'Authorization: Bearer abcDEF123' --password=hunter2 x"}),
                            tim=self.tim(catat_detail=True))
        self.assertNotIn("abcDEF123", b["detail"])
        self.assertNotIn("hunter2", b["detail"])

    def test_detail_urutan_kunci(self):
        tim = self.tim(catat_detail=True)
        urut = [({"path": "p1", "command": "ls"}, "ls"), ({"url": "u", "path": "p1"}, "p1"),
                ({"url": "u", "goal": "g"}, "g"), ({"url": "u"}, "u"), ({"query": "q", "goal": "g"}, "q"),
                ({"foo": 1}, json.dumps({"foo": 1}, ensure_ascii=False))]
        for args, harap in urut:
            with self.subTest(args=args):
                if self.log.exists():
                    self.log.unlink()
                self.assertEqual(self.satu_baris(payload_tool(args=args), tim=tim)["detail"], harap)

    def test_teks_maks_default_dan_tidak_sah_300(self):
        panjang = "k" * 2500
        for nilai in ("DEFAULT", 0, -5, 2001, "20", 20.5, True, None, [20]):
            with self.subTest(teks_maks=nilai):
                if self.log.exists():
                    self.log.unlink()
                akt = {"catat_teks": True} if nilai == "DEFAULT" else {"catat_teks": True, "teks_maks": nilai}
                b = self.satu_baris(payload_msg(teks=panjang), tim=self.tim(**akt))
                self.assertEqual(len(b["text"]), 300)

    def test_teks_maks_batas_sah(self):
        panjang = "k" * 2500
        for nilai, harap in ((1, 1), (2000, 2000)):
            with self.subTest(teks_maks=nilai):
                if self.log.exists():
                    self.log.unlink()
                b = self.satu_baris(payload_msg(teks=panjang), tim=self.tim(catat_teks=True, teks_maks=nilai))
                self.assertEqual(len(b["text"]), harap)

    def test_detail_maks_default_dan_tidak_sah_1000(self):
        panjang = "d" * 5000
        for nilai in ("DEFAULT", 0, -1, 4001, "50", 50.5, True, None):
            with self.subTest(detail_maks=nilai):
                if self.log.exists():
                    self.log.unlink()
                akt = {"catat_detail": True} if nilai == "DEFAULT" else {"catat_detail": True, "detail_maks": nilai}
                b = self.satu_baris(payload_tool(args={"command": panjang}), tim=self.tim(**akt))
                self.assertEqual(len(b["detail"]), 1000)

    def test_detail_maks_batas_sah(self):
        panjang = "d" * 5000
        for nilai, harap in ((1, 1), (4000, 4000)):
            with self.subTest(detail_maks=nilai):
                if self.log.exists():
                    self.log.unlink()
                b = self.satu_baris(payload_tool(args={"command": panjang}),
                                    tim=self.tim(catat_detail=True, detail_maks=nilai))
                self.assertEqual(len(b["detail"]), harap)

    def test_sub_dan_sistem_tetap_ada_saat_teks_nyala(self):
        b = self.satu_baris(payload_msg(platform="subagent", teks="[IMPORTANT: Background process 3 selesai]"),
                            tim=self.tim(catat_teks=True))
        self.assertIs(b["sub"], True)
        self.assertIs(b["sistem"], True)
        self.assertIn("text", b)

    def test_koordinator_teks_nyala(self):
        b = self.satu_baris(payload_msg(profile="koord", teks="pesan token=rahasia1"), tim=self.tim(catat_teks=True))
        self.assertEqual((b["role"], b["name"]), ("owner", "Pemilik Contoh"))
        self.assertEqual(b["text"], "pesan token=***")


if __name__ == "__main__":
    unittest.main()
