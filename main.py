"""
Punto de entrada modernizado para ZeepubsBot.
Incluye health checks completos y gestión avanzada del ciclo de vida.
"""

import os
import signal
import sys
from typing import Optional, Dict, Any

from config.bot_config import get_config, get_logger
from data.database_connection import get_database
from zeepubs_bot import ZeepubsBot, create_bot
from utils.error_handler import log_service_error


class BotLauncher:
    """Launcher principal del bot con gestión completa de ciclo de vida."""

    def __init__(self):
        """Inicializa el launcher."""
        self.logger = get_logger(__name__)
        self.bot: Optional[ZeepubsBot] = None
        self._shutdown_requested = False

    def setup_signal_handlers(self) -> None:
        """Configura manejadores de señales para cierre graceful."""
        def signal_handler(signum, frame):
            """Maneja señales de cierre del sistema."""
            signal_names = {
                signal.SIGINT: "SIGINT (Ctrl+C)",
                signal.SIGTERM: "SIGTERM (Sistema)"
            }

            signal_name = signal_names.get(signum, f"Signal {signum}")
            self.logger.info(f"🛑 Señal {signal_name} recibida - Iniciando cierre graceful...")

            self._shutdown_requested = True

            if self.bot:
                self.bot.stop()

        # Registrar manejadores para señales comunes
        try:
            signal.signal(signal.SIGINT, signal_handler)
            signal.signal(signal.SIGTERM, signal_handler)
            self.logger.debug("✅ Manejadores de señales configurados")
        except Exception as e:
            self.logger.warning(f"⚠️ Error configurando señales: {e}")

    def validate_environment(self) -> Dict[str, Any]:
        """
        Valida que el entorno esté correctamente configurado.

        Returns:
            Dict con resultado de validación y detalles
        """
        validation_result = {
            'valid': True,
            'errors': [],
            'warnings': [],
            'details': {}
        }

        try:
            self.logger.info("🔍 Validando entorno de ejecución...")

            # Verificar versión de Python
            python_version = sys.version_info
            validation_result['details']['python_version'] = f"{python_version.major}.{python_version.minor}.{python_version.micro}"

            if python_version < (3, 8):
                validation_result['valid'] = False
                validation_result['errors'].append(f"Python 3.8+ requerido. Actual: {python_version.major}.{python_version.minor}")

            # Validar configuración crítica
            config = get_config()

            if not config.telegram_token:
                validation_result['valid'] = False
                validation_result['errors'].append("Token de Telegram no configurado (ZEEPUBSBOT_TOKEN)")

            if not config.deepseek_api_key:
                validation_result['warnings'].append("API key de DeepSeek no configurada - recomendaciones deshabilitadas")

            validation_result['details']['telegram_configured'] = bool(config.telegram_token)
            validation_result['details']['ai_configured'] = bool(config.deepseek_api_key)

            # Verificar estructura de directorios críticos
            required_dirs = ['config', 'data', 'utils', 'services', 'handlers']
            missing_dirs = []

            for dir_name in required_dirs:
                if not os.path.exists(dir_name):
                    missing_dirs.append(dir_name)

            if missing_dirs:
                validation_result['valid'] = False
                validation_result['errors'].append(f"Directorios faltantes: {', '.join(missing_dirs)}")

            validation_result['details']['directories_ok'] = len(missing_dirs) == 0

            # Verificar permisos de escritura
            temp_dir = "temp_uploads"
            try:
                os.makedirs(temp_dir, exist_ok=True)
                validation_result['details']['write_permissions'] = True
            except Exception as e:
                validation_result['warnings'].append(f"Problema con permisos de escritura: {e}")
                validation_result['details']['write_permissions'] = False

            if validation_result['valid']:
                self.logger.info("✅ Validación de entorno completada exitosamente")
            else:
                self.logger.error("❌ Validación de entorno falló")

            return validation_result

        except Exception as e:
            log_service_error("BotLauncher", e, {"component": "environment_validation"})
            return {
                'valid': False,
                'errors': [f"Error en validación: {str(e)}"],
                'warnings': [],
                'details': {}
            }

    def initialize_bot(self) -> bool:
        """
        Inicializa el bot y sus servicios con validaciones.

        Returns:
            True si la inicialización fue exitosa
        """
        try:
            self.logger.info("🤖 Inicializando ZeepubsBot...")

            # Crear instancia del bot
            self.bot = create_bot()

            if not self.bot:
                self.logger.error("❌ Error creando instancia del bot")
                return False

            # Verificar que está completamente inicializado
            if not self.bot.is_initialized():
                self.logger.error("❌ Bot no se inicializó correctamente")
                return False

            self.logger.info("✅ Bot inicializado correctamente")
            return True

        except Exception as e:
            log_service_error("BotLauncher", e, {"component": "bot_initialization"})
            self.logger.error(f"❌ Error inicializando bot: {e}")
            return False

    def run_bot(self) -> None:
        """Ejecuta el bot en modo polling con manejo de errores."""
        if not self.bot:
            raise RuntimeError("Bot no inicializado")

        try:
            self.logger.info("🚀 Iniciando ZeepubsBot...")
            self._log_startup_info()

            # Ejecutar bot
            self.bot.start_polling()

        except KeyboardInterrupt:
            self.logger.info("⌨️ Interrupción de teclado detectada")
        except Exception as e:
            log_service_error("BotLauncher", e, {"component": "bot_execution"})
            self.logger.error(f"❌ Error ejecutando bot: {e}")
            raise
        finally:
            self.logger.info("🔄 Proceso de bot finalizado")

    def _log_startup_info(self) -> None:
        """Registra información útil del startup."""
        try:
            if self.bot:
                status = self.bot.get_system_status()

                # Información de la base de datos
                db_info = status.get('database', {})
                books_count = db_info.get('books_count', 0)
                db_size = db_info.get('db_size_mb', 0)

                self.logger.info(f"📚 Biblioteca: {books_count} libros disponibles")
                self.logger.info(f"💾 Base de datos: {db_size} MB")

                # Estado de recomendaciones
                rec_info = status.get('recommendations', {})
                if rec_info.get('service_ready', False):
                    self.logger.info("🔮 Servicio de recomendaciones: ✅ Activo")
                else:
                    self.logger.info("🔮 Servicio de recomendaciones: ⚠️ No disponible")

        except Exception as e:
            self.logger.debug(f"Error loggeando info de startup: {e}")

    def cleanup(self) -> None:
        """Limpia recursos y realiza tareas de cierre."""
        try:
            self.logger.info("🧹 Iniciando limpieza de recursos...")

            if self.bot:
                # Obtener servicios para limpieza
                services = self.bot.get_services()

                # Limpiar archivos temporales
                if 'file_manager' in services and services['file_manager']:
                    services['file_manager'].cleanup_temp_directory()

                # Cerrar conexiones de BD
                if 'database' in services and services['database']:
                    services['database'].close_all_connections()

            self.logger.info("✅ Limpieza completada")

        except Exception as e:
            log_service_error("BotLauncher", e, {"component": "cleanup"})
            self.logger.error(f"❌ Error durante limpieza: {e}")

    def launch(self) -> int:
        """
        Lanza el bot con manejo completo de errores y validaciones.

        Returns:
            Código de salida (0 = éxito, 1 = error)
        """
        try:
            # Configurar manejadores de señales
            self.setup_signal_handlers()

            # Validar entorno
            validation = self.validate_environment()
            if not validation['valid']:
                self.logger.error("❌ Validación de entorno falló:")
                for error in validation['errors']:
                    self.logger.error(f"  • {error}")
                return 1

            # Mostrar advertencias si las hay
            for warning in validation.get('warnings', []):
                self.logger.warning(f"⚠️ {warning}")

            # Inicializar bot
            if not self.initialize_bot():
                self.logger.error("❌ Inicialización del bot falló")
                return 1

            # Ejecutar bot
            self.run_bot()

            return 0

        except KeyboardInterrupt:
            self.logger.info("👋 Cierre solicitado por usuario")
            return 0
        except Exception as e:
            log_service_error("BotLauncher", e, {"component": "main_launch"})
            self.logger.critical(f"💥 Error crítico: {e}")
            return 1
        finally:
            # Limpieza final
            self.cleanup()


