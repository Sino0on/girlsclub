import asyncio

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from tickets import telegram_bot


class Command(BaseCommand):
    help = "Run the aiogram moderator bot (long polling) that handles the Да/Нет buttons."

    def handle(self, *args, **options):
        if not settings.TELEGRAM_BOT_TOKEN:
            raise CommandError("TELEGRAM_BOT_TOKEN is not set — see .env.example.")
        self.stdout.write("Starting Telegram moderator bot (long polling)...")
        asyncio.run(telegram_bot.run())
