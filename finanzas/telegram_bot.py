# finanzas/telegram_bot.py
import os
import logging
import requests

logger = logging.getLogger(__name__)
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
API_URL = f'https://api.telegram.org/bot{BOT_TOKEN}' if BOT_TOKEN else None


def enviar_mensaje(chat_id, texto):
    if not BOT_TOKEN or not chat_id:
        logger.warning('Telegram: token o chat_id ausente.')
        return False
    try:
        r = requests.post(
            f'{API_URL}/sendMessage',
            json={'chat_id': chat_id, 'text': texto, 'parse_mode': 'HTML'},
            timeout=5
        )
        if not r.ok:
            logger.error(f'Telegram error: {r.status_code} {r.text}')
        return r.ok
    except Exception as e:
        logger.exception(f'Telegram exception: {e}')
        return False


def notificar_representante(representante, texto):
    if representante.telegram_chat_id:
        return enviar_mensaje(representante.telegram_chat_id, texto)
    return False
