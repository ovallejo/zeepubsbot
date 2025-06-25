"""
Servicio completo de recomendaciones con IA para ZeepubsBot.
Incluye streaming, personalidades, y todas las funcionalidades necesarias.

Ubicación: services/recommendation_service.py
"""

import asyncio
import time
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
        """Procesa solicitud de recomendación con streaming mejorado."""
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

            # *** PAUSA INICIAL para evitar flood desde el inicio ***
            await asyncio.sleep(1.5)

            # Generar recomendación con streaming controlado
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
        """Maneja la respuesta en streaming con control de flood mejorado."""
        buffer = ""
        update_counter = 0
        last_update_time = time.time()
        last_significant_length = 0

        # Control de flood más inteligente
        MIN_UPDATE_INTERVAL = 3.0  # Mínimo 3 segundos entre actualizaciones
        MIN_CONTENT_CHANGE = 100  # Mínimo 100 caracteres de cambio
        MAX_UPDATES_PER_RESPONSE = 8  # Máximo 8 actualizaciones por respuesta
        total_updates = 0

        try:
            for chunk in response:
                if chunk.choices[0].delta.content:
                    buffer += chunk.choices[0].delta.content
                    update_counter += 1

                    current_time = time.time()
                    time_since_last_update = current_time - last_update_time
                    content_change = len(buffer) - last_significant_length

                    # Condiciones para actualizar (TODAS deben cumplirse):
                    should_update = (
                            total_updates < MAX_UPDATES_PER_RESPONSE and
                            time_since_last_update >= MIN_UPDATE_INTERVAL and
                            content_change >= MIN_CONTENT_CHANGE and
                            update_counter % 50 == 0  # Cada 50 chunks (no 30)
                    )

                    if should_update:
                        try:
                            await self._update_streaming_message_safe(
                                processing_msg, buffer, context, show_cursor=True
                            )
                            last_update_time = current_time
                            last_significant_length = len(buffer)
                            total_updates += 1

                            # Log para debug
                            self.logger.debug(f"Streaming update #{total_updates}: {len(buffer)} chars")

                        except Exception as e:
                            # Si hay error, aumentar el intervalo para la próxima vez
                            if "flood" in str(e).lower() or "429" in str(e):
                                MIN_UPDATE_INTERVAL = min(MIN_UPDATE_INTERVAL * 1.5, 10.0)
                                self.logger.warning(f"Flood detectado, aumentando intervalo a {MIN_UPDATE_INTERVAL}s")
                            else:
                                self.logger.debug(f"Error en streaming update: {e}")

            # Mensaje final sin cursor - SIEMPRE enviar
            final_text = buffer.strip() if buffer.strip() else (
                self.message_formatter.format_recommendation_status('unavailable')
            )

            # Esperar un poco antes del mensaje final si acabamos de actualizar
            if total_updates > 0:
                await asyncio.sleep(2.0)

            await processing_msg.edit_text(final_text, parse_mode="Markdown")
            self.logger.info(f"✅ Streaming completado: {len(final_text)} chars, {total_updates} actualizaciones")

        except Exception as e:
            log_service_error("RecommendationService", e)
            self.logger.error(f"Error en streaming: {e}")

            # Mensaje de error en caso de fallo - SIN editar si acabamos de tener flood
            if "flood" not in str(e).lower() and "429" not in str(e):
                try:
                    error_message = self.message_formatter.format_recommendation_status('unavailable')
                    await processing_msg.edit_text(error_message, parse_mode="Markdown")
                except:
                    pass  # Si falla, no hacer nada más

    async def _update_streaming_message_safe(
            self,
            message,
            content: str,
            context: ContextTypes.DEFAULT_TYPE,
            show_cursor: bool = False
    ) -> None:
        """Actualiza mensaje durante streaming con protección contra flood."""
        try:
            # Preparar texto con cursor opcional
            display_text = content.strip()
            if show_cursor:
                display_text += " ▌"

            # Validar longitud - IMPORTANTE: usar límite más conservador
            max_length = min(self.config.max_message_length - 200, 3800)  # Margen de seguridad
            if len(display_text) > max_length:
                # Truncar de forma inteligente
                truncated = display_text[:max_length - 50]
                # Buscar último punto o espacio para cortar mejor
                last_period = truncated.rfind('.')
                last_space = truncated.rfind(' ')

                if last_period > max_length * 0.8:
                    display_text = display_text[:last_period + 1] + "..."
                elif last_space > max_length * 0.8:
                    display_text = display_text[:last_space] + "..."
                else:
                    display_text = truncated + "..."

            # NO enviar acción de typing para evitar requests adicionales
            # Directamente editar el mensaje
            await message.edit_text(display_text, parse_mode="Markdown")

        except Exception as e:
            # Si es flood control, propagarlo para manejo superior
            if "flood" in str(e).lower() or "429" in str(e) or "Too Many Requests" in str(e):
                raise e
            else:
                # Otros errores se ignoran silenciosamente
                self.logger.debug(f"Error actualizando mensaje streaming (ignorado): {e}")

    def _calculate_safe_update_interval(self, error_count: int = 0) -> float:
        """Calcula intervalo seguro entre actualizaciones basado en errores previos."""
        base_interval = 3.0  # Base de 3 segundos

        # Aumentar exponencialmente si ha habido errores de flood
        if error_count > 0:
            multiplier = min(2 ** error_count, 8)  # Máximo 8x
            return base_interval * multiplier

        return base_interval

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
        """Construye el prompt del sistema con la biblioteca organizada."""
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

    {books_list}

    🔥 **Libros más populares actualmente:**
    {self._format_popular_books(popular_books)}

    💡 **Tip:** Siempre busco ofrecer variedad en géneros, autores y estilos para enriquecer tu experiencia lectora.
    """

        except Exception as e:
            log_service_error("RecommendationService", e)
            return self._get_fallback_prompt()

    def get_library_statistics(self) -> Dict[str, Any]:
        """Obtiene estadísticas detalladas de la biblioteca para debugging."""
        try:
            available_books = self.book_repository.get_books_for_recommendations()

            series_count = {}
            standalone_count = 0

            for book_id, title in available_books:
                if any(indicator in title for indicator in [" - Vol.", " - Parte", " - Volume", " - Tomo"]):
                    series_name = title
                    for separator in [" - Vol.", " - Parte", " - Volume", " - Tomo"]:
                        if separator in series_name:
                            series_name = series_name.split(separator)[0].strip()
                            break

                    if series_name not in series_count:
                        series_count[series_name] = 0
                    series_count[series_name] += 1
                else:
                    standalone_count += 1

            return {
                'total_books': len(available_books),
                'total_series': len(series_count),
                'total_volumes': sum(series_count.values()),
                'standalone_books': standalone_count,
                'largest_series': max(series_count.items(), key=lambda x: x[1]) if series_count else None,
                'series_breakdown': dict(sorted(series_count.items(), key=lambda x: x[1], reverse=True)[:10])
            }

        except Exception as e:
            log_service_error("RecommendationService", e)
            return {'error': str(e)}

    def _format_books_for_prompt(self, books: List[Tuple[str, str]]) -> str:
        """Formatea lista de libros organizados por categorías para mejor comprensión de la IA."""
        try:
            if not books:
                return "No hay libros disponibles."

            # Organizar por series y libros individuales
            series_books = {}
            standalone_books = []

            for book_id, title in books:
                if book_id and title:
                    clean_title = title.strip()[:100]

                    # Detectar si es parte de una serie
                    if any(indicator in clean_title for indicator in [
                        " - Vol.", " - Parte", " - Volume", " - Tomo", " - Capítulo",
                        "Vol. ", "Parte ", "Volume ", "Tomo "
                    ]):
                        # Extraer nombre base de la serie
                        series_name = clean_title
                        for separator in [" - Vol.", " - Parte", " - Volume", " - Tomo"]:
                            if separator in series_name:
                                series_name = series_name.split(separator)[0]
                                break

                        # Limpiar nombre de la serie
                        series_name = series_name.strip()

                        if series_name not in series_books:
                            series_books[series_name] = []
                        series_books[series_name].append(f"/{book_id} - {clean_title}")
                    else:
                        standalone_books.append(f"/{book_id} - {clean_title}")

            # Construir texto organizado
            formatted_sections = []

            # Sección de series (ordenadas alfabéticamente)
            if series_books:
                formatted_sections.append("🔗 **SERIES DISPONIBLES:**")

                # Ordenar series por nombre
                sorted_series = sorted(series_books.items())

                for series_name, volumes in sorted_series:
                    # Ordenar volúmenes de la serie
                    volumes_sorted = sorted(volumes)

                    series_section = f"\n📖 **{series_name}:**"

                    # Mostrar hasta 12 volúmenes por serie para no saturar
                    max_volumes = 12
                    if len(volumes_sorted) <= max_volumes:
                        series_section += "\n" + "\n".join(volumes_sorted)
                    else:
                        series_section += "\n" + "\n".join(volumes_sorted[:max_volumes])
                        series_section += f"\n... y {len(volumes_sorted) - max_volumes} volúmenes más de esta serie"

                    formatted_sections.append(series_section)

            # Sección de libros individuales (ordenados alfabéticamente)
            if standalone_books:
                formatted_sections.append("\n📚 **LIBROS INDIVIDUALES:**")

                # Ordenar alfabéticamente
                standalone_sorted = sorted(standalone_books)

                # Mostrar hasta 80 libros individuales
                max_standalone = 80
                if len(standalone_sorted) <= max_standalone:
                    formatted_sections.append("\n".join(standalone_sorted))
                else:
                    formatted_sections.append("\n".join(standalone_sorted[:max_standalone]))
                    formatted_sections.append(
                        f"... y {len(standalone_sorted) - max_standalone} libros individuales más")

            # Estadísticas finales
            total_series = len(series_books)
            total_volumes = sum(len(volumes) for volumes in series_books.values())
            total_standalone = len(standalone_books)
            total_books = total_volumes + total_standalone

            stats_section = f"""
    📊 **RESUMEN DE BIBLIOTECA:**
    • {total_series} series con {total_volumes} volúmenes
    • {total_standalone} libros individuales
    • **TOTAL: {total_books} libros disponibles**"""

            formatted_sections.append(stats_section)

            return "\n".join(formatted_sections)

        except Exception as e:
            log_service_error("RecommendationService", e)
            self.logger.error(f"Error organizando biblioteca: {e}")
            return f"Error organizando biblioteca. Total de libros: {len(books)}"

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