#!/usr/bin/env python3
"""cek_v3.py - uji peramban tampilan v3 agent-dashboard (Patchright, channel chromium).

Dijalankan dari container ajeng (patchright-py) terhadap server uji lewat alamat NON-loopback (tunnel ssh yang di-bind ke
IP container ajeng). Dua server uji:
  --live URL  server dengan storage/ringkasan live (mount ro): matriks tangkapan layar, font, CSP, overflow, tema, FOUC.
  --fix  URL  server dengan fixture (tmp/test/v3/fixture, dibuat_pada disegarkan): fitur saring/rincian/gabung, isolasi,
              uji status (menunggu/bebas).
Akun uji: --pw-dir berisi berkas <label>-<akun> (password saat ini) dan <label>-<akun>.baru (dipakai bila server meminta
ganti password; sesudah berhasil, berkas <label>-<akun> ditimpa). Password tidak pernah dicetak.

  patchright-py cek_v3.py --live http://10.249.1.2:24151 --fix http://10.249.1.2:24152 --pw-dir DIR \
     --acuan-isolasi acuan-akbar.json --layar DIR --keluaran HASIL.json [--bagian a,b] [--ganti /aset/app.js=BERKAS]

Bagian: matriks, tema, fouc, fitur, isolasi, status (bawaan semua). Keluar 0 = semua lulus, 1 = ada gagal, 2 = galat alat.
Harapan fitur dihitung dari JSON mentah yang diterima halaman (direkam dari EventSource di init script, dibaca bersama DOM
dalam satu evaluate), bukan konstanta.
"""
import argparse
import datetime as dt
import json
import math
import os
import re
import sys
import time

INIT = r"""(() => { try {
  window.__rk = null; window.__nrk = 0; window.__csp = [];
  const E = window.EventSource;
  if (E) {
    class ES extends E {
      constructor(u, o) { super(u, o);
        this.addEventListener('ringkasan', ev => { try { window.__rk = JSON.parse(ev.data).data; window.__nrk++; } catch (e) {} }); }
    }
    window.EventSource = ES;
  }
  document.addEventListener('securitypolicyviolation', ev => { window.__csp.push({dir: ev.violatedDirective, blocked: ev.blockedURI, sample: ev.sample}); }, true);
  document.addEventListener('DOMContentLoaded', () => { try { window.__dcl = getComputedStyle(document.body).backgroundColor; } catch (e) {} }, {once: true});
} catch (e) {} })();"""

JS_DOM = r"""() => {
  const n = s => (s == null ? '' : String(s)).replace(/\u00a0/g, ' ').replace(/\s+/g, ' ').trim();
  const q = (s, r) => (r || document).querySelector(s), qa = (s, r) => [...(r || document).querySelectorAll(s)];
  const baris = li => ({jam: n(q('.jam', li) && q('.jam', li).textContent), teks: n(li.children[1] ? li.children[1].textContent : '')});
  const tugas = qa('#tugas-isi .tugas > li').map(li => {
    const r = q('.rinci', li), b = q('.rinci-tombol', li);
    return {judul: n(q('h3', li) && q('h3', li).textContent), tanpa: !!(q('h3', li) && q('h3', li).classList.contains('tanpa')),
      meta: n(q('.meta', li) && q('.meta', li).textContent), st: n(q('.st', li) && q('.st', li).textContent),
      langkah: q('.langkah', li) ? baris(q('.langkah', li)) : null,
      tombol: b ? {teks: n(b.textContent), exp: b.getAttribute('aria-expanded')} : null,
      rinci: r ? {dl: qa('dt', r).map(dt => [n(dt.textContent), n(dt.nextElementSibling && dt.nextElementSibling.textContent)]),
                  h4: n(q('h4', r) && q('h4', r).textContent), keg: qa('ol > li', r).map(baris),
                  kosong: n(q('.kosong', r) && q('.kosong', r).textContent)} : null};
  });
  const grup = qa('#riwayat-isi .grup').map(g => ({judul: n(q('h3', g).textContent), item: qa('ol > li', g).map(baris)}));
  const tb = q('#riwayat-tombol'), tt = q('#tema-tombol'), sv = q('nav.saring');
  return {
    data: window.__rk, nrk: window.__nrk,
    tugas, tugas_kosong: n(q('#tugas-isi > .kosong') && q('#tugas-isi > .kosong').textContent),
    tugas_jml: n(q('#tugas-jml') && q('#tugas-jml').textContent),
    grup, riwayat_kosong: n(q('#riwayat-isi > .kosong') && q('#riwayat-isi > .kosong').textContent),
    riwayat_jml: n(q('#riwayat-jml') && q('#riwayat-jml').textContent),
    tombol: tb ? {hidden: tb.hidden, teks: n(tb.textContent)} : null,
    saring: sv ? {hidden: sv.hidden, lbl: n(q('.lbl', sv) && q('.lbl', sv).textContent),
                  tombol: qa('button', sv).map(b => ({teks: n(b.textContent), pressed: b.getAttribute('aria-pressed')}))} : null,
    pohon: qa('#tim-isi button.simpul.agen').map(b => ({nm: n(q('.nm', b) && q('.nm', b).textContent), pressed: b.getAttribute('aria-pressed'),
             st: n(q('.st', b) && q('.st', b).textContent)})),
    pohon_urut_ok: qa('#tim-isi ul').every(ul => { const k = [...ul.children].map(li => !!li.querySelector(':scope > ul'));
             return k.every((x, i) => !x || k.slice(i).every(Boolean)); }),
    koneksi: n(q('#k-teks') && q('#k-teks').textContent),
    tema: document.documentElement.dataset.tema || null,
    tema_tombol: tt ? {hidden: tt.hidden, teks: n(tt.textContent), pressed: tt.getAttribute('aria-pressed')} : null,
    bg: getComputedStyle(document.body).backgroundColor,
    sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth,
    teks_halaman: n(document.body.innerText),
    teks_tugas_riwayat: n((q('#tugas-isi') ? q('#tugas-isi').innerText : '') + ' ' + (q('#riwayat-isi') ? q('#riwayat-isi').innerText : '')),
  };
}"""

