package main

import (
	"bufio"
	"bytes"
	"context"
	"encoding/json"
	"io"
	"net/http"
	"net/http/httptest"
	"net/url"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"sync"
	"sync/atomic"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"
)

const (
	pwAwal   = "AwalPassword-1"
	ipBawaan = "192.0.2.1:1234"
	ipLain   = "198.51.100.7:5000"
	cspUji   = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"
)

var (
	wibUji  = time.FixedZone("WIB", 7*3600)
	polaISO = regexp.MustCompile(`^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\+07:00$`)
)

// jamUji adalah jam suntik yang bisa dimajukan.
type jamUji struct {
	mu sync.Mutex
	t  time.Time
}

func (j *jamUji) Now() time.Time {
	j.mu.Lock()
	defer j.mu.Unlock()
	return j.t
}

func (j *jamUji) Maju(d time.Duration) {
	j.mu.Lock()
	j.t = j.t.Add(d)
	j.mu.Unlock()
}

// bufAman: penangkap log yang aman dipakai banyak goroutine.
type bufAman struct {
	mu sync.Mutex
	b  bytes.Buffer
}

func (b *bufAman) Write(p []byte) (int, error) {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.b.Write(p)
}

func (b *bufAman) String() string {
	b.mu.Lock()
	defer b.mu.Unlock()
	return b.b.String()
}

type entriUji struct {
	Hash       string `json:"hash"`
	WajibGanti bool   `json:"wajib_ganti"`
	DiubahPada string `json:"diubah_pada"`
}

type berkasUji struct {
	Versi int                 `json:"versi"`
	Akun  map[string]entriUji `json:"akun"`
}

func bacaBerkasUji(t *testing.T, path string) berkasUji {
	t.Helper()
	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatalf("baca %s: %v", path, err)
	}
	var b berkasUji
	dec := json.NewDecoder(bytes.NewReader(raw))
	dec.DisallowUnknownFields()
	if err := dec.Decode(&b); err != nil {
		t.Fatalf("akun.json tidak sah (%v): %s", err, raw)
	}
	return b
}

func tulisBerkasUji(t *testing.T, path string, b berkasUji) {
	t.Helper()
	raw, err := json.Marshal(b)
	if err != nil {
		t.Fatal(err)
	}
	if err := os.WriteFile(path, raw, 0o600); err != nil {
		t.Fatal(err)
	}
}

type lingkungan struct {
	t            *testing.T
	dirRingkasan string
	berkasAkun   string
	jam          *jamUji
	app          *App
	log          *bufAman
	banding      atomic.Int32
}

// baruLingkungan membuat App dengan jam suntik, bcrypt MinCost, dan interval pendek.
// Nilai nol pada jedaCek/jedaDetak (lewat fungsi ubah) berarti bawaan produksi.
func baruLingkungan(t *testing.T, ubah ...func(*Config)) *lingkungan {
	t.Helper()
	dir := t.TempDir()
	l := &lingkungan{
		t:            t,
		dirRingkasan: filepath.Join(dir, "ringkasan"),
		berkasAkun:   filepath.Join(dir, "db", "akun.json"),
		jam:          &jamUji{t: time.Date(2026, 10, 16, 8, 0, 0, 0, wibUji)},
		log:          &bufAman{},
	}
	for _, d := range []string{l.dirRingkasan, filepath.Dir(l.berkasAkun)} {
		if err := os.MkdirAll(d, 0o755); err != nil {
			t.Fatal(err)
		}
	}
	cfg := Config{
		Alamat:      "127.0.0.1:0",
		Ringkasan:   l.dirRingkasan,
		Akun:        l.berkasAkun,
		biaya:       bcrypt.MinCost,
		jam:         l.jam.Now,
		jedaCek:     20 * time.Millisecond,
		jedaDetak:   60 * time.Millisecond,
		keluaranLog: l.log,
	}
	for _, f := range ubah {
		f(&cfg)
	}
	app, err := NewApp(cfg)
	if err != nil {
		t.Fatalf("NewApp: %v", err)
	}
	asli := app.banding
	app.banding = func(h, p []byte) error {
		l.banding.Add(1)
		return asli(h, p)
	}
	l.app = app
	return l
}

func (l *lingkungan) setAkun(nama, pw string, wajib bool) {
	l.t.Helper()
	b := berkasUji{Versi: 1, Akun: map[string]entriUji{}}
	if _, err := os.Stat(l.berkasAkun); err == nil {
		b = bacaBerkasUji(l.t, l.berkasAkun)
	}
	h, err := bcrypt.GenerateFromPassword([]byte(pw), bcrypt.MinCost)
	if err != nil {
		l.t.Fatal(err)
	}
	b.Akun[nama] = entriUji{Hash: string(h), WajibGanti: wajib, DiubahPada: l.jam.Now().In(wibUji).Format(time.RFC3339)}
	tulisBerkasUji(l.t, l.berkasAkun, b)
}

