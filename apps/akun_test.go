package main

import (
	"bytes"
	"os"
	"path/filepath"
	"regexp"
	"strconv"
	"strings"
	"syscall"
	"testing"
	"time"

	"golang.org/x/crypto/bcrypt"
)

const abjadUji = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"

var polaAwal = regexp.MustCompile("^Password awal (satu|dua|tiga): ([" + abjadUji + "]{20})$")

type hasilCLI struct {
	kode     int
	out, err string
}

func envAkun(path string) func(string) string {
	return func(k string) string {
		switch k {
		case "AD_AKUN":
			return path
		case "AD_TIM":
			return timUji
		}
		return ""
	}
}

func jalankanCLI(path string, args ...string) hasilCLI {
	var out, errb bytes.Buffer
	kode := run(args, envAkun(path), &out, &errb)
	return hasilCLI{kode, out.String(), errb.String()}
}

// passwordDari mengurai keluaran tambah/reset: tepat dua baris.
func passwordDari(t *testing.T, h hasilCLI, nama string) string {
	t.Helper()
	if h.kode != 0 {
		t.Fatalf("kode keluar = %d, ingin 0; stderr=%q", h.kode, h.err)
	}
	baris := strings.Split(strings.TrimSuffix(h.out, "\n"), "\n")
	if len(baris) != 2 {
		t.Fatalf("stdout harus 2 baris, dapat %d: %q", len(baris), h.out)
	}
	m := polaAwal.FindStringSubmatch(baris[0])
	if m == nil || m[1] != nama {
		t.Fatalf("baris 1 tidak sesuai format untuk %s: %q", nama, baris[0])
	}
	if baris[1] != "Wajib diganti saat login pertama." {
		t.Fatalf("baris 2 = %q", baris[1])
	}
	if n := strings.Count(h.out, m[2]); n != 1 {
		t.Fatalf("password tercetak %d kali di stdout, ingin tepat 1", n)
	}
	if strings.Contains(h.err, m[2]) {
		t.Fatalf("password bocor ke stderr: %q", h.err)
	}
	return m[2]
}

func TestAkunTambahMencetakPasswordTepatSekali(t *testing.T) {
	path := filepath.Join(t.TempDir(), "akun.json")
	h := jalankanCLI(path, "akun", "tambah", "satu")
	pw := passwordDari(t, h, "satu")

	raw, err := os.ReadFile(path)
	if err != nil {
		t.Fatal(err)
	}
	if bytes.Contains(raw, []byte(pw)) {
		t.Fatal("password asli tertulis di akun.json")
	}
	b := bacaBerkasUji(t, path) // juga menolak field tak dikenal
	if b.Versi != 1 {
		t.Fatalf("versi = %d, ingin 1", b.Versi)
	}
	e, ok := b.Akun["satu"]
	if !ok || len(b.Akun) != 1 {
		t.Fatalf("akun = %+v, ingin hanya satu", b.Akun)
	}
	if err := bcrypt.CompareHashAndPassword([]byte(e.Hash), []byte(pw)); err != nil {
		t.Fatalf("password yang dicetak tidak memverifikasi hash: %v", err)
	}
	if c, _ := bcrypt.Cost([]byte(e.Hash)); c != 12 {
		t.Fatalf("cost bcrypt = %d, ingin 12", c)
	}
	if !e.WajibGanti {
		t.Fatal("wajib_ganti harus true")
	}
	if !polaISO.MatchString(e.DiubahPada) {
		t.Fatalf("diubah_pada %q bukan ISO +07:00", e.DiubahPada)
	}
	w, err := time.Parse(time.RFC3339, e.DiubahPada)
	if err != nil || time.Since(w).Abs() > time.Minute {
		t.Fatalf("diubah_pada %q tidak dekat sekarang (%v)", e.DiubahPada, err)
	}
}

func TestAkunBerkas0600WalauUmask(t *testing.T) {
	for _, umask := range []int{0, 0o077, 0o277} {
		umask := umask
		t.Run("umask_"+strconv.FormatInt(int64(umask), 8), func(t *testing.T) {
			dir := t.TempDir() // dibuat sebelum umask diubah
			lama := syscall.Umask(umask)
			defer syscall.Umask(lama)
			path := filepath.Join(dir, "akun.json")
			passwordDari(t, jalankanCLI(path, "akun", "tambah", "satu"), "satu")
			passwordDari(t, jalankanCLI(path, "akun", "tambah", "dua"), "dua") // penulisan ulang (rename)
			passwordDari(t, jalankanCLI(path, "akun", "reset", "satu"), "satu")
			fi, err := os.Stat(path)
			if err != nil {
				t.Fatal(err)
			}
			if m := fi.Mode().Perm(); m != 0o600 {
				t.Fatalf("mode = %o, ingin 600", m)
			}
			ents, _ := os.ReadDir(dir)
			if len(ents) != 1 {
				t.Fatalf("direktori berisi %d entri (sisa berkas sementara?), ingin 1", len(ents))
			}
		})
	}
}

