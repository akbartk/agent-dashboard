package main

import (
	"context"
	"net/http"
	"net/http/cookiejar"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"
)

// Uji ujung ke ujung memakai serve() dengan soket TCP sungguhan di loopback.
func TestServeUjungKeUjung(t *testing.T) {
	dir := t.TempDir()
	ringkasan := filepath.Join(dir, "ringkasan")
	if err := os.MkdirAll(ringkasan, 0o755); err != nil {
		t.Fatal(err)
	}
	akunPath := filepath.Join(dir, "akun.json")
	hash, _ := bcrypt.GenerateFromPassword([]byte(pwAwal), bcrypt.MinCost)
	tulisBerkasUji(t, akunPath, berkasUji{Versi: 1, Akun: map[string]entriUji{
		"satu": {Hash: string(hash), WajibGanti: false, DiubahPada: "2026-10-16T08:00:00+07:00"},
	}})
	if err := os.WriteFile(filepath.Join(ringkasan, "satu.json"), []byte(`{"halo":"dunia"}`), 0o640); err != nil {
		t.Fatal(err)
	}

	ctx, batal := context.WithCancel(context.Background())
	defer batal()
	keluar := &bufAman{}
	galat := &bufAman{}
	kode := make(chan int, 1)
	cfg := Config{Alamat: "127.0.0.1:0", Ringkasan: ringkasan, Akun: akunPath, biaya: bcrypt.MinCost}
	go func() { kode <- serve(ctx, cfg, keluar, galat) }()

	var alamat string
	polaAlamat := regexp.MustCompile(`(?m)^server_mulai waktu=\S+ alamat=(\S+) `)
	if !cekSampai(5*time.Second, func() bool {
		m := polaAlamat.FindStringSubmatch(keluar.String())
		if m != nil {
			alamat = m[1]
		}
		return m != nil
	}) {
		t.Fatalf("baris mulai server tidak muncul; stdout=%q stderr=%q", keluar.String(), galat.String())
	}

	jar, _ := cookiejar.New(nil)
	klien := &http.Client{Jar: jar, CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }}
	base := "http://" + alamat

	resp, err := klien.Get(base + "/")
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != 303 || resp.Header.Get("Location") != "/login" {
		t.Fatalf("GET / tanpa sesi: %d %q", resp.StatusCode, resp.Header.Get("Location"))
	}
	resp, err = klien.PostForm(base+"/login", url.Values{"akun": {"satu"}, "password": {pwAwal}})
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != 303 || resp.Header.Get("Location") != "/" {
		t.Fatalf("POST /login: %d %q", resp.StatusCode, resp.Header.Get("Location"))
	}
	resp, err = klien.Get(base + "/")
	if err != nil {
		t.Fatal(err)
	}
	resp.Body.Close()
	if resp.StatusCode != 200 {
		t.Fatalf("GET / dengan sesi: %d", resp.StatusCode)
	}
	// SSE lewat server sungguhan, memakai cookie dari jar
	u, _ := url.Parse(base)
	var tok string
	for _, c := range jar.Cookies(u) {
		if c.Name == "sesi" {
			tok = c.Value
		}
	}
	if tok == "" {
		t.Fatal("cookie sesi tidak tersimpan di jar")
	}
	a := bukaAliran(t, base, "/events", tok)
	e, ok := a.tunggu("ringkasan", 2*time.Second)
	if !ok || !strings.Contains(e.Data, `"data":{"halo":"dunia"}`) {
		t.Fatalf("peristiwa ringkasan: ok=%v %+v", ok, e)
	}

	// SIGTERM (disimulasikan dengan membatalkan context): berhenti <= 5 dtk dengan kode 0
	batal()
	select {
	case k := <-kode:
		if k != 0 {
			t.Fatalf("kode keluar serve = %d, ingin 0; stderr=%q", k, galat.String())
		}
	case <-time.After(6 * time.Second):
		t.Fatal("serve tidak berhenti dalam 6 dtk setelah context selesai")
	}
	if !a.tertutup(2 * time.Second) {
		t.Fatal("aliran SSE tidak ditutup saat shutdown")
	}
	if strings.Contains(keluar.String()+galat.String(), pwAwal) {
		t.Fatal("password bocor ke log")
	}
}

func TestServeGagalBilaAlamatTidakBisaDipakai(t *testing.T) {
	dir := t.TempDir()
	cfg := Config{Alamat: "bukan-alamat", Ringkasan: dir, Akun: filepath.Join(dir, "akun.json")}
	var keluar, galat bufAman
	k := serve(context.Background(), cfg, &keluar, &galat)
	if k != 1 || galat.String() == "" {
		t.Fatalf("kode = %d stderr=%q, ingin 1 + pesan", k, galat.String())
	}
}
