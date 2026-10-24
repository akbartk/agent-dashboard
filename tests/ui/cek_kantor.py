#!/usr/bin/env python3
"""cek_kantor.py - uji peramban tampilan "Kantor Agen" agent-dashboard (KONTRAK-kantor-agen.md bagian D; Patchright chromium).

Dijalankan dari container ajeng (patchright-py) terhadap container uji ka-uji-alfa (127.0.0.1:24131 di host) lewat alamat
NON-loopback: harness membuka tunnel ssh yang di-bind ke IP container ajeng (bawaan 10.249.1.2:24131).
Fixture: dibangun dari tests/ui/bangun_fixture_kantor.py (KARANGAN UJI), digeser sehingga dibuat_pada = saat uji, lalu diunggah
atomik ke --host-dir (folder yang di-mount :ro ke container uji). Penyegar latar memperbarui dibuat_pada tiap 8 dtk agar tidak
basi; uji SSE/Jeda/galat/basi mengubah fixture lewat spesifikasi pembangun (dicky/jati tetap turunan C7 dari akbar).
Akun uji: --pw-dir berisi berkas <akun> (password saat ini, 600). Bila server meminta ganti password, password baru acak ditulis
dulu ke <akun>.baru lalu menggantikan <akun> sesudah berhasil. Password tidak pernah dicetak.

  patchright-py cek_kantor.py --pembangun tests/ui/bangun_fixture_kantor.py --pw-dir DIR --layar DIR --keluaran HASIL.json \
      [--base http://10.249.1.2:24131] [--host-dir /data/agent-dashboard/tmp/test/kantor-agen/alfa-uji/ringkasan] \
      [--bagian masuk,akbar,akbar390,dicky,jati,basi] [--ganti /aset/app.js=BERKAS]

Harapan dihitung dari JSON fixture yang sedang berlaku (aturan D1-D13), bukan konstanta. Durasi "N m" dicek polanya saja.
Keluar 0 = semua lulus, 1 = ada gagal, 2 = galat alat. Catatan: uji lintas tengah malam WIB tidak didukung (geser waktu).

Mode DATA ASLI (sesi integrasi 24 Okt): --asli DIR_HOST (folder keluaran generator yang di-mount :ro ke container uji; tanpa
fixture, tanpa unggah). Harapan dihitung dari ringkasan yang DITERIMA halaman (window.__rk, diambil dalam evaluate yang sama
dengan potret DOM; render app.js sinkron). Isolasi dicky/jati dibanding akbar.json sezaman (dibuat_pada sama) yang dibaca dari
DIR_HOST lewat ssh. Bagian: asli_akbar (1366 terang + SSE tanpa reload + gelap), asli_akbar390, asli_dicky, asli_jati,
gladi_lama_ui (UI lama v3 + ringkasan generator baru), gladi_skema_lama (UI baru + ringkasan skema lama). SSE: alat mencetak
"SIAP-SSE" (dan menulis --sinyal bila ada) lalu menunggu <= --batas-sse dtk sampai DOM berubah karena data. Judul misi/tugas di
keluaran disamarkan ("Judul misi <nomor>"). Port tunnel di host = port --base.
  patchright-py cek_kantor.py --asli /data/agent-dashboard/tmp/test/kantor-agen/ringkasan --pw-dir DIR --layar DIR \
      --keluaran HASIL.json --bagian masuk,asli_akbar,asli_akbar390,asli_dicky,asli_jati [--sinyal BERKAS] [--batas-sse 60]
Klik pada elemen yang diharapkan ada = cek per butir (gagal dicatat, bagian berlanjut), bukan pengecualian yang menghentikan bagian.
"""
import argparse
import datetime as dt
import importlib.util
import io
import json
import os
import re
import secrets
import shlex
import socket
import subprocess
import sys
import tarfile
import threading
import time

WIB = dt.timezone(dt.timedelta(hours=7))
SSH = ['ssh', '-F', '/opt/data/.ssh/config', '-o', 'BatchMode=yes', '-o', 'ConnectTimeout=10']
HOST = 'bskdev-host'
DASAR_DIBUAT = '2026-10-24T11:00:00+07:00'   # dibuat_pada fixture asli (bangun_fixture_kantor.py)

INIT = r"""(() => { try {
  window.__rk = null; window.__nrk = 0; window.__csp = []; window.__dialog = [];
  ['alert', 'confirm', 'prompt'].forEach(k => { window[k] = function (m) { window.__dialog.push(k + ':' + String(m)); return null; }; });
  const E = window.EventSource;
  if (E) {
    class ES extends E {
      constructor(u, o) { super(u, o);
        this.addEventListener('ringkasan', ev => { try { window.__rk = JSON.parse(ev.data).data; window.__nrk++; } catch (e) {} }); }
    }
    window.EventSource = ES;
  }
  document.addEventListener('securitypolicyviolation', ev => { window.__csp.push({dir: ev.violatedDirective, blocked: ev.blockedURI}); }, true);
} catch (e) {} })();"""

SNAP = r"""() => {
  const q = s => document.querySelector(s), qa = (s, r) => [...(r || document).querySelectorAll(s)];
  const n = x => x == null ? null : x.replace(/\s+/g, ' ').trim();
  const tx = el => el ? n(el.textContent) : null;
  const tanpaAv = el => el ? n([...el.childNodes].filter(c => !(c.classList && c.classList.contains('av'))).map(c => c.textContent).join('')) : null;
  const baris = r => ({id: r.dataset.task, cls: r.className, pressed: r.getAttribute('aria-pressed'),
    head: tx(r.querySelector('.row > span:first-child')), st: tx(r.querySelector('.st')), stCls: (r.querySelector('.st') || {}).className,
    judul: tx(r.querySelector(':scope > strong')), who: tx(r.querySelector('.who > span:last-child')),
    avCls: (r.querySelector('.who .av') || {}).className, segDone: qa('.segs i.done', r).length, segCur: qa('.segs i.cur', r).length,
    segAll: qa('.segs i', r).length, subs: tx(r.querySelector('.m-subs'))});
  const det = q('#detail');
  const dl = det ? qa('.facts > div', det).map(d => [tx(d.querySelector('dt')), tanpaAv(d.querySelector('dd'))]) : [];
  const own = q('#owner');
  return {
    url: location.pathname, tema: document.documentElement.dataset.tema, summary: tx(q('#summary')), stamp: tx(q('#stamp')),
    pause: tx(q('#pause')), pausePressed: q('#pause') ? q('#pause').getAttribute('aria-pressed') : null,
    pauseLabel: q('#pause') ? q('#pause').getAttribute('aria-label') : null, panel: det ? det.getAttribute('data-panel') : null,
    detailTeks: det ? n(det.innerText) : null, dotPaused: q('#liveDot') ? q('#liveDot').classList.contains('paused') : null,
    meAv: tx(q('#me .av')), meNama: tanpaAv(q('#me')), meAvCls: (q('#me .av') || {}).className,
    banner: q('#banner') && !q('#banner').hidden ? tx(q('#banner')) : null,
    legendSibuk: q('#legend-sibuk') ? !q('#legend-sibuk').hidden : null,
    rooms: qa('.map-room').map(r => ({nama: r.querySelector('h3') ? n(r.querySelector('h3').firstChild.textContent) : null, sibuk: tx(r.querySelector('h3 span')),
      wide: r.classList.contains('wide'),
      chips: qa('.chip', r).map(c => ({id: c.dataset.agent, cls: c.className, nama: tx(c.querySelector('strong')),
        teks: tx(c.querySelector('small')), av: (c.querySelector('.av') || {}).className, avTeks: tx(c.querySelector('.av')),
        label: c.getAttribute('aria-label'), pressed: c.getAttribute('aria-pressed')}))})),
    alertJudul: tx(q('#alert .alert > strong')), alertTeks: tx(q('#alert .alert > span')),
    alertLinks: qa('#alert [data-task]').map(b => [b.dataset.task, tx(b)]), alertKosong: q('#alert') ? q('#alert').children.length === 0 : null,
    missionCount: tx(q('#missionCount')), missions: qa('#missions .m-row').map(baris), missionsEmpty: tx(q('#missions .empty')),
    doneHidden: q('#doneCard') ? q('#doneCard').hidden : null, doneJudul: tx(q('#doneCard h2')), doneN: tx(q('#doneCard .sec-head > span')),
    done: qa('#doneCard .m-row').map(baris),
    detail: det ? {h2: tx(q('#h-detail')), meta: tx(det.querySelector('.d-meta')), pill: tx(det.querySelector('.pill')),
      pillCls: (det.querySelector('.pill') || {}).className, facts: dl,
      callout: tx(det.querySelector('.d-callout p')), calloutLinks: qa('.d-callout [data-task]', det).map(b => [b.dataset.task, tx(b)]),
      stepsHead: tx(det.querySelector('.d-box[aria-label="Langkah"] h3 span')),
      steps: qa('.steps li', det).map(li => [tx(li.children[0]), tx(li.children[2]), tx(li.children[3]), li.className]),
      subsHead: tx(det.querySelector('.d-box[aria-label="Sub-agen"] h3 span')),
      subs: qa('.sub-row', det).map(r => [tx(r.querySelector('.chair')), tx(r.children[1]), tx(r.querySelector('small')), r.className]),
      subEmpty: tx(det.querySelector('.sub-empty')),
      evN: tx(q('#lbl-log span')), ev: qa('.d-log .ev', det).map(e => [tx(e.querySelector('time')), tx(e.querySelector('span'))])} : null,
    owner: own ? {h2: tx(q('#h-owner')), small: tx(own.querySelector('.owner-head small')), av: (own.querySelector('.owner-head .av') || {}).className,
      insLabel: tx(q('#lbl-ins')), ins: qa('.ins', own).map(i => [tx(i.querySelector('time')), tx(i.querySelector('span')), tx(i.querySelector('small')),
        (i.querySelector('small') || {}).className]),
      givers: qa('.giver', own).map(g => [tx(g.querySelector('strong')), tx(g.querySelector('span:not(.av)')), (g.querySelector('.av') || {}).className])} : null,
    ownerTeks: /Instruksi hari ini|Pemberi order|Pemilik tim/.test(document.body.innerText),
    eventCount: tx(q('#eventCount')), events: qa('#events .ev').map(e => [tx(e.querySelector('time')), tx(e.querySelector('span'))]),
    more: tx(q('#events .more')), active: document.activeElement ? (document.activeElement.dataset.key || document.activeElement.id || document.activeElement.tagName) : null,
    imgs: qa('img').length, scripts: qa('script').map(s => [s.getAttribute('src'), s.textContent.length]),
    handler: qa('[onerror],[onload],[onclick],[onmouseover],[onfocus]').length, styleAttr: qa('[style]').map(e => e.tagName + '.' + e.className).filter(x => !/done-list/.test(x)),
    dialog: window.__dialog || [], csp: window.__csp || [], nrk: window.__nrk, rkPenonton: window.__rk ? window.__rk.penonton : null,
    sw: document.documentElement.scrollWidth, cw: document.documentElement.clientWidth, bsw: document.body.scrollWidth,
    teks: document.body.innerText, html: document.body.innerHTML
  };
}"""


class Galat(Exception):
    pass


# ------------------------------------------------------------------ format + harapan (aturan KONTRAK D)
def jam(iso):
    m = re.search(r'T(\d\d):(\d\d)', iso or '')
    return '%s.%s' % (m.group(1), m.group(2)) if m else None


def label(m):
    st, al = m['status'], m['alasan']
    if st == 'jalan':
        return 'Langkah %d dari —' % (len(m['langkah']) + 1)
    if st == 'menunggu':
        return {'misi-lain': 'Tertahan', 'review': 'Menunggu review', 'gantung': 'Gantung'}[al]
    return ('Selesai %s' if st == 'selesai' else 'Berakhir %s') % jam(m['selesai'])


def jenis(m):
    return {'jalan': 'work', 'menunggu': 'wait'}.get(m['status'], 'done')


def aktif(m):
    return m['status'] in ('jalan', 'menunggu')


def nama_id(D, i):
    for o in D['orang'] + D['agen']:
        if o['id'] == i:
            return o['nama']
    return i


def misi_id(D, i):
    return next((m for m in D['misi'] if m['id'] == i), None)


def sub_aktif(m):
    return sum(1 for s in (m['subagen'] or []) if s['selesai'] is None)


