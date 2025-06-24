"""
Manejo centralizado de errores para ZeepubsBot.
Proporciona logging estructurado y notificaciones de errores.
"""

import html
import traceback
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Dict, Any, Optional

from telegram import Update
from telegram.constants import ParseMode
from telegram.error import TelegramError, NetworkError, TimedOut, BadRequest
from telegram.ext import ContextTypes

from config.bot_config import get_config, get_logger


class ErrorSeverity(Enum):
    """Niveles de severidad de errores."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class ErrorInfo:
    """Información estructurada de un error."""
    timestamp: datetime
    severity: ErrorSeverity
    error_type: str
    message: str
    context: Optional[Dict[str, Any]] = None
    user_id: Optional[int] = None
    chat_id: Optional[int] = None
    traceback: Optional[str] = None


class ErrorHandler:
    """Manejador centralizado de errores."""

    def __init__(self):
        """Inicializa el manejador de errores."""
        self.config = get_config()
        self.logger = get_logger(__name__)

        # Contador de errores para rate limiting
        self._error_count = 0
        self._last_error_time = None

    async def handle_application_error(
            self,
            update: object,
            context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Maneja errores globales de la aplicación."""
        try:
            # Extraer información del error
            error_info = self._extract_error_info(update, context)

            # Log del error
            self._log_error(error_info)

            # Determinar si notificar al desarrollador
            if self._should_notify_developer(error_info):
                await self._notify_developer(error_info, context)

            # Responder al usuario si es posible
            if isinstance(update, Update) and update.effective_chat:
                await self._send_user_error_response(update, context, error_info)

        except Exception as e:
            # Error crítico en el error handler
            self.logger.critical(f"Error en el error handler: {e}")

    def _extract_error_info(
            self,
            update: object,
            context: ContextTypes.DEFAULT_TYPE
    ) -> ErrorInfo:
        """Extrae información estructurada del error."""
        try:
            # Información básica
            timestamp = datetime.now()
            error = context.error
            error_type = type(error).__name__
            message = str(error)

            # Determinar severidad
            severity = self._determine_severity(error)

            # Información del usuario/chat
            user_id = None
            chat_id = None
            if isinstance(update, Update):
                if update.effective_user:
                    user_id = update.effective_user.id
                if update.effective_chat:
                    chat_id = update.effective_chat.id

            # Traceback
            tb_string = None
            if error:
                tb_list = traceback.format_exception(
                    None, error, error.__traceback__
                )
                tb_string = "".join(tb_list)

            # Contexto adicional
            error_context = {
                'update': self._sanitize_update(update),
                'chat_data': str(context.chat_data) if context.chat_data else None,
                'user_data': str(context.user_data) if context.user_data else None
            }

            return ErrorInfo(
                timestamp=timestamp,
                severity=severity,
                error_type=error_type,
                message=message,
                context=error_context,
                user_id=user_id,
                chat_id=chat_id,
                traceback=tb_string
            )

        except Exception as e:
            self.logger.error(f"Error extrayendo información de error: {e}")
            return ErrorInfo(
                timestamp=datetime.now(),
                severity=ErrorSeverity.HIGH,
                error_type="ErrorExtractionFailure",
                message=f"Error procesando error original: {str(e)}"
            )

    def _determine_severity(self, error: Exception) -> ErrorSeverity:
        """Determina la severidad del error basada en su tipo."""
        # Errores críticos que requieren atención inmediata
        critical_errors = (
            ConnectionError,
            PermissionError,
            SystemError
        )

        # Errores de alta prioridad
        high_errors = (
            ValueError,
            TypeError,
            AttributeError,
            KeyError
        )

        # Errores de red/Telegram (usualmente temporales)
        medium_errors = (
            NetworkError,
            TimedOut,
            TelegramError
        )

        # Errores de usuario (baja prioridad)
        low_errors = (
            BadRequest,
            FileNotFoundError
        )

        if isinstance(error, critical_errors):
            return ErrorSeverity.CRITICAL
        elif isinstance(error, high_errors):
            return ErrorSeverity.HIGH
        elif isinstance(error, medium_errors):
            return ErrorSeverity.MEDIUM
        elif isinstance(error, low_errors):
            return ErrorSeverity.LOW
        else:
            return ErrorSeverity.MEDIUM  # Default

    def _log_error(self, error_info: ErrorInfo) -> None:
        """Registra el error en los logs con formato estructurado."""
        try:
            log_message = self._format_log_message(error_info)

            # Log según severidad
            if error_info.severity == ErrorSeverity.CRITICAL:
                self.logger.critical(log_message)
            elif error_info.severity == ErrorSeverity.HIGH:
                self.logger.error(log_message)
            elif error_info.severity == ErrorSeverity.MEDIUM:
                self.logger.warning(log_message)
            else:
                self.logger.info(log_message)

        except Exception as e:
            self.logger.error(f"Error loggeando error: {e}")

    def _format_log_message(self, error_info: ErrorInfo) -> str:
        """Formatea mensaje de log estructurado."""
        base_message = (
            f"[{error_info.severity.value.upper()}] "
            f"{error_info.error_type}: {error_info.message}"
        )

        if error_info.user_id:
            base_message += f" | User: {error_info.user_id}"

        if error_info.chat_id:
            base_message += f" | Chat: {error_info.chat_id}"

        return base_message

    def _should_notify_developer(self, error_info: ErrorInfo) -> bool:
        """Determina si se debe notificar al desarrollador."""
        # Rate limiting para evitar spam
        if self._is_rate_limited():
            return False

        # Solo notificar errores de severidad media o superior
        return error_info.severity in [
            ErrorSeverity.MEDIUM,
            ErrorSeverity.HIGH,
            ErrorSeverity.CRITICAL
        ]

    def _is_rate_limited(self) -> bool:
        """Implementa rate limiting para notificaciones."""
        current_time = datetime.now()

        # Rate limiting: máximo 5 notificaciones por hora
        if self._last_error_time:
            time_diff = (current_time - self._last_error_time).total_seconds()
            if time_diff < 720:  # 12 minutos
                self._error_count += 1
                if self._error_count > 5:
                    return True
            else:
                self._error_count = 1
        else:
            self._error_count = 1

        self._last_error_time = current_time
        return False

    async def _notify_developer(
            self,
            error_info: ErrorInfo,
            context: ContextTypes.DEFAULT_TYPE
    ) -> None:
        """Envía notificación de error al desarrollador."""
        try:
            # Construir mensaje de notificación
            notification_message = self._build_developer_notification(error_info)

            # Truncar si es muy largo
            if len(notification_message) > self.config.max_message_length:
                notification_message = (
                        notification_message[:self.config.max_message_length - 100] +
                        "\n...[MENSAJE TRUNCADO]"
                )

            # Enviar mensaje
            await context.bot.send_message(
                chat_id=self.config.developer_chat_id,
                text=notification_message,
                parse_mode=ParseMode.HTML
            )

        except Exception as e:
            self.logger.error(f"Error enviando notificación al desarrollador: {e}")

    def _build_developer_notification(self, error_info: ErrorInfo) -> str:
        """Construye mensaje de notificación para el desarrollador."""
        try:
            # Emoji según severidad
            severity_emoji = {
                ErrorSeverity.LOW: "ℹ️",
                ErrorSeverity.MEDIUM: "⚠️",
                ErrorSeverity.HIGH: "🚨",
                ErrorSeverity.CRITICAL: "🔥"
            }

            emoji = severity_emoji.get(error_info.severity, "❓")

            # Mensaje base
            message = (
                f"{emoji} <b>Error en ZeepubsBot</b>\n"
                f"<b>Severidad:</b> {error_info.severity.value.upper()}\n"
                f"<b>Tipo:</b> {error_info.error_type}\n"
                f"<b>Hora:</b> {error_info.timestamp.strftime('%Y-%m-%d %H:%M:%S')}\n\n"
                f"<b>Mensaje:</b>\n<code>{html.escape(error_info.message)}</code>\n"
            )

            # Información del usuario si está disponible
            if error_info.user_id:
                message += f"\n<b>Usuario:</b> {error_info.user_id}"

            if error_info.chat_id:
                message += f"\n<b>Chat:</b> {error_info.chat_id}"

            # Contexto del update si está disponible
            if error_info.context and error_info.context.get('update'):
                update_str = str(error_info.context['update'])[:200]
                message += f"\n\n<b>Update:</b>\n<pre>{html.escape(update_str)}</pre>"

            # Traceback (limitado)
            if error_info.traceback:
                tb_preview = error_info.traceback[-500:]  # Últimas 500 chars
                message += f"\n\n<b>Traceback:</b>\n<pre>{html.escape(tb_preview)}</pre>"

            return message

        except Exception as e:
            self.logger.error(f"Error construyendo notificación: {e}")
            return f"Error construyendo notificación de error: {str(e)}"

    async def _send_user_error_response(
            self,
            update: Update,
            context: ContextTypes.DEFAULT_TYPE,
            error_info: ErrorInfo
    ) -> None:
        """Envía respuesta de error amigable al usuario."""
        try:
            # Mensajes según severidad
            user_messages = {
                ErrorSeverity.LOW: "Hubo un pequeño problema. Por favor, intenta nuevamente.",
                ErrorSeverity.MEDIUM: "Ocurrió un error temporal. Intenta en unos momentos.",
                ErrorSeverity.HIGH: "Lo siento, ocurrió un error. El problema ha sido reportado.",
                ErrorSeverity.CRITICAL: "Servicio temporalmente no disponible. Intenta más tarde."
            }

            message = user_messages.get(
                error_info.severity,
                "Ocurrió un error inesperado. Por favor, intenta nuevamente."
            )

            # Intentar responder
            if update.message:
                await update.message.reply_text(message)
            elif update.callback_query:
                await update.callback_query.answer(message, show_alert=True)

        except Exception as e:
            self.logger.warning(f"No se pudo enviar respuesta de error al usuario: {e}")

    def _sanitize_update(self, update: object) -> Dict[str, Any]:
        """Sanitiza información del update para logging seguro."""
        try:
            if isinstance(update, Update):
                return {
                    'update_id': update.update_id,
                    'message_id': update.message.message_id if update.message else None,
                    'user_id': update.effective_user.id if update.effective_user else None,
                    'chat_id': update.effective_chat.id if update.effective_chat else None,
                    'message_text': update.message.text[:100] if update.message and update.message.text else None
                }
            else:
                return {'raw_update': str(update)[:200]}

        except Exception as e:
            return {'sanitization_error': str(e)}

    def handle_service_error(
            self,
            service_name: str,
            error: Exception,
            context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Maneja errores específicos de servicios."""
        try:
            error_info = ErrorInfo(
                timestamp=datetime.now(),
                severity=self._determine_severity(error),
                error_type=f"{service_name}Error",
                message=f"Error en {service_name}: {str(error)}",
                context=context or {}
            )

            self._log_error(error_info)

        except Exception as e:
            self.logger.error(f"Error manejando error de servicio: {e}")

    def get_error_statistics(self) -> Dict[str, Any]:
        """Retorna estadísticas básicas de errores."""
        return {
            'error_count': self._error_count,
            'last_error_time': self._last_error_time.isoformat() if self._last_error_time else None,
            'rate_limited': self._is_rate_limited()
        }


# Instancia global del manejador de errores
error_handler = ErrorHandler()


# Funciones de conveniencia
async def handle_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Función de conveniencia para manejo de errores de aplicación."""
    await error_handler.handle_application_error(update, context)


def log_service_error(
        service_name: str,
        error: Exception,
        context: Optional[Dict[str, Any]] = None
) -> None:
    """Función de conveniencia para errores de servicios."""
    error_handler.handle_service_error(service_name, error, context)
