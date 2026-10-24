#!/usr/bin/env python3
"""cek_kantor_statis.py - cek statis tampilan "Kantor Agen" agent-dashboard (KONTRAK-kantor-agen.md D1-D3, D12).

Pakai: python3 tests/ui/cek_kantor_statis.py <dir apps/web>   -> keluar 0 bila gagal=0 (stdlib saja).
Mencetak satu baris per cek + angka kontras. Tidak membaca data apa pun selain berkas web.

D1  berkas, font Public Sans 400/500/600/700 + OFL, tema.js sinkron di <head>, form login/ganti sama persis dengan v3.
D2  CSP: tanpa style=/<style>/skrip inline/on*=, tanpa API yang melewati CSP, warna avatar lewat kelas .t-<indeks 0-9>,
    hex warna hanya di blok :root dan aturan .t-<indeks>.
D3  escape: semua HTML dibangun lewat tag templat h`` (escape bawaan); innerHTML hanya di satu tempat dari objek Html.
D4  (bagian statis) sumber data hanya EventSource('/events') + 4 event; tanpa simulasi/Tagih/"Data contoh".
D12 kontras teks >= 4.5:1 tiap pasangan warna x latar tempat ia muncul, tema terang dan gelap (palet dibaca dari app.css).
"""
import os
import re
import sys

W = sys.argv[1] if len(sys.argv) > 1 else ''
HASIL = []


def cek(nama, ok, ket=''):
    HASIL.append((bool(ok), nama, ket))


def baca(n, mode='r'):
    try:
        with open(os.path.join(W, n), mode, **({} if 'b' in mode else {'encoding': 'utf-8'})) as f:
            return f.read()
    except OSError:
        return None


# ------------------------------------------------------------------ D1 berkas + font
F = {n: baca(n) for n in ('index.html', 'app.js', 'app.css', 'tema.js', 'login.html', 'ganti.html')}
for n, s in F.items():
    cek('D1 %s ada' % n, s is not None)
F = {n: s or '' for n, s in F.items()}
SEMUA = ''.join(F.values())
FONT = {'Regular': 400, 'Medium': 500, 'SemiBold': 600, 'Bold': 700}
fdir = os.path.join(W, 'font')
fonts = sorted(os.listdir(fdir)) if os.path.isdir(fdir) else []
harap_font = sorted(['PublicSans-%s.woff2' % k for k in FONT] + ['PublicSans-OFL.txt'])
cek('D1 isi font/ = 4 woff2 Public Sans + PublicSans-OFL.txt (tanpa Inter/lainnya)', fonts == harap_font, fonts)
for k in FONT:
    b = baca('font/PublicSans-%s.woff2' % k, 'rb') or b''
    cek('D1 PublicSans-%s.woff2 berformat woff2' % k, b[:4] == b'wOF2' and len(b) > 10000, len(b))
ofl = baca('font/PublicSans-OFL.txt') or ''
cek('D1 PublicSans-OFL.txt = SIL OFL 1.1 Public Sans', 'SIL OPEN FONT LICENSE Version 1.1' in ofl and 'Public Sans' in ofl)
css = F['app.css']
ff = re.findall(r'@font-face\s*\{([^}]*)\}', css)
dapat = {}
for blok in ff:
    fam = re.search(r'font-family:\s*["\']?([^;"\']+)', blok)
    wt = re.search(r'font-weight:\s*(\d+)', blok)
    src = re.findall(r'url\(\s*["\']?([^)"\']+)', blok)
    if fam and wt:
        dapat[int(wt.group(1))] = (fam.group(1).strip(), src)
cek('D1 @font-face Public Sans 400/500/600/700 -> berkas bobot yang benar',
    len(ff) == 4 and all(dapat.get(w) == ('Public Sans', ['/aset/font/PublicSans-%s.woff2' % k]) for k, w in FONT.items()), dapat)
cek('D1 body memakai font-family "Public Sans"', re.search(r'\bbody\s*\{[^}]*font:[^;}]*"Public Sans"', css) is not None)
cek('D1 tanpa URL luar (http(s):// atau //host)', not re.search(r'https?://|(?<![:\w])//[a-z0-9-]+\.[a-z]', SEMUA.replace('//aset', '')))
cek('D1 tanpa googleapis/gstatic/preconnect/cdn', not re.search(r'googleapis|gstatic|preconnect|cdn\.', SEMUA, re.I))
cek('D1 tidak merujuk style.css / Inter', not re.search(r'style\.css|\bInter\b', SEMUA))


