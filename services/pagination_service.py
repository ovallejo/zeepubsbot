"""
Servicio modernizado de paginación para listas de libros.
Integrado con nuevos modelos y estadísticas.
"""

import math
from dataclasses import dataclass
from typing import List, Tuple, Dict, Any, Optional, Union

from telegram import InlineKeyboardMarkup, InlineKeyboardButton
from telegram_bot_pagination import InlineKeyboardPaginator

from config.bot_config import get_config, get_logger
from data.book_models import Book
from data.database_config import DatabaseConstants
from utils.error_handler import log_service_error


@dataclass
class PaginationConfig:
    """Configuración para paginación."""
    items_per_page: int
    max_pages: int
    current_page: int = 1
    menu_type: str = "default"


@dataclass
class PaginationResult:
    """Resultado de paginación."""
    keyboard: InlineKeyboardMarkup
    message: str
    current_page: int
    total_pages: int
    total_items: int
    has_results: bool = True

    @property
    def items_in_page(self) -> int:
        """Calcula items en la página actual."""
        return min(self.items_per_page, self.total_items - ((self.current_page - 1) * self.items_per_page))

    @property
    def items_per_page(self) -> int:
        """Items por página desde configuración."""
        return get_config().books_per_page


class PaginationService:
    """Servicio para manejo de paginación modernizado."""

    def __init__(self):
        """Inicializa el servicio de paginación."""
        self.config = get_config()
        self.logger = get_logger(__name__)

    def create_book_pagination(
            self,
            books: Union[List[Book], List[Tuple]],
            menu_type: str,
            current_page: int = 1,
            items_per_page: Optional[int] = None
    ) -> PaginationResult:
        """
        Crea paginación completa para lista de libros.

        Args:
            books: Lista de libros (modelos Book o tuplas legacy)
            menu_type: Tipo de menú para callback
            current_page: Página actual
            items_per_page: Items por página (usa config si None)

        Returns:
            PaginationResult con keyboard y mensaje
        """
        if not books:
            return self._create_empty_result(menu_type)

        try:
            # Configuración de paginación
            items_per_page = items_per_page or self.config.books_per_page
            total_items = len(books)
            total_pages = math.ceil(total_items / items_per_page)

            # Validar página actual
            current_page = self._validate_page_number(current_page, total_pages)

            # Crear teclado de navegación
            keyboard = self._create_navigation_keyboard(
                current_page, total_pages, menu_type
            )

            # Generar mensaje con libros de la página actual
            message = self._build_books_page_message(
                books, menu_type, current_page, items_per_page, total_items
            )

            return PaginationResult(
                keyboard=keyboard,
                message=message,
                current_page=current_page,
                total_pages=total_pages,
                total_items=total_items,
                has_results=True
            )

        except Exception as e:
            log_service_error("PaginationService", e, {
                "menu_type": menu_type,
                "total_books": len(books)
            })
            self.logger.error(f"Error creando paginación: {e}")
            return self._create_error_result(menu_type)

    def create_book_pagination_with_stats(
            self,
            books: List[Book],
            menu_type: str,
            current_page: int = 1,
            sort_by_popularity: bool = False
    ) -> PaginationResult:
        """
        Crea paginación con ordenamiento inteligente basado en estadísticas.

        Args:
            books: Lista de modelos Book
            menu_type: Tipo de menú
            current_page: Página actual
            sort_by_popularity: Si ordenar por popularidad

        Returns:
            PaginationResult optimizado
        """
        if not books:
            return self._create_empty_result(menu_type)

        try:
            # Ordenar por popularidad si se solicita
            if sort_by_popularity:
                # Nota: Esto requeriría integrar estadísticas en el modelo Book
                # Por ahora mantenemos orden alfabético
                sorted_books = sorted(books, key=lambda b: b.title.lower())
            else:
                sorted_books = sorted(books, key=lambda b: b.title.lower())

            # Convertir a tuplas para compatibilidad con sistema existente
            book_tuples = [book.to_legacy_tuple() for book in sorted_books]

            return self.create_book_pagination(
                book_tuples, menu_type, current_page
            )

        except Exception as e:
            log_service_error("PaginationService", e, {
                "menu_type": menu_type,
                "sort_by_popularity": sort_by_popularity
            })
            return self._create_error_result(menu_type)

    def _create_navigation_keyboard(
            self,
            current_page: int,
            total_pages: int,
            menu_type: str
    ) -> InlineKeyboardMarkup:
        """Crea teclado de navegación para paginación."""
        try:
            if total_pages <= 1:
                return InlineKeyboardMarkup([])

            # Usar librería de paginación existente
            paginator = InlineKeyboardPaginator(
                total_pages,
                current_page=current_page,
                data_pattern=f'character#{"{page}"} #{menu_type}'
            )

            return paginator.markup

        except Exception as e:
            self.logger.error(f"Error creando teclado de navegación: {e}")
            # Fallback: navegación simple
            return self._create_simple_navigation_keyboard(
                current_page, total_pages, menu_type
            )

    def _create_simple_navigation_keyboard(
            self,
            current_page: int,
            total_pages: int,
            menu_type: str
    ) -> InlineKeyboardMarkup:
        """Crea teclado de navegación simple como fallback."""
        try:
            buttons = []

            # Botón anterior
            if current_page > 1:
                buttons.append(InlineKeyboardButton(
                    "⬅️ Anterior",
                    callback_data=f"character#{current_page - 1} #{menu_type}"
                ))

            # Indicador de página
            buttons.append(InlineKeyboardButton(
                f"{current_page}/{total_pages}",
                callback_data="noop"
            ))

            # Botón siguiente
            if current_page < total_pages:
                buttons.append(InlineKeyboardButton(
                    "Siguiente ➡️",
                    callback_data=f"character#{current_page + 1} #{menu_type}"
                ))

            return InlineKeyboardMarkup([buttons]) if buttons else InlineKeyboardMarkup([])

        except Exception as e:
            self.logger.error(f"Error creando navegación simple: {e}")
            return InlineKeyboardMarkup([])

    def _build_books_page_message(
            self,
            books: Union[List[Book], List[Tuple]],
            menu_type: str,
            current_page: int,
            items_per_page: int,
            total_items: int
    ) -> str:
        """Construye mensaje para página específica de libros."""
        try:
            # Encabezado según tipo de menú
            header = self._get_page_header(menu_type, total_items)

            # Calcular índices para la página actual
            start_index = (current_page - 1) * items_per_page
            end_index = min(start_index + items_per_page, len(books))

            # Obtener libros para esta página
            page_books = books[start_index:end_index]

            # Construir lista de libros
            books_list = self._format_books_list(page_books)

            # Pie de página con información de navegación
            footer = self._get_page_footer(current_page, math.ceil(len(books) / items_per_page))

            # Combinar todas las partes
            message_parts = [header, books_list]
            if footer:
                message_parts.append(footer)

            return '\n'.join(filter(None, message_parts))

        except Exception as e:
            log_service_error("PaginationService", e, {
                "menu_type": menu_type,
                "page": current_page
            })
            return "Error generando lista de libros."

    def _get_page_header(self, menu_type: str, total_items: int) -> str:
        """Genera encabezado según el tipo de menú."""
        headers = {
            'm_list': (
                f"Actualmente, tu biblioteca de **Zeepubs** tiene "
                f"***{total_items}*** libros disponibles para leer.\n\n"
            ),
            'm_ebook': (
                f"He encontrado {total_items} libros relacionados con tu búsqueda. "
                f"Si necesitas más información sobre cualquiera de ellos, "
                f"por favor házmelo saber.\n\n"
            ),
            'search': f"📚 **Resultados de búsqueda** ({total_items} libros encontrados)\n\n",
            'popular': f"🔥 **Libros más populares** ({total_items} disponibles)\n\n",
            'recent': f"🆕 **Libros recientes** ({total_items} añadidos)\n\n"
        }

        return headers.get(menu_type, f"📖 **Lista de libros** ({total_items} encontrados)\n\n")

    def _format_books_list(self, books: Union[List[Book], List[Tuple]]) -> str:
        """Formatea lista de libros para mostrar."""
        try:
            if not books:
                return "No hay libros en esta página."

            formatted_books = []
            for book in books:
                if isinstance(book, Book):
                    title = self._shorten_title(book.title)
                    book_command = book.book_id
                elif isinstance(book, tuple) and len(book) >= 3:
                    title = self._shorten_title(book[2])  # title en posición 2
                    book_command = book[1]  # book_id en posición 1
                else:
                    self.logger.warning(f"Formato de libro desconocido: {type(book)}")
                    continue

                formatted_books.append(f"***{title}\t/{book_command}***")

            return '\n'.join(formatted_books)

        except Exception as e:
            log_service_error("PaginationService", e)
            return "Error mostrando libros."

    def _shorten_title(self, title: str) -> str:
        """Acorta título usando configuración de la aplicación."""
        if not title:
            return "Sin título"

        try:
            from config.bot_config import BotConstants
            max_length = BotConstants.TITLE_TRUNCATE_LENGTH

            if len(title) <= max_length:
                return title

            parts_length = BotConstants.TITLE_PARTS_LENGTH
            return f"{title[:parts_length]}...{title[-parts_length:]}"

        except Exception as e:
            self.logger.debug(f"Error acortando título: {e}")
            # Fallback simple
            return title[:40] + "..." if len(title) > 40 else title

    def _get_page_footer(self, current_page: int, total_pages: int) -> Optional[str]:
        """Genera pie de página con información de navegación."""
        if total_pages <= 1:
            return None

        return f"\n📖 Página {current_page} de {total_pages}"

    def _validate_page_number(self, page: int, total_pages: int) -> int:
        """Valida y corrige número de página."""
        if page < 1:
            return 1
        if page > total_pages:
            return total_pages
        return page

    def _create_empty_result(self, menu_type: str) -> PaginationResult:
        """Crea resultado para lista vacía."""
        messages = {
            'm_list': "📚 Por el momento no tengo libros en la biblioteca.",
            'm_ebook': "🔍 No se encontraron libros que coincidan con tu búsqueda.",
            'search': "🔍 Tu búsqueda no arrojó resultados.",
            'popular': "📊 No hay estadísticas de popularidad disponibles.",
            'recent': "🆕 No hay libros recientes."
        }

        message = messages.get(menu_type, "📖 No hay elementos disponibles.")

        return PaginationResult(
            keyboard=InlineKeyboardMarkup([]),
            message=message,
            current_page=1,
            total_pages=0,
            total_items=0,
            has_results=False
        )

    def _create_error_result(self, menu_type: str) -> PaginationResult:
        """Crea resultado para casos de error."""
        return PaginationResult(
            keyboard=InlineKeyboardMarkup([]),
            message="❌ Error generando lista. Intenta nuevamente.",
            current_page=1,
            total_pages=0,
            total_items=0,
            has_results=False
        )

    def parse_pagination_callback(self, callback_data: str) -> Dict[str, Any]:
        """
        Parsea datos de callback de paginación.

        Args:
            callback_data: Datos del callback (ej: "character#2 #m_list")

        Returns:
            Dict con página, menu_type y validez
        """
        try:
            # Formato esperado: "character#2 #m_list"
            parts = callback_data.split('#')
            if len(parts) < 3:
                raise ValueError("Formato de callback inválido")

            page_part = parts[1].strip()
            menu_type = parts[2].strip()

            # Extraer número de página
            page = int(page_part.split(' ')[0])

            return {
                'page': page,
                'menu_type': menu_type,
                'valid': True
            }

        except (ValueError, IndexError) as e:
            self.logger.warning(f"Error parseando callback '{callback_data}': {e}")
            return {
                'page': 1,
                'menu_type': 'default',
                'valid': False,
                'error': str(e)
            }

    def get_page_range(self, current_page: int, items_per_page: int) -> Tuple[int, int]:
        """
        Calcula rango de índices para página actual.

        Args:
            current_page: Página actual (1-based)
            items_per_page: Items por página

        Returns:
            Tupla con (start_index, end_index) para slicing
        """
        start_index = (current_page - 1) * items_per_page
        end_index = start_index + items_per_page
        return start_index, end_index

    def calculate_pagination_stats(
            self,
            total_items: int,
            items_per_page: int,
            current_page: int
    ) -> Dict[str, Any]:
        """
        Calcula estadísticas completas de paginación.

        Args:
            total_items: Total de elementos
            items_per_page: Items por página
            current_page: Página actual

        Returns:
            Dict con todas las estadísticas de paginación
        """
        try:
            total_pages = math.ceil(total_items / items_per_page) if total_items > 0 else 1
            validated_page = self._validate_page_number(current_page, total_pages)

            start_index, end_index = self.get_page_range(validated_page, items_per_page)
            end_index = min(end_index, total_items)

            items_in_page = max(0, end_index - start_index)

            return {
                'total_items': total_items,
                'total_pages': total_pages,
                'current_page': validated_page,
                'items_per_page': items_per_page,
                'start_index': start_index,
                'end_index': end_index,
                'items_in_current_page': items_in_page,
                'has_previous': validated_page > 1,
                'has_next': validated_page < total_pages,
                'is_first_page': validated_page == 1,
                'is_last_page': validated_page == total_pages
            }

        except Exception as e:
            log_service_error("PaginationService", e, {
                "total_items": total_items,
                "items_per_page": items_per_page,
                "current_page": current_page
            })

            # Retornar estadísticas mínimas en caso de error
            return {
                'total_items': 0,
                'total_pages': 1,
                'current_page': 1,
                'items_per_page': items_per_page,
                'start_index': 0,
                'end_index': 0,
                'items_in_current_page': 0,
                'has_previous': False,
                'has_next': False,
                'is_first_page': True,
                'is_last_page': True,
                'error': str(e)
            }

    def validate_pagination_request(
            self,
            items: List[Any],
            page: int,
            items_per_page: int
    ) -> Dict[str, Any]:
        """
        Valida parámetros de paginación.

        Args:
            items: Lista de elementos
            page: Página solicitada
            items_per_page: Items por página

        Returns:
            Dict con validez y errores si los hay
        """
        errors = []

        try:
            if not isinstance(items, list):
                errors.append("Items debe ser una lista")

            if not isinstance(page, int) or page < 1:
                errors.append("Página debe ser un entero mayor a 0")

            if not isinstance(items_per_page, int) or items_per_page < 1:
                errors.append("Items por página debe ser un entero mayor a 0")

            # Límite máximo de items por página
            max_items_per_page = DatabaseConstants.MAX_TITLE_LENGTH // 10  # Estimación conservadora
            if items_per_page > max_items_per_page:
                errors.append(f"Máximo {max_items_per_page} items por página")

            total_pages = math.ceil(len(items) / items_per_page) if items and items_per_page > 0 else 1
            if page > total_pages:
                errors.append(f"Página {page} no existe. Máximo: {total_pages}")

            return {
                'valid': len(errors) == 0,
                'errors': errors,
                'total_pages': total_pages,
                'total_items': len(items) if isinstance(items, list) else 0
            }

        except Exception as e:
            return {
                'valid': False,
                'errors': [f"Error validando paginación: {str(e)}"],
                'total_pages': 1,
                'total_items': 0
            }