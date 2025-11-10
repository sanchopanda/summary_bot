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
from telegram.request import HTTPXRequest
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
        # Store user states for waiting input
        self.user_states = {}  # {user_id: "waiting_channel_name"}

    async def initialize(self):
        """Initialize bot and database."""
        await self.db.init_db()
        await self.channel_reader.start()

    async def shutdown(self):
        """Cleanup on shutdown."""
        await self.channel_reader.stop()

    def build_application(self) -> Application:
        """Build and configure the bot application."""
        # Configure request with increased timeouts for slow networks
        request = HTTPXRequest(
            connection_pool_size=8,
            connect_timeout=30.0,
            read_timeout=30.0,
            write_timeout=30.0,
            pool_timeout=30.0
        )

        self.application = (
            Application.builder()
            .token(config.BOT_TOKEN)
            .request(request)
            .build()
        )

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

        # Message handler for text input (must be last)
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))

        return self.application

    async def cmd_start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command."""
        user = update.effective_user
        await self.db.add_user(user.id, user.username, user.first_name)

        welcome_text = f"""👋 Привет, {user.first_name}!

Я помогу вам отслеживать Telegram каналы и создавать саммари сообщений.

**Как начать:**
1. Добавьте каналы: /add @channelname
2. Настройте период (по умолчанию раз в день)
3. Получайте автоматические саммари или запрашивайте вручную

