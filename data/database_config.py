"""
Configuración específica de base de datos para ZeepubsBot.
Maneja configuración, schemas y migraciones de la base de datos.
"""

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum

from config.bot_config import get_config, get_logger, BotConstants
from utils.error_handler import log_service_error


class DatabaseType(Enum):
    """Tipos de base de datos soportados."""
    SQLITE = "sqlite"
    POSTGRESQL = "postgresql"
    MYSQL = "mysql"


@dataclass(frozen=True)
class DatabaseConfig:
    """Configuración inmutable de base de datos."""
    db_type: DatabaseType
    database_path: str
    connection_timeout: int
    max_connections: int
    enable_wal_mode: bool
    enable_foreign_keys: bool
    cache_size_mb: int
    backup_enabled: bool
    backup_interval_hours: int

    @classmethod
    def create_sqlite_config(cls) -> 'DatabaseConfig':
        """Crea configuración optimizada para SQLite."""
        config = get_config()

        return cls(
            db_type=DatabaseType.SQLITE,
            database_path=str(Path(BotConstants.DATABASE_FILE).absolute()),
            connection_timeout=30,
            max_connections=10,
            enable_wal_mode=True,
            enable_foreign_keys=True,
            cache_size_mb=64,
            backup_enabled=True,
            backup_interval_hours=24
        )


class DatabaseSchema:
    """Define el schema de la base de datos."""

    @staticmethod
    def get_tables_definition() -> Dict[str, str]:
        """Retorna definiciones de todas las tablas."""
        return {
            'books': DatabaseSchema._get_books_table(),
            'book_stats': DatabaseSchema._get_book_stats_table(),
            'user_preferences': DatabaseSchema._get_user_preferences_table()
        }

    @staticmethod
    def _get_books_table() -> str:
        """Definición de la tabla principal de libros."""
        return """
               CREATE TABLE IF NOT EXISTS books \
               ( \
                   id          INTEGER PRIMARY KEY AUTOINCREMENT, \
                   book_id     TEXT NOT NULL UNIQUE, \
                   title       TEXT NOT NULL, \
                   alt_title   TEXT, \
                   author      TEXT NOT NULL, \
                   description TEXT, \
                   language    TEXT NOT NULL DEFAULT 'es', \
                   type        TEXT NOT NULL DEFAULT 'book', \
                   isbn        TEXT, \
                   publisher   TEXT, \
                   year        INTEGER, \
                   file_id     TEXT, \
                   cover_id    TEXT, \
                   file_size   INTEGER, \
                   created_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP, \
                   updated_at  TIMESTAMP     DEFAULT CURRENT_TIMESTAMP, \

                   CONSTRAINT chk_year CHECK (year IS NULL OR (year >= 1000 AND year <= 2100)), \
                   CONSTRAINT chk_language CHECK (language IN ('es', 'en', 'fr', 'de', 'it', 'pt', 'unknown')), \
                   CONSTRAINT chk_type CHECK (type IN ('book', 'novel', 'essay', 'manual', 'comic', 'magazine', 'other'))
               ) \
               """

    @staticmethod
    def _get_book_stats_table() -> str:
        """Tabla para estadísticas de libros."""
        return """
               CREATE TABLE IF NOT EXISTS book_stats \
               ( \
                   id            INTEGER PRIMARY KEY AUTOINCREMENT, \
                   book_id       TEXT NOT NULL, \
                   downloads     INTEGER   DEFAULT 0, \
                   searches      INTEGER   DEFAULT 0, \
                   last_accessed TIMESTAMP, \
                   created_at    TIMESTAMP DEFAULT CURRENT_TIMESTAMP, \

                   FOREIGN KEY (book_id) REFERENCES books (book_id) ON DELETE CASCADE
               ) \
               """

    @staticmethod
    def _get_user_preferences_table() -> str:
        """Tabla para preferencias de usuarios."""
        return """
               CREATE TABLE IF NOT EXISTS user_preferences \
               ( \
                   id                    INTEGER PRIMARY KEY AUTOINCREMENT, \
                   user_id               INTEGER NOT NULL UNIQUE, \
                   preferred_language    TEXT      DEFAULT 'es', \
                   notifications_enabled BOOLEAN   DEFAULT 1, \
                   created_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP, \
                   updated_at            TIMESTAMP DEFAULT CURRENT_TIMESTAMP, \

                   CONSTRAINT chk_user_language CHECK (preferred_language IN ('es', 'en', 'fr', 'de', 'it', 'pt'))
               ) \
               """

    @staticmethod
    def get_indexes_definition() -> List[str]:
        """Retorna definiciones de índices para optimización."""
        return [
            # Índices principales para books
            "CREATE INDEX IF NOT EXISTS idx_books_book_id ON books(book_id)",
            "CREATE INDEX IF NOT EXISTS idx_books_title ON books(title)",
            "CREATE INDEX IF NOT EXISTS idx_books_author ON books(author)",
            "CREATE INDEX IF NOT EXISTS idx_books_language ON books(language)",
            "CREATE INDEX IF NOT EXISTS idx_books_type ON books(type)",
            "CREATE INDEX IF NOT EXISTS idx_books_created_at ON books(created_at)",

            # Índices para búsquedas compuestas
            "CREATE INDEX IF NOT EXISTS idx_books_title_author ON books(title, author)",
            "CREATE INDEX IF NOT EXISTS idx_books_language_type ON books(language, type)",

            # Índices para book_stats
            "CREATE INDEX IF NOT EXISTS idx_book_stats_book_id ON book_stats(book_id)",
            "CREATE INDEX IF NOT EXISTS idx_book_stats_downloads ON book_stats(downloads DESC)",
            "CREATE INDEX IF NOT EXISTS idx_book_stats_last_accessed ON book_stats(last_accessed DESC)",

            # Índices para user_preferences
            "CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON user_preferences(user_id)"
        ]

    @staticmethod
    def get_triggers_definition() -> List[str]:
        """Retorna definiciones de triggers para automatización."""
        return [
            # Trigger para actualizar updated_at en books
            """
            CREATE TRIGGER IF NOT EXISTS trigger_books_updated_at
                AFTER UPDATE
                ON books
                FOR EACH ROW
            BEGIN
                UPDATE books SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
            """,

            # Trigger para actualizar updated_at en user_preferences
            """
            CREATE TRIGGER IF NOT EXISTS trigger_user_preferences_updated_at
                AFTER UPDATE
                ON user_preferences
                FOR EACH ROW
            BEGIN
                UPDATE user_preferences SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
            END
            """,

            # Trigger para crear stats automáticamente
            """
            CREATE TRIGGER IF NOT EXISTS trigger_create_book_stats
                AFTER INSERT
                ON books
                FOR EACH ROW
            BEGIN
                INSERT INTO book_stats (book_id) VALUES (NEW.book_id);
            END
            """
        ]


