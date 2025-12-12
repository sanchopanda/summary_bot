"""Main bot class for the Telegram Summary Bot."""
import logging
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters
)
from telegram.request import HTTPXRequest
from database import Database
from client import ChannelReader
import config
from .summarizer import Summarizer
from .commands import CommandHandlers
from .callbacks import CallbackHandlers
from .messages import MessageHandlers
from .helpers import create_summary_logger, cleanup_summary_logger


logger = logging.getLogger(__name__)


class SummaryBot:
    """Main bot class for handling commands and interactions."""

    def __init__(self):
        self.db = Database()
        self.channel_reader = ChannelReader()
        self.summarizer = Summarizer()
        self.application = None
        # Store user states for waiting input
        self.user_states = {}  # {user_id: "waiting_channel_name"}

        # Initialize handlers
        self.command_handlers = CommandHandlers(self)
        self.callback_handlers = CallbackHandlers(self)
        self.message_handlers = MessageHandlers(self)

        logger.info("SummaryBot instance created")

    async def initialize(self):
        """Initialize bot and database."""
        logger.info("Initializing database and channel reader...")
        await self.db.init_db()
        await self.channel_reader.start()
        logger.info("Bot initialization complete")

    async def shutdown(self):
        """Cleanup on shutdown."""
        logger.info("Shutting down bot...")
        await self.channel_reader.stop()
        logger.info("Bot shutdown complete")

    def build_application(self) -> Application:
        """Build and configure the bot application."""
        logger.info("Building bot application...")

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
        self.application.add_handler(CommandHandler("start", self.command_handlers.cmd_start))
        self.application.add_handler(CommandHandler("help", self.command_handlers.cmd_help))
        self.application.add_handler(CommandHandler("add", self.command_handlers.cmd_add_channel))
        self.application.add_handler(CommandHandler("remove", self.command_handlers.cmd_remove_channel))
        self.application.add_handler(CommandHandler("list", self.command_handlers.cmd_list_channels))
        self.application.add_handler(CommandHandler("period", self.command_handlers.cmd_set_period))
        self.application.add_handler(CommandHandler("summary", self.command_handlers.cmd_manual_summary))

        # Callback query handler for inline buttons
        self.application.add_handler(CallbackQueryHandler(self.callback_handlers.handle_callback))

        # Message handler for text input (must be last)
        self.application.add_handler(MessageHandler(
            filters.TEXT & ~filters.COMMAND,
            self.message_handlers.handle_text_message
        ))

        logger.info("Bot application built successfully")
        return self.application

    async def send_scheduled_summaries(self):
        """Send summaries to all users who need them (called by scheduler)."""
        logger.info("Starting scheduled summaries job...")
        users = await self.db.get_users_for_summary()
        logger.info(f"Found {len(users)} users needing summaries")

        success_count = 0
        error_count = 0

        for user_id, username, period_days, last_summary in users:
            try:
                logger.info(f"Generating scheduled summary for user {user_id} (@{username}), period: {period_days} days")

                # Get user's channels
                channels = await self.db.get_user_channels(user_id)

                if not channels:
                    logger.warning(f"User {user_id} (@{username}) has no channels, skipping")
                    continue

                channel_list = [ch[0] for ch in channels]

                # Create dedicated logger for this scheduled summary
                request_logger, file_handler, log_filename = create_summary_logger(user_id, f"{username}_scheduled")

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

                    request_logger.info(f"SCHEDULED summary for user {user_id}, {len(channel_list)} channels ({', '.join(['@'+ch for ch in channel_list])}), period: {period_days} days")
                    logger.info(f"User {user_id} channels: {', '.join(['@'+ch for ch in channel_list])} | Log: {log_filename}")

                    # Read messages
                    channel_usernames = [username for username, _, _ in channels]
                    channels_messages = await self.channel_reader.read_multiple_channels(
                        channel_usernames,
                        days=period_days
                    )

                    # Generate summary (with user_id for logging)
                    summary = self.summarizer.generate_multi_channel_summary(channels_messages, user_id=user_id)

                    # Send to user
                    await self.application.bot.send_message(
                        chat_id=user_id,
                        text=f"🤖 <b>Автоматическое саммари</b>\n\n{summary}",
                        parse_mode='HTML'
                    )

                    # Update last summary time
                    await self.db.update_last_summary(user_id)

                    request_logger.info(f"Scheduled summary sent successfully to user {user_id}")
                    logger.info(f"Scheduled summary sent successfully to user {user_id}")
                    success_count += 1

                finally:
                    # Clean up logger and restore original levels
                    summarizer_logger.removeHandler(file_handler)
                    client_logger.removeHandler(file_handler)
                    summarizer_logger.setLevel(original_summarizer_level)
                    client_logger.setLevel(original_client_level)
                    cleanup_summary_logger(request_logger, file_handler)

            except Exception as e:
                logger.error(f"Error sending summary to user {user_id}: {e}", exc_info=True)
                error_count += 1

        logger.info(f"Scheduled summaries job complete: {success_count} success, {error_count} errors")
