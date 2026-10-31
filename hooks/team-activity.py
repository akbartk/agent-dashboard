#!/usr/bin/env python3
"""Hook pencatat aktivitas agen (pre_llm_call + pre_tool_call + post_llm_call koordinator). Hanya mencatat, tidak
pernah memblok: error apa pun = keluar 0 tanpa output.

Satu baris JSON per kejadian ditambahkan ke berkas jsonl yang dibaca generator dashboard. Format dan privasi: KONTRAK
bagian 6 dan 6a (docs/).
  TEAM_ACTIVITY_LOG  path berkas jsonl. Tidak diset = tidak menulis apa pun.
  AD_TIM             path conf/tim.json (id koordinator, nama pemilik, nama agen, kunci `aktivitas`). Tidak diset atau
                     tidak sah = tidak menulis apa pun (koordinator tidak diketahui).

Privasi (default tanpa isi): `text` (pesan) dan `detail` (argumen tool) hanya ditulis bila tim.json memuat
`aktivitas.catat_teks` / `aktivitas.catat_detail` bernilai persis true (boolean). Bila ditulis: rahasia disamarkan DULU,
baru dipotong `teks_maks` (int 1-2000, bawaan 300) / `detail_maks` (int 1-4000, bawaan 1000).

Tidak ada kunci `blocked`: Hermes menjalankan hook pre_tool_call secara independen (tiap hook hanya menerima payload,
bukan keputusan hook lain), jadi blok tak bisa diketahui di sini. Sumber blok = log guard (g7-tim-guard.jsonl, qc-gate-g7.jsonl).

Koordinator (profil = tim.json.koordinator): role "owner", name = nama pemilik, tanpa kunci `profile` (generator memakai
ketiadaan `profile` sebagai penanda baris koordinator). Agen lain: role "tim", name = tim.json.agen[profil].nama.
"""
import json
import os
import re
import sys
import time
from pathlib import Path

# Heuristik, bukan jaminan: kunci (<= 80 karakter) yang memuat kata rahasia lazim, diikuti `=` atau `:` (kutip opsional),
# nilainya diganti `***`. Dipindai manual (bukan satu regex bersarang) supaya waktunya linear pada masukan patologis.
KUNCI = re.compile(r"([\w.-]{1,80})[\"']?[ \t]*[=:]")
NILAI = re.compile(r"[ \t]*[\"']?(?:(?:Bearer|Basic)[ \t]+)?\S+")
KATA_RAHASIA = re.compile(r"(?i)pass(?:word|wd)?|secret|token|api[_-]?key|access[_-]?key|private[_-]?key|credential|auth")
BEARER = re.compile(r"(?i)\b(Bearer)\s+[\w.~+/=-]{8,}")
AWALAN_TOKEN = re.compile(r"\b(?:sk|pk|ghp|gho|ghs|xox[abp])-?[A-Za-z0-9_-]{16,}")
SISTEM = re.compile(r"^\s*\[IMPORTANT: Background process|\[INTERNAL NOTIFICATION")  # = RE_SISTEM generator
URUTAN_DETAIL = ("command", "path", "query", "goal", "url")
BATAS_REGEX = 100_000  # batasi masukan pemindai; keluaran dipotong jauh di bawah ini


def samarkan(s: str) -> str:
    s = s[:BATAS_REGEX]
    keluar, pos = [], 0
    while True:
        m = KUNCI.search(s, pos)
        if m is None:
            break
        if KATA_RAHASIA.search(m.group(1)):
            nilai = NILAI.match(s, m.end())
            keluar += [s[pos:m.start()], m.group(1), "=***"]
            pos = nilai.end() if nilai else m.end()
        else:
            keluar.append(s[pos:m.end()])
            pos = m.end()
    keluar.append(s[pos:])
    s = BEARER.sub(r"\1 ***", "".join(keluar))
    return AWALAN_TOKEN.sub("***", s)


