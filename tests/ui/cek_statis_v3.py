#!/usr/bin/env python3
"""cek_statis_v3.py - cek statis tampilan v3 agent-dashboard (stdlib saja, tanpa peramban).

Pemakaian (host bskdev atau container ajeng):
  python3 cek_statis_v3.py --web DIR [--tema-src /aset/font/tema.js] [--kontras PATH/kontras.py]
                           [--acuan DIR_WEB_V2] [--keluaran HASIL.json]

--web       folder web (berisi app.css, app.js, index.html, login.html, ganti.html, font/).
--tema-src  src tema.js yang wajib dipakai 3 HTML: /aset/font/tema.js (opsi B, bawaan) atau /aset/tema.js (opsi A).
            Berkasnya dicari di <web>/font/tema.js atau <web>/tema.js sesuai src itu.
--kontras   docs/mockup/v3/uji/kontras.py; palet TEMA DIBACA dari berkas ini (ast), lalu skripnya dijalankan.
--acuan     folder web v2: login.html/ganti.html v3 hanya boleh berbeda pada baris <script src=tema.js>.
Keluar 0 = semua lulus, 1 = ada yang gagal. Tidak menulis apa pun kecuali --keluaran.
"""
import argparse
import ast
import difflib
import json
import os
import re
import subprocess
import sys

SKALA_FONT = {"14px", "16px", "20px", "28px", "inherit"}
BOBOT = {"400", "600", "inherit"}
NAMA_WARNA = ("white|black|red|green|blue|gray|grey|silver|orange|yellow|purple|pink|brown|navy|teal|maroon|olive|"
              "lime|aqua|fuchsia|gold|crimson|tomato|coral|salmon|indigo|violet|beige|ivory|khaki|lavender|plum|tan")
RE_WARNA = re.compile(r"#[0-9a-fA-F]{3,8}\b|\b(?:rgb|rgba|hsl|hsla|hwb|lab|lch|oklab|oklch)\(|\b(?:%s)\b" % NAMA_WARNA, re.I)
RE_EMOJI = re.compile("[\U0001F000-\U0001FAFF\u2600-\u27BF\u2B00-\u2BFF\uFE0F\u200D]")
BLOK_TERANG = ":root"
BLOK_GELAP = ':root[data-tema="gelap"]'
# kunci TEMA kontras.py -> nama variabel CSS mockup v3 (fokus = --aksen, garis bawah = strip)
PETA_VAR = {"fokus": "aksen"}


# ------------------------------------------------------------------ util
def baca(p):
    with open(p, encoding="utf-8") as f:
        return f.read()


def L(h):
    h = h.lstrip("#")
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    c = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def kontras(a, b):
    la, lb = sorted([L(a), L(b)], reverse=True)
    return (la + 0.05) / (lb + 0.05)


def urai_css(teks):
    """Parser kurung kurawal sederhana: [(selektor, {prop: nilai}, konteks @media)]."""
    teks = re.sub(r"/\*.*?\*/", "", teks, flags=re.S)
    aturan, i, n = [], 0, len(teks)

    def blok(i, konteks):
        while i < n:
            j = teks.find("{", i)
            k = teks.find("}", i)
            if k != -1 and (j == -1 or k < j):
                return k + 1
            if j == -1:
                return n
            sel = teks[i:j].strip()
            if sel.startswith("@media") or sel.startswith("@supports"):
                i = blok(j + 1, konteks + [sel])
                continue
            k = teks.find("}", j)
            isi = teks[j + 1:k]
            dek = {}
            for d in isi.split(";"):
                if ":" in d:
                    p, v = d.split(":", 1)
                    dek[p.strip()] = v.strip()
            aturan.append((sel, dek, tuple(konteks), isi))
            i = k + 1
        return i

    blok(0, [])
    return aturan


def tema_dari_kontras(path):
    pohon = ast.parse(baca(path))
    for nd in ast.walk(pohon):
        if isinstance(nd, ast.Assign) and any(isinstance(t, ast.Name) and t.id == "TEMA" for t in nd.targets):
            hasil = {}
            for k, v in zip(nd.value.keys, nd.value.values):
                if isinstance(v, ast.Call):
                    hasil[k.value] = {kw.arg: kw.value.value for kw in v.keywords}
                else:
                    hasil[k.value] = ast.literal_eval(v)
            return hasil
    raise ValueError("TEMA tidak ditemukan di " + path)


