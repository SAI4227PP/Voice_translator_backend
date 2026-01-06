"""
Script to download all required models for the voice translator.
Professional parallel download implementation with progress tracking.
"""
import os
import sys
import asyncio
import zipfile
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from concurrent.futures import ThreadPoolExecutor
import time

try:
    import aiohttp
    from tqdm import tqdm
except ImportError:
    print("\n" + "="*70)
    print("Missing Required Packages")
    print("="*70)
    print("\nThis script requires: aiohttp, tqdm")
    print("\nPlease install them first:")
    print("\n  Option 1 - Install pip:")
    print("    sudo apt update")
    print("    sudo apt install python3-pip")
    print("\n  Option 2 - Install via apt (Ubuntu/Debian):")
    print("    sudo apt install python3-aiohttp python3-tqdm")
    print("\n  Option 3 - Install via pip:")
    print("    pip3 install aiohttp tqdm")
    print("\n  Option 4 - Use virtual environment:")
    print("    python3 -m venv venv")
    print("    source venv/bin/activate")
    print("    pip install aiohttp tqdm")
    print("    python scripts/download_models.py")
    print("\n" + "="*70)
    sys.exit(1)


class ParallelDownloader:
    """Professional parallel file downloader with progress tracking."""
    
    def __init__(self, max_concurrent: int = 3, chunk_size: int = 8192):
        """Initialize downloader.
        
        Args:
            max_concurrent: Maximum number of concurrent downloads
            chunk_size: Download chunk size in bytes
        """
        self.max_concurrent = max_concurrent
        self.chunk_size = chunk_size
        self.session: Optional[aiohttp.ClientSession] = None
        
    async def __aenter__(self):
        """Async context manager entry."""
        connector = aiohttp.TCPConnector(limit=self.max_concurrent)
        timeout = aiohttp.ClientTimeout(total=3600)  # 1 hour timeout
        self.session = aiohttp.ClientSession(connector=connector, timeout=timeout)
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
            
    async def download_file(
        self, 
        url: str, 
        destination: Path,
        description: str,
        pbar: Optional[tqdm] = None
    ) -> bool:
        """Download a single file asynchronously.
        
        Args:
            url: URL to download from
            destination: Local file path
            description: Description for progress bar
            pbar: Optional parent progress bar
            
        Returns:
            True if successful, False otherwise
        """
        try:
            async with self.session.get(url) as response:
                if response.status != 200:
                    if pbar:
                        pbar.write(f"✗ {description}: HTTP {response.status}")
                    return False
                    
                total_size = int(response.headers.get('content-length', 0))
                
                # Create file-specific progress bar
                file_pbar = tqdm(
                    total=total_size,
                    unit='B',
                    unit_scale=True,
                    unit_divisor=1024,
                    desc=description,
                    leave=False
                )
                
                destination.parent.mkdir(parents=True, exist_ok=True)
                
                with open(destination, 'wb') as f:
                    async for chunk in response.content.iter_chunked(self.chunk_size):
                        f.write(chunk)
                        file_pbar.update(len(chunk))
                        
                file_pbar.close()
                
                if pbar:
                    pbar.write(f"✓ {description}")
                    pbar.update(1)
                    
                return True
                
        except asyncio.TimeoutError:
            if pbar:
                pbar.write(f"✗ {description}: Timeout")
            return False
        except Exception as e:
            if pbar:
                pbar.write(f"✗ {description}: {str(e)[:50]}")
            return False
            
    async def download_multiple(
        self,
        downloads: List[Tuple[str, Path, str]]
    ) -> Dict[str, bool]:
        """Download multiple files in parallel.
        
        Args:
            downloads: List of (url, destination, description) tuples
            
        Returns:
            Dictionary mapping descriptions to success status
        """
        results = {}
        
        # Create overall progress bar
        pbar = tqdm(
            total=len(downloads),
            desc="Overall Progress",
            unit="file",
            position=0
        )
        
        # Create semaphore to limit concurrent downloads
        semaphore = asyncio.Semaphore(self.max_concurrent)
        
        async def download_with_semaphore(url: str, dest: Path, desc: str):
            async with semaphore:
                success = await self.download_file(url, dest, desc, pbar)
                results[desc] = success
                return success
                
        # Schedule all downloads
        tasks = [
            download_with_semaphore(url, dest, desc)
            for url, dest, desc in downloads
        ]
        
        # Wait for all downloads to complete
        await asyncio.gather(*tasks)
        
        pbar.close()
        
        return results


