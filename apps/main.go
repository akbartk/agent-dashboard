package main

import (
	"context"
	"fmt"
	"io"
	"net"
	"os"
	"os/signal"
	"syscall"
	"time"
)

const pemakaian = "pemakaian: agent-dashboard [serve] | agent-dashboard akun tambah|reset <akun> | agent-dashboard akun daftar"

func main() {
	os.Exit(run(os.Args[1:], os.Getenv, os.Stdout, os.Stderr))
}

func muatKonfig(getenv func(string) string) Config {
	ambil := func(kunci, bawaan string) string {
		if v := getenv(kunci); v != "" {
			return v
		}
		return bawaan
	}
	return Config{
		Alamat:    ambil("AD_ALAMAT", ":8080"),
		Ringkasan: ambil("AD_RINGKASAN", "/srv/ringkasan"),
		Akun:      ambil("AD_AKUN", "/srv/db/akun.json"),
		Tim:       ambil("AD_TIM", "/srv/conf/tim.json"),
	}
}

func run(args []string, getenv func(string) string, stdout, stderr io.Writer) int {
	cfg := muatKonfig(getenv)
	switch {
	case len(args) == 0 || (args[0] == "serve" && len(args) == 1):
		// gagal tertutup: tanpa tim.json yang sah server tidak start
		if _, err := bacaTim(cfg.Tim); err != nil {
			fmt.Fprintf(stderr, "galat: %v\n", err)
			return 1
		}
		ctx, stop := signal.NotifyContext(context.Background(), syscall.SIGTERM, os.Interrupt)
		defer stop()
		return serve(ctx, cfg, stdout, stderr)
	case args[0] == "akun":
		sah, err := bacaTim(cfg.Tim)
		if err != nil {
			fmt.Fprintf(stderr, "galat: %v\n", err)
			return 1
		}
		return cmdAkun(args[1:], cfg.Akun, sah, stdout, stderr)
	}
	fmt.Fprintln(stderr, pemakaian)
	return 2
}

// serve menjalankan server sampai ctx selesai (SIGTERM), lalu Shutdown paling lama 5 dtk.
func serve(ctx context.Context, cfg Config, stdout, stderr io.Writer) int {
	if cfg.keluaranLog == nil {
		cfg.keluaranLog = stdout
	}
	app, err := NewApp(cfg)
	if err != nil {
		fmt.Fprintf(stderr, "galat: %v\n", err)
		return 1
	}
	srv := app.BuatServer(ctx)
	ln, err := net.Listen("tcp", srv.Addr)
	if err != nil {
		fmt.Fprintf(stderr, "galat: %v\n", err)
		return 1
	}
	go app.Jalankan(ctx)
	app.log.Printf("server_mulai waktu=%s alamat=%s ringkasan=%s akun=%s", app.waktu(), ln.Addr(), cfg.Ringkasan, cfg.Akun)

	selesai := make(chan error, 1)
	go func() { selesai <- srv.Serve(ln) }()
	select {
	case err := <-selesai:
		fmt.Fprintf(stderr, "galat: %v\n", err)
		return 1
	case <-ctx.Done():
	}
	sd, batal := context.WithTimeout(context.Background(), 5*time.Second)
	defer batal()
	if err := srv.Shutdown(sd); err != nil {
		srv.Close()
		fmt.Fprintf(stderr, "galat shutdown: %v\n", err)
		return 1
	}
	return 0
}
