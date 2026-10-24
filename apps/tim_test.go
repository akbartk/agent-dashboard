package main

import (
	"fmt"
	"os"
	"path/filepath"
	"regexp"
	"strings"
	"testing"
)

// timUji = path tim.json netral (dibuat TestMain) yang dipakai semua uji CLI lewat AD_TIM.
var timUji string

// Berisi juga kunci yang tidak dibaca web (orang, agen, sumber, kunci berawalan "_") untuk membuktikan diabaikan.
const isiTimUji = `{
  "_catatan": "data uji netral",
  "versi": 1,
  "orang": [{"id": "satu", "nama": "Orang Satu", "peran": "Pemilik", "induk": []}],
  "penonton": ["satu", "dua", "tiga"],
  "pemilik": "satu",
  "koordinator": "agen-a",
  "agen": {"agen-a": {"nama": "Agen A", "peran": "Koordinator", "induk": ["satu"], "ruang": "koordinasi"}},
  "sumber": {"proc": "/proc"}
}`

func TestMain(m *testing.M) {
	dir, err := os.MkdirTemp("", "ad-tim-uji-")
	if err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	timUji = filepath.Join(dir, "tim.json")
	if err := os.WriteFile(timUji, []byte(isiTimUji), 0o600); err != nil {
		fmt.Fprintln(os.Stderr, err)
		os.Exit(1)
	}
	kode := m.Run()
	os.RemoveAll(dir)
	os.Exit(kode)
}

// jalankanDenganEnv menjalankan run() dengan env eksplisit (AD_TIM diatur pemanggil).
func jalankanDenganEnv(env map[string]string, args ...string) hasilCLI {
	var out, errb strings.Builder
	kode := run(args, func(k string) string { return env[k] }, &out, &errb)
	return hasilCLI{kode, out.String(), errb.String()}
}

func tulisTimUji(t *testing.T, isi string) string {
	t.Helper()
	p := filepath.Join(t.TempDir(), "tim.json")
	if err := os.WriteFile(p, []byte(isi), 0o600); err != nil {
		t.Fatal(err)
	}
	return p
}

func TestAkunSahDariTim(t *testing.T) {
	tim := tulisTimUji(t, `{"versi":1,"penonton":["pa","pb"]}`)
	for _, tc := range []struct {
		nama string
		kode int
	}{
		{"pa", 0},
		{"pb", 0},
		{"pc", 2},   // bukan penonton di tim.json
		{"satu", 2}, // nama yang ada di tim.json LAIN tidak ikut sah
		{"PA", 2},   // huruf besar
		{"root", 2},
	} {
		tc := tc
		t.Run(tc.nama, func(t *testing.T) {
			akun := filepath.Join(t.TempDir(), "akun.json")
			h := jalankanDenganEnv(map[string]string{"AD_TIM": tim, "AD_AKUN": akun}, "akun", "tambah", tc.nama)
			if h.kode != tc.kode {
				t.Fatalf("akun tambah %q: kode = %d, ingin %d; stderr=%q", tc.nama, h.kode, tc.kode, h.err)
			}
			if tc.kode == 2 {
				if !strings.Contains(h.err, "pa") || !strings.Contains(h.err, "pb") {
					t.Fatalf("pesan galat harus menyebut nama sah dari tim.json: %q", h.err)
				}
				if _, err := os.Stat(akun); err == nil {
					t.Fatal("akun.json tidak boleh dibuat untuk nama tidak sah")
				}
			}
		})
	}
}

func TestPemakaianTanpaNamaAkun(t *testing.T) {
	h := jalankanDenganEnv(map[string]string{"AD_TIM": timUji}, "akun")
	if h.kode != 2 || !strings.Contains(h.err, "<akun>") {
		t.Fatalf("pemakaian akun: kode=%d stderr=%q, ingin 2 + <akun>", h.kode, h.err)
	}
	h = jalankanDenganEnv(map[string]string{"AD_TIM": timUji}, "foo")
	if h.kode != 2 || !strings.Contains(h.err, "<akun>") {
		t.Fatalf("pemakaian utama: kode=%d stderr=%q, ingin 2 + <akun>", h.kode, h.err)
	}
}