def kepala(s):
    m = re.search(r'<head>(.*?)</head>', s, re.S | re.I)
    return m.group(1) if m else ''


for n in ('index.html', 'login.html', 'ganti.html'):
    s, hd = F[n], kepala(F[n])
    tag = re.findall(r'<script\b[^>]*>', hd)
    cek('D1 %s: tema.js dimuat sinkron di <head> sebelum app.css' % n,
        tag and tag[0] == '<script src="/aset/tema.js">'
        and hd.find('/aset/tema.js') < hd.find('/aset/app.css') and hd.find('/aset/app.css') >= 0)
    cek('D1 %s: <html lang="id">, meta viewport, judul Kantor Agen' % n,
        '<html lang="id">' in s and 'name="viewport" content="width=device-width, initial-scale=1"' in s and '<title>Kantor Agen</title>' in s)
    links = re.findall(r'<link\b[^>]*>', s)
    cek('D1 %s: satu-satunya <link> = stylesheet /aset/app.css' % n, links == ['<link rel="stylesheet" href="/aset/app.css">'], links)
cek('D1 index.html: app.js defer di <head>, tema.js tanpa defer',
    re.findall(r'<script\b[^>]*>', kepala(F['index.html'])) == ['<script src="/aset/tema.js">', '<script src="/aset/app.js" defer>'])
cek('D1 login/ganti tanpa app.js', 'app.js' not in F['login.html'] + F['ganti.html'])


def atribut(tag):
    return dict((k.lower(), v) for k, v in re.findall(r'\s([a-zA-Z-]+)(?:="([^"]*)")?', tag))


def form(s):
    f = re.findall(r'<form\b[^>]*>', s)
    inp = [atribut(t) for t in re.findall(r'<input\b[^>]*>', s)]
    btn = re.findall(r'<button\b[^>]*type="submit"[^>]*>', s)
    return [atribut(t) for t in f], inp, len(btn)


# atribut persis versi v3 (live 17 Okt, sha login ff84d900..., ganti 0785c214...): field/action/nama input TIDAK berubah (D1)
LOGIN = ([{'method': 'post', 'action': '/login'}],
         [{'id': 'akun', 'name': 'akun', 'type': 'text', 'autocomplete': 'username', 'autocapitalize': 'none', 'spellcheck': 'false',
           'value': '{{.Akun}}', 'required': ''},
          {'id': 'password', 'name': 'password', 'type': 'password', 'autocomplete': 'current-password', 'required': ''}], 1)
GANTI = ([{'method': 'post', 'action': '/ganti-password'}],
         [{'id': 'password_baru', 'name': 'password_baru', 'type': 'password', 'autocomplete': 'new-password', 'minlength': '12', 'required': ''},
          {'id': 'password_ulang', 'name': 'password_ulang', 'type': 'password', 'autocomplete': 'new-password', 'minlength': '12', 'required': ''}], 1)
cek('D1 login.html: form/input sama persis dengan v3', form(F['login.html']) == LOGIN, form(F['login.html']))
cek('D1 ganti.html: form/input sama persis dengan v3', form(F['ganti.html']) == GANTI, form(F['ganti.html']))
for n in ('login.html', 'ganti.html'):
    cek('D1 %s: label for= tiap input + blok pesan {{if .Pesan}}' % n,
        all(('for="%s"' % i['id']) in F[n] for i in form(F[n])[1]) and '{{if .Pesan}}<p class="pesan" role="alert">{{.Pesan}}</p>{{end}}' in F[n])
idx = F['index.html']
cek('D1 index: form POST /logout dengan tombol submit Keluar',
    re.search(r'<form[^>]*method="post"[^>]*action="/logout"[^>]*>\s*<button[^>]*type="submit"[^>]*>Keluar</button>\s*</form>', idx) is not None)
