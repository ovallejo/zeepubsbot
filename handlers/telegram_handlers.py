"""
Handlers simplificados para comandos y callbacks de Telegram.
Código limpio, simple y sin errores.
"""

import json
from typing import Dict, Optional, Any

from telegram import Update, InlineKeyboardMarkup
from telegram.constants import ChatAction, ParseMode
from telegram.ext import ContextTypes, CallbackContext

from config.bot_config import get_config, get_logger, BotConstants
from data.book_repository import BookRepository
from utils.error_handler import log_service_error
from utils.message_formatter import MessageFormatter


class TelegramHandlers:
    """Maneja todos los comandos y callbacks de Telegram."""

    def __init__(self, book_service, file_manager, recommendation_service):
        """Inicializa handlers con servicios inyectados."""
        self.file_manager = file_manager
        self.recommendation_service = recommendation_service
        self.book_repository = BookRepository()

        self.config = get_config()
        self.logger = get_logger(__name__)
        self.message_formatter = MessageFormatter()
        self.bot_messages = self._load_messages()

    def _load_messages(self) -> Dict[str, str]:
        """Carga mensajes del bot desde archivo JSON con fallbacks."""
        try:
            with open(BotConstants.MESSAGES_FILE, encoding="UTF-8") as file:
                messages = json.load(file)
                if messages:
                    return messages
        except (FileNotFoundError, json.JSONDecodeError) as e:
            self.logger.warning(f"No se pudieron cargar mensajes: {e}")

        # Fallback messages
        return {
            'bienvenida': '¡Bienvenido a ZeepubsBot! 📚\n\nTu biblioteca personal de libros EPUB.',
            'ayuda': '🔧 <b>Ayuda de ZeepubsBot</b>\n\nUsa los comandos para explorar la biblioteca.',
            'info': '📖 <b>Acerca de ZeepubsBot</b>\n\nBot para gestión de libros EPUB con recomendaciones IA.'
        }

    async def start_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja el comando /start."""
        try:
            message = self.bot_messages.get('bienvenida')
            await self._send_message(update, message, ParseMode.HTML)
        except Exception as e:
            await self._handle_error(update, e, "start")

    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja el comando /help."""
        try:
            commands = [
                '/start - Mensaje de bienvenida del bot',
                '/help - Muestra esta ayuda',
                '/ebook <nombre> - Busca libros por título',
                '/list - Lista todos los libros disponibles',
                '/recommend <preferencias> - Recomendaciones personalizadas',
                '/about - Información sobre el bot'
            ]

            base_message = self.bot_messages.get('ayuda')
            message = self.message_formatter.format_help_message(base_message, commands)
            await self._send_message(update, message, ParseMode.HTML)
        except Exception as e:
            await self._handle_error(update, e, "help")

    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja el comando /about con estadísticas detalladas."""
        try:
            # Obtener estadísticas detalladas
            stats = await self._get_detailed_stats()

            base_message = self.bot_messages.get('info')
            detailed_stats = self._format_detailed_stats(stats)

            message = f"{base_message}\n\n{detailed_stats}"
            await self._send_message(update, message, ParseMode.HTML)
        except Exception as e:
            await self._handle_error(update, e, "about")

    async def _get_detailed_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas detalladas del sistema."""
        try:
            stats = {}

            # Estadísticas básicas de libros
            stats['total_books'] = self.book_repository.count()

            # Obtener estadísticas de base de datos
            db_stats = self.book_repository.db.get_database_stats()
            stats['db_size_mb'] = db_stats.get('db_size_mb', 0)

            # Estadísticas de uso
            usage_stats = await self._get_usage_statistics()
            stats.update(usage_stats)

            # Libros más populares
            popular_books = self.book_repository.find_popular(3)
            stats['popular_books'] = popular_books

            # Estadísticas de idiomas
            language_stats = await self._get_language_statistics()
            stats['languages'] = language_stats

            # Estado de servicios
            rec_status = self.recommendation_service.get_service_status()
            stats['ai_available'] = rec_status.get('service_ready', False)

            return stats

        except Exception as e:
            self.logger.error(f"Error obteniendo estadísticas detalladas: {e}")
            return {'total_books': self.book_repository.count()}

    async def _get_usage_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas de uso de la biblioteca."""
        try:
            # Query para obtener estadísticas agregadas
            query = """
                    SELECT COUNT(*)                                              as books_with_stats, \
                           SUM(downloads)                                        as total_downloads, \
                           SUM(searches)                                         as total_searches, \
                           AVG(downloads)                                        as avg_downloads, \
                           MAX(downloads)                                        as max_downloads, \
                           COUNT(CASE WHEN downloads > 0 THEN 1 END)             as downloaded_books, \
                           COUNT(CASE WHEN last_accessed IS NOT NULL THEN 1 END) as accessed_books
                    FROM book_stats \
                    """

            results = self.book_repository.db.execute_query(query)

            if results:
                row = results[0]
                return {
                    'total_downloads': row['total_downloads'] or 0,
                    'total_searches': row['total_searches'] or 0,
                    'avg_downloads': round(row['avg_downloads'] or 0, 1),
                    'max_downloads': row['max_downloads'] or 0,
                    'downloaded_books': row['downloaded_books'] or 0,
                    'accessed_books': row['accessed_books'] or 0
                }

            return {}

        except Exception as e:
            self.logger.error(f"Error obteniendo estadísticas de uso: {e}")
            return {}

    # Actualización del método about_command en telegram_handlers.py

    async def about_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja el comando /about con estadísticas detalladas."""
        try:
            # Obtener estadísticas detalladas
            stats = await self._get_detailed_stats()

            base_message = self.bot_messages.get('info')
            detailed_stats = self._format_detailed_stats(stats)

            message = f"{base_message}\n\n{detailed_stats}"
            await self._send_message(update, message, ParseMode.HTML)
        except Exception as e:
            await self._handle_error(update, e, "about")

    async def _get_detailed_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas detalladas del sistema."""
        try:
            stats = {}

            # Estadísticas básicas de libros
            stats['total_books'] = self.book_repository.count()

            # Obtener estadísticas de base de datos
            db_stats = self.book_repository.db.get_database_stats()
            stats['db_size_mb'] = db_stats.get('db_size_mb', 0)

            # Estadísticas de uso
            usage_stats = await self._get_usage_statistics()
            stats.update(usage_stats)

            # Libros más populares
            popular_books = self.book_repository.find_popular(3)
            stats['popular_books'] = popular_books

            # Estadísticas de idiomas
            language_stats = await self._get_language_statistics()
            stats['languages'] = language_stats

            # Estado de servicios
            rec_status = self.recommendation_service.get_service_status()
            stats['ai_available'] = rec_status.get('service_ready', False)

            return stats

        except Exception as e:
            self.logger.error(f"Error obteniendo estadísticas detalladas: {e}")
            return {'total_books': self.book_repository.count()}

    async def _get_usage_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas de uso de la biblioteca."""
        try:
            # Query para obtener estadísticas agregadas
            query = """
                    SELECT COUNT(*)                                              as books_with_stats, \
                           SUM(downloads)                                        as total_downloads, \
                           SUM(searches)                                         as total_searches, \
                           AVG(downloads)                                        as avg_downloads, \
                           MAX(downloads)                                        as max_downloads, \
                           COUNT(CASE WHEN downloads > 0 THEN 1 END)             as downloaded_books, \
                           COUNT(CASE WHEN last_accessed IS NOT NULL THEN 1 END) as accessed_books
                    FROM book_stats \
                    """

            results = self.book_repository.db.execute_query(query)

            if results:
                row = results[0]
                return {
                    'total_downloads': row['total_downloads'] or 0,
                    'total_searches': row['total_searches'] or 0,
                    'avg_downloads': round(row['avg_downloads'] or 0, 1),
                    'max_downloads': row['max_downloads'] or 0,
                    'downloaded_books': row['downloaded_books'] or 0,
                    'accessed_books': row['accessed_books'] or 0
                }

            return {}

        except Exception as e:
            self.logger.error(f"Error obteniendo estadísticas de uso: {e}")
            return {}

    async def _get_language_statistics(self) -> Dict[str, int]:
        """Obtiene estadísticas por idioma."""
        try:
            query = """
                    SELECT language, COUNT(*) as count
                    FROM books
                    GROUP BY language
                    ORDER BY count DESC \
                    """

            results = self.book_repository.db.execute_query(query)

            language_names = {
                'es': 'Español',
                'en': 'English',
                'fr': 'Français',
                'de': 'Deutsch',
                'it': 'Italiano',
                'pt': 'Português',
                'unknown': 'Desconocido'
            }

            languages = {}
            for row in results:
                lang_code = row['language']
                lang_name = language_names.get(lang_code, lang_code.title())
                languages[lang_name] = row['count']

            return languages

        except Exception as e:
            self.logger.error(f"Error obteniendo estadísticas de idiomas: {e}")
            return {}

    def _format_detailed_stats(self, stats: Dict[str, Any]) -> str:
        """Formatea las estadísticas en un mensaje HTML atractivo."""
        try:
            total_books = stats.get('total_books', 0)
            total_downloads = stats.get('total_downloads', 0)
            total_searches = stats.get('total_searches', 0)
            downloaded_books = stats.get('downloaded_books', 0)
            db_size = stats.get('db_size_mb', 0)
            ai_available = stats.get('ai_available', False)

            # Sección principal
            message = f"""
    📊 <b>Estadísticas de la Biblioteca</b>

    📚 <b>Colección:</b>
    • Libros disponibles: <b>{total_books}</b>
    • Libros descargados: <b>{downloaded_books}</b> de {total_books}
    • Base de datos: <b>{db_size} MB</b>

    📈 <b>Actividad:</b>
    • Total descargas: <b>{total_downloads:,}</b>
    • Total búsquedas: <b>{total_searches:,}</b>"""

            # Agregar promedio si hay datos
            if stats.get('avg_downloads', 0) > 0:
                avg_downloads = stats.get('avg_downloads', 0)
                max_downloads = stats.get('max_downloads', 0)
                message += f"\n• Promedio descargas: <b>{avg_downloads}</b>"
                message += f"\n• Libro más popular: <b>{max_downloads}</b> descargas"

            # Libros populares
            popular_books = stats.get('popular_books', [])
            if popular_books:
                message += f"\n\n🔥 <b>Más Populares:</b>"
                for i, book in enumerate(popular_books[:3], 1):
                    title = book.title[:30] + "..." if len(book.title) > 30 else book.title
                    # Obtener descargas del libro
                    book_stats = self.book_repository.get_book_stats(book.book_id)
                    downloads = book_stats.downloads if book_stats else 0
                    message += f"\n{i}. <i>{title}</i> ({downloads} desc.)"

            # Idiomas
            languages = stats.get('languages', {})
            if languages:
                message += f"\n\n🌐 <b>Por Idioma:</b>"
                for lang, count in list(languages.items())[:3]:
                    message += f"\n• {lang}: <b>{count}</b>"

            # Estado de servicios
            message += f"\n\n🤖 <b>Servicios:</b>"
            message += f"\n• Recomendaciones IA: {'✅ Activo' if ai_available else '⚠️ No disponible'}"
            message += f"\n• Búsqueda: <b>✅ Activo</b>"
            message += f"\n• Subida de archivos: <b>✅ Activo</b>"

            # Información adicional
            message += f"\n\n💡 <b>Consejos:</b>"
            message += f"\n• Usa <code>/list</code> para ver todos los libros"
            message += f"\n• Usa <code>/recommend [tema]</code> para recomendaciones"

            return message.strip()

        except Exception as e:
            self.logger.error(f"Error formateando estadísticas: {e}")
            total_books = stats.get('total_books', 0)
            return f"📊 <b>Estadísticas:</b>\n• Libros disponibles: <b>{total_books}</b>"

    # También agregar este método auxiliar para obtener el libro más descargado
    async def _get_most_popular_book(self) -> Optional[str]:
        """Obtiene el libro más popular por descargas."""
        try:
            query = """
                    SELECT b.title, bs.downloads
                    FROM books b
                             JOIN book_stats bs ON b.book_id = bs.book_id
                    WHERE bs.downloads > 0
                    ORDER BY bs.downloads DESC
                    LIMIT 1 \
                    """

            results = self.book_repository.db.execute_query(query)

            if results:
                row = results[0]
                title = row['title']
                downloads = row['downloads']
                return f"{title[:25]}{'...' if len(title) > 25 else ''} ({downloads} desc.)"

            return None

        except Exception as e:
            self.logger.error(f"Error obteniendo libro más popular: {e}")
            return None

    async def book_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja el comando /ebook para buscar libros."""
        try:
            book_name = " ".join(context.args).strip()
            if not book_name:
                error_msg = self.message_formatter.format_error_message('missing_book_name')
                await update.message.reply_text(error_msg)
                return

            books = self.book_repository.search(book_name)
            if not books:
                error_msg = self.message_formatter.format_error_message('book_not_found')
                await update.message.reply_text(error_msg)
                return

            # Actualizar estadísticas de búsqueda
            for book in books:
                self.book_repository.increment_searches(book.book_id)

            # Crear paginación
            keyboard, message = self._create_book_pagination(books, 'm_ebook')
            await self._send_message(update, message, ParseMode.MARKDOWN, keyboard)
        except Exception as e:
            await self._handle_error(update, e, "ebook")

    async def list_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja el comando /list para mostrar todos los libros."""
        try:
            books = self.book_repository.find_all()
            if not books:
                error_msg = self.message_formatter.format_error_message('no_books')
                await update.message.reply_text(error_msg)
                return

            keyboard, message = self._create_book_pagination(books, "m_list")
            await self._send_message(update, message, ParseMode.MARKDOWN, keyboard)
        except Exception as e:
            await self._handle_error(update, e, "list")

    async def recommend_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja el comando /recommend para recomendaciones."""
        try:
            user_message = " ".join(context.args).strip()

            # Validar que hay argumentos
            if not user_message:
                help_message = self._create_recommendation_help_message()
                await update.message.reply_text(help_message, parse_mode=ParseMode.MARKDOWN)
                return

            # Validar longitud mínima
            if len(user_message) < 3:
                await update.message.reply_text(
                    "🔮 **Necesito más información**\n\n"
                    "Por favor, describe con más detalle qué tipo de libro te gustaría leer.\n\n"
                    "💡 *Ejemplo: 'Novelas de misterio ambientadas en la época victoriana'*",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            # Procesar recomendación
            await self.recommendation_service.process_recommendation(
                user_message, update, context
            )
        except Exception as e:
            await self._handle_error(update, e, "recommend")

    async def upload_command(self, update: Update, context: CallbackContext) -> None:
        """Maneja la subida de archivos EPUB."""
        try:
            user_id = update.effective_user.id

            # VERIFICAR SI ES EL DESARROLLADOR
            if not self._is_developer(user_id):
                await self._send_unauthorized_message(update)
                return

            result = await self.file_manager.process_uploaded_file(
                update.message.effective_attachment, context
            )

            if result['success']:
                book_data = result['book_data']
                message = self.message_formatter.format_new_book_announcement(book_data)

                # Registrar nuevo comando dinámico
                zeepubs_bot = context.application.bot_data.get('zeepubs_bot')
                if zeepubs_bot:
                    zeepubs_bot.register_new_book_command(book_data['id'])

                await self._send_message(update, message, ParseMode.MARKDOWN)
            else:
                error_msg = result.get('message', 'Error procesando el archivo')
                await update.message.reply_text(error_msg, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await self._handle_error(update, e, "upload")

    async def _send_unauthorized_message(self, update: Update) -> None:
        """Envía mensaje cuando un usuario no autorizado intenta subir archivos."""
        try:
            unauthorized_message = """
    🚫 **Acceso Restringido**

    La subida de libros está limitada al administrador del bot.

    📚 **¿Quieres agregar un libro?**
    • Contacta al administrador del bot
    • Sugiere libros que te gustaría ver en la biblioteca
    • Usa los comandos disponibles para explorar el catálogo actual

    💡 **Comandos disponibles:**
    • `/list` - Ver todos los libros
    • `/ebook [título]` - Buscar libros específicos  
    • `/recommend [tema]` - Obtener recomendaciones
    • `/help` - Ver todos los comandos

    ✨ ¡Disfruta leyendo la biblioteca actual!
    """

            await update.message.reply_text(
                unauthorized_message,
                parse_mode=ParseMode.MARKDOWN
            )

            # Log del intento no autorizado
            self.logger.warning(
                f"Intento de subida no autorizado - Usuario: {update.effective_user.id} "
                f"(@{update.effective_user.username})"
            )

        except Exception as e:
            self.logger.error(f"Error enviando mensaje de no autorizado: {e}")
            # Fallback simple
            await update.message.reply_text(
                "🚫 Solo el administrador puede subir archivos."
            )

    def _is_developer(self, user_id: int) -> bool:
        """Verifica si el usuario es el desarrollador autorizado."""
        try:
            developer_id = self.config.developer_chat_id
            return user_id == developer_id
        except Exception as e:
            self.logger.error(f"Error verificando desarrollador: {e}")
            return False

    async def book_callback(self, update: Update, context: CallbackContext) -> None:
        """Maneja callbacks dinámicos de libros específicos."""
        try:
            # Extraer book_id del comando
            book_id = update.message.text.replace("/", "").replace("@ZeepubsBot", "")

            book = self.book_repository.find_by_book_id(book_id)
            if not book:
                await update.message.reply_text("Libro no encontrado.")
                return

            # Actualizar estadísticas
            self.book_repository.update_last_accessed(book_id)

            # Formatear detalles del libro
            book_dict = book.to_dict()
            message = self.message_formatter.format_book_details(book_dict)
            keyboard = self.message_formatter.create_download_keyboard(book_id)

            # Enviar con o sin portada
            if book.cover_id:
                await self._send_book_with_cover(update, context, book.cover_id, message, keyboard)
            else:
                await update.message.reply_text(
                    text=message,
                    parse_mode=ParseMode.MARKDOWN,
                    reply_markup=keyboard
                )
        except Exception as e:
            await self._handle_error(update, e, "book_callback")

    async def pagination_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja callbacks de paginación."""
        try:
            query = update.callback_query
            await query.answer()

            # Parsear callback data
            callback_data = query.data
            parts = callback_data.split('#')

            if len(parts) < 3:
                await query.edit_message_text("Error en paginación")
                return

            page = int(parts[1])
            menu = parts[2]

            # Obtener libros según el menú
            if menu == 'm_list':
                books = self.book_repository.find_all()
            else:  # m_ebook - fallback temporal
                books = self.book_repository.find_all()

            if not books:
                await query.edit_message_text("No hay libros disponibles")
                return

            # Crear nueva paginación
            keyboard, message = self._create_book_pagination(books, menu, page)

            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.TYPING
            )

            await query.edit_message_text(
                text=message,
                reply_markup=keyboard,
                parse_mode=ParseMode.MARKDOWN
            )
        except Exception as e:
            try:
                await update.callback_query.answer("Error en paginación", show_alert=True)
            except:
                pass
            await self._handle_error(update, e, "pagination")

    async def download_callback(self, update: Update, context: CallbackContext) -> None:
        """Maneja callbacks de descarga de libros."""
        try:
            query = update.callback_query
            book_id = query.data.split(" ", 1)[1]

            book = self.book_repository.find_by_book_id(book_id)
            if not book:
                await query.answer("Libro no encontrado")
                return

            if not book.file_id:
                await query.answer("Archivo no disponible")
                return

            # Incrementar contador de descargas
            self.book_repository.increment_downloads(book_id)

            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.UPLOAD_DOCUMENT
            )

            # Enviar archivo
            await context.bot.send_document(
                chat_id=query.message.chat_id,
                document=book.file_id,
                caption=f"📖 {book.title}"
            )

            await query.answer("📚 Descarga iniciada")
        except Exception as e:
            try:
                await update.callback_query.answer("Error en descarga", show_alert=True)
            except:
                pass
            await self._handle_error(update, e, "download")

    def _create_book_pagination(self, books, menu_type: str, current_page: int = 1):
        """Crea paginación simple para libros."""
        try:
            if not books:
                return InlineKeyboardMarkup([]), "No hay libros disponibles."

            items_per_page = self.config.books_per_page
            total_items = len(books)
            total_pages = (total_items + items_per_page - 1) // items_per_page

            # Validar página actual
            current_page = max(1, min(current_page, total_pages))

            # Generar mensaje con header
            header = self.message_formatter.format_book_list_header(total_items, menu_type)

            # Calcular índices para la página actual
            start_index = (current_page - 1) * items_per_page
            end_index = min(start_index + items_per_page, total_items)

            # Formatear libros de la página
            book_list = ""
            for book in books[start_index:end_index]:
                title = self._shorten_title(book.title)
                book_command = book.book_id
                book_list += self.message_formatter.format_book_list_item(title, book_command)

            message = header + book_list

            # Crear teclado de navegación si hay múltiples páginas
            keyboard = self.message_formatter.create_pagination_keyboard(
                current_page, total_pages, menu_type
            ) if total_pages > 1 else InlineKeyboardMarkup([])

            return keyboard, message
        except Exception as e:
            log_service_error("TelegramHandlers", e, {"menu_type": menu_type})
            return InlineKeyboardMarkup([]), "Error generando lista de libros."

    def _create_recommendation_help_message(self) -> str:
        """Crea mensaje de ayuda para el comando /recommend."""
        return """
🔮 **Recomendaciones de Neko-Chan**

Para obtener recomendaciones personalizadas, describe qué tipo de libro te gustaría leer:

📚 **Ejemplos de uso:**
• `/recommend Novelas de terror psicológico`
• `/recommend Libros de ciencia ficción espacial`
• `/recommend Romance histórico ambientado en el siglo XIX`
• `/recommend Ensayos sobre filosofía moderna`
• `/recommend Algo ligero y divertido para leer`

💡 **Consejos:**
- Sé específico sobre géneros, temas o estilos
- Menciona autores que te gustan
- Describe el tipo de historia que buscas
- Indica si prefieres algo ligero o profundo

✨ **Neko-Chan analizará tu solicitud y te recomendará los mejores libros de nuestra biblioteca que coincidan con tus gustos!**
"""

    def _shorten_title(self, title: str) -> str:
        """Acorta título usando configuración de la aplicación."""
        if not title:
            return "Sin título"

        try:
            max_length = BotConstants.TITLE_TRUNCATE_LENGTH
            if len(title) <= max_length:
                return title

            parts_length = BotConstants.TITLE_PARTS_LENGTH
            return f"{title[:parts_length]}...{title[-parts_length:]}"
        except Exception:
            return title[:40] + "..." if len(title) > 40 else title

    async def _send_message(
            self,
            update: Update,
            message: str,
            parse_mode: str = ParseMode.HTML,
            keyboard: Optional[InlineKeyboardMarkup] = None
    ) -> None:
        """Envía un mensaje con acción de typing."""
        try:
            await update.effective_chat.send_action(ChatAction.TYPING)
            await update.message.reply_text(
                message,
                parse_mode=parse_mode,
                reply_markup=keyboard
            )
        except Exception as e:
            self.logger.error(f"Error enviando mensaje: {e}")

    async def _send_book_with_cover(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            cover_id: str,
            message: str,
            keyboard: InlineKeyboardMarkup
    ) -> None:
        """Envía información del libro con portada."""
        try:
            await update.effective_chat.send_action(ChatAction.TYPING)
            await update.message.reply_photo(
                photo=cover_id,
                caption=message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )
        except Exception as e:
            # Fallback: enviar sin imagen
            await update.message.reply_text(
                text=message,
                parse_mode=ParseMode.MARKDOWN,
                reply_markup=keyboard
            )

    async def _handle_error(self, update: Update, error: Exception, command: str) -> None:
        """Maneja errores de forma consistente."""
        log_service_error("TelegramHandlers", error, {
            "command": command,
            "user_id": update.effective_user.id if update.effective_user else None
        })

        try:
            await update.message.reply_text(f"❌ Error en comando {command}. Intenta nuevamente.")
        except Exception:
            pass

    async def activity_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja el comando /activity para controlar recomendaciones automáticas."""
        try:
            user_id = update.effective_user.id
            chat_id = update.effective_chat.id  # ← IMPORTANTE: Capturar el chat_id

            # Solo el desarrollador puede controlar este servicio
            if not self._is_developer(user_id):
                await update.message.reply_text(
                    "🚫 Solo el administrador puede controlar las recomendaciones automáticas."
                )
                return

            # Obtener servicio
            zeepubs_bot = context.application.bot_data.get('zeepubs_bot')
            if not zeepubs_bot or not zeepubs_bot.auto_activity_service:
                await update.message.reply_text(
                    "❌ Servicio de actividad automática no disponible."
                )
                return

            activity_service = zeepubs_bot.auto_activity_service
            args = context.args

            # Sin argumentos: mostrar estado
            if not args:
                await self._show_activity_status(update, activity_service)
                return

            command = args[0].lower()

            # Comandos disponibles
            if command == "start":
                await self._handle_activity_start(update, activity_service, chat_id)  # ← Pasar chat_id
            elif command == "stop":
                await self._handle_activity_stop(update, activity_service)
            elif command == "add":
                await self._handle_add_chat(update, activity_service, chat_id)
            elif command == "remove":
                await self._handle_remove_chat(update, activity_service, chat_id)
            elif command == "force":
                await self._handle_force_recommendation(update, activity_service)
            elif command == "interval":
                await self._handle_interval_config(update, activity_service, args)
            elif command == "status":
                await self._show_detailed_status(update, activity_service)
            elif command == "chats":
                await self._show_active_chats(update, activity_service)
            else:
                await self._show_activity_help(update)

        except Exception as e:
            await self._handle_error(update, e, "activity")

    async def _show_active_chats(self, update, activity_service) -> None:
        """Muestra lista de chats activos."""
        try:
            status = activity_service.get_service_status()
            active_chats = status.get('active_chats', [])

            if not active_chats:
                message = "📝 **Chats Activos**\n\nNo hay chats recibiendo recomendaciones automáticas."
            else:
                chat_list = "\n".join([f"• Chat ID: `{chat_id}`" for chat_id in active_chats])
                message = f"""
    📝 **Chats Activos** ({len(active_chats)})

    {chat_list}

    💡 **Comandos útiles:**
    • `/activity add` - Agregar este chat
    • `/activity remove` - Remover este chat
    • `/activity start` - Iniciar servicio en este chat
    """

            await update.message.reply_text(message, parse_mode="Markdown")
        except Exception as e:
            await update.message.reply_text("❌ Error obteniendo lista de chats.")

    async def _show_activity_status(self, update, activity_service) -> None:
        """Muestra estado básico del servicio."""
        try:
            status = activity_service.get_service_status()
            message = self._format_activity_status(status)
            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text("❌ Error obteniendo estado del servicio.")

    async def _handle_activity_start(self, update, activity_service, chat_id) -> None:
        """Inicia el servicio de actividad con el chat actual."""
        try:
            status = activity_service.get_service_status()

            if status.get('is_running', False):
                # Si ya está corriendo, agregar este chat
                if chat_id not in activity_service.active_chats:
                    activity_service.add_chat(chat_id)
                    await update.message.reply_text(
                        f"✅ **Chat agregado a recomendaciones automáticas**\n\n"
                        f"📊 Chats activos: {len(activity_service.active_chats)}\n"
                        f"⏰ Próxima recomendación: {status.get('next_recommendation_eta', 'calculando...')}"
                    )
                else:
                    await update.message.reply_text(
                        f"ℹ️ **Este chat ya recibe recomendaciones automáticas**\n\n"
                        f"⏰ Próxima recomendación: {status.get('next_recommendation_eta', 'calculando...')}"
                    )
            else:
                # Iniciar servicio con este chat
                success = await activity_service.start_activity_service(chat_id)
                if success:
                    chat_type = "canal" if update.effective_chat.type == "channel" else "chat"
                    await update.message.reply_text(
                        f"✅ **Servicio iniciado correctamente**\n\n"
                        f"🤖 Neko-chan enviará recomendaciones automáticas a este {chat_type} cada 30 minutos.\n"
                        f"📊 Usa `/activity status` para monitorear."
                    )
                else:
                    await update.message.reply_text("❌ Error iniciando el servicio.")
        except Exception as e:
            await update.message.reply_text("❌ Error al iniciar el servicio.")

    async def _handle_activity_stop(self, update, activity_service) -> None:
        """Detiene el servicio de actividad."""
        try:
            status = activity_service.get_service_status()

            if not status.get('is_running', False):
                await update.message.reply_text("ℹ️ El servicio ya está detenido.")
            else:
                await activity_service.stop_activity_service()
                await update.message.reply_text(
                    "🛑 **Servicio detenido correctamente**\n\n"
                    "💤 Las recomendaciones automáticas se han pausado."
                )
        except Exception as e:
            await update.message.reply_text("❌ Error al detener el servicio.")

    async def _handle_force_recommendation(self, update, activity_service) -> None:
        """Fuerza una recomendación inmediata."""
        try:
            await update.message.reply_text("🔄 Preparando recomendación inmediata...")

            success = await activity_service.force_recommendation()
            if success:
                await update.message.reply_text("✅ Recomendación enviada correctamente.")
            else:
                await update.message.reply_text("❌ Error enviando recomendación.")
        except Exception as e:
            await update.message.reply_text("❌ Error procesando recomendación forzada.")

    async def _handle_interval_config(self, update, activity_service, args) -> None:
        """Configura el intervalo de recomendaciones."""
        try:
            if len(args) < 2:
                await update.message.reply_text(
                    "❓ **Uso correcto:**\n"
                    "`/activity interval <minutos>`\n\n"
                    "**Ejemplos:**\n"
                    "• `/activity interval 30` - Cada 30 minutos\n"
                    "• `/activity interval 60` - Cada hora\n"
                    "• `/activity interval 15` - Cada 15 minutos",
                    parse_mode=ParseMode.MARKDOWN
                )
                return

            try:
                minutes = int(args[1])
                success = activity_service.configure_interval(minutes)

                if success:
                    await update.message.reply_text(
                        f"✅ **Intervalo actualizado**\n\n"
                        f"⏰ Nuevas recomendaciones cada {minutes} minutos."
                    )
                else:
                    await update.message.reply_text(
                        "❌ **Intervalo inválido**\n\n"
                        "📝 Debe ser entre 5 y 1440 minutos (24 horas)."
                    )
            except ValueError:
                await update.message.reply_text("❌ El intervalo debe ser un número válido.")

        except Exception as e:
            await update.message.reply_text("❌ Error configurando intervalo.")

    async def _show_detailed_status(self, update, activity_service) -> None:
        """Muestra estado detallado del servicio."""
        try:
            # Verificar si el servicio tiene método mejorado
            if hasattr(activity_service, 'get_enhanced_status'):
                status = activity_service.get_enhanced_status()
                message = self._format_enhanced_status(status)
            else:
                status = activity_service.get_service_status()
                message = self._format_activity_status(status)

            await update.message.reply_text(message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            await update.message.reply_text("❌ Error obteniendo estado detallado.")

    async def _show_activity_help(self, update) -> None:
        """Muestra ayuda del comando activity."""
        help_message = """
    🤖 **Comandos de Actividad Automática**

    **Comandos básicos:**
    • `/activity` - Ver estado actual
    • `/activity start` - Iniciar recomendaciones en este chat
    • `/activity stop` - Detener todas las recomendaciones
    • `/activity status` - Estado detallado

    **Gestión de chats:**
    • `/activity add` - Agregar este chat a recomendaciones
    • `/activity remove` - Remover este chat de recomendaciones  
    • `/activity chats` - Ver lista de chats activos

    **Configuración:**
    • `/activity interval <mins>` - Cambiar frecuencia
    • `/activity force` - Recomendación inmediata

    **Ejemplos:**
    • `/activity start` - En un canal para que reciba recomendaciones
    • `/activity interval 45` - Cada 45 minutos
    • `/activity force` - Enviar recomendación ahora

    💡 *Solo el administrador puede usar estos comandos.*
    💡 *Ejecuta `/activity start` en cada canal donde quieras recomendaciones.*
    """
        await update.message.reply_text(help_message, parse_mode="Markdown")

    def _format_activity_status(self, status: dict) -> str:
        """Formatea el estado básico del servicio."""
        try:
            is_running = status.get('is_running', False)
            interval = status.get('interval_minutes', 0)
            last_rec = status.get('last_recommendation')
            next_eta = status.get('next_recommendation_eta')
            recent_count = status.get('recently_recommended_count', 0)

            status_emoji = "🟢" if is_running else "🔴"
            status_text = "Activo" if is_running else "Detenido"

            message = f"""
