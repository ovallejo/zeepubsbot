# services/auto_activity_service.py - VERSIÓN COMPLETA Y MEJORADA

"""
Servicio completo de actividad automática para ZeepubsBot.
Mantiene el chat activo con recomendaciones personalizadas cada media hora.
Incluye personalidad, variedad de mensajes y configuración avanzada.
"""

import asyncio
import random
from datetime import datetime, timedelta, time
from typing import Dict, Any, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

from telegram import Bot
from telegram.constants import ChatAction, ParseMode
from telegram.error import TelegramError

from config.bot_config import get_config, get_logger
from data.book_repository import BookRepository
from utils.error_handler import log_service_error
from utils.message_formatter import MessageFormatter


class ActivityMode(Enum):
    """Modos de actividad del servicio."""
    NORMAL = "normal"  # Recomendaciones regulares
    DISCOVERY = "discovery"  # Enfoque en libros menos conocidos
    POPULAR = "popular"  # Enfoque en libros populares
    VARIED = "varied"  # Mezcla de todo


@dataclass
class BookOpinion:
    """Estructura mejorada para opiniones sobre libros."""
    book_id: str
    title: str
    author: str
    positive_aspects: List[str]
    concerns: List[str]
    rating: int  # 1-5
    recommendation_reason: str
    target_audience: str
    mood_tags: List[str]
    personality_tone: str  # enthusiastic, thoughtful, casual
    special_note: Optional[str] = None


