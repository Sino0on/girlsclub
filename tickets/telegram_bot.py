"""Moderator bot: listens for the Да/Нет buttons attached to the receipt
photo posted by services.notify_moderators(). Runs as its own long-lived
process (see management/commands/run_telegram_bot.py) — sending messages
happens separately via a plain HTTP call in services.py; this module
only needs to *receive* button presses, which requires a running bot.
"""

import asyncio
import logging

from aiogram import Bot, Dispatcher, F
from aiogram.client.session.aiohttp import AiohttpSession
from aiogram.types import CallbackQuery
from asgiref.sync import sync_to_async
from django.conf import settings

from . import services

logger = logging.getLogger(__name__)

dp = Dispatcher()


def _order_id_from(callback_data: str) -> int:
    return int(callback_data.split(":", 1)[1])


@dp.callback_query(F.data.startswith("order_yes:"))
async def on_confirm(callback: CallbackQuery):
    order_id = _order_id_from(callback.data)
    await sync_to_async(services.approve_order)(order_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    new_caption = (callback.message.caption or callback.message.text or "") + "\n\n✅ Подтверждено"
    try:
        await callback.message.edit_caption(caption=new_caption)
    except Exception:
        try:
            await callback.message.edit_text(text=new_caption)
        except Exception:
            pass
    await callback.answer("Принято")


@dp.callback_query(F.data.startswith("order_no:"))
async def on_reject(callback: CallbackQuery):
    order_id = _order_id_from(callback.data)
    await sync_to_async(services.reject_order)(order_id)
    await callback.message.edit_reply_markup(reply_markup=None)
    new_caption = (callback.message.caption or callback.message.text or "") + "\n\n❌ Отклонено, билет аннулирован"
    try:
        await callback.message.edit_caption(caption=new_caption)
    except Exception:
        try:
            await callback.message.edit_text(text=new_caption)
        except Exception:
            pass
    await callback.answer("Билет аннулирован")


async def run():
    # Constructed here (not at module import time) so importing this
    # module — e.g. from the Django shell, or anything that touches
    # services.py — doesn't require a valid TELEGRAM_BOT_TOKEN.
    #
    # api.telegram.org can be slow/flaky to reach from some hosts —
    # give it more room than aiogram's 60s default, and retry with
    # backoff instead of letting one bad connection kill the whole
    # process (docker-compose would restart it, but that's a much
    # blunter, slower way to recover from a transient network hiccup).
    session = AiohttpSession(timeout=90)
    bot = Bot(token=settings.TELEGRAM_BOT_TOKEN, session=session)

    backoff = 5
    while True:
        try:
            await dp.start_polling(bot)
            return  # start_polling only returns on a clean shutdown
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("Telegram polling crashed — retrying in %ss", backoff)
            await asyncio.sleep(backoff)
            backoff = min(backoff * 2, 120)