// tulisRingkasan menulis atomik (tmp + rename) seperti generator host.
func (l *lingkungan) tulisRingkasan(nama, isi string) {
	l.t.Helper()
	tmp := filepath.Join(l.dirRingkasan, nama+".json.tmp")
	if err := os.WriteFile(tmp, []byte(isi), 0o640); err != nil {
		l.t.Fatal(err)
	}
	if err := os.Rename(tmp, filepath.Join(l.dirRingkasan, nama+".json")); err != nil {
		l.t.Fatal(err)
	}
}

type opsi struct {
	cookie string
	origin string
	asal   []string // beberapa header Origin (Add satu per nilai); nil = tidak ada
	ip     string
	host   string
	form   url.Values
	body   string
	hdr    map[string]string
	batas  time.Duration // konteks permintaan dibatalkan setelah batas (untuk /events)
}

func (l *lingkungan) req(method, path string, o opsi) *httptest.ResponseRecorder {
	l.t.Helper()
	var body io.Reader
	switch {
	case o.form != nil:
		body = strings.NewReader(o.form.Encode())
	case o.body != "":
		body = strings.NewReader(o.body)
	}
	r := httptest.NewRequest(method, path, body)
	if body != nil {
		r.Header.Set("Content-Type", "application/x-www-form-urlencoded")
	}
	r.RemoteAddr = ipBawaan
	if o.ip != "" {
		r.RemoteAddr = o.ip
	}
	if o.host != "" {
		r.Host = o.host
	}
	if o.origin != "" {
		r.Header.Set("Origin", o.origin)
	}
	for _, v := range o.asal {
		r.Header.Add("Origin", v)
	}
	if o.cookie != "" {
		r.AddCookie(&http.Cookie{Name: "sesi", Value: o.cookie})
	}
	for k, v := range o.hdr {
		r.Header.Set(k, v)
	}
	if o.batas > 0 {
		ctx, cancel := context.WithTimeout(r.Context(), o.batas)
		defer cancel()
		r = r.WithContext(ctx)
	}
	rec := httptest.NewRecorder()
	l.app.Handler().ServeHTTP(rec, r)
	return rec
}

func formLogin(akun, pw string) url.Values {
	return url.Values{"akun": {akun}, "password": {pw}}
}

func (l *lingkungan) login(akun, pw string, o opsi) *httptest.ResponseRecorder {
	l.t.Helper()
	o.form = formLogin(akun, pw)
	return l.req("POST", "/login", o)
}

// masuk login yang harus berhasil dan mengembalikan token sesi.
func (l *lingkungan) masuk(akun, pw string) string {
	l.t.Helper()
	rec := l.login(akun, pw, opsi{})
	if rec.Code != http.StatusSeeOther {
		l.t.Fatalf("login %s: status %d, ingin 303; badan: %s", akun, rec.Code, rec.Body.String())
	}
	tok := tokenDari(rec)
	if tok == "" {
		l.t.Fatalf("login %s: tidak ada cookie sesi", akun)
	}
	return tok
}

func tokenDari(rec *httptest.ResponseRecorder) string {
	for _, c := range rec.Result().Cookies() {
		if c.Name == "sesi" {
			return c.Value
		}
	}
	return ""
}

func harapKode(t *testing.T, rec *httptest.ResponseRecorder, kode int) {
	t.Helper()
	if rec.Code != kode {
		t.Fatalf("status = %d, ingin %d; badan: %.300s", rec.Code, kode, rec.Body.String())
	}
}

func harapAlih(t *testing.T, rec *httptest.ResponseRecorder, lokasi string) {
	t.Helper()
	if rec.Code != http.StatusSeeOther || rec.Header().Get("Location") != lokasi {
		t.Fatalf("status/Location = %d %q, ingin 303 %q; badan: %.200s", rec.Code, rec.Header().Get("Location"), lokasi, rec.Body.String())
	}
}

func harapMemuat(t *testing.T, rec *httptest.ResponseRecorder, sub string) {
	t.Helper()
	if !strings.Contains(rec.Body.String(), sub) {
		t.Fatalf("badan tidak memuat %q; badan: %.400s", sub, rec.Body.String())
	}
}

// ---- SSE ----

type peristiwa struct{ Nama, Data, Retry string }

type pemecah struct {
	cur peristiwa
	ada bool
}

