"""
Application settings and configuration management.
"""
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Server Configuration
    host: str = Field(default="0.0.0.0", description="Server host")
    port: int = Field(default=8000, description="Server port")
    workers: int = Field(default=4, description="Number of worker threads")
    
    # Environment
    environment: str = Field(default="development", description="Environment name")
    debug: bool = Field(default=False, description="Debug mode")
    
    # Logging
    log_level: str = Field(default="INFO", description="Logging level")
    log_file: Optional[str] = Field(default="logs/app.log", description="Log file path")
    
    # WebSocket Configuration
    ws_ping_interval: int = Field(default=30, description="WebSocket ping interval in seconds")
    ws_ping_timeout: int = Field(default=10, description="WebSocket ping timeout in seconds")
    max_connections: int = Field(default=100, description="Maximum concurrent connections")
    max_message_size: int = Field(default=10485760, description="Max message size in bytes (10MB)")
    
    # Audio Configuration
    audio_sample_rate: int = Field(default=16000, description="Audio sample rate in Hz")
    audio_channels: int = Field(default=1, description="Number of audio channels")
    audio_chunk_size: int = Field(default=4096, description="Audio chunk size in bytes")
    audio_format: str = Field(default="PCM16", description="Audio format")
    
    # Model Paths
    vosk_model_base_path: str = Field(
        default="models/stt",
        description="Base path for Vosk models"
    )
    vosk_model_path_en: str = Field(
        default="models/stt/vosk-en",
        description="Path to English Vosk model"
    )
    vosk_model_path_hi: str = Field(
        default="models/stt/vosk-hi",
        description="Path to Hindi Vosk model"
    )
    vosk_model_path_te: str = Field(
        default="models/stt/vosk-te",
        description="Path to Telugu Vosk model"
    )
    vosk_model_path_gu: str = Field(
        default="models/stt/vosk-gu",
        description="Path to Gujarati Vosk model"
    )
    vosk_model_path_bn: str = Field(
        default="models/stt/vosk-bn",
        description="Path to Bengali (Indian English) Vosk model"
    )
    argos_model_path: str = Field(
        default="models/translate/argos-packages",
        description="Path to Argos translation models"
    )
    coqui_model_path: str = Field(
        default="models/tts/coqui-models",
        description="Path to Coqui TTS models"
    )
    
    # Pipeline Configuration
    stt_engine: str = Field(default="vosk", description="Speech-to-text engine")
    translation_engine: str = Field(default="argos", description="Translation engine")
    tts_engine: str = Field(default="coqui", description="Text-to-speech engine")
    
    # Performance Tuning
    enable_gpu: bool = Field(default=False, description="Enable GPU acceleration")
    worker_threads: int = Field(default=2, description="Worker thread count")
    buffer_size: int = Field(default=8192, description="Buffer size in bytes")
    queue_size: int = Field(default=100, description="Queue size for tasks")
    
    # Room Configuration
    max_users_per_room: int = Field(default=10, description="Maximum users per room")
    room_timeout: int = Field(default=3600, description="Room timeout in seconds")
    idle_timeout: int = Field(default=300, description="Idle connection timeout in seconds")
    
    # Security
    enable_auth: bool = Field(default=False, description="Enable authentication")
    jwt_secret_key: str = Field(
        default="your-secret-key-change-in-production",
        description="JWT secret key"
    )
    jwt_algorithm: str = Field(default="HS256", description="JWT algorithm")
    jwt_expiration: int = Field(default=3600, description="JWT expiration in seconds")
    api_keys: list[str] = Field(default_factory=list, description="Valid API keys")
    
    # Rate Limiting
    rate_limit_per_minute: int = Field(default=60, description="Rate limit per minute")
    max_requests_per_minute: int = Field(default=100, description="Max requests per minute")
    max_connections_per_ip: int = Field(default=10, description="Max connections per IP")
    max_messages_per_second: int = Field(default=10, description="Max messages per second per connection")
    
    # Worker Pools
    translation_workers: int = Field(default=4, description="Number of translation workers")
    tts_workers: int = Field(default=2, description="Number of TTS workers")
    
    # TTS Warm Start Configuration
    tts_preload_languages: str = Field(
        default="en,hi,bn,ta",
        description="Comma-separated list of languages to preload TTS models for warm start"
    )
    tts_enable_warm_start: bool = Field(
        default=True,
        description="Enable TTS model warm start (preload models at startup)"
    )
    
    # STT Warm Start Configuration
    stt_preload_languages: str = Field(
        default="en,hi",
        description="Comma-separated list of languages to preload STT models for warm start"
    )
    stt_enable_warm_start: bool = Field(
        default=True,
        description="Enable STT model warm start (preload models at startup)"
    )
    
    # Translation Warm Start Configuration
    translation_enable_warm_start: bool = Field(
        default=True,
        description="Enable Translation model warm start (preload models at startup)"
    )
    translation_warm_start_mode: str = Field(
        default="common",
        description="Translation warm start mode: 'all' (all installed packages) or 'common' (common pairs only)"
    )
    translation_common_pairs: str = Field(
        default="en-hi,hi-en,en-bn,bn-en",
        description="Comma-separated list of common translation pairs (format: src-tgt)"
    )

    
    # Monitoring
    enable_metrics: bool = Field(default=True, description="Enable metrics collection")
    metrics_port: int = Field(default=9090, description="Metrics server port")
    
    # CORS
    cors_origins: str = Field(default="*", description="CORS allowed origins")
    
    # Optional: Database
    database_url: Optional[str] = Field(default=None, description="Database connection URL")
    
    # Optional: Redis
    redis_url: Optional[str] = Field(default=None, description="Redis connection URL")
    
    @property
    def is_development(self) -> bool:
        """Check if running in development mode."""
        return self.environment.lower() in ("development", "dev")
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.environment.lower() in ("production", "prod")
    
    @property
    def cors_origins_list(self) -> list[str]:
        """Get CORS origins as a list."""
        if self.cors_origins == "*":
            return ["*"]
        return [origin.strip() for origin in self.cors_origins.split(",")]
    
    @property
    def tts_preload_languages_list(self) -> list[str]:
        """Get TTS preload languages as a list."""
        if not self.tts_preload_languages:
            return []
        return [lang.strip() for lang in self.tts_preload_languages.split(",") if lang.strip()]
    
    @property
    def stt_preload_languages_list(self) -> list[str]:
        """Get STT preload languages as a list."""
        if not self.stt_preload_languages:
            return []
        return [lang.strip() for lang in self.stt_preload_languages.split(",") if lang.strip()]
    
    @property
    def translation_common_pairs_list(self) -> list[tuple[str, str]]:
        """Get translation common pairs as a list of tuples."""
        if not self.translation_common_pairs:
            return []
        pairs = []
        for pair in self.translation_common_pairs.split(","):
            pair = pair.strip()
            if "-" in pair:
                src, tgt = pair.split("-", 1)
                pairs.append((src.strip(), tgt.strip()))
        return pairs
    
    def get_vosk_model_path(self, language: str) -> str:
        """Get Vosk model path for a specific language.
        
        Args:
            language: Language code (e.g., 'en', 'hi', 'te', 'gu', 'bn')
            
        Returns:
            Path to the Vosk model directory
        
        Note:
            Available languages: English, Hindi, Telugu, Gujarati, Bengali (Indian English)
            Other Indian languages (Tamil, Kannada, Malayalam, Marathi) not yet available in Vosk
        """
        model_mapping = {
            "en": self.vosk_model_path_en,
            "hi": self.vosk_model_path_hi,
            "te": self.vosk_model_path_te,
            "gu": self.vosk_model_path_gu,
            "bn": self.vosk_model_path_bn,
        }
        return model_mapping.get(language.lower(), self.vosk_model_path_en)


# Global settings instance
settings = Settings()


def get_settings() -> Settings:
    """Get application settings instance.
    
    Returns:
        Settings instance
    """
    return settings


def reload_settings() -> Settings:
    """Reload settings from environment.
    
    Returns:
        New Settings instance
    """
    global settings
    settings = Settings()
    return settings
