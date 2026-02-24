import sqlite3
import json
from config import DATABASE_PATH

class Database:
    def __init__(self):
        self.db_path = DATABASE_PATH
        self.init_db()

    def init_db(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY,
                    moodle_login TEXT UNIQUE NOT NULL,
                    moodle_password TEXT NOT NULL,
                    auto_enabled BOOLEAN DEFAULT 0,
                    login_times TEXT DEFAULT '[]'
                )
            ''')
            conn.commit()

    def add_or_update_user(self, user_id, login, password):
        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute('''
                    INSERT OR REPLACE INTO users (user_id, moodle_login, moodle_password)
                    VALUES (?, ?, ?)
                ''', (user_id, login, password))
                conn.commit()
                return True
        except sqlite3.IntegrityError:
            return False  # Login already exists

    def get_user(self, user_id):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
            row = cursor.fetchone()
            if row:
                return {
                    'user_id': row[0],
                    'moodle_login': row[1],
                    'moodle_password': row[2],
                    'auto_enabled': bool(row[3]),
                    'login_times': json.loads(row[4])
                }
            return None

    def get_user_by_login(self, login):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT user_id FROM users WHERE moodle_login = ?', (login,))
            row = cursor.fetchone()
            return row[0] if row else None

    def update_auto_enabled(self, user_id, enabled):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET auto_enabled = ? WHERE user_id = ?', (enabled, user_id))
            conn.commit()

    def update_login_times(self, user_id, times):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('UPDATE users SET login_times = ? WHERE user_id = ?', (json.dumps(times), user_id))
            conn.commit()

    def get_all_users(self):
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT * FROM users')
            rows = cursor.fetchall()
            users = []
            for row in rows:
                users.append({
                    'user_id': row[0],
                    'moodle_login': row[1],
                    'moodle_password': row[2],
                    'auto_enabled': bool(row[3]),
                    'login_times': json.loads(row[4])
                })
            return users