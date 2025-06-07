import re

import dateparser


class NoteManager:
    def __init__(self, user_data_manager):
        self.user_data = user_data_manager

    def extract_time(self, note_text):
        patterns = [
            r'через \d+ (минут|минуту|час|часов|день|дней|неделю|недель|месяц|месяцев)',
            r'сегодня в \d{1,2}(:\d{2})?',
            r'завтра в \d{1,2}(:\d{2})?',
            r'послезавтра в \d{1,2}(:\d{2})?',
            r'\d{1,2}(:\d{2})? (утра|вечера|дня|ночи)',
            r'в \d{1,2}(:\d{2})?',
            r'через час',
            r'через минуту',
        ]

        for pattern in patterns:
            match = re.search(pattern, note_text.lower())
            if match:
                parsed_date = dateparser.parse(match.group(), settings={'PREFER_DATES_FROM': 'future'})
                if parsed_date:
                    return parsed_date
        return None

    def add_note(self, message):
        chat_id = message.chat.id
        notes = self.user_data.get_user_notes(chat_id)
        reminders = self.user_data.get_user_reminders(chat_id)

        note_text = message.text.strip()
        if note_text:
            note_id = len(notes) + 1
            notes[note_id] = note_text
            self.user_data.update_user_statistics(chat_id, "notes_created")

            time_to_remind = self.extract_time(note_text)
            if time_to_remind:
                reminders.append((note_id, time_to_remind))
                return f"Заметка добавлена с напоминанием на {time_to_remind.strftime('%Y-%m-%d %H:%M:%S')}."
            else:
                return "Заметка добавлена без напоминания."
        else:
            return "Текст заметки не может быть пустым."

    def delete_note(self, chat_id, note_id_str):
        notes = self.user_data.get_user_notes(chat_id)
        reminders = self.user_data.get_user_reminders(chat_id)

        try:
            note_id = int(note_id_str.strip())
            if note_id in notes:
                notes.pop(note_id)
                self.user_data.update_user_statistics(chat_id, "notes_deleted")

                old_notes = dict(notes)
                notes.clear()
                for new_id, old_id in enumerate(sorted(old_notes.keys()), start=1):
                    notes[new_id] = old_notes[old_id]

                new_reminders = []
                for rem_note_id, rem_time in reminders:
                    if rem_note_id == note_id:
                        continue

                    new_id = None
                    for k, v in notes.items():
                        if old_notes.get(rem_note_id) == v:
                            new_id = k
                            break
                    if new_id is not None:
                        new_reminders.append((new_id, rem_time))

                self.user_data.user_reminders[chat_id] = new_reminders
                return f"Заметка {note_id} удалена."
            else:
                return "Такой заметки нет."
        except ValueError:
            return "Пожалуйста, укажите корректный номер заметки."

    def edit_note(self, chat_id, note_id, new_text):
        notes = self.user_data.get_user_notes(chat_id)
        reminders = self.user_data.get_user_reminders(chat_id)

        new_text = new_text.strip()
        if new_text:
            notes[note_id] = new_text
            time_to_remind = self.extract_time(new_text)
            if time_to_remind:
                reminders.append((note_id, time_to_remind))
                return f"Заметка {note_id} обновлена с напоминанием на {time_to_remind.strftime('%Y-%m-%d %H:%M:%S')}."
            else:
                return f"Заметка {note_id} успешно обновлена."
        else:
            return "Текст заметки не может быть пустым."

    def search_notes(self, chat_id, search_query):
        notes = self.user_data.get_user_notes(chat_id)
        search_query = search_query.strip().lower()

        if not search_query:
            return "Вы ввели пустой запрос."

        found_notes = {}
        for note_id, note_text in notes.items():
            if search_query in note_text.lower():
                highlighted_text = note_text.replace(
                    search_query,
                    f"*{search_query}*"
                )
                found_notes[note_id] = highlighted_text

        if found_notes:
            response = "🔍 Найдены заметки:\n\n"
            for note_id, note_text in found_notes.items():
                response += f"{note_id}. {note_text}\n\n"
            return response
        else:
            return f"Заметки, содержащие '{search_query}', не найдены."

    def export_notes(self, chat_id, note_ids_str):
        notes = self.user_data.get_user_notes(chat_id)

        try:
            note_ids = list(map(int, note_ids_str.split(',')))
            selected_notes = [notes[note_id] for note_id in note_ids if note_id in notes]

            if not selected_notes:
                return "Вы ввели некорректные номера заметок. Попробуйте снова."

            files = []
            for note_id, note_text in zip(note_ids, selected_notes):
                file_name = f"note_{note_id}.txt"
                with open(file_name, "w", encoding="utf-8") as file:
                    file.write(note_text)
                files.append(file_name)

            return files
        except Exception as e:
            return f"Произошла ошибка при экспорте заметок: {str(e)}"
