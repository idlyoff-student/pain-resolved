import os

BOT_TOKEN = os.getenv('BOT_TOKEN', '')

MOODLE_LOGIN_URL = ''
MOODLE_MY_URL = ''

DATABASE_PATH = 'moodle_bot.db'

TIMEZONE = 'Europe/Moscow'

LOG_LEVEL = 'INFO'
LOG_FILE = 'bot.log'

CHROME_DRIVER_PATH = None  

SCHEDULER_TIMEZONE = TIMEZONE