⚠️ **Важно:** Для доступа к приватным каналам вы должны быть подписаны на них через тот же аккаунт, который используется для работы бота."""

        # Create main menu keyboard
        keyboard = [
            [
                InlineKeyboardButton("📋 Мои каналы", callback_data="menu_list"),
                InlineKeyboardButton("📊 Получить саммари", callback_data="menu_summary")
            ],
            [
                InlineKeyboardButton("⏰ Настроить период", callback_data="menu_period"),
                InlineKeyboardButton("❓ Помощь", callback_data="menu_help")
            ]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await update.message.reply_text(welcome_text, parse_mode='Markdown', reply_markup=reply_markup)

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

        # Send "checking" message
        msg = await update.message.reply_text(
            f"🔍 Проверяю доступ к каналу @{channel_username}..."
        )

        # Check channel access
        can_access, access_msg = await self.channel_reader.check_channel_access(channel_username)

        if not can_access:
            keyboard = [
                [InlineKeyboardButton("❓ Помощь", callback_data="menu_help")],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await msg.edit_text(access_msg, reply_markup=reply_markup)
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
            title_text = f" ({channel_title})" if channel_title else ""
            await msg.edit_text(
                f"✅ Канал @{channel_username}{title_text} добавлен в список отслеживания!",
                reply_markup=reply_markup
            )
        else:
            await msg.edit_text(
                f"⚠️ Канал @{channel_username} уже есть в вашем списке.",
                reply_markup=reply_markup
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

        # Build channel list
        channel_list = "📋 **Ваши отслеживаемые каналы:**\n\n"
        for username, title, added_at in channels:
            title_text = f" - {title}" if title else ""
            channel_list += f"• @{username}{title_text}\n"

        # Add current period
        period = await self.db.get_summary_period(user_id)
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

        await update.message.reply_text(channel_list, parse_mode='Markdown', reply_markup=reply_markup)

    async def cmd_set_period(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /period command to set summary period."""
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

        user_id = update.effective_user.id

        # Handle main menu
        if query.data == "menu_main":
            keyboard = [
                [
                    InlineKeyboardButton("📋 Мои каналы", callback_data="menu_list"),
                    InlineKeyboardButton("📊 Получить саммари", callback_data="menu_summary")
                ],
                [
                    InlineKeyboardButton("⏰ Настроить период", callback_data="menu_period"),
                    InlineKeyboardButton("❓ Помощь", callback_data="menu_help")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "🏠 **Главное меню**\n\n"
                "Выберите действие:",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

        # Handle list channels
        elif query.data == "menu_list":
            await self._show_channels_list(query, user_id)

        # Handle summary
        elif query.data == "menu_summary":
            await self._generate_summary_callback(query, user_id)

        # Handle period setting
        elif query.data == "menu_period":
            keyboard = [
                [InlineKeyboardButton("📅 Раз в день", callback_data="period_1")],
                [InlineKeyboardButton("📅 Раз в 3 дня", callback_data="period_3")],
                [InlineKeyboardButton("📅 Раз в неделю", callback_data="period_7")],
                [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "⏰ Выберите период автоматической отправки саммари:",
                reply_markup=reply_markup
            )

        # Handle help
        elif query.data == "menu_help":
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

**О приватных каналах:**
Чтобы бот мог читать приватные каналы, вы должны быть на них подписаны через тот же Telegram аккаунт, что используется ботом."""

            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                help_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

        # Handle add help
        elif query.data == "menu_add_help":
            add_help_text = """➕ **Как добавить канал**

Используйте команду:
`/add @channelname`

**Примеры:**
• `/add @durov`
• `/add @python_news`
• `/add channelname` (без @)

**Важно:**
• Для публичных каналов достаточно знать username
• Для приватных каналов вы должны быть на них подписаны
• Username канала обычно указан в описании канала"""

            keyboard = [
                [InlineKeyboardButton("✏️ Ввести username канала", callback_data="input_channel")],
                [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                add_help_text,
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

        # Handle input channel request
        elif query.data == "input_channel":
            # Set user state to waiting for channel name
            self.user_states[user_id] = "waiting_channel_name"

            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_input")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "✏️ Отправьте username канала, который хотите добавить.\n\n"
                "Например: `@durov` или `durov`\n\n"
                "Канал должен быть публичным или вы должны быть на него подписаны.",
                parse_mode='Markdown',
                reply_markup=reply_markup
            )

        # Handle cancel input
        elif query.data == "cancel_input":
            # Remove user state
            if user_id in self.user_states:
                del self.user_states[user_id]

            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ Добавление канала отменено.",
                reply_markup=reply_markup
            )

        # Handle period selection
        elif query.data.startswith("period_"):
            period_days = int(query.data.split("_")[1])

            await self.db.set_summary_period(user_id, period_days)

            period_text = {1: "раз в день", 3: "раз в 3 дня", 7: "раз в неделю"}[period_days]

            keyboard = [
                [
                    InlineKeyboardButton("📋 Мои каналы", callback_data="menu_list"),
                    InlineKeyboardButton("📊 Саммари", callback_data="menu_summary")
                ],
                [InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                f"✅ Период установлен: {period_text}\n\n"
                f"Вы будете получать автоматические саммари каждые {period_days} дней.",
                reply_markup=reply_markup
            )

    async def _show_channels_list(self, query, user_id: int):
        """Show user's channels list."""
        channels = await self.db.get_user_channels(user_id)

        if not channels:
            keyboard = [
                [InlineKeyboardButton("➕ Добавить канал", callback_data="menu_add_help")],
                [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "📭 У вас нет отслеживаемых каналов.\n"
                "Добавьте канал командой: /add @channelname",
                reply_markup=reply_markup
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

        # Create action buttons
        keyboard = [
            [
                InlineKeyboardButton("📊 Получить саммари", callback_data="menu_summary"),
                InlineKeyboardButton("⏰ Период", callback_data="menu_period")
            ],
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(channel_list, parse_mode='Markdown', reply_markup=reply_markup)

    async def _generate_summary_callback(self, query, user_id: int):
        """Generate summary from callback."""
        # Get user's channels
        channels = await self.db.get_user_channels(user_id)

        if not channels:
            keyboard = [
                [InlineKeyboardButton("➕ Добавить канал", callback_data="menu_add_help")],
                [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ У вас нет отслеживаемых каналов.\n"
                "Добавьте канал командой: /add @channelname",
                reply_markup=reply_markup
            )
            return

        # Get period
        period_days = await self.db.get_summary_period(user_id)

        # Update message to show progress
        await query.edit_message_text(
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

        # Create action buttons
        keyboard = [
            [
                InlineKeyboardButton("📋 Мои каналы", callback_data="menu_list"),
                InlineKeyboardButton("⏰ Период", callback_data="menu_period")
            ],
            [InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        # Send summary (delete old message and send new one)
        await query.message.delete()

        # Split if too long
        max_length = 4096 - 200  # Leave room for buttons
        if len(summary) <= max_length:
            await query.message.reply_text(summary, parse_mode='Markdown', reply_markup=reply_markup)
        else:
            # Split by channel separators
            parts = summary.split("─" * 50)
            for i, part in enumerate(parts):
                if i == len(parts) - 1:  # Last part gets buttons
                    await query.message.reply_text(part, parse_mode='Markdown', reply_markup=reply_markup)
                else:
                    await query.message.reply_text(part, parse_mode='Markdown')

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages when bot is waiting for input."""
        user_id = update.effective_user.id

        # Check if we're waiting for channel name from this user
        if user_id in self.user_states and self.user_states[user_id] == "waiting_channel_name":
            channel_username = update.message.text.strip().lstrip('@')

            # Clear user state
            del self.user_states[user_id]

            # Send "checking" message
            msg = await update.message.reply_text(
                f"🔍 Проверяю доступ к каналу @{channel_username}..."
            )

            # Check channel access
            can_access, access_msg = await self.channel_reader.check_channel_access(channel_username)

            if not can_access:
                keyboard = [
                    [InlineKeyboardButton("🔄 Попробовать снова", callback_data="input_channel")],
                    [InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                await msg.edit_text(access_msg, reply_markup=reply_markup)
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

            # Create action buttons
            keyboard = [
                [
                    InlineKeyboardButton("📋 Мои каналы", callback_data="menu_list"),
                    InlineKeyboardButton("📊 Саммари", callback_data="menu_summary")
                ],
                [
                    InlineKeyboardButton("➕ Добавить еще", callback_data="input_channel"),
                    InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if added:
                title_text = f" ({channel_title})" if channel_title else ""
                await msg.edit_text(
                    f"✅ Канал @{channel_username}{title_text} добавлен в список отслеживания!",
                    reply_markup=reply_markup
                )
            else:
                await msg.edit_text(
                    f"⚠️ Канал @{channel_username} уже есть в вашем списке.",
                    reply_markup=reply_markup
                )
        else:
            # User sent a message without context - show help
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "Используйте команды или кнопки для управления ботом.\n\n"
                "Нажмите на кнопку ниже или отправьте /help для справки.",
                reply_markup=reply_markup
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
