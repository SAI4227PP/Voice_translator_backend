#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROTO_FILE="$ROOT_DIR/proto/voice_translator.proto"
OUT_DIR="$ROOT_DIR/go_server/proto"

if ! command -v protoc >/dev/null 2>&1; then
  echo "ERROR: protoc not found. Install protobuf compiler first."
  exit 1
fi

if ! command -v protoc-gen-go >/dev/null 2>&1; then
  echo "ERROR: protoc-gen-go not found. Run:"
  echo "  go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.34.2"
  exit 1
fi

if ! command -v protoc-gen-go-grpc >/dev/null 2>&1; then
  echo "ERROR: protoc-gen-go-grpc not found. Run:"
  echo "  go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1"
  exit 1
fi

mkdir -p "$OUT_DIR"
protoc -I "$ROOT_DIR/proto" \
  --go_out="$OUT_DIR" --go_opt=paths=source_relative \
  --go-grpc_out="$OUT_DIR" --go-grpc_opt=paths=source_relative \
  "$PROTO_FILE"

echo "Generated:"
echo "  $OUT_DIR/voice_translator.pb.go"
echo "  $OUT_DIR/voice_translator_grpc.pb.go"