class DatabaseMigrator:
    """Maneja migraciones de base de datos."""

    def __init__(self):
        """Inicializa el migrador."""
        self.logger = get_logger(__name__)
        self.current_version = 1

    def get_migrations(self) -> Dict[int, List[str]]:
        """Retorna todas las migraciones disponibles."""
        return {
            1: self._migration_v1_initial_schema(),
            2: self._migration_v2_add_stats_table(),
            3: self._migration_v3_add_user_preferences()
        }

    def _migration_v1_initial_schema(self) -> List[str]:
        """Migración inicial - crear tabla books."""
        return [
            DatabaseSchema._get_books_table(),
            *DatabaseSchema.get_indexes_definition()[:6]  # Solo índices básicos
        ]

    def _migration_v2_add_stats_table(self) -> List[str]:
        """Migración v2 - agregar tabla de estadísticas."""
        return [
            DatabaseSchema._get_book_stats_table(),
            *DatabaseSchema.get_indexes_definition()[6:9],  # Índices de stats
            DatabaseSchema.get_triggers_definition()[2]  # Trigger para crear stats
        ]

    def _migration_v3_add_user_preferences(self) -> List[str]:
        """Migración v3 - agregar preferencias de usuario."""
        return [
            DatabaseSchema._get_user_preferences_table(),
            DatabaseSchema.get_indexes_definition()[-1],  # Índice user_preferences
            *DatabaseSchema.get_triggers_definition()[:2]  # Triggers updated_at
        ]

    def get_schema_version_table(self) -> str:
        """Tabla para tracking de versiones de schema."""
        return """
               CREATE TABLE IF NOT EXISTS schema_version \
               ( \
                   version     INTEGER PRIMARY KEY, \
                   applied_at  TIMESTAMP DEFAULT CURRENT_TIMESTAMP, \
                   description TEXT
               ) \
               """