func (p *pemecah) baris(b string) (peristiwa, bool) {
	switch {
	case b == "":
		if p.ada {
			e := p.cur
			p.cur, p.ada = peristiwa{}, false
			return e, true
		}
	case strings.HasPrefix(b, "event: "):
		p.cur.Nama, p.ada = strings.TrimPrefix(b, "event: "), true
	case strings.HasPrefix(b, "data: "):
		p.cur.Data, p.ada = strings.TrimPrefix(b, "data: "), true
	case strings.HasPrefix(b, "retry: "):
		p.cur.Retry, p.ada = strings.TrimPrefix(b, "retry: "), true
	}
	return peristiwa{}, false
}

func parsePeristiwa(s string) []peristiwa {
	var hasil []peristiwa
	var p pemecah
	for _, b := range strings.Split(s, "\n") {
		if e, ok := p.baris(b); ok {
			hasil = append(hasil, e)
		}
	}
	return hasil
}

type aliran struct {
	Kode   int
	Header http.Header
	ch     chan peristiwa
	cancel context.CancelFunc
}

func (l *lingkungan) server() *httptest.Server {
	srv := httptest.NewServer(l.app.Handler())
	l.t.Cleanup(srv.Close)
	l.t.Cleanup(srv.CloseClientConnections)
	return srv
}

// bukaAliran membuka GET path dan membaca peristiwa SSE di goroutine terpisah.
func bukaAliran(t *testing.T, alamat, path, token string) *aliran {
	t.Helper()
	ctx, cancel := context.WithCancel(context.Background())
	req, err := http.NewRequestWithContext(ctx, "GET", alamat+path, nil)
	if err != nil {
		cancel()
		t.Fatal(err)
	}
	if token != "" {
		req.AddCookie(&http.Cookie{Name: "sesi", Value: token})
	}
	klien := &http.Client{Transport: &http.Transport{DisableKeepAlives: true}}
	resp, err := klien.Do(req)
	if err != nil {
		cancel()
		t.Fatalf("GET %s: %v", path, err)
	}
	a := &aliran{Kode: resp.StatusCode, Header: resp.Header, ch: make(chan peristiwa, 4096), cancel: cancel}
	t.Cleanup(a.Tutup)
	go func() {
		defer close(a.ch)
		defer resp.Body.Close()
		sc := bufio.NewScanner(resp.Body)
		var p pemecah
		for sc.Scan() {
			if e, ok := p.baris(sc.Text()); ok {
				select {
				case a.ch <- e:
				default:
				}
			}
		}
	}()
	return a
}

func (a *aliran) Tutup() { a.cancel() }

// berikut mengembalikan peristiwa berikutnya selain detak dan blok retry.
func (a *aliran) berikut(d time.Duration) (peristiwa, bool) {
	timer := time.NewTimer(d)
	defer timer.Stop()
	for {
		select {
		case e, ok := <-a.ch:
			if !ok {
				return peristiwa{}, false
			}
			if e.Nama == "detak" || (e.Nama == "" && e.Retry != "") {
				continue
			}
			return e, true
		case <-timer.C:
			return peristiwa{}, false
		}
	}
}

// tunggu mengembalikan peristiwa pertama bernama tertentu (yang lain dilewati).
func (a *aliran) tunggu(nama string, d time.Duration) (peristiwa, bool) {
	timer := time.NewTimer(d)
	defer timer.Stop()
	for {
		select {
		case e, ok := <-a.ch:
			if !ok {
				return peristiwa{}, false
			}
			if e.Nama == nama {
				return e, true
			}
		case <-timer.C:
			return peristiwa{}, false
		}
	}
}

// tertutup benar bila aliran ditutup server dalam d.
func (a *aliran) tertutup(d time.Duration) bool {
	timer := time.NewTimer(d)
	defer timer.Stop()
	for {
		select {
		case _, ok := <-a.ch:
			if !ok {
				return true
			}
		case <-timer.C:
			return false
		}
	}
}

func jsonDari(t *testing.T, s string) map[string]any {
	t.Helper()
	var m map[string]any
	if err := json.Unmarshal([]byte(s), &m); err != nil {
		t.Fatalf("bukan JSON objek sah (%v): %q", err, s)
	}
	return m
}

// cekSampai memanggil kondisi berkala sampai benar atau batas habis.
func cekSampai(d time.Duration, kondisi func() bool) bool {
	akhir := time.Now().Add(d)
	for time.Now().Before(akhir) {
		if kondisi() {
			return true
		}
		time.Sleep(10 * time.Millisecond)
	}
	return kondisi()
}
