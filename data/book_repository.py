"""
Repository para operaciones CRUD de libros.
Implementa patrón Repository para acceso a datos de libros.
"""

from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass, asdict

from data.database_connection import get_database
from data.database_config import DatabaseConstants
from config.bot_config import get_logger
from utils.error_handler import log_service_error


@dataclass
class Book:
    """Modelo de datos para un libro."""
    book_id: str
    title: str
    author: str
    description: str = ""
    alt_title: Optional[str] = None
    language: str = "es"
    type: str = "book"
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    year: Optional[int] = None
    file_id: Optional[str] = None
    cover_id: Optional[str] = None
    file_size: Optional[int] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el libro a diccionario."""
        return asdict(self)

    def to_legacy_tuple(self) -> Tuple:
        """Convierte a tupla para compatibilidad con BookService."""
        return (
            self.id,
            self.book_id,
            self.title,
            self.alt_title,
            self.author,
            self.description,
            self.language,
            self.type,
            self.file_id,
            self.cover_id,
            self.isbn,
            self.publisher,
            self.year,
            self.file_size
        )

    @classmethod
    def from_row(cls, row) -> 'Book':
        """Crea instancia de Book desde fila de base de datos."""
        return cls(
            id=row['id'],
            book_id=row['book_id'],
            title=row['title'],
            alt_title=row['alt_title'],
            author=row['author'],
            description=row['description'] or "",
            language=row['language'] or "es",
            type=row['type'] or "book",
            isbn=row['isbn'],
            publisher=row['publisher'],
            year=row['year'],
            file_id=row['file_id'],
            cover_id=row['cover_id'],
            file_size=row['file_size'],
            created_at=row['created_at'],
            updated_at=row['updated_at']
        )


@dataclass
class BookStats:
    """Modelo para estadísticas de libros."""
    book_id: str
    downloads: int = 0
    searches: int = 0
    last_accessed: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> 'BookStats':
        """Crea instancia desde fila de base de datos."""
        return cls(
            id=row['id'],
            book_id=row['book_id'],
            downloads=row['downloads'] or 0,
            searches=row['searches'] or 0,
            last_accessed=row['last_accessed'],
            created_at=row['created_at']
        )


class BookRepository:
    """Repository para operaciones CRUD de libros."""

    def __init__(self):
        """Inicializa el repository."""
        self.db = get_database()
        self.logger = get_logger(__name__)

    def create(self, book: Book) -> Optional[Book]:
        """Crea un nuevo libro en la base de datos."""
        try:
            # Validar límites antes de insertar
            self._validate_book_limits(book)

            command = """
                INSERT INTO books (book_id, title, alt_title, author, description, 
                                 language, type, isbn, publisher, year, file_id, cover_id, file_size)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """
            params = (
                book.book_id,
                book.title,
                book.alt_title,
                book.author,
                book.description,
                book.language,
                book.type,
                book.isbn,
                book.publisher,
                book.year,
                book.file_id,
                book.cover_id,
                book.file_size
            )

            rows_affected = self.db.execute_command(command, params)

            if rows_affected > 0:
                # Obtener el libro creado con su ID generado
                return self.find_by_book_id(book.book_id)

            return None

        except Exception as e:
            log_service_error("BookRepository", e, {"book_id": book.book_id})
            self.logger.error(f"Error creando libro {book.book_id}: {e}")
            return None

    def find_by_id(self, id: int) -> Optional[Book]:
        """Busca libro por ID de base de datos."""
        try:
            query = """
                SELECT id, book_id, title, alt_title, author, description, 
                       language, type, isbn, publisher, year, file_id, cover_id, 
                       file_size, created_at, updated_at
                FROM books 
                WHERE id = ?
            """
            results = self.db.execute_query(query, (id,))

            if results:
                return Book.from_row(results[0])

            return None

        except Exception as e:
            log_service_error("BookRepository", e, {"id": id})
            self.logger.error(f"Error buscando libro por ID {id}: {e}")
            return None

    def find_by_book_id(self, book_id: str) -> Optional[Book]:
        """Busca libro por book_id único."""
        try:
            query = """
                SELECT id, book_id, title, alt_title, author, description, 
                       language, type, isbn, publisher, year, file_id, cover_id, 
                       file_size, created_at, updated_at
                FROM books 
                WHERE book_id = ?
            """
            results = self.db.execute_query(query, (book_id,))

            if results:
                return Book.from_row(results[0])

            return None

        except Exception as e:
            log_service_error("BookRepository", e, {"book_id": book_id})
            self.logger.error(f"Error buscando libro por book_id {book_id}: {e}")
            return None

    def find_all(self, limit: Optional[int] = None, offset: int = 0) -> List[Book]:
        """Obtiene todos los libros con paginación opcional."""
        try:
            query = """
                SELECT id, book_id, title, alt_title, author, description, 
                       language, type, isbn, publisher, year, file_id, cover_id, 
                       file_size, created_at, updated_at
                FROM books 
                ORDER BY title
            """

            if limit:
                query += f" LIMIT {limit} OFFSET {offset}"

            results = self.db.execute_query(query)
            return [Book.from_row(row) for row in results]

        except Exception as e:
            log_service_error("BookRepository", e, {"limit": limit, "offset": offset})
            self.logger.error(f"Error obteniendo todos los libros: {e}")
            return []

    def search(self, search_term: str) -> List[Book]:
        """Búsqueda general en título, autor y descripción con relevancia."""
        try:
            query = """
                SELECT id, book_id, title, alt_title, author, description, 
                       language, type, isbn, publisher, year, file_id, cover_id, 
                       file_size, created_at, updated_at
                FROM books 
                WHERE title LIKE ? OR alt_title LIKE ? OR author LIKE ? OR description LIKE ?
                ORDER BY 
                    CASE 
                        WHEN title LIKE ? THEN 1
                        WHEN alt_title LIKE ? THEN 2
                        WHEN author LIKE ? THEN 3
                        ELSE 4
                    END,
                    title
            """
            search_pattern = f"%{search_term}%"
            params = (search_pattern, search_pattern, search_pattern, search_pattern,
                     search_pattern, search_pattern, search_pattern)

            results = self.db.execute_query(query, params)
            return [Book.from_row(row) for row in results]

        except Exception as e:
            log_service_error("BookRepository", e, {"search_term": search_term})
            self.logger.error(f"Error en búsqueda general '{search_term}': {e}")
            return []

    def find_by_title(self, title: str, exact_match: bool = False) -> List[Book]:
        """Busca libros por título."""
        try:
            if exact_match:
                query = """
                    SELECT id, book_id, title, alt_title, author, description, 
                           language, type, isbn, publisher, year, file_id, cover_id, 
                           file_size, created_at, updated_at
                    FROM books 
                    WHERE LOWER(title) = ? OR LOWER(alt_title) = ?
                    ORDER BY title
                """
                params = (title.lower(), title.lower())
            else:
                query = """
                    SELECT id, book_id, title, alt_title, author, description, 
                           language, type, isbn, publisher, year, file_id, cover_id, 
                           file_size, created_at, updated_at
                    FROM books 
                    WHERE title LIKE ? OR alt_title LIKE ?
                    ORDER BY title
                """
                search_term = f"%{title}%"
                params = (search_term, search_term)

            results = self.db.execute_query(query, params)
            return [Book.from_row(row) for row in results]

        except Exception as e:
            log_service_error("BookRepository", e, {"title": title, "exact_match": exact_match})
            self.logger.error(f"Error buscando libros por título '{title}': {e}")
            return []

    def find_by_author(self, author: str) -> List[Book]:
        """Busca libros por autor."""
        try:
            query = """
                SELECT id, book_id, title, alt_title, author, description, 
                       language, type, isbn, publisher, year, file_id, cover_id, 
                       file_size, created_at, updated_at
                FROM books 
                WHERE author LIKE ?
                ORDER BY title
            """
            search_term = f"%{author}%"
            results = self.db.execute_query(query, (search_term,))

            return [Book.from_row(row) for row in results]

        except Exception as e:
            log_service_error("BookRepository", e, {"author": author})
            self.logger.error(f"Error buscando libros por autor '{author}': {e}")
            return []

    def find_popular(self, limit: int = 10) -> List[Book]:
        """Encuentra libros más populares por descargas."""
        try:
            query = """
                SELECT b.id, b.book_id, b.title, b.alt_title, b.author, b.description, 
                       b.language, b.type, b.isbn, b.publisher, b.year, b.file_id, 
                       b.cover_id, b.file_size, b.created_at, b.updated_at
                FROM books b
                LEFT JOIN book_stats bs ON b.book_id = bs.book_id
                ORDER BY COALESCE(bs.downloads, 0) DESC, b.title
                LIMIT ?
            """
            results = self.db.execute_query(query, (limit,))

            return [Book.from_row(row) for row in results]

        except Exception as e:
            log_service_error("BookRepository", e, {"limit": limit})
            self.logger.error(f"Error obteniendo libros populares: {e}")
            return []

    def update(self, book: Book) -> bool:
        """Actualiza un libro existente."""
        try:
            # Validar límites antes de actualizar
            self._validate_book_limits(book)

            command = """
                UPDATE books 
                SET title = ?, alt_title = ?, author = ?, description = ?, 
                    language = ?, type = ?, isbn = ?, publisher = ?, year = ?,
                    file_id = ?, cover_id = ?, file_size = ?, updated_at = CURRENT_TIMESTAMP
                WHERE book_id = ?
            """
            params = (
                book.title,
                book.alt_title,
                book.author,
                book.description,
                book.language,
                book.type,
                book.isbn,
                book.publisher,
                book.year,
                book.file_id,
                book.cover_id,
                book.file_size,
                book.book_id
            )

            rows_affected = self.db.execute_command(command, params)
            success = rows_affected > 0

            if success:
                self.logger.info(f"Libro actualizado: {book.book_id}")
            else:
                self.logger.warning(f"No se encontró libro para actualizar: {book.book_id}")

            return success

        except Exception as e:
            log_service_error("BookRepository", e, {"book_id": book.book_id})
            self.logger.error(f"Error actualizando libro {book.book_id}: {e}")
            return False

    def update_file_id(self, book_id: str, file_id: str, file_size: Optional[int] = None) -> bool:
        """Actualiza file_id y opcionalmente file_size de un libro."""
        try:
            if file_size:
                command = """
                    UPDATE books 
                    SET file_id = ?, file_size = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE book_id = ?
                """
                params = (file_id, file_size, book_id)
            else:
                command = """
                    UPDATE books 
                    SET file_id = ?, updated_at = CURRENT_TIMESTAMP 
                    WHERE book_id = ?
                """
                params = (file_id, book_id)

            rows_affected = self.db.execute_command(command, params)
            success = rows_affected > 0

            if success:
                self.logger.info(f"File ID actualizado para libro: {book_id}")

            return success

        except Exception as e:
            log_service_error("BookRepository", e, {"book_id": book_id, "file_id": file_id})
            self.logger.error(f"Error actualizando file_id: {e}")
            return False

    def delete(self, book_id: str) -> bool:
        """Elimina un libro por book_id."""
        try:
            command = "DELETE FROM books WHERE book_id = ?"
            rows_affected = self.db.execute_command(command, (book_id,))
            success = rows_affected > 0

            if success:
                self.logger.info(f"Libro eliminado: {book_id}")
            else:
                self.logger.warning(f"No se encontró libro para eliminar: {book_id}")

            return success

        except Exception as e:
            log_service_error("BookRepository", e, {"book_id": book_id})
            self.logger.error(f"Error eliminando libro {book_id}: {e}")
            return False

    def exists(self, book_id: str) -> bool:
        """Verifica si existe un libro con el book_id dado."""
        try:
            query = "SELECT 1 FROM books WHERE book_id = ? LIMIT 1"
            results = self.db.execute_query(query, (book_id,))
            return len(results) > 0

        except Exception as e:
            log_service_error("BookRepository", e, {"book_id": book_id})
            self.logger.error(f"Error verificando existencia del libro {book_id}: {e}")
            return False

    def exists_by_title(self, title: str) -> bool:
        """Verifica si existe un libro con el título dado."""
        try:
            query = "SELECT 1 FROM books WHERE LOWER(title) = ? LIMIT 1"
            results = self.db.execute_query(query, (title.lower(),))
            return len(results) > 0

        except Exception as e:
            log_service_error("BookRepository", e, {"title": title})
            self.logger.error(f"Error verificando existencia por título '{title}': {e}")
            return False

    def count(self) -> int:
        """Retorna el número total de libros."""
        try:
            query = "SELECT COUNT(*) as count FROM books"
            results = self.db.execute_query(query)

            if results:
                return results[0]['count']

            return 0

        except Exception as e:
            log_service_error("BookRepository", e)
            self.logger.error(f"Error contando libros: {e}")
            return 0

    def get_all_book_ids(self) -> List[str]:
        """Obtiene todos los book_ids para comandos dinámicos."""
        try:
            query = "SELECT book_id FROM books WHERE book_id IS NOT NULL ORDER BY book_id"
            results = self.db.execute_query(query)

            return [row['book_id'] for row in results]

        except Exception as e:
            log_service_error("BookRepository", e)
            self.logger.error(f"Error obteniendo book_ids: {e}")
            return []

    def get_books_for_recommendations(self) -> List[Tuple[str, str]]:
        """Obtiene lista simplificada (book_id, title) para recomendaciones."""
        try:
            query = """
                SELECT b.book_id, b.title 
                FROM books b
                LEFT JOIN book_stats bs ON b.book_id = bs.book_id
                WHERE b.book_id IS NOT NULL 
                ORDER BY COALESCE(bs.downloads, 0) DESC, b.title
            """
            results = self.db.execute_query(query)

            return [(row['book_id'], row['title']) for row in results]

        except Exception as e:
            log_service_error("BookRepository", e)
            self.logger.error(f"Error obteniendo libros para recomendaciones: {e}")
            return []

    # OPERACIONES CON ESTADÍSTICAS

    def get_book_stats(self, book_id: str) -> Optional[BookStats]:
        """Obtiene estadísticas de un libro."""
        try:
            query = """
                SELECT id, book_id, downloads, searches, last_accessed, created_at
                FROM book_stats 
                WHERE book_id = ?
            """
            results = self.db.execute_query(query, (book_id,))

            if results:
                return BookStats.from_row(results[0])

            return None

        except Exception as e:
            log_service_error("BookRepository", e, {"book_id": book_id})
            self.logger.error(f"Error obteniendo estadísticas del libro {book_id}: {e}")
            return None

    def increment_downloads(self, book_id: str) -> bool:
        """Incrementa contador de descargas."""
        try:
            command = """
                UPDATE book_stats 
                SET downloads = downloads + 1, last_accessed = CURRENT_TIMESTAMP 
                WHERE book_id = ?
            """
            rows_affected = self.db.execute_command(command, (book_id,))

            if rows_affected == 0:
                # Crear registro si no existe
                self._ensure_stats_record(book_id)
                rows_affected = self.db.execute_command(command, (book_id,))

            return rows_affected > 0

        except Exception as e:
            log_service_error("BookRepository", e, {"book_id": book_id})
            self.logger.error(f"Error incrementando descargas: {e}")
            return False

    def increment_searches(self, book_id: str) -> bool:
        """Incrementa contador de búsquedas."""
        try:
            command = """
                UPDATE book_stats 
                SET searches = searches + 1 
                WHERE book_id = ?
            """
            rows_affected = self.db.execute_command(command, (book_id,))

            if rows_affected == 0:
                # Crear registro si no existe
                self._ensure_stats_record(book_id)
                rows_affected = self.db.execute_command(command, (book_id,))

            return rows_affected > 0

        except Exception as e:
            log_service_error("BookRepository", e, {"book_id": book_id})
            self.logger.error(f"Error incrementando búsquedas: {e}")
            return False

    def update_last_accessed(self, book_id: str) -> bool:
        """Actualiza timestamp de último acceso."""
        try:
            command = """
                UPDATE book_stats 
                SET last_accessed = CURRENT_TIMESTAMP 
                WHERE book_id = ?
            """
            rows_affected = self.db.execute_command(command, (book_id,))

            if rows_affected == 0:
                # Crear registro si no existe
                self._ensure_stats_record(book_id)
                rows_affected = self.db.execute_command(command, (book_id,))

            return rows_affected > 0

        except Exception as e:
            log_service_error("BookRepository", e, {"book_id": book_id})
            self.logger.error(f"Error actualizando último acceso: {e}")
            return False

    def _ensure_stats_record(self, book_id: str) -> None:
        """Asegura que existe un registro de estadísticas para el libro."""
        try:
            command = """
                INSERT OR IGNORE INTO book_stats (book_id, downloads, searches) 
                VALUES (?, 0, 0)
            """
            self.db.execute_command(command, (book_id,))

        except Exception as e:
            self.logger.warning(f"Error creando registro de estadísticas: {e}")

    def _validate_book_limits(self, book: Book) -> None:
        """Valida que el libro cumple con los límites de BD."""
        if len(book.title) > DatabaseConstants.MAX_TITLE_LENGTH:
            raise ValueError(f"Título excede {DatabaseConstants.MAX_TITLE_LENGTH} caracteres")

        if len(book.author) > DatabaseConstants.MAX_AUTHOR_LENGTH:
            raise ValueError(f"Autor excede {DatabaseConstants.MAX_AUTHOR_LENGTH} caracteres")

        if book.description and len(book.description) > DatabaseConstants.MAX_DESCRIPTION_LENGTH:
            raise ValueError(f"Descripción excede {DatabaseConstants.MAX_DESCRIPTION_LENGTH} caracteres")

        if (len(book.book_id) < DatabaseConstants.MIN_BOOK_ID_LENGTH or
            len(book.book_id) > DatabaseConstants.MAX_BOOK_ID_LENGTH):
            raise ValueError(f"book_id debe tener entre {DatabaseConstants.MIN_BOOK_ID_LENGTH} y {DatabaseConstants.MAX_BOOK_ID_LENGTH} caracteres")