"""
Telegram Proxy para ThothBot.
Recibe mensajes de Telegram via polling y los reenvía a la API REST de Rasa.
Evita el bug de 'Event loop is closed' del canal nativo de Rasa 3.6.x.
"""
import os
import logging
import requests
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, MessageHandler, CommandHandler, filters, ContextTypes

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

TELEGRAM_TOKEN = os.environ["TOKEN_TELEGRAM"]
RASA_URL = os.environ.get("RASA_URL", "http://rasa:5005/webhooks/rest/webhook")


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja el comando /start."""
    sender_id = str(update.effective_user.id)
    await _send_to_rasa_and_reply(update, sender_id, "/start")


async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Maneja mensajes de texto normales."""
    sender_id = str(update.effective_user.id)
    user_message = update.message.text
    logger.info(f"Mensaje de {sender_id}: {user_message}")
    await _send_to_rasa_and_reply(update, sender_id, user_message)


def convertir_markdown(texto):
    """Convierte markdown de GitHub a Telegram Markdown."""
    texto = re.sub(r'\*\*(.+?)\*\*', r'*\1*', texto)
    return texto

def extraer_botones(texto):
    """Extrae enlaces Markdown y los convierte en botones InlineKeyboardMarkup."""
    patron = r'\[([^\]]+)\]\((https?://[^\)]+)\)'
    botones = []
    for match in re.finditer(patron, texto):
        label, url = match.group(1), match.group(2)
        botones.append([InlineKeyboardButton(label, url=url)])
    texto_limpio = re.sub(patron, '', texto).strip()
    return texto_limpio, botones


async def _send_to_rasa_and_reply(update: Update, sender_id: str, message: str) -> None:
    """Envía el mensaje a Rasa y devuelve la respuesta al usuario."""
    try:
        response = requests.post(
            RASA_URL,
            json={"sender": sender_id, "message": message},
            timeout=15
        )
        response.raise_for_status()
        bot_messages = response.json()

        if not bot_messages:
            await update.message.reply_text("...")
            return

        for msg in bot_messages:
            if "text" in msg:
                texto_limpio, botones = extraer_botones(msg["text"])
                texto_formateado = convertir_markdown(texto_limpio)
                reply_markup = InlineKeyboardMarkup(botones) if botones else None
                
                # Enviar mensaje con Markdown habilitado y los botones parseados
                try:
                    await update.message.reply_text(
                        texto_formateado,
                        parse_mode='Markdown',
                        reply_markup=reply_markup
                    )
                except Exception as ex:
                    logger.error(f"Error al enviar mensaje con Markdown: {ex}. Enviando sin formato.")
                    await update.message.reply_text(texto_limpio, reply_markup=reply_markup)
            elif "image" in msg:
                await update.message.reply_photo(msg["image"])

    except requests.exceptions.ConnectionError:
        logger.error(f"No se pudo conectar con Rasa en {RASA_URL}")
        await update.message.reply_text(
            "Lo siento, el servicio no está disponible en este momento. Inténtalo de nuevo en unos segundos."
        )
    except Exception as e:
        logger.error(f"Error inesperado: {e}")
        await update.message.reply_text("Ha ocurrido un error inesperado.")


def main() -> None:
    logger.info(f"Iniciando proxy de Telegram → Rasa ({RASA_URL})")
    app = Application.builder().token(TELEGRAM_TOKEN).build()
    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    logger.info("Bot iniciado con polling...")
    # Asegurarse de que no hay un webhook activo que bloquee el polling
    import asyncio
    
    async def delete_webhook_and_start():
        await app.bot.delete_webhook(drop_pending_updates=True)
        # run_polling es bloqueante, así que lo llamamos normalmente después
        # Pero run_polling ya crea su propio loop. 
        # En PTB 20+, lo mejor es usar drop_pending_updates=True dentro de run_polling
        # que INTERNAMENTE debería llamar a delete_webhook si detecta el conflicto, 
        # pero a veces falla en el primer intento.
    
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=True)


if __name__ == "__main__":
    main()
