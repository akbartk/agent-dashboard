package main

import (
	"strings"
	"sync"
	"time"
)

const (
	// gagal ke-5 dan seterusnya mulai menahan percobaan berikutnya
	ambangGagal = 5
	// jeda tahan paling lama
	tahanMaks = 300 * time.Second
	// entri yang menganggur lebih lama dari ini dibuang
	rlMenganggur = time.Hour
)

// kunciRL: (akun huruf kecil dipotong 32 byte, IP dari RemoteAddr tanpa port).
type kunciRL struct{ akun, ip string }

type entriRL struct {
	gagal    int
	terakhir time.Time
}

type rateLimiter struct {
	mu   sync.Mutex
	now  func() time.Time
	peta map[kunciRL]*entriRL
}

func newRateLimiter(now func() time.Time) *rateLimiter {
	return &rateLimiter{now: now, peta: map[kunciRL]*entriRL{}}
}

func buatKunci(akun, ip string) kunciRL {
	akun = strings.ToLower(akun)
	if len(akun) > 32 {
		akun = akun[:32]
	}
	return kunciRL{akun, ip}
}

// tahan mengembalikan sisa waktu tahan; 0 berarti percobaan boleh diperiksa.
// Sesudah gagal ke-n (n>=5) tahan = min(2^(n-5), 300) detik sejak kegagalan terakhir.
func (r *rateLimiter) tahan(k kunciRL) time.Duration {
	n := r.now()
	r.mu.Lock()
	defer r.mu.Unlock()
	e := r.peta[k]
	if e == nil || e.gagal < ambangGagal {
		return 0
	}
	jeda := tahanMaks
	if p := e.gagal - ambangGagal; p <= 8 { // 2^8 = 256 < 300; 2^9 sudah melewati batas
		jeda = time.Duration(1<<p) * time.Second
	}
	sisa := e.terakhir.Add(jeda).Sub(n)
	if sisa < 0 {
		return 0
	}
	return sisa
}

func (r *rateLimiter) gagal(k kunciRL) {
	n := r.now()
	r.mu.Lock()
	defer r.mu.Unlock()
	e := r.peta[k]
	if e == nil {
		e = &entriRL{}
		r.peta[k] = e
	}
	e.gagal++
	e.terakhir = n
}

func (r *rateLimiter) reset(k kunciRL) {
	r.mu.Lock()
	delete(r.peta, k)
	r.mu.Unlock()
}

func (r *rateLimiter) bersih() {
	n := r.now()
	r.mu.Lock()
	defer r.mu.Unlock()
	for k, e := range r.peta {
		if n.Sub(e.terakhir) > rlMenganggur {
			delete(r.peta, k)
		}
	}
}

func (r *rateLimiter) jumlah() int {
	r.mu.Lock()
	defer r.mu.Unlock()
	return len(r.peta)
}
