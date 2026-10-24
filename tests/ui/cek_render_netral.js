#!/usr/bin/env node
/* cek_render_netral.js - uji render app.js tanpa peramban (stub DOM, data netral). Memeriksa aturan KONTRAK §4:
   warna avatar t-<indeks mod 10> dari urutan [koordinator, agen, orang]; panel pemilik hanya bila penonton = pemilik;
   daftar pemberi = orang selain pemilik; perlakuan khusus koordinator dari D.koordinator; kunci baru hilang = tidak crash.
   Pakai: node tests/ui/cek_render_netral.js apps/web/app.js   -> keluar 0 bila gagal=0. Hanya stdlib Node. */
'use strict';
const fs = require('fs');
const vm = require('vm');

const berkas = process.argv[2] || 'apps/web/app.js';
const sumber = fs.readFileSync(berkas, 'utf8');
const HASIL = [];
const cek = (nama, ok, ket) => HASIL.push([!!ok, nama, ok ? '' : ' [' + String(ket).slice(0, 300) + ']']);

function buatElemen(id, dok) {
  const dasar = {
    id, dataset: {}, style: {}, children: [], hidden: false, textContent: '', scrollTop: 0, _html: '', dihapus: false,
    classList: { toggle() {}, add() {}, remove() {}, contains() { return false; } },
    setAttribute() {}, addEventListener() {}, removeEventListener() {}, querySelector() { return null; }, querySelectorAll() { return []; },
    closest() { return null; }, focus() {}, appendChild() {}, scrollIntoView() {},
    remove() { this.dihapus = true; if (dok.peta.get(this.id) === this) { dok.peta.delete(this.id); } },
    prepend(anak) { dok.peta.set(anak.id, anak); },
    set innerHTML(v) { this._html = String(v); },
    get innerHTML() { return this._html; },
  };
  return dasar;
}

function jalankan(payload) {
  const dok = { peta: new Map(), dibuat: [] };
  const ambil = id => {
    if (id === 'owner') { return dok.peta.get('owner') || null; }
    if (!dok.peta.has(id)) { dok.peta.set(id, buatElemen(id, dok)); }
    return dok.peta.get(id);
  };
  const dokumen = {
    getElementById: ambil, createElement: () => { const e = buatElemen('', dok); dok.dibuat.push(e); const asli = e.setAttribute; e.setAttribute = (k, v) => { if (k === 'id') { e.id = v; } return asli(); }; return e; },
    querySelector: () => buatElemen('q', dok), querySelectorAll: () => [], addEventListener() {}, activeElement: null,
    documentElement: { dataset: {} },
  };
  const es = { dengar: {} };
  class EventSourceUji { constructor() { es.contoh = this; this.readyState = 1; } addEventListener(n, f) { es.dengar[n] = f; } close() {} }
  const galat = [];
  const konteks = vm.createContext({
    document: dokumen, window: { addEventListener() {} }, performance, Date, JSON, Math, Map, Set, Promise, Number, String, Array, Object,
    setInterval() { return 0; }, setTimeout() { return 0; }, clearTimeout() {}, localStorage: { setItem() {}, getItem() { return null; } },
    location: { assign() {} }, fetch: () => Promise.resolve({ ok: true, status: 200 }), EventSource: EventSourceUji, console,
  });
  try {
    vm.runInContext(sumber, konteks, { filename: berkas });
    es.dengar.ringkasan({ data: JSON.stringify({ waktu_server: payload.dibuat_pada, data: payload }) });
  } catch (e) { galat.push(String(e && e.stack || e)); }
  return { ambil, dok, galat };
}

