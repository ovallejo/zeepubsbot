"""
Utilidades modernizadas para procesamiento de archivos EPUB.
Integrado con nuevos modelos y validaciones automáticas.
"""

import re
import secrets
from pathlib import Path
from typing import Dict, Any, Optional, Set, List

import ebooklib
import isbnlib
from ebooklib import epub

from config.bot_config import get_logger, BotConstants
from data.book_models import Book, BookMetadata, TelegramFileInfo, BookLanguage, BookType
from data.database_config import DatabaseConstants
from utils.error_handler import log_service_error


class EpubsUtils:
    """Utilidades para procesamiento seguro de archivos EPUB."""

    def __init__(self):
        """Inicializa las utilidades EPUB."""
        self.logger = get_logger(__name__)
        self._generated_codes: Set[str] = set()

    def processing_ebook(self, file_path: Path, file_id: str) -> Optional[Book]:
        """
        Procesa un archivo EPUB y retorna modelo Book validado.

        Args:
            file_path: Ruta al archivo EPUB
            file_id: ID del archivo en Telegram

        Returns:
            Book validado o None si falla
        """
        try:
            if not self._validate_epub_file(file_path):
                self.logger.warning(f"Archivo EPUB inválido: {file_path}")
                return None

            # Extraer metadatos base
            epub_data = self._extract_epub_metadata(file_path)
            if not epub_data:
                self.logger.error(f"No se pudieron extraer metadatos: {file_path}")
                return None

            # Crear metadatos estructurados
            metadata = self._create_book_metadata(epub_data)

            # Crear información del archivo
            file_info = TelegramFileInfo(
                file_id=file_id,
                file_size=file_path.stat().st_size,
                mime_type="application/epub+zip"
            )

            # Extraer portada si existe
            cover_data = self._extract_cover(file_path)

            # Crear modelo Book completo
            book = Book(
                book_id=self._create_book_id(),
                metadata=metadata,
                file_info=file_info
            )

            # Agregar cover_data como atributo temporal para file_manager
            if cover_data:
                book._cover_data = cover_data

            self.logger.info(f"EPUB procesado: {book.title}")
            return book

        except Exception as e:
            log_service_error("EpubsUtils", e, {"file_path": str(file_path)})
            self.logger.error(f"Error procesando EPUB {file_path}: {e}")
            return None

    def _validate_epub_file(self, file_path: Path) -> bool:
        """Valida que el archivo sea un EPUB válido."""
        try:
            # Verificar extensión
            if not str(file_path).lower().endswith(BotConstants.EPUB_EXTENSION):
                return False

            # Verificar existencia y tamaño
            if not file_path.exists() or file_path.stat().st_size == 0:
                return False

            # Verificar que se puede abrir como EPUB
            book = epub.read_epub(str(file_path))
            return bool(book and hasattr(book, 'get_metadata'))

        except Exception as e:
            self.logger.debug(f"Validación EPUB falló para {file_path}: {e}")
            return False

    def _extract_epub_metadata(self, file_path: Path) -> Optional[Dict[str, Any]]:
        """Extrae metadatos básicos del archivo EPUB."""
        try:
            book = epub.read_epub(str(file_path))

            # Extraer campos básicos
            title = self._get_metadata_value(book, "DC", "title")
            author = self._get_metadata_value(book, "DC", "creator")
            description = self._get_metadata_value(book, "DC", "description")
            language = self._get_metadata_value(book, "DC", "language")

            # Extraer campos opcionales
            publisher = self._get_metadata_value(book, "DC", "publisher")
            isbn = self._extract_isbn(book)
            year = self._extract_year(book)

            # Buscar título alternativo
            alt_title = self._extract_alt_title_from_isbn(isbn) if isbn else None

            return {
                'title': self._clean_title(title) if title else 'Sin título',
                'author': self._clean_text(author) if author else 'Autor desconocido',
                'description': self._clean_description(description) if description else '',
                'alt_title': alt_title,
                'language': self._normalize_language(language),
                'type': 'book',  # Default, se puede mejorar con detección automática
                'publisher': self._clean_text(publisher) if publisher else None,
                'isbn': isbn,
                'year': year
            }

        except Exception as e:
            log_service_error("EpubsUtils", e, {"file_path": str(file_path)})
            return None

    def _create_book_metadata(self, epub_data: Dict[str, Any]) -> BookMetadata:
        """Crea BookMetadata validado desde datos EPUB."""
        return BookMetadata(
            title=epub_data['title'],
            author=epub_data['author'],
            description=epub_data['description'],
            alt_title=epub_data.get('alt_title'),
            language=BookLanguage(epub_data.get('language', 'es')),
            type=BookType(epub_data.get('type', 'book')),
            isbn=epub_data.get('isbn'),
            publisher=epub_data.get('publisher'),
            year=epub_data.get('year')
        )

    def _get_metadata_value(self, book, namespace: str, name: str) -> Optional[str]:
        """Obtiene valor de metadato específico de forma segura."""
        try:
            metadata_list = book.get_metadata(namespace, name)
            if metadata_list and len(metadata_list) > 0:
                return str(metadata_list[0][0]).strip()
        except Exception:
            pass
        return None

    def _extract_isbn(self, book) -> Optional[str]:
        """Extrae y valida ISBN del libro."""
        try:
            identifiers = book.get_metadata('DC', 'identifier') or []

            for identifier in identifiers:
                identifier_str = str(identifier[0]).lower()
                if 'isbn' in identifier_str:
                    # Limpiar ISBN
                    isbn = re.sub(r'[^\d\dX]', '', identifier_str.upper())
                    if len(isbn) in [10, 13] and (isbn.replace('X', '').isdigit()):
                        return isbn

        except Exception as e:
            self.logger.debug(f"Error extrayendo ISBN: {e}")

        return None

    def _extract_year(self, book) -> Optional[int]:
        """Extrae año de publicación."""
        try:
            date_value = self._get_metadata_value(book, "DC", "date")
            if date_value:
                # Buscar año de 4 dígitos
                year_match = re.search(r'\b(19|20)\d{2}\b', date_value)
                if year_match:
                    year = int(year_match.group())
                    if 1000 <= year <= 2100:
                        return year
        except Exception as e:
            self.logger.debug(f"Error extrayendo año: {e}")

        return None

    def _extract_alt_title_from_isbn(self, isbn: str) -> Optional[str]:
        """Extrae título alternativo usando ISBN."""
        if not isbn:
            return None

        try:
            # Validar ISBN antes de consultar
            if not (isbnlib.is_isbn10(isbn) or isbnlib.is_isbn13(isbn)):
                return None

            meta_data = isbnlib.meta(isbn)
            if meta_data and 'Title' in meta_data:
                alt_title = str(meta_data['Title']).strip()
                return self._clean_title(alt_title) if alt_title else None

        except Exception as e:
            self.logger.debug(f"Error obteniendo metadatos ISBN {isbn}: {e}")

        return None

    def _extract_cover(self, file_path: Path) -> Optional[bytes]:
        """Extrae portada del archivo EPUB."""
        try:
            book = epub.read_epub(str(file_path))

            # Buscar por tipo COVER
            for item in book.get_items():
                if item.get_type() == ebooklib.ITEM_COVER:
                    cover_content = item.get_content()
                    if cover_content and len(cover_content) > 0:
                        self.logger.debug("Portada encontrada (ITEM_COVER)")
                        return cover_content

            # Buscar imagen con 'cover' en el nombre
            for item in book.get_items():
                if (item.get_type() == ebooklib.ITEM_IMAGE and
                        "cover" in item.file_name.lower()):
                    cover_content = item.get_content()
                    if cover_content and len(cover_content) > 0:
                        self.logger.debug(f"Portada encontrada: {item.file_name}")
                        return cover_content

            self.logger.debug("No se encontró portada")
            return None

        except Exception as e:
            self.logger.debug(f"Error extrayendo portada: {e}")
            return None

    def _clean_title(self, title: str) -> str:
        """Limpia y formatea título usando límites de BD."""
        if not title:
            return ""

        try:
            # Remover contenido entre corchetes y paréntesis
            cleaned = re.sub(r'\[.*?\]', '', title).strip()
            cleaned = re.sub(r'\(.*?\)', '', cleaned).strip()

            # Formatear volúmenes
            cleaned = cleaned.replace("Volumen", "Vol.")

            # Limpiar caracteres y espacios
            cleaned = re.sub(r'\s+', ' ', cleaned).strip()

            # Aplicar límite de BD
            max_length = DatabaseConstants.MAX_TITLE_LENGTH
            if len(cleaned) > max_length:
                cleaned = cleaned[:max_length].strip()

            return cleaned

        except Exception as e:
            self.logger.warning(f"Error limpiando título: {e}")
            return title[:DatabaseConstants.MAX_TITLE_LENGTH]

    def _clean_text(self, text: str) -> str:
        """Limpia texto general aplicando límites de BD."""
        if not text:
            return ""

        try:
            # Normalizar espacios
            cleaned = re.sub(r'\s+', ' ', text.strip())

            # Remover caracteres especiales problemáticos
            cleaned = re.sub(r'[^\w\s\-\.,;:!?()\'"áéíóúñüÁÉÍÓÚÑÜ]', '', cleaned)

            return cleaned

        except Exception as e:
            self.logger.warning(f"Error limpiando texto: {e}")
            return text

    def _clean_description(self, description: str) -> str:
        """Limpia descripción aplicando límites de BD."""
        if not description:
            return ""

        try:
            # Remover tags HTML
            cleaned = re.sub(r'<[^>]+>', '', description)

            # Normalizar espacios
            cleaned = re.sub(r'\s+', ' ', cleaned.strip())

            # Aplicar límite de BD
            max_length = DatabaseConstants.MAX_DESCRIPTION_LENGTH
            if len(cleaned) > max_length:
                cleaned = cleaned[:max_length - 3] + "..."

            return cleaned

        except Exception as e:
            self.logger.warning(f"Error limpiando descripción: {e}")
            return description[:DatabaseConstants.MAX_DESCRIPTION_LENGTH]

    def _normalize_language(self, language: str) -> str:
        """Normaliza código de idioma a valores soportados."""
        if not language:
            return 'es'

        # Mapeo de códigos comunes
        language_map = {
            'spa': 'es', 'spanish': 'es', 'español': 'es',
            'eng': 'en', 'english': 'en', 'inglés': 'en',
            'fra': 'fr', 'french': 'fr', 'français': 'fr',
            'deu': 'de', 'german': 'de', 'deutsch': 'de',
            'ita': 'it', 'italian': 'it', 'italiano': 'it',
            'por': 'pt', 'portuguese': 'pt', 'português': 'pt'
        }

        lang_lower = language.lower().strip()

        # Verificar si ya es un código válido
        valid_codes = ['es', 'en', 'fr', 'de', 'it', 'pt', 'unknown']
        if lang_lower in valid_codes:
            return lang_lower

        # Buscar en mapeo
        return language_map.get(lang_lower, 'unknown')

    def _create_book_id(self) -> str:
        """Crea ID único para el libro usando límites de BD."""
        max_attempts = 100
        attempts = 0

        while attempts < max_attempts:
            # Generar código entre límites de BD
            min_length = DatabaseConstants.MIN_BOOK_ID_LENGTH
            max_length = DatabaseConstants.MAX_BOOK_ID_LENGTH

            # Usar longitud média
            code_length = (min_length + max_length) // 2
            code = secrets.token_hex(code_length // 2)[:code_length]

            if code not in self._generated_codes:
                self._generated_codes.add(code)
                return code

            attempts += 1

        # Fallback con timestamp
        import time
        fallback_id = f"bk{int(time.time())}"
        return fallback_id[:DatabaseConstants.MAX_BOOK_ID_LENGTH]

    def shorten_middle_text(self, text: str) -> str:
        """Acorta texto largo manteniendo inicio y final."""
        if not text or len(text) <= BotConstants.TITLE_TRUNCATE_LENGTH:
            return text

        try:
            parts_length = BotConstants.TITLE_PARTS_LENGTH
            return f"{text[:parts_length]}...{text[-parts_length:]}"
        except Exception:
            return text[:BotConstants.TITLE_TRUNCATE_LENGTH]

    def get_epub_files(self, directory: str) -> List[str]:
        """Obtiene lista de archivos EPUB válidos en un directorio."""
        epub_files = []

        try:
            directory_path = Path(directory)
            if not directory_path.exists():
                return epub_files

            for epub_file in directory_path.rglob(f"*{BotConstants.EPUB_EXTENSION}"):
                if self._validate_epub_file(epub_file):
                    epub_files.append(str(epub_file))

            self.logger.info(f"Encontrados {len(epub_files)} EPUBs válidos en {directory}")
            return epub_files

        except Exception as e:
            log_service_error("EpubsUtils", e, {"directory": directory})
            return []

    def extract_basic_info(self, file_path: str) -> Dict[str, str]:
        """Extrae información básica sin procesamiento completo."""
        try:
            path = Path(file_path)
            if not self._validate_epub_file(path):
                return {
                    'title': "Archivo EPUB inválido",
                    'author': "Desconocido",
                    'language': "unknown"
                }

            epub_data = self._extract_epub_metadata(path)
            if not epub_data:
                return {
                    'title': "Error leyendo metadatos",
                    'author': "Desconocido",
                    'language': "unknown"
                }

            return {
                'title': epub_data['title'],
                'author': epub_data['author'],
                'language': epub_data['language']
            }

        except Exception as e:
            log_service_error("EpubsUtils", e, {"file_path": file_path})
            return {
                'title': "Error procesando archivo",
                'author': "Desconocido",
                'language': "unknown"
            }

    def get_file_stats(self, file_path: str) -> Dict[str, Any]:
        """Obtiene estadísticas del archivo EPUB."""
        try:
            path = Path(file_path)

            if not path.exists():
                return {'exists': False}

            stat = path.stat()
            is_valid = self._validate_epub_file(path)

            return {
                'exists': True,
                'size_bytes': stat.st_size,
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'modified_time': stat.st_mtime,
                'is_valid_epub': is_valid,
                'extension': path.suffix.lower()
            }

        except Exception as e:
            log_service_error("EpubsUtils", e, {"file_path": file_path})
            return {'exists': False, 'error': str(e)}