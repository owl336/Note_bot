import threading
import time
from datetime import datetime


class ReminderWorkerService(threading.Thread):
    def __init__(self, bot, user_data_manager):
        super().__init__(daemon=True)
        self.bot = bot
        self.user_data = user_data_manager
        self.running = True

    def run(self):
        while self.running:
            now = datetime.now()
            for chat_id in list(self.user_data.user_reminders.keys()):
                reminders = self.user_data.get_user_reminders(chat_id)
                notes = self.user_data.get_user_notes(chat_id)

                for reminder in reminders[:]:
                    note_id, remind_time = reminder
                    if now >= remind_time:
                        if note_id in notes:
                            self.bot.send_message(chat_id, f"Напоминание: {notes[note_id]}")
                        reminders.remove(reminder)
            time.sleep(30)

    def stop(self):
        self.running = False
