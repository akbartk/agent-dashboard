package main

import (
	"bytes"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"time"
)

const maksRingkasan = 4 << 20 // berkas ringkasan lebih besar dari ini dianggap tidak sah

// muatRingkasan membaca berkas dan menghasilkan (nama peristiwa, data JSON satu baris).
func (a *App) muatRingkasan(path string) (string, string) {
	waktu := a.waktu()
	if raw, err := bacaBatas(path); err == nil {
		var buf bytes.Buffer
		if json.Compact(&buf, raw) == nil {
			return "ringkasan", `{"waktu_server":"` + waktu + `","data":` + buf.String() + `}`
		}
	}
	return "galat", `{"waktu_server":"` + waktu + `","pesan":"Ringkasan tidak tersedia"}`
}

func bacaBatas(path string) ([]byte, error) {
	f, err := os.Open(path)
	if err != nil {
		return nil, err
	}
	defer f.Close()
	raw, err := io.ReadAll(io.LimitReader(f, maksRingkasan+1))
	if err == nil && len(raw) > maksRingkasan {
		err = fmt.Errorf("berkas melebihi %d byte", maksRingkasan)
	}
	return raw, err
}

// berubah membandingkan (mtime, ukuran, inode) dua hasil os.Stat; nil = berkas tidak ada.
func berubah(a, b os.FileInfo) bool {
	if a == nil || b == nil {
		return a != b
	}
	return !os.SameFile(a, b) || !a.ModTime().Equal(b.ModTime()) || a.Size() != b.Size()
}

// events melayani SSE. Penonton SELALU dari sesi, tidak pernah dari URL/parameter/header klien.
func (a *App) events(w http.ResponseWriter, r *http.Request) {
	s, ok := a.sesiDari(r)
	if !ok || s.WajibGanti {
		teksGalat(w, http.StatusUnauthorized, "Sesi tidak sah.")
		return
	}
	if !a.sesi.bukaAliran(s.Token) {
		teksGalat(w, http.StatusTooManyRequests, "Terlalu banyak sambungan.")
		return
	}
	defer a.sesi.tutupAliran(s.Token)

	rc := http.NewResponseController(w)
	rc.SetWriteDeadline(time.Time{}) // WriteTimeout server tidak berlaku untuk aliran

	h := w.Header()
	h.Set("Content-Type", "text/event-stream")
	h.Set("Cache-Control", "no-store")
	h.Set("X-Accel-Buffering", "no")
	w.WriteHeader(http.StatusOK)

	kirim := func(nama, data string) bool {
		if _, err := fmt.Fprintf(w, "event: %s\ndata: %s\n\n", nama, data); err != nil {
			return false
		}
		return rc.Flush() == nil
	}

	if _, err := io.WriteString(w, "retry: 2000\n\n"); err != nil {
		return
	}
	// nama akun dari akun.json disunting tangan: jangan pernah dipakai sebagai path bila tidak sah
	var path string
	if polaAkun.MatchString(s.Akun) {
		path = filepath.Join(a.dirRingkasan, s.Akun+".json")
	}
	terakhir, _ := os.Stat(path) // sebelum membaca, agar perubahan di antaranya terdeteksi tick berikutnya
	if !kirim(a.muatRingkasan(path)) {
		return
	}

	cek := time.NewTicker(a.jedaCek)
	defer cek.Stop()
	detak := time.NewTicker(a.jedaDetak)
	defer detak.Stop()
	for {
		select {
		case <-r.Context().Done():
			return
		case <-cek.C:
			if _, ok := a.sesi.ambil(s.Token, false); !ok { // tidak memperpanjang sesi
				kirim("sesi", `{"pesan":"habis"}`)
				return
			}
			sekarang, _ := os.Stat(path)
			if berubah(terakhir, sekarang) {
				terakhir = sekarang
				if !kirim(a.muatRingkasan(path)) {
					return
				}
			}
		case <-detak.C:
			if !kirim("detak", `{"waktu_server":"`+a.waktu()+`"}`) {
				return
			}
		}
	}
}
