package main

import (
	"bytes"
	"context"
	"errors"
	"fmt"
	"html/template"
	"io"
	"log"
	"math"
	"net"
	"net/http"
	"os"
	"path"
	"regexp"
	"strconv"
	"strings"
	"sync"
	"time"
	"unicode/utf8"

	"golang.org/x/crypto/bcrypt"
)

const kebijakanKonten = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self'; font-src 'self'; connect-src 'self'; base-uri 'none'; form-action 'self'; frame-ancestors 'none'"

var wib = time.FixedZone("WIB", 7*3600)

// polaAkun adalah bentuk nama akun yang boleh muncul di log dan di path berkas ringkasan.
var polaAkun = regexp.MustCompile(`^[a-z0-9]{1,32}$`)

// Config: nilai tak-terekspor dipakai uji (kosong = bawaan produksi).
type Config struct {
	Alamat    string
	Ringkasan string
	Akun      string
	Tim       string

	biaya       int
	jam         func() time.Time
	jedaCek     time.Duration
	jedaDetak   time.Duration
	jedaBersih  time.Duration
	keluaranLog io.Writer
}

type App struct {
	alamat       string
	dirRingkasan string
	berkasAkun   string
	now          func() time.Time
	biaya        int
	jedaCek      time.Duration
	jedaDetak    time.Duration
	jedaBersih   time.Duration
	log          *log.Logger
	sesi         *sesiStore
	rl           *rateLimiter
	banding      func(hash, password []byte) error
	hashPalsu    []byte
	akunMu       sync.Mutex // melindungi baca-ubah-tulis akun.json oleh web
	tmplLogin    *template.Template
	tmplGanti    *template.Template
	index        []byte
}

func NewApp(cfg Config) (*App, error) {
	a := &App{
		alamat:       cfg.Alamat,
		dirRingkasan: cfg.Ringkasan,
		berkasAkun:   cfg.Akun,
		now:          cfg.jam,
		biaya:        cfg.biaya,
		jedaCek:      cfg.jedaCek,
		jedaDetak:    cfg.jedaDetak,
		jedaBersih:   cfg.jedaBersih,
		banding:      bcrypt.CompareHashAndPassword,
	}
	if a.now == nil {
		a.now = time.Now
	}
	if a.biaya == 0 {
		a.biaya = biayaBcrypt
	}
	if a.jedaCek == 0 {
		a.jedaCek = 500 * time.Millisecond
	}
	if a.jedaDetak == 0 {
		a.jedaDetak = 5 * time.Second
	}
	if a.jedaBersih == 0 {
		a.jedaBersih = time.Minute
	}
	keluaran := cfg.keluaranLog
	if keluaran == nil {
		keluaran = os.Stdout
	}
	a.log = log.New(keluaran, "", 0)
	a.sesi = newSesiStore(a.now)
	a.rl = newRateLimiter(a.now)

	var err error
	if a.tmplLogin, err = template.ParseFS(webFS, "web/login.html"); err != nil {
		return nil, err
	}
	if a.tmplGanti, err = template.ParseFS(webFS, "web/ganti.html"); err != nil {
		return nil, err
	}
	if a.index, err = webFS.ReadFile("web/index.html"); err != nil {
		return nil, err
	}
	// hash palsu: akun tak dikenal tetap membayar satu bcrypt compare (waktu setara)
	if a.hashPalsu, err = bcrypt.GenerateFromPassword([]byte("hash-palsu-waktu-setara"), a.biaya); err != nil {
		return nil, err
	}
	return a, nil
}

func (a *App) Handler() http.Handler { return http.HandlerFunc(a.layani) }

// Bersihkan membuang sesi kedaluwarsa dan entri rate-limit yang menganggur.
func (a *App) Bersihkan() {
	a.sesi.bersih()
	a.rl.bersih()
}

// Jalankan membersihkan secara berkala sampai ctx selesai.
func (a *App) Jalankan(ctx context.Context) {
	t := time.NewTicker(a.jedaBersih)
	defer t.Stop()
	for {
		select {
		case <-ctx.Done():
			return
		case <-t.C:
			a.Bersihkan()
		}
	}
}

// BuatServer membuat http.Server; ctx menjadi konteks dasar semua permintaan sehingga
// aliran SSE berhenti ketika ctx selesai (mis. SIGTERM) dan Shutdown tidak tertahan.
func (a *App) BuatServer(ctx context.Context) *http.Server {
	return &http.Server{
		Addr:              a.alamat,
		Handler:           a.Handler(),
		ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout:       15 * time.Second,
		WriteTimeout:      30 * time.Second,
		IdleTimeout:       120 * time.Second,
		MaxHeaderBytes:    16 << 10,
		BaseContext:       func(net.Listener) context.Context { return ctx },
	}
}

