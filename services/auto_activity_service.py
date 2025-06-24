"""
Servicio de actividad automática para ZeepubsBot.
Mantiene el chat activo con recomendaciones cada media hora.

Ubicación: services/auto_activity_service.py
"""

import asyncio
import random
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Coroutine, Set
from dataclasses import dataclass

from telegram import Bot
from telegram.constants import ChatAction, ParseMode
from telegram.error import TelegramError

from config.bot_config import get_config, get_logger
from data.book_repository import BookRepository
from utils.error_handler import log_service_error
from services.activity_personality import ActivityPersonality, PersonalityType

from openai import OpenAI


@dataclass
class BookOpinion:
    """Opinión estructurada sobre un libro."""
    book_id: str
    title: str
    author: str
    positive_aspects: List[str]
    concerns: List[str]
    rating: int  # 1-5
    recommendation_reason: str
    target_audience: str
    mood_tags: List[str]
    personality_tone: PersonalityType


class AutoActivityService:
    """Servicio para mantener actividad automática en el chat."""

    def __init__(self, bot: Bot):
        """Inicializa el servicio con cliente IA propio."""
        self.bot = bot
        self.config = get_config()
        self.logger = get_logger(__name__)
        self.book_repository = BookRepository()
        self.personality = ActivityPersonality()

        # Cliente IA propio
        self.ai_client = self._initialize_ai_client()

        # Estado del servicio
        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        self._last_recommendation_time: Optional[datetime] = None

        # Configuración
        self.interval_minutes = 30

        # NUEVO: Lista de chats donde enviar recomendaciones
        self.active_chats: Set[int] = set()  # IDs de chats donde está activo

        # Cache y estadísticas
        self._recently_recommended: List[str] = []
        self._max_recent_cache = 20
        self._daily_recommendations = 0
        self._last_reset_date = datetime.now().date()

        # Personalidad actual
        self._current_personality = PersonalityType.ENTHUSIASTIC

        # *** MENSAJE DE DEBUG PARA VERIFICAR INICIALIZACIÓN ***
        self.logger.info("AutoActivityService inicializado correctamente")

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

            self.logger.info("Cliente de IA para actividad inicializado correctamente")
            return client

        except Exception as e:
            log_service_error("AutoActivityService", e)
            self.logger.error(f"Error inicializando cliente de IA: {e}")
            return None

    async def start_activity_service(self, chat_id: Optional[int] = None) -> bool:
        """Inicia el servicio de actividad automática."""
        try:
            if self._is_running:
                self.logger.warning("Servicio ya está ejecutándose")
                return False

            # Si se proporciona chat_id, agregarlo a la lista activa
            if chat_id:
                self.active_chats.add(chat_id)
                self.logger.info(f"➕ Chat {chat_id} agregado a recomendaciones automáticas")

            # Si no hay chats activos, usar chat del desarrollador como fallback
            if not self.active_chats:
                self.active_chats.add(self.config.developer_chat_id)
                self.logger.info("📱 Usando chat del desarrollador como fallback")

            self._is_running = True
            self._task = asyncio.create_task(self._activity_loop())

            self.logger.info(f"🤖 Servicio iniciado para {len(self.active_chats)} chats")

            # Enviar mensaje de inicio
            await self._send_startup_message()

            return True

        except Exception as e:
            log_service_error("AutoActivityService", e)
            self.logger.error(f"Error iniciando servicio: {e}")
            self._is_running = False
            return False

    def add_chat(self, chat_id: int) -> bool:
        """Agrega un chat a las recomendaciones automáticas."""
        try:
            self.active_chats.add(chat_id)
            self.logger.info(f"➕ Chat {chat_id} agregado a recomendaciones")
            return True
        except Exception as e:
            log_service_error("AutoActivityService", e)
            return False

    def remove_chat(self, chat_id: int) -> bool:
        """Remueve un chat de las recomendaciones automáticas."""
        try:
            if chat_id in self.active_chats:
                self.active_chats.remove(chat_id)
                self.logger.info(f"➖ Chat {chat_id} removido de recomendaciones")
                return True
            return False
        except Exception as e:
            log_service_error("AutoActivityService", e)
            return False

    async def stop_activity_service(self) -> None:
        """Detiene el servicio de actividad automática."""
        try:
            self._is_running = False

            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

            # Mensaje de despedida
            farewell_message = self.personality.get_farewell_message(
                self._daily_recommendations,
                len(self._recently_recommended)
            )
            await self._send_activity_message(farewell_message)

            self.logger.info("🛑 Servicio de actividad automática detenido")

        except Exception as e:
            log_service_error("AutoActivityService", e)
            self.logger.error(f"Error deteniendo servicio: {e}")

    async def _activity_loop(self) -> None:
        """Loop principal del servicio de actividad."""
        try:
            while self._is_running:
                try:
                    # Esperar el intervalo con ligera variación
                    variation = random.randint(-2, 2)
                    sleep_time = max(5, self.interval_minutes + variation) * 60
                    await asyncio.sleep(sleep_time)

                    if not self._is_running:
                        break

                    # Resetear contador diario si es necesario
                    self._reset_daily_counter_if_needed()

                    # Cambiar personalidad ocasionalmente
                    if self.personality.should_change_personality(0.25):
                        self._current_personality = self.personality.get_random_personality()

                    # Generar y enviar recomendación
                    await self._send_automatic_recommendation()

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log_service_error("AutoActivityService", e)
                    self.logger.error(f"Error en loop de actividad: {e}")
                    await asyncio.sleep(300)  # Esperar 5 minutos en caso de error

        except Exception as e:
            log_service_error("AutoActivityService", e)
            self.logger.error(f"Error crítico en loop: {e}")
        finally:
            self._is_running = False

    async def _send_startup_message(self) -> None:
        """Envía mensaje de inicio del servicio."""
        try:
            startup_message = self.personality.get_startup_message()
            await self._send_activity_message(startup_message)

        except Exception as e:
            self.logger.warning(f"Error enviando mensaje de inicio: {e}")

    async def _send_automatic_recommendation(self) -> None:
        """Genera y envía una recomendación automática."""
        try:
            # Seleccionar libro para recomendar
            book = await self._select_book_for_recommendation()

            if not book:
                await self._send_no_books_message()
                return

            # Generar opinión del libro
            opinion = await self._generate_book_opinion(book)

            # Formatear mensaje de recomendación
            message = self._format_recommendation_message(book, opinion)

            # Enviar con portada si está disponible
            if book.cover_id:
                await self._send_recommendation_with_cover(book, message)
            else:
                await self._send_activity_message(message)

            # Actualizar estadísticas
            self._update_recommendation_stats(book.book_id)

            self.logger.info(f"Recomendación automática enviada: {book.title}")

        except Exception as e:
            log_service_error("AutoActivityService", e)
            self.logger.error(f"Error enviando recomendación: {e}")

    async def _select_book_for_recommendation(self) -> Optional[Any]:
        """Selecciona un libro para recomendar evitando repeticiones."""
        try:
            # Obtener todos los libros disponibles
            all_books = self.book_repository.find_all()

            if not all_books:
                return None

            # Filtrar libros ya recomendados recientemente
            available_books = [
                book for book in all_books
                if book.book_id not in self._recently_recommended
            ]

            # Si todos han sido recomendados, limpiar cache parcialmente
            if not available_books:
                # Mantener solo los últimos 10 en lugar de limpiar todo
                self._recently_recommended = self._recently_recommended[-10:]
                available_books = [
                                      book for book in all_books
                                      if book.book_id not in self._recently_recommended
                                  ] or all_books

            # Selección inteligente: 70% aleatorio, 30% popular
            if random.random() < 0.7:
                selected_book = random.choice(available_books)
            else:
                # Usar libros populares
                popular_books = self.book_repository.find_popular(10)
                candidate_books = [
                                      book for book in popular_books
                                      if book.book_id not in self._recently_recommended
                                  ] or popular_books[:3]

                selected_book = random.choice(candidate_books)

            return selected_book

        except Exception as e:
            log_service_error("AutoActivityService", e)
            self.logger.error(f"Error seleccionando libro: {e}")
            return None

    async def _generate_book_opinion(self, book) -> BookOpinion:
        """Genera una opinión personalizada sobre el libro usando IA."""
        try:
            # Si tenemos IA disponible, usar análisis inteligente
            if self.ai_client:
                ai_opinion = await self._generate_ai_opinion(book)
                if ai_opinion:
                    return ai_opinion

            # Fallback: método original sin IA
            return self._generate_fallback_opinion(book)

        except Exception as e:
            log_service_error("AutoActivityService", e)
            self.logger.error(f"Error generando opinión: {e}")
            return self._generate_fallback_opinion(book)

    async def _generate_ai_opinion(self, book) -> Optional[BookOpinion]:
        """Genera opinión usando IA (DeepSeek)."""
        try:
            # Obtener estadísticas del libro
            stats = self.book_repository.get_book_stats(book.book_id)
            downloads = stats.downloads if stats else 0

            # Construir prompt para la IA
            personality_name = {
                PersonalityType.ENTHUSIASTIC: "entusiasta y energética",
                PersonalityType.THOUGHTFUL: "reflexiva y analítica",
                PersonalityType.CASUAL: "relajada y amigable",
                PersonalityType.EXCITED: "súper emocionada y expresiva"
            }.get(self._current_personality, "entusiasta")

            prompt = f"""Eres Neko-chan, bibliotecaria con personalidad {personality_name}.

    Analiza este libro:
    - Título: {book.title}
    - Autor: {book.author}
    - Descripción: {book.description[:200] if book.description else 'Sin descripción'}
    - Descargas: {downloads}

    RESPONDE SOLO CON JSON VÁLIDO (sin texto adicional):
    {{
        "rating": 4,
        "positive_aspects": ["aspecto 1", "aspecto 2"],
        "concerns": ["preocupación 1"],
        "recommendation_reason": "razón breve",
        "target_audience": "tipo de lectores",
        "mood_tags": ["mood1", "mood2"]
    }}"""

            response = self.ai_client.chat.completions.create(
                model="deepseek-chat",
                messages=[
                    {"role": "system", "content": "Responde SOLO con JSON válido, sin explicaciones adicionales."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=300,
                temperature=0.6
            )

            if response and response.choices:
                ai_text = response.choices[0].message.content.strip()

                # Log para debug
                self.logger.debug(f"IA response: {ai_text[:200]}")

                # Limpiar respuesta si tiene texto adicional
                import re
                json_match = re.search(r'\{.*\}', ai_text, re.DOTALL)
                if json_match:
                    ai_text = json_match.group()

                # Parsear respuesta JSON
                import json
                try:
                    ai_data = json.loads(ai_text)

                    # Validar campos requeridos
                    if not all(key in ai_data for key in ['rating', 'positive_aspects', 'recommendation_reason']):
                        self.logger.warning("IA response missing required fields")
                        return None

                    self.logger.info(f"✅ IA analysis successful for: {book.title}")

                    return BookOpinion(
                        book_id=book.book_id,
                        title=book.title,
                        author=book.author,
                        positive_aspects=ai_data.get("positive_aspects", [])[:3],
                        concerns=ai_data.get("concerns", ["Podría no ser para todos"])[:2],
                        rating=max(1, min(5, int(ai_data.get("rating", 3)))),
                        recommendation_reason=ai_data.get("recommendation_reason", "Es una buena lectura"),
                        target_audience=ai_data.get("target_audience", "lectores curiosos"),
                        mood_tags=ai_data.get("mood_tags", ["interesante"])[:3],
                        personality_tone=self._current_personality
                    )

                except json.JSONDecodeError as e:
                    self.logger.warning(f"❌ IA JSON parse error: {e} | Text: {ai_text[:100]}")
                    return None
                except ValueError as e:
                    self.logger.warning(f"❌ IA data validation error: {e}")
                    return None

            return None

        except Exception as e:
            log_service_error("AutoActivityService", e)
            self.logger.warning(f"❌ Error with AI, using fallback: {e}")
            return None

    def _get_book_specific_aspects(self, book, downloads: int, positive: bool) -> List[str]:
        """Genera aspectos específicos basados en características del libro."""
        aspects = []

        if positive:
            if downloads > 10:
                aspects.append("Es muy popular entre nuestros lectores")
            elif downloads > 5:
                aspects.append("Ha ganado una buena audiencia")

            if book.description and len(book.description) > 150:
                aspects.append("Tiene una premisa muy bien desarrollada")

            if book.year and book.year > 2020:
                aspects.append("Es una lectura contemporánea")
        else:
            if book.language != 'es':
                lang_names = {'en': 'inglés', 'fr': 'francés', 'de': 'alemán'}
                lang_name = lang_names.get(book.language, book.language)
                aspects.append(f"Está en {lang_name}, que puede ser desafiante")

            if downloads == 0:
                aspects.append("Aún no lo ha descargado nadie, ¡sé el primero!")

        return aspects

    def _calculate_book_rating(self, book, downloads: int) -> int:
        """Calcula rating del libro basado en factores múltiples."""
        base_rating = 3.0

        # Ajustar por popularidad
        if downloads > 15:
            base_rating += 1.0
        elif downloads > 8:
            base_rating += 0.5
        elif downloads < 2:
            base_rating -= 0.3

        # Ajustar por completitud de metadatos
        if book.description and len(book.description) > 100:
            base_rating += 0.3

        if book.publisher:
            base_rating += 0.2

        # Ajustar por personalidad actual
        personality_adjustments = {
            PersonalityType.ENTHUSIASTIC: 0.3,
            PersonalityType.EXCITED: 0.4,
            PersonalityType.THOUGHTFUL: 0.0,
            PersonalityType.CASUAL: -0.1
        }

        base_rating += personality_adjustments.get(self._current_personality, 0)

        # Asegurar rango 1-5
        return max(1, min(5, round(base_rating)))

    def _generate_mood_tags(self, book) -> List[str]:
        """Genera tags de mood para el libro."""
        moods = []

        # Moods base según tipo de libro
        type_moods = {
            'novel': ['envolvente', 'narrativo'],
            'essay': ['reflexivo', 'intelectual'],
            'manual': ['práctico', 'educativo'],
            'comic': ['visual', 'dinámico']
        }

        if book.type in type_moods:
            moods.extend(type_moods[book.type])

        # Moods generales
        general_moods = ['interesante', 'descubrimiento', 'relajante', 'inspirador']
        moods.extend(random.sample(general_moods, 2))

        # Retornar 2-3 moods únicos
        unique_moods = list(set(moods))
        return random.sample(unique_moods, min(3, len(unique_moods)))

    def _format_recommendation_message(self, book, opinion: BookOpinion) -> str:
        """Formatea el mensaje de recomendación."""
        try:
            # Obtener plantillas según personalidad
            intro = self.personality.get_intro_message(opinion.personality_tone)
            closing = self.personality.get_closing_message(opinion.personality_tone)
            rating_comment = self.personality.get_rating_comment(opinion.personality_tone, opinion.rating)

            # Generar estrellas
            stars = "⭐" * opinion.rating + "☆" * (5 - opinion.rating)

            # Formatear moods con emojis
            mood_emojis = self.personality.get_mood_emojis()
            mood_text = " ".join([
                f"{mood_emojis.get(mood, '📚')}{mood.title()}"
                for mood in opinion.mood_tags
            ])

            message = f"""
{intro}

📖 **{opinion.title}**
✍️ *{opinion.author}*

{stars} **Mi rating:** {opinion.rating}/5
💬 {rating_comment}

✅ **Lo que me gustó:**
{chr(10).join([f"• {aspect}" for aspect in opinion.positive_aspects])}

🤔 **Puntos a considerar:**
{chr(10).join([f"• {concern}" for concern in opinion.concerns])}

💡 **¿Por qué lo recomiendo?**
{opinion.recommendation_reason}

🎯 **Perfecto para:** {opinion.target_audience}
🏷️ **Vibes:** {mood_text}

📥 **Descárgalo:** /{book.book_id}

───────────────────
{closing}
"""

            return message.strip()

        except Exception as e:
            log_service_error("AutoActivityService", e)
            self.logger.error(f"Error formateando mensaje: {e}")

            # Mensaje simple como fallback
            return f"""
🌟 **Recomendación de Neko-chan**

📖 **{book.title}**
✍️ *{book.author}*

✨ {opinion.recommendation_reason}

📥 Descárgalo: /{book.book_id}
"""

    async def _send_recommendation_with_cover(self, book, message: str) -> None:
        """Envía recomendación con portada a todos los chats activos."""
        try:
            if not self.active_chats:
                self.logger.warning("No hay chats activos para enviar portada")
                return

            successful_sends = 0
            failed_sends = 0

            for chat_id in list(self.active_chats):
                try:
                    await self.bot.send_chat_action(
                        chat_id=chat_id,
                        action=ChatAction.UPLOAD_PHOTO
                    )

                    await asyncio.sleep(random.uniform(0.5, 1.5))

                    await self.bot.send_photo(
                        chat_id=chat_id,
                        photo=book.cover_id,
                        caption=message,
                        parse_mode=ParseMode.MARKDOWN
                    )

                    successful_sends += 1

                except Exception as e:
                    failed_sends += 1
                    self.logger.warning(f"Error enviando portada a chat {chat_id}: {e}")

                    # Si falla con portada, intentar sin portada como fallback
                    try:
                        await asyncio.sleep(0.5)
                        await self.bot.send_message(
                            chat_id=chat_id,
                            text=message,
                            parse_mode=ParseMode.MARKDOWN
                        )
                        self.logger.info(f"✅ Enviado sin portada a chat {chat_id}")
                        successful_sends += 1
                        failed_sends -= 1  # Corregir contador ya que al final funcionó
                    except Exception as e2:
                        self.logger.error(f"Error enviando fallback a chat {chat_id}: {e2}")
                        # Si el chat ya no es válido, removerlo
                        if any(error in str(e2).lower() for error in [
                            "chat not found", "bot was blocked", "forbidden"
                        ]):
                            self.active_chats.discard(chat_id)
                            self.logger.info(f"❌ Chat {chat_id} removido (inválido)")

            self.logger.info(f"📸 Envío con portada: {successful_sends} exitosos, {failed_sends} fallos")

        except Exception as e:
            self.logger.error(f"Error general enviando portadas: {e}")
            # Fallback completo: enviar solo texto
            await self._send_activity_message(message)

    async def _send_no_books_message(self) -> None:
        """Envía mensaje cuando no hay libros disponibles."""
        no_books_message = self.personality.get_no_books_message()
        await self._send_activity_message(no_books_message)

    async def _send_activity_message(self, message: str) -> None:
        """Envía mensaje de actividad a todos los chats activos."""
        try:
            if not self.active_chats:
                self.logger.warning("No hay chats activos para enviar mensaje")
                return

            successful_sends = 0
            failed_sends = 0

            self.logger.info(f"📡 Enviando recomendación a {len(self.active_chats)} chats...")

            # Enviar a todos los chats activos
            for chat_id in list(self.active_chats):  # Lista para evitar modificación durante iteración
                try:
                    await self.bot.send_chat_action(
                        chat_id=chat_id,
                        action=ChatAction.TYPING
                    )

                    # Pausa pequeña para rate limiting
                    await asyncio.sleep(random.uniform(0.5, 1.5))

                    await self.bot.send_message(
                        chat_id=chat_id,
                        text=message,
                        parse_mode=ParseMode.MARKDOWN
                    )

                    successful_sends += 1

                except Exception as e:
                    failed_sends += 1
                    self.logger.warning(f"Error enviando a chat {chat_id}: {e}")

                    # Si el chat ya no es válido, removerlo automáticamente
                    if any(error in str(e).lower() for error in [
                        "chat not found", "bot was blocked", "forbidden", "bad request"
                    ]):
                        self.active_chats.discard(chat_id)
                        self.logger.info(f"❌ Chat {chat_id} removido automáticamente (inválido)")

            # Log de resultados
            self.logger.info(f"📊 Envío completado: {successful_sends} exitosos, {failed_sends} fallos")

        except Exception as e:
            log_service_error("AutoActivityService", e)
            self.logger.error(f"Error enviando mensaje de actividad: {e}")

    def _reset_daily_counter_if_needed(self) -> None:
        """Resetea contador diario si cambió el día."""
        today = datetime.now().date()
        if today > self._last_reset_date:
            self._daily_recommendations = 0
            self._last_reset_date = today
            self.logger.info("🔄 Contador diario reseteado")

    def _update_recommendation_stats(self, book_id: str) -> None:
        """Actualiza estadísticas de recomendaciones."""
        # Cache de libros recientes
        self._recently_recommended.append(book_id)
        if len(self._recently_recommended) > self._max_recent_cache:
            self._recently_recommended.pop(0)

        # Estadísticas del libro
        self.book_repository.increment_searches(book_id)

        # Estadísticas del servicio
        self._daily_recommendations += 1
        self._last_recommendation_time = datetime.now()

    # MÉTODOS DE CONTROL

    async def force_recommendation(self) -> bool:
        """Fuerza una recomendación inmediata."""
        try:
            await self._send_automatic_recommendation()
            return True
        except Exception as e:
            log_service_error("AutoActivityService", e)
            return False

    def configure_interval(self, minutes: int) -> bool:
        """Configura el intervalo de recomendaciones."""
        if minutes < 5 or minutes > 1440:  # Entre 5 minutos y 24 horas
            return False

        self.interval_minutes = minutes
        self.logger.info(f"Intervalo actualizado: {minutes} minutos")
        return True

    def get_service_status(self) -> Dict[str, Any]:
        """Retorna estado del servicio."""
        return {
            'is_running': self._is_running,
            'interval_minutes': self.interval_minutes,
            'active_chats': list(self.active_chats),
            'active_chats_count': len(self.active_chats),
            'last_recommendation': self._last_recommendation_time.isoformat() if self._last_recommendation_time else None,
            'recently_recommended_count': len(self._recently_recommended),
            'daily_recommendations': self._daily_recommendations,
            'current_personality': self._current_personality.value,
            'ai_available': bool(self.ai_client),
            'ai_configured': bool(self.config.deepseek_api_key),
            'next_recommendation_eta': self._calculate_next_recommendation_eta()
        }

    def _calculate_next_recommendation_eta(self) -> Optional[str]:
        """Calcula tiempo estimado para próxima recomendación."""
        if not self._last_recommendation_time or not self._is_running:
            return None

        next_time = self._last_recommendation_time + timedelta(minutes=self.interval_minutes)
        now = datetime.now()

        if next_time > now:
            delta = next_time - now
            minutes_left = int(delta.total_seconds() / 60)

            if minutes_left < 60:
                return f"{minutes_left} minutos"
            else:
                hours = minutes_left // 60
                minutes = minutes_left % 60
                return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
        else:
            return "Próximamente"