const agen = (id, nama, ruang) => ({ id, nama, peran: 'Peran ' + nama, ruang, keadaan: 'bebas', status: 'bebas', misi_aktif: [] });
function dasar(ubah) {
  const D = {
    versi_skema: '1', penonton: 'pemilik', cakupan: 'semua', dibuat_pada: '2026-10-25T10:00:00+07:00', galat: [], peringatan: [],
    pemilik: 'pemilik', koordinator: 'koord',
    orang: [{ id: 'pemilik', nama: 'Pemilik Uji', peran: 'Pemilik tim', induk: [] }, { id: 'satu', nama: 'Orang Satu', peran: 'Anggota', induk: [] },
      { id: 'dua', nama: 'Orang Dua', peran: 'Anggota', induk: [] }],
    agen: [agen('agen-b', 'Agen B', 'teknik'), agen('koord', 'Koord', 'koordinasi')],
    misi: [], tugas_aktif: [], riwayat_hari_ini: [],
    ringkasan: { agen: { bekerja: 0, menunggu: 0, bebas: 2, sibuk: 0 }, misi: { aktif: 0, selesai_hari_ini: 0 }, subagen_aktif: 0 },
  };
  if (ubah) { ubah(D); }
  return D;
}
const kelasDi = (html, teks) => { const i = html.indexOf(teks); return i < 0 ? null : (html.slice(Math.max(0, i - 400), i).match(/class="av[^"]*"/g) || []).pop(); };

// 1. data lengkap: warna dari urutan [koord, agen-b, pemilik, satu, dua]
{
  const r = jalankan(dasar());
  cek('tanpa galat saat render', r.galat.length === 0, r.galat.join(' | '));
  const peta = r.ambil('map').innerHTML, saya = r.ambil('me').innerHTML, pemilik = r.ambil('owner');
  cek('chip koordinator memakai t-0', /class="av t-0"[^>]*>K<\/span><span><strong>Koord/.test(peta), peta.slice(0, 400));
  cek('chip agen kedua memakai t-1', /class="av t-1"[^>]*>A<\/span><span><strong>Agen B/.test(peta));
  cek('header penonton (pemilik) memakai t-2', /class="av t-2"/.test(saya), saya);
  cek('chip koordinator: teks khusus koordinator ("memantau 0 misi")', /memantau 0 misi/.test(peta));
  cek('panel pemilik dirender', !!pemilik && /id="h-owner">Pemilik Uji</.test(pemilik.innerHTML), pemilik && pemilik.innerHTML.slice(0, 300));
  const p = pemilik ? pemilik.innerHTML : '';
  cek('panel pemilik: peran dari D.orang + nama koordinator dari D.koordinator', /<small>Pemilik tim · memberi arahan lewat Koord<\/small>/.test(p), p.slice(0, 400));
  cek('panel pemilik: pemberi = orang selain pemilik (2 baris, urutan D.orang)', (p.match(/class="giver"/g) || []).length === 2 && p.indexOf('Orang Satu') < p.indexOf('Orang Dua')
    && !/class="giver"[^]*Pemilik Uji/.test(p.slice(p.indexOf('givers'))), p.slice(p.indexOf('givers')));
  cek('pemberi memakai warna t-3 dan t-4', kelasDi(p, '<strong>Orang Satu') === 'class="av sm t-3"' && kelasDi(p, '<strong>Orang Dua') === 'class="av sm t-4"', [kelasDi(p, '<strong>Orang Satu'), kelasDi(p, '<strong>Orang Dua')]);
}
// 2. penonton bukan pemilik: tanpa panel pemilik
{
  const r = jalankan(dasar(D => { D.penonton = 'satu'; D.cakupan = 'order-sendiri'; }));
  cek('penonton ≠ pemilik: tanpa panel pemilik', r.galat.length === 0 && r.ambil('owner') === null, r.galat.join(' | '));
  cek('penonton ≠ pemilik: header memakai t-3', /class="av t-3"/.test(r.ambil('me').innerHTML));
}
// 3. kunci baru tidak ada: tidak crash, tanpa panel pemilik, tanpa perlakuan khusus koordinator
{
  const r = jalankan(dasar(D => { delete D.pemilik; delete D.koordinator; }));
  const peta = r.ambil('map').innerHTML;
  cek('tanpa pemilik/koordinator: tidak crash, tanpa panel pemilik', r.galat.length === 0 && r.ambil('owner') === null, r.galat.join(' | '));
  cek('tanpa koordinator: tidak ada teks khusus koordinator', !/memantau/.test(peta), peta.slice(0, 300));
  cek('tanpa koordinator: warna mulai dari agen pertama (t-0)', /class="av t-0"[^>]*>A<\/span><span><strong>Agen B/.test(peta));
}
// 4. pemilik ada tetapi koordinator tidak: panel tanpa "memberi arahan lewat"
{
  const r = jalankan(dasar(D => { delete D.koordinator; }));
  const p = r.ambil('owner') ? r.ambil('owner').innerHTML : '';
  cek('pemilik tanpa koordinator: panel dirender tanpa "lewat"', r.galat.length === 0 && /<small>Pemilik tim<\/small>/.test(p), p.slice(0, 300));
}
// 5. lebih dari 10 id: indeks mod 10, id di luar urutan tanpa kelas warna
{
  const r = jalankan(dasar(D => { for (let i = 0; i < 10; i++) { D.agen.push(agen('x' + i, 'X' + i, 'lain')); } }));
  const peta = r.ambil('map').innerHTML;
  // urutan: koord 0, agen-b 1, x0..x9 = 2..11 -> x8 = 10 mod 10 = t-0, x9 = t-1
  cek('indeks ke-10 kembali ke t-0 (x8)', /class="av t-0"[^>]*>X<\/span><span><strong>X8/.test(peta));
  cek('indeks ke-11 = t-1 (x9)', /class="av t-1"[^>]*>X<\/span><span><strong>X9/.test(peta));
}
// 6. id penonton di luar urutan (tidak ada di orang/agen): tanpa kelas warna, tetap tidak crash
{
  const r = jalankan(dasar(D => { D.penonton = 'asing'; }));
  cek('penonton tak dikenal: tanpa kelas warna di header', r.galat.length === 0 && !/ t-\d/.test(r.ambil('me').innerHTML), r.ambil('me').innerHTML);
}
// 7. sumber app.js tidak lagi punya daftar id tetap
cek('app.js tanpa konstanta WARNA berisi id', !/const WARNA\b/.test(sumber));

let gagal = 0;
for (const [ok, nama, ket] of HASIL) { console.log((ok ? 'LULUS ' : 'GAGAL ') + nama + ket); if (!ok) { gagal++; } }
console.log('lulus=' + (HASIL.length - gagal) + ' gagal=' + gagal);
process.exit(gagal ? 1 : 0);
