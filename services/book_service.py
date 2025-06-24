"""
Servicio de gestión de libros.
Maneja toda la lógica de negocio relacionada con libros y paginación.
"""

import math
from typing import List, Tuple, Dict, Any, Optional
from dataclasses import dataclass

from telegram import InlineKeyboardMarkup
from telegram_bot_pagination import InlineKeyboardPaginator

from config.bot_config import get_config, get_logger
from data.database_connection import get_database
from data.database_config import DatabaseConstants
from utils.epubs_utils import EpubsUtils
from utils.error_handler import log_service_error


@dataclass
class BookData:
    """Estructura de datos para un libro."""
    id: str
    book_id: str
    title: str
    alt_title: Optional[str]
    author: str
    description: str
    language: str
    type: str
    file_id: str
    cover_id: Optional[str]
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    year: Optional[int] = None
    file_size: Optional[int] = None

    @classmethod
    def from_db_row(cls, row: Tuple) -> 'BookData':
        """Crea instancia desde fila de base de datos."""
        return cls(
            id=str(row[0]),
            book_id=row[1],
            title=row[2],
            alt_title=row[3],
            author=row[4],
            description=row[5],
            language=row[6] if len(row) > 6 else 'es',
            type=row[7] if len(row) > 7 else 'book',
            file_id=row[8] if len(row) > 8 else None,
            cover_id=row[9] if len(row) > 9 else None,
            isbn=row[10] if len(row) > 10 else None,
            publisher=row[11] if len(row) > 11 else None,
            year=row[12] if len(row) > 12 else None,
            file_size=row[13] if len(row) > 13 else None
        )