def harap_summary(D):
    r = D['ringkasan']
    a = r['agen']
    s = 'Agen %d bekerja %d menunggu %d bebas' % (a['bekerja'], a['menunggu'], a['bebas'])
    if D['cakupan'] == 'order-sendiri':
        s += ' %d sibuk' % a['sibuk']
    s += ' Misi %d aktif %d selesai hari ini' % (r['misi']['aktif'], r['misi']['selesai_hari_ini'])
    return s + ' Sub-agen %s aktif' % ('—' if r['subagen_aktif'] is None else r['subagen_aktif'])


RUANG = [('koordinasi', 'Ruang koordinasi'), ('riset', 'Riset dan peraturan'), ('qa', 'QA/QC'), ('teknik', 'Ruang teknik'), ('lain', 'Ruang lain')]
KELAS = {'bekerja': 'work', 'menunggu': 'wait', 'bebas': 'idle', 'sibuk': 'busy'}


def kelas_warna(D, ident):
    """Kelas avatar yang diharapkan (KONTRAK §4): urutan [koordinator, id agen lain sesuai D.agen, id D.orang], t-<indeks mod 10>."""
    urut = []
    for i in [D.get('koordinator')] + [a['id'] for a in D['agen']] + [o['id'] for o in D['orang']]:
        if i and i not in urut:
            urut.append(i)
    return 't-%d' % (urut.index(ident) % 10) if ident in urut else None


def harap_chip(D, a):
    """(pola regex teks chip, kelas, label aria awal, id misi terpilih saat diklik)."""
    M = [misi_id(D, i) for i in a['misi_aktif']]
    m0 = M[0] if M else None
    nsub = sum(sub_aktif(m) for m in M)
    k = a['keadaan']
    if D.get('koordinator') and a['id'] == D['koordinator']:
        t = [t for t in D['tugas_aktif'] if t['pengerja_id'] == a['id']]
        teks = re.escape('melayani %s' % t[0]['pemberi']) if t else re.escape('memantau %d misi' % D['ringkasan']['misi']['aktif'])
    elif k == 'bekerja':
        teks = (re.escape(m0['id'] + ' · ') + r'\d+ m') if m0 else 'bekerja'
    elif k == 'menunggu':
        if m0 and m0['alasan'] == 'misi-lain' and m0['menunggu_misi']:
            teks = re.escape('tunggu ' + m0['menunggu_misi'][0])
        elif m0 and m0['alasan'] == 'review':
            teks = 'menunggu review'
        else:
            teks = 'menunggu'
    else:
        teks = k
    if nsub:
        teks += re.escape(' · %d sub-agen' % nsub)
    milik = [m for m in D['misi'] if m['pelaksana_id'] == a['id']]
    # K-2 (koreksi header 24 Okt): misi aktif pertama; else misi non-aktif dengan selesai terbesar (seri: nomor terbesar);
    # else misi pelaksana pertama di berkas; tanpa misi pelaksana -> None (panel agen)
    sel = sorted((m for m in milik if not aktif(m)), key=lambda m: (m['selesai'] or '', m['nomor']))
    pilih = m0['id'] if m0 else (sel[-1]['id'] if sel else (milik[0]['id'] if milik else None))
    aria = '%s, %s, %s' % (a['nama'], a['peran'], k) + (', %s' % m0['id'] if m0 else '') + (', %d sub-agen aktif' % nsub if nsub else '')
    return '^%s$' % teks, KELAS[k], aria, pilih


PESAN_AGEN = {'bebas': 'Belum ada misi hari ini.', 'sibuk': 'Sedang mengerjakan order lain.',
              'bekerja': 'Sedang bekerja di luar misi tercatat.', 'menunggu': 'Sedang menunggu di luar misi tercatat.'}


def cek_panel_agen(s, a):
    """K-3/K-4: panel agen = data-panel agen:<id>, h2 nama, pesan per keadaan; tanpa baris misi tertekan."""
    d = s['detail'] or {}
    tekan_misi = [x['id'] for x in s['missions'] + s['done'] if x['pressed'] == 'true']
    ok = (s.get('panel') == 'agen:' + a['id'] and d.get('h2') == a['nama'] and PESAN_AGEN[a['keadaan']] in (s.get('detailTeks') or '')
          and (a.get('terakhir_aktif') is None or 'Terakhir aktif' in (s.get('detailTeks') or '')) and not tekan_misi)
    return ok, (s.get('panel'), d.get('h2'), tekan_misi)


# KR-2 (koreksi 1 header): baris kecil panel agen = nama ruang saja bila peran (trim, huruf kecil) = nama ruang; selain itu "<peran> · <ruang>"
META_TETAP = {'via': 'Riset dan peraturan', 'uci': 'QA/QC', 'desy': 'CTO · Ruang teknik'}  # teks brief koreksi 1 (S2)


def harap_meta(a):
    ruang = dict(RUANG).get(a.get('ruang'), 'Ruang lain')
    p = a.get('peran') or ''
    return ruang if not p or p.strip().lower() == ruang.strip().lower() else '%s · %s' % (p, ruang)


def cek_meta_agen(cek, bag, nm, s, a):
    """KR-2: baris kecil panel agen sesuai harap_meta (dihitung dari JSON) + teks tetap brief untuk via/uci/desy; tanpa teks ganda."""
    meta = (s['detail'] or {}).get('meta')
    h = harap_meta(a)
    cek(bag, '%s: panel agen %s baris kecil = "%s" (KR-2)' % (nm, a['id'], h), meta == h, meta)
    if a['id'] in META_TETAP:
        p = (a.get('peran') or '').strip()
        cek(bag, '%s: panel agen %s baris kecil = teks brief "%s", peran tidak ganda (KR-2)' % (nm, a['id'], META_TETAP[a['id']]),
            meta == META_TETAP[a['id']] and (not p or (meta or '').count(p) == 1), meta)


# KR-1 (koreksi 1 header): nama aksesibel #pause dibaca dari pohon aksesibilitas peramban (CDP), bukan dihitung dari DOM
FRASA_JEDA = ', jeda pembaruan tampilan'


def nama_ax(page, cdp, sel):
    """(nama AX, peran AX, properti pressed AX, teks #stamp DOM) dengan stamp stabil di sekitar pembacaan AX (stamp bisa berganti tiap SSE)."""
    for _ in range(5):
        st1 = ev(page, "() => (document.getElementById('stamp') || {}).textContent || null")
        root = cdp.send('DOM.getDocument', {'depth': 0})['root']['nodeId']
        nid = cdp.send('DOM.querySelector', {'nodeId': root, 'selector': sel})['nodeId']
        if not nid:
            return None, None, None, st1
        bid = cdp.send('DOM.describeNode', {'nodeId': nid})['node']['backendNodeId']
        nodes = cdp.send('Accessibility.getPartialAXTree', {'backendNodeId': bid, 'fetchRelatives': False})['nodes']
        n = next((x for x in nodes if x.get('backendDOMNodeId') == bid), {})
        st2 = ev(page, "() => (document.getElementById('stamp') || {}).textContent || null")
        if st1 == st2:
            props = {p['name']: (p.get('value') or {}).get('value') for p in n.get('properties', [])}
            return (n.get('name') or {}).get('value'), (n.get('role') or {}).get('value'), props.get('pressed'), st1
    return None, None, None, None


def cek_jeda_ax(cek, bag, nm, hasil):
    """hasil = [(langkah, nama, peran, pressedAX, stamp, pressedDOM, aria-label), ...] untuk awal / ditekan / dilepas."""
    for lk, nama, peran, pax, st, pdom, lab in hasil:
        cek(bag, '%s: #pause %s tanpa atribut aria-label (KR-1)' % (nm, lk), lab is None, lab)
        cek(bag, '%s: #pause %s nama aksesibel (pohon AX, peran button) memuat teks stamp + "%s" (KR-1, WCAG 2.5.3)' % (nm, lk, FRASA_JEDA),
            bool(nama) and bool(st) and st in nama and FRASA_JEDA in nama and peran == 'button', (nama, peran, st))
    tekan = [(h[0], h[5], h[3]) for h in hasil]
    cek(bag, '%s: aria-pressed berganti false -> true -> false (DOM dan pohon AX) (KR-1)' % nm,
        [(t[1], str(t[2]).lower()) for t in tekan] == [('false', 'false'), ('true', 'true'), ('false', 'false')], tekan)
    sisa = [(h[1] or '').replace(h[4] or '\0', '', 1) for h in hasil]
    cek(bag, '%s: nama aksesibel #pause sama sebelum/sesudah ditekan di luar teks stamp (label tetap, pola toggle APG) (KR-1)' % nm,
        len(set(sisa)) == 1 and sisa[0].strip() == FRASA_JEDA.strip(), sisa)


def harap_baris(D, m):
    cur = ('menunggu ' + m['menunggu_misi'][0]) if m['alasan'] == 'misi-lain' and m['menunggu_misi'] else (m['langkah_sekarang'] or '—')
    sub = None
    if m['subagen']:
        sub = '%d sub-agen aktif · %d dari %s spawn' % (sub_aktif(m), len(m['subagen']), '—' if m['spawn_kuota'] is None else m['spawn_kuota'])
    return {'id': m['id'], 'head': '%s · %s · %s' % (m['id'], m['pemberi'] or '—', jam(m['mulai']) or '—'), 'st': label(m),
            'stKind': jenis(m), 'judul': m['judul'] or '(tanpa judul)', 'who': '%s · %s' % (m['pelaksana'], cur),
            'av': 't-' + m['pelaksana_id'], 'segDone': len(m['langkah']), 'segCur': 1 if aktif(m) else 0, 'subs': sub}


def pilihan_awal(D):
    M = D['misi']
    for m in M:
        if m['status'] == 'menunggu' and m['alasan'] == 'misi-lain':
            return m['id']
    akt = [m for m in M if aktif(m)]
    return (akt or M or [{'id': None}])[0]['id']


def peran(D, i):
    return next((a['peran'] for a in D['agen'] if a['id'] == i), '')


def harap_detail(D, m):
    rw = [r for r in D['riwayat_hari_ini'] if r.get('misi') == m['id']][::-1]
    sa = '—' if m['subagen'] is None else '%d aktif · %d dari %s spawn' % (sub_aktif(m), len(m['subagen']), '—' if m['spawn_kuota'] is None else m['spawn_kuota'])
    facts = [['Pelaksana', '%s %s' % (m['pelaksana'], peran(D, m['pelaksana_id']))],
             ['Rantai order', ' → '.join(nama_id(D, x) for x in m['rantai'])],
             ['Berjalan' if aktif(m) else 'Total waktu', r'^\d+ m$'], ['Sub-agen', sa]]
    steps = []
    for x in m['langkah']:
        steps.append([jam(x['waktu']), x['label'], r'^\d+ m$', 'done'])
    if aktif(m):
        if m['status'] == 'jalan':
            steps.append(['—', m['langkah_sekarang'] or '—', r'^berjalan \d+ m$', 'cur'])
        else:
            note = {'misi-lain': ('menunggu ' + m['menunggu_misi'][0]) if m['menunggu_misi'] else 'menunggu',
                    'review': 'menunggu review', 'gantung': 'gantung'}[m['alasan']]
            steps.append(['—', m['langkah_sekarang'] or '—', '^%s$' % re.escape(note), 'cur wait'])
    subs = None if m['subagen'] is None else [[str(s['ke']), 'Sub-agen ke-%d' % s['ke'],
                                                (r'^bekerja · \d+ m$' if s['selesai'] is None else '^selesai %s$' % re.escape(jam(s['selesai']))),
                                                'sub-row ' + ('work' if s['selesai'] is None else 'done')] for s in m['subagen']]
    callout, links = None, []
    cs = anak_misi(D, m)
    if m['status'] == 'menunggu' and m['alasan'] == 'misi-lain' and cs:
        # D9 revisi CTO (6a): callout tertahan menyebut SEMUA anak menunggu_misi, kalimat per anak digabung "; ", Buka per anak
        callout = r'^Tertahan: menunggu %s\.$' % '; '.join(r'%s menyelesaikan %s \(%s\), sudah \d+ m' % (
            re.escape(c['pelaksana']), c['id'], re.escape(c['judul'] or '(tanpa judul)')) for c in cs)
        links = [[c['id'], 'Buka ' + c['id']] for c in cs]
    else:
        w = next((x for x in D['misi'] if aktif(x) and m['id'] in x['menunggu_misi']), None)
        if w:
            callout = '^%s$' % re.escape('%s menunggu misi ini selesai untuk melanjutkan %s.' % (w['pelaksana'], w['id']))
            links = [[w['id'], 'Buka ' + w['id']]]
    return {'h2': m['judul'] or '(tanpa judul)', 'meta': '%s · order dari %s pukul %s' % (m['id'], m['pemberi'] or '—', jam(m['mulai']) or '—'),
            'pill': label(m), 'pillKind': jenis(m), 'facts': facts, 'steps': steps,
            'stepsHead': '%d dari —' % (len(m['langkah']) + (1 if aktif(m) else 0)), 'subs': subs,
            'ev': [[jam(r['waktu']), r['teks']] for r in rw], 'evN': str(len(rw)), 'callout': callout, 'calloutLinks': links}


