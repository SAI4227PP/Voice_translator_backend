"""
Script to download required models for the voice translator.
Downloads Vosk STT models and verifies local Svara ONNX model path.
"""
import asyncio
import sys
import time
import zipfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple

try:
    import aiohttp
    from tqdm import tqdm
except ImportError:
    print("\nMissing required packages: aiohttp, tqdm")
    print("Install with: pip install aiohttp tqdm")
    sys.exit(1)


class ParallelDownloader:
    """Parallel downloader with progress tracking."""

    def __init__(self, max_concurrent: int = 3, chunk_size: int = 8192):
        self.max_concurrent = max_concurrent
        self.chunk_size = chunk_size
        self.session: Optional[aiohttp.ClientSession] = None

    async def __aenter__(self):
        connector = aiohttp.TCPConnector(limit=self.max_concurrent)
        timeout = aiohttp.ClientTimeout(total=3600)
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()

    async def download_file(self, url: str, destination: Path, description: str, pbar: tqdm) -> bool:
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    pbar.write(f"x {description}: HTTP {response.status}")
                    pbar.update(1)
                    return False

                total_size = int(response.headers.get("content-length", 0))
                destination.parent.mkdir(parents=True, exist_ok=True)

                file_pbar = tqdm(total=total_size, unit="B", unit_scale=True, desc=description, leave=False)
                with open(destination, "wb") as f:
                    async for chunk in response.content.iter_chunked(self.chunk_size):
                        f.write(chunk)
                        file_pbar.update(len(chunk))
                file_pbar.close()
                pbar.write(f"ok {description}")
                pbar.update(1)
                return True
        except Exception as e:
            pbar.write(f"x {description}: {str(e)[:80]}")
            pbar.update(1)
            return False

    async def download_multiple(self, downloads: List[Tuple[str, Path, str]]) -> Dict[str, bool]:
        results: Dict[str, bool] = {}
        pbar = tqdm(total=len(downloads), desc="Overall Progress", unit="file")
        sem = asyncio.Semaphore(self.max_concurrent)

        async def worker(url: str, dest: Path, desc: str):
            async with sem:
                results[desc] = await self.download_file(url, dest, desc, pbar)

        await asyncio.gather(*[worker(url, dest, desc) for url, dest, desc in downloads])
        pbar.close()
        return results


async def download_vosk_models() -> None:
    print("\n" + "=" * 60)
    print("Downloading Vosk STT Models")
    print("=" * 60)

    models_dir = Path("models/stt")
    models_dir.mkdir(parents=True, exist_ok=True)

    models = {
        "en": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
            "extracted_name": "vosk-model-small-en-us-0.15",
            "display_name": "English",
        },
        "hi": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-hi-0.22.zip",
            "extracted_name": "vosk-model-hi-0.22",
            "display_name": "Hindi",
        },
        "te": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-te-0.42.zip",
            "extracted_name": "vosk-model-small-te-0.42",
            "display_name": "Telugu",
        },
        "gu": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-gu-0.42.zip",
            "extracted_name": "vosk-model-small-gu-0.42",
            "display_name": "Gujarati",
        },
        "bn": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-en-in-0.5.zip",
            "extracted_name": "vosk-model-en-in-0.5",
            "display_name": "Bengali (Indian English)",
        },
    }

    downloads: List[Tuple[str, Path, str]] = []
    for lang_code, model in models.items():
        target_dir = models_dir / f"vosk-{lang_code}"
        if target_dir.exists():
            continue
        downloads.append((model["url"], models_dir / f"vosk-model-{lang_code}.zip", f"Vosk {model['display_name']}"))

    if downloads:
        async with ParallelDownloader(max_concurrent=3) as downloader:
            results = await downloader.download_multiple(downloads)
    else:
        results = {}
        print("All Vosk models already exist.")

    print("\nExtracting models...")
    extraction_pbar = tqdm(total=len(models), desc="Extraction", unit="model")
    for lang_code, model in models.items():
        target_dir = models_dir / f"vosk-{lang_code}"
        zip_path = models_dir / f"vosk-model-{lang_code}.zip"

        if target_dir.exists():
            extraction_pbar.update(1)
            continue
        if downloads and not results.get(f"Vosk {model['display_name']}", False):
            extraction_pbar.update(1)
            continue
        if not zip_path.exists():
            extraction_pbar.update(1)
            continue

        try:
            with zipfile.ZipFile(zip_path, "r") as zf:
                zf.extractall(models_dir)
            extracted = models_dir / model["extracted_name"]
            if extracted.exists():
                extracted.rename(target_dir)
            zip_path.unlink(missing_ok=True)
        except Exception as e:
            print(f"x Failed to extract {model['display_name']}: {str(e)[:80]}")
        extraction_pbar.update(1)

    extraction_pbar.close()


def setup_tts_models() -> None:
    print("\n" + "=" * 60)
    print("TTS Model Setup")
    print("=" * 60)

    tts_dir = Path("models/tts/svara")
    tts_dir.mkdir(parents=True, exist_ok=True)
    onnx_path = tts_dir / "svara_tts.onnx"
    if onnx_path.exists():
        print(f"Found local ONNX model: {onnx_path}")
    else:
        print("Missing local ONNX model for TTS.")
        print("Generate it with:")
        print("python scripts/export_svara_onnx.py --model-id kenpath/svara-tts-v1 --output models/tts/svara/svara_tts.onnx")


def check_existing_models() -> Tuple[bool, List[str]]:
    missing: List[str] = []
    models_dir = Path("models/stt")
    required_vosk = ["vosk-en", "vosk-hi", "vosk-te", "vosk-gu", "vosk-bn"]
    for lang in required_vosk:
        if not (models_dir / lang).exists():
            missing.append(f"Vosk {lang}")

    return len(missing) == 0, missing


async def main() -> None:
    print("\n" + "=" * 70)
    print("Voice-to-Voice Translator Model Downloader")
    print("=" * 70)

    Path("models").mkdir(exist_ok=True)

    all_exist, missing = check_existing_models()
    # Always validate local TTS ONNX presence, even when STT models already exist.
    setup_tts_models()
    if all_exist:
        print("All required STT model directories already exist.")
        return

    print(f"Missing items: {len(missing)}")
    for item in missing:
        print(f"- {item}")

    start_time = time.time()
    await download_vosk_models()

    elapsed = int(time.time() - start_time)
    mins, secs = divmod(elapsed, 60)
    print("\n" + "=" * 70)
    print(f"Done in {mins}m {secs}s")
    print("Translation engine: Sarvam (no Argos package download)")
    print("TTS ONNX is expected from app image build path (/app/tts-models/svara_tts.onnx) in Docker runtime.")


if __name__ == "__main__":
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
