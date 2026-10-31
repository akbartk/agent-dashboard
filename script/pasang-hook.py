"""Pasang hook aktivitas agent-dashboard (docs/pasang-g7.md Langkah F) di semua profil agen tim.json.
Jalan di DALAM container Hermes (butuh ruamel dari venv Hermes). Berkas ini disimpan di project; jalankan lewat pipa:

  ssh <host> cat <AKAR>/script/pasang-hook.py > <scratch>/pasang-hook.py   # simpan dulu, cocokkan sha256 dengan verdict QC
  HERMES_HOME=<akar data Hermes> /opt/hermes/.venv/bin/python <scratch>/pasang-hook.py <mode> <host> <AKAR>

HERMES_HOME WAJIB akar data Hermes (yang memuat config.yaml dan profiles/), bukan folder satu profil: sesi profil Hermes
mengekspor HERMES_HOME=<akar>/profiles/<p>, jadi setel eksplisit. Path di-resolve dan divalidasi di semua mode.

  mode: cek | uji (tampilkan diff config, tanpa menulis) | pasang | perbarui | rollback | bersihkan

`perbarui` hanya mengganti isi salinan hook dan salinan tim.json hook (atomik, mode berkas lama dipertahankan, cadangan
`<berkas>.lama-<YYYYmmddTHHMMSS>` hanya bila isi berubah, sebelum mengganti hook baru diuji-jalan di folder sementara,
verifikasi sha256 lewat `cek`) TANPA menyentuh config/allowlist: approval Hermes dikunci per (event, command), bukan isi
berkas, dan hook dispawn per panggilan (tanpa restart). Tanpa perubahan = tidak ada cadangan. Rollback: perintah `mv -f`
yang dicetak (satu per berkas yang diganti).

Rollback dua tahap (verdict G7-QC 20261025-1809 K1/M1, 1820 M2): `rollback` hanya mencabut entri yang merujuk berkas
hook (di semua profil di disk) dari config + approval allowlist (perubahan lain sesudah pasang tetap utuh) dan TIDAK menghapus berkas hook, karena proses yang masih hidup tetap
memanggilnya dan berkas yang hilang = python rc 2 = pre_tool_call diblok. Restart gateway (dan tunggu sesi `hermes -p`
selesai), baru `bersihkan` untuk menghapus salinan hook + tim.json.

Tanpa nilai tertanam: daftar profil = kunci `agen` di tim.json (koordinator = profil default di HERMES_HOME), folder data
Hermes = $HERMES_HOME. Hook dan tim.json disalin dari <host>:<AKAR> ke $HERMES_HOME/agent-hooks/ (container tidak melihat
folder project); `cek` membandingkan sha256 salinan dengan sumbernya. Entri hook ditaruh PALING AKHIR di tiap event supaya
penjaga yang sudah ada tetap jalan lebih dulu. Isi log mengikuti tim.json `aktivitas` (bawaan metadata saja).
Sesudah pasang/rollback: restart gateway (sesi CLI `hermes -p` memuat hook saat start).
"""
import difflib
import hashlib
import io
import json
import os
import shlex
import shutil
import stat
import subprocess
import sys
import tempfile
import time
from pathlib import Path

from ruamel.yaml import YAML

if len(sys.argv) != 4 or sys.argv[1] not in ("cek", "uji", "pasang", "perbarui", "rollback", "bersihkan"):
    sys.exit("pemakaian: ... | python - cek|uji|pasang|perbarui|rollback|bersihkan <host> <AKAR>")
MODE, HOST, AKAR = sys.argv[1:4]
HH = Path(os.environ.get("HERMES_HOME") or sys.exit("HERMES_HOME tidak diset")).resolve()
if not ((HH / "config.yaml").is_file() and (HH / "profiles").is_dir()) or HH.parent.name == "profiles":
    sys.exit(f"HERMES_HOME harus akar data Hermes (config.yaml + profiles/), bukan folder profil: {HH}")
HOOK = HH / "agent-hooks/team-activity.py"
TIM = HH / "agent-hooks/agent-dashboard-tim.json"
LOG = HH / "agent-hooks/state/activity.jsonl"
BACKUP = HH / "backups/agent-dashboard-hook"
SUMBER = {HOOK: "hooks/team-activity.py", TIM: "conf/tim.json"}
CMD = f"/usr/bin/env TEAM_ACTIVITY_LOG={LOG} AD_TIM={TIM} {sys.executable} {HOOK}"
BERKAS = ("config.yaml", "shell-hooks-allowlist.json")
SRC_HERMES = Path(sys.executable).parent.parent.parent  # <src>/.venv/bin/python -> <src> (tanpa resolve symlink)
if not (SRC_HERMES / "agent/shell_hooks.py").is_file():
    sys.exit(f"jalankan dengan python venv Hermes (agent/shell_hooks.py tidak ada di {SRC_HERMES})")


