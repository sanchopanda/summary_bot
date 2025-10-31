"""Telegram bot for managing channel summaries."""
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ContextTypes,
    MessageHandler,
    filters
)
from database import Database
from client import ChannelReader
from summarizer import Summarizer
import config


class SummaryBot:
    """Main bot class for handling commands and interactions."""

    def __init__(self):
        self.db = Database()
        self.channel_reader = ChannelReader()
        self.summarizer = Summarizer()
        self.application = None

    async def initialize(self):
        """Initialize bot and database."""
        await self.db.init_db()
        await self.channel_reader.start()

    async def shutdown(self):
        """Cleanup on shutdown."""
        await self.channel_reader.stop()

    def build_application(self) -> Application:
        """Build and configure the bot application."""
        self.application = Application.builder().token(config.BOT_TOKEN).build()

        # Command handlers
        self.application.add_handler(CommandHandler("start", self.cmd_start))
        self.application.add_handler(CommandHandler("help", self.cmd_help))
        self.application.add_handler(CommandHandler("add", self.cmd_add_channel))
        self.application.add_handler(CommandHandler("remove", self.cmd_remove_channel))
        self.application.add_handler(CommandHandler("list", self.cmd_list_channels))
        self.application.add_handler(CommandHandler("period", self.cmd_set_period))
        self.application.add_handler(CommandHandler("summary", self.cmd_manual_summary))

        # Callback query handler for inline buttons
        self.application.add_handler(CallbackQueryHandler(self.handle_callback))

        return self.application

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        await self.db.add_user(user.id, user.username, user.first_name)

        welcome_text = f"""👋 Привет, {user.first_name}!

Я помогу вам отслеживать Telegram каналы и создавать саммари сообщений.

**Основные команды:**
/add <@канал> - добавить канал для отслеживания
/remove <@канал> - удалить канал из отслеживания
/list - показать список отслеживаемых каналов
/period - настроить период отправки саммари
/summary - получить саммари сейчас
/help - показать помощь

**Как начать:**
1. Добавьте каналы: /add @channelname
2. Настройте период (по умолчанию раз в день): /period
3. Получайте автоматические саммари или запрашивайте вручную: /summary

⚠️ **Важно:** Для доступа к приватным каналам вы должны быть подписаны на них через тот же аккаунт, который используется для работы бота."""

        await update.message.reply_text(welcome_text, parse_mode='Markdown')

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        help_text = """📖 **Справка по командам**

**/add <@канал>**
Добавить канал в список отслеживания.
Пример: `/add @durov`

**/remove <@канал>**
Удалить канал из списка.
Пример: `/remove @durov`

**/list**
Показать все отслеживаемые каналы.

**/period**
Выбрать период автоматической отправки саммари:
• Раз в день (по умолчанию)
• Раз в 3 дня
• Раз в неделю

**/summary**
Получить саммари по всем каналам прямо сейчас.

**/help**
Показать эту справку.

**О приватных каналах:**
Чтобы бот мог читать приватные каналы, вы должны быть на них подписаны через тот же Telegram аккаунт, что используется ботом."""

        await update.message.reply_text(help_text, parse_mode='Markdown')

    async def cmd_add_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add command to add a channel."""
        user_id = update.effective_user.id

        if not context.args:
            await update.message.reply_text(
                "❌ Укажите username канала.\n"
                "Использование: /add @channelname или /add channelname"
            )
            return

        channel_username = context.args[0].lstrip('@')

        # Send "checking" message
        msg = await update.message.reply_text(
            f"🔍 Проверяю доступ к каналу @{channel_username}..."
        )

        # Check channel access
        can_access, access_msg = await self.channel_reader.check_channel_access(channel_username)

        if not can_access:
            await msg.edit_text(access_msg)
            return

        # Get channel info
        channel_info = await self.channel_reader.get_channel_info(channel_username)

        if channel_info:
            channel_id, channel_title = channel_info
        else:
            channel_id, channel_title = None, None

        # Add to database
        added = await self.db.add_channel(
            user_id,
            channel_username,
            channel_id,
            channel_title
        )

        if added:
            title_text = f" ({channel_title})" if channel_title else ""
            await msg.edit_text(
                f"✅ Канал @{channel_username}{title_text} добавлен в список отслеживания!"
            )
        else:
            await msg.edit_text(
                f"⚠️ Канал @{channel_username} уже есть в вашем списке."
            )

    async def cmd_remove_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /remove command to remove a channel."""
        user_id = update.effective_user.id

        if not context.args:
            await update.message.reply_text(
                "❌ Укажите username канала.\n"
                "Использование: /remove @channelname или /remove channelname"
            )
            return

        channel_username = context.args[0].lstrip('@')

        removed = await self.db.remove_channel(user_id, channel_username)

        if removed:
            await update.message.reply_text(
                f"✅ Канал @{channel_username} удален из списка отслеживания."
            )
        else:
            await update.message.reply_text(
                f"⚠️ Канал @{channel_username} не найден в вашем списке."
            )

    async def cmd_list_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list command to show all tracked channels."""
        user_id = update.effective_user.id

        channels = await self.db.get_user_channels(user_id)

        if not channels:
            await update.message.reply_text(
                "📭 У вас нет отслеживаемых каналов.\n"
                "Добавьте канал командой: /add @channelname"
            )
            return

        # Build channel list
        channel_list = "📋 **Ваши отслеживаемые каналы:**\n\n"
        for username, title, added_at in channels:
            title_text = f" - {title}" if title else ""
            channel_list += f"• @{username}{title_text}\n"

        # Add current period
        period = await self.db.get_summary_period(user_id)
        period_text = {1: "раз в день", 3: "раз в 3 дня", 7: "раз в неделю"}.get(period, f"раз в {period} дней")

        channel_list += f"\n⏰ Период отправки саммари: {period_text}"
        channel_list += f"\n\n💡 Используйте /summary для получения саммари сейчас"

        await update.message.reply_text(channel_list, parse_mode='Markdown')

    async def cmd_set_period(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /period command to set summary period."""
        keyboard = [
            [InlineKeyboardButton("📅 Раз в день", callback_data="period_1")],
            [InlineKeyboardButton("📅 Раз в 3 дня", callback_data="period_3")],
            [InlineKeyboardButton("📅 Раз в неделю", callback_data="period_7")],
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "⏰ Выберите период автоматической отправки саммари:",
            reply_markup=reply_markup
        )

    async def cmd_manual_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /summary command to generate summary manually."""
        user_id = update.effective_user.id

        # Get user's channels
        channels = await self.db.get_user_channels(user_id)

        if not channels:
            await update.message.reply_text(
                "❌ У вас нет отслеживаемых каналов.\n"
                "Добавьте канал командой: /add @channelname"
            )
            return

        # Get period
        period_days = await self.db.get_summary_period(user_id)

        # Send "generating" message
        msg = await update.message.reply_text(
            f"⏳ Собираю сообщения за последние {period_days} дней и генерирую саммари..."
        )

        # Read messages from all channels
        channel_usernames = [username for username, _, _ in channels]
        channels_messages = await self.channel_reader.read_multiple_channels(
            channel_usernames,
            days=period_days
        )

        # Generate summary
        summary = self.summarizer.generate_multi_channel_summary(channels_messages)

        # Update last summary time
        await self.db.update_last_summary(user_id)

        # Send summary (split if too long)
        await self._send_long_message(update, summary)
        await msg.delete()

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline buttons."""
        query = update.callback_query
        await query.answer()

        # Handle period selection
        if query.data.startswith("period_"):
            period_days = int(query.data.split("_")[1])
            user_id = update.effective_user.id

            await self.db.set_summary_period(user_id, period_days)

            period_text = {1: "раз в день", 3: "раз в 3 дня", 7: "раз в неделю"}[period_days]

            await query.edit_message_text(
                f"✅ Период установлен: {period_text}\n\n"
                f"Вы будете получать автоматические саммари каждые {period_days} дней."
            )

    async def _send_long_message(self, update: Update, text: str):
        """Send a long message, splitting it if necessary."""
        max_length = 4096

        if len(text) <= max_length:
            await update.message.reply_text(text, parse_mode='Markdown')
        else:
            # Split by channel separators
            parts = text.split("─" * 50)
            current_part = ""

            for part in parts:
                if len(current_part) + len(part) + 50 < max_length:
                    current_part += part + "\n" + "─" * 50 + "\n"
                else:
                    if current_part:
                        await update.message.reply_text(current_part, parse_mode='Markdown')
                    current_part = part + "\n" + "─" * 50 + "\n"

            if current_part:
                await update.message.reply_text(current_part, parse_mode='Markdown')

    async def send_scheduled_summaries(self):
        """Send summaries to all users who need them (called by scheduler)."""
        users = await self.db.get_users_for_summary()

        for user_id, period_days, last_summary in users:
            try:
                # Get user's channels
                channels = await self.db.get_user_channels(user_id)

                if not channels:
                    continue

                # Read messages
                channel_usernames = [username for username, _, _ in channels]
                channels_messages = await self.channel_reader.read_multiple_channels(
                    channel_usernames,
                    days=period_days
                )

                # Generate summary
                summary = self.summarizer.generate_multi_channel_summary(channels_messages)

                # Send to user
                await self.application.bot.send_message(
                    chat_id=user_id,
                    text=f"🤖 **Автоматическое саммари**\n\n{summary}",
                    parse_mode='Markdown'
                )

                # Update last summary time
                await self.db.update_last_summary(user_id)

            except Exception as e:
                print(f"Error sending summary to user {user_id}: {e}")
