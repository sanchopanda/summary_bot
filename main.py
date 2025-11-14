"""Main entry point for the Telegram Summary Bot."""
import asyncio
import signal
import sys
import logging
from logging.handlers import RotatingFileHandler
from bot.core import SummaryBot
from scheduler import SummaryScheduler
import config


def setup_logging():
    """Setup logging configuration."""
    # Create logs directory if it doesn't exist
    import os
    os.makedirs('logs', exist_ok=True)

    # Configure logging format
    log_format = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    date_format = '%Y-%m-%d %H:%M:%S'

    # File handler with rotation
    file_handler = RotatingFileHandler(
        'logs/bot.log',
        maxBytes=10*1024*1024,  # 10MB
        backupCount=5,
        encoding='utf-8'
    )
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(logging.Formatter(log_format, date_format))

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(logging.Formatter(log_format, date_format))

    # Root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Suppress noisy loggers
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('telegram').setLevel(logging.WARNING)
    logging.getLogger('apscheduler').setLevel(logging.WARNING)

    logging.info("=" * 60)
    logging.info("Logging system initialized")
    logging.info("=" * 60)


async def main():
    """Main function to run the bot."""
    # Setup logging
    setup_logging()

    # Validate configuration
    try:
        config.validate_config()
    except ValueError as e:
        logging.error(f"Configuration error: {e}")
        sys.exit(1)

    # Create bot instance
    bot = SummaryBot()

    # Initialize bot and database
    logging.info("Initializing bot and database...")
    await bot.initialize()

    # Build application
    logging.info("Building bot application...")
    application = bot.build_application()

    # Create and start scheduler
    logging.info("Starting scheduler...")
    scheduler = SummaryScheduler(bot)
    scheduler.start()

    # Setup graceful shutdown
    def signal_handler(signum, frame):
        logging.info("Shutting down gracefully...")
        scheduler.stop()
        asyncio.create_task(bot.shutdown())
        asyncio.create_task(application.stop())
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start the bot
    logging.info("Bot is running! Press Ctrl+C to stop.")
    logging.info("=" * 60)

    # Run the bot with retry logic for initialization
    max_retries = 3
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            await application.initialize()
            break
        except Exception as e:
            if attempt < max_retries - 1:
                logging.warning(f"Connection failed (attempt {attempt + 1}/{max_retries}): {e}")
                logging.info(f"Retrying in {retry_delay} seconds...")
                await asyncio.sleep(retry_delay)
            else:
                logging.error(f"Failed to connect after {max_retries} attempts: {e}")
                logging.error("Possible solutions:")
                logging.error("  - Check your internet connection")
                logging.error("  - Verify BOT_TOKEN is correct in .env")
                logging.error("  - Check if Telegram API is accessible from your network")
                logging.error("  - Try using a VPN or proxy if Telegram is blocked")
                scheduler.stop()
                await bot.shutdown()
                sys.exit(1)

    await application.start()
    await application.updater.start_polling(
        allowed_updates=["message", "callback_query"]
    )

    # Keep the bot running
    try:
        await asyncio.Event().wait()
    except (KeyboardInterrupt, SystemExit):
        print("\n🛑 Received exit signal...")
    finally:
        scheduler.stop()
        await bot.shutdown()
        await application.stop()
        print("👋 Bot stopped.")


if __name__ == "__main__":
    asyncio.run(main())
