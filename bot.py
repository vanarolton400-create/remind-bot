import asyncio
import json
import os
from datetime import datetime, timedelta
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, ConversationHandler

TOKEN = "8890934172:AAGOosCXBaStONs-nzXNWED5w2ikXT0SZMY"

# Хранилище напоминаний
reminders = {}

# Состояния для ConversationHandler
TEXT, TIME = range(2)

# ===== ФУНКЦИИ РАБОТЫ С ФАЙЛОМ =====
def load_reminders():
    global reminders
    if os.path.exists("reminders.json"):
        try:
            with open("reminders.json", "r", encoding="utf-8") as f:
                data = json.load(f)
                for user_id, user_reminders in data.items():
                    reminders[user_id] = []
                    for rem in user_reminders:
                        rem["time"] = datetime.fromisoformat(rem["time"])
                        reminders[user_id].append(rem)
        except:
            reminders = {}

def save_reminders():
    data = {}
    for user_id, user_reminders in reminders.items():
        data[user_id] = []
        for rem in user_reminders:
            data[user_id].append({"text": rem["text"], "time": rem["time"].isoformat()})
    with open("reminders.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

# ===== ФОНОВАЯ ЗАДАЧА =====
async def check_reminders(app):
    while True:
        now = datetime.now()
        to_delete = []
        for user_id, user_reminders in reminders.items():
            for i, rem in enumerate(user_reminders):
                if rem["time"] <= now:
                    try:
                        await app.bot.send_message(
                            chat_id=int(user_id),
                            text=f"⏰ НАПОМИНАНИЕ!\n\n{rem['text']}"
                        )
                    except:
                        pass
                    to_delete.append((user_id, i))
        for user_id, i in sorted(to_delete, key=lambda x: x[1], reverse=True):
            del reminders[user_id][i]
            if not reminders[user_id]:
                del reminders[user_id]
        if to_delete:
            save_reminders()
        await asyncio.sleep(30)

# ===== КОМАНДЫ =====
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет! Я бот-напоминалка.\n\n"
        "/new - Создать напоминание\n"
        "/list - Список напоминаний\n"
        "/del - Удалить напоминание\n"
        "/clear - Очистить все\n"
        "/help - Помощь"
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "📖 **Форматы времени:**\n"
        "DD.MM.YYYY HH:MM - точная дата\n"
        "+5m - через 5 минут\n"
        "+1h - через час\n"
        "+1d - через день\n\n"
        "Пример: /new\n"
        "Купить молоко\n"
        "25.12.2026 15:30"
    )

async def new_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📝 Введите текст напоминания:")
    return TEXT

async def get_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["text"] = update.message.text
    await update.message.reply_text(
        "🕐 Введите время:\n"
        "DD.MM.YYYY HH:MM или +5m, +1h, +1d"
    )
    return TIME

async def get_time(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    time_str = update.message.text.strip()
    reminder_time = None
    
    try:
        if "." in time_str and ":" in time_str:
            reminder_time = datetime.strptime(time_str, "%d.%m.%Y %H:%M")
        elif time_str.startswith("+"):
            parts = time_str[1:]
            if parts.endswith("m"):
                reminder_time = datetime.now() + timedelta(minutes=int(parts[:-1]))
            elif parts.endswith("h"):
                reminder_time = datetime.now() + timedelta(hours=int(parts[:-1]))
            elif parts.endswith("d"):
                reminder_time = datetime.now() + timedelta(days=int(parts[:-1]))
            else:
                await update.message.reply_text("❌ Неверный формат. Используйте: +5m, +1h, +1d")
                return TIME
        else:
            await update.message.reply_text("❌ Неверный формат. Используйте DD.MM.YYYY HH:MM или +5m")
            return TIME
        
        if reminder_time <= datetime.now():
            await update.message.reply_text("❌ Время должно быть в будущем!")
            return TIME
        
        if user_id not in reminders:
            reminders[user_id] = []
        reminders[user_id].append({"text": context.user_data["text"], "time": reminder_time})
        save_reminders()
        
        await update.message.reply_text(
            f"✅ Напоминание создано!\n\n"
            f"📝 {context.user_data['text']}\n"
            f"🕐 {reminder_time.strftime('%d.%m.%Y %H:%M')}"
        )
        return ConversationHandler.END
        
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {e}. Попробуйте снова.")
        return TIME

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("❌ Отменено.")
    return ConversationHandler.END

async def list_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in reminders or not reminders[user_id]:
        await update.message.reply_text("📭 Нет напоминаний.")
        return
    
    text = "📋 **Ваши напоминания:**\n\n"
    for i, rem in enumerate(sorted(reminders[user_id], key=lambda x: x["time"]), 1):
        text += f"{i}. {rem['time'].strftime('%d.%m %H:%M')} - {rem['text']}\n"
    await update.message.reply_text(text)

async def delete_reminder(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in reminders or not reminders[user_id]:
        await update.message.reply_text("📭 Нет напоминаний.")
        return
    
    keyboard = []
    for i, rem in enumerate(reminders[user_id]):
        keyboard.append([InlineKeyboardButton(
            f"{i+1}. {rem['time'].strftime('%d.%m %H:%M')} - {rem['text'][:20]}",
            callback_data=f"del_{i}"
        )])
    keyboard.append([InlineKeyboardButton("❌ Отмена", callback_data="del_cancel")])
    
    await update.message.reply_text(
        "Выберите напоминание для удаления:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def delete_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = str(query.from_user.id)
    
    if query.data == "del_cancel":
        await query.edit_message_text("❌ Отменено.")
        return
    
    try:
        index = int(query.data.split("_")[1])
        if user_id in reminders and 0 <= index < len(reminders[user_id]):
            removed = reminders[user_id].pop(index)
            if not reminders[user_id]:
                del reminders[user_id]
            save_reminders()
            await query.edit_message_text(f"✅ Удалено: {removed['text']}")
        else:
            await query.edit_message_text("❌ Не найдено.")
    except:
        await query.edit_message_text("❌ Ошибка.")

async def clear_reminders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = str(update.effective_user.id)
    if user_id not in reminders or not reminders[user_id]:
        await update.message.reply_text("📭 Нет напоминаний.")
        return
    count = len(reminders[user_id])
    del reminders[user_id]
    save_reminders()
    await update.message.reply_text(f"✅ Удалено {count} напоминаний.")

# ===== ЗАПУСК =====
def main():
    load_reminders()
    
    app = Application.builder().token(TOKEN).build()
    
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("new", new_reminder)],
        states={
            TEXT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_text)],
            TIME: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_time)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )
    
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(conv_handler)
    app.add_handler(CommandHandler("list", list_reminders))
    app.add_handler(CommandHandler("del", delete_reminder))
    app.add_handler(CallbackQueryHandler(delete_callback, pattern="del_"))
    app.add_handler(CommandHandler("clear", clear_reminders))
    
    # Запускаем фоновую проверку
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(check_reminders(app))
    
    print("Бот запущен!")
    app.run_polling()

if __name__ == "__main__":
    main()
