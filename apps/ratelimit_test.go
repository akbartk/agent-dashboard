package main

import (
	"fmt"
	"strconv"
	"strings"
	"testing"
	"time"
)

func (l *lingkungan) salah(akun string, ip string) int {
	l.t.Helper()
	rec := l.login(akun, "salah-salah-salah", opsi{ip: ip})
	return rec.Code
}

func TestRateLimitEnamPercobaanDitahan(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	for i := 1; i <= 5; i++ {
		if k := l.salah("satu", ""); k != 401 {
			t.Fatalf("gagal ke-%d: status %d, ingin 401", i, k)
		}
	}
	sebelum := l.banding.Load()
	rec := l.login("satu", pwAwal, opsi{}) // password BENAR tetap ditahan
	harapKode(t, rec, 429)
	if ra := rec.Header().Get("Retry-After"); ra != "1" {
		t.Fatalf("Retry-After = %q, ingin 1", ra)
	}
	harapMemuat(t, rec, "Terlalu banyak percobaan. Coba lagi dalam 1 detik.")
	if l.banding.Load() != sebelum {
		t.Fatal("percobaan yang ditahan tidak boleh memeriksa password")
	}
	if len(rec.Result().Cookies()) != 0 {
		t.Fatal("percobaan yang ditahan tidak boleh membuat sesi")
	}
}

func TestRateLimitJedaEksponensialMaks300(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	for i := 1; i <= 5; i++ {
		if k := l.salah("satu", ""); k != 401 {
			t.Fatalf("gagal ke-%d: status %d", i, k)
		}
	}
	// jeda sesudah gagal ke-5, 6, 7, ... = min(2^(n-5), 300)
	jeda := []int{1, 2, 4, 8, 16, 32, 64, 128, 256, 300, 300, 300}
	for i, s := range jeda {
		gagal := 5 + i
		sebelum := l.banding.Load()
		rec := l.login("satu", pwAwal, opsi{})
		if rec.Code != 429 {
			t.Fatalf("setelah gagal ke-%d: status %d, ingin 429", gagal, rec.Code)
		}
		if ra := rec.Header().Get("Retry-After"); ra != strconv.Itoa(s) {
			t.Fatalf("setelah gagal ke-%d: Retry-After = %q, ingin %d", gagal, ra, s)
		}
		harapMemuat(t, rec, fmt.Sprintf("Terlalu banyak percobaan. Coba lagi dalam %d detik.", s))

		l.jam.Maju(time.Duration(s)*time.Second - 500*time.Millisecond)
		rec = l.login("satu", pwAwal, opsi{})
		harapKode(t, rec, 429)
		if ra := rec.Header().Get("Retry-After"); ra != "1" {
			t.Fatalf("setelah gagal ke-%d, sisa 0,5 dtk: Retry-After = %q, ingin 1", gagal, ra)
		}
		if l.banding.Load() != sebelum {
			t.Fatalf("setelah gagal ke-%d: password diperiksa saat ditahan", gagal)
		}

		l.jam.Maju(600 * time.Millisecond) // jeda lewat
		if k := l.salah("satu", ""); k != 401 {
			t.Fatalf("gagal ke-%d (sesudah jeda): status %d, ingin 401", gagal+1, k)
		}
	}
}

func TestRateLimitTahananTidakDiperpanjangPercobaanDitahan(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	for i := 0; i < 5; i++ {
		l.salah("satu", "")
	}
	for i := 0; i < 10; i++ {
		harapKode(t, l.login("satu", pwAwal, opsi{}), 429)
	}
	l.jam.Maju(1100 * time.Millisecond)
	harapAlih(t, l.login("satu", pwAwal, opsi{}), "/")
}

