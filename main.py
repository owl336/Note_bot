import dateparser
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import threading
import time
import re
from dotenv import load_dotenv
import os
import requests
import io
from datetime import datetime, timedelta
import matplotlib
import matplotlib.pyplot as plt

matplotlib.use('Agg')

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
API_KEY = os.getenv('API_KEY')
API_URL = os.getenv('API_URL')

bot = telebot.TeleBot(BOT_TOKEN)

# Словари для хранения данных пользователей
user_notes = {}  # {chat_id: {note_id: note_text}}
user_reminders = {}  # {chat_id: [(note_id, remind_time)]}
user_statistics = {}  # {chat_id: statistics_dict}
current_page = {}  # {chat_id: page_number}


def get_user_notes(chat_id):
    """Получить заметки пользователя"""
    if chat_id not in user_notes:
        user_notes[chat_id] = {}
    return user_notes[chat_id]


def get_user_reminders(chat_id):
    """Получить напоминания пользователя"""
    if chat_id not in user_reminders:
        user_reminders[chat_id] = []
    return user_reminders[chat_id]


def get_user_statistics(chat_id):
    """Получить статистику пользователя"""
    if chat_id not in user_statistics:
        user_statistics[chat_id] = {
            "notes_created": {},  # {date: count}
            "notes_deleted": {},  # {date: count}
            "ai_analysis": {},  # {date: count}
            "total_ai_used": 0
        }
    return user_statistics[chat_id]


def update_user_statistics(chat_id, stat_type):
    """Обновить статистику пользователя"""
    stats = get_user_statistics(chat_id)
    today = datetime.now().strftime("%m-%d")

    if stat_type in stats:
        if today in stats[stat_type]:
            stats[stat_type][today] += 1
        else:
            stats[stat_type][today] = 1

        if stat_type == "ai_analysis":
            stats["total_ai_used"] += 1


@bot.message_handler(commands=['start'])
def start_message(message):
    send_main_menu(message.chat.id)


@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    chat_id = message.chat.id
    text = message.text

    if chat_id in current_page and (text.isdigit() or (text and text.strip()[0].isdigit())):
        process_note_selection_for_edit(message)
        return

    if text == "➕ Добавить заметку":
        msg = bot.send_message(message.chat.id, "Введите текст заметки (можно с временем).")
        bot.register_next_step_handler(msg, add_note)

    elif text == "❌ Удалить заметку":
        notes = get_user_notes(message.chat.id)
        if notes:
            send_notes_list(message.chat.id)
            msg = bot.send_message(message.chat.id, "Введите номер заметки для удаления:")
            bot.register_next_step_handler(msg, delete_note)
        else:
            bot.send_message(message.chat.id, "У вас пока нет заметок.")

    elif text == "✏️ Редактировать заметку":
        edit_note_step1(message)

    elif text in ["⬅️ Назад", "Вперед ➡️"]:
        process_note_selection_for_edit(message)

    elif text == "📋 Показать список заметок":
        send_notes_list(message.chat.id)

    elif text == "🤖 Анализ от ИИ":
        analyze_notes_step1(message)
    elif text == "🔍 Поиск по заметкам":
        notes = get_user_notes(message.chat.id)
        if notes:
            msg = bot.send_message(message.chat.id, "Введите текст для поиска в заметках:")
            bot.register_next_step_handler(msg, search_notes)
        else:
            bot.send_message(message.chat.id, "У вас пока нет заметок для поиска.")
    elif text == "📊 Статистика":
        show_statistics(message)
    elif text in ["📈 7 дней", "📉 30 дней"]:
        change_statistics_period(message)
    elif text == "📤 Экспорт заметок":
        export_notes_step1(message)
    elif text == "ℹ️ О боте":
        about_bot(message)
    else:
        bot.send_message(message.chat.id, "Я не понял ваше сообщение. Вот меню:")
        send_main_menu(message.chat.id)


def add_note(message):
    chat_id = message.chat.id
    notes = get_user_notes(chat_id)
    reminders = get_user_reminders(chat_id)

    note_text = message.text.strip()
    if note_text:
        note_id = len(notes) + 1
        notes[note_id] = note_text
        update_user_statistics(chat_id, "notes_created")

        time_to_remind = extract_time(note_text)
        if time_to_remind:
            reminders.append((note_id, time_to_remind))
            bot.send_message(
                chat_id,
                f"Заметка добавлена с напоминанием на {time_to_remind.strftime('%Y-%m-%d %H:%M:%S')}."
            )
        else:
            bot.send_message(chat_id, "Заметка добавлена без напоминания.")
    else:
        bot.send_message(chat_id, "Текст заметки не может быть пустым.")
    send_main_menu(chat_id)


