package main

import (
	"encoding/base64"
	"net/http"
	"net/url"
	"os"
	"strconv"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"
)

const pesanSalah = "Akun atau password salah."

func TestLogin(t *testing.T) {
	tabel := []struct {
		nama, akun, pw string
		kode           int
		lokasi         string
		pesan          string
	}{
		{"benar", "satu", pwAwal, http.StatusSeeOther, "/", ""},
		{"password salah", "satu", "salah-salah-salah", http.StatusUnauthorized, "", pesanSalah},
		{"akun tidak dikenal", "dua", pwAwal, http.StatusUnauthorized, "", pesanSalah},
		{"akun dan password kosong", "", "", http.StatusUnauthorized, "", pesanSalah},
		{"huruf besar pada akun diterima", "SATU", pwAwal, http.StatusSeeOther, "/", ""},
	}
	for _, tc := range tabel {
		tc := tc
		t.Run(tc.nama, func(t *testing.T) {
			l := baruLingkungan(t)
			l.setAkun("satu", pwAwal, false)
			rec := l.login(tc.akun, tc.pw, opsi{})
			if rec.Code != tc.kode {
				t.Fatalf("status = %d, ingin %d", rec.Code, tc.kode)
			}
			if tc.lokasi != "" {
				harapAlih(t, rec, tc.lokasi)
				if tokenDari(rec) == "" {
					t.Fatal("tidak ada cookie sesi")
				}
				return
			}
			harapMemuat(t, rec, tc.pesan)
			if len(rec.Result().Cookies()) != 0 {
				t.Fatal("login gagal tidak boleh mengirim cookie")
			}
		})
	}
}

func TestLoginPesanGagalSamaUntukAkunTakDikenal(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	a := l.login("satu", "salah-salah-salah", opsi{})
	b := l.login("zzz", "salah-salah-salah", opsi{})
	if a.Code != 401 || b.Code != 401 {
		t.Fatalf("status = %d dan %d, ingin 401 keduanya", a.Code, b.Code)
	}
	sa := strings.ReplaceAll(a.Body.String(), "satu", "X")
	sb := strings.ReplaceAll(b.Body.String(), "zzz", "X")
	if sa != sb {
		t.Fatalf("badan berbeda antara akun ada dan tidak ada:\n%s\n---\n%s", sa, sb)
	}
	if !strings.HasPrefix(a.Header().Get("Content-Type"), "text/html") {
		t.Fatalf("Content-Type = %q", a.Header().Get("Content-Type"))
	}
}

func TestLoginBcryptPalsuUntukAkunTakDikenal(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	tabel := []struct {
		nama, akun, pw string
		harap          int32
	}{
		{"akun ada, password salah", "satu", "salah-salah-salah", 1},
		{"akun tak dikenal", "dua", pwAwal, 1},
		{"akun ada, password benar", "satu", pwAwal, 1},
	}
	for _, tc := range tabel {
		sebelum := l.banding.Load()
		l.login(tc.akun, tc.pw, opsi{ip: "203.0.113.9:1"}) // IP berbeda agar tidak saling menahan
		if d := l.banding.Load() - sebelum; d != tc.harap {
			t.Errorf("%s: jumlah bcrypt compare = %d, ingin %d", tc.nama, d, tc.harap)
		}
	}
	// berkas akun.json belum ada sama sekali: tetap satu compare palsu
	l2 := baruLingkungan(t)
	l2.login("satu", pwAwal, opsi{})
	if n := l2.banding.Load(); n != 1 {
		t.Errorf("tanpa akun.json: bcrypt compare = %d, ingin 1", n)
	}
}

func TestLoginMembacaAkunTiapKali(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	if rec := l.login("dua", "Dua-Password-1", opsi{}); rec.Code != 401 {
		t.Fatalf("dua belum ada: status = %d", rec.Code)
	}
	l.setAkun("dua", "Dua-Password-1", false) // seperti `akun tambah` dari proses lain
	harapAlih(t, l.login("dua", "Dua-Password-1", opsi{ip: ipLain}), "/")
	l.setAkun("dua", "Dua-Password-2", false) // seperti `akun reset`
	if rec := l.login("dua", "Dua-Password-1", opsi{ip: ipLain}); rec.Code != 401 {
		t.Fatalf("password lama masih berlaku: %d", rec.Code)
	}
	harapAlih(t, l.login("dua", "Dua-Password-2", opsi{ip: ipLain}), "/")
}

