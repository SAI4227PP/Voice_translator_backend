"""Python runtime adapter for the C++ TTS daemon."""
import asyncio
import base64
import json
import os
import struct
import uuid
from typing import Optional

from app.config import get_logger, get_settings
from app.utils.exceptions import ConfigurationError, ModelLoadError, TTSError

logger = get_logger(__name__)
settings = get_settings()


SUPPORTED_TTS_LANGUAGES = {
    "en", "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok", "mai",
    "ml", "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta", "te", "ur",
}


class _CppTTSDaemonClient:
    """Shared client that manages a single persistent C++ daemon process."""

    def __init__(self) -> None:
        self.cpp_binary_path = settings.svara_tts_cpp_binary_path
        self.api_base_url = settings.svara_tts_api_base_url
        self.model_id = settings.svara_tts_model_id
        self.onnx_model_path = settings.svara_tts_onnx_model_path
        self.tokenizer_id = settings.svara_tts_tokenizer_id
        self.voice = settings.svara_tts_default_voice
        self.api_key = settings.svara_tts_api_key
        self.timeout_seconds = settings.svara_tts_timeout_seconds
        self.queue_size = settings.svara_tts_daemon_queue_size
        self.worker_count = settings.svara_tts_daemon_workers
        self.max_input_chars = settings.svara_tts_max_input_chars
        self.onnx_threads = settings.svara_tts_onnx_threads
        self.onnx_sample_rate = settings.svara_tts_onnx_sample_rate
        self.use_onnx = bool(self.onnx_model_path and self.onnx_model_path.lower().endswith(".onnx"))
        self.model_ref = self.onnx_model_path if self.use_onnx else self.model_id
        self._tokenizer = None
        self._token_cache: dict[str, tuple[str, str]] = {}
        self._token_cache_order: list[str] = []
        self._token_cache_limit = 512

        self._proc: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._pending: dict[str, asyncio.Future] = {}
        self._write_lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()
        self._stderr_tail = ""

        if not os.path.isfile(self.cpp_binary_path):
            raise ModelLoadError(f"C++ TTS engine binary not found at: {self.cpp_binary_path}")
        if self.use_onnx and not os.path.isfile(self.onnx_model_path):
            raise ModelLoadError(f"ONNX TTS model not found at: {self.onnx_model_path}")
        if self.use_onnx:
            try:
                from transformers import AutoTokenizer

                self._tokenizer = AutoTokenizer.from_pretrained(
                    self.tokenizer_id,
                    trust_remote_code=True,
                    use_fast=True,
                )
                for phrase in ("नमस्ते", "hello", "how are you", "thank you"):
                    self._tokenize_for_onnx(phrase)
            except Exception as exc:
                raise ModelLoadError(f"Failed to load HF tokenizer ({self.tokenizer_id}): {exc}") from exc

    @staticmethod
    def _encode_i64_b64(values: list[int]) -> str:
        if not values:
            return ""
        payload = struct.pack(f"<{len(values)}q", *values)
        return base64.b64encode(payload).decode("ascii")

    def _tokenize_for_onnx(self, text: str) -> Optional[tuple[str, str]]:
        if not self.use_onnx or self._tokenizer is None or not text:
            return None
        cached = self._token_cache.get(text)
        if cached is not None:
            return cached

        encoded = self._tokenizer(
            text,
            return_attention_mask=True,
            add_special_tokens=True,
        )
        token_ids = [int(x) for x in encoded.get("input_ids", [])]
        attention = [int(x) for x in encoded.get("attention_mask", [])]
        if not token_ids or len(token_ids) != len(attention):
            return None
        packed = (
            self._encode_i64_b64(token_ids),
            self._encode_i64_b64(attention),
        )
        self._token_cache[text] = packed
        self._token_cache_order.append(text)
        if len(self._token_cache_order) > self._token_cache_limit:
            old = self._token_cache_order.pop(0)
            self._token_cache.pop(old, None)
        return packed

    async def _ensure_started(self) -> None:
        if self._proc and self._proc.returncode is None:
            return

        async with self._start_lock:
            if self._proc and self._proc.returncode is None:
                return

            validate_cmd = [
                self.cpp_binary_path,
                "validate",
                self.api_base_url if not self.use_onnx else "-",
                self.model_ref,
            ]
            proc = await asyncio.create_subprocess_exec(
                *validate_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            v_out, v_err = await asyncio.wait_for(proc.communicate(), timeout=self.timeout_seconds)
            if proc.returncode != 0:
                raise ModelLoadError(
                    f"C++ TTS engine validation failed: {v_err.decode('utf-8', errors='ignore').strip()}"
                )

            daemon_cmd = [
                self.cpp_binary_path,
                "daemon",
                self.api_base_url if not self.use_onnx else "-",
                self.model_ref,
                self.voice,
                str(self.timeout_seconds),
                str(self.queue_size),
                str(self.worker_count),
                str(self.max_input_chars),
                self.api_key or "-",
                str(self.onnx_threads),
                str(self.onnx_sample_rate),
            ]
            self._proc = await asyncio.create_subprocess_exec(
                *daemon_cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._reader_task = asyncio.create_task(self._reader_loop())
            self._stderr_task = asyncio.create_task(self._stderr_loop())
            logger.info("tts_daemon_started", pid=self._proc.pid)

    async def _stderr_loop(self) -> None:
        assert self._proc is not None
        assert self._proc.stderr is not None
        while True:
            chunk = await self._proc.stderr.read(1024)
            if not chunk:
                break
            txt = chunk.decode("utf-8", errors="ignore")
            self._stderr_tail = (self._stderr_tail + txt)[-4000:]

    async def _reader_loop(self) -> None:
        assert self._proc is not None
        assert self._proc.stdout is not None
        try:
            while True:
                line = await self._proc.stdout.readline()
                if not line:
                    break
                line_txt = line.decode("utf-8", errors="ignore").strip()
                if not line_txt:
                    continue
                try:
                    payload = json.loads(line_txt)
                except json.JSONDecodeError:
                    continue

                req_id = payload.get("id", "")
                fut = self._pending.pop(req_id, None)
                if fut and not fut.done():
                    fut.set_result(payload)
        finally:
            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(TTSError(f"tts daemon exited: {self._stderr_tail[:300]}"))
            self._pending.clear()

    async def request(self, cmd: str, language: str = "", text: str = "") -> dict:
        await self._ensure_started()
        if not self._proc or self._proc.returncode is not None or not self._proc.stdin:
            raise TTSError("tts daemon is not running")

        req_id = uuid.uuid4().hex
        payload = {"id": req_id, "cmd": cmd, "language": language}
        if text:
            payload["text_b64"] = base64.b64encode(text.encode("utf-8")).decode("ascii")
            packed = self._tokenize_for_onnx(text)
            if packed is not None:
                payload["token_ids_i64_b64"] = packed[0]
                payload["attention_mask_i64_b64"] = packed[1]

        fut = asyncio.get_running_loop().create_future()
        self._pending[req_id] = fut

        body = (json.dumps(payload, ensure_ascii=False) + "\n").encode("utf-8")
        async with self._write_lock:
            self._proc.stdin.write(body)
            await self._proc.stdin.drain()

        try:
            return await asyncio.wait_for(fut, timeout=self.timeout_seconds)
        except Exception:
            self._pending.pop(req_id, None)
            raise


class CppTTSEngine:
    """Language-bound TTS engine wrapper."""

    def __init__(self, language: str, daemon: _CppTTSDaemonClient):
        self.language = language
        self._daemon = daemon

    async def synthesize_async(self, text: str) -> bytes:
        return await self.synthesize_to_bytes_async(text)

    async def synthesize_to_bytes_async(self, text: str) -> bytes:
        if self.language not in SUPPORTED_TTS_LANGUAGES:
            raise TTSError(f"Unsupported TTS language: {self.language}")
        payload = await self._daemon.request("synthesize", language=self.language, text=text)
        if payload.get("status") != "ok":
            raise TTSError(payload.get("error") or payload.get("stderr_snippet") or "tts_failed")
        audio_b64 = str(payload.get("audio_b64", ""))
        if not audio_b64:
            return b""
        try:
            return base64.b64decode(audio_b64)
        except Exception as exc:
            raise TTSError(f"invalid_audio_payload: {exc}") from exc


class TTSFactory:
    """Factory for C++ TTS engines."""

    _engines: dict[str, CppTTSEngine] = {}
    _daemon: Optional[_CppTTSDaemonClient] = None

    @classmethod
    def _get_daemon(cls) -> _CppTTSDaemonClient:
        if cls._daemon is None:
            cls._daemon = _CppTTSDaemonClient()
        return cls._daemon

    @classmethod
    def create(cls, engine_type: str = "svara", language: str = "en", model_name: Optional[str] = None) -> CppTTSEngine:
        if engine_type.lower() != "svara":
            raise ConfigurationError(f"Unsupported TTS engine: {engine_type}. Only 'svara' is supported.")
        key = f"{engine_type}_{language}_{model_name or 'default'}"
        if key in cls._engines:
            return cls._engines[key]
        engine = CppTTSEngine(language=language, daemon=cls._get_daemon())
        cls._engines[key] = engine
        return engine

    @classmethod
    def get_engine(cls, language: str = "en") -> CppTTSEngine:
        return cls.create(settings.tts_engine, language)

    @classmethod
    def preload_engines(cls, languages: list[str]) -> dict[str, bool]:
        result: dict[str, bool] = {}
        for language in languages:
            try:
                cls.get_engine(language)
                result[language] = True
            except Exception:
                result[language] = False
        return result

    @classmethod
    def clear_cache(cls) -> None:
        cls._engines.clear()


_tts_factory: Optional[TTSFactory] = None


def get_tts_factory() -> TTSFactory:
    global _tts_factory
    if _tts_factory is None:
        _tts_factory = TTSFactory()
    return _tts_factory
