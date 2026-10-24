/* Tema terang/gelap: dijalankan sinkron di <head> sebelum CSS agar halaman tidak berkedip (CSP melarang skrip inline). */
(function () {
  var t = null;
  try { t = localStorage.getItem('tema'); } catch (e) { t = null; }
  document.documentElement.dataset.tema = t || (matchMedia('(prefers-color-scheme: dark)').matches ? 'gelap' : 'terang');
}());