def harap_alert(D):
    L = [m for m in D['misi'] if m['status'] == 'menunggu' and m['alasan'] == 'misi-lain']
    if not L:
        return None
    m = L[0]
    j = '%s tertahan di %s' % (m['pelaksana'], m['id']) + (' (+%d lainnya)' % (len(L) - 1) if len(L) > 1 else '')
    cs = anak_misi(D, m)
    if not cs:
        return j, None, [[m['id'], 'Buka ' + m['id']]]
    # D7 revisi CTO (6a): SEMUA anak menunggu_misi, kalimat per anak digabung "; ", tautan Buka per anak lalu Buka <T>
    teks = 'Menunggu %s.' % '; '.join('%s menyelesaikan %s, sejak %s. %s di langkah %d dari —' % (
        c['pelaksana'], c['id'], jam(c['mulai']), c['pelaksana'], len(c['langkah']) + 1) for c in cs)
    return j, teks, [[c['id'], 'Buka ' + c['id']] for c in cs] + [[m['id'], 'Buka ' + m['id']]]


def anak_misi(D, m):
    """misi anak di menunggu_misi yang ada di berkas, urut menunggu_misi (D7/D9 revisi CTO 6a)."""
    return [c for c in (misi_id(D, x) for x in m['menunggu_misi']) if c]


def harap_owner(D):
    hari = D['dibuat_pada'][:10]
    ins = sorted([m for m in D['misi'] if m['pemberi_id'] == 'akbar' and (m['mulai'] or '')[:10] == hari], key=lambda m: m['mulai'], reverse=True)
    giv = []
    for v, nm in (('dicky', 'Mas Dicky'), ('jati', 'Mas Jati')):
        ids = sorted([m['id'] for m in D['misi'] if m['pemberi_id'] == v and aktif(m)], key=lambda x: int(x[2:]))
        giv.append([nm, ('%d order aktif · %s' % (len(ids), ', '.join(ids))) if ids else 'tanpa order aktif', 'av sm ' + kelas_warna(D, v)])
    return {'insLabel': 'Instruksi hari ini · %d' % len(ins), 'ins': [[jam(m['mulai']), m['judul'] or '(tanpa judul)', label(m)] for m in ins],
            'insKind': [jenis(m) for m in ins], 'givers': giv}


def harap_events(D, semua=False):
    rw = D['riwayat_hari_ini'][::-1]
    return [[jam(r['waktu']), r['teks']] for r in rw[:60 if semua else 8]], len(rw)


def inisial(nama):
    return ''.join(w[0] for w in nama.split()[:2]).upper()


# ------------------------------------------------------------------ fixture di host
class Fixture:
    def __init__(self, pembangun, host_dir):
        self.pembangun, self.host_dir = pembangun, host_dir
        self.lock = threading.Lock()
        self.henti = threading.Event()
        self.jeda = False
        sekarang = dt.datetime.now(WIB).replace(microsecond=0)
        self.ke = sekarang.isoformat()
        self.delta = sekarang - dt.datetime.fromisoformat(DASAR_DIBUAT)
        self.muat_ulang()
        self.unggah()
        self.th = threading.Thread(target=self._segar, daemon=True)
        self.th.start()

    def muat_ulang(self):
        sp = importlib.util.spec_from_file_location('bangun_fixture_kantor', self.pembangun)
        self.mod = importlib.util.module_from_spec(sp)
        sp.loader.exec_module(self.mod)
        self.bangun()

    def bangun(self):
        self.data = self.mod.semua(self.ke)
        self._cap()

    def _cap(self):
        now = dt.datetime.now(WIB).replace(microsecond=0).isoformat()
        for d in self.data.values():
            d['dibuat_pada'] = now

    def basis(self):
        """jam spesifikasi pembangun yang setara dengan 'sekarang' (sebelum digeser)."""
        return (dt.datetime.now(WIB) - self.delta).strftime('%H:%M:%S')

    def _kirim(self, isi):
        buf = io.BytesIO()
        with tarfile.open(fileobj=buf, mode='w') as t:
            for nama, b in isi.items():
                ti = tarfile.TarInfo(nama)
                ti.size, ti.mode, ti.mtime = len(b), 0o644, int(time.time())
                t.addfile(ti, io.BytesIO(b))
        mv = ' && '.join('mv -f .baru/%s .' % n for n in isi)
        cmd = 'cd %s && rm -rf .baru && mkdir .baru && tar xf - -C .baru && chmod 644 .baru/* && %s && rmdir .baru' % (self.host_dir, mv)
        r = subprocess.run(SSH + [HOST, cmd], input=buf.getvalue(), capture_output=True, timeout=30)
        if r.returncode != 0:
            raise Galat('unggah fixture rc=%d %s' % (r.returncode, r.stderr[:200]))

    def unggah(self):
        with self.lock:
            self._cap()
            self._kirim({p + '.json': (json.dumps(d, ensure_ascii=False, separators=(',', ':')) + '\n').encode() for p, d in self.data.items()})

    def ubah(self, fn):
        with self.lock:
            fn(self.mod)
            self.bangun()
        self.unggah()

    def kembalikan(self):
        with self.lock:
            self.muat_ulang()
        self.unggah()

    def rusak(self, akun):
        with self.lock:
            self._kirim({akun + '.json': b'{"rusak":\n'})

    def _segar(self):
        while not self.henti.wait(8):
            if not self.jeda:
                try:
                    self.unggah()
                except Exception as e:  # noqa: BLE001
                    print('peringatan penyegar:', type(e).__name__, str(e)[:120])

    def tutup(self):
        self.henti.set()


# ------------------------------------------------------------------ alat peramban (pola cek_v3.py)
class Pantau:
    def __init__(self, ctx, page, rahasia):
        self.log, self.req, self.res, self.rahasia = [], [], [], rahasia
        page.on('request', lambda r: self.req.append(r.url))
        page.on('response', lambda r: self.res.append((r.url, r.status, r.headers.get('content-type', ''))))
        self.dialog = []
        page.on('dialog', lambda d: (self.dialog.append(d.message), d.dismiss()))
        c = ctx.new_cdp_session(page)
        self.cdp = c

        def tambah(jn, teks, url=None):
            for r in self.rahasia:
                teks = teks.replace(r, '***')
            self.log.append({'jenis': jn, 'teks': teks[:240], 'url': url})
        c.on('Runtime.consoleAPICalled', lambda e: tambah('console.' + e['type'], str([x.get('value', x.get('description')) for x in e['args']]))
             if e['type'] in ('error', 'assert', 'warning') else None)
        c.on('Runtime.exceptionThrown', lambda e: tambah('exception', str(e['exceptionDetails'].get('exception', {}).get('description', e['exceptionDetails'].get('text')))))
        c.on('Log.entryAdded', lambda e: tambah('log.' + e['entry']['source'], e['entry']['text'], e['entry'].get('url')) if e['entry']['level'] in ('error', 'warning') else None)
        c.send('Runtime.enable')
        c.send('Log.enable')

    def galat(self):
        fav = [x for x in self.log if (x['url'] or '').split('?')[0].endswith('/favicon.ico')]
        return [x for x in self.log if x not in fav], len(fav)


def pasang_init(cdp, skrip):
    """Init script lewat CDP (dunia utama). add_init_script Patchright memicu blokir Local Network Access (cek_v3.py)."""
    cdp.send('Page.enable')
    for s in skrip:
        cdp.send('Page.addScriptToEvaluateOnNewDocument', {'source': s})


def ev(page, js, arg=None):
    return page.evaluate(js, arg, isolated_context=False) if arg is not None else page.evaluate(js, isolated_context=False)


def tunggu(page, js, batas=15.0, arg=None):
    t0 = time.time()
    while time.time() - t0 < batas:
        try:
            if ev(page, js, arg) if arg is not None else ev(page, js):
                return True
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(250)
    return False


def snap_rk(page):
    """potret DOM + ringkasan yang diterima halaman dalam SATU evaluate (render app.js sinkron di handler SSE)."""
    r = ev(page, '() => { const f = %s; return {s: f(), rk: window.__rk, nrk: window.__nrk}; }' % SNAP)
    return r['s'], r['rk']


SAMAR_DURASI = re.compile(r'\b\d+ m\b')


def sidik(s):
    """sidik DOM berbasis data (durasi relatif 'N m' dibuang): berubah hanya bila data yang dirender berubah."""
    f = lambda x: SAMAR_DURASI.sub('N m', x) if isinstance(x, str) else x
    d = s['detail'] or {}
    return json.dumps([s['summary'], [[r[k] for k in ('id', 'st', 'who', 'segDone', 'segCur', 'subs')] for r in s['missions'] + s['done']],
                       s['events'], s['eventCount'], s['alertJudul'], f(s['alertTeks']), d.get('h2'), d.get('pill'),
                       [[a[0], a[1], a[3]] for a in d.get('steps') or []], [[a[0], a[1], a[3]] for a in d.get('subs') or []], d.get('ev'),
                       f(d.get('callout')), [[c['id'], f(c['teks'])] for r in s['rooms'] for c in r['chips']]], ensure_ascii=False)


class Asli:
    """sumber data asli: folder keluaran generator di host (hanya DIBACA lewat ssh; tidak ada unggah/ubah)."""
    def __init__(self, host_dir):
        self.host_dir = host_dir

    def baca(self, akun):
        r = subprocess.run(SSH + [HOST, 'cat %s' % shlex.quote('%s/%s.json' % (self.host_dir, akun))], capture_output=True, timeout=30, stdin=subprocess.DEVNULL)
        if r.returncode != 0:
            raise Galat('baca %s.json rc=%d' % (akun, r.returncode))
        return json.loads(r.stdout.decode('utf-8'))

    def tutup(self):
        pass

    def kembalikan(self):
        pass


