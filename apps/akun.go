package main

import (
	"crypto/rand"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"math/big"
	"os"
	"path/filepath"
	"sort"
	"time"

	"golang.org/x/crypto/bcrypt"
)

const (
	biayaBcrypt     = 12
	panjangPassword = 20
	// alfabet tanpa karakter ambigu (0/O, 1/l/I)
	alfabetPassword = "abcdefghjkmnpqrstuvwxyzABCDEFGHJKLMNPQRSTUVWXYZ23456789"
)

type entriAkun struct {
	Hash       string `json:"hash"`
	WajibGanti bool   `json:"wajib_ganti"`
	DiubahPada string `json:"diubah_pada"`
}

type berkasAkun struct {
	Versi int                  `json:"versi"`
	Akun  map[string]entriAkun `json:"akun"`
}

// bacaAkun membaca akun.json; berkas belum ada = daftar kosong.
func bacaAkun(path string) (berkasAkun, error) {
	b := berkasAkun{Versi: 1, Akun: map[string]entriAkun{}}
	raw, err := os.ReadFile(path)
	if errors.Is(err, os.ErrNotExist) {
		return b, nil
	}
	if err != nil {
		return b, err
	}
	if err := json.Unmarshal(raw, &b); err != nil {
		return b, fmt.Errorf("akun.json tidak sah: %w", err)
	}
	if b.Versi != 1 {
		return b, fmt.Errorf("akun.json versi %d tidak didukung", b.Versi)
	}
	if b.Akun == nil {
		b.Akun = map[string]entriAkun{}
	}
	return b, nil
}

// tulisAkun menulis atomik: berkas sementara 0600 di direktori yang sama lalu rename.
// Mode dipaksa dengan Chmod sehingga tidak bergantung umask.
func tulisAkun(path string, b berkasAkun) error {
	raw, err := json.Marshal(b)
	if err != nil {
		return err
	}
	raw = append(raw, '\n')
	dir := filepath.Dir(path)
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return err
	}
	f, err := os.CreateTemp(dir, ".akun-*.tmp")
	if err != nil {
		return err
	}
	selesai := false
	defer func() {
		if !selesai {
			f.Close()
			os.Remove(f.Name())
		}
	}()
	if err := f.Chmod(0o600); err != nil {
		return err
	}
	if _, err := f.Write(raw); err != nil {
		return err
	}
	if err := f.Sync(); err != nil {
		return err
	}
	if err := f.Close(); err != nil {
		return err
	}
	if err := os.Rename(f.Name(), path); err != nil {
		return err
	}
	selesai = true
	return nil
}

func passwordAcak() (string, error) {
	maks := big.NewInt(int64(len(alfabetPassword)))
	b := make([]byte, panjangPassword)
	for i := range b {
		n, err := rand.Int(rand.Reader, maks)
		if err != nil {
			return "", err
		}
		b[i] = alfabetPassword[n.Int64()]
	}
	return string(b), nil
}

const pemakaianAkun = "pemakaian: agent-dashboard akun tambah|reset <akun> | agent-dashboard akun daftar"

// cmdAkun menjalankan `akun tambah|reset|daftar`; args = argumen sesudah "akun"; sah = penonton dari tim.json.
func cmdAkun(args []string, path string, sah map[string]bool, stdout, stderr io.Writer) int {
	if len(args) == 0 {
		fmt.Fprintln(stderr, pemakaianAkun)
		return 2
	}
	switch args[0] {
	case "daftar":
		if len(args) != 1 {
			fmt.Fprintln(stderr, pemakaianAkun)
			return 2
		}
		return daftarAkun(path, stdout, stderr)
	case "tambah", "reset":
		if len(args) != 2 {
			fmt.Fprintln(stderr, pemakaianAkun)
			return 2
		}
		if !sah[args[1]] {
			fmt.Fprintf(stderr, "nama akun tidak sah %q: harus salah satu penonton di tim.json (%s)\n", args[1], daftarSah(sah))
			return 2
		}
		return aturAkun(args[0] == "reset", args[1], path, stdout, stderr)
	}
	fmt.Fprintln(stderr, pemakaianAkun)
	return 2
}

func aturAkun(reset bool, nama, path string, stdout, stderr io.Writer) int {
	b, err := bacaAkun(path)
	if err != nil {
		fmt.Fprintf(stderr, "galat: %v\n", err)
		return 1
	}
	_, ada := b.Akun[nama]
	if !reset && ada {
		fmt.Fprintf(stderr, "akun %s sudah ada; pakai `akun reset %s` untuk membuat password baru\n", nama, nama)
		return 1
	}
	if reset && !ada {
		fmt.Fprintf(stderr, "akun %s belum ada; pakai `akun tambah %s`\n", nama, nama)
		return 1
	}
	pw, err := passwordAcak()
	if err != nil {
		fmt.Fprintf(stderr, "galat membuat password: %v\n", err)
		return 1
	}
	hash, err := bcrypt.GenerateFromPassword([]byte(pw), biayaBcrypt)
	if err != nil {
		fmt.Fprintf(stderr, "galat bcrypt: %v\n", err)
		return 1
	}
	b.Akun[nama] = entriAkun{Hash: string(hash), WajibGanti: true, DiubahPada: time.Now().In(wib).Format(time.RFC3339)}
	if err := tulisAkun(path, b); err != nil {
		fmt.Fprintf(stderr, "galat menulis akun.json: %v\n", err)
		return 1
	}
	fmt.Fprintf(stdout, "Password awal %s: %s\nWajib diganti saat login pertama.\n", nama, pw)
	return 0
}

func daftarAkun(path string, stdout, stderr io.Writer) int {
	b, err := bacaAkun(path)
	if err != nil {
		fmt.Fprintf(stderr, "galat: %v\n", err)
		return 1
	}
	nama := make([]string, 0, len(b.Akun))
	for n := range b.Akun {
		nama = append(nama, n)
	}
	sort.Strings(nama)
	for _, n := range nama {
		e := b.Akun[n]
		ganti := "tidak"
		if e.WajibGanti {
			ganti = "ya"
		}
		fmt.Fprintf(stdout, "%s\twajib_ganti=%s\tdiubah=%s\n", n, ganti, e.DiubahPada)
	}
	return 0
}
