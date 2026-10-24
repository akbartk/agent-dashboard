package main

import (
	"net/url"
	"regexp"
	"strings"
	"testing"
	"time"
)

func gantiForm(baru, ulang string) url.Values {
	return url.Values{"password_baru": {baru}, "password_ulang": {ulang}}
}

func TestHeaderKeamananDiSemuaRespons(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	tok := l.masuk("satu", pwAwal)
	tabel := []struct {
		nama, metode, path string
		o                  opsi
		kode               int
		cache              string // kosong = tidak diperiksa
	}{
		{"login", "GET", "/login", opsi{}, 200, "no-store"},
		{"beranda", "GET", "/", opsi{cookie: tok}, 200, "no-store"},
		{"beranda tanpa sesi (303)", "GET", "/", opsi{}, 303, "no-store"},
		{"ganti-password", "GET", "/ganti-password", opsi{cookie: tok}, 200, "no-store"},
		{"events", "GET", "/events", opsi{cookie: tok, batas: 100 * time.Millisecond}, 200, "no-store"},
		{"events tanpa sesi (401)", "GET", "/events", opsi{}, 401, "no-store"},
		{"login salah (401)", "POST", "/login", opsi{form: formLogin("satu", "salah")}, 401, "no-store"},
		{"origin asing (403)", "POST", "/login", opsi{origin: "http://evil.example", form: formLogin("satu", "x")}, 403, "no-store"},
		{"404", "GET", "/tidak-ada", opsi{}, 404, "no-store"},
		{"405", "PUT", "/login", opsi{}, 405, "no-store"},
		{"aset css", "GET", "/aset/app.css", opsi{}, 200, "no-cache"},
		{"aset js", "GET", "/aset/app.js", opsi{}, 200, "no-cache"},
		{"aset tema.js", "GET", "/aset/tema.js", opsi{}, 200, "no-cache"},
		{"aset 404", "GET", "/aset/tidak-ada.css", opsi{}, 404, ""},
	}
	for _, tc := range tabel {
		rec := l.req(tc.metode, tc.path, tc.o)
		if rec.Code != tc.kode {
			t.Errorf("%s: status %d, ingin %d", tc.nama, rec.Code, tc.kode)
			continue
		}
		h := rec.Result().Header
		harap := map[string]string{
			"Content-Security-Policy": cspUji,
			"X-Content-Type-Options":  "nosniff",
			"Referrer-Policy":         "same-origin",
			"X-Frame-Options":         "DENY",
		}
		for k, v := range harap {
			if h.Get(k) != v {
				t.Errorf("%s: header %s = %q, ingin %q", tc.nama, k, h.Get(k), v)
			}
		}
		if tc.cache != "" && h.Get("Cache-Control") != tc.cache {
			t.Errorf("%s: Cache-Control = %q, ingin %q", tc.nama, h.Get("Cache-Control"), tc.cache)
		}
	}
}

func TestAsetTipeIsiDanCache(t *testing.T) {
	l := baruLingkungan(t) // tanpa login sama sekali
	tabel := []struct{ path, tipe string }{
		{"/aset/app.css", "text/css"},
		{"/aset/app.js", "text/javascript"},
		{"/aset/tema.js", "text/javascript"},
		{"/aset/font/PublicSans-Regular.woff2", "font/woff2"},
		{"/aset/font/PublicSans-Medium.woff2", "font/woff2"},
		{"/aset/font/PublicSans-SemiBold.woff2", "font/woff2"},
		{"/aset/font/PublicSans-Bold.woff2", "font/woff2"},
		{"/aset/font/PublicSans-OFL.txt", "text/plain"},
	}
	for _, tc := range tabel {
		rec := l.req("GET", tc.path, opsi{})
		if rec.Code != 200 {
			t.Errorf("%s: status %d, ingin 200", tc.path, rec.Code)
			continue
		}
		if ct := rec.Header().Get("Content-Type"); !strings.HasPrefix(ct, tc.tipe) {
			t.Errorf("%s: Content-Type = %q, ingin awalan %q", tc.path, ct, tc.tipe)
		}
		if cc := rec.Header().Get("Cache-Control"); cc != "no-cache" {
			t.Errorf("%s: Cache-Control = %q, ingin no-cache", tc.path, cc)
		}
		if rec.Body.Len() == 0 {
			t.Errorf("%s: badan kosong", tc.path)
		}
	}
}

