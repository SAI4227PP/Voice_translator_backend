"""
Health check script for Voice-to-Voice Translator.
"""
import sys
import asyncio
import aiohttp
from pathlib import Path


async def check_server_health(host: str = "localhost", port: int = 8000) -> bool:
    """Check if server is responding.
    
    Args:
        host: Server host
        port: Server port
        
    Returns:
        True if healthy, False otherwise
    """
    url = f"http://{host}:{port}/health"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=5)) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    print(f"✓ Server is healthy")
                    print(f"  - Status: {data.get('status')}")
                    print(f"  - Connections: {data.get('connections')}")
                    print(f"  - Rooms: {data.get('rooms')}")
                    print(f"  - Total Users: {data.get('total_users')}")
                    return True
                else:
                    print(f"✗ Server returned status {resp.status}")
                    return False
    except Exception as e:
        print(f"✗ Server health check failed: {e}")
        return False


def check_models() -> bool:
    """Check if required models are present.
    
    Returns:
        True if all models present, False otherwise
    """
    print("\nChecking models...")
    
    models = [
        ("Vosk English", "models/stt/vosk-en"),
        ("Vosk Hindi", "models/stt/vosk-hi"),
        ("Argos Translate", "models/translate/argos-packages"),
        ("Coqui TTS", "models/tts/coqui-models"),
    ]
    
    all_present = True
    for name, path in models:
        model_path = Path(path)
        if model_path.exists() and any(model_path.iterdir()):
            print(f"  ✓ {name}: Found")
        else:
            print(f"  ✗ {name}: Not found at {path}")
            all_present = False
    
    return all_present


def check_dependencies() -> bool:
    """Check if required Python packages are installed.
    
    Returns:
        True if all dependencies installed, False otherwise
    """
    print("\nChecking dependencies...")
    
    required_packages = [
        "fastapi",
        "uvicorn",
        "websockets",
        "vosk",
        "argostranslate",
        "TTS",
        "pydantic",
        "structlog",
    ]
    
    all_installed = True
    for package in required_packages:
        try:
            __import__(package)
            print(f"  ✓ {package}: Installed")
        except ImportError:
            print(f"  ✗ {package}: Not installed")
            all_installed = False
    
    return all_installed


def check_config() -> bool:
    """Check if configuration file exists.
    
    Returns:
        True if config exists, False otherwise
    """
    print("\nChecking configuration...")
    
    if Path(".env").exists():
        print("  ✓ .env file: Found")
        return True
    else:
        print("  ✗ .env file: Not found")
        print("    Create .env file from .env.example")
        return False


async def main():
    """Main health check function."""
    print("=" * 60)
    print("Voice-to-Voice Translator - Health Check")
    print("=" * 60)
    
    checks = {
        "Dependencies": check_dependencies(),
        "Configuration": check_config(),
        "Models": check_models(),
    }
    
    # Check server if running
    print("\nChecking server...")
    checks["Server"] = await check_server_health()
    
    # Summary
    print("\n" + "=" * 60)
    print("Health Check Summary")
    print("=" * 60)
    
    for check_name, passed in checks.items():
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{check_name}: {status}")
    
    all_passed = all(checks.values())
    
    if all_passed:
        print("\n✓ All checks passed!")
        return 0
    else:
        print("\n✗ Some checks failed. Please review the output above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