def delete_note(message):
    chat_id = message.chat.id
    notes = get_user_notes(chat_id)
    reminders = get_user_reminders(chat_id)

    try:
        note_id = int(message.text.strip())
        if note_id in notes:
            notes.pop(note_id)
            update_user_statistics(chat_id, "notes_deleted")

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

            user_reminders[chat_id] = new_reminders
            bot.send_message(chat_id, f"Заметка {note_id} удалена.")
        else:
            bot.send_message(chat_id, "Такой заметки нет.")
    except ValueError:
        bot.send_message(chat_id, "Пожалуйста, укажите корректный номер заметки.")
    send_main_menu(chat_id)


def edit_note_step1(message):
    chat_id = message.chat.id
    notes = get_user_notes(chat_id)

    if not notes:
        bot.send_message(chat_id, "У вас пока нет заметок для редактирования.")
        send_main_menu(chat_id)
        return

    current_page[chat_id] = 0
    show_notes_page(chat_id)


def show_notes_page(chat_id, page=0):
    notes = get_user_notes(chat_id)
    note_ids = sorted(notes.keys())
    total_notes = len(note_ids)
    notes_per_page = 4

    total_pages = (total_notes + notes_per_page - 1) // notes_per_page

    if page < 0:
        page = 0
    elif page >= total_pages:
        page = total_pages - 1

    current_page[chat_id] = page

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

    bot.send_message(
        chat_id,
        f"Выберите заметку для редактирования (Страница {page + 1}/{total_pages}):",
        reply_markup=markup
    )


def process_note_selection_for_edit(message):
    chat_id = message.chat.id

    if message.text == "❌ Отмена":
        send_main_menu(chat_id)
        return

    if message.text == "⬅️ Назад":
        show_notes_page(chat_id, current_page.get(chat_id, 0) - 1)
        return
    elif message.text == "Вперед ➡️":
        show_notes_page(chat_id, current_page.get(chat_id, 0) + 1)
        return

    try:
        note_id = int(message.text.split(":")[0].strip())
        notes = get_user_notes(chat_id)

        if note_id in notes:
            current_text = notes[note_id]

            markup = ReplyKeyboardMarkup(resize_keyboard=True)
            markup.add(KeyboardButton("❌ Отмена редактирования"))

            msg = bot.send_message(
                chat_id,
                f"Текущий текст заметки #{note_id}:\n\n{current_text}\n\nВведите новый текст для заметки:",
                reply_markup=markup
            )
            bot.register_next_step_handler(msg, edit_note_step2, note_id)
        else:
            bot.send_message(chat_id, "Такой заметки нет.")
            show_notes_page(chat_id, current_page.get(chat_id, 0))
    except (ValueError, IndexError):
        bot.send_message(chat_id, "Пожалуйста, выберите заметку из списка.")
        show_notes_page(chat_id, current_page.get(chat_id, 0))


def edit_note_step2(message, note_id):
    chat_id = message.chat.id
    notes = get_user_notes(chat_id)
    reminders = get_user_reminders(chat_id)

    if message.text == "❌ Отмена редактирования":
        send_main_menu(chat_id)
        return

    new_text = message.text.strip()
    if new_text:
        notes[note_id] = new_text
        time_to_remind = extract_time(new_text)
        if time_to_remind:
            reminders.append((note_id, time_to_remind))
            bot.send_message(
                chat_id,
                f"Заметка {note_id} обновлена с напоминанием на {time_to_remind.strftime('%Y-%m-%d %H:%M:%S')}."
            )
        else:
            bot.send_message(chat_id, f"Заметка {note_id} успешно обновлена.")
    else:
        bot.send_message(chat_id, "Текст заметки не может быть пустым.")

    send_main_menu(chat_id)


def extract_time(note_text):
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


def send_notes_list(chat_id):
    notes = get_user_notes(chat_id)

    if not notes:
        bot.send_message(chat_id, "У вас пока нет заметок.")
        return

    message_text = "Ваши заметки:\n"
    for note_id, note_text in notes.items():
        message_text += f"{note_id}. {note_text}\n"

    bot.send_message(chat_id, message_text)


def send_main_menu(chat_id):
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
    bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)


def reminder_worker():
    while True:
        now = datetime.now()
        for chat_id in list(user_reminders.keys()):
            reminders = get_user_reminders(chat_id)
            notes = get_user_notes(chat_id)

            for reminder in reminders[:]:
                note_id, remind_time = reminder
                if now >= remind_time:
                    if note_id in notes:
                        bot.send_message(chat_id, f"Напоминание: {notes[note_id]}")
                    reminders.remove(reminder)
        time.sleep(30)


def search_notes(message):
    chat_id = message.chat.id
    notes = get_user_notes(chat_id)
    search_query = message.text.strip().lower()

    if not search_query:
        bot.send_message(chat_id, "Вы ввели пустой запрос.")
        send_main_menu(chat_id)
        return

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
        bot.send_message(chat_id, response, parse_mode="Markdown")
    else:
        bot.send_message(chat_id, f"Заметки, содержащие '{search_query}', не найдены.")

    send_main_menu(chat_id)