func TestLoginCookieSesi(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	rec := l.login("satu", pwAwal, opsi{})
	harapAlih(t, rec, "/")
	sc := rec.Header().Values("Set-Cookie")
	if len(sc) != 1 {
		t.Fatalf("Set-Cookie = %v, ingin tepat satu", sc)
	}
	if strings.Contains(sc[0], "Secure") {
		t.Fatalf("cookie tidak boleh Secure (HTTP polos, debt ADR-003): %s", sc[0])
	}
	c := rec.Result().Cookies()[0]
	if c.Name != "sesi" || c.Path != "/" || !c.HttpOnly || c.SameSite != http.SameSiteStrictMode || c.MaxAge != 7*24*3600 {
		t.Fatalf("atribut cookie salah: %s", sc[0])
	}
	raw, err := base64.RawURLEncoding.DecodeString(strings.TrimRight(c.Value, "="))
	if err != nil || len(raw) != 32 {
		t.Fatalf("token bukan base64url dari 32 byte (len=%d err=%v): %q", len(raw), err, c.Value)
	}
	tok2 := l.masuk("satu", pwAwal)
	if tok2 == c.Value {
		t.Fatal("dua login menghasilkan token sama")
	}
	if l.app.sesi.jumlah() != 2 {
		t.Fatalf("jumlah sesi = %d, ingin 2", l.app.sesi.jumlah())
	}
}

func TestLoginBodyDibatasi4KB(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	rec := l.login("satu", strings.Repeat("a", 5000), opsi{})
	if rec.Code != http.StatusRequestEntityTooLarge {
		t.Fatalf("status = %d, ingin 413", rec.Code)
	}
	if len(rec.Result().Cookies()) != 0 || l.banding.Load() != 0 {
		t.Fatal("body kelewat besar tidak boleh diproses")
	}
}

func TestLoginPesanDisaringHTML(t *testing.T) {
	l := baruLingkungan(t)
	rec := l.login(`"><script>alert(1)</script>`, "x", opsi{})
	harapKode(t, rec, 401)
	if strings.Contains(rec.Body.String(), "<script>alert(1)</script>") {
		t.Fatal("isian akun dipantulkan tanpa escape (XSS)")
	}
	harapMemuat(t, rec, "&lt;script&gt;")
}

func TestHalamanLogin(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	l.setAkun("dua", pwAwal, true)
	rec := l.req("GET", "/login", opsi{})
	harapKode(t, rec, 200)
	if !strings.HasPrefix(rec.Header().Get("Content-Type"), "text/html") {
		t.Fatalf("Content-Type = %q", rec.Header().Get("Content-Type"))
	}
	for _, s := range []string{`action="/login"`, `name="akun"`, `name="password"`} {
		harapMemuat(t, rec, s)
	}
	if strings.Contains(rec.Body.String(), pesanSalah) {
		t.Fatal("halaman awal tidak boleh memuat pesan galat")
	}
	// sesi sah tanpa wajib_ganti -> ke /
	tok := l.masuk("satu", pwAwal)
	harapAlih(t, l.req("GET", "/login", opsi{cookie: tok}), "/")
	// sesi wajib_ganti tetap melihat halaman login
	tokD := l.masuk("dua", pwAwal)
	harapKode(t, l.req("GET", "/login", opsi{cookie: tokD}), 200)
	// cookie palsu
	harapKode(t, l.req("GET", "/login", opsi{cookie: "palsu"}), 200)
}

func TestBerandaDanHalamanGanti(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	harapAlih(t, l.req("GET", "/", opsi{}), "/login")
	harapAlih(t, l.req("GET", "/", opsi{cookie: "palsu"}), "/login")
	harapAlih(t, l.req("GET", "/ganti-password", opsi{}), "/login")
	tok := l.masuk("satu", pwAwal)
	rec := l.req("GET", "/", opsi{cookie: tok})
	harapKode(t, rec, 200)
	if !strings.HasPrefix(rec.Header().Get("Content-Type"), "text/html") {
		t.Fatalf("Content-Type = %q", rec.Header().Get("Content-Type"))
	}
	harapMemuat(t, rec, "/logout")
	rec = l.req("GET", "/ganti-password", opsi{cookie: tok})
	harapKode(t, rec, 200)
	for _, s := range []string{`action="/ganti-password"`, `name="password_baru"`, `name="password_ulang"`} {
		harapMemuat(t, rec, s)
	}
}

