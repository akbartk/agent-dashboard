package main

import (
	"crypto/rand"
	"encoding/base64"
	"sync"
	"time"
)

const (
	batasTakAktif     = 12 * time.Hour
	batasMutlak       = 7 * 24 * time.Hour
	batasAliranSesi   = 5
	batasAliranGlobal = 100
)

type sesi struct {
	akun       string
	wajibGanti bool
	dibuat     time.Time
	terakhir   time.Time
	aliran     int
}

// infoSesi adalah salinan keadaan sesi yang aman dibawa keluar dari kunci.
type infoSesi struct {
	Token      string
	Akun       string
	WajibGanti bool
}

// sesiStore menyimpan sesi di memori. Jam disuntik agar kedaluwarsa bisa diuji.
type sesiStore struct {
	mu     sync.Mutex
	now    func() time.Time
	peta   map[string]*sesi
	global int
}

func newSesiStore(now func() time.Time) *sesiStore {
	return &sesiStore{now: now, peta: map[string]*sesi{}}
}

func (s *sesiStore) buat(akun string, wajibGanti bool) string {
	b := make([]byte, 32)
	rand.Read(b) // tidak pernah mengembalikan galat (Go 1.24+)
	token := base64.RawURLEncoding.EncodeToString(b)
	n := s.now()
	s.mu.Lock()
	s.peta[token] = &sesi{akun: akun, wajibGanti: wajibGanti, dibuat: n, terakhir: n}
	s.mu.Unlock()
	return token
}

func kedaluwarsa(x *sesi, n time.Time) bool {
	return n.Sub(x.terakhir) >= batasTakAktif || n.Sub(x.dibuat) >= batasMutlak
}

// ambil mengembalikan sesi yang masih sah dan membuang yang kedaluwarsa.
// sentuh=true menandai sesi aktif (permintaan HTTP); aliran SSE yang berjalan memakai false.
func (s *sesiStore) ambil(token string, sentuh bool) (infoSesi, bool) {
	n := s.now()
	s.mu.Lock()
	defer s.mu.Unlock()
	x, ok := s.peta[token]
	if !ok {
		return infoSesi{}, false
	}
	if kedaluwarsa(x, n) {
		delete(s.peta, token)
		return infoSesi{}, false
	}
	if sentuh {
		x.terakhir = n
	}
	return infoSesi{Token: token, Akun: x.akun, WajibGanti: x.wajibGanti}, true
}

func (s *sesiStore) hapus(token string) {
	s.mu.Lock()
	delete(s.peta, token)
	s.mu.Unlock()
}

func (s *sesiStore) setWajibGanti(token string, v bool) {
	s.mu.Lock()
	if x, ok := s.peta[token]; ok {
		x.wajibGanti = v
	}
	s.mu.Unlock()
}

// bukaAliran memesan satu slot SSE (maks 5 per sesi, 100 global).
func (s *sesiStore) bukaAliran(token string) bool {
	s.mu.Lock()
	defer s.mu.Unlock()
	x, ok := s.peta[token]
	if !ok || x.aliran >= batasAliranSesi || s.global >= batasAliranGlobal {
		return false
	}
	x.aliran++
	s.global++
	return true
}

func (s *sesiStore) tutupAliran(token string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.global--
	if x, ok := s.peta[token]; ok {
		x.aliran--
	}
}

func (s *sesiStore) bersih() {
	n := s.now()
	s.mu.Lock()
	defer s.mu.Unlock()
	for t, x := range s.peta {
		if kedaluwarsa(x, n) {
			delete(s.peta, t)
		}
	}
}

func (s *sesiStore) jumlah() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return len(s.peta)
}

func (s *sesiStore) aliranGlobal() int {
	s.mu.Lock()
	defer s.mu.Unlock()
	return s.global
}
