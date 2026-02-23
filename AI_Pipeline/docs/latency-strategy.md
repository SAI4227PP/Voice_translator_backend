# Latency Optimization Strategy

## Latency Budget

Target end-to-end latency: **< 500ms**

### Component Breakdown

| Component | Target Latency | Optimization Level |
|-----------|---------------|-------------------|
| Network RTT | 20-50ms | Infrastructure |
| Audio Buffering | 50-100ms | Application |
| STT Processing | 100-200ms | Model/Code |
| Translation | 30-80ms | Model/Code |
| TTS Generation | 150-300ms | Model/Code |
| Audio Playback Buffer | 50-100ms | Application |
| **Total** | **400-830ms** | **Target: <500ms** |

## Optimization Strategies

### 1. Network Layer Optimizations

#### WebSocket Configuration
- **Keep-Alive**: Enable TCP keep-alive to prevent connection drops
- **No-Delay**: Disable Nagle's algorithm for immediate packet sending
```python
# In websocket_server.py
websocket_settings = {
    'ping_interval': 20,  # Seconds
    'ping_timeout': 10,
    'max_size': 10 * 1024 * 1024,  # 10MB
    'compression': None  # Disable compression for latency
}
```

#### Binary Protocol
- Use binary frames for audio (no JSON overhead)
- Pack metadata efficiently in headers
- Avoid string encoding/decoding in hot path

#### Connection Pooling
- Reuse connections where possible
- Pre-establish internal service connections
- Use connection multiplexing

### 2. Audio Buffering Strategy

#### Adaptive Buffering
```python
# Dynamic buffer sizing based on network conditions
class AdaptiveBuffer:
    def __init__(self):
        self.min_buffer = 50  # ms
        self.max_buffer = 200  # ms
        self.current_buffer = 100  # ms
        
    def adjust(self, jitter, packet_loss):
        if jitter > 30 or packet_loss > 0.01:
            self.current_buffer = min(self.max_buffer, 
                                     self.current_buffer + 10)
        else:
            self.current_buffer = max(self.min_buffer,
                                     self.current_buffer - 5)
```

#### Chunk Size Optimization
- Smaller chunks = lower latency, higher overhead
- Larger chunks = higher latency, lower overhead
- **Sweet spot**: 100-200ms chunks (1600-3200 bytes at 16kHz)

```python
OPTIMAL_CHUNK_SIZE = 3200  # bytes (100ms at 16kHz PCM16)
```

### 3. STT Engine Optimizations

#### Vosk-Specific
- **Partial Results**: Enable and use intermediate results
- **Model Selection**: Use small models for real-time (trade accuracy for speed)
- **Thread Pool**: Pre-allocate recognizer instances

```python
# vosk_engine.py optimization
class VoskEngine:
    def __init__(self, model_path, num_instances=4):
        self.recognizers = [
            KaldiRecognizer(model, 16000) 
            for _ in range(num_instances)
        ]
        self.recognizer_pool = Queue()
        for rec in self.recognizers:
            self.recognizer_pool.put(rec)
    
    def recognize_streaming(self, audio_chunk):
        recognizer = self.recognizer_pool.get()
        try:
            recognizer.AcceptWaveform(audio_chunk)
            result = recognizer.PartialResult()  # Don't wait for final
            return json.loads(result)
        finally:
            self.recognizer_pool.put(recognizer)
```

#### Model Loading
- Load models at startup (not on first use)
- Use memory-mapped files
- Keep models in RAM

```python
# Warm-up on startup
async def warmup_models():
    dummy_audio = np.zeros(16000, dtype=np.int16)
    await stt_engine.recognize(dummy_audio)
```

### 4. Translation Engine Optimizations

#### Argos Translate
- **Batching**: Translate multiple sentences together when possible
- **Caching**: Cache common phrases (LRU cache)
- **Async Processing**: Don't block on translation

```python
from functools import lru_cache

@lru_cache(maxsize=1000)
def translate_cached(text, source_lang, target_lang):
    return translator.translate(text, source_lang, target_lang)
```

#### Streaming Translation
```python
# Translate as words arrive, don't wait for full sentence
async def streaming_translate(text_stream):
    buffer = []
    async for word in text_stream:
        buffer.append(word)
        if is_sentence_boundary(word):
            translated = await translate(' '.join(buffer))
            yield translated
            buffer = []
```