class EnhancedAutoActivityService:
    """Servicio mejorado para mantener actividad automática en el chat."""

    def __init__(self, bot: Bot):
        """Inicializa el servicio con configuración avanzada."""
        self.bot = bot
        self.config = get_config()
        self.logger = get_logger(__name__)
        self.book_repository = BookRepository()
        self.message_formatter = MessageFormatter()

        # Estado del servicio
        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        self._last_recommendation_time: Optional[datetime] = None

        # Configuración base
        self.interval_minutes = 30
        self.target_chat_id = self.config.developer_chat_id

        # Configuración avanzada
        self.activity_mode = ActivityMode.VARIED
        self.respect_quiet_hours = False
        self.quiet_hours = (23, 7)  # 11 PM a 7 AM

        # Cache y estadísticas
        self._recently_recommended: List[str] = []
        self._max_recent_cache = 25
        self._daily_recommendations = 0
        self._last_reset_date = datetime.now().date()

        # Personalidad y variedad
        self._personality_states = ['enthusiastic', 'thoughtful', 'casual', 'excited']
        self._current_personality = 'enthusiastic'
        self._message_templates = self._load_message_templates()

    def _load_message_templates(self) -> Dict[str, List[str]]:
        """Carga plantillas de mensajes para variedad."""
        return {
            'intro_enthusiastic': [
                "🌟 **¡Neko-chan con una recomendación especial!** 🌟",
                "✨ **¡Hora de una nueva joya literaria!** ✨",
                "🎉 **¡Tengo el libro perfecto para compartir!** 🎉",
                "📚 **¡Nueva recomendación de tu bibliotecaria favorita!** 📚"
            ],
            'intro_thoughtful': [
                "🤔 **Reflexionando sobre mi próxima recomendación...** 🤔",
                "💭 **He estado pensando en este libro...** 💭",
                "📖 **Déjame compartir una reflexión literaria...** 📖",
                "🧐 **Análisis literario de Neko-chan...** 🧐"
            ],
            'intro_casual': [
                "😊 **¡Hola! ¿Qué tal otra recomendación?** 😊",
                "📚 **Oye, este libro me llamó la atención...** 📚",
                "✨ **¡Quick recommendation time!** ✨",
                "🎯 **Libro del día cortesía de Neko-chan...** 🎯"
            ],
            'closing_enthusiastic': [
                "¡Espero que lo ames tanto como yo! 💖",
                "¡No puedo esperar a que me cuentes qué te pareció! 🤗",
                "¡Seguro que será una experiencia increíble! ✨",
                "¡Disfrútalo mucho y cuéntame todo! 😍"
            ],
            'closing_thoughtful': [
                "Me encantaría conocer tu perspectiva cuando lo termines. 🤔",
                "Será interesante ver si coincidimos en nuestras impresiones. 💭",
                "Espero que encuentres en él lo mismo que yo vi. 📚",
                "Tu opinión siempre enriquece mi comprensión de los libros. 🧠"
            ],
            'transitions': [
                "Mientras tanto, en nuestra biblioteca...",
                "Cambiando de tema literario...",
                "En otras noticias bookish...",
                "Y ahora, para algo completamente diferente...",
                "Siguiente parada: ¡otro gran libro!",
                "Plot twist: ¡más recomendaciones!"
            ]
        }

    async def start_activity_service(self) -> bool:
        """Inicia el servicio con mensaje personalizado."""
        try:
            if self._is_running:
                self.logger.warning("Servicio ya está ejecutándose")
                return False

            self._is_running = True
            self._task = asyncio.create_task(self._enhanced_activity_loop())

            self.logger.info("🤖 Servicio de actividad automática iniciado")

            # Mensaje de inicio más personalizado
            await self._send_enhanced_startup_message()

            return True

        except Exception as e:
            log_service_error("EnhancedAutoActivityService", e)
            self._is_running = False
            return False

    async def _enhanced_activity_loop(self) -> None:
        """Loop mejorado con gestión inteligente de tiempo."""
        try:
            while self._is_running:
                try:
                    # Verificar si es hora silenciosa
                    if self._is_quiet_time():
                        await asyncio.sleep(300)  # Revisar cada 5 minutos
                        continue

                    # Resetear contador diario si es necesario
                    self._reset_daily_counter_if_needed()

                    # Esperar intervalo con variación aleatoria (±5 minutos)
                    variation = random.randint(-5, 5)
                    sleep_time = max(5, self.interval_minutes + variation) * 60
                    await asyncio.sleep(sleep_time)

                    if not self._is_running:
                        break

                    # Cambiar personalidad ocasionalmente
                    if random.random() < 0.3:  # 30% chance
                        self._current_personality = random.choice(self._personality_states)

                    # Enviar recomendación mejorada
                    await self._send_enhanced_recommendation()

                except asyncio.CancelledError:
                    break
                except Exception as e:
                    log_service_error("EnhancedAutoActivityService", e)
                    await asyncio.sleep(300)  # Wait 5 minutes on error

        except Exception as e:
            log_service_error("EnhancedAutoActivityService", e)
        finally:
            self._is_running = False

    def _is_quiet_time(self) -> bool:
        """Verifica si estamos en horario silencioso."""
        if not self.respect_quiet_hours:
            return False

        now = datetime.now().time()
        quiet_start = time(self.quiet_hours[0])
        quiet_end = time(self.quiet_hours[1])

        if quiet_start > quiet_end:  # Cruza medianoche
            return now >= quiet_start or now <= quiet_end
        else:
            return quiet_start <= now <= quiet_end

    def _reset_daily_counter_if_needed(self) -> None:
        """Resetea contador diario si cambió el día."""
        today = datetime.now().date()
        if today > self._last_reset_date:
            self._daily_recommendations = 0
            self._last_reset_date = today
            self.logger.info("🔄 Contador diario de recomendaciones reseteado")

    async def _send_enhanced_startup_message(self) -> None:
        """Envía mensaje de inicio mejorado y personalizado."""
        try:
            startup_messages = [
                """
🤖 **¡Neko-chan despertó con energía renovada!** ✨

¡Hola! He activado mi sistema de recomendaciones automáticas con nuevas mejoras:

🎯 **Características especiales:**
• Recomendaciones cada 30 minutos (con pequeñas variaciones)
• Opiniones personales detalladas sobre cada libro
• Diferentes personalidades y tonos para mantener la variedad
• Selección inteligente evitando repeticiones recientes

📚 **Mi promesa:** Mantener nuestra conversación literaria siempre viva y emocionante.

💫 *¿Listos para descubrir juntos los tesoros de nuestra biblioteca?*
""",
                """
🌟 **¡Sistema de recomendaciones Neko-chan 2.0 activado!** 🌟

¡Bienvenidos a una experiencia literaria mejorada!

✨ **Qué pueden esperar:**
• Recomendaciones automáticas cada media hora
• Mi análisis personal honesto de cada libro
• Variedad en estilos y personalidades
• Enfoque en mantener nuestra charla activa y divertida

🎲 **Modo actual:** Variado (mezclo de todo tipo de libros)

📖 *¡Prepárense para una aventura literaria continua!*
"""
            ]

            message = random.choice(startup_messages)
            await self._send_activity_message(message)

        except Exception as e:
            self.logger.warning(f"Error enviando mensaje de inicio: {e}")

    async def _send_enhanced_recommendation(self) -> None:
        """Envía recomendación mejorada con personalidad."""
        try:
            # Seleccionar libro según modo de actividad
            book = await self._intelligent_book_selection()

            if not book:
                await self._send_enhanced_no_books_message()
                return

            # Generar opinión con personalidad actual
            opinion = await self._generate_enhanced_opinion(book)

            # Formatear mensaje con plantillas
            message = self._format_enhanced_message(book, opinion)

            # Enviar con efectos visuales
            await self._send_with_visual_effects(book, message)

            # Actualizar estadísticas
            self._update_recommendation_stats(book.book_id)

            self.logger.info(f"Recomendación mejorada enviada: {book.title} (modo: {self._current_personality})")

        except Exception as e:
            log_service_error("EnhancedAutoActivityService", e)

    async def _intelligent_book_selection(self) -> Optional[Any]:
        """Selección inteligente basada en el modo de actividad."""
        try:
            all_books = self.book_repository.find_all()
            if not all_books:
                return None

            # Filtrar libros recientes
            available_books = [
                book for book in all_books
                if book.book_id not in self._recently_recommended
            ]

            if not available_books:
                # Limpiar cache parcialmente en lugar de completamente
                self._recently_recommended = self._recently_recommended[-10:]
                available_books = all_books

            # Selección según modo de actividad
            if self.activity_mode == ActivityMode.POPULAR:
                candidate_books = self.book_repository.find_popular(15)
                available_candidates = [
                                           book for book in candidate_books
                                           if book.book_id not in self._recently_recommended
                                       ] or candidate_books[:5]

            elif self.activity_mode == ActivityMode.DISCOVERY:
                # Libros con menos descargas
                all_with_stats = []
                for book in available_books:
                    stats = self.book_repository.get_book_stats(book.book_id)
                    downloads = stats.downloads if stats else 0
                    all_with_stats.append((book, downloads))

                # Ordenar por menos descargas
                all_with_stats.sort(key=lambda x: x[1])
                available_candidates = [book for book, _ in all_with_stats[:20]]

            else:  # NORMAL o VARIED
                # Mezcla inteligente: 60% aleatorio, 40% popular
                if random.random() < 0.6:
                    available_candidates = available_books
                else:
                    popular_books = self.book_repository.find_popular(10)
                    available_candidates = [
                                               book for book in popular_books
                                               if book.book_id not in self._recently_recommended
                                           ] or popular_books[:3]

            return random.choice(available_candidates)

        except Exception as e:
            log_service_error("EnhancedAutoActivityService", e)
            return None

    async def _generate_enhanced_opinion(self, book) -> BookOpinion:
        """Genera opinión mejorada con personalidad dinámica."""
        try:
            stats = self.book_repository.get_book_stats(book.book_id)
            downloads = stats.downloads if stats else 0

            # Generar componentes con personalidad
            positive_aspects = self._generate_personality_aspects(book, downloads, positive=True)
            concerns = self._generate_personality_aspects(book, downloads, positive=False)

            # Rating con ligera variación aleatoria para naturalidad
            base_rating = self._calculate_dynamic_rating(book, downloads)
            rating = max(1, min(5, base_rating + random.choice([-1, 0, 0, 1])))

            # Generar elementos según personalidad actual
            recommendation_reason = self._generate_personality_reason(book, rating)
            target_audience = self._generate_smart_audience(book)
            mood_tags = self._generate_contextual_moods(book)
            special_note = self._generate_special_note(book, downloads)

            return BookOpinion(
                book_id=book.book_id,
                title=book.title,
                author=book.author,
                positive_aspects=positive_aspects,
                concerns=concerns,
                rating=rating,
                recommendation_reason=recommendation_reason,
                target_audience=target_audience,
                mood_tags=mood_tags,
                personality_tone=self._current_personality,
                special_note=special_note
            )

        except Exception as e:
            log_service_error("EnhancedAutoActivityService", e)
            # Opinión simple como fallback
            return BookOpinion(
                book_id=book.book_id,
                title=book.title,
                author=book.author,
                positive_aspects=["Me parece una lectura interesante"],
                concerns=["Podría no ser para todos"],
                rating=3,
                recommendation_reason="Es una buena opción para explorar",
                target_audience="lectores curiosos",
                mood_tags=["exploración"],
                personality_tone="casual"
            )

    def _generate_personality_aspects(self, book, downloads: int, positive: bool) -> List[str]:
        """Genera aspectos positivos o negativos según personalidad."""
        if positive:
            base_aspects = {
                'enthusiastic': [
                    f"¡Me fascina completamente el estilo de {book.author}!",
                    "¡La premisa me tiene súper emocionada!",
                    "¡Es exactamente el tipo de historia que amo!",
                    f"¡{book.title} promete ser una experiencia increíble!"
                ],
                'thoughtful': [
                    f"La propuesta narrativa de {book.author} es muy sólida",
                    "Me parece una exploración profunda del tema",
                    "La estructura del libro está muy bien pensada",
                    "Ofrece perspectivas realmente valiosas"
                ],
                'casual': [
                    "Tiene buena pinta, la verdad",
                    f"Me gusta cómo escribe {book.author}",
                    "Es del tipo de libros que disfruto",
                    "Se ve como una lectura entretenida"
                ]
            }
        else:
            base_aspects = {
                'enthusiastic': [
                    "¡Aunque podría ser un poquito intenso para algunos!",
                    "¡Requiere estar en el mood perfecto para disfrutarlo!",
                    "¡Definitivamente no es una lectura ligera!"
                ],
                'thoughtful': [
                    "Requiere cierta preparación mental para apreciarlo",
                    "El ritmo podría no ser ideal para todos los momentos",
                    "Es importante tener expectativas realistas"
                ],
                'casual': [
                    "No es para todos los gustos, eso sí",
                    "Mejor leerlo cuando tengas tiempo",
                    "Podría ser un poco lento al principio"
                ]
            }

        personality_aspects = base_aspects.get(self._current_personality, base_aspects['casual'])

        # Agregar aspectos específicos según características del libro
        if positive:
            if downloads > 10:
                personality_aspects.append("Es súper popular entre nuestros lectores")
            if book.description and len(book.description) > 150:
                personality_aspects.append("La sinopsis me convenció totalmente")
        else:
            if book.language != 'es':
                personality_aspects.append("Está en otro idioma, que puede ser desafiante")

        # Seleccionar 2-3 aspectos
        return random.sample(personality_aspects, min(3, len(personality_aspects)))

    def _generate_personality_reason(self, book, rating: int) -> str:
        """Genera razón de recomendación según personalidad."""
        reasons = {
            'enthusiastic': {
                5: ["¡Es absolutamente PERFECTO y tienes que leerlo YA!",
                    "¡No puedo contener mi emoción por este libro!", "¡Es una obra maestra que cambiará tu vida!"],
                4: ["¡Me encanta y estoy segura de que a ti también!",
                    "¡Es súper bueno y lo recomiendo con los ojos cerrados!",
                    "¡Definitivamente vale cada minuto que inviertas!"],
                3: ["¡Es una lectura sólida que merece una oportunidad!", "¡Me gustó y creo que podría sorprenderte!",
                    "¡Es perfecto para cuando buscas algo confiable!"],
                2: ["Es interesante, aunque con sus peculiaridades", "Podría gustarte si estás en mood experimental"],
                1: ["Es... una experiencia única, eso seguro"]
            },
            'thoughtful': {
                5: ["Representa una contribución significativa a la literatura",
                    "Es una lectura que enriquece profundamente", "Ofrece una experiencia reflexiva excepcional"],
                4: ["Es una obra sólida que vale la pena considerar", "Presenta ideas valiosas de manera efectiva",
                    "Me parece una lectura muy recomendable"],
                3: ["Es una opción razonable para explorar", "Tiene méritos que justifican su lectura",
                    "Puede aportar perspectivas interesantes"],
                2: ["Es una experiencia literaria particular", "Podría ser valioso para ciertos lectores"],
                1: ["Es una propuesta experimental interesante"]
            },
            'casual': {
                5: ["Es buenísimo, la verdad", "Me gustó un montón", "Está súper bien"],
                4: ["Es bastante bueno", "Me parece una buena opción", "Está chévere"],
                3: ["Está decente", "Es una opción sólida", "No está mal"],
                2: ["Es raro pero interesante", "Podría gustarte"],
                1: ["Es... diferente"]
            }
        }

        personality_reasons = reasons.get(self._current_personality, reasons['casual'])
        return random.choice(personality_reasons.get(rating, personality_reasons[3]))

    def _generate_smart_audience(self, book) -> str:
        """Genera audiencia objetivo inteligente."""
        audiences = []

        # Basado en tipo de libro
        type_audiences = {
            'novel': ["amantes de la ficción", "lectores de narrativa", "fans de las historias"],
            'essay': ["lectores reflexivos", "personas analíticas", "pensadores críticos"],
            'manual': ["personas prácticas", "estudiosos del tema", "profesionales"],
            'comic': ["amantes del arte visual", "fans de la narrativa gráfica"]
        }

        if book.type in type_audiences:
            audiences.extend(type_audiences[book.type])

        # Audiencias según personalidad
        personality_audiences = {
            'enthusiastic': ["aventureros literarios", "exploradores de historias", "entusiastas de la lectura"],
            'thoughtful': ["lectores contemplativo", "personas de mente analítica", "buscadores de profundidad"],
            'casual': ["lectores relajados", "gente con mente abierta", "cualquiera que busque algo nuevo"]
        }

        audiences.extend(personality_audiences.get(self._current_personality, []))

        return random.choice(audiences) if audiences else "lectores curiosos"

    def _generate_contextual_moods(self, book) -> List[str]:
        """Genera moods contextuales más inteligentes."""
        moods = []

        # Moods base según tipo
        type_moods = {
            'novel': ['inmersivo', 'narrativo', 'envolvente'],
            'essay': ['reflexivo', 'intelectual', 'analítico'],
            'manual': ['práctico', 'educativo', 'útil'],
            'comic': ['visual', 'dinámico', 'artístico']
        }

        if book.type in type_moods:
            moods.extend(type_moods[book.type])

        # Moods según hora del día
        now = datetime.now().hour
        if 6 <= now <= 12:
            moods.extend(['energizante', 'motivacional'])
        elif 13 <= now <= 18:
            moods.extend(['productivo', 'estimulante'])
        elif 19 <= now <= 22:
            moods.extend(['relajante', 'contemplativo'])
        else:
            moods.extend(['tranquilo', 'sereno'])

        # Moods según personalidad
        personality_moods = {
            'enthusiastic': ['emocionante', 'inspirador', 'energético'],
            'thoughtful': ['profundo', 'meditativo', 'enriquecedor'],
            'casual': ['cómodo', 'accesible', 'natural']
        }

        moods.extend(personality_moods.get(self._current_personality, []))

        # Seleccionar 2-3 moods únicos
        unique_moods = list(set(moods))
        return random.sample(unique_moods, min(3, len(unique_moods)))

    def _generate_special_note(self, book, downloads: int) -> Optional[str]:
        """Genera nota especial ocasional."""
        # 20% de probabilidad de nota especial
        if random.random() > 0.2:
            return None

        special_notes = []

        if downloads > 20:
            special_notes.append("🔥 ¡Es súper popular! Muchos lectores ya lo han disfrutado.")
        elif downloads == 0:
            special_notes.append("✨ ¡Serías el primero en descargarlo! Pioneer reader.")

        if book.year and book.year < 2000:
            special_notes.append("📚 Un clásico que nunca pasa de moda.")
        elif book.year and book.year > 2020:
            special_notes.append("🆕 Una lectura contemporánea y actual.")

        if len(book.title) > 50:
            special_notes.append("📖 El título ya cuenta toda una historia.")

        if not special_notes:
            general_notes = [
                "💎 Una joya oculta en nuestra biblioteca.",
                "🎲 Elegido especialmente para este momento.",
                "⭐ Selección personal de Neko-chan.",
                "🔮 Mi intuición dice que te gustará."
            ]
            special_notes.extend(general_notes)

        return random.choice(special_notes)

    def _format_enhanced_message(self, book, opinion: BookOpinion) -> str:
        """Formatea mensaje mejorado con plantillas."""
        try:
            # Seleccionar plantillas según personalidad
            intro_template = random.choice(self._message_templates[f'intro_{opinion.personality_tone}'])
            closing_template = random.choice(self._message_templates[f'closing_{opinion.personality_tone}'])

            # Generar estrellas con variación
            star_styles = ["⭐", "🌟", "✨"]
            star_char = random.choice(star_styles)
            stars = star_char * opinion.rating + "☆" * (5 - opinion.rating)

            # Emojis para moods
            mood_emojis = {
                'reflexivo': '🤔', 'envolvente': '📖', 'práctico': '🛠️',
                'visual': '🎨', 'interesante': '✨', 'relajante': '😌',
                'emocionante': '🎢', 'energético': '⚡', 'profundo': '🌊',
                'inmersivo': '🌀', 'contemplativo': '🧘', 'inspirador': '💡'
            }

            mood_text = " ".join([
                f"{mood_emojis.get(mood, '📚')}{mood.title()}"
                for mood in opinion.mood_tags
            ])

            message = f"""
{intro_template}

📖 **{opinion.title}**
✍️ *{opinion.author}*

{stars} **Mi rating personal:** {opinion.rating}/5

💭 **Mi análisis honesto:**

✅ **Lo que me enamoró:**
{chr(10).join([f"• {aspect}" for aspect in opinion.positive_aspects])}

🤔 **Puntos a considerar:**
{chr(10).join([f"• {concern}" for concern in opinion.concerns])}

💡 **¿Por qué lo recomiendo?**
{opinion.recommendation_reason}

🎯 **Ideal para:** {opinion.target_audience}
🏷️ **Vibes:** {mood_text}
"""

            # Agregar nota especial si existe
            if opinion.special_note:
                message += f"\n💫 **Nota especial:** {opinion.special_note}"

            # Agregar estadísticas del día ocasionalmente
            if self._daily_recommendations > 0 and random.random() < 0.3:
                message += f"\n\n📊 *Recomendación #{self._daily_recommendations + 1} del día*"

            message += f"""

📥 **Descárgalo:** /{book.book_id}

───────────────────
{closing_template}
"""

            return message.strip()

        except Exception as e:
            log_service_error("EnhancedAutoActivityService", e)
            # Mensaje simple como fallback
            return f"""
🌟 **Recomendación de Neko-chan**

📖 **{book.title}**
✍️ *{book.author}*

✨ {opinion.recommendation_reason}

📥 Descárgalo: /{book.book_id}
"""

    async def _send_with_visual_effects(self, book, message: str) -> None:
        """Envía mensaje con efectos visuales mejorados."""
        try:
            # Efecto de typing más natural
            await self.bot.send_chat_action(
                chat_id=self.target_chat_id,
                action=ChatAction.TYPING
            )

            # Pausa para efecto natural
            await asyncio.sleep(random.uniform(1.5, 3.0))

            # Enviar con o sin portada
            if book.cover_id and random.random() < 0.8:  # 80% chance de usar portada
                await self.bot.send_chat_action(
                    chat_id=self.target_chat_id,
                    action=ChatAction.UPLOAD_PHOTO
                )

                await self.bot.send_photo(
                    chat_id=self.target_chat_id,
                    photo=book.cover_id,
                    caption=message,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await self.bot.send_message(
                    chat_id=self.target_chat_id,
                    text=message,
                    parse_mode=ParseMode.MARKDOWN
                )

        except Exception as e:
            self.logger.warning(f"Error con efectos visuales: {e}")
            # Fallback simple
            await self._send_activity_message(message)

    async def _send_enhanced_no_books_message(self) -> None:
        """Mensaje mejorado cuando no hay libros."""
        no_books_messages = [
            """
😅 **¡Oops! Neko-chan se quedó sin material...**

Parece que he agotado mi lista de recomendaciones por ahora. 

🎁 **¿Qué tal si me ayudas?**
• Sube algunos archivos EPUB nuevos
• ¡Prometo análisis súper detallados de cada uno!
• Mis recomendaciones serán aún más especiales

🔄 **Mientras tanto:** puedes usar `/recommend [tema]` para recomendaciones personalizadas.

*¡Volveré pronto con más treasures literarios!* ✨
""",
            """
📚 **¡Momento de reabastecimiento!**

Mi biblioteca personal de recomendaciones necesita nuevos libros para seguir sorprendiéndote.

💡 **Ideas:**
• ¿Tienes algún EPUB favorito para compartir?
• ¿Algún género que te gustaría ver más?
• ¡Cualquier sugerencia es bienvenida!

🎯 *Usa `/list` para ver todos los libros disponibles o `/recommend` para búsquedas específicas.*
"""
        ]

        message = random.choice(no_books_messages)
        await self._send_activity_message(message)

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

    # MÉTODOS DE CONTROL Y CONFIGURACIÓN

    async def configure_activity_mode(self, mode: ActivityMode) -> bool:
        """Configura el modo de actividad."""
        try:
            self.activity_mode = mode
            self.logger.info(f"Modo de actividad cambiado a: {mode.value}")

            # Notificar cambio
            mode_descriptions = {
                ActivityMode.NORMAL: "recomendaciones equilibradas",
                ActivityMode.POPULAR: "enfoque en libros populares",
                ActivityMode.DISCOVERY: "descubrimiento de joyas ocultas",
                ActivityMode.VARIED: "máxima variedad"
            }

            message = f"""
⚙️ **Configuración actualizada**

🎯 **Nuevo modo:** {mode_descriptions[mode]}

*Las próximas recomendaciones seguirán este enfoque.*
"""
            await self._send_activity_message(message)
            return True

        except Exception as e:
            log_service_error("EnhancedAutoActivityService", e)
            return False

    def configure_quiet_hours(self, start_hour: int, end_hour: int, enabled: bool = True) -> bool:
        """Configura horarios silenciosos."""
        try:
            if not (0 <= start_hour <= 23) or not (0 <= end_hour <= 23):
                return False

            self.quiet_hours = (start_hour, end_hour)
            self.respect_quiet_hours = enabled

            self.logger.info(
                f"Horarios silenciosos: {start_hour}:00-{end_hour}:00 ({'activo' if enabled else 'inactivo'})")
            return True

        except Exception as e:
            log_service_error("EnhancedAutoActivityService", e)
            return False

    async def force_recommendation_with_mode(self, mode: Optional[ActivityMode] = None) -> bool:
        """Fuerza recomendación con modo específico."""
        try:
            original_mode = self.activity_mode
            if mode:
                self.activity_mode = mode

            await self._send_enhanced_recommendation()

            if mode:
                self.activity_mode = original_mode

            return True

        except Exception as e:
            log_service_error("EnhancedAutoActivityService", e)
            return False

    def get_enhanced_status(self) -> Dict[str, Any]:
        """Retorna estado completo y detallado del servicio."""
        return {
            'is_running': self._is_running,
            'interval_minutes': self.interval_minutes,
            'activity_mode': self.activity_mode.value,
            'current_personality': self._current_personality,
            'target_chat_id': self.target_chat_id,
            'last_recommendation': self._last_recommendation_time.isoformat() if self._last_recommendation_time else None,
            'recently_recommended_count': len(self._recently_recommended),
            'daily_recommendations': self._daily_recommendations,
            'quiet_hours': {
                'enabled': self.respect_quiet_hours,
                'start': self.quiet_hours[0],
                'end': self.quiet_hours[1],
                'currently_quiet': self._is_quiet_time()
            },
            'next_recommendation_eta': self._calculate_next_recommendation_eta(),
            'cache_status': {
                'size': len(self._recently_recommended),
                'max_size': self._max_recent_cache,
                'usage_percent': round(len(self._recently_recommended) / self._max_recent_cache * 100, 1)
            }
        }

    async def stop_activity_service(self) -> None:
        """Detiene el servicio con mensaje de despedida."""
        try:
            self._is_running = False

            if self._task and not self._task.done():
                self._task.cancel()
                try:
                    await self._task
                except asyncio.CancelledError:
                    pass

            # Mensaje de despedida
            farewell_message = f"""
😴 **Neko-chan se va a descansar...**

¡Hasta aquí llegamos por hoy! 

📊 **Estadísticas de la sesión:**
• Recomendaciones enviadas: {self._daily_recommendations}
• Libros en rotación: {len(self._recently_recommended)}

💤 *Puedes reactivarme cuando quieras con `/activity start`*

¡Que disfrutes la lectura! 📚✨
"""

            await self._send_activity_message(farewell_message)
            self.logger.info("🛑 Servicio de actividad automática detenido")

        except Exception as e:
            log_service_error("EnhancedAutoActivityService", e)

    async def _send_activity_message(self, message: str) -> None:
        """Envía mensaje de actividad con manejo de errores."""
        try:
            await self.bot.send_chat_action(
                chat_id=self.target_chat_id,
                action=ChatAction.TYPING
            )

            await self.bot.send_message(
                chat_id=self.target_chat_id,
                text=message,
                parse_mode=ParseMode.MARKDOWN
            )

        except TelegramError as e:
            self.logger.error(f"Error enviando mensaje de actividad: {e}")
        except Exception as e:
            log_service_error("EnhancedAutoActivityService", e)

    def _calculate_dynamic_rating(self, book, downloads: int) -> int:
        """Calcula rating dinámico más sofisticado."""
        base_rating = 3.0

        # Factores de popularidad
        if downloads > 25:
            base_rating += 1.2
        elif downloads > 15:
            base_rating += 0.8
        elif downloads > 8:
            base_rating += 0.4
        elif downloads < 2:
            base_rating -= 0.3

        # Factores de completitud de metadatos
        if book.description and len(book.description) > 200:
            base_rating += 0.4
        if book.publisher:
            base_rating += 0.2
        if book.year and 2000 <= book.year <= 2023:
            base_rating += 0.3

        # Ajuste por personalidad
        personality_adjustments = {
            'enthusiastic': 0.3,  # Más generosa
            'thoughtful': 0.0,  # Neutral
            'casual': -0.2  # Más crítica
        }

        base_rating += personality_adjustments.get(self._current_personality, 0)

        return max(1, min(5, round(base_rating)))

    def _calculate_next_recommendation_eta(self) -> Optional[str]:
        """Calcula ETA más preciso."""
        if not self._last_recommendation_time or not self._is_running:
            return None

        next_time = self._last_recommendation_time + timedelta(minutes=self.interval_minutes)
        now = datetime.now()

        if next_time > now:
            delta = next_time - now
            total_minutes = int(delta.total_seconds() / 60)

            if total_minutes < 60:
                return f"{total_minutes} minutos"
            else:
                hours = total_minutes // 60
                minutes = total_minutes % 60
                return f"{hours}h {minutes}m" if minutes > 0 else f"{hours}h"
        else:
            return "Próximamente"


# Crear alias para mantener compatibilidad
AutoActivityService = EnhancedAutoActivityService