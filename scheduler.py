from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from database import Database
from selenium_service import SeleniumService
from config import SCHEDULER_TIMEZONE
import logging
import asyncio
from aiogram import Bot
from config import BOT_TOKEN

logger = logging.getLogger(__name__)

class SchedulerService:
    def __init__(self, loop=None):
        self.scheduler = BackgroundScheduler(timezone=SCHEDULER_TIMEZONE)
        self.db = Database()
        self.selenium = SeleniumService()
        self.bot = Bot(token=BOT_TOKEN)
        self.loop = loop
        self.scheduler.start()

        if self.loop is not None:
            self.load_jobs()

    def load_jobs(self):
        users = self.db.get_all_users()
        for user in users:
            if user['auto_enabled']:
                self.add_user_jobs(user)

    def add_user_jobs(self, user):
        user_id = user['user_id']
        times = user['login_times']
        for time_str in times:
            # 'HH:MM'
            hour, minute = map(int, time_str.split(':'))
            job_id = f"{user_id}_{time_str}"
            self.scheduler.add_job(
                self._job_wrapper,
                trigger=CronTrigger(hour=hour, minute=minute),
                id=job_id,
                args=[user_id],
                replace_existing=True
            )

    def _job_wrapper(self, user_id):
        if not self.loop:
            logger.error('No asyncio loop set for SchedulerService; cannot run job')
            return
        try:
            asyncio.run_coroutine_threadsafe(self.perform_login_for_user(user_id), self.loop)
        except Exception as e:
            logger.exception(f'Failed to submit job coroutine for user {user_id}: {e}')

    def remove_user_jobs(self, user_id):
        jobs = [job for job in self.scheduler.get_jobs() if str(user_id) in job.id]
        for job in jobs:
            job.remove()

    def update_user_schedule(self, user_id):
        self.remove_user_jobs(user_id)
        user = self.db.get_user(user_id)
        if user and user['auto_enabled']:
            self.add_user_jobs(user)

    async def perform_login_for_user(self, user_id):
        user = self.db.get_user(user_id)
        if not user:
            return
        success, message = self.selenium.perform_login(user['moodle_login'], user['moodle_password'])
        if success:
            await self.bot.send_message(chat_id=user_id, text="✅ Автоматический вход выполнен успешно")
        else:
            await self.bot.send_message(chat_id=user_id, text=f"❌ Ошибка автоматического входа: {message}")
        logger.info(f"Auto login for user {user_id}: {message}")