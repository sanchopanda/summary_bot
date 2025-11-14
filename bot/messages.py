"""Text message handlers for the bot."""
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from .helpers import escape_html


logger = logging.getLogger(__name__)


class MessageHandlers:
    """Handles text messages."""

    def __init__(self, bot):
        """Initialize message handlers with bot instance."""
        self.bot = bot

    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages when bot is waiting for input."""
        user_id = update.effective_user.id
        username = update.effective_user.username

        # Check if we're waiting for channel name from this user
        if user_id in self.bot.user_states and self.bot.user_states[user_id] == "waiting_channel_name":
            channel_username = update.message.text.strip().lstrip('@')
            logger.info(f"User {user_id} (@{username}) entered channel username: @{channel_username}")

            # Clear user state
            del self.bot.user_states[user_id]

            # Send "checking" message
            msg = await update.message.reply_text(
                f"🔍 Проверяю доступ к каналу @{channel_username}..."
            )

            # Check channel access
            can_access, access_msg = await self.bot.channel_reader.check_channel_access(channel_username)

            if not can_access:
                logger.warning(f"User {user_id} cannot access entered channel @{channel_username}: {access_msg}")
                keyboard = [
                    [InlineKeyboardButton("🔄 Попробовать снова", callback_data="input_channel")],
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
                [
                    InlineKeyboardButton("➕ Добавить еще", callback_data="input_channel"),
                    InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)

            if added:
                logger.info(f"User {user_id} successfully added channel @{channel_username} via text input (title: {channel_title})")
                title_text = f" ({escape_html(channel_title)})" if channel_title else ""
                await msg.edit_text(
                    f"✅ Канал @{channel_username}{title_text} добавлен в список отслеживания!",
                    reply_markup=reply_markup
                )
            else:
                logger.info(f"User {user_id} tried to add duplicate channel @{channel_username} via text input")
                await msg.edit_text(
                    f"⚠️ Канал @{channel_username} уже есть в вашем списке.",
                    reply_markup=reply_markup
                )
        else:
            # User sent a message without context - show help
            logger.info(f"User {user_id} (@{username}) sent unexpected message: {update.message.text[:50]}")
            keyboard = [[InlineKeyboardButton("🏠 Главное меню", callback_data="menu_main")]]
            reply_markup = InlineKeyboardMarkup(keyboard)

            await update.message.reply_text(
                "Используйте команды или кнопки для управления ботом.\n\n"
                "Нажмите на кнопку ниже или отправьте /help для справки.",
                reply_markup=reply_markup
            )
