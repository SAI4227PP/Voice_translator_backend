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
    
    # Define all language models to download
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
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-te-0.4.zip",
            "extracted_name": "vosk-model-small-te-0.4",
            "display_name": "Telugu"
        },
        "ta": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-ta-0.4.zip",
            "extracted_name": "vosk-model-ta-0.4",
            "display_name": "Tamil"
        },
        "kn": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-kn-0.4.zip",
            "extracted_name": "vosk-model-small-kn-0.4",
            "display_name": "Kannada"
        },
        "ml": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-ml-0.4.zip",
            "extracted_name": "vosk-model-small-ml-0.4",
            "display_name": "Malayalam"
        },
        "gu": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-gu-0.4.zip",
            "extracted_name": "vosk-model-small-gu-0.4",
            "display_name": "Gujarati"
        },
        "mr": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-mr-0.4.zip",
            "extracted_name": "vosk-model-small-mr-0.4",
            "display_name": "Marathi"
        },
        "bn": {
            "url": "https://alphacephei.com/vosk/models/vosk-model-small-bn-0.4.zip",
            "extracted_name": "vosk-model-small-bn-0.4",
            "display_name": "Bengali"
        }
    }
    
    # Download and extract each model
    for lang_code, model_info in models.items():
        target_dir = models_dir / f"vosk-{lang_code}"
        
        if target_dir.exists():
            print(f"{model_info['display_name']} model already exists, skipping...")
            continue
        
        print(f"\nDownloading {model_info['display_name']} model...")
        model_path = models_dir / f"vosk-model-{lang_code}.zip"
        Define language pairs to install
        language_pairs = [
            ("en", "hi", "English", "Hindi"),
            ("hi", "en", "Hindi", "English"),
            ("en", "te", "English", "Telugu"),
            ("te", "en", "Telugu", "English"),
            ("en", "ta", "English", "Tamil"),
            ("ta", "en", "Tamil", "English"),
            ("en", "kn", "English", "Kannada"),
            ("kn", "en", "Kannada", "English"),
            ("en", "ml", "English", "Malayalam"),
            ("ml", "en", "Malayalam", "English"),
            ("en", "gu", "English", "Gujarati"),
            ("gu", "en", "Gujarati", "English"),
            ("en", "mr", "English", "Marathi"),
            ("mr", "en", "Marathi", "English"),
            ("en", "bn", "English", "Bengali"),
            ("bn", "en", "Bengali", "English"),
        ]
        
        installed_count = 0
        
        for from_code, to_code, from_name, to_name in language_pairs:
            print(f"\nInstalling {from_name} to {to_name} translation package...")
            
            packages = [
                pkg for pkg in available_packages
                if pkg.from_code == from_code and pkg.to_code == to_code
            ]
            
            if packages:
                try:
                    argostranslate.package.install_from_path(
                        packages[0].download()
                    )
                    print(f"{from_name} to {to_name} package installed!")
                    installed_count += 1
                except Exception as e:
                    print(f"Warning: Could not install {from_name} to {to_name}: {e}")
            else:
                print(f"Warning: {from_name} to {to_name} package not available")
        
        print(f"\nArgos Translate packages: {installed_count}
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