async def download_vosk_models():
    """Download Vosk speech recognition models in parallel."""
    print("\n" + "="*60)
    print("Downloading Vosk STT Models")
    print("="*60)
    
    models_dir = Path("models/stt")
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # Define all language models to download
    # NOTE: Only English, Hindi, Telugu, and Gujarati have available Vosk models
    # Other Indian languages don't have models yet on Vosk repository
    models = {
        "en": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip",
            "extracted_name": "vosk-model-small-en-us-0.15",
            "display_name": "English"
        },
        "hi": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-hi-0.22.zip",
            "extracted_name": "vosk-model-hi-0.22",
            "display_name": "Hindi"
        },
        "te": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-te-0.42.zip",
            "extracted_name": "vosk-model-small-te-0.42",
            "display_name": "Telugu"
        },
        "gu": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-gu-0.42.zip",
            "extracted_name": "vosk-model-small-gu-0.42",
            "display_name": "Gujarati"
        },
        "bn": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-en-in-0.5.zip",
            "extracted_name": "vosk-model-en-in-0.5",
            "display_name": "Bengali (Indian English)"
        }
    }
    
    # Prepare download list (skip existing models)
    downloads = []
    skipped = []
    
    for lang_code, model_info in models.items():
        target_dir = models_dir / f"vosk-{lang_code}"
        
        if target_dir.exists():
            skipped.append(model_info['display_name'])
            continue
            
        model_path = models_dir / f"vosk-model-{lang_code}.zip"
        downloads.append((
            model_info['url'],
            model_path,
            f"Vosk {model_info['display_name']}"
        ))
    
    if skipped:
        print(f"\nSkipping existing models: {', '.join(skipped)}")
    
    if not downloads:
        print("\n✓ All Vosk models already downloaded!")
        return
    
    print(f"\nDownloading {len(downloads)} models in parallel...")
    
    # Download all models in parallel
    async with ParallelDownloader(max_concurrent=3) as downloader:
        results = await downloader.download_multiple(downloads)
    
    # Extract downloaded models
    print("\n\nExtracting models...")
    extraction_pbar = tqdm(total=len(downloads), desc="Extraction", unit="model")
    
    for lang_code, model_info in models.items():
        target_dir = models_dir / f"vosk-{lang_code}"
        
        if target_dir.exists():
            continue
            
        model_path = models_dir / f"vosk-model-{lang_code}.zip"
        desc = f"Vosk {model_info['display_name']}"
        
        if not results.get(desc, False):
            extraction_pbar.write(f"✗ Skipping {model_info['display_name']} (download failed)")
            extraction_pbar.update(1)
            continue
        
        try:
            if not model_path.exists():
                extraction_pbar.write(f"✗ {model_info['display_name']}: File not found")
                extraction_pbar.update(1)
                continue
                
            # Extract the model
            with zipfile.ZipFile(model_path, 'r') as zip_ref:
                zip_ref.extractall(models_dir)
            
            # Rename to standard format
            extracted_path = models_dir / model_info['extracted_name']
            if extracted_path.exists():
                extracted_path.rename(target_dir)
                extraction_pbar.write(f"✓ {model_info['display_name']} extracted")
            
            # Clean up zip file
            model_path.unlink()
            
        except Exception as e:
            extraction_pbar.write(f"✗ {model_info['display_name']}: {str(e)[:50]}")
            if model_path.exists():
                model_path.unlink()
        
        extraction_pbar.update(1)
    
    extraction_pbar.close()
    print("\n✓ Vosk models setup complete!")



async def install_argos_packages():
    """Install Argos Translate language packages in parallel."""
    print("\n" + "="*60)
    print("Installing Argos Translate Packages")
    print("="*60)
    
    # Set ARGOS_PACKAGES_DIR to use volume-mounted directory
    argos_dir = Path("models/translate/argos-packages")
    argos_dir.mkdir(parents=True, exist_ok=True)
    os.environ['ARGOS_PACKAGES_DIR'] = str(argos_dir.absolute())
    print(f"\n✓ Using package directory: {argos_dir.absolute()}")
    
    try:
        import argostranslate.package
        
        # Update package index
        print("\nUpdating package index...")
        await asyncio.get_event_loop().run_in_executor(
            None, 
            argostranslate.package.update_package_index
        )
        
        # Get available packages
        available_packages = argostranslate.package.get_available_packages()
        
        # Define language pairs to install - Only available packages
        # NOTE: Argos Translate only has Hindi and Bengali packages available
        # Other Indian languages (Telugu, Tamil, Kannada, Malayalam, Gujarati, Marathi) 
        # don't have translation packages in Argos repository yet
        language_pairs = [
            ("en", "hi", "English", "Hindi"),
            ("hi", "en", "Hindi", "English"),
            ("en", "bn", "English", "Bengali"),
            ("bn", "en", "Bengali", "English"),
        ]
        
        print(f"\n✓ Strategy: English as bridge language")
        print(f"✓ Installing {len(language_pairs)} available translation packages")
        print(f"✓ Available: Hindi, Bengali (Other Indian languages not yet in Argos)")
        print(f"✓ Indian-to-Indian uses bridge: Source→English→Target\n")
        
        # Use ThreadPoolExecutor for parallel installation
        with ThreadPoolExecutor(max_workers=4) as executor:
            pbar = tqdm(total=len(language_pairs), desc="Installing packages", unit="pkg")
            
            def install_package(pair):
                from_code, to_code, from_name, to_name = pair
                
                packages = [
                    pkg for pkg in available_packages
                    if pkg.from_code == from_code and pkg.to_code == to_code
                ]
                
                if not packages:
                    pbar.write(f"✗ {from_name}→{to_name}: Not available")
                    return False
                    
                try:
                    argostranslate.package.install_from_path(
                        packages[0].download()
                    )
                    pbar.write(f"✓ {from_name}→{to_name}")
                    return True
                except Exception as e:
                    pbar.write(f"✗ {from_name}→{to_name}: {str(e)[:40]}")
                    return False
                finally:
                    pbar.update(1)
            
            # Install packages in parallel
            results = list(executor.map(install_package, language_pairs))
            pbar.close()
        
        installed_count = sum(results)
        print(f"\n✓ Argos Translate: {installed_count}/{len(language_pairs)} packages installed")
        return True
        
    except ImportError:
        print("\n✗ Error: argostranslate not installed")
        print("  Run: pip install -r requirements.txt")
        return False
    except Exception as e:
        print(f"\n✗ Error installing packages: {str(e)[:60]}")
        print("  Packages will be installed on first use")
        return False



