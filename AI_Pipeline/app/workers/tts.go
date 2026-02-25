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
	stderr  strings.Builder
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
	textLen := len(text)
	log.Printf("tts_synthesize_start language=%s text_len=%d", language, textLen)
	resp, err := t.sendRequest("synthesize", language, text)
	if err != nil {
		log.Printf("tts_synthesize_failed language=%s text_len=%d error=%v", language, textLen, err)
		return nil, err
	}
	if resp["status"] != "ok" {
		msg := fmt.Sprintf("%v", resp["error"])
		if snippet, _ := resp["stderr_snippet"].(string); strings.TrimSpace(snippet) != "" {
			msg = fmt.Sprintf("%s (stderr_snippet=%s)", msg, strings.TrimSpace(snippet))
		}
		log.Printf("tts_synthesize_failed language=%s text_len=%d status_error=%s", language, textLen, msg)
		return nil, fmt.Errorf("tts_failed: %s", msg)
	}
	audioB64, _ := resp["audio_b64"].(string)
	if audioB64 == "" {
		log.Printf("tts_synthesize_done language=%s text_len=%d audio_bytes=0", language, textLen)
		return []byte{}, nil
	}
	audio, decErr := base64.StdEncoding.DecodeString(audioB64)
	if decErr != nil {
		log.Printf("tts_synthesize_failed language=%s text_len=%d decode_error=%v", language, textLen, decErr)
		return nil, decErr
	}
	log.Printf("tts_synthesize_done language=%s text_len=%d audio_bytes=%d", language, textLen, len(audio))
	return audio, nil
}

func (t *SvaraTTS) ensureStarted() error {
	t.mu.Lock()
	if t.started && t.cmd != nil && t.cmd.Process != nil {
		t.mu.Unlock()
		return nil
	}

	modelRef, err := resolveTTSRuntimeConfig(t.settings)
	if err != nil {
		t.mu.Unlock()
		return err
	}

	validate := exec.Command(
		t.settings.SvaraCppBinaryPath,
		"validate",
		modelRef,
		valueOrDash(t.settings.LlamaCppPath, "/app/llama.cpp"),
		"-",
	)
	if out, err := validate.CombinedOutput(); err != nil {
		t.mu.Unlock()
		return fmt.Errorf("tts validation failed: %s (%w)", strings.TrimSpace(string(out)), err)
	}

	args := []string{
		"daemon",
		modelRef,
		t.settings.SvaraDefaultVoice,
		fmt.Sprintf("%d", t.settings.SvaraTimeoutSeconds),
		fmt.Sprintf("%d", t.settings.SvaraDaemonQueueSize),
		fmt.Sprintf("%d", t.settings.SvaraDaemonWorkers),
		fmt.Sprintf("%d", t.settings.SvaraMaxInputChars),
		valueOrDash(t.settings.LlamaCppPath, "/app/llama.cpp"),
		fmt.Sprintf("%d", t.settings.LlamaServerPort+1),
		"-",
		fmt.Sprintf("%d", t.settings.SvaraThreads),
		fmt.Sprintf("%d", t.settings.SvaraContextSize),
		fmt.Sprintf("%t", t.settings.SvaraPinWorkers),
	}
	cmd := exec.Command(t.settings.SvaraCppBinaryPath, args...)
	stdin, err := cmd.StdinPipe()
	if err != nil {
		t.mu.Unlock()
		return err
	}
	stdout, err := cmd.StdoutPipe()
	if err != nil {
		t.mu.Unlock()
		return err
	}
	stderr, err := cmd.StderrPipe()
	if err != nil {
		t.mu.Unlock()
		return err
	}
	if err := cmd.Start(); err != nil {
		t.mu.Unlock()
		return err
	}

	t.cmd = cmd
	t.stdin = bufio.NewWriter(stdin)
	t.stdout = bufio.NewReader(stdout)
	t.started = true
	go t.readLoop()
	go t.stderrLoop(stderr)
	t.mu.Unlock()

	// One-time daemon warm-up to avoid first user request latency spikes.
	_, _ = t.sendRequest("warm_up", "hi", "Hello")
	return nil
}

func resolveTTSRuntimeConfig(s Settings) (modelRef string, err error) {
	modelID := strings.TrimSpace(s.SvaraModelID)
	if modelID == "" {
		return "", errors.New("tts model ref missing; set SVARA_TTS_MODEL_ID to local GGUF path")
	}
	if st, statErr := os.Stat(modelID); statErr == nil && !st.IsDir() {
		// Local GGUF model path mode.
		return modelID, nil
	}
	return "", fmt.Errorf("local TTS model not found at '%s'; API mode is disabled, set SVARA_TTS_MODEL_ID to a local .gguf path", modelID)
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

func (t *SvaraTTS) stderrTailLocked() string {
	s := strings.TrimSpace(t.stderr.String())
	if len(s) > 500 {
		return s[len(s)-500:]
	}
	return s
}

func (t *SvaraTTS) stderrLoop(r io.Reader) {
	buf := make([]byte, 1024)
	for {
		n, err := r.Read(buf)
		if n > 0 {
			chunk := strings.TrimSpace(string(buf[:n]))
			if chunk != "" {
				log.Printf("tts_daemon_stderr chunk=%s", chunk)
			}
			t.mu.Lock()
			t.stderr.Write(buf[:n])
			if t.stderr.Len() > 4000 {
				txt := t.stderr.String()
				t.stderr.Reset()
				t.stderr.WriteString(txt[len(txt)-4000:])
			}
			t.mu.Unlock()
		}
		if err != nil {
			return
		}
	}
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
		t.mu.Lock()
		tail := t.stderrTailLocked()
		t.mu.Unlock()
		if tail != "" {
			return nil, fmt.Errorf("%w (stderr_tail=%s)", err, tail)
		}
		return nil, err
	}

	timeout := time.Duration(t.settings.SvaraTimeoutSeconds) * time.Second
	select {
	case resp := <-ch:
		if status, _ := resp["status"].(string); status == "error" {
			msg := fmt.Sprintf("%v", resp["error"])
			if snippet, _ := resp["stderr_snippet"].(string); strings.TrimSpace(snippet) != "" {
				msg = fmt.Sprintf("%s (stderr_snippet=%s)", msg, strings.TrimSpace(snippet))
			}
			return nil, errors.New(msg)
		}
		return resp, nil
	case <-time.After(timeout):
		t.mu.Lock()
		delete(t.pending, id)
		tail := t.stderrTailLocked()
		t.mu.Unlock()
		if tail != "" {
			return nil, fmt.Errorf("tts timeout (stderr_tail=%s)", tail)
		}
		return nil, errors.New("tts timeout")
	}
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