def host_baca(rel: str) -> bytes:
    return subprocess.run(["ssh", HOST, f"cat {AKAR}/{rel}"], check=True, capture_output=True).stdout


TIM_SUMBER = json.loads(host_baca("conf/tim.json"))
PROFIL = list(TIM_SUMBER["agen"])


def home(p: str) -> Path:
    return HH if p == TIM_SUMBER["koordinator"] else HH / "profiles" / p


def events(p: str) -> list[str]:  # post_llm_call (balasan) hanya dicatat untuk koordinator
    return ["pre_llm_call", "pre_tool_call"] + (["post_llm_call"] if p == TIM_SUMBER["koordinator"] else [])


def yaml_rt() -> YAML:
    y = YAML()
    y.preserve_quotes = True
    y.width = 4096
    return y


def dengan_hook(p: str) -> tuple[str, str]:
    """(teks config sekarang, teks config dengan entri hook di akhir tiap event)."""
    src = (home(p) / "config.yaml").read_text(encoding="utf-8")
    y = yaml_rt()
    cfg = y.load(src)
    if cfg.get("hooks") is None:
        cfg["hooks"] = {}
    for ev in events(p):
        if cfg["hooks"].get(ev) is None:
            cfg["hooks"][ev] = []
        if not any(x.get("command") == CMD for x in cfg["hooks"][ev]):
            cfg["hooks"][ev].append({"command": CMD, "timeout": 5})
    out = io.StringIO()
    y.dump(cfg, out)
    return src, out.getvalue()


def cek() -> bool:
    gagal = []
    for salinan, rel in SUMBER.items():
        if not salinan.is_file() or hashlib.sha256(salinan.read_bytes()).digest() != hashlib.sha256(host_baca(rel)).digest():
            gagal.append(f"{salinan.name}: tidak ada / beda dengan {HOST}:{AKAR}/{rel}")
    for p in PROFIL:
        cfg = yaml_rt().load((home(p) / "config.yaml").read_text(encoding="utf-8"))
        allow = json.loads((home(p) / BERKAS[1]).read_text(encoding="utf-8")).get("approvals", [])
        for ev in events(p):
            daftar = [x.get("command") for x in ((cfg.get("hooks") or {}).get(ev) or [])]
            if not daftar or daftar[-1] != CMD:
                gagal.append(f"{p}/{ev}: hook tidak di posisi akhir")
            if not any(e.get("event") == ev and e.get("command") == CMD for e in allow):
                gagal.append(f"{p}/{ev}: belum di allowlist")
    for g in gagal:
        print("GAGAL ", g)
    print("LULUS  semua" if not gagal else f"{len(gagal)} gagal")
    return not gagal


def uji() -> None:
    for p in PROFIL:
        a, b = dengan_hook(p)
        beda = [l for l in difflib.unified_diff(a.splitlines(), b.splitlines(), lineterm="", n=0)
                if l[:1] in "+-" and l[:3] not in ("+++", "---")]
        kunci_baru = tuple(f"{ev}:" for ev in events(p))
        lain = [l for l in beda if l.startswith("-") or not (CMD in l or l[1:].strip() == "timeout: 5"
                                                             or l[1:].strip() in kunci_baru)]
        print(f"{p}: {len(beda)} baris berubah; di luar entri hook: {lain or 'tidak ada'}")


def allowlist_ubah(fungsi: str, p: str, *args: str) -> None:
    """Panggil agent.shell_hooks.<fungsi>(*args) dengan HERMES_HOME profil p (allowlist per profil)."""
    subprocess.run([sys.executable, "-c", f"import sys; from agent.shell_hooks import {fungsi} as f; f(*sys.argv[1:])",
                    *args], check=True, cwd=SRC_HERMES, env={**os.environ, "HERMES_HOME": str(home(p))})


def home_di_disk() -> list[Path]:
    """Semua folder profil yang punya config.yaml (bukan hanya yang ada di tim.json)."""
    return [HH] + sorted(p.parent for p in HH.glob("profiles/*/config.yaml"))