JS_FONT = r"""async () => { await document.fonts.ready;
  return {status: document.fonts.status, f: [...document.fonts].map(f => ({family: f.family.replace(/"/g, ''), weight: String(f.weight), status: f.status}))}; }"""

JS_WARNA_STATUS = r"""() => {
  const cx = document.createElement('canvas').getContext('2d');
  const rgb = v => { cx.fillStyle = '#010203'; cx.fillStyle = v.trim(); return cx.fillStyle.toLowerCase(); };
  const v = k => rgb(getComputedStyle(document.documentElement).getPropertyValue(k));
  const out = [];
  for (const t of document.querySelectorAll('.titik')) {
    const k = [...t.classList].find(c => c !== 'titik') || '';
    out.push({kelas: k, bg: rgb(getComputedStyle(t).backgroundColor)});
  }
  const lbl = [...document.querySelectorAll('.label.menunggu')].map(e => rgb(getComputedStyle(e).color));
  return {titik: out, label_menunggu: lbl, v: {jalan: v('--jalan'), menunggu: v('--menunggu'), bebas: v('--bebas'),
          menunggu_teks: v('--menunggu-teks'), latar: v('--latar')}};
}"""

BLN = ["Jan", "Feb", "Mar", "Apr", "Mei", "Jun", "Jul", "Agu", "Sep", "Okt", "Nov", "Des"]
LABEL = {"bebas": "bebas", "jalan": "sedang jalan", "menunggu": "menunggu keputusan", "sibuk": "sibuk"}
BG = {"terang": "rgb(255, 255, 255)", "gelap": "rgb(19, 19, 22)"}
LABEL_UI = ("Agen BSK Diperbarui Menyambung Tema gelap terang Keluar Tampilkan Semua Tim Tugas aktif Riwayat hari ini peristiwa "
            "Lihat Tutup rincian Mulai Lama Project Pemberi Pengerja Langkah terakhir Kegiatan sejak mulai mnt j Belum ada "
            "tercatat Tidak tugas tidak sedang memegang Judul belum pemberi jalan menunggu keputusan bebas sibuk jam sebelumnya "
            "Pak Akbar Mas Dicky Jati Terputus data menyambung ulang Data basi generator memperbarui Galat Ringkasan tersedia "
            + " ".join(BLN)).split()


class Galat(Exception):
    pass


# ------------------------------------------------------------------ harapan (dihitung dari JSON mentah)
def ms(iso):
    try:
        return dt.datetime.fromisoformat(iso).timestamp() * 1000 if iso else None
    except (TypeError, ValueError):
        return None


def jam(iso):
    m = re.search(r"T(\d\d):(\d\d)", iso or "")
    return "%s.%s" % m.groups() if m else ""


def detik(iso):
    m = re.search(r"T(\d\d):(\d\d):(\d\d)", iso or "")
    return "%s.%s.%s" % m.groups() if m else ""


def tgl_beda(a, b):
    return a and b and a[:10] != b[:10]


def waktu_mulai(mulai, dibuat, fungsi):
    if tgl_beda(mulai, dibuat):
        return "%d %s %s" % (int(mulai[8:10]), BLN[int(mulai[5:7]) - 1], fungsi(mulai))
    return fungsi(mulai)


