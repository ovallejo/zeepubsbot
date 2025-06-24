"""
Modelos de datos para ZeepubsBot.
Define estructuras de datos, validaciones y reglas de negocio.
"""

import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from enum import Enum

from config.bot_config import get_logger
from data.database_config import DatabaseConstants
from utils.error_handler import log_service_error


class BookLanguage(Enum):
    """Idiomas soportados para libros (sincronizado con BD)."""
    SPANISH = "es"
    ENGLISH = "en"
    FRENCH = "fr"
    GERMAN = "de"
    ITALIAN = "it"
    PORTUGUESE = "pt"
    UNKNOWN = "unknown"


class BookType(Enum):
    """Tipos de publicaciones soportadas (sincronizado con BD)."""
    BOOK = "book"
    NOVEL = "novel"
    ESSAY = "essay"
    MANUAL = "manual"
    COMIC = "comic"
    MAGAZINE = "magazine"
    OTHER = "other"


@dataclass
class BookMetadata:
    """Metadatos completos de un libro."""
    title: str
    author: str
    description: str = ""
    alt_title: Optional[str] = None
    language: BookLanguage = BookLanguage.SPANISH
    type: BookType = BookType.BOOK
    isbn: Optional[str] = None
    publisher: Optional[str] = None
    year: Optional[int] = None

    def __post_init__(self):
        """Validación y limpieza después de inicialización."""
        self.title = self._clean_text(self.title)
        self.author = self._clean_text(self.author)
        self.description = self._clean_description(self.description)

        if self.alt_title:
            self.alt_title = self._clean_text(self.alt_title)

        self._validate()

    def _clean_text(self, text: str) -> str:
        """Limpia y normaliza texto usando límites de BD."""
        if not text:
            return ""

        # Remover espacios excesivos y caracteres especiales
        cleaned = re.sub(r'\s+', ' ', text.strip())
        cleaned = re.sub(r'[^\w\s\-\.,;:!?()\'"áéíóúñüÁÉÍÓÚÑÜ]', '', cleaned)

        # Usar límites de DatabaseConstants
        max_length = DatabaseConstants.MAX_TITLE_LENGTH
        return cleaned[:max_length]

    def _clean_description(self, description: str) -> str:
        """Limpia descripción usando límites de BD."""
        if not description:
            return ""

        # Remover tags HTML
        cleaned = re.sub(r'<[^>]+>', '', description)

        # Normalizar espacios
        cleaned = re.sub(r'\s+', ' ', cleaned.strip())

        # Limitar longitud usando DatabaseConstants
        max_length = DatabaseConstants.MAX_DESCRIPTION_LENGTH
        if len(cleaned) > max_length:
            cleaned = cleaned[:max_length - 3] + "..."

        return cleaned

    def _validate(self):
        """Valida los datos del modelo contra constrains de BD."""
        if not self.title or len(self.title.strip()) == 0:
            raise ValueError("El título es requerido")

        if not self.author or len(self.author.strip()) == 0:
            raise ValueError("El autor es requerido")

        # Validar longitudes contra DatabaseConstants
        if len(self.title) > DatabaseConstants.MAX_TITLE_LENGTH:
            raise ValueError(f"Título excede {DatabaseConstants.MAX_TITLE_LENGTH} caracteres")

        if len(self.author) > DatabaseConstants.MAX_AUTHOR_LENGTH:
            raise ValueError(f"Autor excede {DatabaseConstants.MAX_AUTHOR_LENGTH} caracteres")

        if self.description and len(self.description) > DatabaseConstants.MAX_DESCRIPTION_LENGTH:
            raise ValueError(f"Descripción excede {DatabaseConstants.MAX_DESCRIPTION_LENGTH} caracteres")

        # Validar año
        if self.year and (self.year < 1000 or self.year > datetime.now().year + 1):
            raise ValueError(f"Año inválido: {self.year}")

        # Validar ISBN
        if self.isbn and not self._validate_isbn(self.isbn):
            raise ValueError(f"ISBN inválido: {self.isbn}")

        # Validar que language y type sean válidos para BD
        if self.language.value not in ['es', 'en', 'fr', 'de', 'it', 'pt', 'unknown']:
            raise ValueError(f"Idioma no soportado: {self.language.value}")

        if self.type.value not in ['book', 'novel', 'essay', 'manual', 'comic', 'magazine', 'other']:
            raise ValueError(f"Tipo no soportado: {self.type.value}")

    def _validate_isbn(self, isbn: str) -> bool:
        """Valida formato de ISBN."""
        # Remover guiones y espacios
        clean_isbn = re.sub(r'[\s\-]', '', isbn)

        # Verificar longitud (ISBN-10 o ISBN-13)
        if len(clean_isbn) not in [10, 13]:
            return False

        # Verificar que sean solo números (excepto X en ISBN-10)
        if not re.match(r'^\d{9}[\dX]$|^\d{13}$', clean_isbn):
            return False

        return True