def print_startup_banner() -> None:
    """Muestra banner de inicio con información del sistema."""
    banner = """
    ███████╗███████╗███████╗██████╗ ██╗   ██╗██████╗ ███████╗
    ╚══███╔╝██╔════╝██╔════╝██╔══██╗██║   ██║██╔══██╗██╔════╝
      ███╔╝ █████╗  █████╗  ██████╔╝██║   ██║██████╔╝███████╗
     ███╔╝  ██╔══╝  ██╔══╝  ██╔═══╝ ██║   ██║██╔══██╗╚════██║
    ███████╗███████╗███████╗██║     ╚██████╔╝██████╔╝███████║
    ╚══════╝╚══════╝╚══════╝╚═╝      ╚═════╝ ╚═════╝ ╚══════╝
    
    📚 Bot de Gestión de Libros EPUB
    🤖 Powered by Telegram Bot API  
    🔮 Con recomendaciones de IA
    ⚡ Arquitectura modernizada
    
    """
    print(banner)


def health_check() -> int:
    """
    Verifica el estado de salud del bot sin ejecutarlo.

    Returns:
        Código de salida (0 = saludable, 1 = problemas)
    """
    try:
        print("🏥 === HEALTH CHECK DE ZEEPUBSBOT ===\n")

        # Crear launcher para validaciones
        launcher = BotLauncher()

        # Validar entorno
        print("🔍 Validando entorno...")
        validation = launcher.validate_environment()

        if validation['valid']:
            print("✅ Entorno: OK")
        else:
            print("❌ Entorno: ERRORES ENCONTRADOS")
            for error in validation['errors']:
                print(f"  • {error}")

        for warning in validation.get('warnings', []):
            print(f"⚠️ Advertencia: {warning}")

        # Verificar base de datos
        print("\n📊 Verificando base de datos...")
        try:
            db = get_database()
            stats = db.get_database_stats()
            schema_version = db.get_schema_version()

            print(f"✅ Base de datos: OK")
            print(f"  • Schema version: {schema_version}")
            print(f"  • Libros: {stats.get('books_count', 0)}")
            print(f"  • Tamaño: {stats.get('db_size_mb', 0)} MB")

        except Exception as e:
            print(f"❌ Base de datos: ERROR - {e}")
            validation['valid'] = False

        # Verificar configuración crítica
        print("\n⚙️ Verificando configuración...")
        try:
            config = get_config()
            print(f"✅ Telegram Bot: {'Configurado' if config.telegram_token else 'NO CONFIGURADO'}")
            print(f"🔮 DeepSeek AI: {'Configurado' if config.deepseek_api_key else 'NO CONFIGURADO'}")
            print(f"📄 Max message length: {config.max_message_length}")
            print(f"📑 Books per page: {config.books_per_page}")

        except Exception as e:
            print(f"❌ Configuración: ERROR - {e}")
            validation['valid'] = False

        # Intentar crear bot (sin ejecutar)
        print("\n🤖 Verificando inicialización del bot...")
        try:
            bot = create_bot()
            if bot and bot.is_initialized():
                print("✅ Bot: Inicialización OK")

                # Obtener estado del sistema
                status = bot.get_system_status()
                rec_status = status.get('recommendations', {})

                if rec_status.get('service_ready', False):
                    print("✅ Recomendaciones: Servicio listo")
                else:
                    print("⚠️ Recomendaciones: Servicio no disponible")

            else:
                print("❌ Bot: Error en inicialización")
                validation['valid'] = False

        except Exception as e:
            print(f"❌ Bot: ERROR - {e}")
            validation['valid'] = False

        # Resultado final
        print(f"\n🏥 === RESULTADO FINAL ===")
        if validation['valid']:
            print("✅ SISTEMA SALUDABLE - Listo para ejecutar")
            return 0
        else:
            print("❌ SISTEMA CON PROBLEMAS - Revisar errores")
            return 1

    except Exception as e:
        print(f"💥 Health check falló: {e}")
        return 1


