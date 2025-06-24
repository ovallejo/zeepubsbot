"""
Clase principal modernizada del bot ZeepubsBot.
Orquesta servicios con migraciones automáticas y health checks.
"""

from typing import Dict, Any, Optional

from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters
)
from services.auto_activity_service import AutoActivityService
from config.bot_config import get_config, get_logger, BotConstants
from data.book_repository import BookRepository
from data.database_connection import get_database
from handlers.telegram_handlers import TelegramHandlers
from services.book_service import BookService
from services.file_manager import FileManager
from services.recommendation_service import RecommendationService
from utils.error_handler import handle_error, log_service_error


class ZeepubsBot:
    """Clase principal del bot que orquesta todos los servicios modernizados."""

    def __init__(self):
        """Inicializa el bot con todos sus servicios."""
        self.config = get_config()
        self.logger = get_logger(__name__)

        # Referencias a servicios principales
        self.database = None
        self.book_repository = None
        self.book_service = None
        self.file_manager = None
        self.recommendation_service = None
        self.handlers = None
        self.auto_activity_service = None
        # Aplicación de Telegram
        self.application = None

        # Estado de inicialización
        self._initialized = False

    def initialize_application(self) -> bool:
        """
        Inicializa la aplicación completa con validaciones.

        Returns:
            True si la inicialización fue exitosa
        """
        try:
            self.logger.info("🚀 Inicializando ZeepubsBot...")

            # 1. Inicializar base de datos y ejecutar migraciones
            if not self._initialize_database():
                return False

            # 2. Inicializar servicios de negocio
            if not self._initialize_services():
                return False

            # 3. Configurar aplicación de Telegram
            if not self._initialize_telegram_application():
                return False

            # 4. Registrar handlers y comandos
            if not self._register_handlers():
                return False

            # 5. Verificar estado del sistema
            health_status = self._perform_health_check()
            if not health_status['healthy']:
                self.logger.warning("⚠️ Sistema inicializado con advertencias")
                for warning in health_status.get('warnings', []):
                    self.logger.warning(f"  - {warning}")

            self._initialized = True
            self.logger.info("✅ ZeepubsBot inicializado correctamente")
            return True

        except Exception as e:
            log_service_error("ZeepubsBot", e)
            self.logger.error(f"❌ Error inicializando bot: {e}")
            return False

    def _initialize_database(self) -> bool:
        """Inicializa base de datos y ejecuta migraciones."""
        try:
            self.logger.info("📊 Inicializando base de datos...")

            # Obtener instancia de BD (ejecuta migraciones automáticamente)
            self.database = get_database()

            # Verificar estado de la BD
            stats = self.database.get_database_stats()
            schema_version = self.database.get_schema_version()

            self.logger.info(f"✅ Base de datos lista - Schema v{schema_version}")
            self.logger.info(f"📚 Libros en BD: {stats.get('books_count', 0)}")
            self.logger.info(f"💾 Tamaño BD: {stats.get('db_size_mb', 0)} MB")

            return True

        except Exception as e:
            log_service_error("ZeepubsBot", e, {"component": "database"})
            self.logger.error(f"❌ Error inicializando base de datos: {e}")
            return False

    def _initialize_services(self) -> bool:
        """Inicializa todos los servicios de negocio."""
        try:
            self.logger.info("⚙️ Inicializando servicios...")

            # Servicios principales
            self.book_repository = BookRepository()
            self.book_service = BookService()  # Mantenido para compatibilidad
            self.file_manager = FileManager(self.book_service)
            self.recommendation_service = RecommendationService(self.book_service)

            # Inicializar handlers con servicios inyectados
            self.handlers = TelegramHandlers(
                book_service=self.book_service,
                file_manager=self.file_manager,
                recommendation_service=self.recommendation_service
            )

            self.logger.info("✅ Servicios inicializados correctamente")
            return True

        except Exception as e:
            log_service_error("ZeepubsBot", e, {"component": "services"})
            self.logger.error(f"❌ Error inicializando servicios: {e}")
            return False

    def _initialize_telegram_application(self) -> bool:
        """Configura la aplicación de Telegram."""
        try:
            self.logger.info("🤖 Configurando aplicación de Telegram...")

            self.application = Application.builder().token(
                self.config.telegram_token
            ).build()
            self.application.bot_data['zeepubs_bot'] = self

            # Registrar error handler global
            self.application.add_error_handler(handle_error)

            # *** AGREGAR ESTAS LÍNEAS NUEVAS ***
            # Inicializar servicio de actividad automática
            self.auto_activity_service = AutoActivityService(self.application.bot)
            self.logger.info("🤖 Servicio de actividad automática inicializado")

            self.logger.info("✅ Aplicación de Telegram configurada")
            return True

        except Exception as e:
            log_service_error("ZeepubsBot", e, {"component": "telegram"})
            self.logger.error(f"❌ Error configurando Telegram: {e}")
            return False

    def _register_handlers(self) -> bool:
        """Registra todos los handlers de comandos."""
        try:
            self.logger.info("📝 Registrando handlers...")

            # Comandos básicos
            basic_commands = {
                "start": self.handlers.start_command,
                "help": self.handlers.help_command,
                "about": self.handlers.about_command,
                "ebook": self.handlers.book_command,
                "list": self.handlers.list_command,
                "recommend": self.handlers.recommend_command,
                "activity": self.handlers.activity_command
            }

            for command, handler in basic_commands.items():
                self.application.add_handler(CommandHandler(command, handler))

            # *** AGREGAR ESTA LÍNEA NUEVA ***
            # Handler especial para inicializar actividad automática
            self.application.add_handler(CommandHandler("init_activity", self._init_activity_handler))

            # Handlers especiales existentes
            self.application.add_handler(
                MessageHandler(filters.Document.ALL, self.handlers.upload_command)
            )

            self.application.add_handler(
                CallbackQueryHandler(
                    self.handlers.pagination_callback,
                    pattern=BotConstants.CHARACTER_PATTERN
                )
            )

            self.application.add_handler(
                CallbackQueryHandler(
                    self.handlers.download_callback,
                    pattern=BotConstants.DOWNLOAD_PATTERN
                )
            )

            # Comandos dinámicos para libros
            dynamic_count = self._register_dynamic_commands()

            self.logger.info(f"✅ Handlers registrados - {len(basic_commands) + 1} básicos, {dynamic_count} dinámicos")
            return True

        except Exception as e:
            log_service_error("ZeepubsBot", e, {"component": "handlers"})
            self.logger.error(f"❌ Error registrando handlers: {e}")
            return False

    async def _init_activity_handler(self, update, context):
        """Handler temporal para inicializar actividad automática."""
        try:
            user_id = update.effective_user.id
            # Solo permitir al desarrollador
            if user_id == self.config.developer_chat_id:
                await self._initialize_activity_service_async()
                await update.message.reply_text("✅ Servicio de actividad inicializado!")
            else:
                await update.message.reply_text("🚫 Comando no autorizado")
        except Exception as e:
            await update.message.reply_text(f"❌ Error: {e}")


    def _register_dynamic_commands(self) -> int:
        """Registra comandos dinámicos para libros específicos."""
        try:
            book_ids = self.book_repository.get_all_book_ids()

            if not book_ids:
                self.logger.info("ℹ️ No hay libros para comandos dinámicos")
                return 0

            registered_count = 0
            for book_id in book_ids:
                if book_id and book_id.strip():
                    try:
                        handler = CommandHandler(book_id, self.handlers.book_callback)
                        self.application.add_handler(handler)
                        registered_count += 1
                    except Exception as e:
                        self.logger.warning(f"Error registrando comando /{book_id}: {e}")

            return registered_count

        except Exception as e:
            log_service_error("ZeepubsBot", e, {"component": "dynamic_commands"})
            self.logger.warning(f"Error registrando comandos dinámicos: {e}")
            return 0

    def _perform_health_check(self) -> Dict[str, Any]:
        """Realiza verificación completa del estado del sistema."""
        try:
            health_status = {
                'healthy': True,
                'warnings': [],
                'components': {}
            }

            # Verificar base de datos
            try:
                stats = self.database.get_database_stats()
                health_status['components']['database'] = {
                    'status': 'healthy',
                    'books_count': stats.get('books_count', 0),
                    'schema_version': self.database.get_schema_version()
                }
            except Exception as e:
                health_status['healthy'] = False
                health_status['warnings'].append(f"Base de datos: {e}")

            # Verificar servicios de recomendación
            try:
                rec_status = self.recommendation_service.get_service_status()
                health_status['components']['recommendations'] = rec_status

                if not rec_status.get('service_ready', False):
                    health_status['warnings'].append("Servicio de recomendaciones no disponible")
            except Exception as e:
                health_status['warnings'].append(f"Recomendaciones: {e}")

            # Verificar disponibilidad de libros
            try:
                book_count = self.book_repository.count()
                if book_count == 0:
                    health_status['warnings'].append("No hay libros disponibles")

                health_status['components']['library'] = {
                    'status': 'healthy',
                    'book_count': book_count
                }
            except Exception as e:
                health_status['warnings'].append(f"Biblioteca: {e}")

            return health_status

        except Exception as e:
            log_service_error("ZeepubsBot", e, {"component": "health_check"})
            return {
                'healthy': False,
                'warnings': [f"Error en health check: {e}"],
                'components': {}
            }

    def register_new_book_command(self, book_id: str) -> bool:
        """
        Registra un nuevo comando dinámico para un libro.

        Args:
            book_id: ID único del libro

        Returns:
            True si se registró correctamente
        """
        if not book_id or not self.application or not self._initialized:
            return False

        try:
            handler = CommandHandler(book_id, self.handlers.book_callback)
            self.application.add_handler(handler)
            self.logger.info(f"✅ Nuevo comando registrado: /{book_id}")
            return True

        except Exception as e:
            log_service_error("ZeepubsBot", e, {"book_id": book_id})
            self.logger.error(f"❌ Error registrando comando /{book_id}: {e}")
            return False

    # REEMPLAZAR EL MÉTODO start_polling() EN zeepubs_bot.py CON ESTA VERSIÓN:

    def start_polling(self) -> None:
        """Inicia el bot en modo polling con manejo de errores."""
        if not self._initialized:
            raise RuntimeError("Bot no inicializado. Llama a initialize_application() primero.")

        try:
            self.logger.info("🚀 Iniciando bot en modo polling...")
            self.logger.info("📱 Bot listo para recibir mensajes")
            self.logger.info("⏹️ Presiona Ctrl+C para detener")

            # Ejecutar bot (SIN el post_init que no existe)
            self.application.run_polling(
                drop_pending_updates=True,
                close_loop=False
            )

        except KeyboardInterrupt:
            self.logger.info("⏹️ Interrupción de teclado detectada")
        except Exception as e:
            log_service_error("ZeepubsBot", e, {"component": "polling"})
            self.logger.error(f"❌ Error ejecutando bot: {e}")
            raise
        finally:
            self.logger.info("🔄 Bot detenido")

    async def stop(self) -> None:
        """Detiene el bot de forma limpia."""
        try:
            self.logger.info("🛑 Deteniendo bot...")

            # *** AGREGAR ESTAS LÍNEAS NUEVAS ***
            # Detener servicio de actividad automática
            if self.auto_activity_service:
                await self.auto_activity_service.stop_activity_service()

            if self.application:
                await self.application.stop()

            # Limpiar recursos
            self._cleanup_resources()

            self.logger.info("✅ Bot detenido correctamente")

        except Exception as e:
            log_service_error("ZeepubsBot", e, {"component": "stop"})
            self.logger.error(f"❌ Error deteniendo bot: {e}")

    async def _initialize_activity_service_async(self) -> None:
        """Inicializa el servicio de actividad de forma asíncrona."""
        try:
            if self.auto_activity_service:
                activity_started = await self.auto_activity_service.start_activity_service()
                if activity_started:
                    self.logger.info("🤖 Servicio de actividad automática iniciado")
                else:
                    self.logger.warning("⚠️ No se pudo iniciar servicio de actividad")
        except Exception as e:
            log_service_error("ZeepubsBot", e, {"component": "activity_init"})
            self.logger.error(f"❌ Error iniciando servicio de actividad: {e}")

    def _cleanup_resources(self) -> None:
        """Limpia recursos del sistema."""
        try:
            # Limpiar archivos temporales
            if self.file_manager:
                self.file_manager.cleanup_temp_directory()

            # Cerrar conexiones de BD
            if self.database:
                self.database.close_all_connections()

            self.logger.info("🧹 Recursos limpiados")

        except Exception as e:
            log_service_error("ZeepubsBot", e, {"component": "cleanup"})
            self.logger.warning(f"⚠️ Error en limpieza: {e}")

    def get_application(self) -> Optional[Application]:
        """Retorna la aplicación de Telegram para testing."""
        return self.application

    def get_services(self) -> Dict[str, Any]:
        """Retorna diccionario con todos los servicios para debugging."""
        return {
            'database': self.database,
            'book_repository': self.book_repository,
            'book_service': self.book_service,
            'file_manager': self.file_manager,
            'recommendation_service': self.recommendation_service,
            'handlers': self.handlers,
            'auto_activity_service': self.auto_activity_service  # *** LÍNEA NUEVA ***
        }

    def get_system_status(self) -> Dict[str, Any]:
        """Retorna estado completo del sistema."""
        try:
            if not self._initialized:
                return {'status': 'not_initialized'}

            # Obtener estadísticas de componentes
            db_stats = self.database.get_database_stats() if self.database else {}
            rec_status = self.recommendation_service.get_service_status() if self.recommendation_service else {}
            temp_stats = self.file_manager.get_temp_directory_stats() if self.file_manager else {}

            # *** AGREGAR ESTA LÍNEA NUEVA ***
            activity_status = self.auto_activity_service.get_service_status() if self.auto_activity_service else {}

            return {
                'status': 'running',
                'initialized': self._initialized,
                'database': db_stats,
                'recommendations': rec_status,
                'temp_files': temp_stats,
                'auto_activity': activity_status,  # *** LÍNEA NUEVA ***
                'handlers_registered': bool(self.handlers),
                'telegram_app_ready': bool(self.application)
            }

        except Exception as e:
            log_service_error("ZeepubsBot", e, {"component": "system_status"})
            return {
                'status': 'error',
                'error': str(e)
            }

    def is_initialized(self) -> bool:
        """Verifica si el bot está completamente inicializado."""
        return self._initialized

    def restart_services(self) -> bool:
        """Reinicia servicios sin reiniciar el bot completo."""
        try:
            self.logger.info("🔄 Reiniciando servicios...")

            # Limpiar recursos actuales
            self._cleanup_resources()

            # Reinicializar servicios
            if self._initialize_services():
                self.logger.info("✅ Servicios reiniciados correctamente")
                return True
            else:
                self.logger.error("❌ Error reiniciando servicios")
                return False

        except Exception as e:
            log_service_error("ZeepubsBot", e, {"component": "restart"})
            self.logger.error(f"❌ Error reiniciando servicios: {e}")
            return False


def create_bot() -> Optional[ZeepubsBot]:
    """
    Factory function para crear una instancia del bot.

    Returns:
        Instancia de ZeepubsBot inicializada o None si falla
    """
    try:
        bot = ZeepubsBot()

        if bot.initialize_application():
            return bot
        else:
            logger = get_logger(__name__)
            logger.error("❌ Error inicializando bot")
            return None

    except Exception as e:
        logger = get_logger(__name__)
        log_service_error("create_bot", e)
        logger.error(f"❌ Error creando bot: {e}")
        return None


def main() -> None:
    """Función principal para ejecutar el bot."""
    try:
        # Crear e inicializar bot
        bot = create_bot()

        if not bot:
            raise RuntimeError("No se pudo crear instancia del bot")

        # Mostrar estado inicial
        status = bot.get_system_status()
        logger = get_logger(__name__)
        logger.info(f"📊 Estado del sistema: {status.get('status', 'unknown')}")

        # Iniciar polling
        bot.start_polling()

    except Exception as e:
        logger = get_logger(__name__)
        log_service_error("main", e)
        logger.critical(f"💥 Error fatal iniciando bot: {e}")
        raise


if __name__ == "__main__":
    main()