func TestAlurWajibGanti(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, true)
	rec := l.login("satu", pwAwal, opsi{})
	harapAlih(t, rec, "/ganti-password")
	tok := tokenDari(rec)

	harapAlih(t, l.req("GET", "/", opsi{cookie: tok}), "/ganti-password")
	ev := l.req("GET", "/events", opsi{cookie: tok, batas: 100 * time.Millisecond})
	harapKode(t, ev, 401)
	if ev.Header().Get("Location") != "" {
		t.Fatal("/events tidak boleh mengalihkan")
	}
	harapKode(t, l.req("GET", "/ganti-password", opsi{cookie: tok}), 200)

	rec = l.req("POST", "/ganti-password", opsi{cookie: tok, form: gantiForm("PasswordBaru-2026", "PasswordBaru-2026")})
	harapAlih(t, rec, "/")
	harapKode(t, l.req("GET", "/", opsi{cookie: tok}), 200)
	ev = l.req("GET", "/events", opsi{cookie: tok, batas: 100 * time.Millisecond})
	harapKode(t, ev, 200)
}

func TestAturanPasswordBaru(t *testing.T) {
	tabel := []struct{ nama, baru, ulang, pesan string }{
		{"tidak sama", "PasswordBaru-2026", "PasswordBaru-2027", "Password baru tidak sama dengan ulangan."},
		{"tidak sama didahulukan dari terlalu pendek", "pendek", "lain", "Password baru tidak sama dengan ulangan."},
		{"tidak sama didahulukan dari terlalu panjang", strings.Repeat("a", 80), strings.Repeat("a", 79), "Password baru tidak sama dengan ulangan."},
		{"11 karakter", "abcdefghijk", "abcdefghijk", "Password minimal 12 karakter."},
		{"11 rune multibyte tetap pendek", strings.Repeat("é", 11), strings.Repeat("é", 11), "Password minimal 12 karakter."},
		{"kosong", "", "", "Password minimal 12 karakter."},
		{"73 byte", strings.Repeat("a", 73), strings.Repeat("a", 73), "Password maksimal 72 byte."},
		{"37 rune multibyte = 74 byte", strings.Repeat("é", 37), strings.Repeat("é", 37), "Password maksimal 72 byte."},
		{"sama dengan password saat ini", pwAwal, pwAwal, "Password baru harus berbeda dari password awal."},
	}
	for _, tc := range tabel {
		tc := tc
		t.Run(tc.nama, func(t *testing.T) {
			l := baruLingkungan(t)
			l.setAkun("satu", pwAwal, true)
			tok := l.masuk("satu", pwAwal)
			sebelum, _ := os.ReadFile(l.berkasAkun)
			rec := l.req("POST", "/ganti-password", opsi{cookie: tok, form: gantiForm(tc.baru, tc.ulang)})
			harapKode(t, rec, 400)
			harapMemuat(t, rec, tc.pesan)
			sesudah, _ := os.ReadFile(l.berkasAkun)
			if string(sebelum) != string(sesudah) {
				t.Fatal("akun.json berubah padahal ditolak")
			}
			harapAlih(t, l.req("GET", "/", opsi{cookie: tok}), "/ganti-password")
		})
	}
}

