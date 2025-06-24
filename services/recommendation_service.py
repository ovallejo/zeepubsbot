"""
Servicio completo de recomendaciones con IA para ZeepubsBot.
Incluye streaming, personalidades, y todas las funcionalidades necesarias.

Ubicación: services/recommendation_service.py
"""

import asyncio
from typing import Dict, Any, Optional, List, Tuple

from openai import OpenAI
from telegram import Update
from telegram.constants import ChatAction
from telegram.ext import ContextTypes

from config.bot_config import get_config, get_logger, BotConstants
from data.book_repository import BookRepository
from utils.error_handler import log_service_error
from utils.message_formatter import MessageFormatter


class RecommendationService:
    """Servicio completo para recomendaciones de libros usando IA."""

    def __init__(self, book_service=None):
        """Inicializa el servicio de recomendaciones."""
        self.book_repository = BookRepository()
        self.message_formatter = MessageFormatter()

        self.config = get_config()
        self.logger = get_logger(__name__)

        # Cliente OpenAI para DeepSeek
        self.client = self._initialize_ai_client()

    def _initialize_ai_client(self) -> Optional[OpenAI]:
        """Inicializa cliente de IA con validación."""
        try:
            if not self.config.deepseek_api_key:
                self.logger.warning("API key de DeepSeek no configurada")
                return None

            client = OpenAI(
                api_key=self.config.deepseek_api_key,
                base_url=self.config.deepseek_endpoint,
                timeout=self.config.api_timeout
            )

            self.logger.info("Cliente de IA inicializado correctamente")
            return client

        except Exception as e:
            log_service_error("RecommendationService", e)
            self.logger.error(f"Error inicializando cliente de IA: {e}")
            return None

    async def process_recommendation(
            self,
            user_message: str,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Procesa solicitud de recomendación con streaming."""
        try:
            user_id = update.effective_user.id
            self.logger.info(f"Procesando recomendación para usuario {user_id}")

            # Validar entrada
            if not user_message or not user_message.strip():
                await update.message.reply_text(
                    self.message_formatter.format_error_message('missing_recommendation_query')
                )
                return

            # Verificar disponibilidad del servicio
            if not self._is_service_available():
                await update.message.reply_text(
                    self.message_formatter.format_recommendation_status('unavailable')
                )
                return

            # Enviar indicador de typing
            await context.bot.send_chat_action(
                chat_id=update.effective_chat.id,
                action=ChatAction.TYPING
            )

            # Mensaje temporal de procesamiento
            processing_msg = await context.bot.send_message(
                chat_id=update.message.chat_id,
                text=self.message_formatter.format_recommendation_status('searching'),
                parse_mode="Markdown"
            )

            # Generar recomendación
            await self._generate_streaming_recommendation(
                user_message.strip(), processing_msg, context
            )

        except Exception as e:
            log_service_error("RecommendationService", e, {
                "user_id": update.effective_user.id,
                "message": user_message[:100] if user_message else ""
            })
            self.logger.error(f"Error procesando recomendación: {e}")
            await self._send_error_response(update, context)

    async def _generate_streaming_recommendation(
            self,
            user_message: str,
            processing_msg,
            context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Genera recomendación con streaming de respuesta."""
        try:
            # Construir prompt del sistema con biblioteca actual
            system_prompt = self._build_system_prompt()

            # Sanitizar mensaje del usuario
            sanitized_message = self._sanitize_user_message(user_message)

            # Realizar llamada a la API con streaming
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": sanitized_message}
                ],
                max_tokens=1024,
                temperature=0.7,
                top_p=0.95,
                frequency_penalty=0.5,
                presence_penalty=0.3,
                stream=True
            )

            # Procesar streaming
            await self._handle_streaming_response(response, processing_msg, context)

        except Exception as e:
            log_service_error("RecommendationService", e, {"user_message": user_message})
            self.logger.error(f"Error generando recomendación: {e}")

            # Mostrar mensaje de error
            error_message = self.message_formatter.format_recommendation_status('unavailable')
            await processing_msg.edit_text(error_message, parse_mode="Markdown")

    async def _handle_streaming_response(
            self,
            response,
            processing_msg,
            context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Maneja la respuesta en streaming de la API."""
        buffer = ""
        update_counter = 0
        last_update_length = 0

        try:
            for chunk in response:
                if chunk.choices[0].delta.content:
                    buffer += chunk.choices[0].delta.content
                    update_counter += 1

                    # Actualizar mensaje periódicamente
                    if update_counter % 30 == 0 and len(buffer) > last_update_length + 50:
                        await self._update_streaming_message(
                            processing_msg, buffer, context, show_cursor=True
                        )
                        last_update_length = len(buffer)

            # Mensaje final sin cursor
            final_text = buffer.strip() if buffer.strip() else (
                self.message_formatter.format_recommendation_status('unavailable')
            )

            await processing_msg.edit_text(final_text, parse_mode="Markdown")

        except Exception as e:
            log_service_error("RecommendationService", e)
            self.logger.error(f"Error en streaming: {e}")

            # Mensaje de error en caso de fallo
            error_message = self.message_formatter.format_recommendation_status('unavailable')
            await processing_msg.edit_text(error_message, parse_mode="Markdown")

    async def _update_streaming_message(
            self,
            message,
            content: str,
            context: ContextTypes.DEFAULT_TYPE,
            show_cursor: bool = False
    ) -> None:
        """Actualiza mensaje durante streaming con validación."""
        try:
            # Preparar texto con cursor opcional
            display_text = content.strip()
            if show_cursor:
                display_text += " ▌"

            # Validar longitud
            if not self.message_formatter.validate_message_length(display_text):
                display_text = display_text[:self.config.max_message_length - 10] + "..."

            # Enviar acción de typing
            await context.bot.send_chat_action(
                chat_id=message.chat_id,
                action=ChatAction.TYPING
            )

            # Actualizar mensaje
            await message.edit_text(display_text, parse_mode="Markdown")

            # Pausa breve para evitar rate limiting
            await asyncio.sleep(1)

        except Exception as e:
            # Ignorar errores de edición (mensaje muy similar, etc.)
            self.logger.debug(f"Error actualizando mensaje streaming: {e}")

    def _build_system_prompt(self) -> str:
        """Construye el prompt del sistema con la biblioteca disponible."""
        try:
            # Obtener libros con estadísticas para mejor recomendación
            available_books = self.book_repository.get_books_for_recommendations()

            if not available_books:
                books_list = "No hay libros disponibles actualmente."
            else:
                books_list = self._format_books_for_prompt(available_books)

            # Obtener estadísticas de la biblioteca
            total_books = self.book_repository.count()
            popular_books = self.book_repository.find_popular(5)

            return f"""
¡Hola! Soy Neko-chan, tu asistente literaria virtual 📚✨

Como experta en literatura, mi misión es encontrar el libro perfecto para ti siguiendo estos principios:

🎯 **Mi proceso mágico:**
- Analizo tus gustos y preferencias con cuidado
- Identifico géneros, autores o temas que te emocionan
- Busco en mi biblioteca de {total_books} libros los tesoros perfectos
- Selecciono hasta 8 joyas únicas para máxima variedad
- Incluyo descripciones detalladas de cada recomendación
- Si no tengo exactamente lo que buscas, sugiero alternativas similares

✨ **Mis características especiales:**
- Uso emojis para expresarme mejor 😊
- Siempre incluyo títulos diversos para sorprenderte
- Los comandos mágicos (/<book_id>) están listos para usar
- Mis respuestas son naturales pero precisas
- Considero popularidad y calidad en mis sugerencias

📝 **Formato de respuesta:**
/<book_id> | **Título del libro**
*Descripción breve y atractiva del libro*

📊 **Biblioteca disponible:**
{books_list}

🔥 **Libros más populares actualmente:**
{self._format_popular_books(popular_books)}

💡 **Tip:** Siempre busco ofrecer variedad en géneros, autores y estilos para enriquecer tu experiencia lectora.
"""

        except Exception as e:
            log_service_error("RecommendationService", e)
            return self._get_fallback_prompt()

    def _format_books_for_prompt(self, books: List[Tuple[str, str]]) -> str:
        """Formatea lista de libros para incluir en el prompt."""
        try:
            if not books:
                return "No hay libros disponibles."

            # Limitar a número manejable para el prompt
            max_books = 80
            limited_books = books[:max_books]

            formatted_books = []
            for book_id, title in limited_books:
                if book_id and title:
                    clean_title = title.strip()[:100]  # Limitar longitud
                    formatted_books.append(f"/{book_id} - {clean_title}")

            books_text = "\n".join(formatted_books)

            if len(books) > max_books:
                books_text += f"\n... y {len(books) - max_books} libros más disponibles"

            return books_text

        except Exception as e:
            log_service_error("RecommendationService", e)
            return "Error cargando lista de libros."

    def _format_popular_books(self, popular_books: List) -> str:
        """Formatea libros populares para el prompt."""
        try:
            if not popular_books:
                return "No hay estadísticas de popularidad disponibles."

            popular_list = []
            for book in popular_books[:5]:  # Top 5
                if hasattr(book, 'title') and hasattr(book, 'book_id'):
                    title = book.title[:50]  # Limitar longitud
                    popular_list.append(f"/{book.book_id} - {title}")
                elif len(book) >= 3:  # Tuple format
                    title = book[2][:50]
                    book_id = book[1]
                    popular_list.append(f"/{book_id} - {title}")

            return "\n".join(popular_list) if popular_list else "Sin datos de popularidad."

        except Exception as e:
            self.logger.debug(f"Error formateando libros populares: {e}")
            return "Estadísticas no disponibles."

    def _get_fallback_prompt(self) -> str:
        """Retorna prompt de respaldo en caso de error."""
        return """
Soy Neko-chan, tu asistente literaria mágica 🔮

Aunque tengo dificultades accediendo a mi biblioteca completa en este momento, 
haré mi mejor esfuerzo para recomendarte libros basándome en tus preferencias.

Por favor, descríbeme qué tipo de historia te gustaría leer y te ayudaré con 
sugerencias generales y consejos de búsqueda.

✨ Recuerda que puedes usar /list para ver todos los libros disponibles.
"""

    async def _send_error_response(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Envía respuesta de error al usuario."""
        try:
            error_message = self.message_formatter.format_error_message(
                'processing_error',
                "El servicio de recomendaciones no está disponible"
            )

            await update.message.reply_text(error_message, parse_mode="Markdown")

        except Exception as e:
            log_service_error("RecommendationService", e)

    def _sanitize_user_message(self, message: str) -> str:
        """Sanitiza mensaje del usuario para evitar inyección de prompts."""
        if not message:
            return ""

        try:
            # Limpiar caracteres problemáticos
            sanitized = message.replace('\n', ' ').replace('\r', ' ')

            # Normalizar espacios
            sanitized = ' '.join(sanitized.split())

            # Limitar longitud
            max_length = 400
            if len(sanitized) > max_length:
                sanitized = sanitized[:max_length] + "..."

            return sanitized.strip()

        except Exception as e:
            log_service_error("RecommendationService", e)
            return str(message)[:400]

    def _is_service_available(self) -> bool:
        """Verifica si el servicio de recomendaciones está disponible."""
        try:
            # Verificar cliente de IA
            if not self.client:
                return False

            # Verificar que hay libros disponibles
            book_count = self.book_repository.count()
            if book_count == 0:
                return False

            return True

        except Exception as e:
            log_service_error("RecommendationService", e)
            return False

    async def get_quick_recommendation(self, genre: str) -> Optional[str]:
        """Genera recomendación rápida sin streaming para un género específico."""
        try:
            if not self._is_service_available():
                return None

            prompt = f"Recomienda brevemente 2-3 libros del género {genre} de nuestra biblioteca."
            system_prompt = self._build_system_prompt()

            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.6
            )

            if response and response.choices:
                return response.choices[0].message.content.strip()

            return None

        except Exception as e:
            log_service_error("RecommendationService", e, {"genre": genre})
            return None

    async def test_api_connection(self) -> bool:
        """Prueba la conexión con la API de DeepSeek."""
        try:
            if not self.client:
                return False

            # Realizar una llamada simple de prueba
            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[{"role": "user", "content": "Test connection"}],
                max_tokens=10,
                temperature=0.1
            )

            return bool(response and response.choices)

        except Exception as e:
            log_service_error("RecommendationService", e)
            return False

    def get_service_status(self) -> Dict[str, Any]:
        """Retorna estado completo del servicio de recomendaciones."""
        try:
            book_count = self.book_repository.count()
            popular_count = len(self.book_repository.find_popular(10))

            return {
                'api_configured': bool(self.client),
                'api_key_present': bool(self.config.deepseek_api_key),
                'books_available': book_count,
                'popular_books_count': popular_count,
                'service_ready': self._is_service_available(),
                'endpoint': self.config.deepseek_endpoint,
                'timeout': self.config.api_timeout
            }

        except Exception as e:
            log_service_error("RecommendationService", e)
            return {
                'api_configured': False,
                'service_ready': False,
                'error': str(e)
            }

    def validate_api_configuration(self) -> List[str]:
        """Valida configuración de la API y retorna lista de errores."""
        errors = []

        try:
            if not self.config.deepseek_api_key:
                errors.append("API key de DeepSeek no configurada")

            if not self.config.deepseek_endpoint:
                errors.append("Endpoint de DeepSeek no configurado")

            if self.config.api_timeout <= 0:
                errors.append("Timeout de API debe ser mayor a 0")

            if not self.client:
                errors.append("Cliente de IA no se pudo inicializar")

            book_count = self.book_repository.count()
            if book_count == 0:
                errors.append("No hay libros disponibles para recomendaciones")

        except Exception as e:
            errors.append(f"Error validando configuración: {str(e)}")

        return errors

    async def generate_book_analysis(self, book_id: str) -> Optional[str]:
        """Genera análisis específico de un libro usando IA."""
        try:
            if not self._is_service_available():
                return None

            # Obtener datos del libro
            book = self.book_repository.find_by_book_id(book_id)
            if not book:
                return None

            # Crear prompt para análisis específico
            analysis_prompt = f"""
Analiza este libro específico como Neko-chan:

📖 **LIBRO:**
• Título: {book.title}
• Autor: {book.author}
• Descripción: {book.description[:300] if book.description else 'Sin descripción'}

Dame tu análisis personal como bibliotecaria experta, incluyendo:
- Por qué te gusta o no te gusta
- Para qué tipo de lectores es ideal
- Qué lo hace especial
- Rating del 1-5 con justificación

Sé natural y personal en tu respuesta.
"""

            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Eres Neko-chan, bibliotecaria experta que analiza libros de forma personal y auténtica."},
                    {"role": "user", "content": analysis_prompt}
                ],
                max_tokens=500,
                temperature=0.7
            )

            if response and response.choices:
                return response.choices[0].message.content.strip()

            return None

        except Exception as e:
            log_service_error("RecommendationService", e, {"book_id": book_id})
            return None

    async def get_recommendation_by_mood(self, mood: str, limit: int = 3) -> Optional[str]:
        """Genera recomendaciones basadas en estado de ánimo."""
        try:
            if not self._is_service_available():
                return None

            mood_prompt = f"""
El usuario está en mood "{mood}". Recomienda {limit} libros perfectos para este estado de ánimo.

Considera libros que:
- Complementen o mejoren su mood actual
- Sean apropiados para lo que siente
- Le den exactamente lo que necesita ahora

Sé empática y considera cómo cada libro puede ayudar o acompañar su estado emocional.
"""

            system_prompt = self._build_system_prompt()

            response = self.client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": mood_prompt}
                ],
                max_tokens=600,
                temperature=0.8
            )

            if response and response.choices:
                return response.choices[0].message.content.strip()

            return None

        except Exception as e:
            log_service_error("RecommendationService", e, {"mood": mood})
            return None

    def get_recommendation_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas del servicio de recomendaciones."""
        try:
            return {
                'total_books': self.book_repository.count(),
                'popular_books': len(self.book_repository.find_popular(20)),
                'api_available': bool(self.client),
                'service_healthy': self._is_service_available(),
                'last_api_test': None  # Se podría implementar cache de test
            }

        except Exception as e:
            log_service_error("RecommendationService", e)
            return {
                'total_books': 0,
                'api_available': False,
                'service_healthy': False,
                'error': str(e)
            }