🤖 **Estado del Servicio de Actividad**

{status_emoji} **Estado:** {status_text}
⏰ **Intervalo:** {interval} minutos
📚 **Libros en cache:** {recent_count}
"""

            if last_rec:
                try:
                    from datetime import datetime
                    last_time = datetime.fromisoformat(last_rec)
                    message += f"🕐 **Última recomendación:** {last_time.strftime('%H:%M')}\n"
                except:
                    message += f"🕐 **Última recomendación:** {last_rec}\n"

            if next_eta and is_running:
                message += f"⏳ **Próxima recomendación:** {next_eta}\n"

            message += f"""
💡 **Comandos disponibles:**
• `/activity start/stop` - Controlar servicio
• `/activity force` - Recomendación inmediata
• `/activity interval <mins>` - Cambiar frecuencia
"""

            return message.strip()

        except Exception as e:
            return "❌ Error formateando estado del servicio."

    def _format_enhanced_status(self, status: dict) -> str:
        """Formatea estado mejorado del servicio (si está disponible)."""
        try:
            is_running = status.get('is_running', False)
            interval = status.get('interval_minutes', 0)
            mode = status.get('activity_mode', 'normal')
            personality = status.get('current_personality', 'casual')
            daily_recs = status.get('daily_recommendations', 0)
            cache_info = status.get('cache_status', {})

            status_emoji = "🟢" if is_running else "🔴"
            status_text = "Activo" if is_running else "Detenido"

            message = f"""
