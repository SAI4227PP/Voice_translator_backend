"""
Script to download all required models for the voice translator.
"""
import os
import sys
import urllib.request
import zipfile
import tarfile
from pathlib import Path


def download_file(url: str, destination: Path) -> None:
    """Download a file with progress bar.
    
    Args:
        url: URL to download from
        destination: Local file path
    """
    print(f"Downloading {url}...")
    
    def reporthook(count, block_size, total_size):
        percent = int(count * block_size * 100 / total_size)
        sys.stdout.write(f"\r{percent}% complete")
        sys.stdout.flush()
    
    urllib.request.urlretrieve(url, destination, reporthook)
    print("\nDownload complete!")


def download_vosk_models():
    """Download Vosk speech recognition models."""
    print("\n=== Downloading Vosk Models ===")
    
    models_dir = Path("models/stt")
    models_dir.mkdir(parents=True, exist_ok=True)
    
    # Vosk English model (small version for faster performance)
    en_model_url = "https://alphacephei.com/vosk/models/vosk-model-small-en-us-0.15.zip"
    en_model_path = models_dir / "vosk-model-en.zip"
    
    if not (models_dir / "vosk-en").exists():
        print("Downloading English model...")
        download_file(en_model_url, en_model_path)
        
        print("Extracting English model...")
        with zipfile.ZipFile(en_model_path, 'r') as zip_ref:
            zip_ref.extractall(models_dir)
        
        # Rename to expected directory
        extracted_dir = models_dir / "vosk-model-small-en-us-0.15"
        if extracted_dir.exists():
            extracted_dir.rename(models_dir / "vosk-en")
        
        en_model_path.unlink()  # Delete zip file
        print("English model installed!")
    else:
        print("English model already exists, skipping...")
    
    # Vosk Hindi model
    hi_model_url = "https://alphacephei.com/vosk/models/vosk-model-hi-0.22.zip"
    hi_model_path = models_dir / "vosk-model-hi.zip"
    
    if not (models_dir / "vosk-hi").exists():
        print("Downloading Hindi model...")
        download_file(hi_model_url, hi_model_path)
        
        print("Extracting Hindi model...")
        with zipfile.ZipFile(hi_model_path, 'r') as zip_ref:
            zip_ref.extractall(models_dir)
        
        # Rename to expected directory
        extracted_dir = models_dir / "vosk-model-hi-0.22"
        if extracted_dir.exists():
            extracted_dir.rename(models_dir / "vosk-hi")
        
        hi_model_path.unlink()  # Delete zip file
        print("Hindi model installed!")
    else:
        print("Hindi model already exists, skipping...")


def install_argos_packages():
    """Install Argos Translate packages."""
    print("\n=== Installing Argos Translate Packages ===")
    
    try:
        import argostranslate.package
        
        # Update package index
        print("Updating package index...")
        argostranslate.package.update_package_index()
        
        # Get available packages
        available_packages = argostranslate.package.get_available_packages()
        
        # Install English to Hindi
        print("Installing English to Hindi translation package...")
        en_hi_packages = [
            pkg for pkg in available_packages
            if pkg.from_code == "en" and pkg.to_code == "hi"
        ]
        
        if en_hi_packages:
            argostranslate.package.install_from_path(
                en_hi_packages[0].download()
            )
            print("English to Hindi package installed!")
        
        # Install Hindi to English
        print("Installing Hindi to English translation package...")
        hi_en_packages = [
            pkg for pkg in available_packages
            if pkg.from_code == "hi" and pkg.to_code == "en"
        ]
        
        if hi_en_packages:
            argostranslate.package.install_from_path(
                hi_en_packages[0].download()
            )
            print("Hindi to English package installed!")
        
        print("Argos Translate packages installed successfully!")
        
    except ImportError:
        print("Error: argostranslate not installed. Install requirements first:")
        print("  pip install -r requirements.txt")
        sys.exit(1)
    except Exception as e:
        print(f"Error installing Argos packages: {e}")
        sys.exit(1)


def setup_tts_models():
    """Setup TTS models (Coqui TTS downloads on first use)."""
    print("\n=== TTS Model Setup ===")
    
    tts_dir = Path("models/tts/coqui-models")
    tts_dir.mkdir(parents=True, exist_ok=True)
    
    print("Coqui TTS models will be downloaded automatically on first use.")
    print("No pre-download necessary.")


def main():
    """Main function."""
    print("=" * 60)
    print("Voice-to-Voice Translator - Model Downloader")
    print("=" * 60)
    
    # Check if we're in the right directory
    if not Path("requirements.txt").exists():
        print("Error: Please run this script from the project root directory")
        sys.exit(1)
    
    # Create models directory
    Path("models").mkdir(exist_ok=True)
    
    # Download models
    try:
        download_vosk_models()
        install_argos_packages()
        setup_tts_models()
        
        print("\n" + "=" * 60)
        print("All models downloaded successfully!")
        print("=" * 60)
        print("\nYou can now run the server with:")
        print("  python app/main.py")
        
    except KeyboardInterrupt:
        print("\n\nDownload cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n\nError during download: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