func TestGantiPasswordBerhasil(t *testing.T) {
	tabel := []struct{ nama, baru string }{
		{"12 karakter", "abcdefghijkl"},
		{"12 rune multibyte (24 byte)", strings.Repeat("é", 12)},
		{"tepat 72 byte", strings.Repeat("b", 72)},
		{"spasi dan simbol", "kata sandi baru !"},
	}
	for _, tc := range tabel {
		tc := tc
		t.Run(tc.nama, func(t *testing.T) {
			l := baruLingkungan(t)
			l.setAkun("satu", pwAwal, true)
			l.setAkun("dua", pwAwal, true)
			lain := bacaBerkasUji(t, l.berkasAkun).Akun["dua"]
			tok := l.masuk("satu", pwAwal)
			l.jam.Maju(time.Minute)
			rec := l.req("POST", "/ganti-password", opsi{cookie: tok, form: gantiForm(tc.baru, tc.baru)})
			harapAlih(t, rec, "/")

			b := bacaBerkasUji(t, l.berkasAkun)
			e := b.Akun["satu"]
			if e.WajibGanti {
				t.Fatal("wajib_ganti harus false")
			}
			if e.DiubahPada != "2026-10-16T08:01:00+07:00" {
				t.Fatalf("diubah_pada = %q", e.DiubahPada)
			}
			if err := bcrypt.CompareHashAndPassword([]byte(e.Hash), []byte(tc.baru)); err != nil {
				t.Fatalf("hash baru tidak cocok dengan password baru: %v", err)
			}
			if bcrypt.CompareHashAndPassword([]byte(e.Hash), []byte(pwAwal)) == nil {
				t.Fatal("hash masih cocok dengan password lama")
			}
			if b.Akun["dua"] != lain {
				t.Fatal("akun lain ikut berubah")
			}
			if fi, _ := os.Stat(l.berkasAkun); fi.Mode().Perm() != 0o600 {
				t.Fatalf("mode akun.json = %o", fi.Mode().Perm())
			}
			harapKode(t, l.req("GET", "/", opsi{cookie: tok}), 200)
			harapAlih(t, l.req("GET", "/login", opsi{cookie: tok}), "/")
			// login ulang: password lama gagal, baru berhasil dan tidak wajib ganti
			if rec := l.login("satu", pwAwal, opsi{ip: ipLain}); rec.Code != 401 {
				t.Fatalf("password lama: status %d", rec.Code)
			}
			harapAlih(t, l.login("satu", tc.baru, opsi{ip: ipLain}), "/")
			// mengganti lagi ke password yang sama dengan saat ini ditolak
			rec = l.req("POST", "/ganti-password", opsi{cookie: tok, form: gantiForm(tc.baru, tc.baru)})
			harapKode(t, rec, 400)
			harapMemuat(t, rec, "Password baru harus berbeda dari password awal.")
		})
	}
}

func TestGantiPasswordBiayaBcrypt12(t *testing.T) {
	l := baruLingkungan(t, func(c *Config) { c.biaya = 0 }) // 0 = bawaan produksi
	l.setAkun("satu", pwAwal, true)
	tok := l.masuk("satu", pwAwal)
	harapAlih(t, l.req("POST", "/ganti-password", opsi{cookie: tok, form: gantiForm("PasswordBaru-2026", "PasswordBaru-2026")}), "/")
	e := bacaBerkasUji(t, l.berkasAkun).Akun["satu"]
	if c, _ := bcrypt.Cost([]byte(e.Hash)); c != 12 {
		t.Fatalf("cost = %d, ingin 12", c)
	}
}

func TestGantiPasswordTanpaSesi(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, true)
	sebelum, _ := os.ReadFile(l.berkasAkun)
	harapAlih(t, l.req("POST", "/ganti-password", opsi{form: gantiForm("PasswordBaru-2026", "PasswordBaru-2026")}), "/login")
	harapAlih(t, l.req("POST", "/ganti-password", opsi{cookie: "palsu", form: gantiForm("PasswordBaru-2026", "PasswordBaru-2026")}), "/login")
	sesudah, _ := os.ReadFile(l.berkasAkun)
	if string(sebelum) != string(sesudah) {
		t.Fatal("akun.json berubah tanpa sesi")
	}
}

func TestLogout(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	tok := l.masuk("satu", pwAwal)
	rec := l.req("POST", "/logout", opsi{cookie: tok})
	harapAlih(t, rec, "/login")
	var hapus *http.Cookie
	for _, c := range rec.Result().Cookies() {
		if c.Name == "sesi" {
			hapus = c
		}
	}
	if hapus == nil || hapus.MaxAge >= 0 || hapus.Value != "" {
		t.Fatalf("cookie penghapus tidak benar: %v", rec.Header().Values("Set-Cookie"))
	}
	if !strings.Contains(rec.Header().Get("Set-Cookie"), "Max-Age=0") {
		t.Fatalf("harus Max-Age=0: %s", rec.Header().Get("Set-Cookie"))
	}
	harapAlih(t, l.req("GET", "/", opsi{cookie: tok}), "/login")
	if l.app.sesi.jumlah() != 0 {
		t.Fatalf("sesi masih tersimpan: %d", l.app.sesi.jumlah())
	}
	// tanpa sesi tetap 303 ke /login
	harapAlih(t, l.req("POST", "/logout", opsi{}), "/login")
}