func (a *App) waktu() string { return a.now().In(wib).Format(time.RFC3339) }

// ---- routing ----

func (a *App) layani(w http.ResponseWriter, r *http.Request) {
	h := w.Header()
	h.Set("Content-Security-Policy", kebijakanKonten)
	h.Set("X-Content-Type-Options", "nosniff")
	h.Set("Referrer-Policy", "same-origin") // agar form POST same-origin membawa Origin asli (lihat asalSah)
	h.Set("X-Frame-Options", "DENY")
	if strings.HasPrefix(r.URL.Path, "/aset/") {
		h.Set("Cache-Control", "no-cache")
	} else {
		h.Set("Cache-Control", "no-store")
	}

	// Routing manual: ServeMux akan membersihkan path ("/aset/../x") dan mengalihkan; di sini
	// path tidak dinormalisasi sehingga traversal jatuh ke 404.
	switch p := r.URL.Path; {
	case p == "/":
		if izinkan(w, r, http.MethodGet) {
			a.beranda(w, r)
		}
	case p == "/login":
		switch {
		case r.Method == http.MethodGet:
			a.halamanLogin(w, r)
		case r.Method == http.MethodPost:
			a.postLogin(w, r)
		default:
			izinkan(w, r, http.MethodGet, http.MethodPost)
		}
	case p == "/ganti-password":
		switch {
		case r.Method == http.MethodGet:
			a.halamanGanti(w, r)
		case r.Method == http.MethodPost:
			a.postGanti(w, r)
		default:
			izinkan(w, r, http.MethodGet, http.MethodPost)
		}
	case p == "/logout":
		if izinkan(w, r, http.MethodPost) {
			a.postLogout(w, r)
		}
	case p == "/events":
		if izinkan(w, r, http.MethodGet) {
			a.events(w, r)
		}
	case strings.HasPrefix(p, "/aset/"):
		if izinkan(w, r, http.MethodGet) {
			a.aset(w, r)
		}
	default:
		teksGalat(w, http.StatusNotFound, "Tidak ditemukan.")
	}
}

// izinkan benar bila metode permintaan termasuk yang diizinkan; selain itu menjawab 405.
func izinkan(w http.ResponseWriter, r *http.Request, metode ...string) bool {
	for _, m := range metode {
		if r.Method == m {
			return true
		}
	}
	w.Header().Set("Allow", strings.Join(metode, ", "))
	teksGalat(w, http.StatusMethodNotAllowed, "Metode tidak diizinkan.")
	return false
}

func teksGalat(w http.ResponseWriter, kode int, pesan string) {
	w.Header().Set("Content-Type", "text/plain; charset=utf-8")
	w.WriteHeader(kode)
	io.WriteString(w, pesan+"\n")
}

func alihkan(w http.ResponseWriter, lokasi string) {
	w.Header().Set("Location", lokasi)
	w.WriteHeader(http.StatusSeeOther)
}

// ---- util ----

// asalSah menerapkan Q-03: Origin yang ada harus tepat satu nilai dan sama dengan http://<Host> (host apa pun yang
// dipakai penonton); yang tidak ada lolos. Dengan Referrer-Policy same-origin peramban mengirim Origin asli untuk
// form POST same-origin. "null" selalu ditolak: ke alamat HTTP non-loopback (LAN/Tailscale) peramban tidak mengirim
// Sec-Fetch-* sama sekali (hanya ke URL potentially trustworthy; terukur 16 Okt), dan "null" juga dikirim halaman
// penyerang mana pun, termasuk port lain di host yang sama (same-site, cookie SameSite tetap terkirim).
func (a *App) asalSah(w http.ResponseWriter, r *http.Request) bool {
	o, ada := r.Header["Origin"]
	if ada && (len(o) != 1 || o[0] != "http://"+r.Host) {
		a.log.Printf("asal_ditolak waktu=%s ip=%s origin=%s host=%s", a.waktu(), ipDari(r),
			kutipPotong(strings.Join(o, ", ")), kutipPotong(r.Host))
		teksGalat(w, http.StatusForbidden, "Asal permintaan ditolak.")
		return false
	}
	return true
}

// kutipPotong memotong s menjadi paling banyak 80 byte lalu meng-quote-nya, agar nilai header kiriman klien tidak
// bisa memecah atau memalsukan baris log.
func kutipPotong(s string) string {
	if len(s) > 80 {
		s = s[:80]
	}
	return strconv.Quote(s)
}

func ipDari(r *http.Request) string {
	h, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return h
}

