"""
Conexión y gestión de base de datos para ZeepubsBot.
Maneja conexiones SQLite, pool de conexiones y operaciones base.
"""

import sqlite3
import threading
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Generator

from config.bot_config import get_config, get_logger
from data.database_config import get_db_config, DatabaseSchema, DatabaseConstants, DatabaseMigrator
from utils.error_handler import log_service_error


class DatabaseConnection:
    """Gestor de conexiones a base de datos SQLite."""

    def __init__(self):
        """Inicializa el gestor de conexiones."""
        self.app_config = get_config()
        self.db_config = get_db_config()
        self.logger = get_logger(__name__)
        self._lock = threading.RLock()
        self._connections = {}

        # Configuración de base de datos
        self.db_path = Path(self.db_config.database_path)
        self._initialize_database()

    def _initialize_database(self) -> None:
        """Inicializa la base de datos y ejecuta migraciones."""
        try:
            with self.get_connection() as conn:
                self._setup_connection_settings(conn)
                self._run_migrations(conn)
                self._create_indexes(conn)
                self._create_triggers(conn)
                self._verify_database_integrity(conn)

            self.logger.info(f"Base de datos inicializada: {self.db_path}")

        except Exception as e:
            log_service_error("DatabaseConnection", e, {"db_path": str(self.db_path)})
            raise RuntimeError(f"Error inicializando base de datos: {e}")

    def _setup_connection_settings(self, conn: sqlite3.Connection) -> None:
        """Configura settings óptimos para la conexión."""
        try:
            cursor = conn.cursor()

            # Aplicar configuración optimizada
            for pragma, value in DatabaseConstants.SQLITE_PRAGMA_SETTINGS.items():
                cursor.execute(f"PRAGMA {pragma} = {value}")

            self.logger.debug("Configuración de conexión aplicada")

        except Exception as e:
            log_service_error("DatabaseConnection", e, {"operation": "setup_connection"})
            raise

    def _run_migrations(self, conn: sqlite3.Connection) -> None:
        """Ejecuta migraciones de base de datos."""
        try:
            cursor = conn.cursor()

            # Crear tabla de versiones si no existe
            migrator = DatabaseMigrator()
            cursor.execute(migrator.get_schema_version_table())

            # Obtener versión actual
            cursor.execute("SELECT MAX(version) FROM schema_version")
            result = cursor.fetchone()
            current_version = result[0] if result[0] else 0

            # Ejecutar migraciones pendientes
            migrations = migrator.get_migrations()
            for version, commands in migrations.items():
                if version > current_version:
                    self.logger.info(f"Ejecutando migración v{version}")

                    for command in commands:
                        cursor.execute(command)

                    # Registrar migración aplicada
                    cursor.execute(
                        "INSERT INTO schema_version (version, description) VALUES (?, ?)",
                        (version, f"Migration v{version}")
                    )

            conn.commit()
            self.logger.debug("Migraciones completadas")

        except Exception as e:
            log_service_error("DatabaseConnection", e, {"operation": "run_migrations"})
            raise

    def _create_indexes(self, conn: sqlite3.Connection) -> None:
        """Crea índices para optimización."""
        try:
            cursor = conn.cursor()

            for index_sql in DatabaseSchema.get_indexes_definition():
                cursor.execute(index_sql)

            conn.commit()
            self.logger.debug("Índices creados/verificados")

        except Exception as e:
            log_service_error("DatabaseConnection", e, {"operation": "create_indexes"})
            raise

    def _create_triggers(self, conn: sqlite3.Connection) -> None:
        """Crea triggers automáticos."""
        try:
            cursor = conn.cursor()

            for trigger_sql in DatabaseSchema.get_triggers_definition():
                cursor.execute(trigger_sql)

            conn.commit()
            self.logger.debug("Triggers creados/verificados")

        except Exception as e:
            log_service_error("DatabaseConnection", e, {"operation": "create_triggers"})
            raise

    def _verify_database_integrity(self, conn: sqlite3.Connection) -> None:
        """Verifica la integridad de la base de datos."""
        try:
            cursor = conn.cursor()
            cursor.execute("PRAGMA integrity_check")
            result = cursor.fetchone()

            if result[0] != "ok":
                raise RuntimeError(f"Verificación de integridad falló: {result[0]}")

            self.logger.debug("Integridad de base de datos verificada")

        except Exception as e:
            log_service_error("DatabaseConnection", e, {"operation": "integrity_check"})
            raise

    @contextmanager
    def get_connection(self) -> Generator[sqlite3.Connection, None, None]:
        """Context manager para obtener conexión thread-safe."""
        thread_id = threading.get_ident()

        try:
            with self._lock:
                if thread_id not in self._connections:
                    self._connections[thread_id] = self._create_connection()

                conn = self._connections[thread_id]

            yield conn

        except Exception as e:
            log_service_error("DatabaseConnection", e, {"thread_id": thread_id})
            # Limpiar conexión corrupta
            with self._lock:
                if thread_id in self._connections:
                    try:
                        self._connections[thread_id].close()
                    except:
                        pass
                    del self._connections[thread_id]
            raise

    def _create_connection(self) -> sqlite3.Connection:
        """Crea una nueva conexión a la base de datos."""
        try:
            conn = sqlite3.connect(
                str(self.db_path),
                check_same_thread=False,
                timeout=float(self.db_config.connection_timeout)
            )

            # Row factory para resultados como dict
            conn.row_factory = sqlite3.Row

            # Aplicar configuración inicial
            self._setup_connection_settings(conn)

            return conn

        except Exception as e:
            log_service_error("DatabaseConnection", e, {"db_path": str(self.db_path)})
            raise

    def execute_query(
        self,
        query: str,
        params: Optional[Tuple] = None
    ) -> List[sqlite3.Row]:
        """Ejecuta consulta SELECT y retorna resultados."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                if params:
                    cursor.execute(query, params)
                else:
                    cursor.execute(query)

                results = cursor.fetchall()

                self.logger.debug(f"Query ejecutada: {len(results)} resultados")
                return results

        except Exception as e:
            log_service_error("DatabaseConnection", e, {
                "query": query[:100],
                "params": str(params) if params else None
            })
            raise

    def execute_command(
        self,
        command: str,
        params: Optional[Tuple] = None
    ) -> int:
        """Ejecuta comando INSERT/UPDATE/DELETE y retorna filas afectadas."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                if params:
                    cursor.execute(command, params)
                else:
                    cursor.execute(command)

                conn.commit()
                rows_affected = cursor.rowcount

                self.logger.debug(f"Comando ejecutado: {rows_affected} filas afectadas")
                return rows_affected

        except Exception as e:
            log_service_error("DatabaseConnection", e, {
                "command": command[:100],
                "params": str(params) if params else None
            })
            raise

    def execute_transaction(self, operations: List[Tuple[str, Optional[Tuple]]]) -> bool:
        """Ejecuta múltiples operaciones en una transacción."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Iniciar transacción explícita
                cursor.execute("BEGIN TRANSACTION")

                try:
                    for operation, params in operations:
                        if params:
                            cursor.execute(operation, params)
                        else:
                            cursor.execute(operation)

                    conn.commit()
                    self.logger.debug(f"Transacción completada: {len(operations)} operaciones")
                    return True

                except Exception as e:
                    conn.rollback()
                    self.logger.warning(f"Transacción revertida: {e}")
                    raise

        except Exception as e:
            log_service_error("DatabaseConnection", e, {
                "operations_count": len(operations)
            })
            return False

    def get_last_insert_id(self) -> int:
        """Obtiene el ID de la última inserción."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                return cursor.lastrowid

        except Exception as e:
            log_service_error("DatabaseConnection", e)
            return 0

    def get_database_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas de la base de datos."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Estadísticas básicas
                cursor.execute("SELECT COUNT(*) FROM books")
                books_count = cursor.fetchone()[0]

                # Verificar si existe tabla book_stats
                cursor.execute("""
                    SELECT name FROM sqlite_master 
                    WHERE type='table' AND name='book_stats'
                """)
                has_stats = bool(cursor.fetchone())

                stats_data = {}
                if has_stats:
                    cursor.execute("SELECT COUNT(*) FROM book_stats")
                    stats_data['stats_records'] = cursor.fetchone()[0]

                # Información de la BD
                cursor.execute("PRAGMA page_count")
                page_count = cursor.fetchone()[0]

                cursor.execute("PRAGMA page_size")
                page_size = cursor.fetchone()[0]

                # Versión del schema
                cursor.execute("SELECT MAX(version) FROM schema_version")
                schema_version = cursor.fetchone()[0] or 0

                db_size_bytes = page_count * page_size

                return {
                    'books_count': books_count,
                    'db_size_mb': round(db_size_bytes / (1024 * 1024), 2),
                    'schema_version': schema_version,
                    'page_count': page_count,
                    'page_size': page_size,
                    'db_path': str(self.db_path),
                    **stats_data
                }

        except Exception as e:
            log_service_error("DatabaseConnection", e)
            return {}

    def backup_database(self, backup_path: str) -> bool:
        """Crea respaldo de la base de datos."""
        try:
            backup_file = Path(backup_path)
            backup_file.parent.mkdir(parents=True, exist_ok=True)

            with self.get_connection() as source:
                backup_conn = sqlite3.connect(str(backup_file))
                try:
                    source.backup(backup_conn)
                    self.logger.info(f"Backup creado: {backup_path}")
                    return True
                finally:
                    backup_conn.close()

        except Exception as e:
            log_service_error("DatabaseConnection", e, {"backup_path": backup_path})
            return False

    def optimize_database(self) -> bool:
        """Optimiza la base de datos."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Ejecutar optimizaciones
                from data.database_config import DatabaseOptimizer

                for query in DatabaseOptimizer.get_optimization_queries():
                    cursor.execute(query)

                self.logger.info("Base de datos optimizada")
                return True

        except Exception as e:
            log_service_error("DatabaseConnection", e)
            return False

    def run_maintenance(self) -> bool:
        """Ejecuta mantenimiento de la base de datos."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()

                # Ejecutar queries de mantenimiento
                from data.database_config import DatabaseOptimizer

                for query in DatabaseOptimizer.get_maintenance_queries():
                    try:
                        cursor.execute(query)
                        conn.commit()
                    except Exception as e:
                        self.logger.warning(f"Error en query de mantenimiento: {e}")
                        # Continuar con otros queries

                self.logger.info("Mantenimiento de BD completado")
                return True

        except Exception as e:
            log_service_error("DatabaseConnection", e)
            return False

    def get_schema_version(self) -> int:
        """Obtiene la versión actual del schema."""
        try:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT MAX(version) FROM schema_version")
                result = cursor.fetchone()
                return result[0] if result[0] else 0

        except Exception as e:
            log_service_error("DatabaseConnection", e)
            return 0

    def close_all_connections(self) -> None:
        """Cierra todas las conexiones activas."""
        try:
            with self._lock:
                for thread_id, conn in self._connections.items():
                    try:
                        conn.close()
                        self.logger.debug(f"Conexión cerrada para thread {thread_id}")
                    except Exception as e:
                        self.logger.warning(f"Error cerrando conexión {thread_id}: {e}")

                self._connections.clear()

        except Exception as e:
            log_service_error("DatabaseConnection", e)

    def __del__(self):
        """Destructor para limpiar conexiones."""
        try:
            self.close_all_connections()
        except:
            pass


# Instancia global del gestor de base de datos
_db_manager: Optional[DatabaseConnection] = None


def get_database() -> DatabaseConnection:
    """Retorna instancia singleton del gestor de base de datos."""
    global _db_manager

    if _db_manager is None:
        _db_manager = DatabaseConnection()

    return _db_manager


def close_database() -> None:
    """Cierra todas las conexiones de base de datos."""
    global _db_manager

    if _db_manager:
        _db_manager.close_all_connections()
        _db_manager = None