def durasi(a, b):
    m = max(0, math.floor((ms(b) - ms(a)) / 60000 + 0.5))   # = Math.round JS
    return "%d mnt" % m if m < 60 else "%d j %d mnt" % (m // 60, m % 60)


def gabung(daftar):
    out = []
    for r in daftar:
        p = out[-1] if out else None
        if p and p["pelaku"] == r["pelaku"] and p["teks"] == r["teks"] and ms(r["waktu"]) - ms(p["akhir"]) <= 600000:
            p["n"] += 1
            p["akhir"] = r["waktu"]
        else:
            out.append({"pelaku": r["pelaku"], "teks": r["teks"], "awal": r["waktu"], "akhir": r["waktu"], "n": 1})
    return out


def baris_riwayat(g):
    j = "%s–%s" % (jam(g["awal"]), jam(g["akhir"])) if g["n"] > 1 and jam(g["awal"]) != jam(g["akhir"]) else jam(g["akhir"])
    return {"jam": j, "teks": g["teks"] + (" ×%d" % g["n"] if g["n"] > 1 else "")}


def urut_riwayat(rw):
    return [x for _, x in sorted(enumerate(rw), key=lambda p: (ms(p[1].get("waktu")) or -8.64e15, p[0]))]


def harap_riwayat(D, saring, batas):
    r = [x for x in urut_riwayat(D["riwayat_hari_ini"]) if not saring or x["pelaku"] == saring]
    g = gabung(r)[::-1]
    per = []
    for x in g:
        j = x["akhir"][11:13]
        if not per or per[-1][0] != j:
            per.append((j, []))
        per[-1][1].append(x)
    tampil = per[:batas]
    sisa = sum(x["n"] for _, xs in per[batas:] for x in xs)
    return {"grup": [{"judul": "%s.00–%s.59" % (j, j), "item": [baris_riwayat(x) for x in xs]} for j, xs in tampil],
            "jml": "%d peristiwa" % len(r), "kosong": "" if r else "Belum ada peristiwa hari ini.",
            "tombol": {"hidden": sisa == 0, "teks": "Tampilkan jam sebelumnya (%d peristiwa)" % sisa} if sisa else {"hidden": True}}


def peringkat(st):
    return 0 if st == "menunggu" else (1 if st == "jalan" else 2)


def urut_tugas(ts):
    def k(t):
        m = ms(t.get("mulai"))
        return (peringkat(t.get("status")), m is None, m or 0, str(t.get("id")))
    return sorted(ts, key=k)


def harap_tugas(D, saring, terbuka):
    agen = {a["id"]: a for a in D["agen"]}
    dib = D["dibuat_pada"]
    out = []
    for t in urut_tugas([t for t in D["tugas_aktif"] if not saring or t.get("pengerja_id") == saring]):
        prj = t.get("project_nama") or t.get("project")
        st = LABEL.get(t["status"], t["status"])
        if t.get("mulai"):
            st += " · sejak %s (%s)" % (waktu_mulai(t["mulai"], dib, jam), durasi(t["mulai"], dib))
        x = {"judul": t.get("judul") or "Judul belum tercatat", "tanpa": not t.get("judul"),
             "meta": ("%s · " % prj if prj else "") + (t.get("pemberi") or "pemberi belum tercatat") + " → " + (t.get("pengerja") or "(tanpa pengerja)"),
             "st": "%s" % st,
             "langkah": {"jam": jam(t.get("langkah_waktu")), "teks": t["langkah_terakhir"]} if t.get("langkah_terakhir") else None,
             "tombol": {"teks": "Tutup rincian" if t["id"] in terbuka else "Lihat rincian", "exp": "true" if t["id"] in terbuka else "false"},
             "rinci": None}
        if t["id"] in terbuka:
            peran = (agen.get(t.get("pengerja_id")) or {}).get("peran")
            lw, lt = t.get("langkah_waktu"), t.get("langkah_terakhir")
            keg = []
            if t.get("mulai"):
                keg = gabung([r for r in urut_riwayat(D["riwayat_hari_ini"]) if r["pelaku"] == t.get("pengerja_id")
                              and ms(r["waktu"]) is not None and ms(r["waktu"]) >= ms(t["mulai"])])[::-1]
            x["rinci"] = {"dl": [["Mulai", waktu_mulai(t["mulai"], dib, detik) if t.get("mulai") else "–"],
                                 ["Lama", durasi(t["mulai"], dib) if t.get("mulai") else "–"],
                                 ["Project", prj or "–"], ["Pemberi", t.get("pemberi") or "belum tercatat"],
                                 ["Pengerja", t.get("pengerja", "") + (" (%s)" % peran if peran else "")],
                                 ["Langkah terakhir", ((detik(lw) + " · ") if lw else "") + lt if lt else "–"]],
                          "h4": "Kegiatan %s sejak mulai" % t.get("pengerja", ""), "keg": [baris_riwayat(g) for g in keg],
                          "kosong": "" if keg else "Belum ada peristiwa tercatat."}
        out.append(x)
    nama = (agen.get(saring) or {}).get("nama")
    kosong = "" if out else ("%s tidak sedang memegang tugas." % nama if saring else "Tidak ada tugas aktif.")
    return {"tugas": out, "jml": str(len(out)), "kosong": kosong}


def harap_saring(D, saring):
    return {"hidden": False, "lbl": "Tampilkan",
            "tombol": [{"teks": "Semua", "pressed": "true" if saring is None else "false"}] +
                      [{"teks": a["nama"], "pressed": "true" if saring == a["id"] else "false"} for a in D["agen"]]}


def norm(s):
    return re.sub(r"\s+", " ", (s or "").replace("\u00a0", " ")).strip()


def kata(s):
    return set(re.findall(r"[A-Za-zÀ-ÿ][A-Za-zÀ-ÿ'-]*", norm(s)))


def string_json(o, out):
    if isinstance(o, str):
        out.append(o)
    elif isinstance(o, dict):
        for v in o.values():
            string_json(v, out)
    elif isinstance(o, list):
        for v in o:
            string_json(v, out)
    return out


# ------------------------------------------------------------------ alat peramban
class Pantau:
    def __init__(self, ctx, page, rahasia):
        self.log, self.req, self.rahasia = [], [], [r for r in rahasia if r]
        page.on("request", lambda r: self.req.append(r.url))
        c = ctx.new_cdp_session(page)
        self.cdp = c

        def tambah(jenis, teks, url=None):
            for r in self.rahasia:
                teks = teks.replace(r, "***")
            self.log.append({"jenis": jenis, "teks": teks[:240], "url": url})
        c.on("Runtime.consoleAPICalled", lambda e: tambah("console." + e["type"], str([x.get("value", x.get("description")) for x in e["args"]]))
             if e["type"] in ("error", "assert", "warning") else None)
        c.on("Runtime.exceptionThrown", lambda e: tambah("exception", str(e["exceptionDetails"].get("exception", {}).get("description", e["exceptionDetails"].get("text")))))
        c.on("Log.entryAdded", lambda e: tambah("log." + e["entry"]["source"], e["entry"]["text"], e["entry"].get("url")) if e["entry"]["level"] in ("error", "warning") else None)
        c.send("Runtime.enable")
        c.send("Log.enable")

    def galat(self):
        fav = [x for x in self.log if (x["url"] or "").split("?")[0].endswith("/favicon.ico")]
        return [x for x in self.log if x not in fav], len(fav)


def penyaji(isi, tipe):
    def h(route):
        route.fulfill(status=200, body=isi, headers={"Content-Type": tipe})
    return h


def pasang_init(cdp, skrip):
    """Init script lewat CDP (Page.addScriptToEvaluateOnNewDocument, dunia utama). JANGAN pakai add_init_script Patchright:
    Patchright menyuntikkannya dengan mencegat respons dokumen, sehingga dokumen dianggap ruang alamat `public` dan Chromium
    (Local Network Access) memblokir CSS/JS same-origin dari IP privat (terukur 17 Okt, Chromium 153.0.8010.12)."""
    cdp.send("Page.enable")
    for s in skrip:
        cdp.send("Page.addScriptToEvaluateOnNewDocument", {"source": s})


def ev(page, js, arg=None):
    return page.evaluate(js, arg, isolated_context=False) if arg is not None else page.evaluate(js, isolated_context=False)


class Uji:
    def __init__(self, a, br):
        self.a, self.br, self.hasil, self.state, self.rahasia = a, br, [], {}, []
        self.ganti = {}
        for g in a.ganti or []:
            p, f = g.split("=", 1)
            self.ganti[p] = open(f, "rb").read()

    def cek(self, bagian, nama, ok, ket, rinci=None):
        self.hasil.append({"bagian": bagian, "nama": nama, "ok": bool(ok), "ket": ket, "rinci": rinci})

    # ---- akun
    def pw(self, label, akun, baru=False):
        p = os.path.join(self.a.pw_dir, "%s-%s%s" % (label, akun, ".baru" if baru else ""))
        v = open(p, encoding="utf-8").read().strip()
        self.rahasia.append(v)
        return v

    def masuk(self, label, base, akun):
        k = (label, akun)
        if k in self.state:
            return self.state[k]
        ctx = self.br.new_context()
        pw = self.pw(label, akun)
        r = ctx.request.post(base + "/login", form={"akun": akun, "password": pw}, headers={"Origin": base}, max_redirects=0)
        lok = r.headers.get("location")
        if r.status != 303:
            ctx.close()
            raise Galat("login %s/%s status %d" % (label, akun, r.status))
        if lok == "/ganti-password":
            baru = self.pw(label, akun, True)
            r = ctx.request.post(base + "/ganti-password", form={"password_baru": baru, "password_ulang": baru},
                                 headers={"Origin": base}, max_redirects=0)
            if r.status != 303 or r.headers.get("location") != "/":
                ctx.close()
                raise Galat("ganti password %s/%s status %d" % (label, akun, r.status))
            p = os.path.join(self.a.pw_dir, "%s-%s" % (label, akun))
            os.replace(p + ".baru", p)
        st = ctx.storage_state()
        ctx.close()
        self.state[k] = st
        return st

    # ---- halaman
    def buka(self, base, path, lebar, tema=None, perangkat="light", state=None, init_tambahan=None, tunggu_data=True, isi_akun=False):
        ctx = self.br.new_context(viewport={"width": lebar, "height": 768 if lebar > 600 else 844},
                                  device_scale_factor=1 if lebar > 600 else 2, color_scheme=perangkat, storage_state=state)
        for p, isi in self.ganti.items():
            ctx.route("**" + p, penyaji(isi, "text/css; charset=utf-8" if p.endswith(".css") else "text/javascript; charset=utf-8"))
        ctx.set_default_timeout(5000)
        ctx.set_default_navigation_timeout(30000)
        page = ctx.new_page()
        mon = Pantau(ctx, page, self.rahasia)
        pasang_init(mon.cdp, [INIT] + (["try { localStorage.setItem('tema', %s); } catch (e) {}" % json.dumps(tema)] if tema else [])
                    + list(init_tambahan or []))
        page.goto(base + path, wait_until="load")
        if isi_akun:
            page.fill("#akun", "akbar")       # agar teks 400 ikut dipakai di halaman masuk
            ev(page, "document.activeElement && document.activeElement.blur()")
        if tunggu_data:
            t0 = time.time()
            while time.time() - t0 < 15 and not ev(page, "!!window.__rk && !!document.querySelector('#tim-isi *')"):
                page.wait_for_timeout(200)
        ev(page, "document.fonts.ready.then(() => 1)")
        page.wait_for_timeout(300)
        return ctx, page, mon

    def font_cdp(self, mon, page, pilih):
        """CSS.getPlatformFontsForNode untuk elemen pertama tiap selektor -> {sel: [familyName...]}."""
        c = mon.cdp
        hasil = {}
        try:
            c.send("DOM.enable")
            c.send("CSS.enable")
            akar = c.send("DOM.getDocument", {"depth": -1})["root"]["nodeId"]
            for sel in pilih:
                nid = c.send("DOM.querySelector", {"nodeId": akar, "selector": sel}).get("nodeId")
                if not nid:
                    hasil[sel] = None
                    continue
                f = c.send("CSS.getPlatformFontsForNode", {"nodeId": nid}).get("fonts", [])
                hasil[sel] = sorted({x["familyName"] for x in f})
        except Exception as e:  # noqa: BLE001
            hasil["galat"] = str(e)[:120]
        return hasil

    def periksa_umum(self, bagian, nama, base, page, mon, lebar, tema, pilih_font, layar=None):
        if layar:
            os.makedirs(self.a.layar, exist_ok=True)
            page.screenshot(path=os.path.join(self.a.layar, layar), full_page=True)
        d = ev(page, JS_DOM)
        f = ev(page, JS_FONT)
        inter = {}
        for x in f["f"]:
            if x["family"].lower() == "inter":
                inter.setdefault(x["weight"], []).append(x["status"])
        fc = self.font_cdp(mon, page, pilih_font)
        ok_font = f["status"] == "loaded" and "loaded" in inter.get("400", []) and "loaded" in inter.get("600", []) and \
            all(v and all(x.startswith("Inter") for x in v) for k, v in fc.items() if k != "galat") and "galat" not in fc
        self.cek(bagian, nama + ":font_inter_400_600", ok_font, "fonts.status=%s Inter=%s platform=%s" % (f["status"], inter, fc))
        self.cek(bagian, nama + ":tanpa_scroll_horizontal", d["sw"] <= d["cw"], "scrollWidth=%s clientWidth=%s" % (d["sw"], d["cw"]))
        csp = ev(page, "JSON.stringify(window.__csp || [])")
        gal, fav = mon.galat()
        self.cek(bagian, nama + ":0_csp_0_galat_konsol", json.loads(csp) == [] and not gal,
                 "csp=%d galat=%d (favicon.ico 404 dikecualikan=%d)" % (len(json.loads(csp)), len(gal), fav), {"csp": json.loads(csp)[:3], "galat": gal[:4]})
        luar = sorted({u[:120] for u in mon.req if not (u == base or u.startswith(base + "/")) and not u.startswith(("data:", "blob:"))})
        self.cek(bagian, nama + ":0_request_luar_origin", not luar and mon.req, "request=%d luar=%d" % (len(mon.req), len(luar)), luar[:5])
        if tema:
            self.cek(bagian, nama + ":tema_diterapkan", d["tema"] == tema and d["bg"] == BG[tema], "data-tema=%s bg=%s" % (d["tema"], d["bg"]))
        return d

    # ------------------------------------------------------------------ bagian
    def matriks(self):
        a = self.a
        for hal, akun in (("utama", "akbar"), ("terbatas", "dicky"), ("login", None)):
            for tema in ("terang", "gelap"):
                for lebar in (1366, 390):
                    nm = "%s-%s-%d" % (hal, tema, lebar)
                    try:
                        st = self.masuk("live", a.live, akun) if akun else None
                        ctx, page, mon = self.buka(a.live, "/" if akun else "/login", lebar, tema, state=st, tunggu_data=bool(akun),
                                                   isi_akun=not akun)
                        pilih = [".peran", ".nm", "h2"] if akun else ["h1", "label"]
                        d = self.periksa_umum("matriks", nm, a.live, page, mon, lebar, tema, pilih, layar=nm + ".png")
                        if akun:
                            harap = "Tema terang" if tema == "gelap" else "Tema gelap"
                            tt = d["tema_tombol"] or {}
                            self.cek("matriks", nm + ":tombol_tema", tt.get("teks") == harap and tt.get("hidden") is False and
                                     tt.get("pressed") == ("true" if tema == "gelap" else "false"), "tombol=%s" % tt)
                            self.cek_isolasi_teks("matriks", nm, d, None)
                            if lebar == 390 or hal == "utama":
                                self.overflow_interaksi("matriks", nm, page)
                        else:
                            js = [u for u in mon.req if u.endswith("/aset/app.js")]
                            self.cek("matriks", nm + ":login_tanpa_app_js_tanpa_tombol_tema", not js and d["tema_tombol"] is None,
                                     "request app.js=%d tombol=%s" % (len(js), d["tema_tombol"]))
                        ctx.close()
                    except Exception as e:  # noqa: BLE001
                        self.cek("matriks", nm + ":jalan", False, "galat %s: %s" % (type(e).__name__, self.aman(str(e))[:300]))

    def overflow_interaksi(self, bagian, nm, page):
        """Saring aktif (agen pertama yang punya tugas, kalau ada) + rincian pertama terbuka -> tetap tanpa scroll horizontal."""
        d = ev(page, JS_DOM)
        D = d["data"] or {}
        target = next((t.get("pengerja_id") for t in urut_tugas(D.get("tugas_aktif", []))), None) or \
            ((D.get("agen") or [{}])[0].get("id"))
        nama = next((x["nama"] for x in D.get("agen", []) if x["id"] == target), None)
        ok_klik = False
        if nama and d["saring"]:
            page.locator("nav.saring button", has_text=re.compile("^%s$" % re.escape(nama))).first.click()
            ok_klik = True
            if page.locator(".rinci-tombol").count():
                page.locator(".rinci-tombol").first.click()
        d2 = ev(page, JS_DOM)
        rinci = any(t["rinci"] for t in d2["tugas"])
        self.cek(bagian, nm + ":tanpa_scroll_horizontal_saring_rincian", ok_klik and d2["sw"] <= d2["cw"],
                 "saring=%s rincian_terbuka=%s scrollWidth=%s clientWidth=%s" % (nama, rinci, d2["sw"], d2["cw"]))

    def aman(self, s):
        for r in self.rahasia:
            s = s.replace(r, "***")
        return s

    def cek_isolasi_teks(self, bagian, nm, d, acuan):
        """innerText halaman (penonton terbatas) hanya memuat kata dari JSON penonton itu + label UI; tanpa string order lain."""
        D = d["data"]
        if not D or D.get("cakupan") != "order-sendiri":
            return
        vocab = set()
        for s in string_json(D, []):
            vocab |= kata(s)
        vocab |= set(LABEL_UI)
        asing_kata = sorted(kata(d["teks_halaman"]) - vocab)
        self.cek(bagian, nm + ":isolasi_kata_subset_json_label", not asing_kata, "kata asing=%d" % len(asing_kata), asing_kata[:10])
        if acuan:
            milik = {t["id"] for t in D["tugas_aktif"]}
            sah = set(string_json(D, []))
            terlarang = set()
            for t in acuan["tugas_aktif"]:
                if t["id"] not in milik:
                    terlarang |= {t.get(k) for k in ("judul", "project", "project_nama") if t.get(k) and t.get(k) not in sah}
            rw_milik = {r["teks"] for r in D["riwayat_hari_ini"]}
            terlarang |= {r["teks"] for r in acuan["riwayat_hari_ini"] if r["teks"] not in rw_milik}
            muncul = sorted(x for x in terlarang if norm(x) in d["teks_halaman"])
            pemberi_lain = sorted({t.get("pemberi") for t in acuan["tugas_aktif"] if t["id"] not in milik and t.get("pemberi")} -
                                  {t.get("pemberi") for t in D["tugas_aktif"]})
            pm = [p for p in pemberi_lain if p in d["teks_tugas_riwayat"]]
            self.cek(bagian, nm + ":isolasi_0_judul_project_pemberi_riwayat_lain", not muncul and not pm and len(terlarang) > 0,
                     "string order lain diuji=%d muncul=%d; pemberi lain %s muncul di tugas/riwayat=%d" % (len(terlarang), len(muncul), pemberi_lain, len(pm)),
                     {"muncul": muncul[:5], "pemberi": pm})

    def tema(self):
        a = self.a
        try:
            st = self.masuk("live", a.live, "akbar")
            ctx, page, mon = self.buka(a.live, "/", 1366, None, "light", st)
            d0 = ev(page, JS_DOM)
            page.click("#tema-tombol")
            d1 = ev(page, JS_DOM)
            ls = ev(page, "(() => { try { return localStorage.getItem('tema'); } catch (e) { return 'GALAT'; } })()")
            page.reload(wait_until="load")
            page.wait_for_timeout(800)
            d2 = ev(page, JS_DOM)
            ctx.clear_cookies()
            page.goto(a.live + "/login", wait_until="load")
            d3 = ev(page, JS_DOM)
            ok = (d0["tema"] == "terang" and d0["bg"] == BG["terang"] and (d0["tema_tombol"] or {}).get("teks") == "Tema gelap" and
                  d1["tema"] == "gelap" and d1["bg"] == BG["gelap"] and ls == "gelap" and (d1["tema_tombol"] or {}).get("teks") == "Tema terang" and
                  (d1["tema_tombol"] or {}).get("pressed") == "true" and
                  d2["tema"] == "gelap" and d2["bg"] == BG["gelap"] and (d2["tema_tombol"] or {}).get("teks") == "Tema terang" and
                  d3["tema"] == "gelap" and d3["bg"] == BG["gelap"])
            self.cek("tema", "pilihan_tersimpan_bertahan_reload_dan_login", ok,
                     "awal=%s/%s klik=%s/%s ls=%s reload=%s/%s login=%s/%s" % (d0["tema"], (d0["tema_tombol"] or {}).get("teks"), d1["tema"],
                     (d1["tema_tombol"] or {}).get("teks"), ls, d2["tema"], d2["bg"], d3["tema"], d3["bg"]))
            gal, _ = mon.galat()
            self.cek("tema", "pilihan_tersimpan:0_galat", not gal, "galat=%d" % len(gal), gal[:3])
            ctx.close()
            for perangkat, harap in (("dark", "gelap"), ("light", "terang")):
                ctx, page, mon = self.buka(a.live, "/login", 390, None, perangkat, None, tunggu_data=False)
                d = ev(page, JS_DOM)
                self.cek("tema", "tanpa_pilihan_ikut_perangkat_%s" % perangkat, d["tema"] == harap and d["bg"] == BG[harap],
                         "data-tema=%s bg=%s" % (d["tema"], d["bg"]))
                ctx.close()
            blok = ("Object.defineProperty(window, 'localStorage', {configurable: true, "
                    "get() { throw new DOMException('diblokir', 'SecurityError'); }});")
            ctx, page, mon = self.buka(a.live, "/", 1366, None, "dark", st, init_tambahan=[blok])
            d0 = ev(page, JS_DOM)
            page.click("#tema-tombol")
            d1 = ev(page, JS_DOM)
            gal, _ = mon.galat()
            self.cek("tema", "localStorage_diblokir_ikut_perangkat_tanpa_galat",
                     d0["tema"] == "gelap" and d1["tema"] == "terang" and d1["bg"] == BG["terang"] and not gal,
                     "awal=%s sesudah_klik=%s galat=%d" % (d0["tema"], d1["tema"], len(gal)), gal[:3])
            ctx.close()
        except Exception as e:  # noqa: BLE001
            self.cek("tema", "jalan", False, "galat %s: %s" % (type(e).__name__, self.aman(str(e))[:300]))

    def fouc(self):
        a = self.a
        for path, simpan, perangkat, harap in (("/", "gelap", "light", "gelap"), ("/", "terang", "dark", "terang"),
                                               ("/login", "gelap", "light", "gelap"), ("/login", "terang", "dark", "terang")):
            nm = "%s_simpan_%s_perangkat_%s" % ("utama" if path == "/" else "login", simpan, perangkat)
            try:
                st = self.masuk("live", a.live, "akbar") if path == "/" else None
                ctx = self.br.new_context(viewport={"width": 1366, "height": 768}, color_scheme=perangkat, storage_state=st)
                tahan = {}
                page = ctx.new_page()
                pasang_init(ctx.new_cdp_session(page), [INIT, "try { localStorage.setItem('tema', %s); } catch (e) {}" % json.dumps(simpan)])
                for pola in ("**/tema.js", "**/app.js"):
                    page.route(pola, lambda route: tahan.__setitem__(route.request.url.rsplit("/", 1)[-1], route))
                page.goto(a.live + path, wait_until="commit")
                sampel, t0, lepas_tema = [], time.time(), False
                js = ("() => { const b = document.body; if (!b) return null; const c = getComputedStyle(b);"
                      " const tt = document.getElementById('tema-tombol');"
                      " return {css: c.fontFamily.includes('Inter'), bg: c.backgroundColor, tema: document.documentElement.dataset.tema || null,"
                      " appjs: !!(tt && !tt.hidden && tt.textContent)}; }")
                while time.time() - t0 < 6:
                    if not lepas_tema and time.time() - t0 >= 2.0:
                        for k in list(tahan):
                            if k == "tema.js":
                                self.lepas(tahan.pop(k))
                                lepas_tema = True
                    s = ev(page, js)
                    if s:
                        s["t"] = round(time.time() - t0, 2)
                        s["tahan_app"] = "app.js" in tahan or path != "/"
                        sampel.append(s)
                    if lepas_tema and s and s["css"] and (path != "/" or "app.js" in tahan) and len([x for x in sampel if x["css"]]) >= 3:
                        break
                    page.wait_for_timeout(100)
                for k in list(tahan):
                    self.lepas(tahan.pop(k))
                page.wait_for_load_state("load")
                page.wait_for_timeout(300)
                dcl = ev(page, "window.__dcl || null")
                tampak = [s for s in sampel if s["css"]]
                salah = [s for s in tampak if s["bg"] != BG[harap]]
                saat_app_ditahan = [s for s in tampak if s["tahan_app"] and not s["appjs"]]
                ok = tampak and not salah and saat_app_ditahan and dcl == BG[harap]
                self.cek("fouc", nm, ok, "sampel_tampak=%d salah=%d sampel_saat_app.js_ditahan=%d bg_DOMContentLoaded=%s harap=%s" % (
                    len(tampak), len(salah), len(saat_app_ditahan), dcl, BG[harap]), {"salah": salah[:3], "sampel": sampel[:4]})
                ctx.close()
            except Exception as e:  # noqa: BLE001
                self.cek("fouc", nm, False, "galat %s: %s" % (type(e).__name__, self.aman(str(e))[:300]))

    def lepas(self, route):
        u = route.request.url
        for p, isi in self.ganti.items():
            if u.endswith(p):
                route.fulfill(status=200, body=isi, headers={"Content-Type": "text/javascript; charset=utf-8"})
                return
        route.continue_()

    # ---- fitur
    def banding_dom(self, bagian, nm, page, saring, terbuka, batas):
        d = ev(page, JS_DOM)
        D = d["data"]
        ht = harap_tugas(D, saring, terbuka)
        hr = harap_riwayat(D, saring, batas)
        nyata_t = [{k: x[k] for k in ("judul", "tanpa", "meta", "st", "langkah", "tombol", "rinci")} for x in d["tugas"]]
        self.cek(bagian, nm + ":tugas_sesuai_json", nyata_t == ht["tugas"] and d["tugas_jml"] == ht["jml"] and d["tugas_kosong"] == ht["kosong"],
                 "tugas harap=%d nyata=%d jml=%s/%s kosong=%r" % (len(ht["tugas"]), len(nyata_t), ht["jml"], d["tugas_jml"], d["tugas_kosong"]),
                 self.beda(ht["tugas"], nyata_t))
        tb = d["tombol"] or {}
        tb_ok = tb.get("hidden") is True if hr["tombol"]["hidden"] else (tb.get("hidden") is False and tb.get("teks") == hr["tombol"]["teks"])
        self.cek(bagian, nm + ":riwayat_sesuai_json_gabung_d5", d["grup"] == hr["grup"] and d["riwayat_jml"] == hr["jml"] and
                 d["riwayat_kosong"] == hr["kosong"] and tb_ok,
                 "grup harap=%d nyata=%d baris harap=%d nyata=%d jml=%s/%s tombol=%s/%s" % (
                     len(hr["grup"]), len(d["grup"]), sum(len(g["item"]) for g in hr["grup"]), sum(len(g["item"]) for g in d["grup"]),
                     hr["jml"], d["riwayat_jml"], hr["tombol"].get("teks", "tersembunyi"), tb), self.beda(hr["grup"], d["grup"]))
        hs = harap_saring(D, saring)
        pohon_ok = sorted(x["nm"] for x in d["pohon"]) == sorted(a_["nama"] for a_ in D["agen"]) and all(
            x["pressed"] == ("true" if any(a_["id"] == saring and a_["nama"] == x["nm"] for a_ in D["agen"]) else "false") for x in d["pohon"])
        self.cek(bagian, nm + ":saring_dan_pohon_aria_pressed", d["saring"] == hs and pohon_ok and d["pohon_urut_ok"],
                 "saring=%s pohon=%s daun_dulu=%s" % ([(x["teks"], x["pressed"]) for x in (d["saring"] or {}).get("tombol", [])],
                                                      [(x["nm"], x["pressed"]) for x in d["pohon"]], d["pohon_urut_ok"]))
        self.cek(bagian, nm + ":tanpa_scroll_horizontal", d["sw"] <= d["cw"], "scrollWidth=%s clientWidth=%s" % (d["sw"], d["cw"]))
        return d

    @staticmethod
    def beda(h, n):
        if h == n:
            return None
        if isinstance(h, list) and isinstance(n, list):
            for i, (x, y) in enumerate(zip(h, n)):
                if x != y:
                    return {"indeks": i, "harap": x, "nyata": y}
            return {"panjang_harap": len(h), "panjang_nyata": len(n)}
        return {"harap": h, "nyata": n}

    def fitur(self):
        a = self.a
        for lebar in (1366, 390):
            b = "fitur%d" % lebar
            try:
                st = self.masuk("fix", a.fix, "akbar")
                ctx, page, mon = self.buka(a.fix, "/", lebar, "terang", "light", st)
                D = ev(page, "window.__rk")
                if not D:
                    raise Galat("ringkasan tidak diterima")
                self.banding_dom(b, "awal_semua", page, None, set(), 3)
                beta = next((x for x in D["agen"] if x["id"] == "beta"), None)
                n_beta_t = sum(1 for t in D["tugas_aktif"] if t.get("pengerja_id") == "beta")
                n_beta_r = sum(1 for r in D["riwayat_hari_ini"] if r["pelaku"] == "beta")
                self.cek(b, "fixture_punya_tugas_dan_riwayat_beta", beta and n_beta_t >= 1 and n_beta_r >= 1,
                         "tugas beta=%d riwayat beta=%d (dihitung dari JSON)" % (n_beta_t, n_beta_r))
                page.locator("nav.saring button", has_text=re.compile("^Beta$")).click()
                d = self.banding_dom(b, "saring_Beta", page, "beta", set(), 3)
                pengerja = {t["meta"].rsplit(" → ", 1)[-1] for t in d["tugas"]}
                self.cek(b, "saring_Beta:hanya_pengerja_Beta", pengerja <= {"Beta"} and len(d["tugas"]) == n_beta_t and
                         d["riwayat_jml"] == "%d peristiwa" % n_beta_r,
                         "pengerja tampil=%s tugas=%d/%d riwayat_jml=%s/%d" % (sorted(pengerja), len(d["tugas"]), n_beta_t, d["riwayat_jml"], n_beta_r))
                id_beta = [t["id"] for t in urut_tugas([t for t in D["tugas_aktif"] if t.get("pengerja_id") == "beta"])]
                page.locator(".rinci-tombol").first.click()
                d = self.banding_dom(b, "rincian_Beta_terbuka", page, "beta", {id_beta[0]}, 3)
                fokus = ev(page, "document.activeElement && document.activeElement.className")
                n0 = ev(page, "window.__nrk")
                t0 = time.time()
                while time.time() - t0 < 8 and ev(page, "window.__nrk") == n0:
                    page.wait_for_timeout(250)
                d = self.banding_dom(b, "rincian_bertahan_sesudah_data_baru", page, "beta", {id_beta[0]}, 3)
                fokus2 = ev(page, "document.activeElement && document.activeElement.className")
                self.cek(b, "rincian:data_baru_diterima_fokus_tetap", ev(page, "window.__nrk") > n0 and fokus == fokus2 and "rinci-tombol" in (fokus2 or ""),
                         "event ringkasan %s->%s fokus=%s->%s" % (n0, ev(page, "window.__nrk"), fokus, fokus2))
                page.locator(".rinci-tombol").first.click()
                page.locator("#tim-isi button.simpul.agen", has=page.locator(".nm", has_text=re.compile("^Desy$"))).click()
                self.banding_dom(b, "klik_pohon_Desy", page, "desy", set(), 3)
                page.locator("#tim-isi button.simpul.agen", has=page.locator(".nm", has_text=re.compile("^Desy$"))).click()
                self.banding_dom(b, "klik_pohon_Desy_lagi_batal", page, None, set(), 3)
                page.locator("nav.saring button", has_text=re.compile("^Carli$")).click()
                d = self.banding_dom(b, "saring_Carli", page, "carli", set(), 3)
                batas = 3
                while not (d["tombol"] or {}).get("hidden", True) and batas < 30:
                    page.click("#riwayat-tombol")
                    batas += 3
                    d = self.banding_dom(b, "saring_Carli_jam_sebelumnya_%d" % batas, page, "carli", set(), batas)
                semua = [x for g in d["grup"] for x in g["item"]]
                uji = [x for x in semua if x["teks"].startswith("Carli mencatat kemajuan · Uji gabung")]
                self.cek(b, "gabung_batas_10_menit_fixture",
                         uji == [{"jam": "06.24", "teks": "Carli mencatat kemajuan · Uji gabung"},
                                 {"jam": "06.00–06.14", "teks": "Carli mencatat kemajuan · Uji gabung ×3"}],
                         "baris uji gabung = %s (harap 06.24 tunggal + 06.00–06.14 ×3; jeda 10:00 gabung, 10:01 pisah)" % uji)
                page.locator("nav.saring button", has_text=re.compile("^Semua$")).click()
                d = self.banding_dom(b, "kembali_Semua", page, None, set(), 3)
                gal, _ = mon.galat()
                csp = json.loads(ev(page, "JSON.stringify(window.__csp || [])"))
                self.cek(b, "0_csp_0_galat_konsol", not gal and not csp, "galat=%d csp=%d" % (len(gal), len(csp)), gal[:3])
                ctx.close()
            except Exception as e:  # noqa: BLE001
                self.cek(b, "jalan", False, "galat %s: %s" % (type(e).__name__, self.aman(str(e))[:300]))

    def isolasi(self):
        a = self.a
        acuan = json.load(open(a.acuan_isolasi, encoding="utf-8"))
        for lebar in (1366, 390):
            b = "isolasi%d" % lebar
            try:
                st = self.masuk("fix", a.fix, "dicky")
                ctx, page, mon = self.buka(a.fix, "/", lebar, "gelap", "light", st)
                d = ev(page, JS_DOM)
                if not d["data"] or d["data"].get("cakupan") != "order-sendiri":
                    raise Galat("ringkasan dicky tidak diterima")
                self.cek(b, "fixture_dicky_punya_tugas", len(d["data"]["tugas_aktif"]) >= 1, "tugas=%d riwayat=%d" % (
                    len(d["data"]["tugas_aktif"]), len(d["data"]["riwayat_hari_ini"])))
                self.cek_isolasi_teks(b, "awal", d, acuan)
                for i in range(page.locator(".rinci-tombol").count()):
                    page.locator(".rinci-tombol").nth(i).click()
                self.cek_isolasi_teks(b, "semua_rincian_terbuka", ev(page, JS_DOM), acuan)
                for x in d["data"]["agen"]:
                    page.locator("nav.saring button", has_text=re.compile("^%s$" % re.escape(x["nama"]))).click()
                    self.cek_isolasi_teks(b, "saring_" + x["id"], ev(page, JS_DOM), acuan)
                gal, _ = mon.galat()
                self.cek(b, "0_galat_konsol", not gal, "galat=%d" % len(gal), gal[:3])
                ctx.close()
            except Exception as e:  # noqa: BLE001
                self.cek(b, "jalan", False, "galat %s: %s" % (type(e).__name__, self.aman(str(e))[:300]))

    def status(self):
        a = self.a
        for tema in ("terang", "gelap"):
            nm = "uji-status-%s-1366" % tema
            try:
                st = self.masuk("fix", a.fix, "akbar")
                ctx, page, mon = self.buka(a.fix, "/", 1366, tema, "light", st)
                page.locator("nav.saring button", has_text=re.compile("^Desy$")).click()
                page.wait_for_timeout(200)
                d = self.periksa_umum("status", nm, a.fix, page, mon, 1366, tema, [".peran", ".nm"], layar=nm + ".png")
                w = ev(page, JS_WARNA_STATUS)
                peta = {"jalan": w["v"]["jalan"], "sibuk": w["v"]["jalan"], "menunggu": w["v"]["menunggu"], "bebas": w["v"]["bebas"]}
                salah = [x for x in w["titik"] if x["kelas"] in peta and x["bg"] != peta[x["kelas"]]]
                ada = {x["kelas"] for x in w["titik"]}
                lbl = all(c == w["v"]["menunggu_teks"] for c in w["label_menunggu"])
                self.cek("status", nm + ":warna_titik_per_status", {"jalan", "menunggu", "bebas"} <= ada and not salah and lbl and w["label_menunggu"],
                         "kelas=%s salah=%d label_menunggu=%s var=%s" % (sorted(ada), len(salah), w["label_menunggu"][:2], w["v"]), salah[:3])
                ctx.close()
            except Exception as e:  # noqa: BLE001
                self.cek("status", nm, False, "galat %s: %s" % (type(e).__name__, self.aman(str(e))[:300]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--live", required=True)
    ap.add_argument("--fix", required=True)
    ap.add_argument("--pw-dir", required=True)
    ap.add_argument("--acuan-isolasi", required=True)
    ap.add_argument("--layar")
    ap.add_argument("--keluaran")
    ap.add_argument("--bagian", default="matriks,tema,fouc,fitur,isolasi,status")
    ap.add_argument("--ganti", action="append", help="/aset/app.js=BERKAS: sajikan isi BERKAS untuk path itu (uji mutasi)")
    a = ap.parse_args()
    a.live, a.fix = a.live.rstrip("/"), a.fix.rstrip("/")
    if "matriks" in a.bagian and not a.layar:
        ap.error("--layar wajib untuk bagian matriks")
    mulai = time.strftime("%Y-%m-%d %H:%M:%S %z")
    try:
        from patchright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        print("GALAT patchright: %s" % e)
        return 2
    with sync_playwright() as p:
        br = p.chromium.launch(channel="chromium", headless=True)
        u = Uji(a, br)
        for bag in a.bagian.split(","):
            getattr(u, bag)()
        br.close()
    lulus = sum(x["ok"] for x in u.hasil)
    for x in u.hasil:
        print("%s %-9s %-62s %s" % ("LULUS" if x["ok"] else "GAGAL", x["bagian"], x["nama"][:62], u.aman(str(x["ket"]))[:260]))
        if not x["ok"] and x["rinci"]:
            print("      rinci:", u.aman(json.dumps(x["rinci"], ensure_ascii=False))[:700])
    print("lulus=%d gagal=%d" % (lulus, len(u.hasil) - lulus))
    if a.keluaran:
        with open(a.keluaran, "w", encoding="utf-8") as f:
            f.write(u.aman(json.dumps({"mulai": mulai, "selesai": time.strftime("%Y-%m-%d %H:%M:%S %z"), "live": a.live, "fix": a.fix,
                                       "bagian": a.bagian, "ganti": a.ganti, "lulus": lulus, "gagal": len(u.hasil) - lulus,
                                       "cek": u.hasil}, ensure_ascii=False, indent=1)))
    return 0 if u.hasil and lulus == len(u.hasil) else 1


if __name__ == "__main__":
    sys.exit(main())