func TestOrigin(t *testing.T) {
	// asal = nilai header Origin (nil = tanpa header; lebih dari satu = header ganda); sfs = header Sec-Fetch-Site.
	// Peramban mengirim Origin asli untuk form POST same-origin bila Referrer-Policy same-origin. Ke alamat HTTP
	// non-loopback (LAN/Tailscale) peramban tidak mengirim Sec-Fetch-* sama sekali (terukur), dan "null"
	// juga dikirim halaman penyerang mana pun (mis. port lain di host yang sama = same-site, SameSite tidak melindungi),
	// jadi "null" ditolak apa pun Sec-Fetch-Site-nya.
	const hostA = "contoh.test:24130"
	const ipB = "198.51.100.20:24130"
	const ipC = "192.0.2.30:24130"
	kasus := []struct {
		nama, host, sfs string
		asal            []string
		ditolak         bool
	}{
		{"nama host", hostA, "", []string{"http://contoh.test:24130"}, false},
		{"ip kedua", ipB, "", []string{"http://198.51.100.20:24130"}, false},
		{"ip ketiga", ipC, "", []string{"http://192.0.2.30:24130"}, false},
		{"absen", hostA, "", nil, false},
		{"absen host bawaan", "", "", nil, false},
		{"cocok host bawaan", "", "", []string{"http://example.com"}, false},
		{"asing", hostA, "", []string{"http://evil.example"}, true},
		{"null", hostA, "", []string{"null"}, true},
		{"null + same-origin", hostA, "same-origin", []string{"null"}, true},
		{"null + cross-site", hostA, "cross-site", []string{"null"}, true},
		{"null + same-site", hostA, "same-site", []string{"null"}, true},
		{"null + none", hostA, "none", []string{"null"}, true},
		{"aplikasi lain di host sama (port lain)", ipB, "", []string{"http://198.51.100.20:4720"}, true},
		{"host lain", ipB, "", []string{"http://contoh.test:24130"}, true},
		{"skema https", hostA, "", []string{"https://contoh.test:24130"}, true},
		{"asing + same-origin palsu", hostA, "same-origin", []string{"http://evil.example"}, true},
		{"dua header Origin (sah + asing)", hostA, "", []string{"http://contoh.test:24130", "http://evil.example"}, true},
		{"dua header Origin (sah + sah)", hostA, "", []string{"http://contoh.test:24130", "http://contoh.test:24130"}, true},
		{"kosong", hostA, "", []string{""}, true},
		{"port berbeda host bawaan", "", "", []string{"http://example.com:81"}, true},
	}
	for _, k := range kasus {
		k := k
		hdr := map[string]string{}
		if k.sfs != "" {
			hdr["Sec-Fetch-Site"] = k.sfs
		}
		o := func(tok string, f url.Values) opsi {
			return opsi{cookie: tok, asal: k.asal, host: k.host, hdr: hdr, form: f}
		}
		t.Run("login/"+k.nama, func(t *testing.T) {
			l := baruLingkungan(t)
			l.setAkun("satu", pwAwal, false)
			rec := l.req("POST", "/login", o("", formLogin("satu", pwAwal)))
			if k.ditolak {
				harapKode(t, rec, 403)
				harapMemuat(t, rec, "Asal permintaan ditolak.")
				if len(rec.Result().Cookies()) != 0 || l.banding.Load() != 0 || l.app.sesi.jumlah() != 0 {
					t.Fatal("login dengan Origin ditolak tidak boleh diproses")
				}
				return
			}
			harapAlih(t, rec, "/")
		})
		t.Run("logout/"+k.nama, func(t *testing.T) {
			l := baruLingkungan(t)
			l.setAkun("satu", pwAwal, false)
			tok := l.masuk("satu", pwAwal)
			rec := l.req("POST", "/logout", o(tok, nil))
			if k.ditolak {
				harapKode(t, rec, 403)
				harapMemuat(t, rec, "Asal permintaan ditolak.")
				if len(rec.Result().Cookies()) != 0 {
					t.Fatal("logout ditolak tidak boleh mengirim cookie penghapus")
				}
				harapKode(t, l.req("GET", "/", opsi{cookie: tok, host: k.host}), 200) // sesi tetap hidup
				return
			}
			harapAlih(t, rec, "/login")
			harapAlih(t, l.req("GET", "/", opsi{cookie: tok, host: k.host}), "/login")
		})
		t.Run("ganti-password/"+k.nama, func(t *testing.T) {
			l := baruLingkungan(t)
			l.setAkun("satu", pwAwal, true)
			tok := l.masuk("satu", pwAwal)
			sebelum, _ := os.ReadFile(l.berkasAkun)
			rec := l.req("POST", "/ganti-password", o(tok, gantiForm("PasswordBaru-2026", "PasswordBaru-2026")))
			if k.ditolak {
				harapKode(t, rec, 403)
				harapMemuat(t, rec, "Asal permintaan ditolak.")
				sesudah, _ := os.ReadFile(l.berkasAkun)
				if string(sebelum) != string(sesudah) {
					t.Fatal("akun.json berubah padahal Origin ditolak")
				}
				// sesi tetap hidup dan masih wajib ganti
				harapAlih(t, l.req("GET", "/", opsi{cookie: tok, host: k.host}), "/ganti-password")
				return
			}
			harapAlih(t, rec, "/")
		})
	}
}