def merujuk_hook(perintah: str) -> bool:
    """Perintah hook memanggil berkas hook ini? Dicocokkan per token secara kanonik (realpath), bukan string perintah utuh
    atau substring: bentuk setara (python vs python3, //, .., symlink) tetap dikenali (verdict G7-QC 1820 M2, 1825 M3)."""
    try:
        token = shlex.split(perintah)
    except ValueError:
        return HOOK.name in perintah  # tidak bisa diurai: anggap merujuk (aman untuk pencabutan)
    kanon = os.path.realpath(HOOK)
    return any(t.endswith(HOOK.name) and os.path.realpath(os.path.expanduser(t)) == kanon for t in token)


def pasang() -> None:
    if BACKUP.exists():
        sys.exit(f"backup sudah ada ({BACKUP}): pasang sudah pernah jalan dan belum di-rollback")
    hilang = [str(home(p) / f) for p in PROFIL for f in BERKAS if not (home(p) / f).is_file()]
    if hilang:  # validasi sebelum menulis apa pun, supaya tidak ada backup parsial
        sys.exit(f"berkas profil tidak ada (HERMES_HOME salah?): {hilang}")
    for p in PROFIL:  # parse semua config + allowlist dulu; YAML/JSON rusak = berhenti sebelum menulis
        try:
            dengan_hook(p)
            json.loads((home(p) / BERKAS[1]).read_text(encoding="utf-8"))
        except Exception as e:
            sys.exit(f"config/allowlist profil {p} tidak bisa dibaca, tidak ada yang diubah: {e}")
    BACKUP.mkdir(parents=True, mode=0o700)
    for p in PROFIL:
        (BACKUP / p).mkdir(mode=0o700)
        for f in BERKAS:
            shutil.copy2(home(p) / f, BACKUP / p / f)
    for salinan, rel in SUMBER.items():
        salinan.parent.mkdir(parents=True, exist_ok=True)
        tmp = salinan.with_name(salinan.name + ".baru")
        tmp.write_bytes(host_baca(rel))
        tmp.chmod(0o644 if salinan == HOOK else 0o640)
        tmp.replace(salinan)
    for p in PROFIL:
        f = home(p) / "config.yaml"
        tmp = f.with_name("config.yaml.baru")
        tmp.write_text(dengan_hook(p)[1], encoding="utf-8")
        shutil.copymode(f, tmp)
        tmp.replace(f)
        for ev in events(p):
            allowlist_ubah("_record_approval", p, ev, CMD)
    print(f"backup: {BACKUP}")


def uji_jalan(hook: bytes, tim: bytes) -> None:
    """Jalankan hook baru (bukan salinan aktif) dengan payload pre_tool_call contoh di folder sementara: harus rc 0 dan
    menulis tepat satu baris JSON sah. Berkas sementara selalu dihapus. Gagal = berhenti sebelum mengganti apa pun."""
    kunci = json.loads(tim)["koordinator"]
    payload = {"hook_event_name": "pre_tool_call", "tool_name": "terminal", "tool_input": {"command": "echo uji"},
               "session_id": "uji-perbarui", "cwd": "/", "profile": kunci, "extra": {}}
    with tempfile.TemporaryDirectory() as d:
        (Path(d) / "hook.py").write_bytes(hook)
        (Path(d) / "tim.json").write_bytes(tim)
        log = Path(d) / "aktivitas.jsonl"
        r = subprocess.run([sys.executable, str(Path(d) / "hook.py")], input=json.dumps(payload).encode(), capture_output=True,
                           env={**os.environ, "TEAM_ACTIVITY_LOG": str(log), "AD_TIM": str(Path(d) / "tim.json")}, timeout=10)
        baris = log.read_text(encoding="utf-8").splitlines() if log.is_file() else []
        if r.returncode != 0 or len(baris) != 1:
            sys.exit(f"uji jalan hook baru gagal (rc {r.returncode}, {len(baris)} baris log): {r.stderr.decode()[:300]}")
        json.loads(baris[0])  # baris bukan JSON sah = ValueError = berhenti


def ganti(tujuan: Path, isi: bytes, cap: str, mode_baru: int) -> bool:
    """Ganti `tujuan` secara atomik; no-op (False) bila isi sama. Berkas lama dicadangkan ke `.lama-<cap>` dan modenya
    dipertahankan; `.baru` dibersihkan bila gagal di tengah."""
    ada = tujuan.is_file()
    if ada and tujuan.read_bytes() == isi:
        return False
    mode = stat.S_IMODE(tujuan.stat().st_mode) if ada else mode_baru
    if ada:
        lama = tujuan.with_name(f"{tujuan.name}.lama-{cap}")
        shutil.copy2(tujuan, lama)
        print(f"cadangan: {lama} (rollback: mv -f {lama} {tujuan})")
    tmp = tujuan.with_name(tujuan.name + ".baru")
    try:
        tmp.write_bytes(isi)
        tmp.chmod(mode)
        tmp.replace(tujuan)
    finally:
        tmp.unlink(missing_ok=True)
    return True