def muat_tim():
    path = os.environ.get("AD_TIM")
    if not path:
        return None
    try:
        with open(path, encoding="utf-8") as f:
            d = json.load(f)
    except (OSError, ValueError):
        return None
    if not isinstance(d, dict):
        return None
    ok = (isinstance(d.get("koordinator"), str) and d["koordinator"] and isinstance(d.get("pemilik"), str)
          and d["pemilik"] and isinstance(d.get("agen"), dict) and isinstance(d.get("orang"), list))
    return d if ok else None


def maks(nilai, atas: int, bawaan: int) -> int:
    return nilai if type(nilai) is int and 1 <= nilai <= atas else bawaan  # type() is int: bool dan float ditolak


def nama_pemilik(tim: dict) -> str:
    for o in tim["orang"]:
        if isinstance(o, dict) and o.get("id") == tim["pemilik"] and isinstance(o.get("nama"), str) and o["nama"]:
            return o["nama"]
    return tim["pemilik"]


def nama_agen(tim: dict, profil: str) -> str:
    a = tim["agen"].get(profil)
    return a["nama"] if isinstance(a, dict) and isinstance(a.get("nama"), str) and a["nama"] else profil


def main() -> None:
    mentah = sys.stdin.read()  # selalu dikuras, juga bila tidak ada yang dicatat
    log = os.environ.get("TEAM_ACTIVITY_LOG")
    if not log:
        return
    tim = muat_tim()
    if tim is None:
        return
    p = json.loads(mentah)
    if not isinstance(p, dict):
        return
    sid = p.get("session_id") if isinstance(p.get("session_id"), str) else ""
    if sid == "test-session":  # payload sintetis `hermes hooks test/doctor`, bukan aktivitas nyata
        return
    profil = p.get("profile") if isinstance(p.get("profile"), str) and p.get("profile") else "?"
    extra = p.get("extra") if isinstance(p.get("extra"), dict) else {}
    ev = p.get("hook_event_name")
    akt = tim.get("aktivitas") if isinstance(tim.get("aktivitas"), dict) else {}
    catat_teks, catat_detail = akt.get("catat_teks") is True, akt.get("catat_detail") is True
    koordinator = profil == tim["koordinator"]
    if koordinator:
        entry = {"role": "owner", "name": nama_pemilik(tim), "sid": sid}
    else:
        entry = {"role": "tim", "name": nama_agen(tim, profil), "profile": profil, "sid": sid}

    if ev == "pre_llm_call":
        teks = extra.get("user_message")
        teks = teks if isinstance(teks, str) else ("" if teks is None else str(teks))
        subagent = extra.get("platform") == "subagent"
        if koordinator and subagent:  # sesi subagent koordinator bukan pesan pemilik
            return
        entry["type"] = "msg"
        if catat_teks:
            entry["text"] = samarkan(teks)[:maks(akt.get("teks_maks"), 2000, 300)]
        if subagent:
            entry["sub"] = True
        if SISTEM.search(teks):  # dihitung di memori; teksnya tidak ditulis
            entry["sistem"] = True
    elif ev == "pre_tool_call":
        args = p.get("tool_input") if isinstance(p.get("tool_input"), dict) else {}
        entry.update(type="tool", tool=str(p.get("tool_name") or ""))  # tanpa `blocked`: hook tidak tahu keputusan guard; lihat log guard
        if catat_detail:
            d = next((args[k] for k in URUTAN_DETAIL if args.get(k)), None)
            d = str(d if d is not None else json.dumps(args, ensure_ascii=False))
            entry["detail"] = samarkan(d)[:maks(akt.get("detail_maks"), 4000, 1000)]
    elif ev == "post_llm_call":  # balasan koordinator saja, tanpa isi
        resp = extra.get("assistant_response")
        if not koordinator or not (isinstance(resp, str) and resp.strip()):
            return
        entry["type"] = "reply"
    else:
        return
    entry["ts"] = time.strftime("%Y-%m-%dT%H:%M:%S")
    Path(log).parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        pass
    sys.exit(0)
