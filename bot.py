import asyncio
import datetime
import json
import os
from typing import Dict, List
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command, StateFilter
from aiogram.types import Message, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# --- Конфигурация ---
TOKEN = '8890934172:AAGOosCXBaStONs-nzXNWED5w2ikXT0SZMY'
REMINDERS_FILE = 'reminders.json'

# --- Инициализация бота ---
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Структура для хранения напоминаний в памяти
# { str(user_id): [ {"text": str, "time": datetime.datetime} ] }
reminders: Dict[str, List[dict]] = {}

# --- Машина состояний для создания напоминания ---
class ReminderForm(StatesGroup):
    waiting_for_text = State()
    waiting_for_time = State()

# --- Загрузка и сохранение данных ---
def load_reminders():
    """Загружает напоминания из JSON-файла."""
    global reminders
    if os.path.exists(REMINDERS_FILE):
        try:
            with open(REMINDERS_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # Преобразуем строки времени обратно в datetime
                for user_id, user_reminders in data.items():
                    reminders[user_id] = []
                    for rem in user_reminders:
                        rem['time'] = datetime.datetime.fromisoformat(rem['time'])
                        reminders[user_id].append(rem)
        except Exception as e:
            print(f"Ошибка загрузки напоминаний: {e}")
            reminders = {}

def save_reminders():
    """Сохраняет напоминания в JSON-файл."""
    data = {}
    for user_id, user_reminders in reminders.items():
        data[user_id] = []
        for rem in user_reminders:
            # Преобразуем datetime в строку
            rem_copy = rem.copy()
            rem_copy['time'] = rem_copy['time'].isoformat()
            data[user_id].append(rem_copy)
    
    try:
        with open(REMINDERS_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
    except Exception as e:
        print(f"Ошибка сохранения напоминаний: {e}")

# --- Фоновая задача для проверки напоминаний ---
async def check_reminders():
    """Проверяет напоминания каждые 30 секунд и отправляет уведомления."""
    while True:
        now = datetime.datetime.now()
        to_remove = []
        
        for user_id, user_reminders in reminders.items():
            for i, rem in enumerate(user_reminders):
                if rem['time'] <= now:
                    try:
                        await bot.send_message(
                            chat_id=int(user_id),
                            text=f"⏰ НАПОМИНАНИЕ!\n\n{rem['text']}"
                        )
                    except Exception as e:
                        print(f"Не удалось отправить напоминание пользователю {user_id}: {e}")
                    
                    # Отмечаем для удаления
                    to_remove.append((user_id, i))
        
        # Удаляем отправленные напоминания (в обратном порядке, чтобы индексы не сбивались)
        for user_id, i in sorted(to_remove, key=lambda x: x[1], reverse=True):
            del reminders[user_id][i]
            if not reminders[user_id]:  # Если список пуст, удаляем ключ
                del reminders[user_id]
        
        # Сохраняем изменения, если что-то удалили
        if to_remove:
            save_reminders()
        
        await asyncio.sleep(30)  # Проверяем каждые 30 секунд

# --- Команда /start ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    """Приветственное сообщение."""
    await message.answer(
        "👋 Привет! Я бот для напоминаний.\n\n"
        "Команды:\n"
        "/new - Создать новое напоминание\n"
        "/list - Показать все напоминания\n"
        "/del - Удалить напоминание\n"
        "/clear - Очистить все напоминания\n\n"
        "Пример: /new\n"
        "Затем введи текст напоминания и дату/время."
    )

# --- Команда /new (создание напоминания) ---
@dp.message(Command("new"))
async def cmd_new(message: Message, state: FSMContext):
    """Начинает процесс создания напоминания."""
    await state.set_state(ReminderForm.waiting_for_text)
    await message.answer(
        "📝 Введите текст напоминания:\n"
        "(можно отменить командой /cancel)"
    )

@dp.message(ReminderForm.waiting_for_text)
async def process_text(message: Message, state: FSMContext):
    """Обрабатывает текст напоминания."""
    if message.text.startswith('/'):
        await state.clear()
        await message.answer("❌ Создание отменено.")
        return
    
    await state.update_data(text=message.text)
    await state.set_state(ReminderForm.waiting_for_time)
    await message.answer(
        "🕐 Введите дату и время напоминания в формате:\n"
        "`DD.MM.YYYY HH:MM`\n\n"
        "Например: `25.12.2026 15:30`\n"
        "Или `+5m` - через 5 минут\n"
        "Или `+1h` - через час\n"
        "Или `+1d` - через день\n\n"
        "Можно отменить командой /cancel",
        parse_mode="Markdown"
    )

@dp.message(ReminderForm.waiting_for_time)
async def process_time(message: Message, state: FSMContext):
    """Обрабатывает дату/время напоминания."""
    if message.text.startswith('/'):
        await state.clear()
        await message.answer("❌ Создание отменено.")
        return
    
    user_data = await state.get_data()
    text = user_data.get('text')
    
    # Парсим время
    time_str = message.text.strip()
    reminder_time = None
    
    # Попробуем распарсить разные форматы
    try:
        # Формат: DD.MM.YYYY HH:MM
        if '.' in time_str and ':' in time_str:
            reminder_time = datetime.datetime.strptime(time_str, "%d.%m.%Y %H:%M")
        # Относительное время: +5m, +1h, +1d
        elif time_str.startswith('+'):
            parts = time_str[1:]
            if parts.endswith('m'):
                minutes = int(parts[:-1])
                reminder_time = datetime.datetime.now() + datetime.timedelta(minutes=minutes)
            elif parts.endswith('h'):
                hours = int(parts[:-1])
                reminder_time = datetime.datetime.now() + datetime.timedelta(hours=hours)
            elif parts.endswith('d'):
                days = int(parts[:-1])
                reminder_time = datetime.datetime.now() + datetime.timedelta(days=days)
            else:
                await message.answer("❌ Неверный формат относительного времени. Используйте: +5m, +1h, +1d")
                return
        else:
            await message.answer("❌ Неверный формат. Используйте: `DD.MM.YYYY HH:MM` или `+5m`", parse_mode="Markdown")
            return
        
        # Проверяем, что время в будущем
        if reminder_time <= datetime.datetime.now():
            await message.answer("❌ Время должно быть в будущем!")
            return
        
        # Сохраняем напоминание
        user_id = str(message.from_user.id)
        if user_id not in reminders:
            reminders[user_id] = []
        
        reminders[user_id].append({
            'text': text,
            'time': reminder_time
        })
        
        save_reminders()
        await state.clear()
        
        # Форматируем дату для красивого вывода
        formatted_time = reminder_time.strftime("%d.%m.%Y в %H:%M")
        await message.answer(
            f"✅ Напоминание создано!\n\n"
            f"📝 {text}\n"
            f"🕐 {formatted_time}"
        )
        
    except ValueError as e:
        await message.answer(f"❌ Ошибка: {e}\n\nПопробуйте снова или отмените командой /cancel")

# --- Команда /cancel (отмена) ---
@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    """Отменяет текущий процесс."""
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("❌ Нет активного процесса.")
        return
    
    await state.clear()
    await message.answer("❌ Операция отменена.")

# --- Команда /list (список напоминаний) ---
@dp.message(Command("list"))
async def cmd_list(message: Message):
    """Показывает все напоминания пользователя."""
    user_id = str(message.from_user.id)
    
    if user_id not in reminders or not reminders[user_id]:
        await message.answer("📭 У вас нет активных напоминаний.")
        return
    
    # Сортируем по времени
    user_reminders = sorted(reminders[user_id], key=lambda x: x['time'])
    
    response = "📋 **Ваши напоминания:**\n\n"
    for i, rem in enumerate(user_reminders, 1):
        time_str = rem['time'].strftime("%d.%m.%Y %H:%M")
        response += f"`{i}.` **{time_str}** - {rem['text']}\n"
    
    await message.answer(response, parse_mode="Markdown")

# --- Команда /del (удаление напоминания) ---
@dp.message(Command("del"))
async def cmd_del(message: Message):
    """Удаляет напоминание по номеру."""
    user_id = str(message.from_user.id)
    
    if user_id not in reminders or not reminders[user_id]:
        await message.answer("📭 У вас нет активных напоминаний.")
        return
    
    args = message.text.split()
    if len(args) < 2:
        # Показываем список для выбора
        keyboard = InlineKeyboardMarkup(inline_keyboard=[])
        for i, rem in enumerate(reminders[user_id], 1):
            time_str = rem['time'].strftime("%d.%m %H:%M")
            keyboard.inline_keyboard.append([
                InlineKeyboardButton(
                    text=f"{i}. {time_str} - {rem['text'][:20]}...",
                    callback_data=f"del_{i-1}"
                )
            ])
        keyboard.inline_keyboard.append([
            InlineKeyboardButton(text="❌ Отмена", callback_data="del_cancel")
        ])
        
        await message.answer(
            "Выберите напоминание для удаления:",
            reply_markup=keyboard
        )
        return
    
    try:
        index = int(args[1]) - 1
        if 0 <= index < len(reminders[user_id]):
            removed = reminders[user_id].pop(index)
            if not reminders[user_id]:
                del reminders[user_id]
            save_reminders()
            
            await message.answer(
                f"✅ Напоминание удалено:\n"
                f"📝 {removed['text']}\n"
                f"🕐 {removed['time'].strftime('%d.%m.%Y %H:%M')}"
            )
        else:
            await message.answer("❌ Неверный номер напоминания.")
    except ValueError:
        await message.answer("❌ Используйте: `/del номер` или `/del` без аргументов для выбора.")

# --- Обработка callback для удаления ---
@dp.callback_query()
async def handle_callback(callback: CallbackQuery):
    """Обрабатывает нажатия на кнопки."""
    if callback.data.startswith('del_'):
        user_id = str(callback.from_user.id)
        
        if callback.data == 'del_cancel':
            await callback.message.delete()
            await callback.answer("❌ Отменено", show_alert=False)
            return
        
        try:
            index = int(callback.data.split('_')[1])
            if user_id in reminders and 0 <= index < len(reminders[user_id]):
                removed = reminders[user_id].pop(index)
                if not reminders[user_id]:
                    del reminders[user_id]
                save_reminders()
                
                await callback.message.delete()
                await callback.answer(
                    f"✅ Удалено: {removed['text'][:30]}...",
                    show_alert=False
                )
                await callback.message.answer(
                    f"✅ Напоминание удалено:\n"
                    f"📝 {removed['text']}\n"
                    f"🕐 {removed['time'].strftime('%d.%m.%Y %H:%M')}"
                )
            else:
                await callback.answer("❌ Напоминание не найдено", show_alert=True)
        except:
            await callback.answer("❌ Ошибка", show_alert=True)

# --- Команда /clear (очистка всех напоминаний) ---
@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    """Очищает все напоминания пользователя."""
    user_id = str(message.from_user.id)
    
    if user_id not in reminders or not reminders[user_id]:
        await message.answer("📭 У вас нет активных напоминаний.")
        return
    
    count = len(reminders[user_id])
    del reminders[user_id]
    save_reminders()
    
    await message.answer(f"✅ Удалено {count} напоминаний.")

# --- Команда /help ---
@dp.message(Command("help"))
async def cmd_help(message: Message):
    """Показывает справку."""
    await message.answer(
        "🤖 **Помощь по боту напоминаний**\n\n"
        "**Команды:**\n"
        "/start - Приветственное сообщение\n"
        "/new - Создать новое напоминание\n"
        "/list - Показать все напоминания\n"
        "/del [номер] - Удалить напоминание\n"
        "/clear - Очистить все напоминания\n"
        "/help - Показать эту справку\n\n"
        "**Форматы времени:**\n"
        "• `DD.MM.YYYY HH:MM` - точная дата\n"
        "• `+5m` - через 5 минут\n"
        "• `+1h` - через час\n"
        "• `+1d` - через день\n\n"
        "**Пример:**\n"
        "/new\n"
        "Купить молоко\n"
        "25.12.2026 15:30",
        parse_mode="Markdown"
    )

# --- Запуск бота ---
async def main():
    """Главная функция запуска."""
    # Загружаем напоминания
    load_reminders()
    print(f"Загружено напоминаний: {sum(len(r) for r in reminders.values())}")
    
    # Запускаем фоновую задачу
    asyncio.create_task(check_reminders())
    
    # Запускаем бота
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
