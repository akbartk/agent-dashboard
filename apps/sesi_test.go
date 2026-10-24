package main

import (
	"context"
	"testing"
	"time"
)

func TestSesiTakAktif12Jam(t *testing.T) {
	t.Run("aktivitas memperpanjang", func(t *testing.T) {
		l := baruLingkungan(t)
		l.setAkun("satu", pwAwal, false)
		tok := l.masuk("satu", pwAwal)
		for i := 0; i < 3; i++ {
			l.jam.Maju(11*time.Hour + 59*time.Minute)
			harapKode(t, l.req("GET", "/", opsi{cookie: tok}), 200)
		}
		l.jam.Maju(12*time.Hour + time.Second)
		harapAlih(t, l.req("GET", "/", opsi{cookie: tok}), "/login")
		if l.app.sesi.jumlah() != 0 {
			t.Fatalf("sesi kedaluwarsa harus dibuang, tersisa %d", l.app.sesi.jumlah())
		}
	})
	t.Run("12 jam lewat sedikit tanpa aktivitas", func(t *testing.T) {
		l := baruLingkungan(t)
		l.setAkun("satu", pwAwal, false)
		tok := l.masuk("satu", pwAwal)
		l.jam.Maju(11*time.Hour + 59*time.Minute + 59*time.Second)
		harapKode(t, l.req("GET", "/ganti-password", opsi{cookie: tok}), 200)
		l.jam.Maju(12*time.Hour + time.Second)
		harapAlih(t, l.req("GET", "/ganti-password", opsi{cookie: tok}), "/login")
		ev := l.req("GET", "/events", opsi{cookie: tok, batas: 50 * time.Millisecond})
		harapKode(t, ev, 401)
	})
	t.Run("POST ikut dihitung aktif", func(t *testing.T) {
		l := baruLingkungan(t)
		l.setAkun("satu", pwAwal, false)
		tok := l.masuk("satu", pwAwal)
		l.jam.Maju(11 * time.Hour)
		harapKode(t, l.req("POST", "/ganti-password", opsi{cookie: tok, form: gantiForm("a", "b")}), 400)
		l.jam.Maju(11 * time.Hour)
		harapKode(t, l.req("GET", "/", opsi{cookie: tok}), 200)
	})
}

func TestSesiMutlak7Hari(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	tok := l.masuk("satu", pwAwal)
	// aktif terus tiap 10 jam sampai 160 jam (6 hari 16 jam)
	for i := 0; i < 16; i++ {
		l.jam.Maju(10 * time.Hour)
		harapKode(t, l.req("GET", "/", opsi{cookie: tok}), 200)
	}
	l.jam.Maju(7 * time.Hour) // 167 jam < 7 hari
	harapKode(t, l.req("GET", "/", opsi{cookie: tok}), 200)
	l.jam.Maju(2 * time.Hour) // 169 jam > 7 hari, padahal baru 2 jam tak aktif
	harapAlih(t, l.req("GET", "/", opsi{cookie: tok}), "/login")
	if l.app.sesi.jumlah() != 0 {
		t.Fatal("sesi lewat batas mutlak harus dibuang")
	}
}

func TestSesiSambunganEventsBaruMemperpanjang(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	tok := l.masuk("satu", pwAwal)
	l.jam.Maju(11 * time.Hour)
	harapKode(t, l.req("GET", "/events", opsi{cookie: tok, batas: 50 * time.Millisecond}), 200)
	l.jam.Maju(11 * time.Hour) // 22 jam sejak login, 11 jam sejak /events
	harapKode(t, l.req("GET", "/", opsi{cookie: tok}), 200)
}

func TestSesiBersihkan(t *testing.T) {
	l := baruLingkungan(t)
	s1 := l.app.sesi.buat("satu", false)
	s2 := l.app.sesi.buat("dua", false)
	l.setAkun("dua", pwAwal, false)
	l.jam.Maju(11 * time.Hour)
	harapKode(t, l.req("GET", "/", opsi{cookie: s2}), 200) // s2 aktif
	l.jam.Maju(2 * time.Hour)                              // s1 tak aktif 13 jam; s2 2 jam
	l.app.Bersihkan()
	if n := l.app.sesi.jumlah(); n != 1 {
		t.Fatalf("sesi tersisa = %d, ingin 1", n)
	}
	harapAlih(t, l.req("GET", "/", opsi{cookie: s1}), "/login")
	harapKode(t, l.req("GET", "/", opsi{cookie: s2}), 200)
}

func TestSesiPembersihanBerkala(t *testing.T) {
	l := baruLingkungan(t, func(c *Config) { c.jedaBersih = 20 * time.Millisecond })
	l.app.sesi.buat("satu", false)
	l.app.sesi.buat("dua", false)
	if n := l.app.sesi.jumlah(); n != 2 {
		t.Fatalf("sesi awal = %d, ingin 2", n)
	}
	l.jam.Maju(13 * time.Hour)
	ctx, cancel := context.WithCancel(context.Background())
	defer cancel()
	selesai := make(chan struct{})
	go func() {
		l.app.Jalankan(ctx)
		close(selesai)
	}()
	if !cekSampai(2*time.Second, func() bool { return l.app.sesi.jumlah() == 0 }) {
		t.Fatalf("pembersihan berkala tidak membuang sesi kedaluwarsa (tersisa %d)", l.app.sesi.jumlah())
	}
	cancel()
	select {
	case <-selesai:
	case <-time.After(2 * time.Second):
		t.Fatal("Jalankan tidak berhenti saat context selesai")
	}
}