func TestRateLimitBerhasilMereset(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	for i := 0; i < 5; i++ {
		l.salah("satu", "")
	}
	l.jam.Maju(1100 * time.Millisecond)
	harapAlih(t, l.login("satu", pwAwal, opsi{}), "/")
	// hitungan mulai dari nol: lima gagal lagi masih 401, baru percobaan ke-6 ditahan
	for i := 1; i <= 5; i++ {
		if k := l.salah("satu", ""); k != 401 {
			t.Fatalf("setelah reset, gagal ke-%d: status %d, ingin 401", i, k)
		}
	}
	harapKode(t, l.login("satu", pwAwal, opsi{}), 429)
}

func TestRateLimitKunciAkunDanIP(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	l.setAkun("dua", pwAwal, false)
	for i := 0; i < 5; i++ {
		l.salah("satu", ipBawaan)
	}
	harapKode(t, l.login("satu", pwAwal, opsi{ip: ipBawaan}), 429)

	// IP lain tidak ikut tertahan
	harapAlih(t, l.login("satu", pwAwal, opsi{ip: ipLain}), "/")
	// akun lain dari IP yang sama tidak ikut tertahan
	harapAlih(t, l.login("dua", pwAwal, opsi{ip: ipBawaan}), "/")
	// X-Forwarded-For tidak dipercaya: IP tertahan tetap tertahan, IP lain tidak
	harapKode(t, l.login("satu", pwAwal, opsi{ip: ipBawaan, hdr: map[string]string{"X-Forwarded-For": "203.0.113.77"}}), 429)
	harapAlih(t, l.login("satu", pwAwal, opsi{ip: ipLain, hdr: map[string]string{"X-Forwarded-For": "192.0.2.1"}}), "/")
	// huruf besar/kecil pada akun satu kunci
	harapKode(t, l.login("SATU", pwAwal, opsi{ip: ipBawaan}), 429)
	// IPv6 dengan port dibaca benar
	for i := 0; i < 5; i++ {
		l.salah("satu", "[2001:db8::1]:4000")
	}
	harapKode(t, l.login("satu", pwAwal, opsi{ip: "[2001:db8::1]:9999"}), 429) // port berbeda, IP sama
	harapAlih(t, l.login("satu", pwAwal, opsi{ip: "[2001:db8::2]:4000"}), "/")
}

func TestRateLimitAkunTakDikenalDanKunciDipotong32Byte(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	dasar := strings.Repeat("a", 32)
	for i := 0; i < 5; i++ {
		if k := l.salah(dasar+strconv.Itoa(i), ""); k != 401 { // akun tak dikenal dihitung sama
			t.Fatalf("status %d", k)
		}
	}
	rec := l.login(dasar+"zzz", "apa-saja", opsi{})
	harapKode(t, rec, 429)
	harapMemuat(t, rec, "Terlalu banyak percobaan.")
	// akun yang berbeda di dalam 32 byte pertama tidak tertahan
	if k := l.salah("b"+dasar, ""); k != 401 {
		t.Fatalf("status %d, ingin 401", k)
	}
}

func TestRateLimitPembersihanEntriMenganggur(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	for i := 0; i < 5; i++ {
		l.salah("satu", "")
	}
	if n := l.app.rl.jumlah(); n != 1 {
		t.Fatalf("entri = %d, ingin 1", n)
	}
	l.jam.Maju(59 * time.Minute)
	l.app.Bersihkan()
	if n := l.app.rl.jumlah(); n != 1 {
		t.Fatalf("entri baru menganggur 59 menit sudah dibuang (%d)", n)
	}
	l.jam.Maju(2 * time.Minute)
	l.app.Bersihkan()
	if n := l.app.rl.jumlah(); n != 0 {
		t.Fatalf("entri menganggur > 1 jam harus dibuang, tersisa %d", n)
	}
	// dan akun itu bisa login lagi
	harapAlih(t, l.login("satu", pwAwal, opsi{}), "/")
}

func TestRateLimitPercobaanDitahanTercatatDiLog(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	for i := 0; i < 5; i++ {
		l.salah("satu", "")
	}
	l.login("satu", pwAwal, opsi{})
	if !strings.Contains(l.log.String(), "hasil=ditahan") {
		t.Fatalf("log tidak memuat hasil=ditahan:\n%s", l.log.String())
	}
}
