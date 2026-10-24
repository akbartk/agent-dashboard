package main

import (
	"encoding/json"
	"fmt"
	"os"
	"sort"
	"strings"
)

// timWeb adalah bagian conf/tim.json yang dibaca web (KONTRAK §2, §4). Kunci lain (orang, agen, sumber, kunci
// berawalan "_", dst.) dibaca generator/hook dan diabaikan di sini.
type timWeb struct {
	Versi    int      `json:"versi"`
	Penonton []string `json:"penonton"`
}

// bacaTim membaca tim.json; gagal tertutup: berkas hilang, JSON rusak, versi bukan 1, penonton kosong,
// id bukan bentuk akun sah (polaAkun), atau id ganda = galat.
func bacaTim(path string) (map[string]bool, error) {
	raw, err := os.ReadFile(path)
	if err != nil {
		return nil, fmt.Errorf("tim.json tidak terbaca (%s): %w", path, err)
	}
	var t timWeb
	if err := json.Unmarshal(raw, &t); err != nil {
		return nil, fmt.Errorf("tim.json tidak sah (%s): %w", path, err)
	}
	if t.Versi != 1 {
		return nil, fmt.Errorf("tim.json versi %d tidak didukung (%s): harus 1", t.Versi, path)
	}
	if len(t.Penonton) == 0 {
		return nil, fmt.Errorf("tim.json tidak sah (%s): penonton kosong atau tidak ada", path)
	}
	sah := make(map[string]bool, len(t.Penonton))
	for _, id := range t.Penonton {
		if !polaAkun.MatchString(id) {
			return nil, fmt.Errorf("tim.json tidak sah (%s): penonton %q bukan nama akun sah (a-z, 0-9, 1-32 karakter)", path, id)
		}
		if sah[id] {
			return nil, fmt.Errorf("tim.json tidak sah (%s): penonton %q ganda", path, id)
		}
		sah[id] = true
	}
	return sah, nil
}

// daftarSah mengurutkan nama akun sah untuk pesan galat.
func daftarSah(sah map[string]bool) string {
	n := make([]string, 0, len(sah))
	for id := range sah {
		n = append(n, id)
	}
	sort.Strings(n)
	return strings.Join(n, ", ")
}