// sesiDari mengambil sesi sah dari cookie (satu-satunya sumber identitas penonton) dan menandainya aktif.
func (a *App) sesiDari(r *http.Request) (infoSesi, bool) {
	c, err := r.Cookie("sesi")
	if err != nil {
		return infoSesi{}, false
	}
	return a.sesi.ambil(c.Value, true)
}

func setCookieSesi(w http.ResponseWriter, token string, maxAge int) {
	http.SetCookie(w, &http.Cookie{
		Name:     "sesi",
		Value:    token,
		Path:     "/",
		HttpOnly: true,
		SameSite: http.SameSiteStrictMode,
		MaxAge:   maxAge, // tanpa Secure: HTTP polos sementara (debt ADR-003)
	})
}

// catat menulis satu baris log tanpa rahasia; akun di luar ^[a-z0-9]{1,32}$ dicatat (tidak_valid).
func (a *App) catat(kejadian, akun, ip, hasil string) {
	if !polaAkun.MatchString(akun) {
		akun = "(tidak_valid)"
	}
	s := fmt.Sprintf("%s waktu=%s akun=%s ip=%s", kejadian, a.waktu(), akun, ip)
	if hasil != "" {
		s += " hasil=" + hasil
	}
	a.log.Print(s)
}

type dataHalaman struct{ Pesan, Akun string }