🤖 **Estado Detallado del Servicio**

{status_emoji} **Estado:** {status_text}
⏰ **Intervalo:** {interval} minutos
🎯 **Modo:** {mode}
🎭 **Personalidad actual:** {personality}
📊 **Recomendaciones hoy:** {daily_recs}

📚 **Cache de libros:**
• Tamaño: {cache_info.get('size', 0)}/{cache_info.get('max_size', 0)}
• Uso: {cache_info.get('usage_percent', 0)}%

⏳ **Próxima recomendación:** {status.get('next_recommendation_eta', 'calculando...')}

💡 **Comandos:**
• `/activity force` - Recomendación ahora
• `/activity interval <mins>` - Cambiar frecuencia
"""

            # Agregar info de horarios silenciosos si está disponible
            quiet_hours = status.get('quiet_hours')
            if quiet_hours:
                quiet_status = "activo" if quiet_hours.get('enabled') else "inactivo"
                message += f"🌙 **Horarios silenciosos:** {quiet_status}\n"

            return message.strip()

        except Exception as e:
            # Fallback al formato básico
            return self._format_activity_status(status)

    async def _handle_add_chat(self, update, activity_service, chat_id) -> None:
        """Agrega el chat actual a recomendaciones."""
        try:
            if chat_id in activity_service.active_chats:
                await update.message.reply_text("ℹ️ Este chat ya recibe recomendaciones automáticas.")
            else:
                success = activity_service.add_chat(chat_id)
                if success:
                    chat_type = "canal" if update.effective_chat.type == "channel" else "chat"
                    await update.message.reply_text(
                        f"✅ **Chat agregado**\n\n"
                        f"Este {chat_type} ahora recibirá recomendaciones automáticas.\n"
                        f"📊 Total de chats activos: {len(activity_service.active_chats)}"
                    )
                else:
                    await update.message.reply_text("❌ Error agregando chat.")
        except Exception as e:
            await update.message.reply_text("❌ Error procesando solicitud.")

    async def _handle_remove_chat(self, update, activity_service, chat_id) -> None:
        """Remueve el chat actual de recomendaciones."""
        try:
            success = activity_service.remove_chat(chat_id)
            if success:
                await update.message.reply_text(
                    f"🚫 **Chat removido**\n\n"
                    f"Este chat ya no recibirá recomendaciones automáticas.\n"
                    f"📊 Chats activos restantes: {len(activity_service.active_chats)}"
                )
            else:
                await update.message.reply_text("ℹ️ Este chat no estaba recibiendo recomendaciones.")
        except Exception as e:
            await update.message.reply_text("❌ Error procesando solicitud.")

    # ACTUALIZAR EL MÉTODO HELP EXISTENTE
    async def help_command(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        """Maneja el comando /help."""
        try:
            user_id = update.effective_user.id
            is_developer = self._is_developer(user_id)

            commands = [
                '/start - Mensaje de bienvenida del bot',
                '/help - Muestra esta ayuda',
                '/ebook <nombre> - Busca libros por título',
                '/list - Lista todos los libros disponibles',
                '/recommend <preferencias> - Recomendaciones personalizadas',
                '/about - Información sobre el bot'
            ]

            # Agregar comandos de desarrollador
            if is_developer:
                commands.extend([
                    '',  # Línea en blanco
                    '🔧 **Comandos de Administrador:**',
                    '/activity - Ver estado de recomendaciones automáticas',
                    '/activity start/stop - Iniciar/detener actividad',
                    '/activity force - Forzar recomendación inmediata',
                    '/activity interval <mins> - Cambiar frecuencia'
                ])

            base_message = self.bot_messages.get('ayuda')
            message = self.message_formatter.format_help_message(base_message, commands)
            await self._send_message(update, message, ParseMode.HTML)
        except Exception as e:
            await self._handle_error(update, e, "help")
