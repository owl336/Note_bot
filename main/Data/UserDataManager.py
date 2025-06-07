from datetime import datetime


class UserDataManager:
    def __init__(self):
        self.user_notes = {}  # {chat_id: {note_id: note_text}}
        self.user_reminders = {}  # {chat_id: [(note_id, remind_time)]}
        self.user_statistics = {}  # {chat_id: statistics_dict}
        self.current_page = {}  # {chat_id: page_number}

    def get_user_notes(self, chat_id):
        if chat_id not in self.user_notes:
            self.user_notes[chat_id] = {}
        return self.user_notes[chat_id]

    def get_user_reminders(self, chat_id):
        if chat_id not in self.user_reminders:
            self.user_reminders[chat_id] = []
        return self.user_reminders[chat_id]

    def get_user_statistics(self, chat_id):
        if chat_id not in self.user_statistics:
            self.user_statistics[chat_id] = {
                "notes_created": {},  # {date: count}
                "notes_deleted": {},  # {date: count}
                "ai_analysis": {},  # {date: count}
                "total_ai_used": 0
            }
        return self.user_statistics[chat_id]

    def update_user_statistics(self, chat_id, stat_type):
        stats = self.get_user_statistics(chat_id)
        today = datetime.now().strftime("%m-%d")

        if stat_type in stats:
            if today in stats[stat_type]:
                stats[stat_type][today] += 1
            else:
                stats[stat_type][today] = 1

            if stat_type == "ai_analysis":
                stats["total_ai_used"] += 1

    def get_current_page(self, chat_id):
        return self.current_page.get(chat_id, 0)

    def set_current_page(self, chat_id, page):
        self.current_page[chat_id] = page
