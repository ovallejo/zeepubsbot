"""
Servicio modernizado de gestión de archivos.
Integrado con nuevos modelos y repository pattern.
"""

from pathlib import Path
from typing import Dict, Any, Optional

from telegram import File
from telegram.error import TelegramError
from telegram.ext import ContextTypes

from config.bot_config import get_config, get_logger, BotConstants
from data.book_repository import BookRepository, Book
from utils.epubs_utils import EpubsUtils
from utils.error_handler import log_service_error


class FileManager:
    """Servicio para gestión segura de archivos EPUB."""

    def __init__(self, book_service=None):
        """
        Inicializa el gestor de archivos.

        Args:
            book_service: Mantenido para compatibilidad, usa repository internamente
        """
        self.config = get_config()
        self.logger = get_logger(__name__)
        self.epub_utils = EpubsUtils()
        self.book_repository = BookRepository()

        # Directorio temporal para archivos
        self.temp_dir = Path("temp_uploads")
        self._ensure_temp_directory()

    def _ensure_temp_directory(self) -> None:
        """Asegura que el directorio temporal exista."""
        try:
            self.temp_dir.mkdir(exist_ok=True)
            self.logger.debug(f"Directorio temporal listo: {self.temp_dir}")
        except Exception as e:
            self.logger.error(f"Error creando directorio temporal: {e}")

    async def process_uploaded_file(
            self,
            file_attachment: File,
            context: ContextTypes.DEFAULT_TYPE
    ) -> Dict[str, Any]:
        """
        Procesa archivo subido y retorna resultado.

        Args:
            file_attachment: Archivo de Telegram
            context: Contexto del bot

        Returns:
            Dict con resultado del procesamiento
        """
        temp_file_path = None

        try:
            # Validar que es un archivo
            if not file_attachment:
                return self._create_error_result("No se recibió ningún archivo")

            # Descargar archivo
            download_result = await self._download_file(file_attachment)
            if not download_result['success']:
                return download_result

            temp_file_path = download_result['file_path']

            # Validar que es EPUB
            if not self._is_epub_file(temp_file_path):
                return self._create_error_result("El archivo debe ser un EPUB válido")

            # Procesar EPUB con nuevos modelos
            book = self._process_epub_file(temp_file_path, file_attachment.file_id)
            if not book:
                return self._create_error_result("Error procesando metadatos del EPUB")

            # Verificar si el libro ya existe
            if self.book_repository.exists_by_title(book.title):
                return self._create_error_result("El libro ya existe en la base de datos")

            # Procesar portada si existe
            cover_result = await self._process_cover(book, context)
            if cover_result['success'] and cover_result.get('cover_id'):
                book.cover_id = cover_result['cover_id']

            # Guardar libro en base de datos
            saved_book = self.book_repository.create(book)

            if not saved_book:
                return self._create_error_result("Error guardando libro en base de datos")

            self.logger.info(f"Libro guardado exitosamente: {saved_book.title}")

            return {
                'success': True,
                'message': 'Libro procesado exitosamente',
                'book_data': {
                    'id': saved_book.book_id,
                    'title': saved_book.title,
                    'author': saved_book.author
                }
            }

        except Exception as e:
            log_service_error("FileManager", e, {
                "file_id": getattr(file_attachment, 'file_id', 'unknown')
            })
            self.logger.error(f"Error procesando archivo subido: {e}")
            return self._create_error_result(f"Error procesando archivo: {str(e)}")

        finally:
            if temp_file_path:
                self._cleanup_temp_file(temp_file_path)

    async def _download_file(self, file_attachment: File) -> Dict[str, Any]:
        """Descarga archivo de Telegram a directorio temporal."""
        try:
            # Obtener el objeto File real de Telegram
            file_obj = await file_attachment.get_file()

            # Generar nombre único para archivo temporal
            temp_filename = f"upload_{file_attachment.file_unique_id}.epub"
            temp_file_path = self.temp_dir / temp_filename

            # Descargar archivo usando el método correcto
            downloaded_file = await file_obj.download_to_drive(temp_file_path)

            self.logger.info(f"Archivo descargado: {downloaded_file}")

            return {
                'success': True,
                'file_path': downloaded_file,
                'original_name': getattr(file_attachment, 'file_name', 'unknown.epub')
            }

        except TelegramError as e:
            self.logger.error(f"Error descargando archivo de Telegram: {e}")
            return self._create_error_result(f"Error descargando archivo: {str(e)}")

        except Exception as e:
            self.logger.error(f"Error inesperado descargando archivo: {e}")
            return self._create_error_result("Error procesando descarga")

    def _is_epub_file(self, file_path: Path) -> bool:
        """Valida que el archivo sea un EPUB válido."""
        try:
            # Verificar extensión
            if not str(file_path).lower().endswith(BotConstants.EPUB_EXTENSION):
                self.logger.debug("Archivo no tiene extensión EPUB")
                return False

            # Verificar que el archivo existe y tiene contenido
            if not file_path.exists() or file_path.stat().st_size == 0:
                self.logger.debug("Archivo no existe o está vacío")
                return False

            # Validar usando EpubsUtils
            return self._validate_epub_structure(file_path)

        except Exception as e:
            self.logger.warning(f"Error validando archivo EPUB: {e}")
            return False

    def _validate_epub_structure(self, file_path: Path) -> bool:
        """Valida estructura básica del archivo EPUB usando EpubsUtils."""
        try:
            # Usar EpubsUtils para validación básica
            basic_info = self.epub_utils.extract_basic_info(str(file_path))

            # Verificar que se pudieron extraer metadatos mínimos
            return (basic_info.get('title') != "Error procesando archivo" and
                    basic_info.get('title') != "Archivo EPUB inválido")

        except Exception as e:
            self.logger.debug(f"Validación de estructura EPUB falló: {e}")
            return False

    def _process_epub_file(self, file_path: Path, file_id: str) -> Optional[Book]:
        """
        Procesa archivo EPUB y retorna modelo Book validado.

        Args:
            file_path: Ruta al archivo EPUB
            file_id: ID del archivo en Telegram

        Returns:
            Modelo Book validado o None si falla
        """
        try:
            # Usar EpubsUtils modernizado que retorna Book directamente
            book = self.epub_utils.processing_ebook(file_path, file_id)

            if not book:
                self.logger.error("EpubsUtils no pudo procesar el archivo")
                return None

            # Agregar tamaño de archivo
            file_size = file_path.stat().st_size
            if book.file_info:
                book.file_info.file_size = file_size

            self.logger.info(f"EPUB procesado exitosamente: {book.title}")
            return book

        except Exception as e:
            log_service_error("FileManager", e, {"file_path": str(file_path)})
            self.logger.error(f"Error procesando EPUB: {e}")
            return None

    async def _process_cover(
            self,
            book: Book,
            context: ContextTypes.DEFAULT_TYPE
    ) -> Dict[str, Any]:
        """
        Procesa y sube portada del libro a Telegram.

        Args:
            book: Modelo Book con posible cover_data
            context: Contexto del bot

        Returns:
            Dict con resultado del procesamiento de portada
        """
        # Verificar si hay cover_data temporal
        cover_data = getattr(book, '_cover_data', None)

        if not cover_data:
            return {'success': True, 'message': 'Sin portada disponible'}

        try:
            # Validar tamaño de portada (10MB máximo)
            max_size = 10 * 1024 * 1024
            if len(cover_data) > max_size:
                self.logger.warning("Portada demasiado grande, omitiendo")
                return {'success': True, 'message': 'Portada omitida (muy grande)'}

            # Subir portada a Telegram
            cover_id = await self._upload_cover_to_telegram(cover_data, context)

            if cover_id:
                self.logger.info("Portada procesada exitosamente")
                return {
                    'success': True,
                    'cover_id': cover_id,
                    'message': 'Portada procesada exitosamente'
                }
            else:
                return {
                    'success': True,
                    'message': 'Error subiendo portada, continuando sin ella'
                }

        except Exception as e:
            log_service_error("FileManager", e, {"book_id": book.book_id})
            self.logger.error(f"Error procesando portada: {e}")
            return {
                'success': True,
                'message': 'Error con portada, continuando sin ella'
            }

    async def _upload_cover_to_telegram(
            self,
            cover_data: bytes,
            context: ContextTypes.DEFAULT_TYPE
    ) -> Optional[str]:
        """
        Sube portada a Telegram y retorna file_id.

        Args:
            cover_data: Datos binarios de la imagen
            context: Contexto del bot

        Returns:
            file_id de la imagen o None si falla
        """
        try:
            message = await context.bot.send_photo(
                chat_id=self.config.developer_chat_id,
                photo=cover_data
            )

            # Retornar file_id de la imagen de mejor calidad
            if message.photo:
                cover_id = message.photo[-1].file_id
                self.logger.debug("Portada subida exitosamente")
                return cover_id

            return None

        except Exception as e:
            log_service_error("FileManager", e)
            self.logger.error(f"Error subiendo portada a Telegram: {e}")
            return None

    def _cleanup_temp_file(self, file_path: Path) -> None:
        """Limpia archivo temporal de forma segura."""
        try:
            if file_path and file_path.exists():
                file_path.unlink()
                self.logger.debug(f"Archivo temporal eliminado: {file_path}")
        except Exception as e:
            self.logger.warning(f"Error eliminando archivo temporal {file_path}: {e}")

    def _create_error_result(self, message: str) -> Dict[str, Any]:
        """Crea resultado de error consistente."""
        return {
            'success': False,
            'message': message,
            'book_data': None
        }

    def cleanup_temp_directory(self) -> None:
        """Limpia directorio temporal de archivos antiguos."""
        try:
            if not self.temp_dir.exists():
                return

            cleaned_count = 0
            for file_path in self.temp_dir.iterdir():
                if file_path.is_file():
                    try:
                        file_path.unlink()
                        cleaned_count += 1
                    except Exception as e:
                        self.logger.warning(f"Error eliminando {file_path}: {e}")

            if cleaned_count > 0:
                self.logger.info(f"Limpieza temporal: {cleaned_count} archivos eliminados")

        except Exception as e:
            log_service_error("FileManager", e)
            self.logger.error(f"Error en limpieza de directorio temporal: {e}")

    def get_file_info(self, file_path: Path) -> Dict[str, Any]:
        """Obtiene información detallada de un archivo."""
        try:
            if not file_path.exists():
                return {'exists': False}

            stat = file_path.stat()

            # Usar EpubsUtils para estadísticas específicas de EPUB
            epub_stats = self.epub_utils.get_file_stats(str(file_path))

            return {
                'exists': True,
                'size_bytes': stat.st_size,
                'size_mb': round(stat.st_size / (1024 * 1024), 2),
                'extension': file_path.suffix.lower(),
                'name': file_path.name,
                'is_valid_epub': epub_stats.get('is_valid_epub', False)
            }

        except Exception as e:
            log_service_error("FileManager", e, {"file_path": str(file_path)})
            return {'exists': False, 'error': str(e)}

    def validate_file_size(self, file_path: Path, max_size_mb: int = 50) -> bool:
        """
        Valida que el archivo no exceda el tamaño máximo.

        Args:
            file_path: Ruta al archivo
            max_size_mb: Tamaño máximo en MB

        Returns:
            True si el tamaño es válido
        """
        try:
            file_info = self.get_file_info(file_path)
            if not file_info.get('exists'):
                return False

            return file_info.get('size_mb', 0) <= max_size_mb

        except Exception as e:
            log_service_error("FileManager", e, {"file_path": str(file_path)})
            return False

    def get_temp_directory_stats(self) -> Dict[str, Any]:
        """Obtiene estadísticas del directorio temporal."""
        try:
            if not self.temp_dir.exists():
                return {'exists': False, 'file_count': 0, 'total_size_mb': 0}

            file_count = 0
            total_size = 0

            for file_path in self.temp_dir.iterdir():
                if file_path.is_file():
                    file_count += 1
                    total_size += file_path.stat().st_size

            return {
                'exists': True,
                'file_count': file_count,
                'total_size_mb': round(total_size / (1024 * 1024), 2),
                'directory': str(self.temp_dir)
            }

        except Exception as e:
            log_service_error("FileManager", e)
            return {'exists': False, 'error': str(e)}