cek('D1 index: tanpa tautan ganti password (D5)', 'ganti-password' not in idx and 'ganti-password' not in F['app.js'])
cek('D1 tema.js membaca localStorage "tema" dan menulis data-tema', "localStorage.getItem('tema')" in F['tema.js'] and 'dataset.tema' in F['tema.js'])
ID_WAJIB = ['banner', 'summary', 'liveDot', 'stamp', 'pause', 'theme', 'me', 'map', 'alert', 'missions', 'missionCount', 'doneCard',
            'detail', 'lower', 'events', 'eventCount', 'announce', 'legend-sibuk']
cek('D1 index: id elemen yang dipakai app.js ada', all(('id="%s"' % i) in idx for i in ID_WAJIB), [i for i in ID_WAJIB if ('id="%s"' % i) not in idx])
cek('D10 index: panel Pak Akbar tidak ada di HTML statis (dibuat JS hanya untuk akbar)', 'id="owner"' not in idx and 'Pak Akbar' not in idx)

# ------------------------------------------------------------------ D2 CSP
for n in ('index.html', 'login.html', 'ganti.html'):
    s = F[n]
    cek('D2 %s: tanpa <style>' % n, '<style' not in s.lower())
    cek('D2 %s: tanpa atribut style=' % n, not re.search(r'\sstyle\s*=', s, re.I))
    cek('D2 %s: tanpa handler on*=' % n, not re.search(r'\son[a-z]+\s*=', s, re.I))
    cek('D2 %s: semua <script> ber-src /aset/ dan kosong' % n,
        all(re.fullmatch(r'<script src="/aset/(tema|app)\.js"( defer)?></script>', t) for t in re.findall(r'<script\b.*?</script>', s, re.S)))
    cek('D2 %s: tanpa javascript: URL' % n, 'javascript:' not in s.lower())

# tokenisasi JS sederhana: komentar, string '..' "..", templat `..${..}..` bersarang, regex literal
js = F['app.js']


def token(src):
    i, n, out, prev = 0, len(src), [], ''
    stack = []  # konteks templat: daftar kedalaman kurung kurawal

    def templat(i, tag):
        start, buf, bagian = i, '', []
        i += 1
        while i < n:
            c = src[i]
            if c == '\\':
                buf += src[i:i + 2]
                i += 2
                continue
            if c == '`':
                bagian.append(buf)
                out.append(('tpl', start, tag, bagian))
                return i + 1
            if c == '$' and src[i + 1:i + 2] == '{':
                bagian.append(buf)
                buf = ''
                i = kode(i + 2, sampai='}')
                continue
            buf += c
            i += 1
        raise ValueError('templat tak tertutup di %d' % start)

    def kode(i, sampai=None):
        nonlocal prev
        depth = 0
        while i < n:
            c = src[i]
            if c in ' \t\r\n':
                i += 1
                continue
            if src.startswith('//', i):
                i = src.find('\n', i)
                i = n if i < 0 else i
                continue
            if src.startswith('/*', i):
                i = src.index('*/', i) + 2
                continue
            if c in '\'"':
                j = i + 1
                while src[j] != c:
                    j += 2 if src[j] == '\\' else 1
                out.append(('str', i, src[i + 1:j]))
                i, prev = j + 1, 'x'
                continue
            if c == '`':
                m = re.search(r'([A-Za-z_$][\w$]*)\s*$', src[max(0, i - 40):i])
                tag = m.group(1) if m and src[i - 1] not in ' \t\n' else ''
                i, prev = templat(i, tag), 'x'
                continue
            if c == '/':
                kata = re.search(r'([A-Za-z_$][\w$]*)\s*$', src[max(0, i - 20):i])
                if prev in '(,=:[!&|?{};+-*%~^<>' or (kata and kata.group(1) in ('return', 'typeof', 'case')):
                    j, kelas = i + 1, False
                    while True:
                        d = src[j]
                        if d == '\\':
                            j += 2
                            continue
                        if d == '[':
                            kelas = True
                        elif d == ']':
                            kelas = False
                        elif d == '/' and not kelas:
                            break
                        j += 1
                    out.append(('re', i, src[i + 1:j]))
                    i, prev = j + 1, 'x'
                    continue
            if sampai and c == '{':
                depth += 1
            elif sampai and c == '}':
                if depth == 0:
                    return i + 1
                depth -= 1
            prev = c if not (c.isalnum() or c in '_$') else 'x'
            i += 1
        return i

    kode(0)
    return out