def perbarui() -> None:
    if not HOOK.is_file():
        sys.exit(f"hook belum terpasang ({HOOK}): pakai `pasang`")
    hook, tim = host_baca(SUMBER[HOOK]), host_baca(SUMBER[TIM])
    compile(hook, SUMBER[HOOK], "exec")  # sintaks rusak = berhenti; berkas hook rusak diblok (rc 2) oleh Hermes
    json.loads(tim)  # tim.json rusak = berhenti sebelum menulis
    uji_jalan(hook, tim)
    cap = time.strftime("%Y%m%dT%H%M%S")
    diganti = [ganti(HOOK, hook, cap, 0o644), ganti(TIM, tim, cap, 0o640)]
    print(f"hook {'diperbarui' if diganti[0] else 'sudah sama'}; tim.json {'diperbarui' if diganti[1] else 'sudah sama'}")


def rollback() -> None:
    """Cabut HANYA entri yang merujuk berkas hook (config) + approval-nya, di semua profil di disk; berkas hook dibiarkan
    sampai `bersihkan`. Gagal (rc 1) bila masih ada rujukan sesudahnya."""
    y = yaml_rt()
    dicabut = 0
    for h in home_di_disk():
        f = h / "config.yaml"
        if HOOK.name in f.read_text(encoding="utf-8"):
            cfg = y.load(f.read_text(encoding="utf-8"))
            hooks = cfg.get("hooks") or {}
            for ev in list(hooks):
                if isinstance(hooks[ev], list):
                    sisa = [x for x in hooks[ev] if not (isinstance(x, dict) and merujuk_hook(str(x.get("command", ""))))]
                    dicabut += len(hooks[ev]) - len(sisa)
                    hooks[ev][:] = sisa
                    if not hooks[ev]:
                        del hooks[ev]  # event yang dibuat pasang (mis. post_llm_call) ikut hilang bila kosong
            tmp = f.with_name("config.yaml.baru")
            with tmp.open("w", encoding="utf-8") as o:
                y.dump(cfg, o)
            shutil.copymode(f, tmp)
            tmp.replace(f)
        a = h / BERKAS[1]
        if a.is_file():
            perintah = {e.get("command", "") for e in json.loads(a.read_text(encoding="utf-8")).get("approvals", [])}
            for c in sorted(x for x in perintah if merujuk_hook(x)):
                subprocess.run([sys.executable, "-c", "import sys; from agent.shell_hooks import revoke; revoke(sys.argv[1])",
                                c], check=True, cwd=SRC_HERMES, env={**os.environ, "HERMES_HOME": str(h)})
    sisa = rujukan_tersisa()
    if sisa:
        sys.exit(f"rollback BELUM bersih, masih ada rujukan hook di: {sisa}")
    if BACKUP.exists():
        BACKUP.rename(BACKUP.with_name(f"{BACKUP.name}.dibatalkan-{time.strftime('%Y%m%d-%H%M%S')}"))
    print(f"rollback selesai: {dicabut} entri hook dicabut, 0 rujukan tersisa di config/allowlist. Berkas hook DIBIARKAN: "
          "restart gateway, tunggu sesi `hermes -p` yang masih jalan selesai, lalu mode `bersihkan`. "
          "activity.jsonl tidak dihapus.")


def rujukan_tersisa() -> list[str]:
    # Pemeriksa independen dari matcher pencabut, sengaja lebih lebar: nama berkas hook di mana pun dalam teks.
    return [str(h / f) for h in home_di_disk() for f in BERKAS
            if (h / f).is_file() and HOOK.name in (h / f).read_text(encoding="utf-8")]


def bersihkan() -> None:
    sisa = rujukan_tersisa()
    if sisa:
        sys.exit(f"hook masih dirujuk di {sisa}: jalankan rollback + restart gateway dulu")
    HOOK.unlink(missing_ok=True)
    TIM.unlink(missing_ok=True)
    print("salinan hook + tim.json dihapus (pastikan gateway sudah di-restart sesudah rollback)")


if MODE == "uji":
    uji()
elif MODE == "pasang":
    pasang()
    sys.exit(0 if cek() else 1)
elif MODE == "perbarui":
    perbarui()
    sys.exit(0 if cek() else 1)
elif MODE == "rollback":
    rollback()
elif MODE == "bersihkan":
    bersihkan()
else:
    sys.exit(0 if cek() else 1)
