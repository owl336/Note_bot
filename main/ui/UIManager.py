from datetime import datetime, timedelta
import io
from matplotlib import pyplot as plt
from telebot.types import ReplyKeyboardMarkup, KeyboardButton


class UIManager:
    def __init__(self, bot, user_data_manager):
        self.bot = bot
        self.user_data = user_data_manager

    def send_main_menu(self, chat_id):
        markup = ReplyKeyboardMarkup(resize_keyboard=True)
        markup.row(
            KeyboardButton("➕ Добавить заметку"),
            KeyboardButton("❌ Удалить заметку")
        )
        markup.row(
            KeyboardButton("✏️ Редактировать заметку"),
            KeyboardButton("📋 Показать список заметок")
        )
        markup.row(
            KeyboardButton("🔍 Поиск по заметкам"),
            KeyboardButton("🤖 Анализ от ИИ")
        )
        markup.row(
            KeyboardButton("📊 Статистика"),
            KeyboardButton("📤 Экспорт заметок")
        )
        markup.row(
            KeyboardButton("ℹ️ О боте")
        )
        self.bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)

    def send_notes_list(self, chat_id):
        notes = self.user_data.get_user_notes(chat_id)

        if not notes:
            self.bot.send_message(chat_id, "У вас пока нет заметок.")
            return

        message_text = "Ваши заметки:\n"
        for note_id, note_text in notes.items():
            message_text += f"{note_id}. {note_text}\n"

        self.bot.send_message(chat_id, message_text)

    def show_notes_page(self, chat_id, page=0):
        notes = self.user_data.get_user_notes(chat_id)
        note_ids = sorted(notes.keys())
        total_notes = len(note_ids)
        notes_per_page = 4

        total_pages = (total_notes + notes_per_page - 1) // notes_per_page

        if page < 0:
            page = 0
        elif page >= total_pages:
            page = total_pages - 1

        self.user_data.set_current_page(chat_id, page)

        start_idx = page * notes_per_page
        end_idx = min(start_idx + notes_per_page, total_notes)
        page_note_ids = note_ids[start_idx:end_idx]

        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=2)

        for note_id in page_note_ids:
            note_preview = notes[note_id][:20] + "..." if len(notes[note_id]) > 20 else notes[note_id]
            markup.add(KeyboardButton(f" {note_id}: {note_preview}"))

        nav_buttons = []
        if page > 0:
            nav_buttons.append(KeyboardButton("⬅️ Назад"))
        if page < total_pages - 1:
            nav_buttons.append(KeyboardButton("Вперед ➡️"))

        if nav_buttons:
            markup.row(*nav_buttons)

        markup.add(KeyboardButton("❌ Отмена"))

        self.bot.send_message(
            chat_id,
            f"Выберите заметку для редактирования (Страница {page + 1}/{total_pages}):",
            reply_markup=markup
        )

    def show_statistics(self, chat_id):
        markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
        markup.add(
            KeyboardButton("📈 7 дней"),
            KeyboardButton("📉 30 дней"),
        )
        markup.add(
            KeyboardButton("🔙 Назад")
        )

        self.bot.send_message(
            chat_id,
            "Выберите период для отображения статистики:",
            reply_markup=markup
        )

    def generate_combined_plot(self, chat_id, days=7):
        stats = self.user_data.get_user_statistics(chat_id)
        fig, ax = plt.subplots(figsize=(12, 6))

        today = datetime.now()
        dates = [(today - timedelta(days=i)).strftime("%m-%d") for i in range(days)][::-1]

        created = [stats["notes_created"].get(date, 0) for date in dates]
        deleted = [stats["notes_deleted"].get(date, 0) for date in dates]
        ai_used = [stats["ai_analysis"].get(date, 0) for date in dates]

        ax.plot(dates, created, marker='o', label='Создано заметок', linewidth=2)
        ax.plot(dates, deleted, marker='s', label='Удалено заметок', linewidth=2)
        ax.plot(dates, ai_used, marker='^', label='AI анализов', linewidth=2)

        ax.set_title(f"Статистика активности за {days} дней", pad=20, fontsize=14)
        ax.set_xlabel("Дата", fontsize=12)
        ax.set_ylabel("Количество", fontsize=12)
        ax.tick_params(axis='x', rotation=45, labelsize=10)
        ax.tick_params(axis='y', labelsize=10)
        ax.grid(True, linestyle='--', alpha=0.7)
        ax.legend(fontsize=12)

        fig.tight_layout()

        buf = io.BytesIO()
        fig.savefig(buf, format='png', dpi=120, bbox_inches='tight')
        buf.seek(0)
        plt.close(fig)

        return buf

    def send_statistics_plot(self, chat_id, days):
        stats = self.user_data.get_user_statistics(chat_id)
        plot = self.generate_combined_plot(chat_id, days)

        stats_text = (
            f"📊 Статистика за {days} дней:\n"
            f"• Всего заметок создано: {sum(stats['notes_created'].values())}\n"
            f"• Всего заметок удалено: {sum(stats['notes_deleted'].values())}\n"
            f"• Всего AI анализов: {stats['total_ai_used']}"
        )

        self.bot.send_photo(chat_id, plot, caption=stats_text)
        plot.close()

    def about_bot(self, chat_id):
        bot_info = (
            "*О боте*\n\n"
            "Этот бот создан для управления заметками и напоминаниями.\n\n"
            "📋 *Функции:*\n"
            "• ➕ Добавить заметку\n"
            "• ❌ Удалить заметку\n"
            "• ✏️ Редактировать заметку\n"
            "• 📋 Показать список заметок\n"
            "• 🔍 Поиск по заметкам\n"
            "• 🤖 Анализ от ИИ\n"
            "• 📊 Статистика\n"
            "• 📤 Экспорт заметок\n\n"
            "⚙️ Если у вас есть вопросы или предложения, свяжитесь с разработчиком ([@the\\_forest\\_owl]("
            "https://t.me/the_forest_owl))."
        )
        self.bot.send_message(chat_id, bot_info, parse_mode="Markdown")