try:
    T = token(js)
    tok_ok = True
except Exception as e:  # noqa: BLE001
    T, tok_ok = [], False
    cek('D3 app.js bisa ditokenisasi', False, str(e))
if tok_ok:
    cek('D3 app.js bisa ditokenisasi', len(T) > 50, len(T))
    tag_html = re.compile(r'<[A-Za-z/!]')
    tpl = [t for t in T if t[0] == 'tpl']
    tak = [js.count('\n', 0, t[1]) + 1 for t in tpl if tag_html.search(''.join(t[3])) and t[2] != 'h']
    cek('D3 setiap templat berisi tag HTML memakai tag h`` (escape bawaan)', not tak, 'baris %s' % tak)
    tanpa_kutip = [js.count('\n', 0, t[1]) + 1 for t in tpl if t[2] == 'h' and any(re.search(r'=\s*$', b) for b in t[3][:-1])]
    cek('D3 interpolasi di nilai atribut selalu berkutip', not tanpa_kutip, 'baris %s' % tanpa_kutip)
    s_html = [js.count('\n', 0, t[1]) + 1 for t in T if t[0] == 'str' and tag_html.search(t[2])]
    cek('D3 tidak ada string \'..\'/".." berisi tag HTML', not s_html, 'baris %s' % s_html)
    cek('D3 templat h`` dipakai (>= 10)', sum(1 for t in tpl if t[2] == 'h') >= 10)
cek('D3 fungsi esc mengganti & < > " \'',
    all(x in js for x in ("'&': '&amp;'", "'<': '&lt;'", "'>': '&gt;'", "'\"': '&quot;'", '"\'": \'&#39;\'')) and re.search(r"replace\(/\[&<>\"'\]/g", js) is not None)
cek('D3 innerHTML hanya satu tempat, dari objek Html (.s)', js.count('innerHTML') == 1 and re.search(r'\.innerHTML = html\.s;', js) is not None)
cek('D3 objek Html hanya dibuat di h``', js.count('new Html(') == 1)
cek('D3 tanpa insertAdjacentHTML/outerHTML/document.write/eval/new Function/innerHTML +=',
    not re.search(r'insertAdjacentHTML|outerHTML|document\.write|\beval\(|new Function|innerHTML\s*\+=|DOMParser|createContextualFragment', js))
cek('D2 app.js tanpa style= di templat dan tanpa on*= di templat',
    not re.search(r'\sstyle\s*=\s*\\?["\']', js) and not re.search(r'<[a-z][^>`]*\son[a-z]+\s*=', js))
cek('D2 app.js tanpa setAttribute(\'style\')/cssText/javascript:', not re.search(r"setAttribute\(\s*['\"]style|cssText|javascript:", js))

IDX_T = [str(i) for i in range(10)]
cek('D2 app.css: kelas warna avatar .t-0 … .t-9 (10 warna; app.js memilih indeks mod 10)',
    all(re.search(r'\.t-%s\s*\{\s*--tint:\s*#[0-9a-fA-F]{6};\s*\}' % i, css) for i in IDX_T), [i for i in IDX_T if '.t-%s' % i not in css])
cek('D2 app.css: avatar punya warna cadangan netral', re.search(r'\.av\s*\{[^}]*background:\s*var\(--tint,\s*var\(--tint-netral\)\)', css) is not None)
cek('D2 app.js: kelas avatar dari urutan payload (indeks mod 10), tanpa daftar id tetap',
    "' t-' + (warnaId.get(id) % JUMLAH_WARNA)" in js and re.search(r'const WARNA\b', js) is None and 'JUMLAH_WARNA = 10' in js)
luar = re.sub(r':root[^{]*\{[^}]*\}', '', css)
luar = re.sub(r'\.t-\d+\s*\{[^}]*\}', '', luar)
cek('D2 app.css: hex warna hanya di blok :root dan .t-<indeks>', not re.search(r'#[0-9a-fA-F]{3,8}\b', luar), re.findall(r'#[0-9a-fA-F]{3,8}\b', luar)[:5])
cek('D2 app.css: tanpa @import/url luar', '@import' not in css and all(u.startswith('/aset/font/') for u in re.findall(r'url\(\s*["\']?([^)"\']+)', css)))

