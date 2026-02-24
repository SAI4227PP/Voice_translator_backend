package workers

import (
	"bufio"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os"
	"os/exec"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
)

type SvaraTTS struct {
	settings Settings

	mu      sync.Mutex
	started bool
	cmd     *exec.Cmd
	stdin   *bufio.Writer
	stdout  *bufio.Reader
	pending map[string]chan map[string]any
}

func NewSvaraTTS(settings Settings) *SvaraTTS {
	return &SvaraTTS{
		settings: settings,
		pending:  map[string]chan map[string]any{},
	}
}

func (t *SvaraTTS) WarmUp(languages []string) {
	for _, lang := range languages {
		_, _ = t.Synthesize(lang, "Hello")
	}
}

func (t *SvaraTTS) HealthCheck() error {
	_, err := t.sendRequest("validate", "en", "health")
	return err
}

func (t *SvaraTTS) Synthesize(language, text string) ([]byte, error) {
	resp, err := t.sendRequest("synthesize", language, text)
	if err != nil {
		return nil, err
	}
	if resp["status"] != "ok" {
		return nil, fmt.Errorf("tts_failed: %v", resp["error"])
	}
	audioB64, _ := resp["audio_b64"].(string)
	if audioB64 == "" {
		return []byte{}, nil
	}
	return base64.StdEncoding.DecodeString(audioB64)
}

func (t *SvaraTTS) ensureStarted() error {
	t.mu.Lock()
	defer t.mu.Unlock()
	if t.started && t.cmd != nil && t.cmd.Process != nil {
		return nil
	}

	localModelPath, err := requireLocalONNXModel(t.settings)
	if err != nil {
		return err
	}

	validate := exec.Command(
		t.settings.SvaraCppBinaryPath,
		"validate",
		"-",
		localModelPath,
	)
	if out, err := validate.CombinedOutput(); err != nil {
		return fmt.Errorf("tts validation failed: %s (%w)", strings.TrimSpace(string(out)), err)
	}

	args := []string{
		"daemon",
		"-",
		localModelPath,
		t.settings.SvaraDefaultVoice,
		fmt.Sprintf("%d", t.settings.SvaraTimeoutSeconds),
		fmt.Sprintf("%d", t.settings.SvaraDaemonQueueSize),
		fmt.Sprintf("%d", t.settings.SvaraDaemonWorkers),
		fmt.Sprintf("%d", t.settings.SvaraMaxInputChars),
		valueOrDash(t.settings.SvaraAPIKey, "-"),
		fmt.Sprintf("%d", t.settings.SvaraOnnxThreads),
		fmt.Sprintf("%d", t.settings.SvaraOnnxSampleRate),
	}
	cmd := exec.Command(t.settings.SvaraCppBinaryPath, args...)
	stdin, err := cmd.StdinPipe()
	if err != nil {
		return err
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		return err
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		return err
	}
	if err := cmd.Start(); err != nil {
		return err
	}

	t.cmd = cmd
	t.stdin = bufio.NewWriter(stdin)
	t.stdout = bufio.NewReader(stdout)
	t.started = true
	go t.readLoop()
	go io.Copy(io.Discard, stderr)
	return nil
}

func requireLocalONNXModel(s Settings) (string, error) {
	path := strings.TrimSpace(s.SvaraOnnxModelPath)
	if path == "" || !strings.HasSuffix(strings.ToLower(path), ".onnx") {
		return "", errors.New("local ONNX TTS model is required; set SVARA_TTS_ONNX_MODEL_PATH to a .onnx file")
	}
	if st, err := os.Stat(path); err != nil || st.IsDir() {
		if err != nil {
			return "", fmt.Errorf("local ONNX TTS model not found at %q: %w", path, err)
		}
		return "", fmt.Errorf("local ONNX TTS model path is a directory: %q", path)
	}
	return path, nil
}

func (t *SvaraTTS) readLoop() {
	for {
		line, err := t.stdout.ReadString('\n')
		if err != nil {
			t.failPending(err)
			return
		}
		line = strings.TrimSpace(line)
		if line == "" {
			continue
		}
		var payload map[string]any
		if json.Unmarshal([]byte(line), &payload) != nil {
			continue
		}
		reqID, _ := payload["id"].(string)
		t.mu.Lock()
		ch := t.pending[reqID]
		delete(t.pending, reqID)
		t.mu.Unlock()
		if ch != nil {
			ch <- payload
		}
	}
}

func (t *SvaraTTS) failPending(err error) {
	t.mu.Lock()
	defer t.mu.Unlock()
	for id, ch := range t.pending {
		ch <- map[string]any{"id": id, "status": "error", "error": err.Error()}
	}
	t.pending = map[string]chan map[string]any{}
}

func (t *SvaraTTS) sendRequest(cmd, language, text string) (map[string]any, error) {
	if err := t.ensureStarted(); err != nil {
		return nil, err
	}

	id := uuid.NewString()
	payload := map[string]any{
		"id":       id,
		"cmd":      cmd,
		"language": language,
	}
	if text != "" {
		payload["text_b64"] = base64.StdEncoding.EncodeToString([]byte(text))
	}
	b, _ := json.Marshal(payload)
	ch := make(chan map[string]any, 1)

	t.mu.Lock()
	t.pending[id] = ch
	_, err := t.stdin.Write(append(b, '\n'))
	if err == nil {
		err = t.stdin.Flush()
	}
	t.mu.Unlock()
	if err != nil {
		return nil, err
	}

	timeout := time.Duration(t.settings.SvaraTimeoutSeconds) * time.Second
	select {
	case resp := <-ch:
		if status, _ := resp["status"].(string); status == "error" {
			return nil, errors.New(fmt.Sprintf("%v", resp["error"]))
		}
		return resp, nil
	case <-time.After(timeout):
		t.mu.Lock()
		delete(t.pending, id)
		t.mu.Unlock()
		return nil, errors.New("tts timeout")
	}
}

func modelRef(s Settings) string {
	if strings.HasSuffix(strings.ToLower(strings.TrimSpace(s.SvaraOnnxModelPath)), ".onnx") {
		return s.SvaraOnnxModelPath
	}
	return s.SvaraModelID
}

func valueOrDash(v, d string) string {
	if strings.TrimSpace(v) == "" {
		return d
	}
	return v
}

func (t *SvaraTTS) Close() {
	t.mu.Lock()
	defer t.mu.Unlock()
	if t.cmd != nil && t.cmd.Process != nil {
		_ = t.cmd.Process.Signal(os.Interrupt)
		_, _ = t.cmd.Process.Wait()
	}
}


