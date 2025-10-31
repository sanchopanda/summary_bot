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
        # Check for summaries every hour
        # The bot will determine which users need summaries based on their last_summary time
        self.scheduler.add_job(
            self.bot.send_scheduled_summaries,
            CronTrigger(minute=0),  # Run every hour at minute 0
            id='send_summaries',
            name='Send scheduled summaries',
            replace_existing=True
        )

        self.scheduler.start()
        print("✅ Scheduler started. Will check for summaries every hour.")

    def stop(self):
        """Stop the scheduler."""
        if self.scheduler.running:
            self.scheduler.shutdown()
            print("❌ Scheduler stopped.")