# ------------------------------------------------------------------ D4 (statis)
cek('D4 EventSource(\'/events\') tepat satu', js.count("new EventSource('/events')") == 1 and js.count('EventSource(') == 1)
for ev in ('ringkasan', 'detak', 'galat', 'sesi', 'open', 'error'):
    cek('D4 tangani event %s' % ev, re.search(r"addEventListener\('%s'" % ev, js) is not None)
cek('D4 tanpa simulasi (seed/tick/Math.random) dan tanpa sumber data lain',
    not re.search(r'\bseed\s*\(|\btick\s*\(|Math\.random|XMLHttpRequest|WebSocket|sendBeacon', js)
    and re.findall(r"fetch\(\s*'([^']*)'", js) == ['/'] and js.count('fetch(') == 1)
cek('D4/D7 tanpa Tagih/nudge/menagih', not re.search(r'Tagih|nudge|menagih', SEMUA, re.I))
cek('D4 tanpa teks "Data contoh"/"disimulasikan"', not re.search(r'Data contoh|disimulasikan', SEMUA))
cek('D4 sesi habis -> /login', "location.assign('/login')" in js)

# ------------------------------------------------------------------ D12 kontras
def tema(sel):
    m = re.search(r':root' + sel + r'\s*\{([^}]*)\}', css)
    return dict(re.findall(r'--([\w-]+):\s*(#[0-9a-fA-F]{6})\b', m.group(1))) if m else {}


def lum(h):
    c = [int(h[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= 0.03928 else ((x + 0.055) / 1.055) ** 2.4 for x in c]
    return 0.2126 * c[0] + 0.7152 * c[1] + 0.0722 * c[2]


def kontras(a, b):
    x, y = sorted([lum(a), lum(b)], reverse=True)
    return (x + 0.05) / (y + 0.05)


TEMA = {'terang': {**tema(''), **tema(r'\[data-tema="terang"\]')}, 'gelap': {**tema(''), **tema(r'\[data-tema="gelap"\]')}}
# warna teks -> latar tempat ia benar-benar muncul (dibaca dari app.css: header di --ground, kartu Kantor/Misi di --floor,
# ruang di --room, chip/baris misi/detail/panel di --surface, baris selesai + strip fakta di --room, callout/banner di --wait-bg)
PASANG = [('ink', ['ground', 'floor', 'room', 'surface', 'wait-bg', 'work-bg']),
          ('muted', ['ground', 'floor', 'room', 'surface']),
          ('work', ['surface', 'work-bg', 'room']),
          ('wait', ['surface', 'wait-bg', 'room']),
          ('wait-ink', ['wait-bg']),
          ('idle', ['idle-bg']),
          ('on-primary', ['primary'])]
for t, P in TEMA.items():
    kurang = sorted({x for fg, bgs in PASANG for x in [fg] + bgs if x not in P})
    cek('D12 %s: semua variabel palet ada' % t, P and not kurang, kurang)
    for fg, bgs in PASANG:
        for bg in bgs:
            if fg in P and bg in P:
                r = kontras(P[fg], P[bg])
                cek('D12 %s %s vs %s %.2f:1 >= 4.5' % (t, fg, bg, r), r >= 4.5)
tint = dict(re.findall(r'\.t-(\d+)\s*\{\s*--tint:\s*(#[0-9a-fA-F]{6})', css))
tint['netral'] = TEMA['terang'].get('tint-netral', '#000000')
for i, warna in sorted(tint.items()):
    for t in TEMA:
        av = TEMA[t].get('av-ink', '#ffffff')
        r = kontras(av, warna)
        cek('D12 %s avatar av-ink vs .t-%s %.2f:1 >= 4.5' % (t, i, r), r >= 4.5)

# ------------------------------------------------------------------ ringkasan
lulus = sum(1 for ok, _, _ in HASIL if ok)
for ok, nama, ket in HASIL:
    print('%s %s%s' % ('LULUS' if ok else 'GAGAL', nama, '' if ok or ket in ('', None) else '  [%s]' % str(ket)[:200]))
print('lulus=%d gagal=%d' % (lulus, len(HASIL) - lulus))
sys.exit(0 if HASIL and lulus == len(HASIL) else 1)
