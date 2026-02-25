package workers

import (
	"bufio"
	"encoding/base64"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"os/exec"
	"strings"
	"sync"
	"time"

	"github.com/google/uuid"
)

type SarvamTranslator struct {
	settings Settings

	mu      sync.Mutex
	started bool
	cmd     *exec.Cmd
	stdin   *bufio.Writer
	stdout  *bufio.Reader
	stderr  strings.Builder
	pending map[string]chan map[string]any

	consecutiveFailures int
	breakerOpenUntil    time.Time
}

func NewSarvamTranslator(settings Settings) *SarvamTranslator {
	return &SarvamTranslator{
		settings: settings,
		pending:  map[string]chan map[string]any{},
	}
}

func (t *SarvamTranslator) WarmUp() {
	_, _ = t.sendRequest("warm_up", "", "", "", nil)
}

func (t *SarvamTranslator) HealthCheck() error {
	_, err := t.sendRequest("validate", "en", "hi", "health", nil)
	return err
}

func (t *SarvamTranslator) WarmUpCommonPairs(pairs [][2]string) {
	if len(pairs) == 0 {
		t.WarmUp()
		return
	}

	seen := make(map[string]struct{}, len(pairs))
	for _, pair := range pairs {
		src := strings.TrimSpace(pair[0])
		tgt := strings.TrimSpace(pair[1])
		if src == "" || tgt == "" {
			continue
		}
		key := src + "->" + tgt
		if _, ok := seen[key]; ok {
			continue
		}
		seen[key] = struct{}{}
		_, _ = t.Translate("warmup", src, tgt)
	}
}

func (t *SarvamTranslator) Translate(text, source, target string) (string, error) {
	var out string
	err := t.executeWithResilience(func() error {
		resp, err := t.sendRequest("translate", source, target, text, nil)
		if err != nil {
			return err
		}
		if resp["status"] != "ok" {
			return fmt.Errorf("translation_failed: %v", resp["error"])
		}
		raw, _ := resp["translated_text"].(string)
		out = sanitizeTranslatedText(raw)
		return nil
	})
	return out, err
}

func (t *SarvamTranslator) BatchTranslate(texts []string, source, target string) ([]string, error) {
	var out []string
	err := t.executeWithResilience(func() error {
		resp, err := t.sendRequest("batch_translate", source, target, "", texts)
		if err != nil {
			return err
		}
		if resp["status"] != "ok" {
			return fmt.Errorf("batch_translate_failed: %v", resp["error"])
		}
		if raw, ok := resp["translated_items"].([]any); ok {
			out = make([]string, 0, len(raw))
			for _, v := range raw {
				out = append(out, sanitizeTranslatedText(fmt.Sprintf("%v", v)))
			}
			return nil
		}
		text, _ := resp["translated_text"].(string)
		if text == "" {
			out = []string{}
			return nil
		}
		parts := strings.Split(text, "\u0000")
		out = make([]string, 0, len(parts))
		for _, p := range parts {
			out = append(out, sanitizeTranslatedText(p))
		}
		return nil
	})
	return out, err
}

func sanitizeTranslatedText(v string) string {
	s := strings.TrimSpace(v)
	for strings.HasPrefix(s, "<") {
		end := strings.Index(s, ">")
		if end <= 1 {
			break
		}
		tag := s[1:end]
		if !isAlphaNumTag(tag) {
			break
		}
		s = strings.TrimSpace(s[end+1:])
	}
	for _, p := range []string{"Translation:", "Output:", "Answer:"} {
		if strings.HasPrefix(s, p) {
			s = strings.TrimSpace(strings.TrimPrefix(s, p))
		}
	}
	return s
}

func isAlphaNumTag(v string) bool {
	for _, r := range v {
		if (r >= 'a' && r <= 'z') || (r >= 'A' && r <= 'Z') || (r >= '0' && r <= '9') || r == '_' || r == '-' {
			continue
		}
		return false
	}
	return v != ""
}

func (t *SarvamTranslator) ensureStarted() error {
	t.mu.Lock()
	defer t.mu.Unlock()
	if t.started && t.cmd != nil && t.cmd.Process != nil {
		return nil
	}

	validate := exec.Command(
		t.settings.SarvamCppBinary,
		"validate",
		t.settings.LlamaCppPath,
		fallback(t.settings.LlamaCliPath, "-"),
		t.settings.SarvamModelPath,
	)
	if out, err := validate.CombinedOutput(); err != nil {
		return fmt.Errorf("translation validation failed: %s (%w)", strings.TrimSpace(string(out)), err)
	}

	args := []string{
		"daemon",
		t.settings.LlamaCppPath,
		fallback(t.settings.LlamaCliPath, "-"),
		t.settings.SarvamModelPath,
		fmt.Sprintf("%d", t.settings.SarvamMaxTokens),
		fmt.Sprintf("%d", t.settings.SarvamContextSize),
		fmt.Sprintf("%d", t.settings.SarvamThreads),
		fmt.Sprintf("%d", t.settings.SarvamGpuLayers),
		fmt.Sprintf("%d", t.settings.SarvamQueueSize),
		fmt.Sprintf("%d", t.settings.SarvamWorkers),
		fmt.Sprintf("%d", t.settings.SarvamMaxInputChar),
		fmt.Sprintf("%d", t.settings.LlamaServerPort),
	}
	cmd := exec.Command(t.settings.SarvamCppBinary, args...)
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
	go t.stderrLoop(stderr)
	return nil
}

