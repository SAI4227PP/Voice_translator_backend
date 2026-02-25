# Go Port of `app/server`

This directory ports the Python `AI_Pipeline/app/server` package into Go:

- `server/connection_manager.go` mirrors `connection_manager.py`
- `server/heartbeat.go` mirrors `heartbeat.py`
- `server/websocket_server.go` mirrors `websocket_server.py`
- `server/registry.go` mirrors Python global instances/getters

Notes:

- Message routing is wired through `messaging.MessageRouter` from `AI_Pipeline/app/messaging`.
- `messaging.NoopRouter` is the default placeholder implementation.
- Protocol helpers used by server error handling are in `AI_Pipeline/app/messaging/protocol.go`.
- gRPC services are implemented in `go_server/grpcserver/server.go` and use existing `workers` + `utils.Scanner`.
- gRPC proto is `AI_Pipeline/proto/voice_translator.proto`; Go stubs are generated at Docker build into `go_server/proto/`.

Run:

```bash
cd AI_Pipeline/go_server
go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.34.2
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1
../scripts/gen_go_proto.sh
go mod tidy
go run .
```

Windows PowerShell:

```powershell
cd AI_Pipeline
go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.34.2
go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1
.\scripts\gen_go_proto.ps1
cd go_server
go mod tidy
go run .
```

WebSocket endpoint:

- `ws://localhost:8000/ws` (or configured `HOST`/`PORT`)

gRPC endpoint:

- gRPC server starts with the Go server.
- Port via `GRPC_PORT` (default `50051`).