// Penolakan asal menulis tepat satu baris asal_ditolak (origin dan host ter-quote, dipotong <= 80 byte sebelum
// di-quote) tanpa isi form, cookie, atau token; permintaan yang lolos tidak menulis baris asal_ditolak.
func TestAsalDitolakTercatat(t *testing.T) {
	const w = "waktu=2026-10-16T08:00:00+07:00"
	const kanari = "KanariPassword-ORIGIN-77"
	baris := func(t *testing.T, l *lingkungan) []string {
		t.Helper()
		var hasil []string
		for _, b := range strings.Split(strings.TrimSuffix(l.log.String(), "\n"), "\n") {
			if strings.HasPrefix(b, "asal_ditolak ") {
				hasil = append(hasil, b)
			}
		}
		return hasil
	}
	harapSatu := func(t *testing.T, l *lingkungan, ingin string) {
		t.Helper()
		b := baris(t, l)
		if len(b) != 1 || b[0] != ingin {
			t.Fatalf("baris asal_ditolak = %q, ingin tepat [%q]; log:\n%s", b, ingin, l.log.String())
		}
	}

	t.Run("login", func(t *testing.T) {
		l := baruLingkungan(t)
		l.setAkun("satu", pwAwal, false)
		rec := l.req("POST", "/login", opsi{origin: "http://evil.example", host: "contoh.test:24130", form: formLogin("kanariakun", kanari)})
		harapKode(t, rec, 403)
		harapSatu(t, l, "asal_ditolak "+w+` ip=192.0.2.1 origin="http://evil.example" host="contoh.test:24130"`)
		for _, terlarang := range []string{kanari, "kanariakun"} {
			if strings.Contains(l.log.String(), terlarang) {
				t.Fatalf("log memuat nilai form %q:\n%s", terlarang, l.log.String())
			}
		}
	})
	t.Run("logout null + same-origin", func(t *testing.T) {
		l := baruLingkungan(t)
		l.setAkun("satu", pwAwal, false)
		tok := l.masuk("satu", pwAwal)
		rec := l.req("POST", "/logout", opsi{cookie: tok, origin: "null", host: "198.51.100.20:24130", ip: ipLain, hdr: map[string]string{"Sec-Fetch-Site": "same-origin"}})
		harapKode(t, rec, 403)
		harapSatu(t, l, "asal_ditolak "+w+` ip=198.51.100.7 origin="null" host="198.51.100.20:24130"`)
		if strings.Contains(l.log.String(), tok) {
			t.Fatal("log memuat token sesi")
		}
	})
	t.Run("ganti-password", func(t *testing.T) {
		l := baruLingkungan(t)
		l.setAkun("satu", pwAwal, true)
		tok := l.masuk("satu", pwAwal)
		rec := l.req("POST", "/ganti-password", opsi{cookie: tok, origin: "http://198.51.100.20:4720", host: "198.51.100.20:24130", form: gantiForm(kanari, kanari)})
		harapKode(t, rec, 403)
		harapSatu(t, l, "asal_ditolak "+w+` ip=192.0.2.1 origin="http://198.51.100.20:4720" host="198.51.100.20:24130"`)
		if strings.Contains(l.log.String(), kanari) || strings.Contains(l.log.String(), tok) {
			t.Fatalf("log memuat password/token:\n%s", l.log.String())
		}
	})
	t.Run("injeksi baris dan kutip", func(t *testing.T) {
		l := baruLingkungan(t)
		jahat := "http://x\"\nlogin waktu=x akun=satu ip=1.1.1.1 hasil=berhasil"
		rec := l.req("POST", "/login", opsi{origin: jahat, host: "a\"b\nc", form: formLogin("satu", kanari)})
		harapKode(t, rec, 403)
		semua := strings.Split(strings.TrimSuffix(l.log.String(), "\n"), "\n")
		if len(semua) != 1 {
			t.Fatalf("satu penolakan harus tepat 1 baris log, dapat %d:\n%s", len(semua), l.log.String())
		}
		harapSatu(t, l, "asal_ditolak "+w+" ip=192.0.2.1 origin="+strconv.Quote(jahat)+" host="+strconv.Quote("a\"b\nc"))
	})
	t.Run("dipotong 80 byte", func(t *testing.T) {
		l := baruLingkungan(t)
		panjang := "http://" + strings.Repeat("a", 200) + ".example"
		hostPanjang := strings.Repeat("h", 120) + ":24130"
		harapKode(t, l.req("POST", "/login", opsi{origin: panjang, host: hostPanjang, form: formLogin("satu", kanari)}), 403)
		harapSatu(t, l, "asal_ditolak "+w+" ip=192.0.2.1 origin="+strconv.Quote(panjang[:80])+" host="+strconv.Quote(hostPanjang[:80]))
	})
	t.Run("header Origin ganda", func(t *testing.T) {
		l := baruLingkungan(t)
		harapKode(t, l.req("POST", "/login", opsi{asal: []string{"http://contoh.test:24130", "http://evil.example"}, host: "contoh.test:24130", form: formLogin("satu", kanari)}), 403)
		if b := baris(t, l); len(b) != 1 {
			t.Fatalf("baris asal_ditolak = %d, ingin 1:\n%s", len(b), l.log.String())
		}
	})
	t.Run("lolos tidak tercatat", func(t *testing.T) {
		l := baruLingkungan(t)
		l.setAkun("satu", pwAwal, false)
		harapAlih(t, l.req("POST", "/login", opsi{origin: "http://contoh.test:24130", host: "contoh.test:24130", form: formLogin("satu", pwAwal)}), "/")
		harapKode(t, l.req("POST", "/login", opsi{form: formLogin("satu", "salah-salah-salah")}), 401)
		if b := baris(t, l); len(b) != 0 {
			t.Fatalf("permintaan sah tidak boleh menulis asal_ditolak: %q", b)
		}
	})
}

