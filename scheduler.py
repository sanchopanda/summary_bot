"""Scheduler for periodic summary sending."""
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
import asyncio


class SummaryScheduler:
    """Schedule periodic summary sending."""

    def __init__(self, bot_instance):
        self.bot = bot_instance
        self.scheduler = AsyncIOScheduler()

    def start(self):
        """Start the scheduler."""
        # Check for summaries every day at 12:00
        # The bot will determine which users need summaries based on their last_summary date
        self.scheduler.add_job(
            self.bot.send_scheduled_summaries,
            CronTrigger(hour=12, minute=0),  # Run every day at 12:00
            id='send_summaries',
            name='Send scheduled summaries',
            replace_existing=True
        )

        self.scheduler.start()
        print("✅ Scheduler started. Will send summaries daily at 12:00.")

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("❌ Scheduler stopped.")