func TestAkunTambahGandaKeluar1(t *testing.T) {
	path := filepath.Join(t.TempDir(), "akun.json")
	passwordDari(t, jalankanCLI(path, "akun", "tambah", "tiga"), "tiga")
	sebelum, _ := os.ReadFile(path)
	h := jalankanCLI(path, "akun", "tambah", "tiga")
	if h.kode != 1 {
		t.Fatalf("kode = %d, ingin 1", h.kode)
	}
	if !strings.Contains(h.err, "reset") {
		t.Fatalf("stderr harus menyarankan reset: %q", h.err)
	}
	if h.out != "" {
		t.Fatalf("stdout harus kosong, dapat %q", h.out)
	}
	sesudah, _ := os.ReadFile(path)
	if !bytes.Equal(sebelum, sesudah) {
		t.Fatal("akun.json berubah padahal tambah ganda ditolak")
	}
}

func TestAkunNamaTidakSahKeluar2(t *testing.T) {
	tabel := [][]string{
		{"akun", "tambah", "root"},
		{"akun", "tambah", "Satu"},
		{"akun", "tambah", ""},
		{"akun", "tambah", "satu "},
		{"akun", "tambah", "../satu"},
		{"akun", "tambah", "satu,dua"},
		{"akun", "tambah"},
		{"akun", "reset", "root"},
		{"akun", "reset"},
	}
	for _, args := range tabel {
		args := args
		t.Run(strings.Join(args, "_"), func(t *testing.T) {
			path := filepath.Join(t.TempDir(), "akun.json")
			h := jalankanCLI(path, args...)
			if h.kode != 2 {
				t.Fatalf("kode = %d, ingin 2", h.kode)
			}
			if h.err == "" || h.out != "" {
				t.Fatalf("stderr harus berisi pesan, stdout kosong: err=%q out=%q", h.err, h.out)
			}
			if _, err := os.Stat(path); err == nil {
				t.Fatal("akun.json tidak boleh dibuat")
			}
		})
	}
}

func TestAkunResetMenggantiPassword(t *testing.T) {
	path := filepath.Join(t.TempDir(), "akun.json")
	pwDua := passwordDari(t, jalankanCLI(path, "akun", "tambah", "dua"), "dua")
	pw1 := passwordDari(t, jalankanCLI(path, "akun", "tambah", "satu"), "satu")

	// simulasi: satu sudah mengganti password sendiri (wajib_ganti=false)
	b := bacaBerkasUji(t, path)
	e := b.Akun["satu"]
	e.WajibGanti = false
	e.DiubahPada = "2020-01-01T00:00:00+07:00"
	b.Akun["satu"] = e
	tulisBerkasUji(t, path, b)
	duaSebelum := b.Akun["dua"]

	pw2 := passwordDari(t, jalankanCLI(path, "akun", "reset", "satu"), "satu")
	if pw2 == pw1 {
		t.Fatal("password reset sama dengan yang lama")
	}
	b = bacaBerkasUji(t, path)
	e = b.Akun["satu"]
	if bcrypt.CompareHashAndPassword([]byte(e.Hash), []byte(pw1)) == nil {
		t.Fatal("password lama masih berlaku")
	}
	if err := bcrypt.CompareHashAndPassword([]byte(e.Hash), []byte(pw2)); err != nil {
		t.Fatalf("password baru tidak memverifikasi: %v", err)
	}
	if !e.WajibGanti {
		t.Fatal("reset harus mengembalikan wajib_ganti=true")
	}
	if e.DiubahPada == "2020-01-01T00:00:00+07:00" || !polaISO.MatchString(e.DiubahPada) {
		t.Fatalf("diubah_pada tidak diperbarui: %q", e.DiubahPada)
	}
	if b.Akun["dua"] != duaSebelum {
		t.Fatal("akun lain ikut berubah")
	}
	if bcrypt.CompareHashAndPassword([]byte(b.Akun["dua"].Hash), []byte(pwDua)) != nil {
		t.Fatal("password dua rusak")
	}
}

