package proto

// Generate Go protobuf/grpc stubs from ../proto/voice_translator.proto
//
//go:generate protoc -I ../../proto --go_out=. --go_opt=paths=source_relative --go-grpc_out=. --go-grpc_opt=paths=source_relative ../../proto/voice_translator.proto
