# -*- coding: utf-8 -*-
import logging
from datetime import datetime, timedelta
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, CallbackQueryHandler, filters, ConversationHandler, ContextTypes
from bookings import add_booking, get_all_bookings, update_booking_status, booking_exists
import os
from dotenv import load_dotenv # type: ignore

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_USERNAME = os.getenv("ADMIN_USERNAME")
ADMIN_CHAT_IDS = [int(cid) for cid in os.getenv("ADMIN_CHAT_IDS", str(os.getenv("ADMIN_CHAT_ID", "")).strip()).split(",") if cid.strip()]
# Новый список экскурсий и расписание
LOCATIONS = [
    "Вершины Феодосии",
    "Белая Скала",
    "Арпатские водопады",
    "Меганом и мысы Судака"
]
LOCATION_TIMES = {
    "Вершины Феодосии": ["09:00", "13:00", "17:00"],
    "Белая Скала": ["08:00", "14:00"],
    "Арпатские водопады": ["08:00", "14:00"],
    "Меганом и мысы Судака": ["08:00", "14:00"]
}

# Состояния для ConversationHandler
(LOCATION, TIME, PEOPLE, CONFIRM, FINAL) = range(5)

def generate_calendar_keyboard(context=None):
    """Генерирует клавиатуру с датами на ближайшие 14 дней, исключая сегодняшнюю дату если все времена уже прошли для выбранной локации."""
    keyboard = []
    current_date = datetime.now()
    ru_weekdays = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс']
    # Получаем выбранную локацию, если context передан
    location = None
    times_for_location = None
    if context and hasattr(context, 'user_data'):
        location = context.user_data.get('location')
        times_for_location = LOCATION_TIMES.get(location, None)
    for i in range(14):
        date = current_date + timedelta(days=i)
        date_str = date.strftime("%d.%m.%Y")
        day_name = ru_weekdays[date.weekday()]
        if date.date() < current_date.date():
            continue
        # Исключаем "Сегодня", если все времена уже прошли для выбранной локации
        if i == 0 and times_for_location:
            now = current_date
            times_left = [t for t in times_for_location if datetime.strptime(t, "%H:%M").time() > now.time()]
            if not times_left:
                continue
            button_text = f"Сегодня ({date_str})"
        elif i == 0:
            button_text = f"Сегодня ({date_str})"
        elif i == 1:
            button_text = f"Завтра ({date_str})"
        else:
            button_text = f"{day_name} {date_str}"
        keyboard.append([InlineKeyboardButton(button_text, callback_data=f"date_{date_str}")])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    return InlineKeyboardMarkup(keyboard)

def generate_people_keyboard():
    """Генерирует клавиатуру для выбора количества пассажиров"""
    keyboard = []
    
    # Создаем кнопки от 1 до 6 пассажиров
    for i in range(1, 7):
        keyboard.append([InlineKeyboardButton(f"{i} {'человек' if i == 1 else 'человека' if i < 5 else 'человек'}", callback_data=f"people_{i}")])
    
    # Добавляем кнопку "Отмена"
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
    
    return InlineKeyboardMarkup(keyboard)

logging.basicConfig(format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Очищаем данные пользователя при новом старте
    context.user_data.clear()
    
    reply_keyboard = [["Забронировать экскурсию"]]
    await update.message.reply_text(
        "Привет! Я бот для бронирования джип-туров. Нажми кнопку, чтобы начать:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return LOCATION

async def choose_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Показываем список локаций
    reply_keyboard = [[loc] for loc in LOCATIONS]
    await update.message.reply_text(
        "Выбери локацию:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return LOCATION

async def handle_location_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора локации"""
    context.user_data['location'] = update.message.text
    await update.message.reply_text(
        f"📍 Выбрана локация: {update.message.text}\n\nВыбери дату:",
        reply_markup=generate_calendar_keyboard(context)
    )
    return TIME



async def choose_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['date'] = update.message.text
    reply_keyboard = [[t] for t in TIMES]
    await update.message.reply_text(
        "Выбери время:",
        reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
    )
    return PEOPLE

async def handle_date_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора даты из календаря"""
    query = update.callback_query
    await query.answer()
    if query.data == "cancel":
        await query.edit_message_text("Бронирование отменено.")
        return ConversationHandler.END
    if query.data.startswith("date_"):
        selected_date = query.data.replace("date_", "")
        context.user_data['date'] = selected_date
        # Получаем выбранную локацию
        location = context.user_data.get('location')
        times_for_location = LOCATION_TIMES.get(location, [])
        # Если выбрана сегодняшняя дата, показываем только будущие времена
        from datetime import datetime
        date_obj = datetime.strptime(selected_date, "%d.%m.%Y")
        now = datetime.now()
        if date_obj.date() == now.date():
            available_times = [t for t in times_for_location if datetime.strptime(t, "%H:%M").time() > now.time()]
        else:
            available_times = times_for_location
        time_keyboard = [[InlineKeyboardButton(t, callback_data=f"time_{t}")] for t in available_times]
        time_keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="cancel")])
        await query.edit_message_text(
            f"📅 Выбрана дата: {selected_date}\n\nВыбери время:",
            reply_markup=InlineKeyboardMarkup(time_keyboard)
        )
        return PEOPLE
    return TIME