class BookService:
    """Servicio para gestión de libros y lógica de negocio."""

    def __init__(self):
        """Inicializa el servicio con dependencias."""
        self.config = get_config()
        self.logger = get_logger(__name__)
        self.db = get_database()
        self.epub_utils = EpubsUtils()

        # Cache para resultados de búsqueda
        self._cached_search_results: Optional[List[Tuple]] = None

    def search_books_by_name(self, book_name: str) -> List[Tuple]:
        """Busca libros por nombre y cachea los resultados."""
        if not book_name or not book_name.strip():
            self.logger.warning("Búsqueda con nombre vacío")
            return []

        try:
            query = """
                SELECT id, book_id, title, alt_title, author, description, 
                       language, type, file_id, cover_id, isbn, publisher, year, file_size
                FROM books 
                WHERE title LIKE ? OR alt_title LIKE ? OR author LIKE ?
                ORDER BY 
                    CASE 
                        WHEN title LIKE ? THEN 1
                        WHEN alt_title LIKE ? THEN 2
                        WHEN author LIKE ? THEN 3
                        ELSE 4
                    END,
                    title
            """
            search_term = f"%{book_name.strip()}%"
            results = self.db.execute_query(query, (
                search_term, search_term, search_term,
                search_term, search_term, search_term
            ))

            # Convertir Row objects a tuplas para compatibilidad
            self._cached_search_results = [tuple(row) for row in results]

            # Actualizar estadísticas de búsqueda
            self._update_search_stats(book_name)

            self.logger.info(f"Búsqueda '{book_name}': {len(self._cached_search_results)} resultados")
            return self._cached_search_results

        except Exception as e:
            log_service_error("BookService", e, {"book_name": book_name})
            self.logger.error(f"Error buscando libros por nombre '{book_name}': {e}")
            return []

    def get_all_books(self) -> List[Tuple]:
        """Obtiene todos los libros disponibles."""
        try:
            query = """
                SELECT id, book_id, title, alt_title, author, description, 
                       language, type, file_id, cover_id, isbn, publisher, year, file_size
                FROM books 
                ORDER BY title
            """
            results = self.db.execute_query(query)

            # Convertir Row objects a tuplas para compatibilidad
            self._cached_search_results = [tuple(row) for row in results]

            self.logger.info(f"Libros totales: {len(self._cached_search_results)}")
            return self._cached_search_results

        except Exception as e:
            log_service_error("BookService", e)
            self.logger.error(f"Error obteniendo todos los libros: {e}")
            return []

    def get_book_by_id(self, book_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene un libro específico por su ID."""
        if not book_id or not book_id.strip():
            self.logger.warning("Búsqueda con ID vacío")
            return None

        try:
            query = """
                SELECT id, book_id, title, alt_title, author, description, 
                       language, type, file_id, cover_id, isbn, publisher, year, file_size
                FROM books 
                WHERE book_id = ?
            """
            results = self.db.execute_query(query, (book_id.strip(),))

            if not results:
                self.logger.info(f"Libro no encontrado: {book_id}")
                return None

            row = results[0]

            # Actualizar estadísticas de acceso
            self._update_access_stats(book_id)

            return {
                'id': row['book_id'],
                'title': row['title'],
                'alt_title': row['alt_title'],
                'author': row['author'],
                'description': row['description'],
                'language': row['language'],
                'type': row['type'],
                'isbn': row['isbn'],
                'publisher': row['publisher'],
                'year': row['year'],
                'file_id': row['file_id'],
                'cover_id': row['cover_id'],
                'file_size': row['file_size'],
                'cached_file_id': bool(row['file_id'])
            }

        except Exception as e:
            log_service_error("BookService", e, {"book_id": book_id})
            self.logger.error(f"Error obteniendo libro por ID '{book_id}': {e}")
            return None

    def get_cached_search_results(self) -> List[Tuple]:
        """Retorna los últimos resultados de búsqueda cacheados."""
        return self._cached_search_results or []

    def create_book_pagination(
        self,
        books: List[Tuple],
        menu_type: str,
        current_page: int = 1
    ) -> Tuple[InlineKeyboardMarkup, str]:
        """Crea paginación para lista de libros."""
        if not books:
            return None, "No hay libros disponibles."

        try:
            max_pages = math.ceil(len(books) / self.config.books_per_page)

            # Crear paginador
            paginator = InlineKeyboardPaginator(
                max_pages,
                current_page=current_page,
                data_pattern=f'character#{"{page}"} #{menu_type}'
            )

            # Generar mensaje
            message = self._generate_books_message(books, menu_type, current_page)

            return paginator.markup, message

        except Exception as e:
            log_service_error("BookService", e, {"menu_type": menu_type, "page": current_page})
            self.logger.error(f"Error creando paginación: {e}")
            return None, "Error generando lista de libros."

    def save_book(self, book_metadata: Dict[str, Any]) -> bool:
        """Guarda un nuevo libro en la base de datos."""
        if not book_metadata:
            self.logger.warning("Intento de guardar libro con metadatos vacíos")
            return False

        try:
            # Validar metadatos antes de guardar
            if not self.validate_book_metadata(book_metadata):
                return False

            command = """
                INSERT INTO books (book_id, title, alt_title, author, description, 
                                 language, type, isbn, publisher, year, file_id, cover_id, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                book_metadata.get('id'),
                book_metadata.get('title'),
                book_metadata.get('alt_title'),
                book_metadata.get('author'),
                book_metadata.get('description'),
                book_metadata.get('language', 'es'),
                book_metadata.get('type', 'book'),
                book_metadata.get('isbn'),
                book_metadata.get('publisher'),
                book_metadata.get('year'),
                book_metadata.get('file_id'),
                book_metadata.get('cover_id'),
                book_metadata.get('file_size')
            )

            rows_affected = self.db.execute_command(command, params)
            success = rows_affected > 0

            if success:
                self.logger.info(f"Libro guardado: {book_metadata.get('title', 'Sin título')}")
            else:
                self.logger.warning("No se afectaron filas al guardar libro")

            return success

        except Exception as e:
            log_service_error("BookService", e, {"title": book_metadata.get('title')})
            self.logger.error(f"Error guardando libro: {e}")
            return False

    def update_file_id(self, book_id: str, file_id: str) -> bool:
        """Actualiza el file_id de un libro."""
        if not book_id or not file_id:
            self.logger.warning("Intento de actualizar file_id con datos vacíos")
            return False

        try:
            command = """
                UPDATE books 
                SET file_id = ?, updated_at = CURRENT_TIMESTAMP 
                WHERE book_id = ?
            """
            rows_affected = self.db.execute_command(command, (file_id, book_id))
            success = rows_affected > 0

            if success:
                self.logger.info(f"File ID actualizado para libro: {book_id}")
            else:
                self.logger.warning(f"No se encontró libro para actualizar: {book_id}")

            return success

        except Exception as e:
            log_service_error("BookService", e, {"book_id": book_id})
            self.logger.error(f"Error actualizando file_id: {e}")
            return False

    def get_all_book_ids(self) -> List[str]:
        """Obtiene todos los IDs de libros para comandos dinámicos."""
        try:
            query = "SELECT book_id FROM books WHERE book_id IS NOT NULL ORDER BY book_id"
            results = self.db.execute_query(query)

            book_ids = [row['book_id'] for row in results if row['book_id']]
            self.logger.info(f"IDs de libros obtenidos: {len(book_ids)}")
            return book_ids

        except Exception as e:
            log_service_error("BookService", e)
            self.logger.error(f"Error obteniendo IDs de libros: {e}")
            return []

    def get_books_for_recommendations(self) -> List[Tuple[str, str]]:
        """Obtiene lista simplificada de libros para recomendaciones."""
        try:
            query = """
                SELECT b.book_id, b.title 
                FROM books b
                LEFT JOIN book_stats bs ON b.book_id = bs.book_id
                WHERE b.book_id IS NOT NULL 
                ORDER BY COALESCE(bs.downloads, 0) DESC, b.title
            """
            results = self.db.execute_query(query)

            # Convertir a lista de tuplas (book_id, title)
            books_list = [(row['book_id'], row['title']) for row in results]

            self.logger.info(f"Libros para recomendaciones: {len(books_list)}")
            return books_list

        except Exception as e:
            log_service_error("BookService", e)
            self.logger.error(f"Error obteniendo libros para recomendaciones: {e}")
            return []

    def get_popular_books(self, limit: int = 10) -> List[Tuple]:
        """Obtiene libros más populares por descargas."""
        try:
            query = """
                SELECT b.id, b.book_id, b.title, b.alt_title, b.author, b.description, 
                       b.language, b.type, b.file_id, b.cover_id, b.isbn, b.publisher, 
                       b.year, b.file_size, COALESCE(bs.downloads, 0) as downloads
                FROM books b
                LEFT JOIN book_stats bs ON b.book_id = bs.book_id
                ORDER BY downloads DESC, b.title
                LIMIT ?
            """
            results = self.db.execute_query(query, (limit,))

            # Convertir a tuplas para compatibilidad (sin el campo downloads)
            popular_books = [tuple(row[:-1]) for row in results]

            self.logger.info(f"Libros populares obtenidos: {len(popular_books)}")
            return popular_books

        except Exception as e:
            log_service_error("BookService", e, {"limit": limit})
            self.logger.error(f"Error obteniendo libros populares: {e}")
            return []

    def _generate_books_message(
        self,
        books: List[Tuple],
        menu_type: str,
        current_page: int
    ) -> str:
        """Genera mensaje formateado para lista de libros."""
        try:
            # Mensaje de encabezado
            if menu_type == 'm_list':
                message = (
                    f"Actualmente, tu biblioteca de **Zeepubs** tiene "
                    f"***{len(books)}*** libros disponibles para leer.\n\n"
                )
            elif menu_type == 'm_ebook':
                message = (
                    f"He encontrado {len(books)} libros relacionados con tu búsqueda. "
                    f"Si necesitas más información sobre cualquiera de ellos, "
                    f"por favor házmelo saber.\n\n"
                )
            else:
                message = f"Lista de libros ({len(books)} encontrados):\n\n"

            # Calcular índices para la página actual
            start_index = (current_page - 1) * self.config.books_per_page
            end_index = min(start_index + self.config.books_per_page, len(books))

            # Agregar libros de la página actual
            for book in books[start_index:end_index]:
                title = self.epub_utils.shorten_middle_text(book[2])
                book_command = book[1]
                message += f"***{title}\t/{book_command}***\n"

            return message

        except Exception as e:
            log_service_error("BookService", e, {"menu_type": menu_type})
            self.logger.error(f"Error generando mensaje de libros: {e}")
            return "Error generando lista de libros."

    def _update_search_stats(self, search_term: str) -> None:
        """Actualiza estadísticas de búsquedas."""
        try:
            # Incrementar contador de búsquedas para libros encontrados
            if self._cached_search_results:
                for book in self._cached_search_results:
                    book_id = book[1]  # book_id está en la posición 1
                    self._increment_book_stat(book_id, 'searches')

        except Exception as e:
            self.logger.debug(f"Error actualizando estadísticas de búsqueda: {e}")
            # No es crítico, no lanzar excepción

    def _update_access_stats(self, book_id: str) -> None:
        """Actualiza estadísticas de acceso a libro."""
        try:
            command = """
                UPDATE book_stats 
                SET last_accessed = CURRENT_TIMESTAMP 
                WHERE book_id = ?
            """
            self.db.execute_command(command, (book_id,))

        except Exception as e:
            self.logger.debug(f"Error actualizando estadísticas de acceso: {e}")
            # No es crítico, no lanzar excepción

    def _increment_book_stat(self, book_id: str, stat_type: str) -> None:
        """Incrementa una estadística específica de un libro."""
        try:
            if stat_type not in ['downloads', 'searches']:
                return

            command = f"""
                UPDATE book_stats 
                SET {stat_type} = {stat_type} + 1 
                WHERE book_id = ?
            """
            self.db.execute_command(command, (book_id,))

        except Exception as e:
            self.logger.debug(f"Error incrementando estadística {stat_type}: {e}")
            # No es crítico, no lanzar excepción

    def increment_download_count(self, book_id: str) -> None:
        """Incrementa contador de descargas de un libro."""
        self._increment_book_stat(book_id, 'downloads')
        self.logger.debug(f"Download incrementado para libro: {book_id}")

    def validate_book_metadata(self, metadata: Dict[str, Any]) -> bool:
        """Valida que los metadatos del libro sean correctos."""
        required_fields = ['id', 'title', 'author']

        for field in required_fields:
            if not metadata.get(field):
                self.logger.warning(f"Campo requerido faltante: {field}")
                return False

        # Validaciones de longitud usando constantes de BD
        if len(metadata['title']) > DatabaseConstants.MAX_TITLE_LENGTH:
            self.logger.warning("Título demasiado largo")
            return False

        if len(metadata['author']) > DatabaseConstants.MAX_AUTHOR_LENGTH:
            self.logger.warning("Autor demasiado largo")
            return False

        if metadata.get('description') and len(metadata['description']) > DatabaseConstants.MAX_DESCRIPTION_LENGTH:
            self.logger.warning("Descripción demasiado larga")
            return False

        book_id = metadata['id']
        if (len(book_id) < DatabaseConstants.MIN_BOOK_ID_LENGTH or
            len(book_id) > DatabaseConstants.MAX_BOOK_ID_LENGTH):
            self.logger.warning("book_id longitud inválida")
            return False

        return True

    def book_exists(self, title: str) -> bool:
        """Verifica si un libro ya existe en la base de datos."""
        if not title:
            return False

        try:
            query = "SELECT id FROM books WHERE LOWER(title) = ? LIMIT 1"
            results = self.db.execute_query(query, (title.lower(),))
            exists = len(results) > 0

            if exists:
                self.logger.debug(f"Libro ya existe: {title}")

            return exists

        except Exception as e:
            log_service_error("BookService", e, {"title": title})
            self.logger.error(f"Error verificando existencia del libro: {e}")
            return False

    def get_book_stats(self, book_id: str) -> Dict[str, Any]:
        """Obtiene estadísticas de un libro específico."""
        try:
            query = """
                SELECT downloads, searches, last_accessed 
                FROM book_stats 
                WHERE book_id = ?
            """
            results = self.db.execute_query(query, (book_id,))

            if results:
                row = results[0]
                return {
                    'downloads': row['downloads'] or 0,
                    'searches': row['searches'] or 0,
                    'last_accessed': row['last_accessed']
                }

            return {'downloads': 0, 'searches': 0, 'last_accessed': None}

        except Exception as e:
            log_service_error("BookService", e, {"book_id": book_id})
            self.logger.error(f"Error obteniendo estadísticas del libro: {e}")
            return {'downloads': 0, 'searches': 0, 'last_accessed': None}