// Gagal tertutup: tim.json hilang / rusak / tidak sah => keluar != 0 dengan pesan yang menyebut tim.json.
func TestTimBermasalahGagalTertutup(t *testing.T) {
	hilang := filepath.Join(t.TempDir(), "tidak-ada.json")
	kasus := map[string]string{
		"hilang":            hilang,
		"bukan json":        tulisTimUji(t, `{bukan json`),
		"versi salah":       tulisTimUji(t, `{"versi":2,"penonton":["pa"]}`),
		"versi hilang":      tulisTimUji(t, `{"penonton":["pa"]}`),
		"penonton hilang":   tulisTimUji(t, `{"versi":1}`),
		"penonton kosong":   tulisTimUji(t, `{"versi":1,"penonton":[]}`),
		"penonton bukan id": tulisTimUji(t, `{"versi":1,"penonton":["../x"]}`),
		"penonton ganda":    tulisTimUji(t, `{"versi":1,"penonton":["pa","pa"]}`),
	}
	perintah := map[string][]string{
		"akun tambah": {"akun", "tambah", "pa"},
		"akun daftar": {"akun", "daftar"},
		"serve":       {"serve"},
	}
	for nk, tim := range kasus {
		for np, args := range perintah {
			nk, tim, np, args := nk, tim, np, args
			t.Run(nk+"/"+np, func(t *testing.T) {
				akun := filepath.Join(t.TempDir(), "akun.json")
				// AD_ALAMAT tidak sah: kalau gerbang tim.json bocor, serve gagal di Listen, bukan menggantung.
				env := map[string]string{"AD_TIM": tim, "AD_AKUN": akun, "AD_ALAMAT": "bukan-alamat"}
				h := jalankanDenganEnv(env, args...)
				if h.kode == 0 {
					t.Fatalf("kode = 0, ingin != 0; stdout=%q", h.out)
				}
				if !strings.Contains(h.err, "tim.json") {
					t.Fatalf("pesan galat harus menyebut tim.json: %q", h.err)
				}
				if _, err := os.Stat(akun); err == nil {
					t.Fatal("akun.json tidak boleh dibuat saat tim.json bermasalah")
				}
			})
		}
	}
}

func TestTimBawaanPathDariEnv(t *testing.T) {
	c := muatKonfig(func(string) string { return "" })
	if c.Tim != "/srv/conf/tim.json" {
		t.Fatalf("bawaan Tim = %q", c.Tim)
	}
	c = muatKonfig(func(k string) string {
		if k == "AD_TIM" {
			return "/x/tim.json"
		}
		return ""
	})
	if c.Tim != "/x/tim.json" {
		t.Fatalf("dari env Tim = %q", c.Tim)
	}
}

// Sumber apps/ (kode Go + aset web) tidak boleh memuat nama tim sumber, host, atau IP nyata (KONTRAK §4, §9-1b).
// Kata dirakit dari potongan supaya berkas uji ini sendiri tidak terkena pemindaian.
func TestSumberTanpaIdentitas(t *testing.T) {
	nama := []string{"di" + "cky", "ja" + "ti", "aj" + "eng", "de" + "sy", "vi" + "a", "u" + "ci", "al" + "fa", "be" + "ta",
		"car" + "li", "del" + "ta", "net" + "-bsk", "ak" + "bar", "bsk" + "dev", "Ec" + "ho"}
	pola := []*regexp.Regexp{
		regexp.MustCompile(`(?i)\b(?:` + strings.Join(nama[:len(nama)-1], "|") + `)\b`),
		regexp.MustCompile(`\b` + nama[len(nama)-1] + `\b`),
		regexp.MustCompile(`10\.103\.|100\.124\.|100\.74\.|192\.168\.`),
	}
	var berkas []string
	for _, g := range []string{"*.go", "web/*.html", "web/*.js", "web/*.css"} {
		m, err := filepath.Glob(g)
		if err != nil || len(m) == 0 {
			t.Fatalf("glob %q: err=%v jumlah=%d", g, err, len(m))
		}
		berkas = append(berkas, m...)
	}
	var temuan []string
	for _, f := range berkas {
		raw, err := os.ReadFile(f)
		if err != nil {
			t.Fatal(err)
		}
		for i, baris := range strings.Split(string(raw), "\n") {
			for _, p := range pola {
				if p.MatchString(baris) {
					temuan = append(temuan, fmt.Sprintf("%s:%d: %s", f, i+1, strings.TrimSpace(baris)))
					break
				}
			}
		}
	}
	if len(temuan) > 0 {
		n := len(temuan)
		if n > 25 {
			temuan = temuan[:25]
		}
		t.Fatalf("%d baris memuat identitas/host/IP nyata (25 pertama):\n%s", n, strings.Join(temuan, "\n"))
	}
}
