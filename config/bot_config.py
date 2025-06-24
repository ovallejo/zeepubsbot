"""
Configuración centralizada para ZeepubsBot.
Maneja todas las constantes, configuraciones de API y logging.
"""

import logging
import os
from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class BotConfig:
    """Configuración inmutable del bot."""

    # Tokens y API Keys
    telegram_token: str
    deepseek_api_key: str

    # Chat IDs
    developer_chat_id: int

    # Configuración de paginación
    books_per_page: int

    # URLs de APIs
    deepseek_endpoint: str

    # Configuración de timeouts
    api_timeout: int

    # Configuración de mensajes
    max_message_length: int
    max_caption_length: int


class ConfigManager:
    """Gestor de configuración del bot."""

    _instance: Optional['ConfigManager'] = None
    _config: Optional[BotConfig] = None

    def __new__(cls) -> 'ConfigManager':
        """Implementa patrón Singleton para configuración global."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Inicializa el gestor si no está configurado."""
        if self._config is None:
            self._config = self._load_config()
            self._setup_logging()

    def _load_config(self) -> BotConfig:
        """Carga configuración desde variables de entorno."""
        return BotConfig(
            telegram_token=self._get_required_env("ZEEPUBSBOT_TOKEN"),
            deepseek_api_key=self._get_required_env("DEEPSEEK_TOKEN"),
            developer_chat_id=int(self._get_env("DEVELOPER_CHAT_ID", "706229521")),
            books_per_page=int(self._get_env("BOOKS_PER_PAGE", "10")),
            deepseek_endpoint=self._get_env("DEEPSEEK_ENDPOINT", "https://api.deepseek.com"),
            api_timeout=int(self._get_env("API_TIMEOUT", "30")),
            max_message_length=int(self._get_env("MAX_MESSAGE_LENGTH", "4096")),
            max_caption_length=int(self._get_env("MAX_CAPTION_LENGTH", "1024"))
        )

    def _get_required_env(self, key: str) -> str:
        """Obtiene variable de entorno requerida."""
        value = os.getenv(key)
        if not value:
            raise ValueError(f"Variable de entorno requerida no encontrada: {key}")
        return value

    def _get_env(self, key: str, default: str) -> str:
        """Obtiene variable de entorno con valor por defecto."""
        return os.getenv(key, default)

    def _setup_logging(self) -> None:
        """Configura el sistema de logging."""
        logging.basicConfig(
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            level=logging.INFO,
            handlers=[
                logging.StreamHandler(),
                logging.FileHandler("zeepubsbot.log", encoding="utf-8")
            ]
        )

    @property
    def config(self) -> BotConfig:
        """Retorna la configuración actual."""
        return self._config

    def get_logger(self, name: str) -> logging.Logger:
        """Retorna un logger configurado."""
        return logging.getLogger(name)


# Instancia global del gestor de configuración
config_manager = ConfigManager()


# Acceso directo a la configuración
def get_config() -> BotConfig:
    """Retorna la configuración del bot."""
    return config_manager.config


def get_logger(name: str) -> logging.Logger:
    """Retorna un logger configurado."""
    return config_manager.get_logger(name)


# Constantes del bot
class BotConstants:
    """Constantes inmutables del bot."""

    # Mensajes del sistema
    PROCESSING_MESSAGE = "🔮 *Neko-Chan está buscando...*"
    UNAVAILABLE_MESSAGE = "🔮 *Neko-Chan No Disponible*"

    # Patrones de callback
    CHARACTER_PATTERN = "^character"
    DOWNLOAD_PATTERN = r"download "

    # Archivos de configuración
    MESSAGES_FILE = "mensajes.json"
    DATABASE_FILE = "books.db"
    LOG_FILE = "zeepubsbot.log"

    # Extensiones de archivo
    EPUB_EXTENSION = ".epub"

    # Límites de texto
    TITLE_TRUNCATE_LENGTH = 40
    TITLE_PARTS_LENGTH = 20
    DESCRIPTION_PREVIEW_LENGTH = 1019