class Uji:
    def __init__(self, a, br, fx):
        self.a, self.br, self.fx, self.hasil, self.state, self.rahasia = a, br, fx, [], {}, []
        self.asli = bool(getattr(a, 'asli', None))
        self.samar = {}
        self.ganti = {}
        for g in a.ganti or []:
            p, f = g.split('=', 1)
            self.ganti[p] = open(f, 'rb').read()
        self.base = a.base

    def cek(self, bagian, nama, ok, ket=''):
        self.hasil.append({'bagian': bagian, 'nama': nama, 'ok': bool(ok), 'ket': ket})
        return bool(ok)

    def klik(self, bag, nama, page, sel, tunggu_ms=250):
        """klik elemen yang DIHARAPKAN ada: tidak ada/gagal diklik = satu cek gagal (bagian berlanjut), bukan pengecualian."""
        try:
            n = page.locator(sel).count()
            if n == 0:
                return self.cek(bag, 'klik %s: elemen %s ada' % (nama, sel), False, 'tidak ada elemen')
            page.click(sel, timeout=5000)
        except Exception as e:  # noqa: BLE001
            return self.cek(bag, 'klik %s: elemen %s bisa diklik' % (nama, sel), False, '%s: %s' % (type(e).__name__, str(e)[:160]))
        page.wait_for_timeout(tunggu_ms)
        return True

    def samarkan(self, D):
        """mode asli: judul misi/tugas dari data asli disamarkan di keluaran (bukan di uji)."""
        for m in (D or {}).get('misi') or []:
            if isinstance(m, dict) and m.get('judul') and isinstance(m.get('nomor'), int):
                self.samar[m['judul']] = 'Judul misi %d' % m['nomor']
        for t in (D or {}).get('tugas_aktif') or []:
            if isinstance(t, dict) and t.get('judul'):
                self.samar.setdefault(t['judul'], 'Judul tugas %s' % t.get('id'))

    def aman(self, s):
        for r in self.rahasia:
            s = s.replace(r, '***')
        for j in sorted(self.samar, key=len, reverse=True):
            s = s.replace(j, self.samar[j])
            s = s.replace(json.dumps(j, ensure_ascii=False)[1:-1], self.samar[j])
        return s

    # ---- akun + masuk lewat form asli
    def pw(self, akun, baru=False):
        p = os.path.join(self.a.pw_dir, akun + ('.baru' if baru else ''))
        if baru and not os.path.exists(p):
            fd = os.open(p, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            os.write(fd, secrets.token_urlsafe(18).encode())
            os.close(fd)
        v = open(p, encoding='utf-8').read().strip()
        if not v:
            raise Galat('password kosong untuk %s' % akun)
        self.rahasia.append(v)
        return v

    def konteks(self, lebar, state=None, tema=None, warna='light'):
        ctx = self.br.new_context(viewport={'width': lebar, 'height': 900 if lebar > 600 else 844},
                                  device_scale_factor=1 if lebar > 600 else 2, color_scheme=warna, storage_state=state)
        def sajikan(p, isi):  # handler dipanggil (route, request): jangan pakai parameter default untuk menangkap isi
            tipe = 'text/css; charset=utf-8' if p.endswith('.css') else 'text/javascript; charset=utf-8'
            return lambda route, request: route.fulfill(status=200, body=isi, headers={'Content-Type': tipe})
        for p, isi in self.ganti.items():
            ctx.route('**' + p, sajikan(p, isi))
        ctx.set_default_timeout(8000)
        ctx.set_default_navigation_timeout(30000)
        page = ctx.new_page()
        mon = Pantau(ctx, page, self.rahasia)
        pasang_init(mon.cdp, [INIT] + (["try { localStorage.setItem('tema', %s); } catch (e) {}" % json.dumps(tema)] if tema else []))
        return ctx, page, mon

    def umum(self, bag, nm, page, mon, lebar, penuh=True):
        s = ev(page, SNAP)
        luar = [u for u in mon.req if not u.startswith(self.base + '/')]
        self.cek(bag, '%s: 0 request ke luar origin uji' % nm, not luar and mon.req, luar[:3] or len(mon.req))
        self.cek(bag, '%s: 0 pelanggaran CSP' % nm, not s['csp'], s['csp'][:3])
        g, fav = mon.galat()
        self.cek(bag, '%s: 0 galat konsol/eksepsi (favicon dikecualikan: %d)' % (nm, fav), not g, g[:3])
        self.cek(bag, '%s: tanpa gulir horizontal (lebar %d)' % (nm, lebar), s['sw'] <= s['cw'] and s['bsw'] <= s['cw'], (s['sw'], s['bsw'], s['cw']))
        self.cek(bag, '%s: 0 dialog/alert (kanari XSS tidak jalan)' % nm, not s['dialog'] and not mon.dialog, (s['dialog'], mon.dialog))
        if not penuh:  # UI lama (gladi rollback): struktur aset/DOM berbeda, hanya cek umum di atas
            return s
        self.cek(bag, '%s: 0 elemen img, 0 atribut handler on*, skrip hanya tema.js+app.js'
                 % nm, s['imgs'] == 0 and s['handler'] == 0 and s['scripts'] == [['/aset/tema.js', 0], ['/aset/app.js', 0]], (s['imgs'], s['handler'], s['scripts']))
        self.cek(bag, '%s: 0 atribut style= di DOM' % nm, not s['styleAttr'], s['styleAttr'][:3])
        return s

    def font(self, bag, nm, page, mon):
        r = ev(page, "() => document.fonts.ready.then(() => [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family.replace(/\"/g, '') + ' ' + f.weight))")
        res = [x for x in mon.res if '/aset/font/' in x[0]]
        self.cek(bag, '%s: font Public Sans termuat dari /aset/font (200 font/woff2)' % nm,
                 r and all(x.startswith('Public Sans') for x in r) and res and all(x[1] == 200 and x[2].startswith('font/woff2') for x in res),
                 (r, [(x[0].rsplit('/', 1)[-1], x[1]) for x in res]))

    def masuk(self, akun, layar=False, judul='Kantor Agen'):
        bag = 'masuk'
        ctx, page, mon = self.konteks(1366)
        page.goto(self.base + '/login', wait_until='load')
        page.wait_for_timeout(300)
        if layar:
            page.screenshot(path=os.path.join(self.a.layar, 'login-1366-terang.png'), full_page=True)
        ok_form = self.cek(bag, '%s: halaman login%s + form /login' % (akun, (' berjudul ' + judul) if judul else ''),
                           (judul is None or page.title() == judul) and ev(page, "() => !!document.querySelector('form[action=\"/login\"] #akun')"))
        if not ok_form:  # elemen yang diharapkan tidak ada: gagal per butir, bukan pengecualian
            ctx.close()
            return False
        page.fill('#akun', akun)
        page.fill('#password', self.pw(akun))
        with page.expect_navigation():
            page.click('form[action="/login"] button[type=submit]')
        ganti = page.url.endswith('/ganti-password')
        if ganti:
            page.wait_for_timeout(300)
            if layar:
                page.screenshot(path=os.path.join(self.a.layar, 'ganti-1366-terang.png'), full_page=True)
            baru = self.pw(akun, True)
            page.fill('#password_baru', baru)
            page.fill('#password_ulang', baru)
            with page.expect_navigation():
                page.click('form[action="/ganti-password"] button[type=submit]')
            if page.url == self.base + '/':
                os.replace(os.path.join(self.a.pw_dir, akun + '.baru'), os.path.join(self.a.pw_dir, akun))
        self.cek(bag, '%s: login lewat form asli -> beranda (%s)' % (akun, 'dengan wajib-ganti' if ganti else 'tanpa wajib-ganti'),
                 page.url == self.base + '/', page.url.replace(self.base, ''))
        g, _ = mon.galat()
        self.cek(bag, '%s: halaman login/ganti 0 galat konsol, 0 request luar' % akun,
                 not g and all(u.startswith(self.base + '/') for u in mon.req), g[:2])
        self.state[akun] = ctx.storage_state()
        ctx.close()
        return ganti

    def login_hp(self):
        ctx, page, mon = self.konteks(390)
        page.goto(self.base + '/login', wait_until='load')
        page.wait_for_timeout(300)
        page.screenshot(path=os.path.join(self.a.layar, 'login-390-terang.png'), full_page=True)
        s = ev(page, "() => [document.documentElement.scrollWidth, document.documentElement.clientWidth]")
        self.cek('masuk', 'login 390: tanpa gulir horizontal', s[0] <= s[1], s)
        ctx.close()

    def buka(self, akun, lebar, tema=None):
        ctx, page, mon = self.konteks(lebar, self.state[akun], tema)
        page.goto(self.base + '/', wait_until='load')
        ok = tunggu(page, "() => window.__nrk > 0 && !!document.querySelector('#map .chip')", 15)
        ev(page, '() => document.fonts.ready.then(() => 1)')
        page.wait_for_timeout(400)
        return ctx, page, mon, ok

    # ---- banding DOM vs harapan
    def data(self, bag, nm, s, D):
        c = lambda n, ok, ket='': self.cek(bag, '%s: %s' % (nm, n), ok, ket)
        c('ringkasan header (D5)', s['summary'] == harap_summary(D), s['summary'])
        c('stamp "Langsung · HH.MM.SS" (D5)', re.fullmatch(r'Langsung · \d\d\.\d\d\.\d\d', s['stamp'] or ''), s['stamp'])
        o = next(x for x in D['orang'] if x['id'] == D['penonton'])
        c('nama penonton + avatar (D5)', s['meNama'] == o['nama'] and s['meAv'] == inisial(o['nama']) and 't-' + o['id'] in (s['meAvCls'] or ''),
          (s['meNama'], s['meAv'], s['meAvCls']))
        c('legenda sibuk hanya untuk order-sendiri', s['legendSibuk'] == (D['cakupan'] == 'order-sendiri'), s['legendSibuk'])
        c('tanpa banner galat', s['banner'] is None, s['banner'])
        # D6 peta kantor
        harap_r = []
        for rid, rn in RUANG:
            A = [a for a in D['agen'] if a['ruang'] == rid]
            if A or rid != 'lain':
                harap_r.append((rn, '%d dari %d sibuk' % (sum(1 for a in A if a['keadaan'] != 'bebas'), len(A)), [a['id'] for a in A]))
        c('ruang urut + "x dari y sibuk" (D6)', [(r['nama'], r['sibuk'], [x['id'] for x in r['chips']]) for r in s['rooms']] == harap_r,
          [(r['nama'], r['sibuk']) for r in s['rooms']])
        chips = {x['id']: x for r in s['rooms'] for x in r['chips']}
        for a in D['agen']:
            pola, kls, aria, _ = harap_chip(D, a)
            x = chips.get(a['id'], {})
            av = kelas_warna(D, a['id'])
            c('chip %s teks/kelas/aria/avatar (D6, D2)' % a['id'],
              re.fullmatch(pola, x.get('teks') or '') and kls in (x.get('cls') or '').split() and (x.get('label') or '').startswith(aria)
              and x.get('nama') == a['nama'] and x.get('avTeks') == a['nama'][0]
              and ((av in (x.get('av') or '').split()) if av else not re.search(r'\bt-', x.get('av') or '')),
              (x.get('teks'), x.get('cls'), x.get('label'), x.get('av'), pola))
        # D7 banner tertahan
        ha = harap_alert(D)
        if ha:
            c('banner tertahan (D7)', s['alertJudul'] == ha[0] and s['alertTeks'] == ha[1] and s['alertLinks'] == ha[2],
              (s['alertJudul'], s['alertTeks'], s['alertLinks']))
        else:
            c('tanpa banner tertahan bila tidak ada misi-lain (D7)', s['alertKosong'], s['alertJudul'])
        # koreksi 1 (keputusan CTO 6a): banner menyebut SEMUA anak menunggu_misi + tautan Buka per anak
        T = [m for m in D['misi'] if m['status'] == 'menunggu' and m['alasan'] == 'misi-lain']
        if D['penonton'] == 'akbar' and not self.asli:  # fixture karangan wajib memuat kasus 6a; data asli apa adanya
            c('fixture memuat misi tertahan dengan >= 2 anak aktif berpelaksana beda (kasus 6a)',
              any(len({x['pelaksana_id'] for x in anak_misi(D, m) if aktif(x)}) >= 2 for m in T), [(m['id'], m['menunggu_misi']) for m in T])
        if T and len(anak_misi(D, T[0])) >= 2:
            cs = anak_misi(D, T[0])
            c('banner menyebut semua anak %s + tautan Buka per anak (D7 rev 6a)' % ','.join(x['id'] for x in cs),
              all(x['id'] in (s['alertTeks'] or '') for x in cs) and all([x['id'], 'Buka ' + x['id']] in (s['alertLinks'] or []) for x in cs),
              (s['alertTeks'], s['alertLinks']))
        c('teks tanpa "Tagih"', 'Tagih' not in s['teks'])
        # D8 daftar misi
        akt = [m for m in D['misi'] if aktif(m)]
        sel = [m for m in D['misi'] if not aktif(m)]
        c('jumlah misi aktif (D8)', s['missionCount'] == '%d aktif · klik untuk melihat detail' % len(akt), s['missionCount'])
        for daftar, harap, nmd in ((s['missions'], akt, 'aktif'), (s['done'], sel, 'selesai')):
            c('urutan daftar %s = urutan berkas (C8)' % nmd, [x['id'] for x in daftar] == [m['id'] for m in harap], [x['id'] for x in daftar])
            for x, m in zip(daftar, harap):
                h = harap_baris(D, m)
                c('baris %s (D8)' % m['id'],
                  x['head'] == h['head'] and x['st'] == h['st'] and h['stKind'] in (x['stCls'] or '').split() and x['judul'] == h['judul']
                  and x['who'] == h['who'] and h['av'] in (x['avCls'] or '').split() and x['segDone'] == h['segDone'] and x['segCur'] == h['segCur']
                  and x['segAll'] == h['segDone'] + h['segCur'] and x['subs'] == h['subs'],
                  {k: (x.get(k), h.get(k)) for k in ('head', 'st', 'judul', 'who', 'segDone', 'segCur', 'subs') if x.get(k) != h.get(k)})
        c('kartu Selesai hari ini (D8)', (s['doneHidden'] and not sel) or (not s['doneHidden'] and s['doneJudul'] == 'Selesai hari ini' and s['doneN'] == '%d misi' % len(sel)),
          (s['doneHidden'], s['doneJudul'], s['doneN']))
        if not akt:
            c('daftar aktif kosong', s['missionsEmpty'] == 'Tidak ada misi aktif.', s['missionsEmpty'])
        # D10 panel Pak Akbar
        if D['penonton'] == 'akbar':
            ho = harap_owner(D)
            o = s['owner'] or {}
            c('panel Pak Akbar (D10)', o.get('h2') == 'Pak Akbar' and o.get('insLabel') == ho['insLabel']
              and [i[:3] for i in o.get('ins', [])] == ho['ins'] and [i[3] for i in o.get('ins', [])] == ho['insKind']
              and o.get('givers') == ho['givers'] and kelas_warna(D, D['pemilik']) in (o.get('av') or '').split(),
              (o.get('insLabel'), o.get('ins'), o.get('givers')))
        else:
            c('panel Pak Akbar TIDAK ada di DOM (D10)', s['owner'] is None and not s['ownerTeks'] and 'id="owner"' not in s['html'])
        # D11 peristiwa
        he, n = harap_events(D)
        c('peristiwa terbaru 8 terbaru dulu + jumlah (D11)', s['events'] == he and s['eventCount'] == '%d hari ini' % n
          and s['more'] == ('Tampilkan semua (%d)' % n if n > 8 else None), (s['events'][:2], s['eventCount'], s['more']))
        # kanari XSS tampil sebagai teks
        kan = [m['judul'] for m in D['misi'] if m['judul'] and '<' in m['judul']]
        if kan or not self.asli:  # fixture wajib berkanari; data asli: hanya bila ada judul ber-'<'
            c('judul berkanari tampil sebagai teks literal (D3)', kan and all(k in s['teks'] for k in kan), kan)
        # data yang diterima = berkas penonton sesi
        c('data SSE milik penonton sesi', s['rkPenonton'] == D['penonton'], s['rkPenonton'])

    def detail(self, bag, nm, s, D, mid):
        m = misi_id(D, mid)
        h = harap_detail(D, m)
        d = s['detail'] or {}
        c = lambda n, ok, ket='': self.cek(bag, '%s: detail %s %s' % (nm, mid, n), ok, ket)
        c('judul + meta + pill (D9)', d.get('h2') == h['h2'] and d.get('meta') == h['meta'] and d.get('pill') == h['pill']
          and h['pillKind'] in (d.get('pillCls') or '').split(), (d.get('h2'), d.get('meta'), d.get('pill')))
        f = d.get('facts') or []
        c('fakta pelaksana/rantai/waktu/sub-agen (D9)', len(f) == 4 and all(a[0] == b[0] and (re.fullmatch(b[1], a[1] or '') if b[1].startswith('^') else a[1] == b[1])
                                                                          for a, b in zip(f, h['facts'])), f)
        st = d.get('steps') or []
        c('kotak Langkah (D9)', d.get('stepsHead') == h['stepsHead'] and len(st) == len(h['steps']) and all(
            a[0] == b[0] and a[1] == b[1] and re.fullmatch(b[2], a[2] or '') and a[3] == b[3] for a, b in zip(st, h['steps'])), (d.get('stepsHead'), st))
        if h['subs'] is None:
            c('kotak Sub-agen: data null', not d.get('subs') and d.get('subEmpty') == 'Data sub-agen tidak tersedia.', d.get('subEmpty'))
        elif not h['subs']:
            c('kotak Sub-agen kosong', not d.get('subs') and (d.get('subEmpty') or '').startswith('Belum ada sub-agen.'), d.get('subEmpty'))
        else:
            sb = d.get('subs') or []
            c('kotak Sub-agen tanpa teks tugas (D9)', d.get('subsHead') == 'nomor = spawn ke-n' and len(sb) == len(h['subs']) and all(
                a[0] == b[0] and a[1] == b[1] and re.fullmatch(b[2], a[2] or '') and a[3] == b[3] for a, b in zip(sb, h['subs'])), sb)
        c('peristiwa misi ini terbaru dulu (D9)', d.get('ev') == h['ev'] and d.get('evN') == h['evN'], (d.get('evN'), (d.get('ev') or [])[:2]))
        if h['callout']:
            c('callout + tautan Buka (D9)', re.fullmatch(h['callout'], d.get('callout') or '') and d.get('calloutLinks') == h['calloutLinks'],
              (d.get('callout'), d.get('calloutLinks')))
        else:
            c('tanpa callout', d.get('callout') is None, d.get('callout'))
        cs = anak_misi(D, m) if m['status'] == 'menunggu' and m['alasan'] == 'misi-lain' else []
        if len(cs) >= 2:  # koreksi 1 (keputusan CTO 6a)
            c('callout menyebut semua anak %s + tautan Buka per anak (D9 rev 6a)' % ','.join(x['id'] for x in cs),
              all(x['id'] in (d.get('callout') or '') for x in cs) and all([x['id'], 'Buka ' + x['id']] in (d.get('calloutLinks') or []) for x in cs),
              (d.get('callout'), d.get('calloutLinks')))
        c('tanpa tombol Tagih', not re.search('Tagih', json.dumps(d)))

    def layar(self, page, nama):
        page.screenshot(path=os.path.join(self.a.layar, nama + '.png'), full_page=True)

    # ---- bagian
    def bag_masuk(self):
        for akun in ('akbar', 'dicky', 'jati'):
            self.masuk(akun, layar=(akun == 'akbar'))
        self.login_hp()

    def pastikan(self, akun):
        if akun not in self.state:
            self.masuk(akun)

    def bag_akbar(self):
        bag, D = 'akbar', self.fx.data['akbar']
        self.pastikan('akbar')
        ctx, page, mon, ok = self.buka('akbar', 1366, 'terang')
        self.cek(bag, 'akbar 1366: data SSE dirender', ok)
        s = self.umum(bag, 'akbar 1366 terang', page, mon, 1366)
        self.font(bag, 'akbar 1366', page, mon)
        self.cek(bag, 'tema awal terang dari localStorage', s['tema'] == 'terang', s['tema'])
        self.data(bag, 'akbar 1366', s, D)
        awal = pilihan_awal(D)
        self.cek(bag, 'pilihan awal = misi tertahan pertama (%s)' % awal, (s['detail'] or {}).get('h2') == (misi_id(D, awal)['judul'] or '(tanpa judul)'))
        self.detail(bag, 'akbar', s, D, awal)
        self.layar(page, 'akbar-1366-terang')
        # klik chip (D6)
        for aid in ('carli', 'uci', 'eko'):
            if not self.klik(bag, 'chip %s' % aid, page, '.chip[data-agent="%s"]' % aid):
                continue
            s = ev(page, SNAP)
            pil = harap_chip(D, next(a for a in D['agen'] if a['id'] == aid))[3]
            if pil:
                m = misi_id(D, pil)
                pressed = [x['id'] for x in s['missions'] + s['done'] if x['pressed'] == 'true']
                self.cek(bag, 'klik chip %s -> buka %s, baris tertekan, fokus tetap di chip (D6, D12, mockup)' % (aid, pil),
                         (s['detail'] or {}).get('h2') == (m['judul'] or '(tanpa judul)') and pressed == [pil] and s['active'] == 'chip-' + aid
                         and s.get('panel') == 'misi:' + pil, ((s['detail'] or {}).get('h2'), pressed, s['active'], s.get('panel')))
                self.detail(bag, 'akbar', s, D, pil)
            else:
                ok, ket = cek_panel_agen(s, next(a for a in D['agen'] if a['id'] == aid))
                self.cek(bag, 'klik chip %s tanpa misi -> panel agen (K-1, K-3)' % aid, ok and s['active'] == 'chip-' + aid, ket)
                cek_meta_agen(self.cek, bag, 'akbar 1366', s, next(a for a in D['agen'] if a['id'] == aid))
            tekan = sorted(x['id'] for r in s['rooms'] for x in r['chips'] if x['pressed'] == 'true')
            self.cek(bag, 'klik chip %s -> hanya chip %s tertekan (K-4)' % (aid, aid), tekan == [aid], tekan)
        for mid in ('T-283', 'T-284', 'T-282', 'T-278', 'T-289', 'T-281'):
            if not self.klik(bag, 'baris misi %s' % mid, page, '.m-row[data-task="%s"]' % mid):
                continue
            s = ev(page, SNAP)
            self.detail(bag, 'akbar', s, D, mid)
            # K-4 (koreksi header): chip tertekan = pelaksana misi yang terbuka
            harap = sorted(a['id'] for a in D['agen'] if a['id'] == misi_id(D, mid)['pelaksana_id'])
            tekan = sorted(x['id'] for r in s['rooms'] for x in r['chips'] if x['pressed'] == 'true')
            self.cek(bag, 'buka %s -> chip tertekan = %s (D6)' % (mid, harap or 'tidak ada'), tekan == harap, tekan)
        # tautan Buka di banner tertahan (D7)
        ha = harap_alert(D)
        for tid_, teks in (ha[2] if ha else []):
            if not self.klik(bag, 'banner "%s"' % teks, page, '#alert [data-task="%s"]' % tid_):
                continue
            s = ev(page, SNAP)
            self.cek(bag, 'banner: "%s" membuka detail %s' % (teks, tid_), (s['detail'] or {}).get('h2') == (misi_id(D, tid_)['judul'] or '(tanpa judul)'),
                     (s['detail'] or {}).get('h2'))
        # D11 tampilkan semua
        if self.klik(bag, 'Tampilkan semua', page, '#events .more', 200):
            s = ev(page, SNAP)
            he, n = harap_events(D, True)
            self.cek(bag, 'Tampilkan semua -> %d peristiwa (maks 60) + "Tampilkan lebih sedikit"' % len(he), s['events'] == he and s['more'] == 'Tampilkan lebih sedikit', (len(s['events']), s['more']))
            if self.klik(bag, 'Tampilkan lebih sedikit', page, '#events .more', 200):
                s = ev(page, SNAP)
                self.cek(bag, 'Tampilkan lebih sedikit -> 8 lagi', len(s['events']) == 8 and s['more'] == 'Tampilkan semua (%d)' % n, (len(s['events']), s['more']))
        # D12 fokus dipulihkan saat render ulang karena data SSE
        if page.locator('.m-row[data-task="T-284"]').count():
            page.focus('.m-row[data-task="T-284"]')
        n0 = ev(page, '() => window.__nrk')
        ada = tunggu(page, '(n) => window.__nrk > n', 15, n0)
        page.wait_for_timeout(300)
        s = ev(page, SNAP)
        self.cek(bag, 'fokus tetap di baris T-284 sesudah render ulang SSE (D12)', ada and s['active'] == 'm-T-284', (ada, s['active']))
        # SSE: tambah langkah + peristiwa -> DOM berubah tanpa reload
        ev(page, "() => { window.__penanda = 'kantor-' + Math.floor(performance.now()); }")
        pen0 = ev(page, '() => [window.__penanda, performance.timeOrigin, performance.getEntriesByType("navigation").length]')
        jb = self.fx.basis()

        def tambah_langkah(mod):
            m = next(x for x in mod.MISI if x['n'] == 283)
            m['lk'] = m['lk'] + [(jb, 'Langkah')]
            m['lw'] = jb
        self.fx.ubah(tambah_langkah)
        D2 = self.fx.data['akbar']
        m2 = misi_id(D2, 'T-283')
        top = harap_events(D2)[0][0]
        ok = tunggu(page, "(h) => { const r = document.querySelector('.m-row[data-task=\"T-283\"] .st'); const e = document.querySelector('#events .ev span');"
                          " return r && r.textContent === h[0] && e && e.textContent.replace(/\\s+/g, ' ').trim() === h[1]; }", 15, [label(m2), top[1]])
        pen1 = ev(page, '() => [window.__penanda, performance.timeOrigin, performance.getEntriesByType("navigation").length]')
        self.cek(bag, 'SSE: langkah + peristiwa baru tampil tanpa reload (%s, "%s")' % (label(m2), top[1]), ok and pen1 == pen0 and pen0[2] == 1, (ok, pen0, pen1))
        s = ev(page, SNAP)
        self.data(bag, 'akbar sesudah SSE', s, D2)
        # D5 Jeda: data baru disimpan, tidak dirender; Lanjutkan menerapkan yang terbaru
        sa = ev(page, SNAP)
        ax = [('awal',) + nama_ax(page, mon.cdp, '#pause') + (sa['pausePressed'], sa['pauseLabel'])]  # KR-1
        self.klik(bag, 'Jeda', page, '#pause', 200)
        s0 = ev(page, SNAP)
        ax.append(('ditekan',) + nama_ax(page, mon.cdp, '#pause') + (s0['pausePressed'], s0['pauseLabel']))
        self.cek(bag, 'Jeda (KR-1): aria-pressed true, tanpa aria-label, stamp "Dijeda · ", titik abu',
                 s0['pausePressed'] == 'true' and s0['pauseLabel'] is None and (s0['stamp'] or '').startswith('Dijeda · ') and s0['dotPaused'],
                 (s0['pausePressed'], s0['pauseLabel'], s0['stamp'], s0['dotPaused']))
        jb = self.fx.basis()

        def selesaikan(mod):
            m = next(x for x in mod.MISI if x['n'] == 282)
            m['st'], m['sel'], m['sub'] = 'selesai', jb, [(a, b or jb) for a, b in m['sub']]
        self.fx.ubah(selesaikan)
        D3 = self.fx.data['akbar']
        tiba = tunggu(page, "() => !!window.__rk && window.__rk.misi.some(m => m.id === 'T-282' && m.status === 'selesai')", 15)
        page.wait_for_timeout(1500)
        s1 = ev(page, SNAP)
        kunci = lambda x: (x['summary'], [m['id'] for m in x['missions']], [m['id'] for m in x['done']], x['events'], x['eventCount'],
                           [(r['nama'], r['sibuk'], [(c['id'], c['teks']) for c in r['chips']]) for r in x['rooms']], x['stamp'])
        self.cek(bag, 'Jeda: data baru diterima tetapi tampilan tidak berubah (D5)', tiba and kunci(s1) == kunci(s0), (tiba, kunci(s1)[0], kunci(s0)[0]))
        self.klik(bag, 'Lanjutkan', page, '#pause', 400)
        s2 = ev(page, SNAP)
        ax.append(('dilepas',) + nama_ax(page, mon.cdp, '#pause') + (s2['pausePressed'], s2['pauseLabel']))
        self.cek(bag, 'Lanjutkan: data terbaru diterapkan (T-282 pindah ke selesai, ringkasan baru)',
                 s2['pausePressed'] == 'false' and s2['pauseLabel'] is None and 'T-282' in [m['id'] for m in s2['done']] and s2['summary'] == harap_summary(D3) and (s2['stamp'] or '').startswith('Langsung · '),
                 (s2['pausePressed'], s2['pauseLabel'], s2['summary'], s2['stamp']))
        cek_jeda_ax(self.cek, bag, 'akbar 1366', ax)
        self.data(bag, 'akbar sesudah Lanjutkan', s2, D3)
        self.fx.kembalikan()
        ok = tunggu(page, "() => !!document.querySelector('#missions .m-row[data-task=\"T-282\"]')", 15)
        self.cek(bag, 'fixture dipulihkan -> T-282 aktif lagi', ok)
        # tema (D5, D12)
        self.klik(bag, 'tombol tema (ke gelap)', page, '#theme', 300)
        t = ev(page, "() => [document.documentElement.dataset.tema, localStorage.getItem('tema'), document.querySelector('#theme').getAttribute('aria-label'), getComputedStyle(document.body).backgroundColor]")
        self.cek(bag, 'tombol tema -> gelap, tersimpan di localStorage "tema", label berganti', t[:3] == ['gelap', 'gelap', 'Ganti ke tema terang'], t)
        self.klik(bag, 'baris misi T-283 (gelap)', page, '.m-row[data-task="T-283"]', 300)
        s = self.umum(bag, 'akbar 1366 gelap', page, mon, 1366)
        self.data(bag, 'akbar 1366 gelap', s, self.fx.data['akbar'])
        self.layar(page, 'akbar-1366-gelap')
        self.klik(bag, 'tombol tema (ke terang)', page, '#theme', 200)
        t2 = ev(page, "() => [document.documentElement.dataset.tema, document.querySelector('#theme').getAttribute('aria-label'), getComputedStyle(document.body).backgroundColor]")
        self.cek(bag, 'tombol tema kembali ke terang, latar berbeda', t2[0] == 'terang' and t2[1] == 'Ganti ke tema gelap' and t2[2] != t[3], t2)
        # D4 galat -> banner, pulih -> hilang
        self.fx.jeda = True
        self.fx.rusak('akbar')
        ok1 = tunggu(page, "() => { const b = document.querySelector('#banner'); return b && !b.hidden && b.textContent === 'Ringkasan tidak tersedia'; }", 10)
        self.fx.jeda = False
        self.fx.unggah()
        ok2 = tunggu(page, "() => document.querySelector('#banner').hidden", 10)
        self.cek(bag, 'event galat -> banner "Ringkasan tidak tersedia", data pulih -> banner hilang (D4)', ok1 and ok2, (ok1, ok2))
        if 'basi' in self.a.bagian:
            self.fx.jeda = True
            ok1 = tunggu(page, "() => { const b = document.querySelector('#banner'); return b && !b.hidden && b.textContent.startsWith('Data basi'); }", 50)
            self.fx.jeda = False
            self.fx.unggah()
            ok2 = tunggu(page, "() => document.querySelector('#banner').hidden", 15)
            self.cek(bag, 'generator berhenti > 30 dtk -> banner "Data basi", segar -> hilang (D4)', ok1 and ok2, (ok1, ok2))
        # sesi habis -> /login (event sesi)
        r = ctx.request.post(self.base + '/logout', headers={'Origin': self.base}, max_redirects=0)
        ok = tunggu(page, "() => location.pathname === '/login'", 10)
        self.cek(bag, 'sesi dicabut (POST /logout lain) -> halaman pindah ke /login (event sesi, D4)', r.status == 303 and ok, (r.status, page.url.replace(self.base, '')))
        ctx.close()
        self.state.pop('akbar', None)

    def bag_akbar390(self):
        bag = 'akbar390'
        self.pastikan('akbar')
        for tema in ('terang', 'gelap'):
            ctx, page, mon, ok = self.buka('akbar', 390, tema)
            self.cek(bag, 'akbar 390 %s: data dirender' % tema, ok)
            s = self.umum(bag, 'akbar 390 %s' % tema, page, mon, 390)
            self.cek(bag, 'akbar 390 %s: data-tema sesuai' % tema, s['tema'] == tema, s['tema'])
            self.data(bag, 'akbar 390 %s' % tema, s, self.fx.data['akbar'])
            self.layar(page, 'akbar-390-%s' % tema)
            ctx.close()

    def bag_v(self, v):
        bag = v
        self.pastikan(v)
        A = self.fx.data['akbar']
        D = self.fx.data[v]
        lain = [m for m in A['misi'] if (m['pemberi_id'] or 'akbar') != v]
        for lebar in (1366, 390):
            ctx, page, mon, ok = self.buka(v, lebar, 'terang')
            self.cek(bag, '%s %d: data dirender' % (v, lebar), ok)
            s = self.umum(bag, '%s %d' % (v, lebar), page, mon, lebar)
            self.data(bag, '%s %d' % (v, lebar), s, D)
            awal = pilihan_awal(D)
            if awal:
                self.detail(bag, '%s %d' % (v, lebar), s, D, awal)
            idx = set(re.findall(r'\bT-\d{3,}\b', s['teks'] + s['html']))
            self.cek(bag, '%s %d: tidak ada id misi orang lain di DOM (teks + atribut)' % (v, lebar),
                     idx <= {m['id'] for m in D['misi']} and not any(m['id'] in idx for m in lain), sorted(idx))
            self.cek(bag, '%s %d: tidak ada judul misi orang lain di DOM' % (v, lebar),
                     not any(m['judul'] and m['judul'] in s['teks'] for m in lain))
            self.layar(page, '%s-%d-terang' % (v, lebar))
            if lebar == 1366:
                for m in D['misi']:
                    if self.klik(bag, '%s baris misi %s' % (v, m['id']), page, '[data-task="%s"].m-row' % m['id'], 200):
                        self.detail(bag, v, ev(page, SNAP), D, m['id'])
                self.chip_meta(bag, v, page, lambda: (ev(page, SNAP), D))  # KR-2
                self.klik(bag, '%s tombol Keluar' % v, page, 'form[action="/logout"] button[type=submit]', 0)
                ok = tunggu(page, "() => location.pathname === '/login'", 10)
                r1 = ctx.request.get(self.base + '/', max_redirects=0)
                r2 = ctx.request.get(self.base + '/events', max_redirects=0)
                self.cek(bag, '%s: Keluar -> /login, sesi berakhir (GET / 303 ke /login, /events 401)' % v,
                         ok and r1.status == 303 and r1.headers.get('location') == '/login' and r2.status == 401, (ok, r1.status, r2.status))
                self.state.pop(v, None)
                self.pastikan(v)
            ctx.close()

    def bag_dicky(self):
        self.bag_v('dicky')

    def bag_jati(self):
        self.bag_v('jati')

    # ---- mode DATA ASLI (sesi integrasi 24 Okt): harapan dari ringkasan yang diterima halaman (window.__rk)
    def buka_asli(self, bag, akun, lebar, tema):
        self.pastikan(akun)
        ctx, page, mon, ok = self.buka(akun, lebar, tema)
        D = snap_rk(page)[1]
        self.samarkan(D)
        ok = self.cek(bag, '%s %d %s: data SSE asli dirender' % (akun, lebar, tema), ok and isinstance(D, dict) and D.get('penonton') == akun,
                      (ok, (D or {}).get('penonton')))
        return ctx, page, mon, D if ok else None

    def chip_meta(self, bag, v, page, potret):
        """KR-2 (koreksi 1 header): klik chip via/uci/desy di tampilan V; tanpa misi -> panel agen + baris kecil (KR-2), ada misi -> detail misi."""
        for aid in META_TETAP:
            if not self.klik(bag, '%s chip %s' % (v, aid), page, '.chip[data-agent="%s"]' % aid):
                continue
            s, D = potret()
            a = next((x for x in D['agen'] if x['id'] == aid), None)
            if a is None:
                self.cek(bag, '%s: agen %s ada di data' % (v, aid), False)
                continue
            pil = harap_chip(D, a)[3]
            if pil:
                self.cek(bag, '%s 1366: klik chip %s -> misi:%s (K-2)' % (v, aid, pil), s.get('panel') == 'misi:' + pil, s.get('panel'))
                continue
            ok, ket = cek_panel_agen(s, a)
            self.cek(bag, '%s 1366: klik chip %s tanpa misi -> panel agen (K-1, K-3)' % (v, aid), ok, ket)
            cek_meta_agen(self.cek, bag, '%s 1366' % v, s, a)

    def potret(self, page):
        s, D = snap_rk(page)
        self.samarkan(D)
        return s, D

    def judul_terpilih(self, s, D):
        h = (s['detail'] or {}).get('h2')
        return next((m['id'] for m in D['misi'] if (m['judul'] or '(tanpa judul)') == h), None)

    def bag_asli_akbar(self):
        bag = 'asli_akbar'
        ctx, page, mon, D = self.buka_asli(bag, 'akbar', 1366, 'terang')
        if D is None:  # data tidak dirender: satu cek gagal sudah dicatat, sisa bagian tidak bermakna
            ctx.close()
            return
        self.umum(bag, 'akbar 1366 terang', page, mon, 1366)
        self.font(bag, 'akbar 1366', page, mon)
        s, D = self.potret(page)
        self.cek(bag, 'tema awal terang dari localStorage', s['tema'] == 'terang', s['tema'])
        self.data(bag, 'akbar 1366', s, D)
        awal = pilihan_awal(D)
        if awal:
            self.cek(bag, 'pilihan awal = %s (tertahan pertama, else aktif pertama)' % awal, (s['detail'] or {}).get('h2') == (misi_id(D, awal)['judul'] or '(tanpa judul)'),
                     (s['detail'] or {}).get('h2'))
            self.detail(bag, 'akbar', s, D, awal)
        self.layar(page, 'akbar-1366-terang')
        # D6 klik chip setiap agen di data
        for aid in [a['id'] for a in D['agen']]:
            if not self.klik(bag, 'chip %s' % aid, page, '.chip[data-agent="%s"]' % aid):
                continue
            s, D = self.potret(page)
            a = next((x for x in D['agen'] if x['id'] == aid), None)
            pil = harap_chip(D, a)[3] if a else None
            if pil:
                pressed = [x['id'] for x in s['missions'] + s['done'] if x['pressed'] == 'true']
                self.cek(bag, 'klik chip %s -> buka %s, baris tertekan, fokus tetap di chip (D6, D12)' % (aid, pil),
                         (s['detail'] or {}).get('h2') == (misi_id(D, pil)['judul'] or '(tanpa judul)') and pressed == [pil] and s['active'] == 'chip-' + aid
                         and s.get('panel') == 'misi:' + pil, ((s['detail'] or {}).get('h2'), pressed, s['active'], s.get('panel')))
                self.detail(bag, 'akbar', s, D, pil)
            elif a:
                ok, ket = cek_panel_agen(s, a)
                self.cek(bag, 'klik chip %s tanpa misi -> panel agen (K-1, K-3)' % aid, ok and s['active'] == 'chip-' + aid, ket)
                cek_meta_agen(self.cek, bag, 'akbar 1366', s, a)
            tekan = sorted(x['id'] for r in s['rooms'] for x in r['chips'] if x['pressed'] == 'true')
            self.cek(bag, 'klik chip %s -> hanya chip %s tertekan (K-4)' % (aid, aid), tekan == [aid], tekan)
        # D8/D9 klik setiap baris misi
        for mid in [m['id'] for m in D['misi']]:
            if not self.klik(bag, 'baris misi %s' % mid, page, '.m-row[data-task="%s"]' % mid):
                continue
            s, D = self.potret(page)
            if not misi_id(D, mid):
                self.cek(bag, 'misi %s masih ada di data sesudah klik' % mid, False)
                continue
            self.detail(bag, 'akbar', s, D, mid)
            harap = sorted(a['id'] for a in D['agen'] if a['id'] == misi_id(D, mid)['pelaksana_id'])  # K-4 (koreksi header)
            tekan = sorted(x['id'] for r in s['rooms'] for x in r['chips'] if x['pressed'] == 'true')
            self.cek(bag, 'buka %s -> chip tertekan = %s (D6)' % (mid, harap or 'tidak ada'), tekan == harap, tekan)
        # D7 tautan Buka di banner tertahan
        ha = harap_alert(D)
        for tid_, teks in (ha[2] if ha else []):
            if not self.klik(bag, 'banner "%s"' % teks, page, '#alert [data-task="%s"]' % tid_):
                continue
            s, D = self.potret(page)
            m = misi_id(D, tid_)
            self.cek(bag, 'banner: "%s" membuka detail %s' % (teks, tid_), m is not None and (s['detail'] or {}).get('h2') == (m['judul'] or '(tanpa judul)'),
                     (s['detail'] or {}).get('h2'))
        # D11 tampilkan semua (hanya bila > 8 peristiwa)
        if len(D['riwayat_hari_ini']) > 8 and self.klik(bag, 'Tampilkan semua', page, '#events .more', 200):
            s, D = self.potret(page)
            he, n = harap_events(D, True)
            self.cek(bag, 'Tampilkan semua -> %d peristiwa (maks 60) + "Tampilkan lebih sedikit"' % len(he), s['events'] == he and s['more'] == 'Tampilkan lebih sedikit',
                     (len(s['events']), s['more']))
            if self.klik(bag, 'Tampilkan lebih sedikit', page, '#events .more', 200):
                s, D = self.potret(page)
                he, n = harap_events(D)
                self.cek(bag, 'Tampilkan lebih sedikit -> 8 lagi', s['events'] == he and s['more'] == 'Tampilkan semua (%d)' % n, (len(s['events']), s['more']))
        # SSE tanpa reload: DOM berubah karena DATA (aktivitas sesi integrasi ini), <= batas dtk sejak SIAP-SSE
        PEN = '() => [window.__penanda, performance.timeOrigin, performance.getEntriesByType("navigation").length]'
        ev(page, "() => { window.__penanda = 'asli-' + Math.floor(performance.now()); }")
        pen0 = ev(page, PEN)
        s0, D0 = self.potret(page)
        f0, t0 = sidik(s0), time.time()
        print('SIAP-SSE %s dibuat_pada=%s' % (time.strftime('%H:%M:%S'), D0['dibuat_pada']), flush=True)
        if self.a.sinyal:
            with open(self.a.sinyal, 'w') as fs:
                fs.write(time.strftime('%H:%M:%S') + '\n')
        hasil_sse = None
        while time.time() - t0 < self.a.batas_sse:
            page.wait_for_timeout(500)
            s1, D1 = self.potret(page)
            if sidik(s1) != f0:
                hasil_sse = (s1, D1, time.time() - t0)
                break
        pen1 = ev(page, PEN)
        if hasil_sse:
            s1, D1, detik = hasil_sse
            a0, a1 = json.loads(f0), json.loads(sidik(s1))
            nama_k = ['ringkasan', 'baris-misi', 'peristiwa', 'jumlah-peristiwa', 'banner-judul', 'banner-teks', 'detail-judul', 'detail-pill',
                      'detail-langkah', 'detail-subagen', 'detail-peristiwa', 'detail-callout', 'chip']
            komp = [nama_k[i] for i in range(len(a0)) if a0[i] != a1[i]]
            m0 = {m['id']: (m['status'], len(m['langkah']), m['langkah_sekarang'], None if m['subagen'] is None else len(m['subagen'])) for m in D0['misi']}
            m1 = {m['id']: (m['status'], len(m['langkah']), m['langkah_sekarang'], None if m['subagen'] is None else len(m['subagen'])) for m in D1['misi']}
            dbeda = ['%s %s->%s' % (k, m0.get(k), m1.get(k)) for k in sorted(set(m0) | set(m1)) if m0.get(k) != m1.get(k)]
            if len(D0['riwayat_hari_ini']) != len(D1['riwayat_hari_ini']):
                dbeda.append('riwayat %d->%d' % (len(D0['riwayat_hari_ini']), len(D1['riwayat_hari_ini'])))
            g0 = {a['id']: (a['keadaan'], a['misi_aktif']) for a in D0['agen']}
            g1 = {a['id']: (a['keadaan'], a['misi_aktif']) for a in D1['agen']}
            dbeda += ['agen %s %s->%s' % (k, g0.get(k), g1.get(k)) for k in sorted(set(g0) | set(g1)) if g0.get(k) != g1.get(k)]
            if D0['ringkasan'] != D1['ringkasan']:
                dbeda.append('ringkasan berubah')
            if [t.get('id') for t in D0['tugas_aktif']] != [t.get('id') for t in D1['tugas_aktif']]:
                dbeda.append('tugas_aktif %d->%d' % (len(D0['tugas_aktif']), len(D1['tugas_aktif'])))
            self.cek(bag, 'SSE: DOM berubah karena data tanpa reload dalam %.1f dtk (batas %d) | komponen: %s | data: %s' % (
                detik, self.a.batas_sse, ','.join(komp), '; '.join(dbeda) or 'tidak ada beda misi/riwayat'),
                pen1 == pen0 and pen0[2] == 1 and D1['dibuat_pada'] != D0['dibuat_pada'] and bool(dbeda), (pen0, pen1, D0['dibuat_pada'], D1['dibuat_pada']))
            self.data(bag, 'akbar sesudah SSE', s1, D1)
            sel = self.judul_terpilih(s1, D1)
            if sel:
                self.detail(bag, 'akbar sesudah SSE', s1, D1, sel)
        else:
            self.cek(bag, 'SSE: DOM berubah karena data tanpa reload dalam <= %d dtk' % self.a.batas_sse, False, (pen0, pen1))
        # KR-1: nama aksesibel tombol jeda dari pohon AX (awal / ditekan / dilepas)
        ax = []
        for lk in ('awal', 'ditekan', 'dilepas'):
            if lk != 'awal':
                self.klik(bag, 'tombol jeda (%s)' % lk, page, '#pause', 300)
            sj = ev(page, SNAP)
            ax.append((lk,) + nama_ax(page, mon.cdp, '#pause') + (sj['pausePressed'], sj['pauseLabel']))
        cek_jeda_ax(self.cek, bag, 'akbar 1366', ax)
        # tema gelap (D5, D12)
        self.klik(bag, 'tombol tema (ke gelap)', page, '#theme', 300)
        t = ev(page, "() => [document.documentElement.dataset.tema, localStorage.getItem('tema'), document.querySelector('#theme').getAttribute('aria-label'), getComputedStyle(document.body).backgroundColor]")
        self.cek(bag, 'tombol tema -> gelap, tersimpan di localStorage "tema", label berganti', t[:3] == ['gelap', 'gelap', 'Ganti ke tema terang'], t)
        self.umum(bag, 'akbar 1366 gelap', page, mon, 1366)
        s, D = self.potret(page)
        self.data(bag, 'akbar 1366 gelap', s, D)
        self.layar(page, 'akbar-1366-gelap')
        self.klik(bag, 'tombol tema (ke terang)', page, '#theme', 200)
        t2 = ev(page, "() => [document.documentElement.dataset.tema, document.querySelector('#theme').getAttribute('aria-label'), getComputedStyle(document.body).backgroundColor]")
        self.cek(bag, 'tombol tema kembali ke terang, latar berbeda', t2[0] == 'terang' and t2[1] == 'Ganti ke tema gelap' and t2[2] != t[3], t2)
        ctx.close()

    def bag_asli_akbar390(self):
        bag = 'asli_akbar390'
        for tema in ('terang', 'gelap'):
            ctx, page, mon, D = self.buka_asli(bag, 'akbar', 390, tema)
            if D is None:
                ctx.close()
                continue
            self.umum(bag, 'akbar 390 %s' % tema, page, mon, 390)
            s, D = self.potret(page)
            self.cek(bag, 'akbar 390 %s: data-tema sesuai' % tema, s['tema'] == tema, s['tema'])
            self.data(bag, 'akbar 390 %s' % tema, s, D)
            self.layar(page, 'akbar-390-%s' % tema)
            ctx.close()

    def akbar_sezaman(self, page):
        """akbar.json dari host dengan dibuat_pada SAMA dengan ringkasan yang sedang dirender halaman V."""
        for _ in range(6):
            A = self.fx.baca('akbar')
            self.samarkan(A)
            if tunggu(page, '(t) => !!window.__rk && window.__rk.dibuat_pada === t', 8, A['dibuat_pada']):
                s, D = self.potret(page)
                if D['dibuat_pada'] == A['dibuat_pada']:
                    return s, D, A
        s, D = self.potret(page)
        return s, D, None

    def bag_asli_v(self, v):
        bag = 'asli_' + v
        for lebar in (1366, 390):
            ctx, page, mon, D = self.buka_asli(bag, v, lebar, 'terang')
            if D is None:
                ctx.close()
                continue
            self.umum(bag, '%s %d' % (v, lebar), page, mon, lebar)
            s, D, A = self.akbar_sezaman(page)
            self.cek(bag, '%s %d: akbar.json sezaman ditemukan (dibuat_pada %s)' % (v, lebar, D['dibuat_pada']), A is not None)
            self.data(bag, '%s %d' % (v, lebar), s, D)
            if A is not None:
                lain = [m for m in A['misi'] if (m['pemberi_id'] or 'akbar') != v]
                idx = set(re.findall(r'\bT-\d{3,}\b', s['teks'] + s['html']))
                self.cek(bag, '%s %d: tidak ada id misi orang lain di DOM (teks + atribut; %d misi lain di akbar.json sezaman)' % (v, lebar, len(lain)),
                         idx <= {m['id'] for m in D['misi']} and not any(m['id'] in idx for m in lain), sorted(idx))
                self.cek(bag, '%s %d: tidak ada judul misi orang lain di DOM' % (v, lebar), not any(m['judul'] and m['judul'] in s['teks'] + s['html'] for m in lain))
                self.cek(bag, '%s %d: misi di berkas V = misi akbar sezaman berpemberi %s' % (v, lebar, v),
                         sorted(m['id'] for m in D['misi']) == sorted(m['id'] for m in A['misi'] if m['pemberi_id'] == v))
            if not D['misi']:  # keadaan kosong yang benar (data asli V tanpa misi)
                k = ev(page, "() => { const t = s => { const e = document.querySelector(s); return e ? e.textContent.replace(/\\s+/g, ' ').trim() : null; };"
                             " return [t('#missions .empty'), t('#h-detail'), t('#detail .empty'), t('#events .empty'), !!document.querySelector('#doneCard') && document.querySelector('#doneCard').hidden]; }")
                harap_k = ['Tidak ada misi aktif.', 'Pilih misi', 'Klik misi di daftar atau agen di peta kantor.',
                           'Belum ada peristiwa hari ini.' if not D['riwayat_hari_ini'] else None, True]
                self.cek(bag, '%s %d: keadaan kosong (pesan misi/detail/peristiwa, kartu selesai tersembunyi)' % (v, lebar),
                         [x for x, h in zip(k, harap_k) if h is not None] == [h for h in harap_k if h is not None], k)
                chips = {x['id']: x for r in s['rooms'] for x in r['chips']}
                self.cek(bag, '%s %d: chip agen non-Ajeng = sibuk/bebas sesuai keadaan (C7)' % (v, lebar),
                         all(a['keadaan'] in ('sibuk', 'bebas') for a in D['agen'])
                         and all((chips.get(a['id']) or {}).get('teks') == a['keadaan'] for a in D['agen'] if a['id'] != D.get('koordinator')),
                         [(a['id'], a['keadaan'], (chips.get(a['id']) or {}).get('teks')) for a in D['agen']])
            self.layar(page, '%s-%d-terang' % (v, lebar))
            if lebar == 1366:
                for m in D['misi']:
                    if self.klik(bag, '%s baris misi %s' % (v, m['id']), page, '[data-task="%s"].m-row' % m['id'], 200):
                        s, D2 = self.potret(page)
                        if misi_id(D2, m['id']):
                            self.detail(bag, v, s, D2, m['id'])
                self.chip_meta(bag, v, page, lambda: self.potret(page))  # KR-2
                self.klik(bag, '%s tombol Keluar' % v, page, 'form[action="/logout"] button[type=submit]', 0)
                ok = tunggu(page, "() => location.pathname === '/login'", 10)
                r1 = ctx.request.get(self.base + '/', max_redirects=0)
                r2 = ctx.request.get(self.base + '/events', max_redirects=0)
                self.cek(bag, '%s: Keluar -> /login, sesi berakhir (GET / 303 ke /login, /events 401)' % v,
                         ok and r1.status == 303 and r1.headers.get('location') == '/login' and r2.status == 401, (ok, r1.status, r2.status))
                self.state.pop(v, None)
            ctx.close()

    def bag_asli_dicky(self):
        self.bag_asli_v('dicky')

    def bag_asli_jati(self):
        self.bag_asli_v('jati')

    # ---- gladi rollback I4
    LAMA = r"""() => { const q = s => document.querySelector(s), qa = s => [...document.querySelectorAll(s)];
      const n = x => x == null ? null : x.replace(/\s+/g, ' ').trim();
      return {tugas: qa('#tugas-isi .tugas > li').length, tugasKosong: n(q('#tugas-isi > .kosong') && q('#tugas-isi > .kosong').textContent),
        tugasJml: n(q('#tugas-jml') && q('#tugas-jml').textContent), tugasTeks: n(q('#tugas-isi') ? q('#tugas-isi').innerText : ''),
        grup: qa('#riwayat-isi .grup').length, rwItem: qa('#riwayat-isi .grup ol > li').length,
        rwKosong: n(q('#riwayat-isi > .kosong') && q('#riwayat-isi > .kosong').textContent), rwJml: n(q('#riwayat-jml') && q('#riwayat-jml').textContent),
        rwTeks: n(q('#riwayat-isi') ? q('#riwayat-isi').innerText : ''), agen: qa('#tim-isi button.simpul.agen').length,
        penonton: n(q('#penonton') && q('#penonton').textContent), koneksi: n(q('#k-teks') && q('#k-teks').textContent),
        banner: q('#banner') && !q('#banner').hidden ? n(q('#banner').textContent) : null, judulHal: document.title,
        rk: window.__rk, teks: document.body.innerText};
    }"""

    def bag_gladi_lama_ui(self):
        """I4(1): image UI lama (:pra-kantor-agen-20261024) + ringkasan generator BARU -> UI lama tampil normal (A1)."""
        bag = 'gladi_lama_ui'
        for akun in ('akbar', 'dicky'):
            self.masuk(akun, judul=None)
            if akun not in self.state:
                continue
            ctx, page, mon = self.konteks(1366, self.state[akun], 'terang')
            page.goto(self.base + '/', wait_until='load')
            ok = tunggu(page, "() => window.__nrk > 0 && !!document.querySelector('#tim-isi *')", 15)
            page.wait_for_timeout(600)
            self.cek(bag, '%s UI lama: data SSE (generator baru) dirender' % akun, ok)
            self.umum(bag, '%s UI lama 1366' % akun, page, mon, 1366, penuh=False)
            L = ev(page, self.LAMA)
            D = L['rk'] or {}
            self.samarkan(D)
            T, R = D.get('tugas_aktif') or [], D.get('riwayat_hari_ini') or []
            self.cek(bag, '%s UI lama: ringkasan baru memuat field tambahan (misi/ringkasan) dan tetap dipakai' % akun, 'misi' in D and 'ringkasan' in D, sorted(D)[:12])
            self.cek(bag, '%s UI lama: pohon tim %d agen' % (akun, len(D.get('agen') or [])), L['agen'] == len(D.get('agen') or []), L['agen'])
            self.cek(bag, '%s UI lama: daftar tugas %d baris (= tugas_aktif)%s' % (akun, len(T), '' if T else ' / pesan kosong'),
                     L['tugas'] == len(T) and (T or L['tugasKosong'] == 'Tidak ada tugas aktif.'), (L['tugas'], L['tugasKosong'], L['tugasJml']))
            self.cek(bag, '%s UI lama: judul tugas tampil' % akun, all((t.get('judul') or '') in (L['tugasTeks'] or '') for t in T))
            self.cek(bag, '%s UI lama: riwayat %s' % (akun, ('%d grup/%d baris dari %d peristiwa' % (L['grup'], L['rwItem'], len(R))) if R else 'kosong + pesan'),
                     (1 <= L['rwItem'] <= len(R)) if R else bool(L['rwKosong']), (L['grup'], L['rwItem'], L['rwKosong'], L['rwJml']))
            self.cek(bag, '%s UI lama: tanpa banner galat/basi, koneksi tersambung' % akun, L['banner'] is None, (L['banner'], L['koneksi']))
            self.cek(bag, '%s UI lama: tanpa teks undefined/NaN/[object' % akun, not re.search(r'undefined|NaN|\[object', L['teks']))
            self.layar(page, 'gladi1-ui-lama-%s-1366' % akun)
            ctx.close()

    def bag_gladi_skema_lama(self):
        """I4(2): image UI BARU + ringkasan skema lama (tar backup 10.51) -> UI baru tidak rusak, misi kosong = keadaan kosong."""
        bag = 'gladi_skema_lama'
        for akun in ('akbar', 'dicky'):
            self.masuk(akun)
            if akun not in self.state:
                continue
            ctx, page, mon = self.konteks(1366, self.state[akun], 'terang')
            page.goto(self.base + '/', wait_until='load')
            ok = tunggu(page, '() => window.__nrk > 0', 15)
            page.wait_for_timeout(1200)
            s = self.umum(bag, '%s skema lama 1366' % akun, page, mon, 1366)
            s, D = self.potret(page)
            D = D or {}
            self.cek(bag, '%s skema lama: data diterima, berkas tanpa misi/ringkasan (skema lama)' % akun, ok and 'misi' not in D and 'ringkasan' not in D, sorted(D)[:12])
            k = ev(page, "() => { const t = s => { const e = document.querySelector(s); return e ? e.textContent.replace(/\\s+/g, ' ').trim() : null; };"
                         " return [t('#missions .empty'), t('#h-detail'), !!document.querySelector('#doneCard') && document.querySelector('#doneCard').hidden]; }")
            self.cek(bag, '%s skema lama: misi kosong ditampilkan sebagai keadaan kosong' % akun, k == ['Tidak ada misi aktif.', 'Pilih misi', True], k)
            he, n = harap_events(D)
            self.cek(bag, '%s skema lama: peristiwa = riwayat_hari_ini lama (%d)' % (akun, n), s['events'] == he and s['eventCount'] == '%d hari ini' % n, (s['events'][:2], s['eventCount']))
            self.cek(bag, '%s skema lama: chip = jumlah agen (%d)' % (akun, len(D.get('agen') or [])), sum(len(r['chips']) for r in s['rooms']) == len(D.get('agen') or []),
                     [(r['nama'], len(r['chips'])) for r in s['rooms']])
            self.cek(bag, '%s skema lama: tanpa teks undefined/NaN/[object' % akun, not re.search(r'undefined|NaN|\[object', s['teks']), s['summary'])
            self.cek(bag, '%s skema lama: banner = Data basi (berkas statis 10.51) atau kosong' % akun, s['banner'] is None or s['banner'].startswith('Data basi'), s['banner'])
            self.layar(page, 'gladi2-skema-lama-%s-1366' % akun)
            ctx.close()


def tunnel(a):
    ip, port = a.base.split('//', 1)[1].split(':')
    p = subprocess.Popen(SSH + ['-o', 'ExitOnForwardFailure=yes', '-N', '-L', '%s:%s:127.0.0.1:%s' % (ip, port, port), HOST],
                         stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    for _ in range(50):
        try:
            socket.create_connection((ip, int(port)), timeout=1).close()
            return p
        except OSError:
            if p.poll() is not None:
                raise Galat('tunnel mati: %s' % p.stderr.read()[:200])
            time.sleep(0.2)
    p.kill()
    raise Galat('tunnel tidak siap')


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--base', default='http://10.249.1.2:24131')
    ap.add_argument('--host-dir', default='/data/agent-dashboard/tmp/test/kantor-agen/alfa-uji/ringkasan')
    ap.add_argument('--pembangun', help='wajib untuk mode fixture')
    ap.add_argument('--asli', help='mode data asli: folder ringkasan di host (dibaca saja; tanpa fixture)')
    ap.add_argument('--sinyal', help='berkas lokal yang ditulis saat uji SSE asli mulai menunggu')
    ap.add_argument('--batas-sse', type=int, default=60)
    ap.add_argument('--pw-dir', required=True)
    ap.add_argument('--layar', required=True)
    ap.add_argument('--keluaran')
    ap.add_argument('--bagian', help='bawaan: masuk,akbar,akbar390,dicky,jati,basi (fixture) / masuk,asli_akbar,asli_akbar390,asli_dicky,asli_jati (--asli)')
    ap.add_argument('--ganti', action='append', help='/aset/app.js=BERKAS: sajikan isi BERKAS untuk path itu (uji mutasi)')
    a = ap.parse_args()
    a.base = a.base.rstrip('/')
    if not a.asli and not a.pembangun:
        ap.error('--pembangun wajib tanpa --asli')
    if not a.bagian:
        a.bagian = 'masuk,asli_akbar,asli_akbar390,asli_dicky,asli_jati' if a.asli else 'masuk,akbar,akbar390,dicky,jati,basi'
    os.makedirs(a.layar, exist_ok=True)
    mulai = time.strftime('%Y-%m-%d %H:%M:%S %z')
    try:
        from patchright.sync_api import sync_playwright
    except Exception as e:  # noqa: BLE001
        print('GALAT patchright: %s' % e)
        return 2
    tn = tunnel(a)
    fx = Asli(a.asli) if a.asli else Fixture(a.pembangun, a.host_dir)
    u = None
    try:
        with sync_playwright() as p:
            br = p.chromium.launch(channel='chromium', headless=True)
            u = Uji(a, br, fx)
            for bag in a.bagian.split(','):
                if bag == 'basi':
                    continue
                try:
                    getattr(u, 'bag_' + bag)()
                except Exception as e:  # noqa: BLE001
                    u.cek(bag, 'bagian %s selesai tanpa pengecualian' % bag, False, '%s: %s' % (type(e).__name__, u.aman(str(e))[:300]))
            br.close()
    finally:
        fx.tutup()
        try:
            fx.kembalikan()
        except Exception:  # noqa: BLE001
            pass
        tn.kill()
    H = u.hasil if u else []
    lulus = sum(x['ok'] for x in H)
    for x in H:
        print('%s %-8s %-90s %s' % ('LULUS' if x['ok'] else 'GAGAL', x['bagian'], u.aman(x['nama'])[:200], '' if x['ok'] else u.aman(json.dumps(x['ket'], ensure_ascii=False, default=str))[:400]))
    print('lulus=%d gagal=%d' % (lulus, len(H) - lulus))
    if a.keluaran:
        with open(a.keluaran, 'w', encoding='utf-8') as f:
            f.write(u.aman(json.dumps({'mulai': mulai, 'selesai': time.strftime('%Y-%m-%d %H:%M:%S %z'), 'base': a.base, 'bagian': a.bagian,
                                       'ganti': a.ganti, 'lulus': lulus, 'gagal': len(H) - lulus, 'cek': H}, ensure_ascii=False, indent=1, default=str)))
    return 0 if H and lulus == len(H) else 1


if __name__ == '__main__':
    sys.exit(main())