async def choose_people(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['time'] = update.message.text
    await update.message.reply_text(
        "На какое количество человек оформить бронирование? (введи число)",
        reply_markup=ReplyKeyboardRemove()
    )
    return CONFIRM

async def handle_people_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора количества пассажиров"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("Бронирование отменено.")
        return ConversationHandler.END
    
    if query.data.startswith("people_"):
        selected_people = query.data.replace("people_", "")
        context.user_data['people'] = selected_people
        
        # Показываем подтверждение бронирования
        booking_summary = (
            f"📋 Подтверждение бронирования:\n\n"
            f"📍 Локация: {context.user_data['location']}\n"
            f"📅 Дата: {context.user_data['date']}\n"
            f"⏰ Время: {context.user_data['time']}\n"
            f"👥 Количество: {selected_people} {'человек' if selected_people == '1' else 'человека' if int(selected_people) < 5 else 'человек'}\n\n"
            f"Подтверждаете бронирование?"
        )
        
        # Создаем кнопки подтверждения
        confirm_keyboard = [
            [InlineKeyboardButton("✅ Подтвердить", callback_data="confirm_yes")],
            [InlineKeyboardButton("❌ Отменить", callback_data="cancel")]
        ]
        
        await query.edit_message_text(
            booking_summary,
            reply_markup=InlineKeyboardMarkup(confirm_keyboard)
        )
        return FINAL
    
    return PEOPLE

async def handle_time_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик выбора времени"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("Бронирование отменено.")
        return ConversationHandler.END
    
    if query.data.startswith("time_"):
        selected_time = query.data.replace("time_", "")
        context.user_data['time'] = selected_time
        
        await query.edit_message_text(
            f"⏰ Выбрано время: {selected_time}\n\nВыбери количество пассажиров:",
            reply_markup=generate_people_keyboard()
        )
        return CONFIRM
    
    return PEOPLE

async def confirm(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['people'] = update.message.text
    # Проверка на дубликат
    if booking_exists(
        update.message.from_user.id,
        context.user_data['location'],
        context.user_data['date'],
        context.user_data['time']
    ):
        await update.message.reply_text(
            "❗️Вы уже забронировали эту экскурсию на выбранное время!"
        )
        return ConversationHandler.END
    # Сохраняем бронирование
    booking_data = {
        'location': context.user_data['location'],
        'date': context.user_data['date'],
        'time': context.user_data['time'],
        'people': context.user_data['people'],
        'user_id': update.message.from_user.id,
        'username': update.message.from_user.username,
        'first_name': update.message.from_user.first_name,
        'chat_id': update.message.chat_id
    }
    
    saved_booking = add_booking(booking_data)
    
    booking_info = (
        f"ID: #{saved_booking['id']}\n"
        f"Локация: {context.user_data['location']}\n"
        f"Дата: {context.user_data['date']}\n"
        f"Время: {context.user_data['time']}\n"
        f"Количество человек: {context.user_data['people']}\n"
        f"Пользователь: @{update.message.from_user.username} ({update.message.from_user.first_name})"
    )
    
    await update.message.reply_text(
        f"✅ Спасибо! Ваше бронирование #{saved_booking['id']} принято.\n\n"
        f"📋 Детали:\n{booking_info}\n\n"
        f"Мы свяжемся с вами для подтверждения."
    )
    
    # Отправка уведомления админу
    admin_message = f"🚗 НОВОЕ БРОНИРОВАНИЕ ДЖИП-ТУРА #{saved_booking['id']}\n\n{booking_info}"
    
    ADMIN_CHAT_IDS = [int(cid) for cid in os.getenv("ADMIN_CHAT_IDS", str(os.getenv("ADMIN_CHAT_ID", "")).strip()).split(",") if cid.strip()]
    
    # Отправляем уведомление всем администраторам
    for admin_id in ADMIN_CHAT_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_message)
            print(f"✅ Уведомление отправлено админу (chat_id: {admin_id})")
        except Exception as e:
            print(f"❌ Ошибка отправки админу {admin_id}: {e}")
            print(f"=== НОВОЕ БРОНИРОВАНИЕ ===")
            print(admin_message)
            print("==========================")
    
    return ConversationHandler.END

async def handle_confirm_booking(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик подтверждения бронирования"""
    query = update.callback_query
    await query.answer()
    
    if query.data == "cancel":
        await query.edit_message_text("Бронирование отменено.")
        return ConversationHandler.END
    
    if query.data == "confirm_yes":
        # Проверка на дубликат
        if booking_exists(
            query.from_user.id,
            context.user_data['location'],
            context.user_data['date'],
            context.user_data['time']
        ):
            await query.edit_message_text(
                "❗️Вы уже забронировали эту экскурсию на выбранное время!"
            )
            return ConversationHandler.END
        # Сохраняем бронирование
        booking_data = {
            'location': context.user_data['location'],
            'date': context.user_data['date'],
            'time': context.user_data['time'],
            'people': context.user_data['people'],
            'user_id': query.from_user.id,
            'username': query.from_user.username,
            'first_name': query.from_user.first_name,
            'chat_id': query.message.chat_id
        }
        
        saved_booking = add_booking(booking_data)
        
        booking_info = (
            f"ID: #{saved_booking['id']}\n"
            f"Локация: {context.user_data['location']}\n"
            f"Дата: {context.user_data['date']}\n"
            f"Время: {context.user_data['time']}\n"
            f"Количество человек: {context.user_data['people']}\n"
            f"Пользователь: @{query.from_user.username} ({query.from_user.first_name})"
        )
        
        await query.edit_message_text(
            f"✅ Спасибо! Ваше бронирование #{saved_booking['id']} принято.\n\n"
            f"📋 Детали:\n{booking_info}\n\n"
            f"Мы свяжемся с вами для подтверждения."
        )
        
        # Отправка уведомления админу
        admin_message = f"🚗 НОВОЕ БРОНИРОВАНИЕ ДЖИП-ТУРА #{saved_booking['id']}\n\n{booking_info}"
        
        ADMIN_CHAT_IDS = [int(cid) for cid in os.getenv("ADMIN_CHAT_IDS", str(os.getenv("ADMIN_CHAT_ID", "")).strip()).split(",") if cid.strip()]
        
        # Отправляем уведомление всем администраторам
        for admin_id in ADMIN_CHAT_IDS:
            try:
                await context.bot.send_message(chat_id=admin_id, text=admin_message)
                print(f"✅ Уведомление отправлено админу (chat_id: {admin_id})")
            except Exception as e:
                print(f"❌ Ошибка отправки админу {admin_id}: {e}")
                print(f"=== НОВОЕ БРОНИРОВАНИЕ ===")
                print(admin_message)
                print("==========================")
        
        return ConversationHandler.END
    
    return CONFIRM

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отменяет текущее бронирование"""
    context.user_data.clear()
    await update.message.reply_text(
        '❌ Бронирование отменено. Напишите /start для нового бронирования.', 
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def clear(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Очищает данные пользователя и сбрасывает состояние"""
    context.user_data.clear()
    # Принудительно завершаем разговор
    await update.message.reply_text(
        '🧹 Данные очищены. Напишите /start для начала работы.', 
        reply_markup=ReplyKeyboardRemove()
    )
    return ConversationHandler.END

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик команды /start вне ConversationHandler"""
    # Очищаем данные пользователя при новом старте
    context.user_data.clear()
    reply_keyboard = [["Забронировать экскурсию"]]
    # Проверяем, был ли параметр start
    if hasattr(context, 'args') and context.args and context.args[0] == "from_channel":
        await update.message.reply_text(
            "Добро пожаловать! Нажмите кнопку ниже, чтобы начать бронирование:",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
        return LOCATION
    else:
        await update.message.reply_text(
            "Привет! Я бот для бронирования джип-туров. Нажми кнопку, чтобы начать:",
            reply_markup=ReplyKeyboardMarkup(reply_keyboard, one_time_keyboard=True)
        )
        return LOCATION

async def get_my_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для получения chat_id пользователя"""
    user_id = update.message.from_user.id
    chat_id = update.message.chat_id
    username = update.message.from_user.username
    first_name = update.message.from_user.first_name
    chat_type = update.message.chat.type
    
    message = f"🔍 Информация о чате:\n\n"
    message += f"Chat Type: {chat_type}\n"
    message += f"Chat ID: {chat_id}\n"
    message += f"Chat Title: {update.message.chat.title or 'N/A'}\n"
    message += f"Username: @{username or 'N/A'}\n"
    message += f"Имя: {first_name or 'N/A'}\n\n"
    message += f"💡 Для настройки уведомлений используй Chat ID: {chat_id}"
    
    # Также выводим в консоль для удобства
    print(f"=== ИНФОРМАЦИЯ О ЧАТЕ ===")
    print(f"Chat Type: {chat_type}")
    print(f"Chat ID: {chat_id}")
    print(f"Chat Title: {update.message.chat.title or 'N/A'}")
    print(f"Username: @{username or 'N/A'}")
    print(f"Имя: {first_name or 'N/A'}")
    print("==========================")
    
    await update.message.reply_text(message)

async def show_bookings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для просмотра всех бронирований (только для админа)"""
    # Проверяем, что это админ
    if update.message.chat_id != ADMIN_CHAT_IDS[0]:  # Твой chat_id
        await update.message.reply_text("❌ У вас нет доступа к этой команде.")
        return
    
    bookings = get_all_bookings()
    
    if not bookings:
        await update.message.reply_text("📋 Бронирований пока нет.")
        return
    
    message = "📋 Список всех бронирований:\n\n"
    
    for booking in bookings:
        status_emoji = "🆕" if booking.get('status') == 'new' else "✅" if booking.get('status') == 'confirmed' else "❌"
        message += f"{status_emoji} #{booking['id']} - {booking['location']}\n"
        message += f"📅 {booking['date']} в {booking['time']}\n"
        message += f"👥 {booking['people']} чел. | @{booking['username']}\n"
        message += f"⏰ {booking['timestamp'][:16].replace('T', ' ')}\n\n"
    
    # Разбиваем на части, если сообщение слишком длинное
    if len(message) > 4096:
        parts = [message[i:i+4096] for i in range(0, len(message), 4096)]
        for part in parts:
            await update.message.reply_text(part)
    else:
        await update.message.reply_text(message)

async def channel_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда для получения информации о канале"""
    chat = update.message.chat
    
    message = f"📢 Информация о канале:\n\n"
    message += f"Название: {chat.title}\n"
    message += f"Тип: {chat.type}\n"
    message += f"Chat ID: {chat.id}\n"
    message += f"Username: @{chat.username or 'Нет'}\n"
    message += f"Описание: {chat.description or 'Нет'}\n"
    message += f"Количество участников: {chat.member_count or 'Неизвестно'}\n\n"
    message += f"💡 Chat ID для настройки: {chat.id}"
    
    # Выводим в консоль
    print(f"=== ИНФОРМАЦИЯ О КАНАЛЕ ===")
    print(f"Название: {chat.title}")
    print(f"Тип: {chat.type}")
    print(f"Chat ID: {chat.id}")
    print(f"Username: @{chat.username or 'Нет'}")
    print("============================")
    
    await update.message.reply_text(message)

async def get_channel_info_direct(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Прямое получение информации о канале через API"""
    try:
        # Получаем информацию о чате через API
        chat = await context.bot.get_chat(chat_id=update.message.chat_id)
        
        message = f"📢 Информация о канале (через API):\n\n"
        message += f"Название: {chat.title}\n"
        message += f"Тип: {chat.type}\n"
        message += f"Chat ID: {chat.id}\n"
        message += f"Username: @{chat.username or 'Нет'}\n"
        message += f"Описание: {chat.description or 'Нет'}\n"
        message += f"Количество участников: {chat.member_count or 'Неизвестно'}\n\n"
        message += f"💡 Chat ID для настройки: {chat.id}"
        
        # Выводим в консоль
        print(f"=== ИНФОРМАЦИЯ О КАНАЛЕ (API) ===")
        print(f"Название: {chat.title}")
        print(f"Тип: {chat.type}")
        print(f"Chat ID: {chat.id}")
        print(f"Username: @{chat.username or 'Нет'}")
        print("==================================")
        
        await update.message.reply_text(message)
        
    except Exception as e:
        error_message = f"❌ Ошибка получения информации о канале: {e}"
        print(f"Ошибка: {e}")
        await update.message.reply_text(error_message)

# Удаляем обработчик сообщений из каналов и связанные функции

def main():
    application = Application.builder().token(BOT_TOKEN).build()

    # Добавляем обработчики команд для пользователя и администраторов
    application.add_handler(CommandHandler('get_my_id', get_my_id))
    application.add_handler(CommandHandler('bookings', show_bookings))
    application.add_handler(CommandHandler('clear', clear))
    application.add_handler(CommandHandler('channel_info', channel_info))
    application.add_handler(CommandHandler('get_channel_info', get_channel_info_direct))
    application.add_handler(CommandHandler('start', start_command))

    # ConversationHandler только для личного бронирования
    conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^Забронировать экскурсию$'), choose_location)],
        states={
            LOCATION: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_location_selection)],
            TIME: [CallbackQueryHandler(handle_date_selection)],
            PEOPLE: [CallbackQueryHandler(handle_time_selection)],
            CONFIRM: [CallbackQueryHandler(handle_people_selection)],
            FINAL: [CallbackQueryHandler(handle_confirm_booking)],
        },
        fallbacks=[CommandHandler('cancel', cancel), CommandHandler('clear', clear)],
        allow_reentry=True
    )
    application.add_handler(conv_handler)
    print("Бот запущен. Нажмите Ctrl+C для остановки.")
    application.run_polling()

if __name__ == '__main__':
    main() 