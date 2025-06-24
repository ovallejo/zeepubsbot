"""
Servicio modernizado de formateo de mensajes.
Integrado con nuevos modelos y estadísticas.
"""

from dataclasses import dataclass
from typing import Dict, Any, List, Optional

from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from config.bot_config import get_config, get_logger, BotConstants
from data.database_config import DatabaseConstants
from utils.error_handler import log_service_error


@dataclass
class MessageTemplate:
    """Template para construcción de mensajes."""
    header: str
    body: str
    footer: Optional[str] = None
    max_length: Optional[int] = None


class MessageFormatter:
    """Servicio para formateo consistente de mensajes."""

    def __init__(self):
        """Inicializa el formateador con configuración."""
        self.config = get_config()
        self.logger = get_logger(__name__)

    def format_book_details(self, book_data: Dict[str, Any]) -> str:
        """
        Formatea los detalles completos de un libro.

        Args:
            book_data: Diccionario con datos del libro

        Returns:
            String formateado con detalles del libro
        """
        try:
            # Extraer datos básicos
            title = book_data.get('title', 'Sin título')
            author = book_data.get('author', 'Autor desconocido')
            description = book_data.get('description', 'Sin descripción disponible')
            alt_title = book_data.get('alt_title')

            # Construir secciones
            title_section = f"***Título:*** **{self._clean_text_for_display(title)}**"
            author_section = f"***Autor:*** **{self._clean_text_for_display(author)}**"
            description_section = f"***Descripción:*** **{self._clean_text_for_display(description)}**"

            # Incluir título alternativo si existe
            if alt_title and alt_title.strip():
                alt_title_section = f"***Título Original:*** **{self._clean_text_for_display(alt_title)}**"
                message = f"{title_section}\n\n{alt_title_section}\n\n{author_section}\n\n{description_section}"
            else:
                message = f"{title_section}\n\n{author_section}\n\n{description_section}"

            # Agregar información adicional si está disponible
            additional_info = self._format_additional_book_info(book_data)
            if additional_info:
                message += f"\n\n{additional_info}"

            # Truncar si excede límite
            return self._truncate_message(message, self.config.max_caption_length)

        except Exception as e:
            log_service_error("MessageFormatter", e, {
                "book_id": book_data.get('id', 'unknown')
            })
            self.logger.error(f"Error formateando detalles del libro: {e}")
            return f"📖 **{book_data.get('title', 'Libro')}**\n\nError mostrando información completa."

    def format_book_list_header(self, books_count: int, menu_type: str) -> str:
        """
        Formatea el encabezado para listas de libros de forma más limpia.

        Args:
            books_count: Número total de libros
            menu_type: Tipo de menú para personalizar mensaje

        Returns:
            Header formateado
        """
        try:
            templates = {
                'm_list': (
                    f"📚 Tu biblioteca de Zeepubs tiene {books_count} libros disponibles:\n\n"
                ),
                'm_ebook': (
                    f"🔍 Encontré {books_count} libros relacionados con tu búsqueda:\n\n"
                ),
                'popular': (
                    f"🔥 Libros más populares ({books_count} disponibles):\n\n"
                ),
                'recent': (
                    f"🆕 Libros añadidos recientemente ({books_count} disponibles):\n\n"
                ),
                'search': (
                    f"🔍 Resultados de búsqueda ({books_count} encontrados):\n\n"
                )
            }

            return templates.get(menu_type, f"📖 Lista de libros ({books_count} encontrados):\n\n")

        except Exception as e:
            log_service_error("MessageFormatter", e, {"menu_type": menu_type})
            return f"📖 Lista de libros ({books_count} encontrados):\n\n"

    def format_book_list_item(self, book_title: str, book_command: str) -> str:
        """Formatea un elemento individual de la lista de libros."""
        try:
            # Limpiar título SIN escape excesivo
            clean_title = self._simple_clean_title(book_title)

            # Aplicar formato uniforme con longitud fija
            uniform_title = self._format_uniform_title(clean_title, target_length=35)

            return f"📖 {uniform_title} → /{book_command}\n"

        except Exception as e:
            log_service_error("MessageFormatter", e, {
                "title": book_title[:50] if book_title else "None",
                "command": book_command
            })
            uniform_error = self._format_uniform_title("Error", target_length=35)
            return f"📖 {uniform_error} → /{book_command}\n"

    def _format_uniform_title(self, title: str, target_length: int = 45) -> str:
        """
        Formatea título con longitud uniforme mostrando inicio...final.

        Args:
            title: Título original
            target_length: Longitud objetivo del título formateado

        Returns:
            Título con longitud uniforme
        """
        if not title:
            return "Sin título".ljust(target_length)

        try:
            title = title.strip()

            # Si el título es igual o menor que la longitud objetivo
            if len(title) <= target_length:
                return title.ljust(target_length)

            # Si es más largo, aplicar formato: inicio...final
            # Reservar 3 caracteres para "..."
            available_chars = target_length - 3

            # Dividir caracteres disponibles: más para el inicio
            start_chars = (available_chars * 2) // 3  # 2/3 para el inicio
            end_chars = available_chars - start_chars  # 1/3 para el final

            # Asegurar que tenemos al menos algunos caracteres para cada parte
            start_chars = max(start_chars, 10)
            end_chars = max(end_chars, 8)

            # Si los caracteres calculados exceden el disponible, ajustar
            if start_chars + end_chars > available_chars:
                start_chars = available_chars // 2
                end_chars = available_chars - start_chars

            # Extraer partes del título
            start_part = title[:start_chars].rstrip()
            end_part = title[-end_chars:].lstrip()

            # Construir título formateado
            formatted = f"{start_part}...{end_part}"

            # Asegurar longitud exacta
            if len(formatted) < target_length:
                formatted = formatted.ljust(target_length)
            elif len(formatted) > target_length:
                # Si por alguna razón es más largo, truncar
                formatted = formatted[:target_length - 3] + "..."

            return formatted

        except Exception as e:
            self.logger.debug(f"Error formateando título uniforme: {e}")
            return "Título no disponible".ljust(target_length)
        """
        Limpia título de libro específicamente para listas, sin escape excesivo.

        Args:
            title: Título original del libro

        Returns:
            Título limpio y formateado
        """
        if not title:
            return "Sin título"

        try:
            # Limpiar el título
            cleaned = str(title).strip()

            # Remover caracteres de control y saltos de línea
            import re
            cleaned = re.sub(r'[\n\r\t]+', ' ', cleaned)
            cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)

            # Normalizar espacios múltiples
            cleaned = ' '.join(cleaned.split())

            # Remover backslashes innecesarios que vienen del escape
            cleaned = cleaned.replace('\\\\', '\\').replace('\\.', '.')
            cleaned = cleaned.replace('\\-', '-').replace('\\(', '(').replace('\\)', ')')

            # Limitar longitud manteniendo legibilidad
            if len(cleaned) > 60:
                # Truncar en espacio si es posible
                truncated = cleaned[:57]
                last_space = truncated.rfind(' ')
                if last_space > 40:  # Si hay un espacio razonable
                    cleaned = cleaned[:last_space] + "..."
                else:
                    cleaned = cleaned[:57] + "..."

            return cleaned

        except Exception as e:
            self.logger.debug(f"Error limpiando título para lista: {e}")
            return "Título no disponible"

    def build_book_list_message(self, books_data: List[Dict[str, Any]], menu_type: str = 'm_list') -> str:
        """
        Construye el mensaje completo de la lista de libros de forma ordenada.

        Args:
            books_data: Lista de diccionarios con datos de libros
            menu_type: Tipo de menú

        Returns:
            Mensaje completo formateado
        """
        try:
            if not books_data:
                return "📚 No hay libros disponibles en este momento.\n\n💡 Puedes subir archivos EPUB para añadir libros a la biblioteca."

            # Header
            header = self.format_book_list_header(len(books_data), menu_type)

            # Ordenar libros alfabéticamente por título
            sorted_books = sorted(books_data, key=lambda x: x.get('title', '').lower())

            # Construir lista de libros con formato uniforme
            book_items = []
            for book in sorted_books:
                title = book.get('title', 'Sin título')
                book_id = book.get('id', 'unknown')

                # Usar el formato uniforme
                book_item = self.format_book_list_item(title, book_id)
                book_items.append(book_item)

            # Unir todo
            books_section = '\n'.join(book_items)

            # Footer con instrucciones
            footer = "\n💡 Toca en cualquier comando para descargar el libro."

            message = f"{header}{books_section}{footer}"

            # Validar longitud
            if len(message) > self.config.max_message_length:
                # Si es muy largo, usar formato más compacto
                return self._build_compact_book_list(sorted_books, menu_type)

            return message

        except Exception as e:
            log_service_error("MessageFormatter", e)
            return "📚 Error generando lista de libros.\n\nUsa /help para más información."

    def _build_compact_book_list(self, books_data: List[Dict[str, Any]], menu_type: str) -> str:
        """
        Construye lista compacta cuando el mensaje es muy largo.

        Args:
            books_data: Lista de libros
            menu_type: Tipo de menú

        Returns:
            Lista compacta formateada
        """
        try:
            header = self.format_book_list_header(len(books_data), menu_type)

            # Formato compacto con longitud uniforme
            book_items = []
            for book in books_data:
                title = book.get('title', 'Sin título')
                book_id = book.get('id', 'unknown')

                # Usar formato uniforme más corto para versión compacta
                clean_title = self._clean_book_title_for_list(title)
                uniform_title = self._format_uniform_title(clean_title, target_length=35)

                book_item = f"📖 {uniform_title} → /{book_id}"
                book_items.append(book_item)

            books_section = '\n'.join(book_items)
            footer = "\n\n💡 Usa /comando para descargar."

            return f"{header}{books_section}{footer}"

        except Exception as e:
            log_service_error("MessageFormatter", e)
            return "📚 Lista de libros disponible.\n\nUsa comandos individuales para descargar."

    def _clean_book_title_for_list(self, title: str) -> str:
        """
        Limpia título de libro específicamente para listas, sin escape excesivo.

        Args:
            title: Título original del libro

        Returns:
            Título limpio y formateado
        """
        if not title:
            return "Sin título"

        try:
            # Limpiar el título
            cleaned = str(title).strip()

            # Remover caracteres de control y saltos de línea
            import re
            cleaned = re.sub(r'[\n\r\t]+', ' ', cleaned)
            cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)

            # Normalizar espacios múltiples
            cleaned = ' '.join(cleaned.split())

            # Remover backslashes innecesarios que vienen del escape
            cleaned = cleaned.replace('\\\\', '\\').replace('\\.', '.')
            cleaned = cleaned.replace('\\-', '-').replace('\\(', '(').replace('\\)', ')')

            # Limitar longitud manteniendo legibilidad
            if len(cleaned) > 60:
                # Truncar en espacio si es posible
                truncated = cleaned[:57]
                last_space = truncated.rfind(' ')
                if last_space > 40:  # Si hay un espacio razonable
                    cleaned = cleaned[:last_space] + "..."
                else:
                    cleaned = cleaned[:57] + "..."

            return cleaned

        except Exception as e:
            self.logger.debug(f"Error limpiando título para lista: {e}")
            return "Título no disponible"

    def format_new_book_announcement(self, book_data: Dict[str, Any]) -> str:
        """
        Formatea anuncio de nuevo libro disponible.

        Args:
            book_data: Datos del libro nuevo

        Returns:
            Mensaje de anuncio formateado
        """
        try:
            title = book_data.get('title', 'Nuevo libro')
            book_id = book_data.get('id', 'unknown')
            author = book_data.get('author', 'Autor desconocido')

            return (
                f"🎉 ***¡Nuevo libro disponible!***\n\n"
                f"📖 ***Título:*** **{self._clean_text_for_display(title)}**\n"
                f"✍️ ***Autor:*** **{self._clean_text_for_display(author)}**\n\n"
                f"📥 **Descárgalo con:** /{book_id}\n\n"
                f"¡Disfrútalo! 📚✨"
            )

        except Exception as e:
            log_service_error("MessageFormatter", e, {"book_data": str(book_data)[:100]})
            return "🎉 ¡Nuevo libro disponible!\n\nUsa /list para ver todos los libros."

    def format_help_message(self, base_message: str, commands: List[str]) -> str:
        """
        Formatea mensaje de ayuda con lista de comandos.

        Args:
            base_message: Mensaje base de ayuda
            commands: Lista de comandos disponibles

        Returns:
            Mensaje de ayuda completo
        """
        try:
            # Limpiar el mensaje base de cualquier formato problemático
            clean_base = self._clean_text_for_display(base_message)

            # Formatear comandos de forma simple y segura
            formatted_commands = []
            for command in commands:
                if command.strip():
                    # Limpiar comando y obtener emoji
                    clean_command = self._clean_text_for_display(command.strip())
                    emoji = self._get_command_emoji(command)
                    formatted_commands.append(f"{emoji} {clean_command}")

            commands_section = '\n'.join(formatted_commands)

            # Construir mensaje sin usar markdown bold/italic problemático
            message = (
                f"{clean_base}\n\n"
                f"🔧 Comandos disponibles:\n\n"
                f"{commands_section}\n\n"
                f"💡 Tip: También puedes enviar archivos EPUB para añadirlos a la biblioteca."
            )

            return message

        except Exception as e:
            log_service_error("MessageFormatter", e)
            # Mensaje de fallback completamente seguro
            return (
                "Ayuda del bot\n\n"
                "🔧 Comandos disponibles:\n\n"
                "🚀 /start - Iniciar el bot\n"
                "❓ /help - Mostrar ayuda\n"
                "🔍 /ebook - Buscar libro\n"
                "📚 /list - Lista de libros\n\n"
                "💡 Tip: También puedes enviar archivos EPUB."
            )

    def _escape_markdown(self, text: str) -> str:
        """Escapa caracteres de Markdown SOLO cuando es necesario para sintaxis válida."""
        if not text:
            return ""

        try:
            # Para texto que va dentro de ** bold **, NO necesitamos escapar tanto
            # Solo escapar los caracteres que realmente rompen el formato

            # Remover cualquier tag HTML primero
            import re
            text = re.sub(r'<[^>]*>', '', text)

            # SOLO escapar caracteres que interfieren con el formato específico que usamos
            # No escapar puntos, guiones, paréntesis, etc. que son parte normal del texto

            # Para **texto bold**, solo necesitamos escapar asteriscos internos
            escaped = text.replace('**', '\\*\\*')  # Solo doble asterisco

            # Para ***texto bold-italic***, escapar triple asterisco
            escaped = escaped.replace('***', '\\*\\*\\*')

            # Escapar backticks que interfieren con código
            escaped = escaped.replace('`', '\\`')

            # Escapar corchetes que interfieren con links
            escaped = escaped.replace('[', '\\[').replace(']', '\\]')

            return escaped

        except Exception as e:
            self.logger.debug(f"Error escapando markdown: {e}")
            # Fallback: NO escapar nada, devolver texto original
            return str(text)

    def _simple_clean_title(self, title: str) -> str:
        """Limpieza ultra simple para títulos que van en anuncios."""
        if not title:
            return "Sin título"

        try:
            # Solo normalizar espacios y remover caracteres de control
            import re
            cleaned = re.sub(r'[\n\r\t]+', ' ', title)
            cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)
            cleaned = ' '.join(cleaned.split())

            # NO aplicar ningún escape
            return cleaned.strip()

        except Exception:
            return str(title)[:100]

    # También actualiza este método para mayor seguridad
    def _clean_text_for_display(self, text: str) -> str:
        """Limpia texto para mostrar en interfaz, SIN OVER-ESCAPING."""
        if not text:
            return "Sin título"

        try:
            # Limpiar el título
            cleaned = str(text).strip()

            # Remover caracteres de control y saltos de línea
            import re
            cleaned = re.sub(r'[\n\r\t]+', ' ', cleaned)
            cleaned = re.sub(r'[\x00-\x1f\x7f-\x9f]', '', cleaned)

            # Normalizar espacios múltiples
            cleaned = ' '.join(cleaned.split())

            # ELIMINAR cualquier escape previo que pueda haberse introducido
            cleaned = cleaned.replace('\\\\', '\\')
            cleaned = cleaned.replace('\\.', '.')
            cleaned = cleaned.replace('\\-', '-')
            cleaned = cleaned.replace('\\(', '(')
            cleaned = cleaned.replace('\\)', ')')
            cleaned = cleaned.replace('\\[', '[')
            cleaned = cleaned.replace('\\]', ']')
            cleaned = cleaned.replace('\\*', '*')
            cleaned = cleaned.replace('\\_', '_')
            cleaned = cleaned.replace('\\`', '`')
            cleaned = cleaned.replace('\\~', '~')
            cleaned = cleaned.replace('\\>', '>')
            cleaned = cleaned.replace('\\#', '#')
            cleaned = cleaned.replace('\\+', '+')
            cleaned = cleaned.replace('\\=', '=')
            cleaned = cleaned.replace('\\|', '|')
            cleaned = cleaned.replace('\\{', '{')
            cleaned = cleaned.replace('\\}', '}')
            cleaned = cleaned.replace('\\!', '!')

            return cleaned if cleaned else "Sin título"

        except Exception as e:
            self.logger.debug(f"Error limpiando texto: {e}")
            # Fallback ultra seguro - remover escapes manualmente
            import re
            # Remover cualquier backslash seguido de carácter especial
            clean_text = re.sub(r'\\(.)', r'\1', str(text))
            return clean_text[:50] if clean_text else "Sin título"

    def format_error_message(self, error_type: str, context: Optional[str] = None) -> str:
        """
        Formatea mensajes de error para el usuario.

        Args:
            error_type: Tipo de error predefinido
            context: Contexto adicional del error

        Returns:
            Mensaje de error formateado
        """
        error_templates = {
            'book_not_found': "🔍 No se han encontrado libros con ese nombre.\n\n💡 *Intenta con palabras clave diferentes.*",
            'no_books': "📚 Por el momento no tengo libros en la biblioteca.\n\n📁 *Puedes subir archivos EPUB para empezar.*",
            'missing_book_name': "❓ Por favor ingresa el nombre del libro después del comando `/ebook`\n\n📝 *Ejemplo: /ebook Don Quijote*",
            'upload_error': "❌ Error procesando el archivo.\n\n🔄 *Intenta nuevamente con un archivo EPUB válido.*",
            'book_exists': "⚠️ El libro ya existe en la base de datos.\n\n🔍 *Usa /list para ver todos los libros disponibles.*",
            'processing_error': "⚙️ Error procesando tu solicitud.\n\n⏰ *Intenta más tarde.*",
            'invalid_file': "📄 El archivo debe ser un EPUB válido.\n\n✅ *Verifica que sea un archivo .epub correcto.*",
            'file_too_large': "📏 El archivo es demasiado grande.\n\n💾 *Máximo 50MB permitido.*",
            'network_error': "🌐 Error de conexión.\n\n🔄 *Verifica tu conexión e intenta nuevamente.*"
        }

        base_message = error_templates.get(error_type, "❌ Ha ocurrido un error inesperado.")

        if context:
            return f"{base_message}\n\n🔍 **Detalle:** {context}"

        return base_message

    def format_recommendation_status(self, status: str) -> str:
        """
        Formatea mensajes de estado para recomendaciones.

        Args:
            status: Estado de la recomendación

        Returns:
            Mensaje de estado formateado
        """
        status_templates = {
            'searching': "🔮 *Neko-Chan está buscando recomendaciones mágicas...*",
            'unavailable': "🔮 *Neko-Chan no está disponible en este momento*\n\n⏰ *Intenta más tarde*",
            'processing': "🤔 *Analizando tus preferencias literarias...*",
            'generating': "✨ *Preparando recomendaciones personalizadas...*",
            'thinking': "💭 *Neko-Chan está pensando...*"
        }

        return status_templates.get(status, BotConstants.PROCESSING_MESSAGE)

    def create_download_keyboard(self, book_id: str) -> InlineKeyboardMarkup:
        """
        Crea teclado inline para descarga de libros.

        Args:
            book_id: ID único del libro

        Returns:
            Teclado inline con botón de descarga
        """
        try:
            buttons = [[
                InlineKeyboardButton(
                    "📥 Descargar",
                    callback_data=f"download {book_id}"
                )
            ]]
            return InlineKeyboardMarkup(buttons)

        except Exception as e:
            log_service_error("MessageFormatter", e, {"book_id": book_id})
            return InlineKeyboardMarkup([])

    def create_pagination_keyboard(
            self,
            current_page: int,
            total_pages: int,
            menu_type: str
    ) -> InlineKeyboardMarkup:
        """
        Crea teclado inline para paginación.

        Args:
            current_page: Página actual
            total_pages: Total de páginas
            menu_type: Tipo de menú para callback

        Returns:
            Teclado inline de navegación
        """
        try:
            if total_pages <= 1:
                return InlineKeyboardMarkup([])

            buttons = []

            # Botón anterior
            if current_page > 1:
                buttons.append(InlineKeyboardButton(
                    "⬅️ Anterior",
                    callback_data=f"character#{current_page - 1} #{menu_type}"
                ))

            # Indicador de página (no clickeable)
            buttons.append(InlineKeyboardButton(
                f"📄 {current_page}/{total_pages}",
                callback_data="noop"
            ))

            # Botón siguiente
            if current_page < total_pages:
                buttons.append(InlineKeyboardButton(
                    "Siguiente ➡️",
                    callback_data=f"character#{current_page + 1} #{menu_type}"
                ))

            return InlineKeyboardMarkup([buttons])

        except Exception as e:
            log_service_error("MessageFormatter", e, {
                "current_page": current_page,
                "total_pages": total_pages
            })
            return InlineKeyboardMarkup([])

    def _format_additional_book_info(self, book_data: Dict[str, Any]) -> str:
        """Formatea información adicional del libro si está disponible."""
        try:
            info_parts = []

            # Información de publicación
            year = book_data.get('year')
            publisher = book_data.get('publisher')

            if year or publisher:
                pub_info = []
                if year:
                    pub_info.append(f"📅 {year}")
                if publisher:
                    pub_info.append(f"🏢 {self._escape_markdown(publisher)}")

                if pub_info:
                    info_parts.append(" • ".join(pub_info))

            # Información técnica
            language = book_data.get('language')
            book_type = book_data.get('type')

            if language or book_type:
                tech_info = []
                if language and language != 'unknown':
                    lang_name = self._get_language_name(language)
                    tech_info.append(f"🌐 {lang_name}")
                if book_type and book_type != 'book':
                    type_name = self._get_type_name(book_type)
                    tech_info.append(f"📂 {type_name}")

                if tech_info:
                    info_parts.append(" • ".join(tech_info))

            return "\n".join(info_parts) if info_parts else ""

        except Exception as e:
            self.logger.debug(f"Error formateando info adicional: {e}")
            return ""

    def _get_language_name(self, lang_code: str) -> str:
        """Convierte código de idioma a nombre legible."""
        language_names = {
            'es': 'Español',
            'en': 'English',
            'fr': 'Français',
            'de': 'Deutsch',
            'it': 'Italiano',
            'pt': 'Português'
        }
        return language_names.get(lang_code, lang_code.upper())

    def _get_type_name(self, type_code: str) -> str:
        """Convierte código de tipo a nombre legible."""
        type_names = {
            'novel': 'Novela',
            'essay': 'Ensayo',
            'manual': 'Manual',
            'comic': 'Cómic',
            'magazine': 'Revista'
        }
        return type_names.get(type_code, type_code.title())

    def _get_command_emoji(self, command: str) -> str:
        """Obtiene emoji apropiado para cada comando."""
        command_lower = command.lower()

        if 'start' in command_lower:
            return '🚀'
        elif 'help' in command_lower:
            return '❓'
        elif 'ebook' in command_lower:
            return '🔍'
        elif 'list' in command_lower:
            return '📚'
        elif 'recommend' in command_lower:
            return '🔮'
        elif 'about' in command_lower:
            return 'ℹ️'
        else:
            return '📖'

    def _clean_text_for_display(self, text: str) -> str:
        """Limpia texto para mostrar en interfaz, removiendo caracteres problemáticos."""
        if not text:
            return "Sin título"

        try:
            # Remover caracteres problemáticos
            cleaned = text.strip()
            cleaned = cleaned.replace('\n', ' ').replace('\r', ' ')
            cleaned = ' '.join(cleaned.split())  # Normalizar espacios

            # Remover caracteres que pueden causar problemas con parsing
            import re
            cleaned = re.sub(r'<[^>]*>', '', cleaned)  # Remover cualquier tag HTML

            return cleaned

        except Exception as e:
            self.logger.debug(f"Error limpiando texto: {e}")
            # Fallback seguro
            import re
            return re.sub(r'[<>]', '', str(text)[:50])

    def _shorten_middle_text(self, text: str) -> str:
        """Acorta texto largo manteniendo inicio y final."""
        if not text or len(text) <= BotConstants.TITLE_TRUNCATE_LENGTH:
            return text

        try:
            parts_length = BotConstants.TITLE_PARTS_LENGTH
            return f"{text[:parts_length]}...{text[-parts_length:]}"
        except Exception:
            return text[:BotConstants.TITLE_TRUNCATE_LENGTH]

    def _truncate_description(self, description: str) -> str:
        """Trunca descripción respetando límites de BD."""
        if not description:
            return "Sin descripción disponible"

        try:
            max_length = min(
                DatabaseConstants.MAX_DESCRIPTION_LENGTH,
                800  # Límite para interfaz
            )

            if len(description) <= max_length:
                # NO ESCAPAR LA DESCRIPCIÓN
                return self._clean_text_for_display(description)

            # Truncar en punto natural si es posible
            truncated = description[:max_length - 3]
            last_period = truncated.rfind('.')
            last_space = truncated.rfind(' ')

            if last_period > max_length * 0.8:
                truncated = description[:last_period + 1]
            elif last_space > max_length * 0.8:
                truncated = description[:last_space]

            # NO ESCAPAR, solo limpiar
            return self._clean_text_for_display(truncated) + "..."

        except Exception as e:
            self.logger.debug(f"Error truncando descripción: {e}")
            return "Descripción no disponible"

    def _truncate_message(self, message: str, max_length: int) -> str:
        """Trunca mensaje si excede el límite especificado."""
        if len(message) <= max_length:
            return message

        try:
            # Truncar conservando formato
            truncated = message[:max_length - 5]

            # Buscar punto de corte natural
            last_newline = truncated.rfind('\n')
            last_space = truncated.rfind(' ')

            if last_newline > max_length * 0.8:
                truncated = message[:last_newline]
            elif last_space > max_length * 0.8:
                truncated = message[:last_space]

            return truncated + "...**"

        except Exception as e:
            self.logger.debug(f"Error truncando mensaje: {e}")
            return message[:max_length - 10] + "...**"

    def _escape_markdown(self, text: str) -> str:
        """Escapa caracteres especiales de Markdown más exhaustivamente."""
        if not text:
            return ""

        try:
            # Escapar todos los caracteres problemáticos para Markdown
            # Incluye caracteres que pueden ser interpretados como tags HTML
            problematic_chars = ['*', '_', '`', '[', ']', '(', ')', '~', '>', '#', '+', '-', '=', '|', '{', '}', '.',
                                 '!', '<', '>']

            escaped = text
            for char in problematic_chars:
                escaped = escaped.replace(char, f'\\{char}')

            return escaped
        except Exception as e:
            self.logger.debug(f"Error escapando markdown: {e}")
            # Si falla el escape, devolver texto plano sin caracteres especiales
            import re
            return re.sub(r'[*_`\[\]()~>#+=|{}.!<>-]', '', str(text))

    def validate_message_length(self, message: str, message_type: str = "default") -> bool:
        """
        Valida que el mensaje no exceda los límites de Telegram.

        Args:
            message: Mensaje a validar
            message_type: Tipo de mensaje (message, caption)

        Returns:
            True si la longitud es válida
        """
        try:
            limits = {
                "message": self.config.max_message_length,
                "caption": self.config.max_caption_length,
                "default": self.config.max_message_length
            }

            max_length = limits.get(message_type, limits["default"])
            return len(message) <= max_length

        except Exception as e:
            log_service_error("MessageFormatter", e, {"message_type": message_type})
            return False

    def build_template_message(self, template: MessageTemplate) -> str:
        """
        Construye mensaje usando template.

        Args:
            template: Template con header, body y footer

        Returns:
            Mensaje construido
        """
        try:
            parts = [template.header.strip(), template.body.strip()]

            if template.footer and template.footer.strip():
                parts.append(template.footer.strip())

            message = '\n\n'.join(filter(None, parts))

            if template.max_length:
                message = self._truncate_message(message, template.max_length)

            return message

        except Exception as e:
            log_service_error("MessageFormatter", e)
            return template.header or "Error generando mensaje."