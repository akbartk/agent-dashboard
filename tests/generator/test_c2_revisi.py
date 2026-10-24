"""Uji KONTRAK C2 revisi (CTO 24 Okt 12.3x, Q2 Beta; koreksi 1 KB3, TL Beta, 24 Okt 2026).

C2: (1) agen punya ≥ 1 misi aktif terlihat di berkas → `menunggu` bila semuanya `menunggu`, else `bekerja`;
(2) `status` = `sibuk`/`bebas` → nilai itu; (3) `status` = `menunggu` → `menunggu`; (4) selain itu `bekerja`.
Kasus yang berubah: di berkas V (dicky/jati), TL yang menjalankan misi V tanpa lock untuk brief itu ber-`status` `sibuk`
(§3.3: tidak punya tugas milik V), padahal punya misi aktif V → `keadaan` harus dari misi, bukan `sibuk`.
"""
import json
import unittest

from bantu_misi import DasarMisi, agen, misi


class UjiC2Revisi(DasarMisi):
    def dunia_carli_tanpa_lock(self, anak_via=False):
        d = self.buat()
        (d.akar / "workspace" / "locks" / "policytrack.lock").unlink()  # brief T-005 (milik dicky) tanpa lock
        b5 = (d.akar / "workspace" / "brief" / "2026-10-24-carli-policytrack-rubi.md").read_text(encoding="utf-8")
        d.proses(3301, d.HERMES + ["-p", "carli", "-z", b5], 1)
        if anak_via:  # Carli menunggu proses Via (misi akbar T-006) yang menjadi keturunannya
            b6 = (d.akar / "workspace" / "brief" / "2026-10-24-via-pemahaman-asn-mutiara.md").read_text(encoding="utf-8")
            d.proses(3302, ["/bin/bash", "-c", "KANARI-argv"], 3301, comm="bash")
            d.proses(3401, d.HERMES + ["-p", "via", "-z", b6], 3302)
        return d.siklus()

    def test_agen_sibuk_di_berkas_v_dengan_misi_v_jalan_menjadi_bekerja(self):
        h = self.dunia_carli_tanpa_lock()
        dk = h["dicky"]
        self.assertEqual("jalan", misi(dk, "T-005")["status"])
        c = agen(dk, "carli")
        self.assertEqual(("sibuk", "bekerja", ["T-005"]), (c["status"], c["keadaan"], c["misi_aktif"]))
        self.assertEqual({"bekerja": 1, "menunggu": 0, "bebas": 2, "sibuk": 4}, dk["ringkasan"]["agen"])
        self.assertEqual(("jalan", "bekerja"), (agen(h["akbar"], "carli")["status"], agen(h["akbar"], "carli")["keadaan"]))
        self.assertEqual(("sibuk", []), (agen(h["jati"], "carli")["keadaan"], agen(h["jati"], "carli")["misi_aktif"]))

    def test_agen_sibuk_di_berkas_v_dengan_semua_misi_v_menunggu_menjadi_menunggu(self):
        h = self.dunia_carli_tanpa_lock(anak_via=True)
        dk = h["dicky"]
        m = misi(dk, "T-005")
        self.assertEqual(("menunggu", "misi-lain", []), (m["status"], m["alasan"], m["menunggu_misi"]))
        c = agen(dk, "carli")
        self.assertEqual(("sibuk", "menunggu", ["T-005"]), (c["status"], c["keadaan"], c["misi_aktif"]))
        self.assertEqual({"bekerja": 0, "menunggu": 1, "bebas": 1, "sibuk": 5}, dk["ringkasan"]["agen"])  # via kini sibuk (proses misi akbar)
        self.assertNotRegex(json.dumps(dk, ensure_ascii=False), r"\bT-006\b")  # isolasi C7 tetap


if __name__ == "__main__":
    unittest.main()
