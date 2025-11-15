"""Callback query handlers for the bot."""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from telegram.error import BadRequest
from .helpers import escape_html, fix_html_tags, _strip_html_tags, create_summary_logger, cleanup_summary_logger


logger = logging.getLogger(__name__)


class CallbackHandlers:
    """Handles all callback queries."""

    def __init__(self, bot):
        """Initialize callback handlers with bot instance."""
        self.bot = bot

    async def handle_callback(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle callback queries from inline buttons."""
        query = update.callback_query
        await query.answer()

        user_id = update.effective_user.id
        username = update.effective_user.username
        action = query.data

        logger.info(f"User {user_id} (@{username}) clicked button: {action}")

        # Handle main menu
        if action == "menu_main":
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

            await query.edit_message_text(
                "🏠 <b>Главное меню</b>\n\n"
                "Выберите действие:",
                parse_mode='HTML',
                reply_markup=reply_markup
            )

        # Handle list channels
        elif action == "menu_list":
            await self._show_channels_list(query, user_id)

        # Handle summary
        elif action == "menu_summary":
            await self._generate_summary_callback(query, user_id, username)

        # Handle period setting
        elif action == "menu_period":
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
        elif action == "menu_help":
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

<b>О приватных каналах:</b>
Чтобы бот мог читать приватные каналы, вы должны быть на них подписаны через тот же Telegram аккаунт, что используется ботом."""

            keyboard = [[InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                help_text,
                parse_mode='HTML',
                reply_markup=reply_markup
            )

        # Handle add help
        elif action == "menu_add_help":
            add_help_text = """➕ <b>Как добавить канал</b>

Используйте команду:
<code>/add @channelname</code>

<b>Примеры:</b>
• <code>/add @durov</code>
• <code>/add @python_news</code>
• <code>/add channelname</code> (без @)

<b>Важно:</b>
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
                parse_mode='HTML',
                reply_markup=reply_markup
            )

        # Handle input channel request
        elif action == "input_channel":
            # Set user state to waiting for channel name
            self.bot.user_states[user_id] = "waiting_channel_name"
            logger.info(f"User {user_id} entered channel input mode")

            keyboard = [[InlineKeyboardButton("❌ Отмена", callback_data="cancel_input")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "✏️ Отправьте username канала, который хотите добавить.\n\n"
                "Например: <code>@durov</code> или <code>durov</code>\n\n"
                "Канал должен быть публичным",
                parse_mode='HTML',
                reply_markup=reply_markup
            )

        # Handle cancel input
        elif action == "cancel_input":
            # Remove user state
            if user_id in self.bot.user_states:
                del self.bot.user_states[user_id]
            logger.info(f"User {user_id} cancelled channel input")

            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await query.edit_message_text(
                "❌ Добавление канала отменено.",
                reply_markup=reply_markup
            )

        # Handle period selection
        elif action.startswith("period_"):
            period_days = int(action.split("_")[1])
            logger.info(f"User {user_id} (@{username}) set period to {period_days} days")

            await self.bot.db.set_summary_period(user_id, period_days)

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
        channels = await self.bot.db.get_user_channels(user_id)

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
        channel_list = "📋 <b>Ваши отслеживаемые каналы:</b>\n\n"
        for channel_username, title, added_at in channels:
            # Format: Title - link
            # Clean username from @ prefix
            clean_username = channel_username.replace('@', '').replace('https://t.me/', '').replace('http://t.me/', '').strip('/')
            channel_url = f"https://t.me/{clean_username}"

            # Use title as display text, fallback to username if no title
            display_name = escape_html(title) if title else f"@{clean_username}"

            # Format: • Title - link
            channel_list += f"• {display_name} - <a href='{channel_url}'>перейти к каналу</a>\n"

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
            [InlineKeyboardButton("🔙 Назад", callback_data="menu_main")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)

        await query.edit_message_text(channel_list, parse_mode='HTML', reply_markup=reply_markup)

    async def _generate_summary_callback(self, query, user_id: int, username: str):
        """Generate summary from callback."""
        # Get user's channels
        channels = await self.bot.db.get_user_channels(user_id)

        if not channels:
            logger.warning(f"User {user_id} requested summary but has no channels")
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
        period_days = await self.bot.db.get_summary_period(user_id)
        channel_list = [ch[0] for ch in channels]

        # Create dedicated logger for this summary request
        request_logger, file_handler, log_filename = create_summary_logger(user_id, username)

        try:
            # Add handler to summarizer and client loggers to capture their logs
            summarizer_logger = logging.getLogger('bot.summarizer')
            client_logger = logging.getLogger('client')

            # Temporarily set to DEBUG to capture detailed logs in per-request file
            original_summarizer_level = summarizer_logger.level
            original_client_level = client_logger.level
            summarizer_logger.setLevel(logging.DEBUG)
            client_logger.setLevel(logging.DEBUG)

            summarizer_logger.addHandler(file_handler)
            client_logger.addHandler(file_handler)

            request_logger.info(f"User {user_id} (@{username}) generating summary for {len(channel_list)} channels ({', '.join(['@'+ch for ch in channel_list])}), period: {period_days} days")
            logger.info(f"User {user_id} (@{username}) generating summary for {len(channel_list)} channels ({', '.join(['@'+ch for ch in channel_list])}), period: {period_days} days | Log: {log_filename}")

            # Update message to show progress
            await query.edit_message_text(
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

            request_logger.info(f"User {user_id} summary generated successfully")
            logger.info(f"User {user_id} summary generated successfully")
        finally:
            # Clean up logger and restore original levels
            summarizer_logger.removeHandler(file_handler)
            client_logger.removeHandler(file_handler)
            summarizer_logger.setLevel(original_summarizer_level)
            client_logger.setLevel(original_client_level)
            cleanup_summary_logger(request_logger, file_handler)

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

        # Fix any unclosed HTML tags before sending
        summary = fix_html_tags(summary)

        try:
            # Split if too long
            max_length = 4096 - 200  # Leave room for buttons
            if len(summary) <= max_length:
                await query.message.reply_text(summary, parse_mode='HTML', reply_markup=reply_markup)
            else:
                # Split by channel separators
                parts = [p.strip() for p in summary.split("─" * 50) if p.strip()]
                for i, part in enumerate(parts):
                    if i == len(parts) - 1:  # Last part gets buttons
                        await query.message.reply_text(part, parse_mode='HTML', reply_markup=reply_markup)
                    else:
                        await query.message.reply_text(part, parse_mode='HTML')
        except BadRequest as e:
            # If Telegram rejects HTML even after fixing, fall back to plain text
            if "Can't parse entities" in str(e):
                logger.error(f"HTML parsing failed even after fixing, falling back to plain text: {e}")
                summary = _strip_html_tags(summary)

                # Retry sending as plain text (without parse_mode)
                if len(summary) <= max_length:
                    await query.message.reply_text(summary, reply_markup=reply_markup)
                else:
                    parts = [p.strip() for p in summary.split("─" * 50) if p.strip()]
                    for i, part in enumerate(parts):
                        if i == len(parts) - 1:
                            await query.message.reply_text(part, reply_markup=reply_markup)
                        else:
                            await query.message.reply_text(part)
            else:
                # Re-raise if it's a different error
                raise
