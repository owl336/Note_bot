import os

import requests


class AIService:
    def __init__(self, user_data_manager):
        self.user_data = user_data_manager
        self.API_KEY = os.getenv('API_KEY')
        self.API_URL = os.getenv('API_URL')

    def analyze_notes(self, chat_id, note_ids_str):
        notes = self.user_data.get_user_notes(chat_id)

        if not self.API_KEY or not self.API_URL:
            return "Ошибка: API-ключ или URL не настроены."

        try:
            note_ids = list(map(int, note_ids_str.split(',')))
            self.user_data.update_user_statistics(chat_id, "ai_analysis")

            selected_notes = [notes[note_id] for note_id in note_ids if note_id in notes]

            if not selected_notes:
                return "Вы ввели неверные номера заметок. Попробуйте снова."

            if len(note_ids) < 3:
                return "Для анализа нужно хотя бы 3 заметки."

            notes_text = " ".join(selected_notes)
            payload = {
                "model": "qwen/qwq-32b:free",
                "messages": [
                    {"role": "system", "content": "Вы — дружелюбный помощник для анализа заметок."},
                    {"role": "user", "content": f"Проанализируйте следующие заметки: {notes_text}"}
                ]
            }
            headers = {"Authorization": f"Bearer {self.API_KEY}"}
            response = requests.post(self.API_URL, json=payload, headers=headers)

            if response.status_code == 200:
                response_data = response.json()
                analysis = response_data.get("choices", [{}])[0].get("message", {}).get("content", "Нет данных.")
                return f"Анализ ваших заметок:\n\n{analysis}"
            else:
                return "Ошибка анализа. Попробуйте позже."
        except ValueError:
            return "Введите корректные номера заметок через запятую."
        except Exception as e:
            return f"Произошла ошибка: {str(e)}"
