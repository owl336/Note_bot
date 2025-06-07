import os

import telebot
from telebot.types import ReplyKeyboardMarkup, KeyboardButton

from Note_bot.main.ui.UIManager import UIManager
from Note_bot.main.service.NoteService import NoteManager
from Note_bot.main.service.AIService import AIService
from Note_bot.main.data.UserDataManager import UserDataManager
from Note_bot.main.service.ReminderWorkerService import ReminderWorkerService


class NoteBot:
    def __init__(self):
        self.bot = telebot.TeleBot(os.getenv('BOT_TOKEN'))
        self.user_data = UserDataManager()
        self.note_manager = NoteManager(self.user_data)
        self.ui_manager = UIManager(self.bot, self.user_data)
        self.ai_service = AIService(self.user_data)
        self.reminder_worker = ReminderWorkerService(self.bot, self.user_data)

        self.register_handlers()
        self.reminder_worker.start()

    def register_handlers(self):
        @self.bot.message_handler(commands=['start'])
        def start_message(message):
            self.ui_manager.send_main_menu(message.chat.id)

        @self.bot.message_handler(func=lambda message: True)
        def handle_other_messages(message):
            chat_id = message.chat.id
            text = message.text

            if chat_id in self.user_data.current_page and (text.isdigit() or (text and text.strip()[0].isdigit())):
                self.process_note_selection_for_edit(message)
                return

            if text == "➕ Добавить заметку":
                msg = self.bot.send_message(chat_id, "Введите текст заметки (можно с временем).")
                self.bot.register_next_step_handler(msg, self.add_note_handler)

            elif text == "❌ Удалить заметку":
                notes = self.user_data.get_user_notes(chat_id)
                if notes:
                    self.ui_manager.send_notes_list(chat_id)
                    msg = self.bot.send_message(chat_id, "Введите номер заметки для удаления:")
                    self.bot.register_next_step_handler(msg, self.delete_note_handler)
                else:
                    self.bot.send_message(chat_id, "У вас пока нет заметок.")

            elif text == "✏️ Редактировать заметку":
                self.edit_note_step1(message)

            elif text in ["⬅️ Назад", "Вперед ➡️"]:
                self.process_note_selection_for_edit(message)

            elif text == "📋 Показать список заметок":
                self.ui_manager.send_notes_list(chat_id)

            elif text == "🤖 Анализ от ИИ":
                self.analyze_notes_step1(message)

            elif text == "🔍 Поиск по заметкам":
                notes = self.user_data.get_user_notes(chat_id)
                if notes:
                    msg = self.bot.send_message(chat_id, "Введите текст для поиска в заметках:")
                    self.bot.register_next_step_handler(msg, self.search_notes_handler)
                else:
                    self.bot.send_message(chat_id, "У вас пока нет заметок для поиска.")

            elif text == "📊 Статистика":
                self.ui_manager.show_statistics(chat_id)

            elif text in ["📈 7 дней", "📉 30 дней"]:
                days_map = {
                    "📈 7 дней": 7,
                    "📉 30 дней": 30
                }
                self.ui_manager.send_statistics_plot(chat_id, days_map[text])
                self.ui_manager.show_statistics(chat_id)

            elif text == "📤 Экспорт заметок":
                self.export_notes_step1(message)

            elif text == "ℹ️ О боте":
                self.ui_manager.about_bot(chat_id)

            elif text == "🔙 Назад":
                self.ui_manager.send_main_menu(chat_id)

            else:
                self.bot.send_message(chat_id, "Я не понял ваше сообщение. Вот меню:")
                self.ui_manager.send_main_menu(chat_id)

    def add_note_handler(self, message):
        result = self.note_manager.add_note(message)
        self.bot.send_message(message.chat.id, result)
        self.ui_manager.send_main_menu(message.chat.id)

    def delete_note_handler(self, message):
        result = self.note_manager.delete_note(message.chat.id, message.text)
        self.bot.send_message(message.chat.id, result)
        self.ui_manager.send_main_menu(message.chat.id)

    def edit_note_step1(self, message):
        chat_id = message.chat.id
        notes = self.user_data.get_user_notes(chat_id)

        if not notes:
            self.bot.send_message(chat_id, "У вас пока нет заметок для редактирования.")
            self.ui_manager.send_main_menu(chat_id)
            return

        self.user_data.set_current_page(chat_id, 0)
        self.ui_manager.show_notes_page(chat_id)

    def process_note_selection_for_edit(self, message):
        chat_id = message.chat.id

        if message.text == "❌ Отмена":
            self.ui_manager.send_main_menu(chat_id)
            return

        if message.text == "⬅️ Назад":
            self.ui_manager.show_notes_page(chat_id, self.user_data.get_current_page(chat_id) - 1)
            return
        elif message.text == "Вперед ➡️":
            self.ui_manager.show_notes_page(chat_id, self.user_data.get_current_page(chat_id) + 1)
            return

        try:
            note_id = int(message.text.split(":")[0].strip())
            notes = self.user_data.get_user_notes(chat_id)

            if note_id in notes:
                current_text = notes[note_id]

                markup = ReplyKeyboardMarkup(resize_keyboard=True)
                markup.add(KeyboardButton("❌ Отмена редактирования"))

                msg = self.bot.send_message(
                    chat_id,
                    f"Текущий текст заметки #{note_id}:\n\n{current_text}\n\nВведите новый текст для заметки:",
                    reply_markup=markup
                )
                self.bot.register_next_step_handler(msg, self.edit_note_step2, note_id)
            else:
                self.bot.send_message(chat_id, "Такой заметки нет.")
                self.ui_manager.show_notes_page(chat_id, self.user_data.get_current_page(chat_id))
        except (ValueError, IndexError):
            self.bot.send_message(chat_id, "Пожалуйста, выберите заметку из списка.")
            self.ui_manager.show_notes_page(chat_id, self.user_data.get_current_page(chat_id))

    def edit_note_step2(self, message, note_id):
        chat_id = message.chat.id

        if message.text == "❌ Отмена редактирования":
            self.ui_manager.send_main_menu(chat_id)
            return

        result = self.note_manager.edit_note(chat_id, note_id, message.text)
        self.bot.send_message(chat_id, result)
        self.ui_manager.send_main_menu(chat_id)

    def search_notes_handler(self, message):
        result = self.note_manager.search_notes(message.chat.id, message.text)
        if result.startswith("🔍 Найдены заметки:"):
            self.bot.send_message(message.chat.id, result, parse_mode="Markdown")
        else:
            self.bot.send_message(message.chat.id, result)
        self.ui_manager.send_main_menu(message.chat.id)

    def analyze_notes_step1(self, message):
        chat_id = message.chat.id
        notes = self.user_data.get_user_notes(chat_id)

        if not notes:
            self.bot.send_message(chat_id, "У вас пока нет заметок для анализа.")
            return

        self.ui_manager.send_notes_list(chat_id)
        self.bot.send_message(chat_id, "Введите номера заметок через запятую, которые хотите отправить на анализ:")
        self.bot.register_next_step_handler(message, self.analyze_notes_step2)

    def analyze_notes_step2(self, message):
        result = self.ai_service.analyze_notes(message.chat.id, message.text)
        self.bot.send_message(message.chat.id, result)
        self.ui_manager.send_main_menu(message.chat.id)

    def export_notes_step1(self, message):
        chat_id = message.chat.id
        notes = self.user_data.get_user_notes(chat_id)

        if not notes:
            self.bot.send_message(chat_id, "У вас пока нет заметок для экспорта.")
            self.ui_manager.send_main_menu(chat_id)
            return

        self.ui_manager.send_notes_list(chat_id)
        self.bot.send_message(chat_id, "Введите номера заметок через запятую, которые хотите экспортировать:")
        self.bot.register_next_step_handler(message, self.export_notes_step2)

    def export_notes_step2(self, message):
        result = self.note_manager.export_notes(message.chat.id, message.text)

        if isinstance(result, list):
            for file_name in result:
                with open(file_name, "rb") as file:
                    self.bot.send_document(message.chat.id, file)
                os.remove(file_name)
            self.bot.send_message(message.chat.id, "Экспорт завершён.")
        else:
            self.bot.send_message(message.chat.id, result)

        self.ui_manager.send_main_menu(message.chat.id)

    def run(self):
        self.bot.infinity_polling()
