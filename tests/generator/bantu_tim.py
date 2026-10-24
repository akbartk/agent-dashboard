"""Bantuan uji: config tim untuk dunia uji. Basis = DATA uji `tests/fixtures/<skenario>/tim.json` (bukan `conf/`);
path `sumber` di fixture relatif, `tulis_tim()` menggantinya dengan path dunia uji (direktori sementara)."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FIXTURE = ROOT / "tests" / "fixtures"
DASAR = FIXTURE / "skenario1" / "tim.json"


def muat(dasar=DASAR):
    return json.loads(Path(dasar).read_text(encoding="utf-8"))


def sumber_dunia(akar):
    akar = Path(akar)
    return {"activity": str(akar / "activity.jsonl"), "profil": str(akar / "profiles"), "workspace": str(akar / "workspace"),
            "workspace_kontainer": "/workspace", "brief": str(akar / "workspace" / "brief"),
            "lock": str(akar / "workspace" / "locks"), "handoff": None, "proc": str(akar / "proc")}


def tulis_tim(tujuan, akar, dasar=DASAR, agen=None, mentah=None, **ubah):
    """Tulis config tim dunia uji ke `tujuan`. `mentah` = isi apa adanya (uji berkas tidak sah); `agen` mengganti
    seluruh nilai kunci `agen`; `ubah` mengganti kunci tingkat atas lain."""
    tujuan = Path(tujuan)
    if mentah is not None:
        tujuan.write_text(mentah, encoding="utf-8")
        return tujuan
    cfg = muat(dasar)
    cfg["sumber"] = sumber_dunia(akar)
    if agen is not None:
        cfg["agen"] = agen
    cfg.update(ubah)
    tujuan.write_text(json.dumps(cfg, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return tujuan
