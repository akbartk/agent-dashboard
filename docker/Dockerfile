# Image web agent-dashboard: biner Go statis di atas scratch (tanpa shell). Konteks build = ./apps (lihat compose).
FROM golang:1.25-alpine AS bangun
WORKDIR /src
ENV CGO_ENABLED=0 GOTOOLCHAIN=local GOFLAGS=-trimpath
COPY go.mod go.sum ./
RUN go mod download && go mod verify
COPY . .
RUN go vet ./... && go build -ldflags="-s -w" -o /out/agent-dashboard .

FROM scratch
COPY --from=bangun /out/agent-dashboard /agent-dashboard
# uid non-root generik; uid runtime ditetapkan compose user: "${AD_UID}:${AD_GID}" (lihat .env.example)
USER 65534:65534
EXPOSE 8080
ENTRYPOINT ["/agent-dashboard"]
CMD ["serve"]
