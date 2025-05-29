import dateparser
import telebot
from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
import threading
import time
from datetime import datetime, timedelta
import re
import dateparser

bot = telebot.TeleBot('7810822364:AAEAgzX1ozEUa577OGB2LF3Zy1kQHW7rVdg')



# Словарь для хранения заметок
notes = {}
# Список для хранения напоминаний
reminders = []


@bot.message_handler(commands=['start'])
def start_message(message):
    show_menu(message.chat.id)


@bot.message_handler(func=lambda message: True)
def handle_other_messages(message):
    bot.send_message(message.chat.id, "Я не понял ваше сообщение. Вот меню:", reply_markup=get_main_menu())


@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == 'add_note':
        msg = bot.send_message(call.message.chat.id,
                               "Введите текст заметки (можно с временем).")
        bot.register_next_step_handler(msg, add_note)

    elif call.data == 'list_notes':
        if notes:
            response = "Ваши заметки:\n"
            response += "\n".join([f"{note_id}. {text}" for note_id, text in notes.items()])
        else:
            response = "У вас пока нет заметок."
        bot.send_message(call.message.chat.id, response)

    elif call.data == 'delete_note':
        if notes:
            response = "Введите номер заметки для удаления:\n"
            response += "\n".join([f"{note_id}. {text}" for note_id, text in notes.items()])
            msg = bot.send_message(call.message.chat.id, response)
            bot.register_next_step_handler(msg, delete_note)
        else:
            bot.send_message(call.message.chat.id, "У вас пока нет заметок.")

    elif call.data == 'edit_note':
        if notes:
            response = "Введите номер заметки для редактирования:\n"
            response += "\n".join([f"{note_id}. {text}" for note_id, text in notes.items()])
            msg = bot.send_message(call.message.chat.id, response)
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


def edit_note_step1(message):
    try:
        note_id = int(message.text.strip())
        if note_id in notes:
            msg = bot.send_message(message.chat.id, "Введите новый текст для заметки:")
            bot.register_next_step_handler(msg, edit_note_step2, note_id)
        else:
            bot.send_message(message.chat.id, "Такой заметки нет.")
    except ValueError:
        bot.send_message(message.chat.id, "Пожалуйста, укажите корректный номер заметки.")


def edit_note_step2(message, note_id):
    new_text = message.text.strip()
    if new_text:
        notes[note_id] = new_text
        time_to_remind = extract_time(notes)
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


def extract_time(note_text):
    patterns = [
        r'через \d+ (минут|час|часов|день|дней|неделю|недель|месяц|месяцев)',  # через 2 часа и т.п.
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


def show_menu(chat_id):
    bot.send_message(chat_id, "Выберите действие:", reply_markup=get_main_menu())


def get_main_menu():
    markup = InlineKeyboardMarkup()
    markup.add(
        InlineKeyboardButton("Добавить заметку", callback_data='add_note'),
        InlineKeyboardButton("Список заметок", callback_data='list_notes'),
        InlineKeyboardButton("Удалить заметку", callback_data='delete_note'),
        InlineKeyboardButton("Редактировать заметку", callback_data='edit_note')
    )
    return markup


def reminder_worker():
    while True:
        now = datetime.now()
        for reminder in reminders[:]:
            chat_id, note_id, remind_time = reminder
            if now >= remind_time:
                bot.send_message(chat_id, f"Напоминание: {notes[note_id]}")
                reminders.remove(reminder)
        time.sleep(30)



threading.Thread(target=reminder_worker, daemon=True).start()


bot.infinity_polling()