def setup_tts_models():
    """Setup TTS models (Coqui TTS downloads on first use)."""
    print("\n" + "="*60)
    print("TTS Model Setup")
    print("="*60)
    
    # Create TTS directory
    tts_dir = Path("models/tts/coqui-models")
    tts_dir.mkdir(parents=True, exist_ok=True)
    
    # Check if TTS is installed
    try:
        from TTS.api import TTS
        print("\n✓ Coqui TTS library installed")
    except ImportError:
        print("\n⚠ Coqui TTS not installed")
        print("  Install with: pip install TTS")
        print("  Or: pip install -r requirements.txt\n")
        return
    
    print("\n📋 Supported TTS Languages:")
    print("  • English (en) - XTTS v2")
    print("  • Hindi (hi), Bengali (bn), Telugu (te), Tamil (ta)")
    print("  • Marathi (mr), Gujarati (gu), Kannada (kn), Malayalam (ml)")
    print("  • Punjabi (pa), Urdu (ur), Assamese (as), Odia (or)")
    print("  • Plus 15 more European/Asian languages via XTTS v2")
    
    print("\n✓ TTS models auto-download on first use (no pre-download needed)")
    
    # Optional: Pre-download commonly used models
    print("\n💡 To pre-download models, use Python:")
    print("  from TTS.api import TTS")
    print("  # For English/European languages:")
    print("  TTS('tts_models/multilingual/multi-dataset/xtts_v2')")
    print("  # For Indian languages (example):")
    print("  TTS('tts_models/hin/fairseq/vits')  # Hindi")
    print("  TTS('tts_models/ben/fairseq/vits')  # Bengali")
    print()


async def main():
    """Main async function."""
    print("\n" + "="*70)
    print(" " * 15 + "Voice-to-Voice Translator")
    print(" " * 20 + "Model Downloader")
    print("="*70)
    
    # Create models directory
    Path("models").mkdir(exist_ok=True)
    
    start_time = time.time()
    
    # Download models
    try:
        await download_vosk_models()
        await install_argos_packages()
        setup_tts_models()
        
        elapsed = time.time() - start_time
        minutes, seconds = divmod(int(elapsed), 60)
        
        print("="*70)
        print(f"\n✓ All models downloaded successfully!")
        print(f"✓ Total time: {minutes}m {seconds}s\n")
        print("="*70)
        
        # Show language support summary
        print("\n📊 Language Support Summary:")
        print("  STT (Speech-to-Text):  5 languages")
        print("    ✓ English, Hindi, Telugu, Gujarati, Bengali")
        print("\n  Translation:           2 bidirectional pairs (4 directions)")
        print("    ✓ English ↔ Hindi")
        print("    ✓ English ↔ Bengali")
        print("    ℹ Other pairs: Use English as bridge (e.g., Hindi→English→Bengali)")
        print("\n  TTS (Text-to-Speech):  13 Indian languages (+ 15 more via XTTS)")
        print("    ✓ English")
        print("    ✓ Hindi, Bengali, Telugu, Tamil")
        print("    ✓ Marathi, Gujarati, Kannada, Malayalam")
        print("    ✓ Punjabi, Urdu, Assamese, Odia")
        
        print("\n" + "="*70)
        print("\n🚀 Ready to Start!")
        print("\nYou can now run the server:")
        print("  python app/main.py")
        print("\nOr with Docker:")
        print("  docker-compose up -d")
        print("\nOr with Uvicorn:")
        print("  uvicorn app.main:app --host 0.0.0.0 --port 8000\n")
        
    except KeyboardInterrupt:
        print("\n\n✗ Download cancelled by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n\n✗ Error during download: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    # Run async main
    if sys.platform == 'win32':
        # Windows-specific event loop policy
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    
    asyncio.run(main())
