"""
Personalidad y mensajes para el servicio de actividad automática.
Define las diferentes personalidades de Neko-chan y sus plantillas de mensajes.

Ubicación: services/activity_personality.py
"""

import random
from typing import Dict, List
from enum import Enum


class PersonalityType(Enum):
    """Tipos de personalidad para Neko-chan."""
    ENTHUSIASTIC = "enthusiastic"
    THOUGHTFUL = "thoughtful"
    CASUAL = "casual"
    EXCITED = "excited"


class ActivityPersonality:
    """Maneja la personalidad y mensajes de Neko-chan."""

    def __init__(self):
        """Inicializa las plantillas de personalidad."""
        self._message_templates = {
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
            'intro_excited': [
                "🚀 **¡ALERTA DE LIBRO INCREÍBLE!** 🚀",
                "⚡ **¡Prepárense para esta bomba literaria!** ⚡",
                "🔥 **¡ESTO NO SE PUEDEN PERDER!** 🔥",
                "💥 **¡RECOMENDACIÓN ÉPICA INCOMING!** 💥"
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
            'closing_casual': [
                "A ver qué tal te va con este. 😊",
                "Espero que te guste tanto como a mí. 👍",
                "Cuéntame si lo disfrutas. 📖",
                "¡Que tengas una buena lectura! ☕"
            ],
            'closing_excited': [
                "¡VAS A FLIPAR CON ESTE LIBRO! 🤯",
                "¡PREPÁRATE PARA LA AVENTURA DE TU VIDA! 🎢",
                "¡NO PODRÁS SOLTARLO! 🎯",
                "¡SERÁ ÉPICO, LO PROMETO! 🔥"
            ]
        }

        self._rating_comments = {
            PersonalityType.ENTHUSIASTIC: {
                5: "¡Es absolutamente PERFECTO!",
                4: "¡Me encanta muchísimo!",
                3: "¡Me gusta bastante!",
                2: "Es interesante, aunque...",
                1: "Bueno, es... particular"
            },
            PersonalityType.THOUGHTFUL: {
                5: "Una obra excepcional y profunda",
                4: "Una lectura sólida y valiosa",
                3: "Una opción razonable para considerar",
                2: "Una experiencia literaria particular",
                1: "Una propuesta experimental"
            },
            PersonalityType.CASUAL: {
                5: "Está buenísimo, la verdad",
                4: "Está bastante bien",
                3: "Está decente",
                2: "Es raro pero interesante",
                1: "Es... diferente"
            },
            PersonalityType.EXCITED: {
                5: "¡ES UNA OBRA MAESTRA TOTAL!",
                4: "¡ESTÁ SÚPER GENIAL!",
                3: "¡ESTÁ BASTANTE COOL!",
                2: "Es medio raro, ¡pero mola!",
                1: "Es... ¡muy experimental!"
            }
        }

        self._positive_aspects_templates = {
            PersonalityType.ENTHUSIASTIC: [
                "¡Me fascina completamente el estilo del autor!",
                "¡La premisa me tiene súper emocionada!",
                "¡Es exactamente el tipo de historia que amo!",
                "¡Promete ser una experiencia increíble!"
            ],
            PersonalityType.THOUGHTFUL: [
                "La propuesta narrativa es muy sólida",
                "Me parece una exploración profunda del tema",
                "La estructura está muy bien pensada",
                "Ofrece perspectivas realmente valiosas"
            ],
            PersonalityType.CASUAL: [
                "Tiene buena pinta, la verdad",
                "Me gusta el estilo del autor",
                "Es del tipo de libros que disfruto",
                "Se ve como una lectura entretenida"
            ],
            PersonalityType.EXCITED: [
                "¡EL AUTOR ES UN GENIO TOTAL!",
                "¡LA TRAMA SUENA ESPECTACULAR!",
                "¡ES JUSTO MI TIPO DE LOCURA!",
                "¡VA A SER ÉPICO, LO SÉ!"
            ]
        }

        self._concerns_templates = {
            PersonalityType.ENTHUSIASTIC: [
                "¡Aunque podría ser un poquito intenso para algunos!",
                "¡Requiere estar en el mood perfecto!",
                "¡Definitivamente no es una lectura ligera!"
            ],
            PersonalityType.THOUGHTFUL: [
                "Requiere cierta preparación mental",
                "El ritmo podría no ser ideal para todos",
                "Es importante tener expectativas realistas"
            ],
            PersonalityType.CASUAL: [
                "No es para todos los gustos",
                "Mejor leerlo cuando tengas tiempo",
                "Podría ser un poco lento al principio"
            ],
            PersonalityType.EXCITED: [
                "¡PODRÍA SER DEMASIADO INTENSO!",
                "¡NECESITAS ESTAR SÚPER CONCENTRADO!",
                "¡NO ES PARA LECTORES CASUALES!"
            ]
        }

    def get_intro_message(self, personality: PersonalityType) -> str:
        """Retorna mensaje de introducción según personalidad."""
        key = f"intro_{personality.value}"
        return random.choice(self._message_templates.get(key, self._message_templates['intro_casual']))

    def get_closing_message(self, personality: PersonalityType) -> str:
        """Retorna mensaje de cierre según personalidad."""
        key = f"closing_{personality.value}"
        return random.choice(self._message_templates.get(key, self._message_templates['closing_casual']))

    def get_rating_comment(self, personality: PersonalityType, rating: int) -> str:
        """Retorna comentario de rating según personalidad."""
        comments = self._rating_comments.get(personality, self._rating_comments[PersonalityType.CASUAL])
        return comments.get(rating, comments[3])

    def get_positive_aspects(self, personality: PersonalityType, count: int = 2) -> List[str]:
        """Retorna aspectos positivos según personalidad."""
        templates = self._positive_aspects_templates.get(
            personality,
            self._positive_aspects_templates[PersonalityType.CASUAL]
        )
        return random.sample(templates, min(count, len(templates)))

    def get_concerns(self, personality: PersonalityType, count: int = 1) -> List[str]:
        """Retorna preocupaciones según personalidad."""
        templates = self._concerns_templates.get(
            personality,
            self._concerns_templates[PersonalityType.CASUAL]
        )
        return random.sample(templates, min(count, len(templates)))

    def get_recommendation_reason(self, personality: PersonalityType, rating: int) -> str:
        """Genera razón de recomendación según personalidad y rating."""
        reasons = {
            PersonalityType.ENTHUSIASTIC: {
                5: "Es de esos libros que realmente valen la pena",
                4: "Me encanta recomendar lecturas de este calibre",
                3: "Es una buena opción para explorar algo diferente",
                2: "Podría ser una grata sorpresa",
                1: "Vale la pena como experiencia literaria"
            },
            PersonalityType.THOUGHTFUL: {
                5: "Representa una contribución significativa a la literatura",
                4: "Es una obra sólida que vale la pena considerar",
                3: "Puede aportar perspectivas interesantes",
                2: "Es una experiencia literaria particular",
                1: "Es una propuesta experimental interesante"
            },
            PersonalityType.CASUAL: {
                5: "Es buenísimo, la verdad",
                4: "Es bastante bueno",
                3: "Es una opción sólida",
                2: "Es raro pero interesante",
                1: "Es... diferente"
            },
            PersonalityType.EXCITED: {
                5: "¡ES ABSOLUTAMENTE ÉPICO!",
                4: "¡ESTÁ SÚPER GENIAL!",
                3: "¡ESTÁ BASTANTE COOL!",
                2: "¡Es raro pero MOLA!",
                1: "¡Es SÚPER experimental!"
            }
        }

        personality_reasons = reasons.get(personality, reasons[PersonalityType.CASUAL])
        return personality_reasons.get(rating, personality_reasons[3])

    def get_target_audience(self, personality: PersonalityType) -> str:
        """Retorna audiencia objetivo según personalidad."""
        audiences = {
            PersonalityType.ENTHUSIASTIC: [
                "aventureros literarios",
                "exploradores de historias",
                "entusiastas de la lectura"
            ],
            PersonalityType.THOUGHTFUL: [
                "lectores contemplativos",
                "personas de mente analítica",
                "buscadores de profundidad"
            ],
            PersonalityType.CASUAL: [
                "lectores relajados",
                "gente con mente abierta",
                "cualquiera que busque algo nuevo"
            ],
            PersonalityType.EXCITED: [
                "¡AVENTUREROS EXTREMOS!",
                "¡FANS DE LA ADRENALINA LITERARIA!",
                "¡LECTORES SIN MIEDO!"
            ]
        }

        personality_audiences = audiences.get(personality, audiences[PersonalityType.CASUAL])
        return random.choice(personality_audiences)

    def get_startup_message(self) -> str:
        """Retorna mensaje de inicio del servicio."""
        messages = [
            """
🤖 **¡Neko-chan despertó con energía renovada!** ✨

¡Hola! He activado mi sistema de recomendaciones automáticas.

🎯 **Qué pueden esperar:**
• Recomendaciones cada 30 minutos
• Mis opiniones personales detalladas
• Diferentes personalidades para mantener variedad
• Selección inteligente de libros

📚 **Mi promesa:** Mantener nuestra conversación literaria siempre viva.

💫 *¿Listos para descubrir juntos los tesoros de nuestra biblioteca?*
""",
            """
🌟 **¡Sistema de recomendaciones Neko-chan activado!** 🌟

¡Bienvenidos a una experiencia literaria mejorada!

✨ **Características:**
• Recomendaciones automáticas cada media hora
• Análisis personal honesto de cada libro
• Variedad en estilos y personalidades
• Enfoque en mantener la charla activa

📖 *¡Prepárense para una aventura literaria continua!*
"""
        ]
        return random.choice(messages)

    def get_no_books_message(self) -> str:
        """Retorna mensaje cuando no hay libros disponibles."""
        messages = [
            """
😅 **¡Oops! Neko-chan se quedó sin material...**

Parece que he agotado mi lista de recomendaciones por ahora.

🎁 **¿Qué tal si me ayudas?**
• Sube algunos archivos EPUB nuevos
• ¡Prometo análisis súper detallados!

🔄 **Mientras tanto:** usa `/recommend [tema]` para recomendaciones personalizadas.

*¡Volveré pronto con más treasures literarios!* ✨
""",
            """
📚 **¡Momento de reabastecimiento!**

Mi biblioteca personal necesita nuevos libros para seguir sorprendiéndote.

💡 **Ideas:**
• ¿Tienes algún EPUB favorito para compartir?
• ¿Algún género que te gustaría ver más?

🎯 *Usa `/list` para ver todos los libros disponibles.*
"""
        ]
        return random.choice(messages)

    def get_farewell_message(self, daily_recommendations: int, cache_size: int) -> str:
        """Retorna mensaje de despedida."""
        return f"""
😴 **Neko-chan se va a descansar...**

¡Hasta aquí llegamos por hoy!

📊 **Estadísticas de la sesión:**
• Recomendaciones enviadas: {daily_recommendations}
• Libros en rotación: {cache_size}

💤 *Puedes reactivarme cuando quieras con `/activity start`*

¡Que disfrutes la lectura! 📚✨
"""

    def get_random_personality(self) -> PersonalityType:
        """Retorna personalidad aleatoria."""
        return random.choice(list(PersonalityType))

    def get_mood_emojis(self) -> Dict[str, str]:
        """Retorna mapeo de moods a emojis."""
        return {
            'reflexivo': '🤔',
            'envolvente': '📖',
            'práctico': '🛠️',
            'visual': '🎨',
            'interesante': '✨',
            'relajante': '😌',
            'emocionante': '🎢',
            'energético': '⚡',
            'profundo': '🌊',
            'inmersivo': '🌀',
            'contemplativo': '🧘',
            'inspirador': '💡',
            'divertido': '😄',
            'misterioso': '🔍',
            'romántico': '💕',
            'aventurero': '🗺️'
        }

    def should_change_personality(self, probability: float = 0.3) -> bool:
        """Determina si debe cambiar de personalidad."""
        return random.random() < probability