def analyze_notes_step1(message):
    chat_id = message.chat.id
    notes = get_user_notes(chat_id)

    if not notes:
        bot.send_message(chat_id, "У вас пока нет заметок для анализа.")
        return

    send_notes_list(chat_id)
    bot.send_message(chat_id, "Введите номера заметок через запятую, которые хотите отправить на анализ:")
    bot.register_next_step_handler(message, analyze_notes_step2)


def analyze_notes_step2(message):
    chat_id = message.chat.id
    notes = get_user_notes(chat_id)

    if not API_KEY or not API_URL:
        bot.send_message(chat_id, "Ошибка: API-ключ или URL не настроены.")
        return

    try:
        note_ids = list(map(int, message.text.split(',')))
        update_user_statistics(chat_id, "ai_analysis")

        selected_notes = [notes[note_id] for note_id in note_ids if note_id in notes]

        if not selected_notes:
            bot.send_message(chat_id, "Вы ввели неверные номера заметок. Попробуйте снова.")
            return

        if len(note_ids) < 3:
            bot.send_message(chat_id, "Для анализа нужно хотя бы 3 заметки.")
            return

        notes_text = " ".join(selected_notes)
        payload = {
            "model": "qwen/qwq-32b:free",
            "messages": [
                {"role": "system", "content": "Вы — дружелюбный помощник для анализа заметок."},
                {"role": "user", "content": f"Проанализируйте следующие заметки: {notes_text}"}
            ]
        }
        headers = {"Authorization": f"Bearer {API_KEY}"}
        response = requests.post(API_URL, json=payload, headers=headers)

        if response.status_code == 200:
            response_data = response.json()
            analysis = response_data.get("choices", [{}])[0].get("message", {}).get("content", "Нет данных.")
            bot.send_message(chat_id, f"Анализ ваших заметок:\n\n{analysis}")
        else:
            bot.send_message(chat_id, "Ошибка анализа. Попробуйте позже.")
    except ValueError:
        bot.send_message(chat_id, "Введите корректные номера заметок через запятую.")
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {str(e)}")


def generate_combined_plot(chat_id, days=7):
    stats = get_user_statistics(chat_id)
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


def send_statistics_plot(chat_id, days):
    stats = get_user_statistics(chat_id)
    plot = generate_combined_plot(chat_id, days)

    stats_text = (
        f"📊 Статистика за {days} дней:\n"
        f"• Всего заметок создано: {sum(stats['notes_created'].values())}\n"
        f"• Всего заметок удалено: {sum(stats['notes_deleted'].values())}\n"
        f"• Всего AI анализов: {stats['total_ai_used']}"
    )

    bot.send_photo(chat_id, plot, caption=stats_text)
    plot.close()


def show_statistics(message):
    chat_id = message.chat.id
    markup = ReplyKeyboardMarkup(resize_keyboard=True, row_width=3)
    markup.add(
        KeyboardButton("📈 7 дней"),
        KeyboardButton("📉 30 дней"),
    )
    markup.add(
        KeyboardButton("🔙 Назад")
    )

    bot.send_message(
        chat_id,
        "Выберите период для отображения статистики:",
        reply_markup=markup
    )


def change_statistics_period(message):
    chat_id = message.chat.id
    days_map = {
        "📈 7 дней": 7,
        "📉 30 дней": 30
    }
    send_statistics_plot(chat_id, days_map[message.text])
    show_statistics(message)


def export_notes_step1(message):
    chat_id = message.chat.id
    notes = get_user_notes(chat_id)

    if not notes:
        bot.send_message(chat_id, "У вас пока нет заметок для экспорта.")
        send_main_menu(chat_id)
        return

    send_notes_list(chat_id)
    bot.send_message(chat_id, "Введите номера заметок через запятую, которые хотите экспортировать:")
    bot.register_next_step_handler(message, export_notes_step2)


def export_notes_step2(message):
    chat_id = message.chat.id
    notes = get_user_notes(chat_id)

    try:
        note_ids = list(map(int, message.text.split(',')))
        selected_notes = [notes[note_id] for note_id in note_ids if note_id in notes]

        if not selected_notes:
            bot.send_message(chat_id, "Вы ввели некорректные номера заметок. Попробуйте снова.")
            return

        for note_id, note_text in zip(note_ids, selected_notes):
            file_name = f"note_{note_id}.txt"
            with open(file_name, "w", encoding="utf-8") as file:
                file.write(note_text)

            with open(file_name, "rb") as file:
                bot.send_document(chat_id, file, caption=f"Заметка #{note_id}")

        bot.send_message(chat_id, "Экспорт завершён.")
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка при экспорте заметок: {str(e)}")
    finally:
        send_main_menu(chat_id)


def about_bot(message):
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
        "⚙️ Если у вас есть вопросы, свяжитесь с разработчиком."
    )
    bot.send_message(message.chat.id, bot_info, parse_mode="Markdown")


# Запуск потока для напоминаний
threading.Thread(target=reminder_worker, daemon=True).start()

bot.infinity_polling()