func TestJalurDanMetode(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	tok := l.masuk("satu", pwAwal)
	tabel := []struct {
		metode, path string
		kode         int
		allow        string
	}{
		{"GET", "/tidak-ada", 404, ""},
		{"GET", "/index.html", 404, ""},
		{"GET", "/web/index.html", 404, ""},
		{"GET", "/akun.json", 404, ""},
		{"GET", "/login/", 404, ""},
		{"GET", "/events/", 404, ""},
		{"POST", "/", 405, "GET"},
		{"PUT", "/login", 405, ""},
		{"DELETE", "/login", 405, ""},
		{"GET", "/logout", 405, "POST"},
		{"DELETE", "/ganti-password", 405, ""},
		{"POST", "/events", 405, "GET"},
		{"POST", "/aset/app.css", 405, "GET"},
	}
	for _, tc := range tabel {
		rec := l.req(tc.metode, tc.path, opsi{cookie: tok})
		if rec.Code != tc.kode {
			t.Errorf("%s %s: status %d, ingin %d", tc.metode, tc.path, rec.Code, tc.kode)
		}
		if tc.allow != "" && rec.Header().Get("Allow") != tc.allow {
			t.Errorf("%s %s: Allow = %q, ingin %q", tc.metode, tc.path, rec.Header().Get("Allow"), tc.allow)
		}
	}
}
