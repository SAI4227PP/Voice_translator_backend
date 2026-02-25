$ErrorActionPreference = "Stop"

$root = Split-Path -Parent $PSScriptRoot
$protoDir = Join-Path $root "proto"
$protoFile = Join-Path $protoDir "voice_translator.proto"
$outDir = Join-Path $root "go_server\proto"

function Require-Command([string]$cmd, [string]$hint) {
    if (-not (Get-Command $cmd -ErrorAction SilentlyContinue)) {
        Write-Error "Missing required command: $cmd. $hint"
    }
}

Require-Command "protoc" "Install protobuf compiler."
Require-Command "protoc-gen-go" "Run: go install google.golang.org/protobuf/cmd/protoc-gen-go@v1.34.2"
Require-Command "protoc-gen-go-grpc" "Run: go install google.golang.org/grpc/cmd/protoc-gen-go-grpc@v1.5.1"

New-Item -ItemType Directory -Path $outDir -Force | Out-Null

protoc -I $protoDir `
  --go_out=$outDir --go_opt=paths=source_relative `
  --go-grpc_out=$outDir --go-grpc_opt=paths=source_relative `
  $protoFile

Write-Host "Generated:"
Write-Host "  $outDir\voice_translator.pb.go"
Write-Host "  $outDir\voice_translator_grpc.pb.go"
