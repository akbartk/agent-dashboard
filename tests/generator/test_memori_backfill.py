"""Uji memori backfill (koreksi 1 KB2, TL Beta, 24 Okt 2026): activity.jsonl dibaca baris demi baris, tidak sekaligus.

Unit live memakai MemoryMax=64M sedangkan activity.jsonl ±17 MB. Membaca seluruh sisa berkas sekaligus (bytes + salinan
irisan + str hasil decode + daftar baris) membuat puncak memori backfill beberapa kali ukuran log; terukur 24 Okt 2026:
unit uji ka-uji-mem-baru berakhir `oom-kill`. Perilaku keluaran dijaga oleh tes lain (UjiLog di test_generator.py).
"""
import tracemalloc
import unittest

from bantu_misi import DasarMisi

UKURAN_BANTALAN = 4 << 20  # 4 MiB baris bantalan


class UjiMemoriBackfill(DasarMisi):
    def puncak_siklus(self, bantalan):
        """Puncak memori Python (tracemalloc) selama satu siklus backfill pada dunia misi1 + `bantalan` byte baris dilewati."""
        d = self.buat()
        # JSON sah tanpa `ts` (dilewati tanpa keadaan); karakter non-BMP membuat str hasil decode 4 byte/karakter
        baris = ('{"pad": "' + "\U0001F600" * 40 + "x" * 60 + '"}\n').encode("utf-8")
        n = bantalan // len(baris) + 1 if bantalan else 0
        with open(d.akar / "activity.jsonl", "ab") as f:
            f.write(baris * n)
        tracemalloc.start()
        try:
            awal = tracemalloc.get_traced_memory()[0]
            tracemalloc.reset_peak()
            h = d.siklus()
            puncak = tracemalloc.get_traced_memory()[1] - awal
        finally:
            tracemalloc.stop()
        self.assertEqual([], h["akbar"]["galat"])
        self.assertGreaterEqual(d.g.baris_dilewati, n)
        return puncak, (d.akar / "activity.jsonl").stat().st_size

    def test_puncak_memori_backfill_tidak_tumbuh_dengan_ukuran_log(self):
        dasar, _ = self.puncak_siklus(0)
        besar, ukuran = self.puncak_siklus(UKURAN_BANTALAN)
        self.assertLess(besar - dasar, ukuran // 8, f"puncak {besar} B (dasar {dasar} B) untuk log {ukuran} B")


if __name__ == "__main__":
    unittest.main()