class DatabaseOptimizer:
    """Optimizaciones y mantenimiento de base de datos."""

    @staticmethod
    def get_optimization_queries() -> List[str]:
        """Queries para optimización de performance."""
        return [
            "PRAGMA optimize",
            "ANALYZE",
            "VACUUM",
            "REINDEX"
        ]

    @staticmethod
    def get_maintenance_queries() -> List[str]:
        """Queries para mantenimiento regular."""
        return [
            # Limpiar registros antiguos (opcional)
            """
            DELETE
            FROM book_stats
            WHERE last_accessed < datetime('now', '-1 year')
              AND downloads = 0
            """,

            # Actualizar estadísticas
            "ANALYZE books",
            "ANALYZE book_stats",
            "ANALYZE user_preferences"
        ]

    @staticmethod
    def get_integrity_checks() -> List[str]:
        """Queries para verificar integridad."""
        return [
            "PRAGMA integrity_check",
            "PRAGMA foreign_key_check",

            # Verificar consistencia de datos
            """
            SELECT COUNT(*) as orphaned_stats
            FROM book_stats bs
                     LEFT JOIN books b ON bs.book_id = b.book_id
            WHERE b.book_id IS NULL
            """
        ]


class DatabaseConstants:
    """Constantes específicas de base de datos."""

    # Configuración SQLite
    SQLITE_PRAGMA_SETTINGS = {
        'journal_mode': 'WAL',
        'synchronous': 'NORMAL',
        'cache_size': -64000,  # 64MB en KB negativos
        'temp_store': 'MEMORY',
        'mmap_size': 268435456,  # 256MB
        'foreign_keys': 'ON'
    }

    # Límites de datos
    MAX_TITLE_LENGTH = 255
    MAX_AUTHOR_LENGTH = 255
    MAX_DESCRIPTION_LENGTH = 2000
    MAX_BOOK_ID_LENGTH = 20
    MIN_BOOK_ID_LENGTH = 5

    # Configuración de backup
    BACKUP_RETENTION_DAYS = 30
    BACKUP_PREFIX = "zeepubsbot_backup"

    # Performance
    DEFAULT_PAGE_SIZE = 4096
    DEFAULT_CACHE_SIZE_MB = 64
    CONNECTION_POOL_SIZE = 10


def get_database_config() -> DatabaseConfig:
    """Factory function para obtener configuración de base de datos."""
    try:
        return DatabaseConfig.create_sqlite_config()
    except Exception as e:
        logger = get_logger(__name__)
        log_service_error("DatabaseConfig", e)
        logger.error(f"Error creando configuración de BD: {e}")
        raise


def validate_database_config(config: DatabaseConfig) -> List[str]:
    """Valida configuración de base de datos."""
    errors = []

    try:
        # Validar path de base de datos
        if config.db_type == DatabaseType.SQLITE:
            db_path = Path(config.database_path)
            parent_dir = db_path.parent

            if not parent_dir.exists():
                try:
                    parent_dir.mkdir(parents=True, exist_ok=True)
                except Exception as e:
                    errors.append(f"No se puede crear directorio de BD: {e}")

            if not parent_dir.is_dir():
                errors.append("El directorio padre de BD no es válido")

        # Validar configuración
        if config.connection_timeout <= 0:
            errors.append("Timeout de conexión debe ser mayor a 0")

        if config.max_connections <= 0:
            errors.append("Máximo de conexiones debe ser mayor a 0")

        if config.cache_size_mb <= 0:
            errors.append("Tamaño de cache debe ser mayor a 0")

        if config.backup_interval_hours <= 0:
            errors.append("Intervalo de backup debe ser mayor a 0")

    except Exception as e:
        errors.append(f"Error validando configuración: {e}")

    return errors


def get_connection_string(config: DatabaseConfig) -> str:
    """Genera string de conexión según el tipo de BD."""
    if config.db_type == DatabaseType.SQLITE:
        return f"sqlite:///{config.database_path}"
    else:
        raise ValueError(f"Tipo de BD no soportado: {config.db_type}")


# Instancia global de configuración
_db_config: Optional[DatabaseConfig] = None


def get_db_config() -> DatabaseConfig:
    """Retorna configuración global de base de datos."""
    global _db_config

    if _db_config is None:
        _db_config = get_database_config()

    return _db_config