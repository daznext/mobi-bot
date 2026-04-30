from __future__ import annotations

import asyncio
import logging
import shutil
import re
import tempfile
import time
import uuid
from dataclasses import dataclass
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ChatAction
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from .config import Config
from .converter import ConversionError, convert_to_mobi, is_supported_book, mobi_name, prepare_source
from .mailer import MailError, send_to_kindle
from .storage import Storage


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
MAX_TELEGRAM_FILE_BYTES = 50 * 1024 * 1024
JOB_TTL_SECONDS = 24 * 60 * 60


@dataclass
class ConvertedJob:
    user_id: int
    path: Path
    kindle_path: Path
    created_at: float


HELP_TEXT = """Пришлите книгу файлом: fb2, fb2.zip, zip с fb2 внутри или epub. Я сконвертирую ее в mobi и отправлю обратно.

Команды:
/setemail name@kindle.com - сохранить или заменить Kindle email
/email - показать сохраненный Kindle email
/deleteemail - удалить сохраненный Kindle email
/whoami - показать ваш Telegram user id
/help - помощь
"""


class KindleBot:
    def __init__(self, config: Config) -> None:
        self.config = config
        self.storage = Storage(config.db_path)
        self.jobs: dict[str, ConvertedJob] = {}
        self.config.output_dir.mkdir(parents=True, exist_ok=True)

    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        await update.effective_message.reply_text(self._help_text(update))

    async def set_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            await self._reject(update)
            return

        message = update.effective_message
        user = update.effective_user
        if not message or not user:
            return

        if not context.args:
            await message.reply_text("Напишите так: /setemail name@kindle.com")
            return

        email = context.args[0].strip()
        if not EMAIL_RE.match(email):
            await message.reply_text("Похоже, это не email. Пример: /setemail name@kindle.com")
            return

        self.storage.set_kindle_email(user.id, email)
        await message.reply_text(
            f"Сохранил Kindle email: {email}\n\n{self._approved_sender_hint()}"
        )

    async def show_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            await self._reject(update)
            return

        message = update.effective_message
        user = update.effective_user
        if not message or not user:
            return

        email = self.storage.get_kindle_email(user.id)
        if email:
            await message.reply_text(f"Сохраненный Kindle email: {email}")
        else:
            await message.reply_text("Kindle email пока не задан. Используйте /setemail name@kindle.com")

    async def delete_email(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            await self._reject(update)
            return

        message = update.effective_message
        user = update.effective_user
        if not message or not user:
            return

        self.storage.delete_kindle_email(user.id)
        await message.reply_text("Удалил сохраненный Kindle email.")

    async def whoami(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        message = update.effective_message
        user = update.effective_user
        if not message or not user:
            return

        await message.reply_text(f"Ваш Telegram user id: {user.id}")

    async def handle_document(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            await self._reject(update)
            return

        message = update.effective_message
        user = update.effective_user
        document = message.document if message else None
        if not message or not user or not document:
            return

        filename = Path(document.file_name or "book").name
        if not is_supported_book(filename):
            await message.reply_text("Поддерживаются fb2, fb2.zip, zip с fb2 внутри и epub.")
            return

        if document.file_size and document.file_size > MAX_TELEGRAM_FILE_BYTES:
            await message.reply_text("Файл слишком большой для обработки через Telegram Bot API.")
            return

        self._cleanup_old_jobs()
        await message.reply_text("Принял файл. Конвертирую в mobi...")
        await context.bot.send_chat_action(chat_id=message.chat_id, action=ChatAction.UPLOAD_DOCUMENT)

        try:
            output_path, kindle_path = await self._download_and_convert(context, document.file_id, filename)
        except ConversionError as exc:
            logging.exception("Book conversion failed")
            await message.reply_text(f"Не удалось сконвертировать книгу: {exc}")
            return
        except Exception as exc:
            logging.exception("Unexpected document processing failure")
            await message.reply_text(f"Не удалось обработать файл: {exc}")
            return

        job_id = uuid.uuid4().hex
        self.jobs[job_id] = ConvertedJob(
            user_id=user.id,
            path=output_path,
            kindle_path=kindle_path,
            created_at=time.time(),
        )

        keyboard = None
        kindle_email = self.storage.get_kindle_email(user.id)
        if kindle_email:
            keyboard = InlineKeyboardMarkup(
                [[InlineKeyboardButton(f"Отправить EPUB на {kindle_email}", callback_data=f"send:{job_id}")]]
            )

        with output_path.open("rb") as converted:
            await message.reply_document(
                document=converted,
                filename=output_path.name,
                caption="Готово: mobi файл во вложении.",
                reply_markup=keyboard,
            )

        if not kindle_email:
            await message.reply_text("Чтобы отправлять книги на Kindle почтой, задайте адрес: /setemail name@kindle.com")

    async def _download_and_convert(
        self,
        context: ContextTypes.DEFAULT_TYPE,
        file_id: str,
        filename: str,
    ) -> tuple[Path, Path]:
        with tempfile.TemporaryDirectory(prefix="kindle-bot-") as temp_dir:
            temp_path = Path(temp_dir)
            source_path = temp_path / filename
            telegram_file = await context.bot.get_file(file_id)
            await telegram_file.download_to_drive(custom_path=source_path)
            prepared_source = prepare_source(source_path, temp_path)

            output_name = f"{uuid.uuid4().hex}-{mobi_name(filename)}"
            output_path = self.config.output_dir / output_name
            await convert_to_mobi(self.config.ebook_convert_bin, prepared_source, output_path)

            kindle_name = f"{uuid.uuid4().hex}-{Path(output_name).with_suffix('.epub').name}"
            kindle_path = self.config.output_dir / kindle_name
            if prepared_source.suffix.lower() == ".epub":
                shutil.copy2(prepared_source, kindle_path)
            else:
                await convert_to_mobi(self.config.ebook_convert_bin, prepared_source, kindle_path)

            return output_path, kindle_path

    async def send_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
        if not self._is_allowed(update):
            await self._reject(update)
            return

        query = update.callback_query
        user = update.effective_user
        if not query or not user or not query.data:
            return

        await query.answer()
        if not query.data.startswith("send:"):
            return

        job_id = query.data.split(":", 1)[1]
        job = self.jobs.get(job_id)
        if not job or job.user_id != user.id or not job.kindle_path.exists():
            await query.edit_message_reply_markup(reply_markup=None)
            await query.message.reply_text("Этот файл уже недоступен. Пришлите книгу заново.")
            return

        kindle_email = self.storage.get_kindle_email(user.id)
        if not kindle_email:
            await query.message.reply_text("Сначала задайте Kindle email: /setemail name@kindle.com")
            return

        await query.message.reply_text(f"Отправляю на {kindle_email}...")
        try:
            await send_to_kindle(self.config, kindle_email, job.kindle_path)
        except MailError as exc:
            logging.exception("Failed to send book to Kindle")
            await query.message.reply_text(f"Не удалось отправить письмо: {exc}")
            return

        await query.edit_message_reply_markup(reply_markup=None)
        await query.message.reply_text("Отправил. Проверьте Kindle Library через несколько минут.")

    def _cleanup_old_jobs(self) -> None:
        cutoff = time.time() - JOB_TTL_SECONDS
        expired = [job_id for job_id, job in self.jobs.items() if job.created_at < cutoff]
        for job_id in expired:
            job = self.jobs.pop(job_id)
            try:
                job.path.unlink(missing_ok=True)
                job.kindle_path.unlink(missing_ok=True)
            except OSError:
                logging.warning("Failed to delete expired output file: %s", job.path)

    def _help_text(self, update: Update | None = None) -> str:
        parts = [HELP_TEXT, self._approved_sender_hint()]
        user = update.effective_user if update else None
        if user and self.config.allowed_user_ids and user.id not in self.config.allowed_user_ids:
            parts.append(
                "Ваш Telegram user id: "
                f"{user.id}\nПопросите владельца бота добавить его в ALLOWED_USER_IDS."
            )
        return "\n".join(parts)

    def _approved_sender_hint(self) -> str:
        if self.config.smtp_from:
            return (
                "Важно: чтобы книги доходили до Kindle, добавьте этот адрес в список "
                f"разрешенных отправителей Amazon: {self.config.smtp_from}"
            )
        return (
            "Важно: чтобы книги доходили до Kindle, адрес SMTP_FROM должен быть добавлен "
            "в список разрешенных отправителей Amazon."
        )

    def _is_allowed(self, update: Update) -> bool:
        user = update.effective_user
        if not user:
            return False
        return not self.config.allowed_user_ids or user.id in self.config.allowed_user_ids

    async def _reject(self, update: Update) -> None:
        user = update.effective_user
        if user:
            logging.warning("Rejected update from unauthorized user_id=%s", user.id)

        if update.callback_query:
            await update.callback_query.answer("Доступ запрещен.", show_alert=True)
            return

        if update.effective_message:
            await update.effective_message.reply_text("Доступ запрещен.")


def build_application(config: Config) -> Application:
    bot = KindleBot(config)
    app = Application.builder().token(config.telegram_bot_token).build()
    app.add_handler(CommandHandler("start", bot.start))
    app.add_handler(CommandHandler("help", bot.start))
    app.add_handler(CommandHandler("setemail", bot.set_email))
    app.add_handler(CommandHandler("email", bot.show_email))
    app.add_handler(CommandHandler("deleteemail", bot.delete_email))
    app.add_handler(CommandHandler("whoami", bot.whoami))
    app.add_handler(CallbackQueryHandler(bot.send_callback))
    app.add_handler(MessageHandler(filters.Document.ALL, bot.handle_document))
    return app


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    config = Config.from_env()
    app = build_application(config)
    app.run_polling(allowed_updates=Update.ALL_TYPES)