def tag_tag(html):
    return [(m.start(), m.group(0)) for m in re.finditer(r"<[a-zA-Z][^>]*>", html)]


# ------------------------------------------------------------------ cek
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", required=True)
    ap.add_argument("--tema-src", default="/aset/font/tema.js")
    ap.add_argument("--kontras", required=True)
    ap.add_argument("--acuan")
    ap.add_argument("--keluaran")
    a = ap.parse_args()
    hasil = []

    def cek(nama, ok, ket, rinci=None):
        hasil.append({"nama": nama, "ok": bool(ok), "ket": ket, "rinci": rinci})

    W = a.web.rstrip("/")
    berkas_tema = W + "/" + a.tema_src[len("/aset/"):] if a.tema_src.startswith("/aset/") else None
    css = baca(W + "/app.css")
    js = baca(W + "/app.js")
    html = {n: baca("%s/%s.html" % (W, n)) for n in ("index", "login", "ganti")}
    tema_js = baca(berkas_tema) if berkas_tema and os.path.isfile(berkas_tema) else None

    # 1-2 tema.js
    cek("tema_js_ada", tema_js is not None and tema_js.strip() != "", "berkas %s %s" % (berkas_tema, "ada" if tema_js else "TIDAK ADA"))
    if tema_js:
        perlu = {
            "getItem tema": r"localStorage\.getItem\(\s*['\"]tema['\"]\s*\)",
            "try/catch": r"\btry\s*\{[^}]*localStorage[^}]*\}\s*catch\b",
            "prefers-color-scheme dark": r"prefers-color-scheme:\s*dark",
            "dataset.tema": r"document\.documentElement\.dataset\.tema\s*=",
            "nilai gelap": r"['\"]gelap['\"]", "nilai terang": r"['\"]terang['\"]",
        }
        terlarang = [p for p in ("setItem", "addEventListener", "fetch", "document.write", "innerHTML", "eval(") if p in tema_js]
        kurang = [k for k, p in perlu.items() if not re.search(p, tema_js)]
        cek("tema_js_logika_mockup_d2", not kurang and not terlarang and len(tema_js.encode()) <= 600,
            "kurang=%s terlarang=%s byte=%d" % (kurang, terlarang, len(tema_js.encode())))
    else:
        cek("tema_js_logika_mockup_d2", False, "tema.js tidak ada")

    # 3-6 variabel CSS vs TEMA (dibaca dari kontras.py)
    TEMA = tema_dari_kontras(a.kontras)
    aturan = urai_css(css)
    blok = {}
    for sel, dek, ktx, _ in aturan:
        if not ktx and sel in (BLOK_TERANG, BLOK_GELAP):
            blok.setdefault(sel, {}).update(dek)
    var = {s: {p[2:]: v for p, v in d.items() if p.startswith("--")} for s, d in blok.items()}
    for tema, sel in (("terang", BLOK_TERANG), ("gelap", BLOK_GELAP)):
        beda = []
        for k, harap in TEMA[tema].items():
            nama = PETA_VAR.get(k, k.replace("_", "-"))
            nyata = var.get(sel, {}).get(nama)
            if nyata is None or nyata.lower() != harap.lower():
                beda.append({"kunci": k, "var": "--" + nama, "harap": harap, "css": nyata})
        cek("css_var_%s_sama_TEMA_kontras_py" % tema, not beda, "%d kunci TEMA, beda=%d (blok %s)" % (len(TEMA[tema]), len(beda), sel), beda)
    vt, vg = set(var.get(BLOK_TERANG, {})), set(var.get(BLOK_GELAP, {}))
    cek("css_var_gelap_menimpa_semua_var_terang", vt and vt == vg, "terang=%d gelap=%d hanya_terang=%s hanya_gelap=%s" % (
        len(vt), len(vg), sorted(vt - vg), sorted(vg - vt)))
    luar = []
    for sel, dek, ktx, isi in aturan:
        if not ktx and sel in (BLOK_TERANG, BLOK_GELAP):
            continue
        for p, v in dek.items():
            if p == "src":
                continue
            for m in RE_WARNA.finditer(v):
                luar.append("%s{%s:%s}" % (sel, p, v))
    cek("css_warna_di_luar_blok_variabel_0", not luar, "kemunculan=%d" % len(luar), luar[:10])

    # 7 kontras.py
    try:
        r = subprocess.run([sys.executable, a.kontras], capture_output=True, text=True, timeout=30)
        ok = r.returncode == 0 and r.stdout.strip().endswith("SEMUA LULUS")
        cek("kontras_py_SEMUA_LULUS", ok, "rc=%d baris_terakhir=%r" % (r.returncode, (r.stdout.strip().splitlines() or [""])[-1]))
    except Exception as e:  # noqa: BLE001
        cek("kontras_py_SEMUA_LULUS", False, "galat %s" % e)

    # 8 kontras pasangan warna di luar TEMA (banner, tombol masuk, seleksi, koneksi bermasalah)
    def nilai_warna(sel, prop, tema):
        for s, dek, ktx, _ in aturan:
            if s == sel and not ktx and prop in dek:
                v = dek[prop].strip()
                m = re.fullmatch(r"var\(--([a-z0-9-]+)\)", v)
                if m:
                    return var.get(BLOK_GELAP if tema == "gelap" else BLOK_TERANG, {}).get(m.group(1)) or \
                        var.get(BLOK_TERANG, {}).get(m.group(1))
                return v if re.fullmatch(r"#[0-9a-fA-F]{6}", v) else None
        return None
    pasangan = [  # (nama, sel_fg, prop_fg, sel_bg, prop_bg, ambang)
        ("banner", ".banner", "color", ".banner-latar", "background", 4.5),
        ("tombol_masuk", ".masuk button", "color", ".masuk button", "background", 4.5),
        ("tombol_masuk_hover", ".masuk button", "color", ".masuk button:hover", "background", 4.5),
        ("isian_masuk", ".masuk input", "color", ".masuk input", "background", 4.5),
        ("seleksi", "::selection", "color", "::selection", "background", 4.5),
        ("titik_koneksi_bermasalah", ".koneksi .titik.bermasalah", "background", "body", "background", 3.0),
    ]
    gagal_p, ukur = [], []
    for tema in ("terang", "gelap"):
        for nm, sf, pf, sb, pb, amb in pasangan:
            fg, bg = nilai_warna(sf, pf, tema), nilai_warna(sb, pb, tema)
            if not fg or not bg:
                gagal_p.append("%s/%s: warna tak terbaca fg=%s bg=%s" % (tema, nm, fg, bg))
                continue
            r_ = kontras(fg, bg)
            ukur.append("%s/%s %s:%s=%.2f" % (tema, nm, fg, bg, r_))
            if r_ < amb:
                gagal_p.append("%s/%s %.2f < %.1f" % (tema, nm, r_, amb))
    if BLOK_GELAP not in blok:
        gagal_p.append("blok gelap tidak ada")
    cek("kontras_pasangan_di_luar_TEMA", not gagal_p, "; ".join(ukur) if not gagal_p else "; ".join(gagal_p[:6]), gagal_p)

    # 9-12 HTML
    inline, urut, appjs, tpl = [], [], [], []
    for n, h in html.items():
        if re.search(r"<style\b", h, re.I):
            inline.append(n + ": <style>")
        if re.search(r"\sstyle\s*=", h, re.I):
            inline.append(n + ": style=")
        if re.search(r"<[^>]*\son[a-z]+\s*=", h, re.I):
            inline.append(n + ": on*=")
        for m in re.finditer(r"<script\b([^>]*)>(.*?)</script>", h, re.I | re.S):
            if "src=" not in m.group(1) or m.group(2).strip():
                inline.append(n + ": <script> inline")
        if re.search(r"\sjavascript:", h, re.I):
            inline.append(n + ": javascript:")
        kepala = h.split("</head>")[0] if "</head>" in h else ""
        tag = tag_tag(kepala)
        skrip = [(i, t) for i, t in tag if t.lower().startswith("<script")]
        css_link = [(i, t) for i, t in tag if t.lower().startswith("<link") and re.search(r'rel="?stylesheet', t, re.I)]
        tema_t = [(i, t) for i, t in skrip if re.search(r'src="%s"' % re.escape(a.tema_src), t)]
        if len(tema_t) != 1:
            urut.append("%s: <script src=%s> di <head> = %d" % (n, a.tema_src, len(tema_t)))
        else:
            i, t = tema_t[0]
            if re.search(r"\b(defer|async)\b|type=\"?module", t, re.I):
                urut.append("%s: tema.js memakai defer/async/module: %s" % (n, t))
            if not css_link or i > css_link[0][0]:
                urut.append("%s: tema.js tidak sebelum stylesheet" % n)
        if [t for _, t in css_link] != ['<link rel="stylesheet" href="/aset/app.css">']:
            urut.append("%s: stylesheet = %s" % (n, [t for _, t in css_link]))
        app = [t for t in re.findall(r"<script\b[^>]*>", h, re.I) if "/aset/app.js" in t]
        if n == "index":
            if app != ['<script src="/aset/app.js" defer>']:
                appjs.append("index: app.js = %s (harus tepat <script src=\"/aset/app.js\" defer>)" % app)
        elif app:
            appjs.append("%s memuat app.js" % n)
    cek("html_0_inline_style_on_script", not inline, "temuan=%d" % len(inline), inline)
    cek("html_tema_js_head_sebelum_css_tanpa_defer", not urut, "3 berkas; masalah=%d" % len(urut), urut)
    cek("index_app_js_defer_login_ganti_tanpa_app_js", not appjs, "masalah=%d" % len(appjs), appjs)
    harap_aksi = {"login": ["{{.Akun}}", "{{if .Pesan}}", "{{.Pesan}}", "{{end}}"], "ganti": ["{{if .Pesan}}", "{{.Pesan}}", "{{end}}"]}
    harap_isian = {"login": ["akun", "password"], "ganti": ["password_baru", "password_ulang"]}
    harap_form = {"login": '<form method="post" action="/login">', "ganti": '<form method="post" action="/ganti-password">'}
    for n in ("login", "ganti"):
        h = html[n]
        aksi = re.findall(r"\{\{[^}]*\}\}", h)
        if aksi != harap_aksi[n]:
            tpl.append("%s: aksi template %s" % (n, aksi))
        isian = re.findall(r'<input[^>]*\sname="([^"]+)"', h)
        if isian != harap_isian[n]:
            tpl.append("%s: input name %s" % (n, isian))
        if harap_form[n] not in h:
            tpl.append("%s: form berubah" % n)
        if '{{if .Pesan}}<p class="pesan" role="alert">{{.Pesan}}</p>{{end}}' not in h:
            tpl.append("%s: blok pesan berubah" % n)
        if a.acuan:
            lama = baca("%s/%s.html" % (a.acuan.rstrip("/"), n)).splitlines()
            beda = [x for x in difflib.unified_diff(lama, h.splitlines(), lineterm="", n=0)
                    if x[:1] in "+-" and not x.startswith(("+++", "---"))]
            lain = [x for x in beda if x != '+<script src="%s"></script>' % a.tema_src]
            if lain or not beda:
                tpl.append("%s: beda vs acuan selain baris tema.js: %s" % (n, lain[:4] if lain else "tidak ada beda sama sekali"))
    cek("login_ganti_template_utuh", not tpl, "masalah=%d%s" % (len(tpl), " (dibanding acuan v2)" if a.acuan else ""), tpl)

    # 13 pedoman K-05/F-18
    ped = []
    for nm, teks in [("app.css", css), ("app.js", js), ("tema.js", tema_js or "")] + [(n + ".html", h) for n, h in html.items()]:
        for pola, ket in ((r"box-shadow", "box-shadow"), (r"(linear|radial|conic)-gradient", "gradient"), (r"<svg\b|<img\b|<i\s", "ikon/gambar"),
                          (r"\bopacity\s*:", "opacity")):
            k = len(re.findall(pola, teks, re.I))
            if k:
                ped.append("%s: %s x%d" % (nm, ket, k))
        e = RE_EMOJI.findall(teks)
        if e:
            ped.append("%s: emoji x%d" % (nm, len(e)))
    for sel, dek, ktx, _ in aturan:
        for p, v in dek.items():
            if p == "font-size" and v not in SKALA_FONT:
                ped.append("%s font-size:%s" % (sel, v))
            if p == "font-weight" and v not in BOBOT:
                ped.append("%s font-weight:%s" % (sel, v))
            if p == "content" and v not in ('""', "''"):
                ped.append("%s content:%s" % (sel, v))
            if p == "font" and v not in ("inherit",):
                ped.append("%s font:%s" % (sel, v))
    cek("pedoman_k05_f18_tanpa_ikon_emoji_bayangan_gradien", not ped, "temuan=%d" % len(ped), ped[:12])

    # 14 app.js
    pola_js = {"innerHTML": r"\.innerHTML\b", "outerHTML": r"\.outerHTML\b", "insertAdjacentHTML": r"insertAdjacentHTML",
               "document.write": r"document\.write", "eval": r"\beval\s*\(", "new Function": r"new\s+Function\b",
               "setAttribute style/on*": r"setAttribute\(\s*['\"](style|on[a-z]+)['\"]", "cssText": r"\.cssText\b"}
    temu = {k: len(re.findall(p, js)) for k, p in pola_js.items()}
    n_ls = len(re.findall(r"localStorage\.", js))
    n_ls_try = len(re.findall(r"\btry\s*\{[^{}]*localStorage\.[^{}]*\}\s*catch\b", js))
    cek("app_js_tanpa_api_html_dinamis_dan_localStorage_dalam_try",
        not any(temu.values()) and n_ls >= 1 and n_ls == n_ls_try,
        "temuan=%s localStorage=%d dalam_try=%d" % ({k: v for k, v in temu.items() if v}, n_ls, n_ls_try))

    # 15 struktur index
    h = html["index"]
    id_wajib = ["k-titik", "k-teks", "penonton", "banner", "tim-isi", "tugas-isi", "riwayat-isi", "riwayat-tombol",
                "tema-tombol", "saring", "tugas-jml", "riwayat-jml"]
    kurang = [i for i in id_wajib if not re.search(r'\sid="%s"' % i, h)]
    lain = []
    if not re.search(r'<button type="button"[^>]*id="tema-tombol"|<button[^>]*id="tema-tombol"[^>]*type="button"', h):
        lain.append("tema-tombol bukan <button type=button>")
    if not re.search(r'<nav class="saring" aria-label="Saring per agen"', h):
        lain.append("nav.saring aria-label")
    if '<form class="keluar" method="post" action="/logout">' not in h:
        lain.append("form keluar")
    if "Halaman ini memerlukan JavaScript." not in h:
        lain.append("noscript")
    if re.findall(r"<h2[^>]*>([^<]*)", h) != ["Tim", "Tugas aktif ", "Riwayat hari ini "]:
        lain.append("h2 = %s" % re.findall(r"<h2[^>]*>([^<]*)", h))
    cek("index_struktur_v3_dan_id_v2_tetap", not kurang and not lain, "id_kurang=%s lain=%s" % (kurang, lain))

    lulus = sum(x["ok"] for x in hasil)
    for x in hasil:
        print("%s %-58s %s" % ("LULUS" if x["ok"] else "GAGAL", x["nama"], x["ket"][:300]))
        if not x["ok"] and x["rinci"]:
            print("      rinci:", json.dumps(x["rinci"], ensure_ascii=False)[:600])
    print("lulus=%d gagal=%d" % (lulus, len(hasil) - lulus))
    if a.keluaran:
        with open(a.keluaran, "w", encoding="utf-8") as f:
            json.dump({"web": W, "tema_src": a.tema_src, "kontras": a.kontras, "acuan": a.acuan, "lulus": lulus,
                       "gagal": len(hasil) - lulus, "cek": hasil}, f, ensure_ascii=False, indent=1)
    return 0 if lulus == len(hasil) else 1


if __name__ == "__main__":
    sys.exit(main())