### 5. TTS Engine Optimizations

#### Coqui TTS
- **Streaming Synthesis**: Generate audio in chunks
- **Model Selection**: Use faster models (FastSpeech2 vs Tacotron)
- **GPU Acceleration**: Use CUDA if available

```python
# tts_factory.py
class CoquiEngine:
    def __init__(self, model_path, use_gpu=True):
        self.tts = TTS(model_path)
        if use_gpu and torch.cuda.is_available():
            self.tts.to('cuda')
    
    def synthesize_streaming(self, text):
        # Generate audio in chunks
        for sentence in split_sentences(text):
            audio_chunk = self.tts.tts(sentence)
            yield audio_chunk
```

#### Audio Quality Trade-offs
- Lower sample rate for faster generation (22kHz vs 44kHz)
- Reduce vocoder quality settings
- Use simpler voice models

### 6. Pipeline Parallelization

#### Concurrent Processing
```python
# pipeline_manager.py
async def process_audio_pipeline(audio_data, source_lang, target_lang):
    # Start STT immediately
    stt_task = asyncio.create_task(stt_engine.recognize(audio_data))
    
    # Wait for STT result
    text = await stt_task
    
    # Run translation and TTS preparation in parallel
    translate_task = asyncio.create_task(
        translator.translate(text, source_lang, target_lang)
    )
    
    # Preload TTS model while translating
    tts_prepare_task = asyncio.create_task(
        tts_engine.prepare(target_lang)
    )
    
    translated_text = await translate_task
    await tts_prepare_task
    
    # Generate audio
    audio_output = await tts_engine.synthesize(translated_text)
    
    return audio_output
```

#### Worker Pool Pattern
```python
# workers/translation_worker.py
class TranslationWorkerPool:
    def __init__(self, num_workers=4):
        self.queue = asyncio.Queue()
        self.workers = [
            asyncio.create_task(self._worker())
            for _ in range(num_workers)
        ]
    
    async def _worker(self):
        while True:
            task = await self.queue.get()
            result = await self._process(task)
            task.callback(result)
    
    async def submit(self, audio_data, callback):
        await self.queue.put(Task(audio_data, callback))
```

### 7. Memory Management

#### Buffer Pools
```python
# audio/audio_buffer.py
class AudioBufferPool:
    def __init__(self, buffer_size, pool_size=20):
        self.pool = [
            bytearray(buffer_size) 
            for _ in range(pool_size)
        ]
        self.available = Queue()
        for buf in self.pool:
            self.available.put(buf)
    
    def acquire(self):
        if self.available.empty():
            return bytearray(self.buffer_size)
        return self.available.get()
    
    def release(self, buffer):
        buffer[:] = b'\x00' * len(buffer)  # Clear
        self.available.put(buffer)
```

#### Garbage Collection Tuning
```python
# main.py
import gc

# Reduce GC frequency in hot path
gc.set_threshold(700, 10, 10)  # Default: 700, 10, 10

# Or disable GC during processing
async def process_with_gc_control(data):
    gc.disable()
    try:
        result = await process(data)
    finally:
        gc.enable()
    return result
```

### 8. Caching Strategies

#### Multi-Level Caching
```python
# Three-tier cache
class TranslationCache:
    def __init__(self):
        self.memory_cache = LRUCache(maxsize=1000)  # Hot data
        self.redis_cache = RedisClient()  # Warm data
        self.db_cache = Database()  # Cold data
    
    async def get(self, key):
        # Try memory first
        if key in self.memory_cache:
            return self.memory_cache[key]
        
        # Try Redis
        value = await self.redis_cache.get(key)
        if value:
            self.memory_cache[key] = value
            return value
        
        # Try database
        value = await self.db_cache.get(key)
        if value:
            await self.redis_cache.set(key, value)
            self.memory_cache[key] = value
        
        return value
```

#### Common Phrase Cache
```python
# Cache frequently translated phrases
COMMON_PHRASES = {
    'en': {
        'hello': {'hi': 'नमस्ते', 'es': 'hola'},
        'thank you': {'hi': 'धन्यवाद', 'es': 'gracias'},
        # ... more phrases
    }
}
```

### 9. CPU/GPU Optimization

