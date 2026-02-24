module voice_translator_go_server

go 1.22

require (
	github.com/google/uuid v1.6.0
	github.com/gorilla/websocket v1.5.3
	google.golang.org/grpc v1.66.0
	google.golang.org/protobuf v1.34.2
	voice_translator_go_server/app/config v0.0.0
	voice_translator_go_server/app/messaging v0.0.0
	voice_translator_go_server/app/rooms v0.0.0
	voice_translator_go_server/app/utils v0.0.0
	voice_translator_go_server/app/workers v0.0.0
)

replace voice_translator_go_server/app/config => ../app/config
replace voice_translator_go_server/app/messaging => ../app/messaging
replace voice_translator_go_server/app/rooms => ../app/rooms
replace voice_translator_go_server/app/utils => ../app/utils
replace voice_translator_go_server/app/workers => ../app/workers
