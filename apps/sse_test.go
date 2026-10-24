package main

import (
	"context"
	"net"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestSSEPeristiwaAwalPenuh(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	l.tulisRingkasan("satu", "{\"versi_skema\": \"1\",\n  \"x\": [1, 2,  3]}\n")
	tok := l.masuk("satu", pwAwal)
	rec := l.req("GET", "/events", opsi{cookie: tok, batas: 150 * time.Millisecond})
	harapKode(t, rec, 200)
	h := rec.Result().Header
	if h.Get("Content-Type") != "text/event-stream" || h.Get("Cache-Control") != "no-store" || h.Get("X-Accel-Buffering") != "no" {
		t.Fatalf("header SSE salah: %v", h)
	}
	ev := parsePeristiwa(rec.Body.String())
	if len(ev) < 2 {
		t.Fatalf("peristiwa = %v, ingin retry lalu ringkasan; badan=%q", ev, rec.Body.String())
	}
	if ev[0].Retry != "2000" || ev[0].Nama != "" {
		t.Fatalf("blok pertama = %+v, ingin hanya `retry: 2000`", ev[0])
	}
	if !strings.HasPrefix(rec.Body.String(), "retry: 2000\n\n") {
		t.Fatalf("badan harus diawali `retry: 2000` + baris kosong: %q", rec.Body.String())
	}
	if ev[1].Nama != "ringkasan" {
		t.Fatalf("peristiwa kedua = %q, ingin ringkasan", ev[1].Nama)
	}
	// waktu jam suntik tetap, data dipadatkan (json.Compact)
	harap := `{"waktu_server":"2026-10-16T08:00:00+07:00","data":{"versi_skema":"1","x":[1,2,3]}}`
	if ev[1].Data != harap {
		t.Fatalf("data =\n%s\nharap\n%s", ev[1].Data, harap)
	}
}

func TestSSEPenontonDariSesiBukanDariKlien(t *testing.T) {
	l := baruLingkungan(t)
	for _, n := range []string{"satu", "dua", "tiga"} {
		l.setAkun(n, pwAwal, false)
		l.tulisRingkasan(n, `{"penonton":"`+n+`"}`)
	}
	srv := l.server()
	tokA := l.masuk("satu", pwAwal)
	tokD := l.masuk("dua", pwAwal)

	tabel := []struct {
		nama, path, tok, harap string
		hdr                    map[string]string
	}{
		{"satu minta dua lewat query", "/events?penonton=dua", tokA, "satu", nil},
		{"satu minta tiga lewat query ganda", "/events?penonton=tiga&penonton=dua", tokA, "satu", nil},
		{"dua minta satu lewat query", "/events?penonton=satu", tokD, "dua", nil},
		{"dua tanpa query", "/events", tokD, "dua", nil},
	}
	for _, tc := range tabel {
		a := bukaAliran(t, srv.URL, tc.path, tc.tok)
		if a.Kode != 200 {
			t.Fatalf("%s: status %d", tc.nama, a.Kode)
		}
		e, ok := a.tunggu("ringkasan", 2*time.Second)
		if !ok {
			t.Fatalf("%s: tidak ada peristiwa ringkasan", tc.nama)
		}
		harap := `{"waktu_server":"2026-10-16T08:00:00+07:00","data":{"penonton":"` + tc.harap + `"}}`
		if e.Data != harap {
			t.Fatalf("%s: data = %s, ingin %s", tc.nama, e.Data, harap)
		}
		a.Tutup()
	}
}

func TestSSEPenontonLewatHeaderDiabaikan(t *testing.T) {
	l := baruLingkungan(t)
	for _, n := range []string{"satu", "dua"} {
		l.setAkun(n, pwAwal, false)
		l.tulisRingkasan(n, `{"penonton":"`+n+`"}`)
	}
	tok := l.masuk("satu", pwAwal)
	rec := l.req("GET", "/events?penonton=dua", opsi{cookie: tok, batas: 150 * time.Millisecond,
		hdr: map[string]string{"X-Penonton": "dua", "X-Forwarded-User": "dua", "Remote-User": "dua"}})
	harapKode(t, rec, 200)
	if !strings.Contains(rec.Body.String(), `"data":{"penonton":"satu"}`) {
		t.Fatalf("data bukan milik sesi: %q", rec.Body.String())
	}
	if strings.Contains(rec.Body.String(), `"penonton":"dua"`) {
		t.Fatal("data dua bocor ke sesi satu")
	}
}

func TestSSETanpaSesiAtauSesiPalsu401(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	l.tulisRingkasan("satu", `{"a":1}`)
	tabel := []struct{ nama, cookie string }{
		{"tanpa cookie", ""},
		{"cookie palsu", "AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA"},
		{"cookie nama akun", "satu"},
	}
	for _, tc := range tabel {
		rec := l.req("GET", "/events?penonton=satu", opsi{cookie: tc.cookie, batas: 100 * time.Millisecond})
		if rec.Code != 401 {
			t.Errorf("%s: status %d, ingin 401", tc.nama, rec.Code)
		}
		if rec.Header().Get("Location") != "" {
			t.Errorf("%s: tidak boleh ada redirect", tc.nama)
		}
		if strings.Contains(rec.Body.String(), `"a":1`) {
			t.Errorf("%s: data bocor", tc.nama)
		}
	}
}

func TestSSEPerubahanBerkasDalamSatuDetik(t *testing.T) {
	// interval bawaan produksi (500 ms)
	l := baruLingkungan(t, func(c *Config) { c.jedaCek = 0; c.jedaDetak = 0 })
	l.setAkun("satu", pwAwal, false)
	l.tulisRingkasan("satu", `{"v":1}`)
	srv := l.server()
	tok := l.masuk("satu", pwAwal)
	a := bukaAliran(t, srv.URL, "/events", tok)
	e, ok := a.tunggu("ringkasan", 2*time.Second)
	if !ok || !strings.Contains(e.Data, `"data":{"v":1}`) {
		t.Fatalf("peristiwa awal: ok=%v %+v", ok, e)
	}
	l.tulisRingkasan("satu", `{"v":2}`)
	mulai := time.Now()
	e, ok = a.tunggu("ringkasan", time.Second)
	if !ok {
		t.Fatalf("tidak ada peristiwa ringkasan baru dalam 1 dtk")
	}
	if !strings.Contains(e.Data, `"data":{"v":2}`) {
		t.Fatalf("data = %s", e.Data)
	}
	if d := time.Since(mulai); d > time.Second {
		t.Fatalf("butuh %v", d)
	}
}

func TestSSETanpaPerubahanTidakMengirimUlang(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	l.tulisRingkasan("satu", `{"v":1}`)
	srv := l.server()
	tok := l.masuk("satu", pwAwal)
	a := bukaAliran(t, srv.URL, "/events", tok)
	if _, ok := a.tunggu("ringkasan", 2*time.Second); !ok {
		t.Fatal("tidak ada peristiwa awal")
	}
	if e, ok := a.tunggu("ringkasan", 400*time.Millisecond); ok {
		t.Fatalf("berkas tidak berubah tapi dikirim ulang: %+v", e)
	}
	// berubah isi namun ukuran sama tetap terdeteksi (mtime/inode)
	time.Sleep(20 * time.Millisecond)
	l.tulisRingkasan("satu", `{"v":2}`)
	if _, ok := a.tunggu("ringkasan", 2*time.Second); !ok {
		t.Fatal("perubahan isi berukuran sama tidak terdeteksi")
	}
}

// Pengganti berkas dengan mtime dan ukuran SAMA tetapi inode berbeda harus terdeteksi.
func TestSSEPergantianInodeDenganMtimeDanUkuranSamaTerdeteksi(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	l.tulisRingkasan("satu", `{"v":1}`)
	path := filepath.Join(l.dirRingkasan, "satu.json")
	lama, err := os.Stat(path)
	if err != nil {
		t.Fatal(err)
	}
	srv := l.server()
	tok := l.masuk("satu", pwAwal)
	a := bukaAliran(t, srv.URL, "/events", tok)
	if e, ok := a.tunggu("ringkasan", 2*time.Second); !ok || !strings.Contains(e.Data, `"v":1`) {
		t.Fatalf("peristiwa awal: ok=%v %+v", ok, e)
	}
	tmp := path + ".tmp"
	if err := os.WriteFile(tmp, []byte(`{"v":2}`), 0o640); err != nil {
		t.Fatal(err)
	}
	if err := os.Chtimes(tmp, lama.ModTime(), lama.ModTime()); err != nil { // mtime disamakan sebelum rename
		t.Fatal(err)
	}
	if err := os.Rename(tmp, path); err != nil {
		t.Fatal(err)
	}
	baru, _ := os.Stat(path)
	if os.SameFile(lama, baru) || !baru.ModTime().Equal(lama.ModTime()) || baru.Size() != lama.Size() {
		t.Fatal("prasyarat uji gagal: inode harus berbeda sementara mtime dan ukuran sama")
	}
	e, ok := a.tunggu("ringkasan", 2*time.Second)
	if !ok || !strings.Contains(e.Data, `"v":2`) {
		t.Fatalf("pergantian inode tidak terdeteksi: ok=%v %+v", ok, e)
	}
}

// Perubahan di tempat (inode sama) terdeteksi lewat salah satu dari mtime atau ukuran saja.
func TestSSEMendeteksiMtimeAtauUkuranTanpaPergantianInode(t *testing.T) {
	kasus := []struct {
		nama string
		ubah func(t *testing.T, path string, lama os.FileInfo)
	}{
		{"hanya mtime berubah", func(t *testing.T, path string, lama os.FileInfo) {
			mt := lama.ModTime().Add(time.Hour)
			if err := os.Chtimes(path, mt, mt); err != nil {
				t.Fatal(err)
			}
		}},
		{"hanya ukuran berubah", func(t *testing.T, path string, lama os.FileInfo) {
			f, err := os.OpenFile(path, os.O_WRONLY|os.O_APPEND, 0)
			if err != nil {
				t.Fatal(err)
			}
			if _, err := f.WriteString("\n"); err != nil { // JSON tetap sah
				t.Fatal(err)
			}
			f.Close()
			if err := os.Chtimes(path, lama.ModTime(), lama.ModTime()); err != nil {
				t.Fatal(err)
			}
		}},
	}
	for _, k := range kasus {
		k := k
		t.Run(k.nama, func(t *testing.T) {
			l := baruLingkungan(t)
			l.setAkun("satu", pwAwal, false)
			l.tulisRingkasan("satu", `{"v":1}`)
			path := filepath.Join(l.dirRingkasan, "satu.json")
			lama, err := os.Stat(path)
			if err != nil {
				t.Fatal(err)
			}
			srv := l.server()
			a := bukaAliran(t, srv.URL, "/events", l.masuk("satu", pwAwal))
			if _, ok := a.tunggu("ringkasan", 2*time.Second); !ok {
				t.Fatal("tidak ada peristiwa awal")
			}
			k.ubah(t, path, lama)
			baru, err := os.Stat(path)
			if err != nil || !os.SameFile(lama, baru) {
				t.Fatalf("prasyarat: inode harus sama (err=%v)", err)
			}
			if _, ok := a.tunggu("ringkasan", 2*time.Second); !ok {
				t.Fatal("perubahan tidak terdeteksi")
			}
		})
	}
}

func TestSSEBerkasTakAdaDanTakSahMenjadiGalat(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	srv := l.server()
	tok := l.masuk("satu", pwAwal)
	a := bukaAliran(t, srv.URL, "/events", tok)

	galat := func(ket string) {
		t.Helper()
		e, ok := a.berikut(2 * time.Second)
		if !ok || e.Nama != "galat" {
			t.Fatalf("%s: peristiwa = %+v ok=%v, ingin galat", ket, e, ok)
		}
		m := jsonDari(t, e.Data)
		ws, _ := m["waktu_server"].(string)
		if m["pesan"] != "Ringkasan tidak tersedia" || !polaISO.MatchString(ws) || len(m) != 2 {
			t.Fatalf("%s: data galat = %s", ket, e.Data)
		}
	}
	galat("berkas tidak ada")
	l.tulisRingkasan("satu", `{bukan json`)
	galat("bukan JSON")
	l.tulisRingkasan("satu", `{"a":1} {"b":2}`)
	galat("dua nilai JSON")
	l.tulisRingkasan("satu", `{"ok":true}`)
	e, ok := a.berikut(2 * time.Second)
	if !ok || e.Nama != "ringkasan" || !strings.Contains(e.Data, `"data":{"ok":true}`) {
		t.Fatalf("setelah berkas sah: %+v ok=%v", e, ok)
	}
	if err := os.Remove(filepath.Join(l.dirRingkasan, "satu.json")); err != nil {
		t.Fatal(err)
	}
	galat("berkas dihapus")
}

func TestSSEDetak(t *testing.T) {
	l := baruLingkungan(t, func(c *Config) { c.jedaDetak = 30 * time.Millisecond })
	l.setAkun("satu", pwAwal, false)
	srv := l.server()
	tok := l.masuk("satu", pwAwal)
	a := bukaAliran(t, srv.URL, "/events", tok)
	for i := 0; i < 3; i++ {
		e, ok := a.tunggu("detak", 2*time.Second)
		if !ok {
			t.Fatalf("detak ke-%d tidak datang", i+1)
		}
		m := jsonDari(t, e.Data)
		ws, _ := m["waktu_server"].(string)
		if len(m) != 1 || !polaISO.MatchString(ws) {
			t.Fatalf("data detak = %s", e.Data)
		}
	}
}

func TestSSESesiHabisMengirimPeristiwaLaluMenutup(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	l.tulisRingkasan("satu", `{"v":1}`)
	srv := l.server()
	tok := l.masuk("satu", pwAwal)
	a := bukaAliran(t, srv.URL, "/events", tok)
	if _, ok := a.tunggu("ringkasan", 2*time.Second); !ok {
		t.Fatal("tidak ada peristiwa awal")
	}
	// aliran yang berjalan TIDAK memperpanjang sesi
	l.jam.Maju(6 * time.Hour)
	if _, ok := a.tunggu("detak", 2*time.Second); !ok {
		t.Fatal("aliran harus masih hidup pada 6 jam")
	}
	l.jam.Maju(6*time.Hour + time.Second)
	e, ok := a.tunggu("sesi", 2*time.Second)
	if !ok {
		t.Fatal("tidak ada peristiwa sesi sesudah kedaluwarsa")
	}
	if e.Data != `{"pesan":"habis"}` {
		t.Fatalf("data sesi = %s", e.Data)
	}
	if !a.tertutup(2 * time.Second) {
		t.Fatal("aliran tidak ditutup setelah peristiwa sesi")
	}
}

func TestSSELogoutMenutupAliran(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	srv := l.server()
	tok := l.masuk("satu", pwAwal)
	a := bukaAliran(t, srv.URL, "/events", tok)
	if _, ok := a.berikut(2 * time.Second); !ok {
		t.Fatal("tidak ada peristiwa awal")
	}
	harapAlih(t, l.req("POST", "/logout", opsi{cookie: tok}), "/login")
	e, ok := a.tunggu("sesi", 2*time.Second)
	if !ok || e.Data != `{"pesan":"habis"}` {
		t.Fatalf("peristiwa sesi: %+v ok=%v", e, ok)
	}
	if !a.tertutup(2 * time.Second) {
		t.Fatal("aliran tidak ditutup")
	}
}

func TestSSEBatasLimaAliranPerSesi(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	l.setAkun("dua", pwAwal, false)
	srv := l.server()
	tok := l.masuk("satu", pwAwal)
	tokD := l.masuk("dua", pwAwal)
	var buka []*aliran
	for i := 0; i < 5; i++ {
		a := bukaAliran(t, srv.URL, "/events", tok)
		if a.Kode != 200 {
			t.Fatalf("aliran ke-%d: status %d", i+1, a.Kode)
		}
		buka = append(buka, a)
	}
	enam := bukaAliran(t, srv.URL, "/events", tok)
	if enam.Kode != http.StatusTooManyRequests {
		t.Fatalf("aliran ke-6: status %d, ingin 429", enam.Kode)
	}
	if enam.Header.Get("Content-Security-Policy") != cspUji {
		t.Fatal("respons 429 tanpa header keamanan")
	}
	if a := bukaAliran(t, srv.URL, "/events", tokD); a.Kode != 200 {
		t.Fatalf("sesi lain terkena batas: status %d", a.Kode)
	}
	if n := l.app.sesi.aliranGlobal(); n != 6 {
		t.Fatalf("aliran global = %d, ingin 6", n)
	}
	buka[0].Tutup() // satu ditutup klien -> slot kembali
	ok := cekSampai(3*time.Second, func() bool {
		a := bukaAliran(t, srv.URL, "/events", tok)
		return a.Kode == 200
	})
	if !ok {
		t.Fatal("slot tidak dibebaskan setelah aliran ditutup")
	}
}

func TestSSEBatasSeratusAliranGlobal(t *testing.T) {
	l := baruLingkungan(t, func(c *Config) { c.jedaCek = 100 * time.Millisecond; c.jedaDetak = time.Second })
	srv := l.server()
	var buka []*aliran
	for s := 0; s < 20; s++ {
		tok := l.app.sesi.buat("satu", false)
		for i := 0; i < 5; i++ {
			a := bukaAliran(t, srv.URL, "/events", tok)
			if a.Kode != 200 {
				t.Fatalf("aliran %d: status %d", len(buka)+1, a.Kode)
			}
			buka = append(buka, a)
		}
	}
	if n := l.app.sesi.aliranGlobal(); n != 100 {
		t.Fatalf("aliran global = %d, ingin 100", n)
	}
	tok := l.app.sesi.buat("satu", false)
	if a := bukaAliran(t, srv.URL, "/events", tok); a.Kode != http.StatusTooManyRequests {
		t.Fatalf("aliran ke-101: status %d, ingin 429", a.Kode)
	}
	for _, a := range buka {
		a.Tutup()
	}
	if !cekSampai(5*time.Second, func() bool { return l.app.sesi.aliranGlobal() == 0 }) {
		t.Fatalf("hitungan aliran bocor: %d", l.app.sesi.aliranGlobal())
	}
}

func TestSSEBerhentiSaatKlienPutus(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	srv := l.server()
	tok := l.masuk("satu", pwAwal)
	a := bukaAliran(t, srv.URL, "/events", tok)
	if _, ok := a.berikut(2 * time.Second); !ok {
		t.Fatal("tidak ada peristiwa awal")
	}
	if l.app.sesi.aliranGlobal() != 1 {
		t.Fatalf("aliran global = %d, ingin 1", l.app.sesi.aliranGlobal())
	}
	a.Tutup()
	if !cekSampai(2*time.Second, func() bool { return l.app.sesi.aliranGlobal() == 0 }) {
		t.Fatal("handler tidak berhenti saat context selesai")
	}
}

func TestSSENamaAkunTidakSahTidakMembacaBerkasLuar(t *testing.T) {
	l := baruLingkungan(t)
	rahasia := filepath.Join(filepath.Dir(l.dirRingkasan), "rahasia.json")
	if err := os.WriteFile(rahasia, []byte(`{"bocor":true}`), 0o600); err != nil {
		t.Fatal(err)
	}
	l.setAkun("../rahasia", pwAwal, false) // akun.json disunting tangan
	tok := l.masuk("../rahasia", pwAwal)
	rec := l.req("GET", "/events", opsi{cookie: tok, batas: 100 * time.Millisecond})
	if strings.Contains(rec.Body.String(), "bocor") {
		t.Fatal("berkas di luar direktori ringkasan terbaca")
	}
	if !strings.Contains(rec.Body.String(), "event: galat") {
		t.Fatalf("harus galat: %q", rec.Body.String())
	}
}

func TestSSETahanWriteTimeout(t *testing.T) {
	l := baruLingkungan(t, func(c *Config) { c.jedaDetak = 40 * time.Millisecond })
	l.setAkun("satu", pwAwal, false)
	ctx, batal := context.WithCancel(context.Background())
	defer batal()
	srv := l.app.BuatServer(ctx)
	srv.WriteTimeout = 150 * time.Millisecond
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	go srv.Serve(ln)
	defer srv.Close()
	tok := l.app.sesi.buat("satu", false)
	a := bukaAliran(t, "http://"+ln.Addr().String(), "/events", tok)
	mulai := time.Now()
	n := 0
	for time.Since(mulai) < 500*time.Millisecond {
		if _, ok := a.tunggu("detak", 300*time.Millisecond); !ok {
			t.Fatalf("aliran putus setelah %v dan %d detak (WriteTimeout tidak dimatikan untuk SSE?)", time.Since(mulai), n)
		}
		n++
	}
	if n < 8 {
		t.Fatalf("hanya %d detak dalam 500 ms", n)
	}
}

func TestShutdownMenutupAliranSSE(t *testing.T) {
	l := baruLingkungan(t)
	l.setAkun("satu", pwAwal, false)
	ctx, batal := context.WithCancel(context.Background())
	defer batal()
	srv := l.app.BuatServer(ctx)
	ln, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	go srv.Serve(ln)
	tok := l.app.sesi.buat("satu", false)
	a := bukaAliran(t, "http://"+ln.Addr().String(), "/events", tok)
	if _, ok := a.tunggu("galat", 2*time.Second); !ok {
		t.Fatal("tidak ada peristiwa awal")
	}
	batal() // seperti SIGTERM
	sd, selesai := context.WithTimeout(context.Background(), 5*time.Second)
	defer selesai()
	mulai := time.Now()
	if err := srv.Shutdown(sd); err != nil {
		t.Fatalf("Shutdown: %v (aliran SSE menahan shutdown)", err)
	}
	if d := time.Since(mulai); d > 3*time.Second {
		t.Fatalf("Shutdown butuh %v", d)
	}
	if !a.tertutup(2 * time.Second) {
		t.Fatal("aliran tidak tertutup")
	}
}

func TestBuatServerBatasWaktu(t *testing.T) {
	l := baruLingkungan(t, func(c *Config) { c.Alamat = ":18080" })
	srv := l.app.BuatServer(context.Background())
	if srv.Addr != ":18080" || srv.Handler == nil {
		t.Fatalf("Addr/Handler salah: %q %v", srv.Addr, srv.Handler)
	}
	if srv.ReadHeaderTimeout != 10*time.Second || srv.ReadTimeout != 15*time.Second ||
		srv.WriteTimeout != 30*time.Second || srv.IdleTimeout != 120*time.Second || srv.MaxHeaderBytes != 16<<10 {
		t.Fatalf("batas waktu salah: RHT=%v RT=%v WT=%v IT=%v MHB=%d",
			srv.ReadHeaderTimeout, srv.ReadTimeout, srv.WriteTimeout, srv.IdleTimeout, srv.MaxHeaderBytes)
	}
}
