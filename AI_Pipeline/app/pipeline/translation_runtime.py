"""Python integration layer for the C++ translation daemon."""
import asyncio
import base64
import json
import os
import time
import uuid
from typing import Optional

from app.config import get_logger, get_settings
from app.utils.exceptions import ConfigurationError, ModelLoadError, TranslationError

logger = get_logger(__name__)
settings = get_settings()

SUPPORTED_INDIAN_LANGUAGES = [
    "en",
    "as", "bn", "brx", "doi", "gu", "hi", "kn", "ks", "kok", "mai", "ml",
    "mni", "mr", "ne", "or", "pa", "sa", "sat", "sd", "ta", "te", "ur",
]
SUPPORTED_INDIAN_LANGUAGE_SET = set(SUPPORTED_INDIAN_LANGUAGES)


class SarvamEngine:
    """Thin adapter over the persistent C++ translation daemon."""

    def __init__(self):
        self.cpp_binary_path = settings.sarvam_cpp_binary_path
        self.llama_cpp_path = settings.llama_cpp_path
        self.llama_cli_path = settings.llama_cli_path or "-"
        self.model_path = settings.sarvam_model_path
        self.max_tokens = settings.sarvam_max_tokens
        self.context_size = settings.sarvam_context_size
        self.threads = settings.sarvam_threads
        self.timeout_seconds = settings.sarvam_timeout_seconds
        self.daemon_workers = settings.sarvam_daemon_workers
        self.daemon_queue_size = settings.sarvam_daemon_queue_size
        self.max_input_chars = settings.sarvam_max_input_chars
        self.gpu_layers = settings.sarvam_gpu_layers
        self.server_port = settings.llama_server_port

        self.retry_count = settings.translation_retry_count
        self.retry_backoff_ms = settings.translation_retry_backoff_ms
        self.breaker_threshold = settings.translation_circuit_breaker_threshold
        self.breaker_reset_seconds = settings.translation_circuit_breaker_reset_seconds

        self._consecutive_failures = 0
        self._breaker_open_until = 0.0

        self._proc: Optional[asyncio.subprocess.Process] = None
        self._reader_task: Optional[asyncio.Task] = None
        self._stderr_task: Optional[asyncio.Task] = None
        self._pending: dict[str, asyncio.Future] = {}
        self._write_lock = asyncio.Lock()
        self._start_lock = asyncio.Lock()
        self._stderr_tail = ""

        if not os.path.isfile(self.cpp_binary_path):
            raise ModelLoadError(f"C++ translation engine binary not found at: {self.cpp_binary_path}")

    async def _ensure_started(self) -> None:
        if self._proc and self._proc.returncode is None:
            return

        async with self._start_lock:
            if self._proc and self._proc.returncode is None:
                return

            validate_cmd = [
                self.cpp_binary_path,
                "validate",
                self.llama_cpp_path,
                self.llama_cli_path,
                self.model_path,
            ]
            p = await asyncio.create_subprocess_exec(
                *validate_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            v_out, v_err = await asyncio.wait_for(p.communicate(), timeout=self.timeout_seconds)
            if p.returncode != 0:
                raise ModelLoadError(
                    f"C++ translation engine validation failed: {v_err.decode('utf-8', errors='ignore').strip()}"
                )

            cmd = [
                self.cpp_binary_path,
                "daemon",
                self.llama_cpp_path,
                self.llama_cli_path,
                self.model_path,
                str(self.max_tokens),
                str(self.context_size),
                str(self.threads),
                str(self.gpu_layers),
                str(self.daemon_queue_size),
                str(self.daemon_workers),
                str(self.max_input_chars),
                str(self.server_port),
            ]

            self._proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            self._reader_task = asyncio.create_task(self._reader_loop())
            self._stderr_task = asyncio.create_task(self._stderr_loop())
            logger.info("translation_daemon_started", pid=self._proc.pid)

    async def _stderr_loop(self) -> None:
        assert self._proc is not None
        assert self._proc.stderr is not None
        while True:
            chunk = await self._proc.stderr.read(1024)
            if not chunk:
                break
            text = chunk.decode("utf-8", errors="ignore")
            self._stderr_tail = (self._stderr_tail + text)[-4000:]

    async def _reader_loop(self) -> None:
        assert self._proc is not None
        assert self._proc.stdout is not None

        try:
            while True:
                line = await self._proc.stdout.readline()
                if not line:
                    break
                line_text = line.decode("utf-8", errors="ignore").strip()
                if not line_text:
                    continue
                try:
                    payload = json.loads(line_text)
                except json.JSONDecodeError:
                    continue

                req_id = payload.get("id", "")
                fut = self._pending.pop(req_id, None)
                if fut and not fut.done():
                    fut.set_result(payload)
        finally:
            err_text = self._stderr_tail

            for fut in self._pending.values():
                if not fut.done():
                    fut.set_exception(TranslationError(f"translation daemon exited: {err_text[:300]}"))
            self._pending.clear()

    async def _send_request(self, cmd: str, source: str = "", target: str = "", text: str = "", texts: Optional[list[str]] = None) -> dict:
        await self._ensure_started()

        if not self._proc or self._proc.returncode is not None or not self._proc.stdin:
            raise TranslationError("translation daemon is not running")

        req_id = uuid.uuid4().hex
        payload = {
            "id": req_id,
            "cmd": cmd,
            "source": source,
            "target": target,
        }

        if text:
            payload["text_b64"] = base64.b64encode(text.encode("utf-8")).decode("ascii")
        if texts is not None:
            blob = "\0".join(texts).encode("utf-8")
            payload["batch_b64"] = base64.b64encode(blob).decode("ascii")

        loop = asyncio.get_running_loop()
        fut = loop.create_future()
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

    def _is_circuit_open(self) -> bool:
        return time.monotonic() < self._breaker_open_until

    def _on_success(self) -> None:
        self._consecutive_failures = 0
        self._breaker_open_until = 0.0

    def _on_failure(self) -> None:
        self._consecutive_failures += 1
        if self._consecutive_failures >= self.breaker_threshold:
            self._breaker_open_until = time.monotonic() + self.breaker_reset_seconds

    async def _execute_with_resilience(self, fn):
        if self._is_circuit_open():
            raise TranslationError("translation circuit breaker is open")

        last_exc: Optional[Exception] = None
        for attempt in range(self.retry_count + 1):
            try:
                result = await fn()
                self._on_success()
                return result
            except Exception as e:
                last_exc = e
                self._on_failure()
                if attempt >= self.retry_count:
                    break
                backoff = (self.retry_backoff_ms * (2 ** attempt)) / 1000.0
                await asyncio.sleep(backoff)

        raise TranslationError(f"translation request failed after retries: {last_exc}")

    async def translate_async(self, text: str, source_lang: str, target_lang: str) -> str:
        async def _do():
            if not self.is_language_pair_available(source_lang, target_lang):
                raise TranslationError("Only 22 Indian languages are supported for translation")
            payload = await self._send_request("translate", source=source_lang, target=target_lang, text=text)
            if payload.get("status") != "ok":
                raise TranslationError(payload.get("error") or payload.get("stderr_snippet") or "translation_failed")
            return str(payload.get("translated_text", "")).strip()

        return await self._execute_with_resilience(_do)

    async def batch_translate_async(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        async def _do():
            if not self.is_language_pair_available(source_lang, target_lang):
                raise TranslationError("Only 22 Indian languages are supported for translation")
            payload = await self._send_request("batch_translate", source=source_lang, target=target_lang, texts=texts)
            if payload.get("status") != "ok":
                raise TranslationError(payload.get("error") or payload.get("stderr_snippet") or "batch_translate_failed")
            items = payload.get("translated_items")
            if isinstance(items, list):
                return [str(x) for x in items]
            raw = str(payload.get("translated_text", ""))
            return [] if not raw else raw.split("\0")

        return await self._execute_with_resilience(_do)

    def get_available_languages(self) -> list[str]:
        return SUPPORTED_INDIAN_LANGUAGES

    def is_language_pair_available(self, source_lang: str, target_lang: str) -> bool:
        return (
            bool(source_lang and target_lang) and
            source_lang in SUPPORTED_INDIAN_LANGUAGE_SET and
            target_lang in SUPPORTED_INDIAN_LANGUAGE_SET
        )

    async def install_language_pair(self, source_lang: str, target_lang: str) -> bool:
        return self.is_language_pair_available(source_lang, target_lang)

    def warm_up(self) -> None:
        async def _warm():
            payload = await self._send_request("warm_up")
            if payload.get("status") != "ok":
                raise TranslationError(payload.get("error") or "warm_up_failed")

        try:
            asyncio.get_running_loop()
            asyncio.create_task(_warm())
        except RuntimeError:
            asyncio.run(_warm())

    def warm_up_common_pairs(self, pairs: list[tuple[str, str]]) -> None:
        self.warm_up()


class Translator:
    """Translator facade used by pipeline and API layers."""

    def __init__(self):
        if settings.translation_engine.lower() != "sarvam":
            raise ConfigurationError(
                f"Unsupported translation engine: {settings.translation_engine}. Only 'sarvam' is supported."
            )
        self.engine = SarvamEngine()

    async def translate(self, text: str, source_lang: str, target_lang: str) -> str:
        return await self.engine.translate_async(text, source_lang, target_lang)

    async def batch_translate(self, texts: list[str], source_lang: str, target_lang: str) -> list[str]:
        return await self.engine.batch_translate_async(texts, source_lang, target_lang)

    def get_available_languages(self) -> list[str]:
        return self.engine.get_available_languages()

    def is_language_pair_supported(self, source_lang: str, target_lang: str) -> bool:
        return self.engine.is_language_pair_available(source_lang, target_lang)

    def warm_up(self) -> None:
        self.engine.warm_up()

    def warm_up_common_pairs(self, pairs: list[tuple[str, str]]) -> None:
        self.engine.warm_up_common_pairs(pairs)


_translator: Optional[Translator] = None


def get_translator() -> Translator:
    global _translator
    if _translator is None:
        _translator = Translator()
    return _translator
