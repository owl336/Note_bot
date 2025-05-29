import dateparser
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton, ReplyKeyboardMarkup, KeyboardButton
import threading
import time
from datetime import datetime
import re
from dotenv import load_dotenv
import os
import requests

load_dotenv()

BOT_TOKEN = os.getenv('BOT_TOKEN')
API_KEY = os.getenv('API_KEY')
API_URL = os.getenv('API_URL')

bot = telebot.TeleBot(BOT_TOKEN)

# Словарь для хранения заметок
notes = {}
# Список для хранения напоминаний
reminders = []


@bot.message_handler(commands=['start'])
def start_message(message):
    send_main_menu(message.chat.id)


@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    text = message.text

    if text == "➕ Добавить заметку":
        msg = bot.send_message(message.chat.id, "Введите текст заметки (можно с временем).")
        bot.register_next_step_handler(msg, add_note)

    elif text == "❌ Удалить заметку":
        if notes:
            send_notes_list(message.chat.id)
            msg = bot.send_message(message.chat.id, "Введите номер заметки для удаления:")
            bot.register_next_step_handler(msg, delete_note)
        else:
            bot.send_message(message.chat.id, "У вас пока нет заметок.")

    elif text == "✏️ Редактировать заметку":
        if notes:
            send_notes_list(message.chat.id)
            msg = bot.send_message(message.chat.id, "Введите номер заметки для редактирования:")
            bot.register_next_step_handler(msg, edit_note_step1)
        else:
            bot.send_message(message.chat.id, "У вас пока нет заметок.")

    elif text == "📋 Показать список заметок":
        send_notes_list(message.chat.id)

    elif text == "🤖 Анализ от ИИ":
        analyze_notes(message.chat.id)


    else:
        bot.send_message(message.chat.id, "Я не понял ваше сообщение. Вот меню:")
        send_main_menu(message.chat.id)


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == 'add_note':
        msg = bot.send_message(call.message.chat.id, "Введите текст заметки (можно с временем).")
        bot.register_next_step_handler(msg, add_note)

    elif call.data == 'list_notes':
        send_notes_list(call.message.chat.id)

    elif call.data == 'delete_note':
        if notes:
            send_notes_list(call.message.chat.id)
            msg = bot.send_message(call.message.chat.id, "Введите номер заметки для удаления:")
            bot.register_next_step_handler(msg, delete_note)
        else:
            bot.send_message(call.message.chat.id, "У вас пока нет заметок.")

    elif call.data == 'edit_note':
        if notes:
            send_notes_list(call.message.chat.id)
            msg = bot.send_message(call.message.chat.id, "Введите номер заметки для редактирования:")
            bot.register_next_step_handler(msg, edit_note_step1)
        else:
            bot.send_message(call.message.chat.id, "У вас пока нет заметок.")


def add_note(message):
    note_text = message.text.strip()
    if note_text:
        note_id = len(notes) + 1
        notes[note_id] = note_text
        time_to_remind = extract_time(note_text)
        if time_to_remind:
            reminders.append((message.chat.id, note_id, time_to_remind))
            bot.send_message(
                message.chat.id,
                f"Заметка добавлена с напоминанием на {time_to_remind.strftime('%Y-%m-%d %H:%M:%S')}."
            )
        else:
            bot.send_message(message.chat.id, "Заметка добавлена без напоминания.")
    else:
        bot.send_message(message.chat.id, "Текст заметки не может быть пустым.")
    send_main_menu(message.chat.id)


def delete_note(message):
    try:
        note_id = int(message.text.strip())
        if note_id in notes:
            notes.pop(note_id)
            global reminders
            reminders = [r for r in reminders if r[1] != note_id]  # Удалить связанные напоминания
            bot.send_message(message.chat.id, f"Заметка {note_id} удалена.")
        else:
            bot.send_message(message.chat.id, "Такой заметки нет.")
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, укажите корректный номер заметки.")
    send_main_menu(message.chat.id)


def edit_note_step1(message):
    try:
        note_id = int(message.text.strip())
        if note_id in notes:
            current_text = notes[note_id]
            msg = bot.send_message(message.chat.id,
                                   f"Текущий текст заметки #{note_id}:\n\n{current_text}\n\nВведите новый текст для заметки:")
            bot.register_next_step_handler(msg, edit_note_step2, note_id)
        else:
            bot.send_message(message.chat.id, "Такой заметки нет.")
            send_main_menu(message.chat.id)
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, укажите корректный номер заметки.")
        send_main_menu(message.chat.id)


