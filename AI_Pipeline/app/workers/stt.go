package workers

import (
	"encoding/base64"
	"encoding/json"
	"fmt"
	"os/exec"
	"strings"
)

type STTResult struct {
	Text       string
	Confidence any
}

type PythonSTTBridge struct{}

func NewPythonSTTBridge() *PythonSTTBridge {
	return &PythonSTTBridge{}
}

func (b *PythonSTTBridge) Transcribe(audio []byte, language string) (STTResult, error) {
	audioB64 := base64.StdEncoding.EncodeToString(audio)
	script := `
import sys, json, base64
from app.pipeline.stt import STTFactory
audio = base64.b64decode(sys.argv[1])
lang = sys.argv[2]
engine = STTFactory.get_engine(lang)
rec = engine.create_recognizer()
engine.recognize(audio, rec)
result = engine.finalize(rec)
print(json.dumps({"text": result.get("text",""), "confidence": result.get("confidence", None)}))
`
	cmd := exec.Command("python", "-c", script, audioB64, language)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return STTResult{}, fmt.Errorf("stt bridge failed: %s (%w)", strings.TrimSpace(string(out)), err)
	}
	var parsed map[string]any
	if err := json.Unmarshal(out, &parsed); err != nil {
		return STTResult{}, err
	}
	return STTResult{
		Text:       fmt.Sprintf("%v", parsed["text"]),
		Confidence: parsed["confidence"],
	}, nil
}

func (b *PythonSTTBridge) WarmUp(languages []string) {
	if len(languages) == 0 {
		return
	}
	for _, language := range languages {
		script := `
from app.pipeline.stt import STTFactory
import sys
STTFactory.get_engine(sys.argv[1])
print("ok")
`
		_ = exec.Command("python", "-c", script, language).Run()
	}
}

func (b *PythonSTTBridge) HealthCheck(language string) error {
	lang := strings.TrimSpace(language)
	if lang == "" {
		lang = "en"
	}
	script := `
from app.pipeline.stt import STTFactory
import sys
STTFactory.get_engine(sys.argv[1])
print("ok")
`
	return exec.Command("python", "-c", script, lang).Run()
}