func TestAsetSelainDaftarDanTraversal404(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	jalur := []string{
		"/aset/../akun.json",
		"/aset/font/../../go.mod",
		"/aset/%2e%2e/akun.json",
		"/aset/font/%2e%2e%2fgo.mod",
		"/aset/font/..%2f..%2fgo.mod",
		"/aset/font/%2e%2e/%2e%2e/go.mod",
		"/aset/",
		"/aset",
		"/aset/font",
		"/aset/font/",
		"/aset/font//PublicSans-Regular.woff2",
		"/aset//app.css",
		"/aset/app.css/",
		"/aset/tema.js/",
		"/aset/font/tema.js",
		"/aset/tidak-ada.css",
		"/aset/font/tidak-ada.woff2",
		"/aset/index.html",
		"/aset/login.html",
		"/aset/ganti.html",
		"/aset/web/index.html",
		"/aset/font/PublicSans-Regular.woff2/..",
	}
	for _, p := range jalur {
		rec := l.req("GET", p, opsi{})
		if rec.Code != 404 {
			t.Errorf("GET %s: status %d, ingin 404", p, rec.Code)
		}
		if strings.Contains(rec.Body.String(), "module agent-dashboard") || strings.Contains(rec.Body.String(), "$2a$") {
			t.Errorf("GET %s: badan memuat isi berkas terlarang", p)
		}
	}
}

// Setiap baris log login berformat tetap, tidak memuat password/token/hash,
// dan nama akun yang tidak sah dicatat (tidak_valid) sehingga tidak bisa menyisipkan baris palsu.
func TestLogTanpaRahasiaDanTanpaInjeksi(t *testing.T) {
	l := baruLingkungan(t)
	const pwBenar = "RahasiaBenar-ABC123"
	const pwSalah = "RahasiaSalah-XYZ789"
	const pwBaru = "RahasiaBaru-QWE456"
	l.setAkun("satu", pwBenar, true)
	hash := bacaBerkasUji(t, l.berkasAkun).Akun["satu"].Hash

	l.login("satu", pwSalah, opsi{})
	l.login("tidakada", pwSalah, opsi{})
	l.login("a\nlogin waktu=x akun=satu ip=1.1.1.1 hasil=berhasil", pwSalah, opsi{})
	l.login("Akun Dengan Spasi", pwSalah, opsi{})
	l.login(strings.Repeat("a", 33), pwSalah, opsi{ip: "[2001:db8::1]:4000"})
	rec := l.login("satu", pwBenar, opsi{ip: ipLain})
	tok := tokenDari(rec)
	l.req("POST", "/ganti-password", opsi{cookie: tok, form: gantiForm(pwBaru, pwBaru+"x")})
	l.req("POST", "/ganti-password", opsi{cookie: tok, form: gantiForm(pwBaru, pwBaru)})
	l.req("POST", "/logout", opsi{cookie: tok})

	log := l.log.String()
	for _, rahasia := range []string{pwBenar, pwSalah, pwBaru, tok, hash, "$2a$", "$2b$"} {
		if rahasia != "" && strings.Contains(log, rahasia) {
			t.Fatalf("log memuat rahasia %q:\n%s", rahasia, log)
		}
	}
	baris := strings.Split(strings.TrimSuffix(log, "\n"), "\n")
	pola := regexp.MustCompile(`^(login waktu=\S+ akun=\S+ ip=\S+ hasil=(berhasil|gagal|ditahan)|ganti_password waktu=\S+ akun=\S+ ip=\S+ hasil=(berhasil|ditolak)|logout waktu=\S+ akun=\S+ ip=\S+)$`)
	for _, b := range baris {
		if !pola.MatchString(b) {
			t.Errorf("baris log tidak sesuai format: %q", b)
		}
	}
	const w = "waktu=2026-10-16T08:00:00+07:00"
	harap := []string{
		"login " + w + " akun=satu ip=192.0.2.1 hasil=gagal",
		"login " + w + " akun=tidakada ip=192.0.2.1 hasil=gagal",
		"login " + w + " akun=(tidak_valid) ip=192.0.2.1 hasil=gagal",
		"login " + w + " akun=(tidak_valid) ip=192.0.2.1 hasil=gagal",
		"login " + w + " akun=(tidak_valid) ip=2001:db8::1 hasil=gagal",
		"login " + w + " akun=satu ip=198.51.100.7 hasil=berhasil",
		"ganti_password " + w + " akun=satu ip=192.0.2.1 hasil=ditolak",
		"ganti_password " + w + " akun=satu ip=192.0.2.1 hasil=berhasil",
		"logout " + w + " akun=satu ip=192.0.2.1",
	}
	if len(baris) != len(harap) {
		t.Fatalf("jumlah baris log = %d, ingin %d (satu baris per kejadian):\n%s", len(baris), len(harap), log)
	}
	for i := range harap {
		if baris[i] != harap[i] {
			t.Errorf("baris %d:\n  dapat  %q\n  harap  %q", i+1, baris[i], harap[i])
		}
	}
}
