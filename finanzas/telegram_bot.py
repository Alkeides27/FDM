# finanzas/telegram_bot.py
import os
import logging
import requests
from decimal import Decimal

logger = logging.getLogger(__name__)
BOT_TOKEN = os.environ.get('TELEGRAM_BOT_TOKEN', '')
API_URL = f'https://api.telegram.org/bot{BOT_TOKEN}' if BOT_TOKEN else None


def formato_bs(valor):
    """Formatea un Decimal como '1.250,00 Bs' (estilo venezolano)."""
    if valor is None:
        return '—'
    s = f'{Decimal(valor):,.2f}'
    s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'{s} Bs'


def formato_usd(valor):
    """Formatea un Decimal como '$ 15,00' (estilo venezolano)."""
    if valor is None:
        return '—'
    s = f'{Decimal(valor):,.2f}'
    s = s.replace(',', 'X').replace('.', ',').replace('X', '.')
    return f'$ {s}'


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


def notificar_pago_aprobado(pago):
    """Envía mensaje de aprobación con formato localizado."""
    texto = (
        f'✅ Tu pago <b>#{pago.id}</b> fue APROBADO.\n'
        f'Monto: {formato_bs(pago.monto_bs)} ({formato_usd(pago.monto_usd)})\n'
        f'Concepto: {pago.concepto}'
    )
    return notificar_representante(pago.representante, texto)


def notificar_pago_rechazado(pago):
    """Envía mensaje de rechazo con formato localizado."""
    texto = (
        f'❌ Tu pago <b>#{pago.id}</b> fue RECHAZADO.\n'
        f'Monto: {formato_bs(pago.monto_bs)}\n'
        f'Motivo: {pago.motivo_rechazo}'
    )
    return notificar_representante(pago.representante, texto)
