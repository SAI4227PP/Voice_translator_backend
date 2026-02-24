module voice_translator_go_server/app/messaging

go 1.22

require (
	github.com/google/uuid v1.6.0
	voice_translator_go_server/app/rooms v0.0.0
)

replace voice_translator_go_server/app/rooms => ../rooms
