"""Command handlers for the bot."""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .helpers import escape_html, send_long_message


logger = logging.getLogger(__name__)


class CommandHandlers:
    """Handles all bot commands."""

    def __init__(self, bot):
        """Initialize command handlers with bot instance."""
        self.bot = bot

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        logger.info(f"User {user.id} (@{user.username}) started the bot")

        await self.bot.db.add_user(user.id, user.username, user.first_name)

        welcome_text = f"""👋 Привет, {user.first_name}!

Я помогу вам отслеживать Telegram каналы и создавать саммари сообщений.

<b>Как начать:</b>
1. Добавьте каналы: /add @channelname
2. Настройте период (по умолчанию раз в день)
3. Получайте автоматические саммари или запрашивайте вручную

⚠️ <b>Приватные каналы не поддерживаются</b>"""

        # Create main menu keyboard
        keyboard = [
            [
                InlineKeyboardButton("📋 Мои каналы", callback_data="menu_list"),
                InlineKeyboardButton("➕ Добавить канал", callback_data="menu_add_help")
            ],
            [
                InlineKeyboardButton("📊 Получить саммари", callback_data="menu_summary"),
                InlineKeyboardButton("⏰ Настроить период", callback_data="menu_period")
            ],
            [
                InlineKeyboardButton("❓ Помощь", callback_data="menu_help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(welcome_text, parse_mode='HTML', reply_markup=reply_markup)

    async def cmd_help(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /help command."""
        user = update.effective_user
        logger.info(f"User {user.id} (@{user.username}) requested help")

        help_text = """📖 <b>Справка по командам</b>

<b>/add &lt;@канал&gt;</b>
Добавить канал в список отслеживания.
Пример: <code>/add @durov</code>

<b>/remove &lt;@канал&gt;</b>
Удалить канал из списка.
Пример: <code>/remove @durov</code>

<b>/list</b>
Показать все отслеживаемые каналы.

<b>/period</b>
Выбрать период автоматической отправки саммари:
• Раз в день (по умолчанию)
• Раз в 3 дня
• Раз в неделю

<b>/summary</b>
Получить саммари по всем каналам прямо сейчас.

<b>/help</b>
Показать эту справку.

<b>О приватных каналах:</b>
Чтобы бот мог читать приватные каналы, вы должны быть на них подписаны через тот же Telegram аккаунт, что используется ботом."""

        await update.message.reply_text(help_text, parse_mode='HTML')

    async def cmd_add_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /add command to add a channel."""
        user_id = update.effective_user.id
        username = update.effective_user.username

        if not context.args:
            logger.info(f"User {user_id} (@{username}) tried /add without arguments")
            keyboard = [
                [InlineKeyboardButton("❓ Как добавить канал?", callback_data="menu_add_help")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "❌ Укажите username канала.\n"
                "Использование: /add @channelname или /add channelname",
                reply_markup=reply_markup
            )
            return

        channel_username = context.args[0].lstrip('@')
        logger.info(f"User {user_id} (@{username}) attempting to add channel @{channel_username}")

        # Send "checking" message
        msg = await update.message.reply_text(
            f"🔍 Проверяю доступ к каналу @{channel_username}..."
        )

        # Check channel access
        can_access, access_msg = await self.bot.channel_reader.check_channel_access(channel_username)

        if not can_access:
            logger.warning(f"User {user_id} cannot access channel @{channel_username}: {access_msg}")
            keyboard = [
                [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await msg.edit_text(access_msg, reply_markup=reply_markup)
            return

        # Get channel info
        channel_info = await self.bot.channel_reader.get_channel_info(channel_username)

        if channel_info:
            channel_id, channel_title = channel_info
        else:
            channel_id, channel_title = None, None

        # Add to database
        added = await self.bot.db.add_channel(
            user_id,
            channel_username,
            channel_id,
            channel_title
        )

        # Create action buttons
        keyboard = [
            [
                InlineKeyboardButton("📋 Мои каналы", callback_data="menu_list"),
                InlineKeyboardButton("📊 Саммари", callback_data="menu_summary")
            ],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        if added:
            logger.info(f"User {user_id} successfully added channel @{channel_username} (title: {channel_title})")
            title_text = f" ({escape_html(channel_title)})" if channel_title else ""
            await msg.edit_text(
                f"✅ Канал @{channel_username}{title_text} добавлен в список отслеживания!",
                reply_markup=reply_markup
            )
        else:
            logger.info(f"User {user_id} tried to add duplicate channel @{channel_username}")
            await msg.edit_text(
                f"⚠️ Канал @{channel_username} уже есть в вашем списке.",
                reply_markup=reply_markup
            )

    async def cmd_remove_channel(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /remove command to remove a channel."""
        user_id = update.effective_user.id
        username = update.effective_user.username

        if not context.args:
            logger.info(f"User {user_id} (@{username}) tried /remove without arguments")
            await update.message.reply_text(
                "❌ Укажите username канала.\n"
                "Использование: /remove @channelname или /remove channelname"
            )
            return

        channel_username = context.args[0].lstrip('@')
        logger.info(f"User {user_id} (@{username}) attempting to remove channel @{channel_username}")

        removed = await self.bot.db.remove_channel(user_id, channel_username)

        if removed:
            logger.info(f"User {user_id} successfully removed channel @{channel_username}")
            await update.message.reply_text(
                f"✅ Канал @{channel_username} удален из списка отслеживания."
            )
        else:
            logger.warning(f"User {user_id} tried to remove non-existent channel @{channel_username}")
            await update.message.reply_text(
                f"⚠️ Канал @{channel_username} не найден в вашем списке."
            )

    async def cmd_list_channels(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /list command to show all tracked channels."""
        user_id = update.effective_user.id
        username = update.effective_user.username
        logger.info(f"User {user_id} (@{username}) requested channel list")

        channels = await self.bot.db.get_user_channels(user_id)

        if not channels:
            logger.info(f"User {user_id} has no channels")
            keyboard = [
                [InlineKeyboardButton("➕ Добавить канал", callback_data="menu_add_help")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "📭 У вас нет отслеживаемых каналов.\n"
                "Добавьте канал командой: /add @channelname",
                reply_markup=reply_markup
            )
            return

        logger.info(f"User {user_id} has {len(channels)} channels")

        # Build channel list
        channel_list = "📋 <b>Ваши отслеживаемые каналы:</b>\n\n"
        for channel_username, title, added_at in channels:
            # Escape HTML special characters in title
            title_text = f" - {escape_html(title)}" if title else ""
            channel_list += f"• @{channel_username}{title_text}\n"

        # Add current period
        period = await self.bot.db.get_summary_period(user_id)
        period_text = {1: "раз в день", 3: "раз в 3 дня", 7: "раз в неделю"}.get(period, f"раз в {period} дней")

        channel_list += f"\n⏰ Период отправки саммари: {period_text}"

        # Create action buttons
        keyboard = [
            [
                InlineKeyboardButton("📊 Получить саммари", callback_data="menu_summary"),
                InlineKeyboardButton("⏰ Период", callback_data="menu_period")
            ],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(channel_list, parse_mode='HTML', reply_markup=reply_markup)

    async def cmd_set_period(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /period command to set summary period."""
        user = update.effective_user
        logger.info(f"User {user.id} (@{user.username}) opened period settings")

        keyboard = [
            [InlineKeyboardButton("📅 Раз в день", callback_data="period_1")],
            [InlineKeyboardButton("📅 Раз в 3 дня", callback_data="period_3")],
            [InlineKeyboardButton("📅 Раз в неделю", callback_data="period_7")],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(
            "⏰ Выберите период автоматической отправки саммари:",
            reply_markup=reply_markup
        )

    async def cmd_manual_summary(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /summary command to generate summary manually."""
        user_id = update.effective_user.id
        username = update.effective_user.username
        logger.info(f"User {user_id} (@{username}) requested manual summary")

        # Get user's channels
        channels = await self.bot.db.get_user_channels(user_id)

        if not channels:
            logger.warning(f"User {user_id} requested summary but has no channels")
            await update.message.reply_text(
                "❌ У вас нет отслеживаемых каналов.\n"
                "Добавьте канал командой: /add @channelname"
            )
            return

        # Get period
        period_days = await self.bot.db.get_summary_period(user_id)
        channel_list = [ch[0] for ch in channels]

        logger.info(f"User {user_id} generating summary for {len(channel_list)} channels ({', '.join(['@'+ch for ch in channel_list])}), period: {period_days} days")

        # Send "generating" message
        msg = await update.message.reply_text(
            f"⏳ Собираю сообщения за последние {period_days} дней и генерирую саммари..."
        )

        # Read messages from all channels
        channel_usernames = [uname for uname, _, _ in channels]
        channels_messages = await self.bot.channel_reader.read_multiple_channels(
            channel_usernames,
            days=period_days
        )

        # Generate summary (with user_id for logging)
        summary = self.bot.summarizer.generate_multi_channel_summary(channels_messages, user_id=user_id)

        # Update last summary time
        await self.bot.db.update_last_summary(user_id)

        logger.info(f"User {user_id} summary generated successfully")

        # Send summary (split if too long)
        await send_long_message(update, summary)
        await msg.delete()
