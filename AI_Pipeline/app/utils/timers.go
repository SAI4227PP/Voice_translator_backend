package utils

import (
	"errors"
	"log/slog"
	"math"
	"sort"
	"sync"
	"time"
)

type Timer struct {
	Name      string
	startTime time.Time
	endTime   time.Time
	started   bool
	stopped   bool
}

func NewTimer(name string) *Timer {
	return &Timer{Name: name}
}

func (t *Timer) Start() {
	t.startTime = time.Now()
	t.started = true
	t.stopped = false
}

func (t *Timer) Stop() (time.Duration, error) {
	if !t.started {
		return 0, errors.New("timer not started")
	}
	t.endTime = time.Now()
	t.stopped = true
	return t.Elapsed(), nil
}

func (t *Timer) Elapsed() time.Duration {
	if !t.started {
		return 0
	}
	if t.stopped {
		return t.endTime.Sub(t.startTime)
	}
	return time.Since(t.startTime)
}

func (t *Timer) ElapsedMs() float64 {
	return float64(t.Elapsed().Microseconds()) / 1000.0
}

func TimeBlock(name string, logResult bool, fn func(timer *Timer) error) error {
	timer := NewTimer(name)
	timer.Start()
	defer func() {
		_, _ = timer.Stop()
		if logResult {
			slog.Default().Debug("time_block_completed", "name", name, "duration_ms", timer.ElapsedMs())
		}
	}()
	return fn(timer)
}

type MetricStats struct {
	Count  int     `json:"count"`
	Mean   float64 `json:"mean"`
	Median float64 `json:"median"`
	Min    float64 `json:"min"`
	Max    float64 `json:"max"`
	Stdev  float64 `json:"stdev"`
	P95    float64 `json:"p95"`
	P99    float64 `json:"p99"`
}

type PerformanceTracker struct {
	mu         sync.RWMutex
	metrics    map[string][]float64
	maxSamples int
}

func NewPerformanceTracker(maxSamples int) *PerformanceTracker {
	if maxSamples <= 0 {
		maxSamples = 1000
	}
	return &PerformanceTracker{
		metrics:    map[string][]float64{},
		maxSamples: maxSamples,
	}
}

func (p *PerformanceTracker) Record(metricName string, value float64) {
	p.mu.Lock()
	defer p.mu.Unlock()

	values := append(p.metrics[metricName], value)
	if len(values) > p.maxSamples {
		values = values[len(values)-p.maxSamples:]
	}
	p.metrics[metricName] = values
}

func (p *PerformanceTracker) Measure(metricName string, fn func() error) error {
	start := time.Now()
	defer func() {
		elapsedMs := float64(time.Since(start).Microseconds()) / 1000.0
		p.Record(metricName, elapsedMs)
	}()
	return fn()
}

func (p *PerformanceTracker) GetStats(metricName string) (*MetricStats, bool) {
	p.mu.RLock()
	values, ok := p.metrics[metricName]
	p.mu.RUnlock()
	if !ok || len(values) == 0 {
		return nil, false
	}

	cp := append([]float64(nil), values...)
	sort.Float64s(cp)

	stats := &MetricStats{
		Count:  len(cp),
		Mean:   mean(cp),
		Median: percentileSorted(cp, 50),
		Min:    cp[0],
		Max:    cp[len(cp)-1],
		Stdev:  stdev(cp),
		P95:    percentileSorted(cp, 95),
		P99:    percentileSorted(cp, 99),
	}
	return stats, true
}

func (p *PerformanceTracker) GetAllStats() map[string]*MetricStats {
	p.mu.RLock()
	keys := make([]string, 0, len(p.metrics))
	for name := range p.metrics {
		keys = append(keys, name)
	}
	p.mu.RUnlock()

	out := make(map[string]*MetricStats, len(keys))
	for _, name := range keys {
		if s, ok := p.GetStats(name); ok {
			out[name] = s
		}
	}
	return out
}

func (p *PerformanceTracker) Clear(metricName string) {
	p.mu.Lock()
	defer p.mu.Unlock()
	if metricName == "" {
		p.metrics = map[string][]float64{}
		return
	}
	delete(p.metrics, metricName)
}

var performanceTracker = NewPerformanceTracker(1000)

func GetPerformanceTracker() *PerformanceTracker {
	return performanceTracker
}

func mean(values []float64) float64 {
	if len(values) == 0 {
		return 0
	}
	total := 0.0
	for _, v := range values {
		total += v
	}
	return total / float64(len(values))
}

func stdev(values []float64) float64 {
	if len(values) <= 1 {
		return 0
	}
	m := mean(values)
	var sum float64
	for _, v := range values {
		diff := v - m
		sum += diff * diff
	}
	return math.Sqrt(sum / float64(len(values)-1))
}

func percentileSorted(values []float64, p float64) float64 {
	if len(values) == 0 {
		return 0
	}
	if p <= 0 {
		return values[0]
	}
	if p >= 100 {
		return values[len(values)-1]
	}
	idx := int(float64(len(values)) * p / 100.0)
	if idx >= len(values) {
		idx = len(values) - 1
	}
	return values[idx]
}