def edit_note_step2(message, note_id):
    new_text = message.text.strip()
    if new_text:
        notes[note_id] = new_text
        time_to_remind = extract_time(new_text)
        if time_to_remind:
            reminders.append((message.chat.id, note_id, time_to_remind))
            bot.send_message(
                message.chat.id,
                f"Заметка {note_id} обновлена с напоминанием на {time_to_remind.strftime('%Y-%m-%d %H:%M:%S')}."
            )
        else:
            bot.send_message(message.chat.id, f"Заметка {note_id} успешно обновлена.")
    else:
        bot.send_message(message.chat.id, "Текст заметки не может быть пустым.")
    send_main_menu(message.chat.id)


def extract_time(note_text):
    patterns = [
        r'через \d+ (минут|минуту|час|часов|день|дней|неделю|недель|месяц|месяцев)',  # через 2 часа и т.п.
        r'сегодня в \d{1,2}(:\d{2})?',  # сегодня в 6 или сегодня в 6:00
        r'завтра в \d{1,2}(:\d{2})?',  # завтра в 10 или завтра в 10:00
        r'послезавтра в \d{1,2}(:\d{2})?',
        r'\d{1,2}(:\d{2})? (утра|вечера|дня|ночи)',  # 10 утра, 6 вечера
        r'в \d{1,2}(:\d{2})?',  # в 10 или в 10:00
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
    if not notes:
        bot.send_message(chat_id, "У вас пока нет заметок.")
        return

    message_text = "Ваши заметки:\n"
    for note_id, note_text in notes.items():
        message_text += f"{note_id}. {note_text}\n"

    bot.send_message(chat_id, message_text)


def get_main_menu():
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Добавить заметку", callback_data='add_note'),
        InlineKeyboardButton("Список заметок", callback_data='list_notes'),
        InlineKeyboardButton("Удалить заметку", callback_data='delete_note'),
        InlineKeyboardButton("Редактировать заметку", callback_data='edit_note'),
        InlineKeyboardButton("Анализ от ИИ", callback_data='analyze_notes')
    )
    return markup


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
        KeyboardButton("🤖 Анализ от ИИ")
    )
    bot.send_message(chat_id, "Выберите действие:", reply_markup=markup)


def reminder_worker():
    while True:
        now = datetime.now()
        for reminder in reminders[:]:
            chat_id, note_id, remind_time = reminder
            if now >= remind_time:
                bot.send_message(chat_id, f"Напоминание: {notes[note_id]}")
                reminders.remove(reminder)
        time.sleep(30)


def analyze_notes(chat_id):
    if len(notes) < 3:
        bot.send_message(chat_id, "Для анализа нужно хотя бы 3 заметки.")
        return

    if not API_KEY or not API_URL:
        bot.send_message(chat_id, "Ошибка: API-ключ или URL не настроены.")
        return

    try:
        # Отправляем запрос к API с последними заметками
        notes_text = " ".join([text for _, text in sorted(notes.items())][-3:])  # Сливаем последние заметки
        payload = {
            "model": "qwen/qwq-32b:free",
            "messages": [
                {"role": "system", "content": "Вы — дружелюбный помощник для анализа заметок. Общайтесь так, будто вы "
                                              "отвечаете пользователю лично, помогаете ему разобраться и находите "
                                              "решение. Не бойтесь добавлять эмодзи и дружелюбный тон, чтобы создать "
                                              "теплую атмосферу! 😊."},
                {"role": "user", "content": f"Проанализируйте следующие заметки и сделай краткий анализ + дай "
                                            f"рекомендации в виде небольшого списка: {notes_text}"}
            ]
        }
        headers = {"Authorization": f"Bearer {API_KEY}"}
        response = requests.post(API_URL, json=payload, headers=headers)

        if response.status_code == 200:
            response_data = response.json()
            # Извлечение текста ответа
            analysis = response_data.get("choices", [{}])[0].get("message", {}).get("content", "Нет данных.")
            bot.send_message(chat_id, f"Анализ ваших заметок:\n\n{analysis}")
        else:
            bot.send_message(chat_id, "Ошибка анализа. Попробуйте позже.")
    except Exception as e:
        bot.send_message(chat_id, f"Произошла ошибка: {str(e)}")


threading.Thread(target=reminder_worker, daemon=True).start()

bot.infinity_polling()