func (t *SarvamTranslator) resetProcessLocked() {
	if t.cmd != nil && t.cmd.Process != nil {
		_ = t.cmd.Process.Kill()
		_, _ = t.cmd.Process.Wait()
	}
	t.started = false
	t.cmd = nil
	t.stdin = nil
	t.stdout = nil
}

func (t *SarvamTranslator) stderrTailLocked() string {
	s := strings.TrimSpace(t.stderr.String())
	if len(s) > 500 {
		return s[len(s)-500:]
	}
	return s
}

func (t *SarvamTranslator) stderrLoop(r io.Reader) {
	buf := make([]byte, 1024)
	for {
		n, err := r.Read(buf)
		if n > 0 {
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

func (t *SarvamTranslator) readLoop() {
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

func (t *SarvamTranslator) failPending(err error) {
	t.mu.Lock()
	defer t.mu.Unlock()
	msg := err.Error()
	if tail := t.stderrTailLocked(); tail != "" {
		msg = fmt.Sprintf("%s (stderr_tail=%s)", msg, tail)
	}
	for id, ch := range t.pending {
		ch <- map[string]any{"id": id, "status": "error", "error": msg}
	}
	t.pending = map[string]chan map[string]any{}
}

func (t *SarvamTranslator) sendRequest(cmd, source, target, text string, texts []string) (map[string]any, error) {
	if err := t.ensureStarted(); err != nil {
		return nil, err
	}

	id := uuid.NewString()
	payload := map[string]any{
		"id":     id,
		"cmd":    cmd,
		"source": source,
		"target": target,
	}
	if text != "" {
		payload["text_b64"] = base64.StdEncoding.EncodeToString([]byte(text))
	}
	if texts != nil {
		blob := strings.Join(texts, "\u0000")
		payload["batch_b64"] = base64.StdEncoding.EncodeToString([]byte(blob))
	}
	b, _ := json.Marshal(payload)

	ch := make(chan map[string]any, 1)
	t.mu.Lock()
	t.pending[id] = ch
	_, err := t.stdin.Write(append(b, '\n'))
	if err == nil {
		err = t.stdin.Flush()
	}
	var stderrTail string
	t.mu.Unlock()
	if err != nil {
		t.mu.Lock()
		delete(t.pending, id)
		stderrTail = t.stderrTailLocked()
		t.resetProcessLocked()
		t.mu.Unlock()
		if stderrTail != "" {
			return nil, fmt.Errorf("%w (stderr_tail=%s)", err, stderrTail)
		}
		return nil, err
	}

	timeout := time.Duration(t.settings.SarvamTimeout) * time.Second
	select {
	case resp := <-ch:
		if status, _ := resp["status"].(string); status == "error" && resp["error"] != nil {
			return nil, errors.New(fmt.Sprintf("%v", resp["error"]))
		}
		return resp, nil
	case <-time.After(timeout):
		t.mu.Lock()
		delete(t.pending, id)
		stderrTail = t.stderrTailLocked()
		t.resetProcessLocked()
		t.mu.Unlock()
		if stderrTail != "" {
			return nil, fmt.Errorf("translation timeout (stderr_tail=%s)", stderrTail)
		}
		return nil, errors.New("translation timeout")
	}
}

func (t *SarvamTranslator) executeWithResilience(fn func() error) error {
	if t.isCircuitOpen() {
		return errors.New("translation circuit breaker is open")
	}
	retries := t.settings.TranslationRetryCount
	lastErr := error(nil)
	for attempt := 0; attempt <= retries; attempt++ {
		err := fn()
		if err == nil {
			t.onSuccess()
			return nil
		}
		lastErr = err
		t.onFailure()
		if attempt >= retries {
			break
		}
		backoff := t.settings.TranslationRetryBackoffMs * (1 << attempt)
		time.Sleep(time.Duration(backoff) * time.Millisecond)
	}
	return fmt.Errorf("translation request failed after retries: %w", lastErr)
}

func (t *SarvamTranslator) isCircuitOpen() bool {
	t.mu.Lock()
	defer t.mu.Unlock()
	return time.Now().Before(t.breakerOpenUntil)
}

func (t *SarvamTranslator) onSuccess() {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.consecutiveFailures = 0
	t.breakerOpenUntil = time.Time{}
}

func (t *SarvamTranslator) onFailure() {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.consecutiveFailures++
	if t.consecutiveFailures >= t.settings.TranslationBreakerThreshold {
		t.breakerOpenUntil = time.Now().Add(time.Duration(t.settings.TranslationBreakerResetSecs) * time.Second)
	}
}

func fallback(v, d string) string {
	if strings.TrimSpace(v) == "" {
		return d
	}
	return v
}

func (t *SarvamTranslator) Close() {
	t.mu.Lock()
	defer t.mu.Unlock()
	t.resetProcessLocked()
}