@dataclass
class TelegramFileInfo:
    """Información de archivos en Telegram."""
    file_id: str
    file_unique_id: Optional[str] = None
    file_size: Optional[int] = None
    mime_type: Optional[str] = None
    uploaded_at: datetime = field(default_factory=datetime.now)

    def __post_init__(self):
        """Validación de file_id."""
        if not self.file_id or len(self.file_id.strip()) == 0:
            raise ValueError("file_id es requerido")

        # Validar formato básico de file_id de Telegram
        if not re.match(r'^[a-zA-Z0-9\-_]{10,}$', self.file_id):
            raise ValueError("Formato de file_id inválido")


@dataclass
class Book:
    """Modelo principal de libro sincronizado con schema de BD."""
    book_id: str
    metadata: BookMetadata
    file_info: Optional[TelegramFileInfo] = None
    cover_id: Optional[str] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    def __post_init__(self):
        """Validación del modelo principal."""
        if not self.book_id or len(self.book_id.strip()) == 0:
            raise ValueError("book_id es requerido")

        # Validar formato de book_id usando DatabaseConstants
        if (len(self.book_id) < DatabaseConstants.MIN_BOOK_ID_LENGTH or
            len(self.book_id) > DatabaseConstants.MAX_BOOK_ID_LENGTH):
            raise ValueError(
                f"book_id debe tener entre {DatabaseConstants.MIN_BOOK_ID_LENGTH} "
                f"y {DatabaseConstants.MAX_BOOK_ID_LENGTH} caracteres"
            )

        # Validar formato alfanumérico
        if not re.match(r'^[a-zA-Z0-9]{5,20}$', self.book_id):
            raise ValueError("book_id debe ser alfanumérico")

    # Properties para acceso directo a metadatos
    @property
    def title(self) -> str:
        """Título principal del libro."""
        return self.metadata.title

    @property
    def author(self) -> str:
        """Autor del libro."""
        return self.metadata.author

    @property
    def description(self) -> str:
        """Descripción del libro."""
        return self.metadata.description

    @property
    def alt_title(self) -> Optional[str]:
        """Título alternativo."""
        return self.metadata.alt_title

    @property
    def language(self) -> str:
        """Idioma como string."""
        return self.metadata.language.value

    @property
    def type(self) -> str:
        """Tipo como string."""
        return self.metadata.type.value

    @property
    def isbn(self) -> Optional[str]:
        """ISBN del libro."""
        return self.metadata.isbn

    @property
    def publisher(self) -> Optional[str]:
        """Editorial del libro."""
        return self.metadata.publisher

    @property
    def year(self) -> Optional[int]:
        """Año de publicación."""
        return self.metadata.year

    @property
    def file_id(self) -> Optional[str]:
        """ID del archivo en Telegram."""
        return self.file_info.file_id if self.file_info else None

    @property
    def file_size(self) -> Optional[int]:
        """Tamaño del archivo en bytes."""
        return self.file_info.file_size if self.file_info else None

    @property
    def has_cover(self) -> bool:
        """Verifica si tiene portada."""
        return bool(self.cover_id)

    @property
    def has_file(self) -> bool:
        """Verifica si tiene archivo asociado."""
        return bool(self.file_info and self.file_info.file_id)

    def to_dict(self) -> Dict[str, Any]:
        """Convierte el libro a diccionario para serialización/BD."""
        return {
            'id': self.id,
            'book_id': self.book_id,
            'title': self.title,
            'alt_title': self.alt_title,
            'author': self.author,
            'description': self.description,
            'language': self.language,
            'type': self.type,
            'isbn': self.isbn,
            'publisher': self.publisher,
            'year': self.year,
            'file_id': self.file_id,
            'cover_id': self.cover_id,
            'file_size': self.file_size,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def to_legacy_tuple(self) -> tuple:
        """Convierte a tupla para compatibilidad con código existente."""
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
    def from_dict(cls, data: Dict[str, Any]) -> 'Book':
        """Crea libro desde diccionario (para EPUBs procesados)."""
        try:
            # Crear metadatos
            metadata = BookMetadata(
                title=data['title'],
                author=data['author'],
                description=data.get('description', ''),
                alt_title=data.get('alt_title'),
                language=BookLanguage(data.get('language', 'es')),
                type=BookType(data.get('type', 'book')),
                isbn=data.get('isbn'),
                publisher=data.get('publisher'),
                year=data.get('year')
            )

            # Crear info de archivo si existe
            file_info = None
            if data.get('file_id'):
                file_info = TelegramFileInfo(
                    file_id=data['file_id'],
                    file_unique_id=data.get('file_unique_id'),
                    file_size=data.get('file_size'),
                    mime_type=data.get('mime_type', 'application/epub+zip')
                )

            # Parsear fechas si existen
            created_at = None
            updated_at = None
            if data.get('created_at'):
                if isinstance(data['created_at'], str):
                    created_at = datetime.fromisoformat(data['created_at'])
                else:
                    created_at = data['created_at']

            if data.get('updated_at'):
                if isinstance(data['updated_at'], str):
                    updated_at = datetime.fromisoformat(data['updated_at'])
                else:
                    updated_at = data['updated_at']

            return cls(
                book_id=data['book_id'] if 'book_id' in data else data['id'],
                metadata=metadata,
                file_info=file_info,
                cover_id=data.get('cover_id'),
                id=data.get('id'),
                created_at=created_at,
                updated_at=updated_at
            )

        except Exception as e:
            logger = get_logger(__name__)
            log_service_error("BookModels", e, {"data": str(data)[:200]})
            logger.error(f"Error creando libro desde diccionario: {e}")
            raise ValueError(f"Datos inválidos para crear libro: {e}")

    @classmethod
    def from_row(cls, row) -> 'Book':
        """Crea libro desde fila de base de datos."""
        try:
            # Convertir row a dict si es necesario
            if hasattr(row, 'keys'):
                data = dict(row)
            else:
                # Mapear tupla a estructura esperada (orden del SELECT)
                data = {
                    'id': row[0],
                    'book_id': row[1],
                    'title': row[2],
                    'alt_title': row[3],
                    'author': row[4],
                    'description': row[5],
                    'language': row[6] if len(row) > 6 else 'es',
                    'type': row[7] if len(row) > 7 else 'book',
                    'file_id': row[8] if len(row) > 8 else None,
                    'cover_id': row[9] if len(row) > 9 else None,
                    'isbn': row[10] if len(row) > 10 else None,
                    'publisher': row[11] if len(row) > 11 else None,
                    'year': row[12] if len(row) > 12 else None,
                    'file_size': row[13] if len(row) > 13 else None,
                    'created_at': row[14] if len(row) > 14 else None,
                    'updated_at': row[15] if len(row) > 15 else None
                }

            return cls.from_dict(data)

        except Exception as e:
            logger = get_logger(__name__)
            log_service_error("BookModels", e, {"row": str(row)[:200]})
            logger.error(f"Error creando libro desde fila de BD: {e}")
            raise ValueError(f"Fila de BD inválida: {e}")

    def update_metadata(self, **kwargs) -> None:
        """Actualiza metadatos del libro con validación."""
        try:
            for key, value in kwargs.items():
                if hasattr(self.metadata, key):
                    setattr(self.metadata, key, value)

            # Re-validar después de actualización
            self.metadata._validate()

        except Exception as e:
            logger = get_logger(__name__)
            log_service_error("BookModels", e, {"book_id": self.book_id, "updates": kwargs})
            logger.error(f"Error actualizando metadatos: {e}")
            raise

    def update_file_info(self, file_id: str, **kwargs) -> None:
        """Actualiza información del archivo."""
        try:
            self.file_info = TelegramFileInfo(
                file_id=file_id,
                file_unique_id=kwargs.get('file_unique_id'),
                file_size=kwargs.get('file_size'),
                mime_type=kwargs.get('mime_type', 'application/epub+zip')
            )

        except Exception as e:
            logger = get_logger(__name__)
            log_service_error("BookModels", e, {"book_id": self.book_id, "file_id": file_id})
            logger.error(f"Error actualizando info de archivo: {e}")
            raise


@dataclass
class BookStats:
    """Modelo para estadísticas de libros (tabla book_stats)."""
    book_id: str
    downloads: int = 0
    searches: int = 0
    last_accessed: Optional[datetime] = None
    id: Optional[int] = None
    created_at: Optional[datetime] = None

    @classmethod
    def from_row(cls, row) -> 'BookStats':
        """Crea instancia desde fila de base de datos."""
        if hasattr(row, 'keys'):
            return cls(
                id=row['id'],
                book_id=row['book_id'],
                downloads=row['downloads'] or 0,
                searches=row['searches'] or 0,
                last_accessed=row['last_accessed'],
                created_at=row['created_at']
            )
        else:
            return cls(
                id=row[0],
                book_id=row[1],
                downloads=row[2] or 0,
                searches=row[3] or 0,
                last_accessed=row[4],
                created_at=row[5]
            )

    def to_dict(self) -> Dict[str, Any]:
        """Convierte a diccionario."""
        return {
            'id': self.id,
            'book_id': self.book_id,
            'downloads': self.downloads,
            'searches': self.searches,
            'last_accessed': self.last_accessed.isoformat() if self.last_accessed else None,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


@dataclass
class BookSearchResult:
    """Resultado de búsqueda de libros."""
    books: List[Book]
    total_count: int
    query: str
    search_time_ms: float = 0.0

    @property
    def has_results(self) -> bool:
        """Verifica si hay resultados."""
        return len(self.books) > 0

    @property
    def result_count(self) -> int:
        """Número de resultados en esta página."""
        return len(self.books)

    def to_legacy_tuples(self) -> List[tuple]:
        """Convierte a lista de tuplas para compatibilidad."""
        return [book.to_legacy_tuple() for book in self.books]


class BookValidator:
    """Validador especializado para libros usando DatabaseConstants."""

    @staticmethod
    def validate_book_id(book_id: str) -> bool:
        """Valida formato de book_id usando DatabaseConstants."""
        if not book_id:
            return False

        # Validar longitud
        if (len(book_id) < DatabaseConstants.MIN_BOOK_ID_LENGTH or
            len(book_id) > DatabaseConstants.MAX_BOOK_ID_LENGTH):
            return False

        # Validar formato alfanumérico
        return bool(re.match(r'^[a-zA-Z0-9]+$', book_id))

    @staticmethod
    def validate_title(title: str) -> bool:
        """Valida título usando DatabaseConstants."""
        if not title or len(title.strip()) == 0:
            return False

        return len(title.strip()) <= DatabaseConstants.MAX_TITLE_LENGTH

    @staticmethod
    def validate_author(author: str) -> bool:
        """Valida autor usando DatabaseConstants."""
        if not author or len(author.strip()) == 0:
            return False

        return len(author.strip()) <= DatabaseConstants.MAX_AUTHOR_LENGTH

    @staticmethod
    def validate_description(description: str) -> bool:
        """Valida descripción usando DatabaseConstants."""
        if not description:
            return True  # Descripción es opcional

        return len(description) <= DatabaseConstants.MAX_DESCRIPTION_LENGTH

    @staticmethod
    def validate_file_id(file_id: str) -> bool:
        """Valida file_id de Telegram."""
        if not file_id:
            return False

        # File IDs de Telegram son alfanuméricos con algunos caracteres especiales
        return bool(re.match(r'^[a-zA-Z0-9\-_]{10,}$', file_id))

    @staticmethod
    def validate_complete_book(book: Book) -> List[str]:
        """Valida libro completo y retorna lista de errores."""
        errors = []

        try:
            if not BookValidator.validate_book_id(book.book_id):
                errors.append("book_id inválido")

            if not BookValidator.validate_title(book.title):
                errors.append("título inválido")

            if not BookValidator.validate_author(book.author):
                errors.append("autor inválido")

            if not BookValidator.validate_description(book.description):
                errors.append("descripción demasiado larga")

            if book.file_id and not BookValidator.validate_file_id(book.file_id):
                errors.append("file_id inválido")

            # Validar enums
            if book.language not in [lang.value for lang in BookLanguage]:
                errors.append("idioma no soportado")

            if book.type not in [type_.value for type_ in BookType]:
                errors.append("tipo no soportado")

        except Exception as e:
            errors.append(f"Error de validación: {str(e)}")

        return errors