def development_mode() -> int:
    """Modo de desarrollo con logging detallado."""
    import logging

    print("🔧 === MODO DE DESARROLLO ===")
    print("📊 Logging detallado habilitado")
    print("🐛 Información de debug visible\n")

    # Configurar logging más detallado
    logging.getLogger().setLevel(logging.DEBUG)

    return main()


def print_usage() -> None:
    """Muestra información de uso del programa."""
    print("""
🔧 === USO DE ZEEPUBSBOT ===

Modos de ejecución:
  python main.py              - Ejecutar bot normal
  BOT_MODE=development         - Ejecutar con debug detallado  
  BOT_MODE=health              - Solo health check (no ejecutar)

Variables de entorno requeridas:
  ZEEPUBSBOT_TOKEN            - Token del bot de Telegram
  DEEPSEEK_TOKEN              - API key de DeepSeek (opcional)
  DEVELOPER_CHAT_ID           - Chat ID del desarrollador

Variables opcionales:
  BOOKS_PER_PAGE=10           - Libros por página en listas
  API_TIMEOUT=30              - Timeout para APIs externas
  MAX_MESSAGE_LENGTH=4096     - Longitud máxima de mensajes

Ejemplos:
  export ZEEPUBSBOT_TOKEN="tu_token_aqui"
  python main.py

  BOT_MODE=health python main.py
  BOT_MODE=development python main.py
""")


def main() -> int:
    """Función principal del programa."""
    try:
        # Verificar argumentos especiales
        if len(sys.argv) > 1:
            if sys.argv[1] in ['--help', '-h', 'help']:
                print_usage()
                return 0
            elif sys.argv[1] in ['--health', 'health']:
                return health_check()

        # Mostrar banner
        print_startup_banner()

        # Crear y ejecutar launcher
        launcher = BotLauncher()
        return launcher.launch()

    except Exception as e:
        logger = get_logger(__name__)
        log_service_error("main", e)
        logger.critical(f"💥 Error fatal en main: {e}")
        return 1


if __name__ == "__main__":
    # Detectar modo de ejecución
    mode = os.getenv("BOT_MODE", "production").lower()

    if mode == "development":
        exit_code = development_mode()
    elif mode == "health":
        exit_code = health_check()
    else:
        exit_code = main()

    sys.exit(exit_code)