#### Model Quantization
```python
# Reduce model size and inference time
import torch

model = torch.load('model.pth')
quantized_model = torch.quantization.quantize_dynamic(
    model, {torch.nn.Linear}, dtype=torch.qint8
)
```

#### Multi-Threading
```python
# Use thread pool for CPU-bound tasks
from concurrent.futures import ThreadPoolExecutor

executor = ThreadPoolExecutor(max_workers=4)

async def process_audio_threaded(audio_data):
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(
        executor, 
        cpu_intensive_task, 
        audio_data
    )
    return result
```

#### GPU Batching
```python
# Batch multiple requests for GPU efficiency
class GPUBatcher:
    def __init__(self, batch_size=8, timeout=0.01):
        self.batch_size = batch_size
        self.timeout = timeout
        self.batch = []
    
    async def process(self, data):
        self.batch.append(data)
        
        if len(self.batch) >= self.batch_size:
            return await self._flush()
        
        await asyncio.sleep(self.timeout)
        if self.batch:
            return await self._flush()
    
    async def _flush(self):
        results = await model.process_batch(self.batch)
        self.batch = []
        return results
```

### 10. Monitoring and Profiling

#### Latency Tracking
```python
# utils/timers.py
class LatencyTracker:
    def __init__(self):
        self.metrics = defaultdict(list)
    
    @contextmanager
    def track(self, component):
        start = time.perf_counter()
        try:
            yield
        finally:
            duration = (time.perf_counter() - start) * 1000
            self.metrics[component].append(duration)
            
            # Alert if over budget
            if duration > LATENCY_BUDGETS[component]:
                logger.warning(
                    f"{component} exceeded budget: {duration:.2f}ms"
                )
```

#### Usage Example
```python
latency_tracker = LatencyTracker()

async def process_pipeline(audio):
    with latency_tracker.track('stt'):
        text = await stt_engine.recognize(audio)
    
    with latency_tracker.track('translation'):
        translated = await translator.translate(text)
    
    with latency_tracker.track('tts'):
        audio_out = await tts_engine.synthesize(translated)
    
    return audio_out
```

### 11. Network-Specific Optimizations

#### Adaptive Bitrate
```python
class AdaptiveBitrateController:
    def adjust_quality(self, bandwidth, latency):
        if bandwidth < 50_000:  # < 50 Kbps
            return AudioQuality.LOW
        elif bandwidth < 100_000:
            return AudioQuality.MEDIUM
        else:
            return AudioQuality.HIGH
```

#### Predictive Buffering
```python
# Predict network jitter and adjust buffer
class PredictiveBuffer:
    def __init__(self):
        self.jitter_history = deque(maxlen=100)
    
    def calculate_buffer_size(self):
        if not self.jitter_history:
            return DEFAULT_BUFFER_SIZE
        
        avg_jitter = statistics.mean(self.jitter_history)
        std_jitter = statistics.stdev(self.jitter_history)
        
        # Buffer = avg + 2*std for 95% coverage
        return int(avg_jitter + 2 * std_jitter)
```

## Performance Benchmarks

### Target Metrics
- **P50 Latency**: < 400ms
- **P95 Latency**: < 600ms
- **P99 Latency**: < 800ms
- **Throughput**: > 100 concurrent users per server

### Measurement Tools
```python
# Performance testing
import time
import statistics

async def benchmark_pipeline(iterations=100):
    latencies = []
    
    for _ in range(iterations):
        start = time.perf_counter()
        await process_audio_pipeline(test_audio)
        latency = (time.perf_counter() - start) * 1000
        latencies.append(latency)
    
    print(f"P50: {statistics.median(latencies):.2f}ms")
    print(f"P95: {np.percentile(latencies, 95):.2f}ms")
    print(f"P99: {np.percentile(latencies, 99):.2f}ms")
```

## Production Checklist

- [ ] Enable WebSocket compression only for non-audio messages
- [ ] Use binary protocol for audio streaming
- [ ] Implement adaptive buffering
- [ ] Pre-load and warm up all models
- [ ] Enable model caching (LRU cache)
- [ ] Use GPU acceleration where available
- [ ] Implement connection pooling
- [ ] Configure optimal chunk sizes
- [ ] Enable latency monitoring
- [ ] Set up alerting for latency SLA breaches
- [ ] Profile hot paths regularly
- [ ] Optimize garbage collection
- [ ] Use worker pools for parallelization
- [ ] Implement graceful degradation
