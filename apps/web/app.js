/* Kantor Agen: tampilan dari payload SSE (kontrak tampilan, bagian D). Satu-satunya sumber data = aliran /events
   (ringkasan/detak/galat/sesi, perilaku sama dengan v3); tanpa data simulasi. Semua HTML dibangun lewat tag templat h``
   yang meng-escape setiap nilai (D3); DOM hanya diisi di pasang() dari objek Html. */
(function () {
  'use strict';

  const MIN = 60000;
  const BATAS_SUNYI_MS = 30000;
  const BATAS_BASI_MS = 30000;
  const JEDA_MAKS = 30;
  const RUANG = [['koordinasi', 'Ruang koordinasi'], ['riset', 'Riset dan peraturan'], ['qa', 'QA/QC'], ['teknik', 'Ruang teknik'], ['lain', 'Ruang lain']];
  const KELAS = {bekerja: 'work', menunggu: 'wait', bebas: 'idle', sibuk: 'busy'};
  const JUMLAH_WARNA = 10;  // kelas .t-0 … .t-9 di app.css
  let warnaId = new Map();  // id → indeks warna; diisi aturWarna() tiap render dari payload (bukan daftar tetap)
  const PENGGULIR = ['.ins-list', '.done-list', '.d-log'];

  /* ---------- escape (D3) ---------- */
  const ESC = {'&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'};
  function esc(v) { return String(v).replace(/[&<>"']/g, c => ESC[c]); }
  class Html { constructor(s) { this.s = s; } }
  function nilai(v) {
    if (v instanceof Html) { return v.s; }
    if (Array.isArray(v)) { return v.map(nilai).join(''); }
    if (v === null || v === undefined || v === false) { return ''; }
    return esc(v);
  }
  function h(bagian, ...isi) {
    let s = bagian[0];
    isi.forEach((v, i) => { s += nilai(v) + bagian[i + 1]; });
    return new Html(s);
  }
  function pasang(el, html) {
    if (el && html instanceof Html) { el.innerHTML = html.s; }
  }

  /* ---------- util ---------- */
  const $ = id => document.getElementById(id);
  const str = x => typeof x === 'string' ? x : (x == null ? '' : String(x));
  const arr = x => Array.isArray(x) ? x : [];
  const obj = x => x && typeof x === 'object' && !Array.isArray(x);
  const ms = iso => { const t = iso ? Date.parse(iso) : NaN; return isNaN(t) ? null : t; };
  const jam = iso => { const m = /T(\d\d):(\d\d)/.exec(str(iso)); return m ? m[1] + '.' + m[2] : '—'; };
  const jamDetik = iso => { const m = /T(\d\d):(\d\d):(\d\d)/.exec(str(iso)); return m ? m[1] + '.' + m[2] + '.' + m[3] : ''; };
  const mnt = d => Math.max(0, Math.floor(d / MIN)) + ' m';
  const inisial = n => str(n).split(/\s+/).filter(Boolean).slice(0, 2).map(w => w[0]).join('').toUpperCase();

  const s = {
    data: null,            // ringkasan terbaru yang diterima
    tampil: null,          // ringkasan yang sedang dirender (beku selama Jeda)
    dibuat: '', dibuatMs: null,
    serverMs: null, serverDiterima: 0, waktuServer: '',
    pesanTerakhir: performance.now(),
    galatEvent: false, terputus: false,
    jeda: false, stampJeda: '',
    sel: null, selTampil: null, agenSel: null, semua: false, fokusDetail: false,
    kenalEv: null, kenalSub: null,
    banner: null
  };
  // jam server diperkirakan dari waktu_server pesan terakhir + waktu berlalu di klien (sama dengan v3)
  function sekarang() { return s.serverMs !== null ? s.serverMs + (performance.now() - s.serverDiterima) : Date.now(); }
  function sejak(iso) {
    const t = ms(iso);
    return h`<span data-since="${str(iso)}">${t === null ? '—' : mnt(sekarang() - t)}</span>`;
  }
  function durasi(a, b) { const x = ms(a), y = ms(b); return x === null || y === null ? '—' : mnt(y - x); }

  /* ---------- akses data ---------- */
  function orang(D, id) { return arr(D.orang).find(o => obj(o) && o.id === id) || null; }
  function agen(D, id) { return arr(D.agen).find(a => obj(a) && a.id === id) || null; }
  function nama(D, id) { const x = orang(D, id) || agen(D, id); return x && x.nama ? str(x.nama) : str(id); }
  function daftarMisi(D) { return arr(D.misi).filter(m => obj(m) && m.id); }
  function misiDari(D, id) { return daftarMisi(D).find(m => m.id === id) || null; }
  const aktif = m => m.status === 'jalan' || m.status === 'menunggu';
  const subAktif = m => arr(m.subagen).filter(x => obj(x) && !x.selesai).length;
  const judul = m => (m.judul === null || m.judul === undefined || m.judul === '') ? '(tanpa judul)' : str(m.judul);
  const kuota = m => typeof m.spawn_kuota === 'number' ? m.spawn_kuota : '—';
  const jenisMisi = m => m.status === 'jalan' ? 'work' : (m.status === 'menunggu' ? 'wait' : 'done');
  function labelMisi(m) {
    if (m.status === 'jalan') { return 'Langkah ' + (arr(m.langkah).length + 1) + ' dari —'; }
    if (m.status === 'menunggu') { return {'misi-lain': 'Tertahan', review: 'Menunggu review', gantung: 'Gantung'}[m.alasan] || 'Menunggu'; }
    return (m.status === 'selesai' ? 'Selesai ' : 'Berakhir ') + jam(m.selesai);
  }
  function keadaan(a) {
    if (KELAS[a.keadaan]) { return a.keadaan; }
    return {jalan: 'bekerja', menunggu: 'menunggu', sibuk: 'sibuk'}[a.status] || 'bebas';
  }
  const ruangDari = a => RUANG.some(r => r[0] === a.ruang) ? a.ruang : 'lain';
  function misiAktifAgen(D, a) { return arr(a.misi_aktif).map(id => misiDari(D, id)).filter(Boolean); }
  // misi anak yang ditunggu (menunggu_misi, urut data) yang ada di berkas; banner D7 dan callout D9 menyebut semuanya
  function anakMisi(D, m) { return arr(m.menunggu_misi).map(id => misiDari(D, id)).filter(Boolean); }
  // K-2 (koreksi 24 Okt 2026): misi yang dibuka saat chip agen diklik = misi aktif pertama; bila tidak ada, misi non-aktif
  // pelaksana itu dengan `selesai` terbesar (seri: nomor terbesar), dihitung eksplisit; tanpa misi pelaksana → null (panel agen)
  const banding = (x, y) => (x < y ? -1 : (x > y ? 1 : 0));
  function misiAgen(D, id) {
    const a = agen(D, id);
    const m = a ? misiAktifAgen(D, a)[0] : null;
    if (m) { return m; }
    const M = daftarMisi(D).filter(x => x.pelaksana_id === id);
    const sel = M.filter(x => !aktif(x)).sort((x, y) => banding(str(x.selesai), str(y.selesai)) || banding(Number(x.nomor) || 0, Number(y.nomor) || 0));
    return sel.length ? sel[sel.length - 1] : (M[0] || null);
  }
  function av(id, teks, kecil) {
    return h`<span class="av${kecil ? ' sm' : ''}${warnaId.has(id) ? ' t-' + (warnaId.get(id) % JUMLAH_WARNA) : ''}" aria-hidden="true">${teks}</span>`;
  }
  // urutan warna: koordinator, agen lain (urutan D.agen), lalu orang (urutan D.orang); id ganda memakai kemunculan pertama
  function aturWarna(D) {
    const urut = [str(D.koordinator), ...arr(D.agen).filter(obj).map(a => str(a.id)), ...arr(D.orang).filter(obj).map(o => str(o.id))];
    warnaId = new Map();
    urut.forEach(id => { if (id && !warnaId.has(id)) { warnaId.set(id, warnaId.size); } });
  }
  const adaKoordinator = (D, id) => !!D.koordinator && id === D.koordinator;
  const adaPemilik = D => !!D.pemilik && D.penonton === D.pemilik;
  const avAgen = (D, id, kecil) => av(id, nama(D, id).charAt(0), kecil);

  /* ---------- header (D5) ---------- */
  function renderKepala(D) {
    const id = str(D.penonton), nm = nama(D, id);
    pasang($('me'), h`${av(id, inisial(nm))}${nm}`);
    const r = obj(D.ringkasan) ? D.ringkasan : {}, a = obj(r.agen) ? r.agen : {}, m = obj(r.misi) ? r.misi : {};
    const n = v => typeof v === 'number' ? v : '—';
    const order = D.cakupan === 'order-sendiri';
    document.querySelector('.top').dataset.cakupan = order ? 'order-sendiri' : 'semua';  // jarak header (H-4)
    pasang($('summary'), h`<span class="sg"><span class="sg-l">Agen</span> <span><i class="k work"></i><b>${n(a.bekerja)}</b> bekerja</span> <span><i class="k wait"></i><b>${n(a.menunggu)}</b> menunggu</span> <span><i class="k idle"></i><b>${n(a.bebas)}</b> bebas</span>${order ? h` <span><i class="k busy"></i><b>${n(a.sibuk)}</b> sibuk</span>` : ''}</span>
      <span class="sg"><span class="sg-l">Misi</span> <span><b>${n(m.aktif)}</b> aktif</span> <span><b>${n(m.selesai_hari_ini)}</b> selesai hari ini</span></span>
      <span class="sg"><span class="sg-l">Sub-agen</span> <span><b>${n(r.subagen_aktif)}</b> aktif</span></span>`);
    $('legend-sibuk').hidden = !order;
  }
  function aturStamp() {
    let t;
    if (s.terputus) { t = 'Terputus'; } else if (s.jeda) { t = 'Dijeda · ' + (s.stampJeda || '—'); } else { t = s.waktuServer ? 'Langsung · ' + jamDetik(s.waktuServer) : '—'; }
    if ($('stamp').textContent !== t) { $('stamp').textContent = t; }
    $('liveDot').classList.toggle('paused', s.jeda || s.terputus);
  }

  /* ---------- peta kantor (D6) ---------- */
  function teksChip(D, a, M) {
    const m0 = M[0], k = keadaan(a), nsub = M.reduce((x, m) => x + subAktif(m), 0);
    const ekor = nsub ? ' · ' + nsub + ' sub-agen' : '';
    if (adaKoordinator(D, a.id)) {
      const t = arr(D.tugas_aktif).find(x => obj(x) && x.pengerja_id === a.id);
      return h`${t ? 'melayani ' + str(t.pemberi) : 'memantau ' + daftarMisi(D).filter(aktif).length + ' misi'}${ekor}`;
    }
    if (k === 'bekerja') { return m0 ? h`${m0.id} · ${sejak(m0.mulai)}${ekor}` : h`bekerja${ekor}`; }
    if (k === 'menunggu') {
      if (m0 && m0.alasan === 'misi-lain' && arr(m0.menunggu_misi).length) { return h`tunggu ${m0.menunggu_misi[0]}${ekor}`; }
      return h`${m0 && m0.alasan === 'review' ? 'menunggu review' : 'menunggu'}${ekor}`;
    }
    return h`${k}${ekor}`;
  }
  function chip(D, a) {
    const M = misiAktifAgen(D, a), k = keadaan(a), m0 = M[0], nsub = M.reduce((x, m) => x + subAktif(m), 0);
    const label = str(a.nama) + ', ' + str(a.peran) + ', ' + k + (m0 ? ', ' + m0.id : '') + (nsub ? ', ' + nsub + ' sub-agen aktif' : '');
    return h`<button class="chip ${KELAS[k]}" type="button" data-agent="${a.id}" data-key="chip-${a.id}" aria-pressed="${String(s.agenSel ? a.id === s.agenSel : (misiDari(D, s.sel) || {}).pelaksana_id === a.id)}" aria-label="${label}">${avAgen(D, a.id)}<span><strong>${a.nama}</strong><small>${teksChip(D, a, M)}</small></span></button>`;
  }
  function renderPeta(D) {
    const A = arr(D.agen).filter(obj);
    const ruang = RUANG.filter(r => r[0] !== 'lain' || A.some(a => ruangDari(a) === 'lain'));
    pasang($('map'), h`${ruang.map(r => {
      const anggota = A.filter(a => ruangDari(a) === r[0]);
      const sibuk = anggota.filter(a => keadaan(a) !== 'bebas').length;
      return h`<div class="map-room${r[0] === 'teknik' ? ' wide' : ''}"><h3>${r[1]}<span>${sibuk} dari ${anggota.length} sibuk</span></h3><div class="chips">${anggota.map(a => chip(D, a))}</div></div>`;
    })}`);
  }

  /* ---------- banner tertahan (D7; tanpa tombol aksi ke agent) ---------- */
  function renderTahan(D) {
    const L = daftarMisi(D).filter(m => m.status === 'menunggu' && m.alasan === 'misi-lain');
    if (!L.length) { pasang($('alert'), h``); return; }
    const m = L[0], C = anakMisi(D, m);
    pasang($('alert'), h`<div class="alert"><strong>${m.pelaksana} tertahan di ${m.id}${L.length > 1 ? ' (+' + (L.length - 1) + ' lainnya)' : ''}</strong>
      ${C.length ? h`<span>Menunggu ${C.map((c, i) => h`${i ? '; ' : ''}${c.pelaksana} menyelesaikan ${c.id}, sejak ${jam(c.mulai)}. ${c.pelaksana} di langkah ${arr(c.langkah).length + 1} dari —`)}.</span>
      ${C.map(c => h`<button class="link" type="button" data-task="${c.id}" data-key="alert-anak-${c.id}">Buka ${c.id}</button>`)}` : ''}
      <button class="link" type="button" data-task="${m.id}" data-key="alert-open">Buka ${m.id}</button></div>`);
  }

  /* ---------- daftar misi (D8) ---------- */
  function baris(D, m) {
    const k = jenisMisi(m), n = subAktif(m), subs = arr(m.subagen), L = arr(m.langkah).length;
    const cur = m.alasan === 'misi-lain' && arr(m.menunggu_misi).length ? 'menunggu ' + m.menunggu_misi[0] : (str(m.langkah_sekarang) || '—');
    const segs = h`${Array.from({length: L}, () => h`<i class="done"></i>`)}${aktif(m) ? h`<i class="cur"></i>` : ''}`;
    return h`<button class="m-row ${k}" type="button" data-task="${m.id}" data-key="m-${m.id}" aria-pressed="${String(m.id === s.sel)}" aria-label="${m.id + ' ' + judul(m) + ', ' + str(m.pelaksana) + ', ' + labelMisi(m) + (n ? ', ' + n + ' sub-agen aktif' : '')}">
      <span class="row"><span>${m.id} · ${m.pemberi || '—'} · ${jam(m.mulai)}</span><span class="st ${k}">${labelMisi(m)}</span></span>
      <strong>${judul(m)}</strong>
      <span class="who">${avAgen(D, m.pelaksana_id, true)}<span><strong>${m.pelaksana}</strong> · ${cur}</span></span>
      <span class="segs" aria-hidden="true">${segs}</span>
      ${subs.length ? h`<span class="m-subs">${n} sub-agen aktif · ${subs.length} dari ${kuota(m)} spawn</span>` : ''}</button>`;
  }
  function renderMisi(D) {
    const M = daftarMisi(D), akt = M.filter(aktif), sel = M.filter(m => !aktif(m));
    $('missionCount').textContent = akt.length + ' aktif · klik untuk melihat detail';
    pasang($('missions'), akt.length ? h`${akt.map(m => baris(D, m))}` : h`<p class="empty">Tidak ada misi aktif.</p>`);
    // kartu terpisah untuk misi selesai hari ini; disembunyikan bila belum ada
    $('doneCard').hidden = !sel.length;
    pasang($('doneCard'), sel.length ? h`<div class="sec-head"><h2 id="lbl-done">Selesai hari ini</h2><span>${sel.length} misi</span></div>
      <div class="done-list" tabindex="0" role="region" aria-labelledby="lbl-done" data-key="done-list">${sel.map(m => baris(D, m))}</div>` : h``);
  }

  /* ---------- detail misi (D9) ---------- */
  function kursi(m, x) {
    const k = m.id + '|' + x.ke, baru = s.kenalSub && !s.kenalSub.has(k);
    return h`<span class="chair ${x.selesai ? 'done' : 'work'}${baru ? ' new' : ''}">${x.ke}</span>`;
  }
  /* ---------- panel agen tanpa misi di berkas (K-3): hanya field agen[] berkas penonton ini ---------- */
  const LABEL_KEADAAN = {bekerja: 'Bekerja', menunggu: 'Menunggu', bebas: 'Bebas', sibuk: 'Sibuk'};
  const PESAN_KEADAAN = {bebas: 'Belum ada misi hari ini.', sibuk: 'Sedang mengerjakan order lain.',
    bekerja: 'Sedang bekerja di luar misi tercatat.', menunggu: 'Sedang menunggu di luar misi tercatat.'};
  const BULAN = ['Jan', 'Feb', 'Mar', 'Apr', 'Mei', 'Jun', 'Jul', 'Agu', 'Sep', 'Okt', 'Nov', 'Des'];
  function terakhirAktif(D, iso) {
    const m = /^(\d{4}-(\d\d)-(\d\d))T(\d\d):(\d\d)/.exec(str(iso));
    if (!m) { return ''; }
    const hari = str(s.waktuServer || D.dibuat_pada).slice(0, 10);
    return 'Terakhir aktif ' + (m[1] === hari ? '' : Number(m[3]) + ' ' + BULAN[Number(m[2]) - 1] + ' ') + 'pukul ' + m[4] + '.' + m[5];
  }
  function renderAgen(D, a) {
    const k = keadaan(a), ruang = RUANG.find(r => r[0] === ruangDari(a))[1], akhir = a.terakhir_aktif ? terakhirAktif(D, a.terakhir_aktif) : '';
    $('detail').dataset.panel = 'agen:' + a.id;
    pasang($('detail'), h`<header class="d-head"><div><h2 id="h-detail" tabindex="-1">${a.nama}</h2>
        <p class="d-meta">${a.peran && str(a.peran).trim().toLowerCase() !== ruang.trim().toLowerCase() ? str(a.peran) + ' · ' : ''}${ruang}</p></div><span class="a-st"><i class="k ${KELAS[k]}"></i>${LABEL_KEADAAN[k]}</span></header>
      <p class="sub-empty a-pesan">${PESAN_KEADAAN[k]}</p>${akhir ? h`<p class="d-meta">${akhir}</p>` : ''}`);
  }
  function renderDetail(D, segar) {
    const ag = s.agenSel ? agen(D, s.agenSel) : null;
    if (ag) { renderAgen(D, ag); return; }
    const m = misiDari(D, s.sel);
    if (!m) { delete $('detail').dataset.panel; pasang($('detail'), h`<h2 id="h-detail">Pilih misi</h2><p class="empty">Klik misi di daftar atau agen di peta kantor.</p>`); return; }
    $('detail').dataset.panel = 'misi:' + m.id;
    const a = agen(D, m.pelaksana_id) || {}, k = jenisMisi(m), akt = aktif(m), L = arr(m.langkah).filter(obj);
    const steps = L.map((x, i) => h`<li class="done"><span>${jam(x.waktu)}</span><span class="dot"></span><span>${x.label}</span><span class="note">${durasi(i ? L[i - 1].waktu : m.mulai, x.waktu)}</span></li>`);
    if (akt) {
      const dari = L.length ? L[L.length - 1].waktu : m.mulai;
      if (m.status === 'jalan') {
        steps.push(h`<li class="cur"><span>—</span><span class="dot"></span><span>${m.langkah_sekarang || '—'}</span><span class="note">berjalan ${sejak(dari)}</span></li>`);
      } else {
        const nota = m.alasan === 'misi-lain' ? (arr(m.menunggu_misi).length ? 'menunggu ' + m.menunggu_misi[0] : 'menunggu') : (m.alasan === 'review' ? 'menunggu review' : 'gantung');
        steps.push(h`<li class="cur wait"><span>—</span><span class="dot"></span><span>${m.langkah_sekarang || '—'}</span><span class="note">${nota}</span></li>`);
      }
    }
    let subs;
    if (m.subagen === null || m.subagen === undefined) {
      subs = h`<p class="sub-empty">Data sub-agen tidak tersedia.</p>`;
    } else if (!arr(m.subagen).length) {
      subs = h`<p class="sub-empty">Belum ada sub-agen. Saat ${m.pelaksana} men-spawn sub-agen, mereka muncul di sini dengan nomor spawn ke-n.</p>`;
    } else {
      subs = h`${arr(m.subagen).filter(obj).map(x => h`<div class="sub-row ${x.selesai ? 'done' : 'work'}">${kursi(m, x)}<span>Sub-agen ke-${x.ke}</span>
        <small>${x.selesai ? 'selesai ' + jam(x.selesai) : h`bekerja · ${sejak(x.mulai)}`}</small></div>`)}`;
    }
    let note = '';
    const anak = m.status === 'menunggu' && m.alasan === 'misi-lain' ? anakMisi(D, m) : [];
    const penunggu = daftarMisi(D).find(x => aktif(x) && arr(x.menunggu_misi).includes(m.id));
    if (anak.length) {
      note = h`<div class="d-callout"><p>Tertahan: menunggu ${anak.map((c, i) => h`${i ? '; ' : ''}${c.pelaksana} menyelesaikan ${c.id} (${judul(c)}), sudah ${sejak(c.mulai)}`)}.</p>
        <div class="d-acts">${anak.map(c => h`<button class="link" type="button" data-task="${c.id}" data-key="d-open-${c.id}">Buka ${c.id}</button>`)}</div></div>`;
    } else if (penunggu) {
      note = h`<div class="d-callout"><p>${penunggu.pelaksana} menunggu misi ini selesai untuk melanjutkan ${penunggu.id}.</p>
        <div class="d-acts"><button class="link" type="button" data-task="${penunggu.id}" data-key="d-open">Buka ${penunggu.id}</button></div></div>`;
    }
    const evs = arr(D.riwayat_hari_ini).map((r, i) => [r, i]).filter(x => obj(x[0]) && x[0].misi === m.id).reverse();
    const sa = m.subagen === null || m.subagen === undefined ? '—' : h`${subAktif(m)} aktif <small>· ${arr(m.subagen).length} dari ${kuota(m)} spawn</small>`;
    const rantai = arr(m.rantai).map(x => nama(D, x)).join(' → ') || '—';
    pasang($('detail'), h`<header class="d-head"><div><h2 id="h-detail" tabindex="-1">${judul(m)}</h2>
        <p class="d-meta">${m.id} · order dari ${m.pemberi || '—'} pukul ${jam(m.mulai)}</p></div><span class="pill ${k}">${labelMisi(m)}</span></header>
      <dl class="facts">
        <div><dt>Pelaksana</dt><dd>${avAgen(D, m.pelaksana_id, true)}<span>${m.pelaksana} <small>${a.peran || ''}</small></span></dd></div>
        <div><dt>Rantai order</dt><dd>${rantai}</dd></div>
        <div><dt>${akt ? 'Berjalan' : 'Total waktu'}</dt><dd>${akt ? sejak(m.mulai) : durasi(m.mulai, m.selesai)}</dd></div>
        <div><dt>Sub-agen</dt><dd>${sa}</dd></div>
      </dl>
      ${note}
      <div class="d-grid">
        <section class="d-box" aria-label="Langkah"><h3>Langkah<span>${L.length + (akt ? 1 : 0)} dari —</span></h3><ol class="steps">${steps}</ol></section>
        <section class="d-box" aria-label="Sub-agen"><h3>Sub-agen<span>nomor = spawn ke-n</span></h3>${subs}</section>
      </div>
      <section class="d-box"><h3 id="lbl-log">Peristiwa misi ini<span>${evs.length}</span></h3>
        <div class="d-log" tabindex="0" role="region" aria-labelledby="lbl-log" data-key="d-log">${evs.map(x => peristiwa(D, x[0], segar.has(x[1])))}</div></section>`);
  }

  /* ---------- panel pemilik (D10): hanya dirender bila penonton = D.pemilik ---------- */
  function renderPemilik(D) {
    let el = $('owner');
    if (!adaPemilik(D)) { if (el) { el.remove(); } return; }
    if (!el) {
      el = document.createElement('section');
      el.className = 'panel';
      el.id = 'owner';
      el.setAttribute('aria-labelledby', 'h-owner');
      $('lower').prepend(el);
    }
    const hari = str(D.dibuat_pada).slice(0, 10), M = daftarMisi(D);
    const ins = M.filter(m => m.pemberi_id === D.pemilik && str(m.mulai).slice(0, 10) === hari).sort((x, y) => str(y.mulai).localeCompare(str(x.mulai)));
    const pemberi = arr(D.orang).filter(o => obj(o) && o.id !== D.pemilik).map(o => o.id).map(id => {
      const ids = M.filter(m => m.pemberi_id === id && aktif(m)).sort((x, y) => x.nomor - y.nomor).map(m => m.id);
      return h`<div class="giver">${av(id, inisial(nama(D, id)), true)}<strong>${nama(D, id)}</strong><span>${ids.length ? ids.length + ' order aktif · ' + ids.join(', ') : 'tanpa order aktif'}</span></div>`;
    });
    const peran = str((orang(D, D.pemilik) || {}).peran) || 'Pemilik';
    const lewat = D.koordinator ? ' · memberi arahan lewat ' + nama(D, D.koordinator) : '';
    pasang(el, h`<div class="owner-head">${av(D.pemilik, inisial(nama(D, D.pemilik)))}<div><h2 id="h-owner">${nama(D, D.pemilik)}</h2><small>${peran + lewat}</small></div></div>
      <div class="owner-cols"><div><span class="label" id="lbl-ins">Instruksi hari ini · ${ins.length}</span>
        <div class="ins-list" tabindex="0" role="region" aria-labelledby="lbl-ins" data-key="ins-list">${ins.length ? ins.map(m => h`<div class="ins"><time>${jam(m.mulai)}</time><div><span>${judul(m)}</span><small class="${jenisMisi(m)}">${labelMisi(m)}</small></div></div>`) : h`<p class="empty">Tidak ada instruksi hari ini.</p>`}</div></div>
        <div><span class="label">Pemberi order</span><div class="givers">${pemberi}</div></div></div>`);
  }

  /* ---------- peristiwa terbaru (D11) ---------- */
  function peristiwa(D, r, segar) {
    const t = str(r.teks), nm = nama(D, r.pelaku);
    const isi = nm && t.indexOf(nm + ' ') === 0 ? h`<strong>${nm}</strong>${t.slice(nm.length)}` : h`${t}`;
    return h`<div class="ev${segar ? ' fresh' : ''}"><time>${jam(r.waktu)}</time><span>${isi}</span></div>`;
  }
  function renderPeristiwa(D, segar) {
    const list = arr(D.riwayat_hari_ini).map((r, i) => [r, i]).filter(x => obj(x[0])).reverse(), cap = s.semua ? 60 : 8;
    $('eventCount').textContent = list.length + ' hari ini';
    pasang($('events'), list.length ? h`${list.slice(0, cap).map(x => peristiwa(D, x[0], segar.has(x[1])))}${list.length > 8
      ? h`<button class="link more" type="button" data-more data-key="more">${s.semua ? 'Tampilkan lebih sedikit' : 'Tampilkan semua (' + list.length + ')'}</button>` : ''}`
      : h`<p class="empty">Belum ada peristiwa hari ini.</p>`);
  }
  // indeks riwayat yang belum pernah dirender (penanda "baru" + pengumuman pembaca layar)
  function hitungSegar(D) {
    const R = arr(D.riwayat_hari_ini), baru = new Map(), segar = new Set();
    R.forEach((r, i) => {
      if (!obj(r)) { return; }
      const k = [r.waktu, r.pelaku, r.teks, r.misi].map(str).join('|'), n = (baru.get(k) || 0) + 1;
      baru.set(k, n);
      if (s.kenalEv && n > (s.kenalEv.get(k) || 0)) { segar.add(i); }
    });
    s.kenalEv = baru;
    if (segar.size) { $('announce').textContent = str(R[Math.max(...segar)].teks); }
    return segar;
  }

  /* ---------- render ---------- */
  function pilihAwal(D) {
    if (s.agenSel && agen(D, s.agenSel)) { return; }  // K-5: panel agen bertahan antar-pembaruan sampai pengguna memilih lain
    s.agenSel = null;
    if (s.sel && misiDari(D, s.sel)) { return; }
    const M = daftarMisi(D);
    const m = M.find(x => x.status === 'menunggu' && x.alasan === 'misi-lain') || M.find(aktif) || M[0];
    s.sel = m ? m.id : null;
  }
  // "Selesai hari ini" menampilkan tepat dua kartu; sisanya digulir (mockup)
  function pasDone() {
    const box = document.querySelector('.done-list');
    if (!box) { return; }
    const a = box.children[0], b = box.children[1];
    box.style.maxHeight = b ? (b.offsetTop + b.offsetHeight - a.offsetTop) + 'px' : '';
  }
  function render(dataBaru) {
    const D = s.tampil;
    if (!D) { return; }
    const akt = document.activeElement, kunci = akt && akt.dataset ? akt.dataset.key : null;
    const gulir = PENGGULIR.map(q => { const el = document.querySelector(q); return el ? el.scrollTop : 0; });
    const selSebelum = s.selTampil, segar = dataBaru ? hitungSegar(D) : new Set();
    pilihAwal(D);
    aturWarna(D);
    renderKepala(D);
    renderPeta(D);
    renderTahan(D);
    renderMisi(D);
    renderDetail(D, segar);
    renderPemilik(D);
    renderPeristiwa(D, segar);
    if (dataBaru) { s.kenalSub = new Set(daftarMisi(D).flatMap(m => arr(m.subagen).filter(obj).map(x => m.id + '|' + x.ke))); }
    s.selTampil = s.sel;
    pasDone(); // tinggi kotak dulu, baru posisi gulir bisa dipulihkan
    PENGGULIR.forEach((q, i) => { const el = document.querySelector(q); if (el && !(q === '.d-log' && selSebelum !== s.sel)) { el.scrollTop = gulir[i]; } });
    if (s.fokusDetail) {
      const x = $('h-detail');
      if (x) { x.focus(); }
      s.fokusDetail = false;
    } else if (kunci) {
      const x = document.querySelector('[data-key="' + CSS.escape(kunci) + '"]');
      if (x) { x.focus(); }
    }
  }
  function detik() {
    const now = sekarang();
    document.querySelectorAll('[data-since]').forEach(el => {
      const t = ms(el.dataset.since), v = t === null ? '—' : mnt(now - t);
      if (el.textContent !== v) { el.textContent = v; }
    });
    periksa();
  }

  /* ---------- koneksi dan banner (sama dengan v3) ---------- */
  function periksa() {
    const kini = performance.now();
    const galat = s.data ? arr(s.data.galat).map(str).filter(Boolean) : [];
    const umur = (s.dibuatMs !== null && s.serverMs !== null) ? s.serverMs + (kini - s.serverDiterima) - s.dibuatMs : 0;
    let teks = '';
    if (kini - s.pesanTerakhir > BATAS_SUNYI_MS) {
      teks = s.dibuat ? 'Terputus \u2014 data terakhir ' + jamDetik(s.dibuat) + ', menyambung ulang\u2026' : 'Terputus \u2014 belum ada data, menyambung ulang\u2026';
    } else if (s.galatEvent) {
      teks = 'Ringkasan tidak tersedia';
    } else if (umur > BATAS_BASI_MS) {
      teks = 'Data basi \u2014 generator tidak memperbarui sejak ' + jamDetik(s.dibuat);
    } else if (galat.length) {
      teks = 'Galat generator \u2014 ' + galat.join('; ');
    }
    if (teks !== s.banner) {
      s.banner = teks;
      const b = $('banner');
      b.textContent = teks;
      b.hidden = !teks;
    }
  }
  function terimaPesan(d) {
    s.pesanTerakhir = performance.now();
    s.terputus = false;
    const t = d && d.waktu_server ? ms(d.waktu_server) : null;
    if (t !== null) { s.serverMs = t; s.serverDiterima = s.pesanTerakhir; s.waktuServer = str(d.waktu_server); }
    aturStamp();
  }
  function parse(teks) { try { return JSON.parse(teks); } catch (e) { return null; } }
  function onRingkasan(e) {
    const d = parse(e.data);
    terimaPesan(d);
    if (d && obj(d.data)) {
      s.galatEvent = false;
      s.data = d.data;
      s.dibuat = str(d.data.dibuat_pada);
      s.dibuatMs = ms(s.dibuat);
      if (!s.jeda) { s.tampil = s.data; render(true); }
    }
    periksa();
  }
  function onDetak(e) { terimaPesan(parse(e.data)); periksa(); }
  function onGalat(e) { terimaPesan(parse(e.data)); s.galatEvent = true; periksa(); }
  function keLogin() { location.assign('/login'); }

  let jeda = 1, timerUlang = null;
  function jadwalUlang() {
    clearTimeout(timerUlang);
    timerUlang = setTimeout(sambung, jeda * 1000);
    jeda = Math.min(jeda * 2, JEDA_MAKS);
  }
  function periksaSesi() {
    fetch('/', {redirect: 'manual', cache: 'no-store', credentials: 'same-origin'}).then(r => {
      if (r.type === 'opaqueredirect' || r.status === 401) { keLogin(); } else { jadwalUlang(); }
    }).catch(jadwalUlang);
  }
  function sambung() {
    const es = new EventSource('/events');
    es.addEventListener('open', () => { jeda = 1; s.terputus = false; aturStamp(); });
    es.addEventListener('ringkasan', onRingkasan);
    es.addEventListener('detak', onDetak);
    es.addEventListener('galat', onGalat);
    es.addEventListener('sesi', keLogin);
    es.addEventListener('error', () => {
      s.terputus = true;
      aturStamp();
      if (es.readyState === 2) { es.close(); periksaSesi(); }
    });
  }

  /* ---------- interaksi ---------- */
  document.addEventListener('click', e => {
    const el = e.target.closest('[data-task], [data-agent], [data-more]');
    if (!el || !s.tampil) { return; }
    const d = el.dataset;
    if (d.task) {
      s.sel = d.task;
      s.agenSel = null;
      s.fokusDetail = !el.classList.contains('m-row');
    } else if (d.agent) {
      const m = misiAgen(s.tampil, d.agent);  // K-1/K-2: tanpa misi di berkas → panel agen
      s.agenSel = m ? null : d.agent;
      s.sel = m ? m.id : null;
    } else {
      s.semua = !s.semua;
    }
    render(false);
  });
  $('pause').addEventListener('click', () => {
    s.jeda = !s.jeda;
    const label = s.jeda ? 'Lanjutkan pembaruan tampilan' : 'Jeda pembaruan tampilan';  // KR-1: hanya title; nama aksesibel = stamp + .sr-only tetap, status lewat aria-pressed
    $('pause').setAttribute('aria-pressed', String(s.jeda));
    $('pause').title = label;
    if (s.jeda) {
      s.stampJeda = jamDetik(s.waktuServer);
    } else if (s.data && s.data !== s.tampil) {
      s.tampil = s.data;
      render(true);
    }
    aturStamp();
  });
  const akar = document.documentElement;
  function pasangTema() {
    const label = akar.dataset.tema === 'gelap' ? 'Ganti ke tema terang' : 'Ganti ke tema gelap';
    $('theme').setAttribute('aria-label', label);
    $('theme').title = label;
  }
  $('theme').addEventListener('click', () => {
    akar.dataset.tema = akar.dataset.tema === 'gelap' ? 'terang' : 'gelap';
    try { localStorage.setItem('tema', akar.dataset.tema); } catch (e) { /* mode privat: pilihan berlaku untuk halaman ini saja */ }
    pasangTema();
  });
  window.addEventListener('resize', pasDone);
  pasangTema();
  aturStamp();
  setInterval(detik, 1000);
  periksa();
  sambung();
}());
