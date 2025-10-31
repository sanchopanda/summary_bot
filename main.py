"""Main entry point for the Telegram Summary Bot."""
import asyncio
import signal
import sys
from bot import SummaryBot
from scheduler import SummaryScheduler
import config


async def main():
    """Main function to run the bot."""
    # Validate configuration
    try:
        config.validate_config()
    except ValueError as e:
        print(f"❌ Configuration error: {e}")
        sys.exit(1)

    # Create bot instance
    bot = SummaryBot()

    # Initialize bot and database
    print("🔧 Initializing bot and database...")
    await bot.initialize()

    # Build application
    print("🤖 Building bot application...")
    application = bot.build_application()

    # Create and start scheduler
    print("⏰ Starting scheduler...")
    scheduler = SummaryScheduler(bot)
    scheduler.start()

    # Setup graceful shutdown
    def signal_handler(signum, frame):
        print("\n🛑 Shutting down gracefully...")
        scheduler.stop()
        asyncio.create_task(bot.shutdown())
        asyncio.create_task(application.stop())
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # Start the bot
    print("✅ Bot is running! Press Ctrl+C to stop.")
    print("=" * 60)

    # Run the bot
    await application.initialize()
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