func TestAkunResetAkunTidakAdaKeluar1(t *testing.T) {
	path := filepath.Join(t.TempDir(), "akun.json")
	h := jalankanCLI(path, "akun", "reset", "satu")
	if h.kode != 1 || h.err == "" || h.out != "" {
		t.Fatalf("hasil = %+v, ingin kode 1 + pesan stderr", h)
	}
	passwordDari(t, jalankanCLI(path, "akun", "tambah", "dua"), "dua")
	h = jalankanCLI(path, "akun", "reset", "satu")
	if h.kode != 1 {
		t.Fatalf("reset satu (tidak ada, berkas ada) kode = %d, ingin 1", h.kode)
	}
}

func TestAkunDaftar(t *testing.T) {
	path := filepath.Join(t.TempDir(), "akun.json")
	h := jalankanCLI(path, "akun", "daftar")
	if h.kode != 0 || h.out != "" {
		t.Fatalf("berkas belum ada: hasil = %+v, ingin kode 0 dan keluaran kosong", h)
	}
	if _, err := os.Stat(path); err == nil {
		t.Fatal("daftar tidak boleh membuat berkas")
	}

	passwordDari(t, jalankanCLI(path, "akun", "tambah", "tiga"), "tiga")
	passwordDari(t, jalankanCLI(path, "akun", "tambah", "satu"), "satu")
	b := bacaBerkasUji(t, path)
	e := b.Akun["tiga"]
	e.WajibGanti = false
	b.Akun["tiga"] = e
	tulisBerkasUji(t, path, b)

	h = jalankanCLI(path, "akun", "daftar")
	if h.kode != 0 {
		t.Fatalf("kode = %d: %s", h.kode, h.err)
	}
	if strings.Contains(h.out, "$2") || strings.Contains(h.out, b.Akun["satu"].Hash) {
		t.Fatalf("daftar membocorkan hash: %q", h.out)
	}
	baris := strings.Split(strings.TrimSuffix(h.out, "\n"), "\n")
	if len(baris) != 2 {
		t.Fatalf("baris = %d, ingin 2: %q", len(baris), h.out)
	}
	pola := regexp.MustCompile(`^(satu|tiga)\twajib_ganti=(ya|tidak)\tdiubah=(\S+)$`)
	harap := map[string]string{"satu": "ya", "tiga": "tidak"}
	for i, nama := range []string{"satu", "tiga"} { // urut nama
		m := pola.FindStringSubmatch(baris[i])
		if m == nil || m[1] != nama || m[2] != harap[nama] {
			t.Fatalf("baris %d = %q", i, baris[i])
		}
		if m[3] != b.Akun[nama].DiubahPada || !polaISO.MatchString(m[3]) {
			t.Fatalf("diubah di baris %d = %q, ingin %q", i, m[3], b.Akun[nama].DiubahPada)
		}
	}
}

func TestAkunPasswordAcak(t *testing.T) {
	lihat := map[string]bool{}
	for i := 0; i < 300; i++ {
		pw, err := passwordAcak()
		if err != nil {
			t.Fatal(err)
		}
		if len(pw) != 20 {
			t.Fatalf("panjang = %d, ingin 20: %q", len(pw), pw)
		}
		for _, r := range pw {
			if !strings.ContainsRune(abjadUji, r) {
				t.Fatalf("karakter %q di luar alfabet tanpa ambigu: %q", r, pw)
			}
		}
		if lihat[pw] {
			t.Fatalf("password berulang: %q", pw)
		}
		lihat[pw] = true
	}
}

func TestRunSubperintahTakDikenal(t *testing.T) {
	path := filepath.Join(t.TempDir(), "akun.json")
	tabel := [][]string{
		{"akun"},
		{"akun", "hapus", "satu"},
		{"foo"},
		{"serve", "ekstra"},
	}
	for _, args := range tabel {
		h := jalankanCLI(path, args...)
		if h.kode != 2 || h.err == "" {
			t.Errorf("run(%v) = %+v, ingin kode 2 + pesan stderr", args, h)
		}
	}
}

func TestMuatKonfig(t *testing.T) {
	c := muatKonfig(func(string) string { return "" })
	if c.Alamat != ":8080" || c.Ringkasan != "/srv/ringkasan" || c.Akun != "/srv/db/akun.json" {
		t.Fatalf("bawaan = %+v", c)
	}
	env := map[string]string{"AD_ALAMAT": "127.0.0.1:9", "AD_RINGKASAN": "/r", "AD_AKUN": "/a.json"}
	c = muatKonfig(func(k string) string { return env[k] })
	if c.Alamat != "127.0.0.1:9" || c.Ringkasan != "/r" || c.Akun != "/a.json" {
		t.Fatalf("dari env = %+v", c)
	}
}