func render(w http.ResponseWriter, t *template.Template, kode int, d dataHalaman) {
	var buf bytes.Buffer
	if err := t.Execute(&buf, d); err != nil {
		teksGalat(w, http.StatusInternalServerError, "Galat internal.")
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.WriteHeader(kode)
	w.Write(buf.Bytes())
}

// bacaForm membatasi body 4 KB dan mengurai form; false bila sudah menjawab galat.
func bacaForm(w http.ResponseWriter, r *http.Request) bool {
	r.Body = http.MaxBytesReader(w, r.Body, 4<<10)
	if err := r.ParseForm(); err != nil {
		var besar *http.MaxBytesError
		if errors.As(err, &besar) {
			teksGalat(w, http.StatusRequestEntityTooLarge, "Permintaan terlalu besar.")
		} else {
			teksGalat(w, http.StatusBadRequest, "Permintaan tidak sah.")
		}
		return false
	}
	return true
}

// ---- halaman ----

func (a *App) beranda(w http.ResponseWriter, r *http.Request) {
	s, ok := a.sesiDari(r)
	if !ok {
		alihkan(w, "/login")
		return
	}
	if s.WajibGanti {
		alihkan(w, "/ganti-password")
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Write(a.index)
}

func (a *App) halamanLogin(w http.ResponseWriter, r *http.Request) {
	if s, ok := a.sesiDari(r); ok && !s.WajibGanti {
		alihkan(w, "/")
		return
	}
	render(w, a.tmplLogin, http.StatusOK, dataHalaman{})
}

func (a *App) postLogin(w http.ResponseWriter, r *http.Request) {
	if !a.asalSah(w, r) || !bacaForm(w, r) {
		return
	}
	akunMentah, pw := r.PostForm.Get("akun"), r.PostForm.Get("password")
	akun := strings.ToLower(akunMentah)
	ip := ipDari(r)
	kunci := buatKunci(akun, ip)

	if sisa := a.rl.tahan(kunci); sisa > 0 {
		detik := int(math.Ceil(sisa.Seconds()))
		w.Header().Set("Retry-After", strconv.Itoa(detik))
		a.catat("login", akun, ip, "ditahan")
		render(w, a.tmplLogin, http.StatusTooManyRequests, dataHalaman{
			Pesan: fmt.Sprintf("Terlalu banyak percobaan. Coba lagi dalam %d detik.", detik),
			Akun:  akunMentah,
		})
		return
	}

	berkas, err := bacaAkun(a.berkasAkun) // setiap login, agar perubahan CLI langsung berlaku
	if err != nil {
		a.log.Printf("galat waktu=%s pesan=akun_json_tidak_terbaca", a.waktu())
		teksGalat(w, http.StatusInternalServerError, "Layanan sementara tidak tersedia.")
		return
	}
	e, ada := berkas.Akun[akun]
	hash := []byte(e.Hash)
	if !ada {
		hash = a.hashPalsu
	}
	if err := a.banding(hash, []byte(pw)); err != nil || !ada {
		a.rl.gagal(kunci)
		a.catat("login", akun, ip, "gagal")
		render(w, a.tmplLogin, http.StatusUnauthorized, dataHalaman{Pesan: "Akun atau password salah.", Akun: akunMentah})
		return
	}

	a.rl.reset(kunci)
	if c, err := r.Cookie("sesi"); err == nil {
		a.sesi.hapus(c.Value) // jangan menumpuk/mewarisi sesi lama
	}
	token := a.sesi.buat(akun, e.WajibGanti)
	setCookieSesi(w, token, int(batasMutlak/time.Second))
	a.catat("login", akun, ip, "berhasil")
	if e.WajibGanti {
		alihkan(w, "/ganti-password")
		return
	}
	alihkan(w, "/")
}

func (a *App) halamanGanti(w http.ResponseWriter, r *http.Request) {
	if _, ok := a.sesiDari(r); !ok {
		alihkan(w, "/login")
		return
	}
	render(w, a.tmplGanti, http.StatusOK, dataHalaman{})
}

func (a *App) postGanti(w http.ResponseWriter, r *http.Request) {
	if !a.asalSah(w, r) {
		return
	}
	s, ok := a.sesiDari(r)
	if !ok {
		alihkan(w, "/login")
		return
	}
	if !bacaForm(w, r) {
		return
	}
	baru, ulang := r.PostForm.Get("password_baru"), r.PostForm.Get("password_ulang")
	ip := ipDari(r)
	tolak := func(pesan string) {
		a.catat("ganti_password", s.Akun, ip, "ditolak")
		render(w, a.tmplGanti, http.StatusBadRequest, dataHalaman{Pesan: pesan})
	}
	switch {
	case baru != ulang:
		tolak("Password baru tidak sama dengan ulangan.")
		return
	case utf8.RuneCountInString(baru) < 12:
		tolak("Password minimal 12 karakter.")
		return
	case len(baru) > 72:
		tolak("Password maksimal 72 byte.")
		return
	}

	a.akunMu.Lock()
	defer a.akunMu.Unlock()
	berkas, err := bacaAkun(a.berkasAkun)
	e, ada := berkas.Akun[s.Akun]
	if err != nil || !ada {
		teksGalat(w, http.StatusInternalServerError, "Layanan sementara tidak tersedia.")
		return
	}
	if a.banding([]byte(e.Hash), []byte(baru)) == nil {
		tolak("Password baru harus berbeda dari password awal.")
		return
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(baru), a.biaya)
	if err != nil {
		teksGalat(w, http.StatusInternalServerError, "Layanan sementara tidak tersedia.")
		return
	}
	berkas.Akun[s.Akun] = entriAkun{Hash: string(hash), WajibGanti: false, DiubahPada: a.waktu()}
	if err := tulisAkun(a.berkasAkun, berkas); err != nil {
		a.log.Printf("galat waktu=%s pesan=akun_json_gagal_ditulis", a.waktu())
		teksGalat(w, http.StatusInternalServerError, "Layanan sementara tidak tersedia.")
		return
	}
	a.sesi.setWajibGanti(s.Token, false)
	a.catat("ganti_password", s.Akun, ip, "berhasil")
	alihkan(w, "/")
}

func (a *App) postLogout(w http.ResponseWriter, r *http.Request) {
	if !a.asalSah(w, r) {
		return
	}
	if c, err := r.Cookie("sesi"); err == nil {
		if s, ok := a.sesi.ambil(c.Value, false); ok {
			a.catat("logout", s.Akun, ipDari(r), "")
		}
		a.sesi.hapus(c.Value)
	}
	setCookieSesi(w, "", -1)
	alihkan(w, "/login")
}

// ---- aset statis (tanpa login) ----

var tipeAset = map[string]string{
	".css":   "text/css; charset=utf-8",
	".js":    "text/javascript; charset=utf-8",
	".woff2": "font/woff2",
	".txt":   "text/plain; charset=utf-8",
}

func (a *App) aset(w http.ResponseWriter, r *http.Request) {
	nama := strings.TrimPrefix(r.URL.Path, "/aset/")
	var berkas string
	switch {
	case nama == "app.css" || nama == "app.js" || nama == "tema.js":
		berkas = "web/" + nama
	case strings.HasPrefix(nama, "font/"):
		f := strings.TrimPrefix(nama, "font/")
		if f == "" || f == "." || f == ".." || strings.ContainsAny(f, `/\`) {
			teksGalat(w, http.StatusNotFound, "Tidak ditemukan.")
			return
		}
		berkas = "web/font/" + f
	}
	tipe, tipeOk := tipeAset[path.Ext(berkas)]
	isi, err := webFS.ReadFile(berkas)
	if berkas == "" || !tipeOk || err != nil {
		teksGalat(w, http.StatusNotFound, "Tidak ditemukan.")
		return
	}
	w.Header().Set("Content-Type", tipe)
	w.Write(isi)
}
