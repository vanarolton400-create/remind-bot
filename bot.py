import asyncio
import datetime
import json
import os
from typing import Dict, List
from aiogram import Bot, Dispatcher, types
from aiogram.filters import Command
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
                    to_remove.append((user_id, i))
        
        for user_id, i in sorted(to_remove, key=lambda x: x[1], reverse=True):
            del reminders[user_id][i]
            if not reminders[user_id]:
                del reminders[user_id]
        
        if to_remove:
            save_reminders()
        
        await asyncio.sleep(30)

# --- Функции для создания кнопок времени ---
def get_time_keyboard():
    """Создает клавиатуру с вариантами времени."""
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="⏰ Через 5 мин", callback_data="time_5m"),
            InlineKeyboardButton(text="⏰ Через 15 мин", callback_data="time_15m"),
            InlineKeyboardButton(text="⏰ Через 30 мин", callback_data="time_30m")
        ],
        [
            InlineKeyboardButton(text="⏰ Через 1 час", callback_data="time_1h"),
            InlineKeyboardButton(text="⏰ Через 2 часа", callback_data="time_2h"),
            InlineKeyboardButton(text="⏰ Через 3 часа", callback_data="time_3h")
        ],
        [
            InlineKeyboardButton(text="📅 Через 1 день", callback_data="time_1d"),
            InlineKeyboardButton(text="📅 Через 2 дня", callback_data="time_2d"),
            InlineKeyboardButton(text="📅 Через 3 дня", callback_data="time_3d")
        ],
        [
            InlineKeyboardButton(text="📅 Через 1 неделю", callback_data="time_1w"),
            InlineKeyboardButton(text="📅 Через 2 недели", callback_data="time_2w"),
            InlineKeyboardButton(text="📅 Через месяц", callback_data="time_1M")
        ],
        [
            InlineKeyboardButton(text="✏️ Своё время", callback_data="time_custom")
        ]
    ])
    return keyboard

def get_confirm_keyboard():
    """Клавиатура подтверждения."""
    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Да, создать", callback_data="confirm_yes"),
            InlineKeyboardButton(text="❌ Отмена", callback_data="confirm_no")
        ]
    ])

# --- Команда /start ---
@dp.message(Command("start"))
async def cmd_start(message: Message):
    await message.answer(
        "👋 Привет! Я бот для напоминаний.\n\n"
        "Команды:\n"
        "/new - Создать новое напоминание\n"
        "/list - Показать все напоминания\n"
        "/del - Удалить напоминание\n"
        "/clear - Очистить все напоминания\n\n"
        "Нажми /new и выбери время из кнопок!"
    )

# --- Команда /new ---
@dp.message(Command("new"))
async def cmd_new(message: Message, state: FSMContext):
    await state.set_state(ReminderForm.waiting_for_text)
    await message.answer(
        "📝 Введите текст напоминания:\n"
        "(можно отменить командой /cancel)"
    )

@dp.message(ReminderForm.waiting_for_text)
async def process_text(message: Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        await message.answer("❌ Создание отменено.")
        return
    
    await state.update_data(text=message.text)
    await state.set_state(ReminderForm.waiting_for_time)
    
    await message.answer(
        "🕐 Выберите время напоминания:",
        reply_markup=get_time_keyboard()
    )

# --- Обработка выбора времени ---
@dp.callback_query()
async def handle_time_callback(callback: CallbackQuery, state: FSMContext):
    if callback.data.startswith('time_'):
        await callback.answer()
        
        user_data = await state.get_data()
        text = user_data.get('text')
        
        now = datetime.datetime.now()
        time_map = {
            'time_5m': now + datetime.timedelta(minutes=5),
            'time_15m': now + datetime.timedelta(minutes=15),
            'time_30m': now + datetime.timedelta(minutes=30),
            'time_1h': now + datetime.timedelta(hours=1),
            'time_2h': now + datetime.timedelta(hours=2),
            'time_3h': now + datetime.timedelta(hours=3),
            'time_1d': now + datetime.timedelta(days=1),
            'time_2d': now + datetime.timedelta(days=2),
            'time_3d': now + datetime.timedelta(days=3),
            'time_1w': now + datetime.timedelta(weeks=1),
            'time_2w': now + datetime.timedelta(weeks=2),
            'time_1M': now + datetime.timedelta(days=30),
        }
        
        if callback.data == 'time_custom':
            await callback.message.edit_text(
                "✏️ Введите время в формате:\n"
                "`DD.MM.YYYY HH:MM`\n\n"
                "Например: `25.12.2026 15:30`\n"
                "Или `+5m` - через 5 минут\n"
                "Или `+1h` - через час\n"
                "Или `+1d` - через день",
                parse_mode="Markdown"
            )
            return
        
        reminder_time = time_map.get(callback.data)
        if reminder_time:
            # Сохраняем время в state
            await state.update_data(time=reminder_time)
            
            formatted_time = reminder_time.strftime("%d.%m.%Y в %H:%M")
            await callback.message.edit_text(
                f"📝 {text}\n"
                f"🕐 {formatted_time}\n\n"
                f"Всё верно?",
                reply_markup=get_confirm_keyboard()
            )

# --- Обработка подтверждения ---
@dp.callback_query()
async def handle_confirm(callback: CallbackQuery, state: FSMContext):
    if callback.data == 'confirm_yes':
        await callback.answer()
        
        user_data = await state.get_data()
        text = user_data.get('text')
        reminder_time = user_data.get('time')
        
        if not reminder_time:
            await callback.message.edit_text("❌ Ошибка: время не выбрано. Попробуйте /new заново.")
            await state.clear()
            return
        
        user_id = str(callback.from_user.id)
        if user_id not in reminders:
            reminders[user_id] = []
        
        reminders[user_id].append({
            'text': text,
            'time': reminder_time
        })
        
        save_reminders()
        await state.clear()
        
        formatted_time = reminder_time.strftime("%d.%m.%Y в %H:%M")
        await callback.message.edit_text(
            f"✅ Напоминание создано!\n\n"
            f"📝 {text}\n"
            f"🕐 {formatted_time}"
        )
    
    elif callback.data == 'confirm_no':
        await callback.answer()
        await state.clear()
        await callback.message.edit_text("❌ Создание отменено.")

# --- Обработка кастомного времени ---
@dp.message(ReminderForm.waiting_for_time)
async def process_custom_time(message: Message, state: FSMContext):
    if message.text.startswith('/'):
        await state.clear()
        await message.answer("❌ Создание отменено.")
        return
    
    user_data = await state.get_data()
    text = user_data.get('text')
    time_str = message.text.strip()
    reminder_time = None
    
    try:
        if '.' in time_str and ':' in time_str:
            reminder_time = datetime.datetime.strptime(time_str, "%d.%m.%Y %H:%M")
        elif time_str.startswith('+'):
            parts = time_str[1:]
            if parts.endswith('m'):
                reminder_time = datetime.datetime.now() + datetime.timedelta(minutes=int(parts[:-1]))
            elif parts.endswith('h'):
                reminder_time = datetime.datetime.now() + datetime.timedelta(hours=int(parts[:-1]))
            elif parts.endswith('d'):
                reminder_time = datetime.datetime.now() + datetime.timedelta(days=int(parts[:-1]))
            else:
                await message.answer("❌ Неверный формат. Используйте: +5m, +1h, +1d")
                return
        else:
            await message.answer("❌ Неверный формат. Используйте `DD.MM.YYYY HH:MM` или `+5m`")
            return
        
        if reminder_time <= datetime.datetime.now():
            await message.answer("❌ Время должно быть в будущем!")
            return
        
        await state.update_data(time=reminder_time)
        formatted_time = reminder_time.strftime("%d.%m.%Y в %H:%M")
        await message.answer(
            f"📝 {text}\n"
            f"🕐 {formatted_time}\n\n"
            f"Всё верно?",
            reply_markup=get_confirm_keyboard()
        )
        
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}. Попробуйте снова.")

# --- Команда /cancel ---
@dp.message(Command("cancel"))
async def cmd_cancel(message: Message, state: FSMContext):
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("❌ Нет активного процесса.")
        return
    
    await state.clear()
    await message.answer("❌ Операция отменена.")

# --- Команда /list ---
@dp.message(Command("list"))
async def cmd_list(message: Message):
    user_id = str(message.from_user.id)
    
    if user_id not in reminders or not reminders[user_id]:
        await message.answer("📭 У вас нет активных напоминаний.")
        return
    
    user_reminders = sorted(reminders[user_id], key=lambda x: x['time'])
    response = "📋 **Ваши напоминания:**\n\n"
    for i, rem in enumerate(user_reminders, 1):
        time_str = rem['time'].strftime("%d.%m.%Y %H:%M")
        response += f"{i}. {time_str} - {rem['text']}\n"
    
    await message.answer(response)

# --- Команда /del ---
@dp.message(Command("del"))
async def cmd_del(message: Message):
    user_id = str(message.from_user.id)
    
    if user_id not in reminders or not reminders[user_id]:
        await message.answer("📭 Нет напоминаний.")
        return
    
    args = message.text.split()
    if len(args) < 2:
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
                f"✅ Удалено: {removed['text']}\n"
                f"🕐 {removed['time'].strftime('%d.%m.%Y %H:%M')}"
            )
        else:
            await message.answer("❌ Неверный номер.")
    except:
        await message.answer("❌ Используйте: /del номер")

# --- Обработка удаления через callback ---
@dp.callback_query()
async def handle_delete_callback(callback: CallbackQuery):
    if callback.data.startswith('del_'):
        user_id = str(callback.from_user.id)
        
        if callback.data == 'del_cancel':
            await callback.message.delete()
            await callback.answer("❌ Отменено")
            return
        
        try:
            index = int(callback.data.split('_')[1])
            if user_id in reminders and 0 <= index < len(reminders[user_id]):
                removed = reminders[user_id].pop(index)
                if not reminders[user_id]:
                    del reminders[user_id]
                save_reminders()
                
                await callback.message.delete()
                await callback.answer("✅ Удалено!")
                await callback.message.answer(
                    f"✅ Удалено: {removed['text']}\n"
                    f"🕐 {removed['time'].strftime('%d.%m.%Y %H:%M')}"
                )
            else:
                await callback.answer("❌ Не найдено")
        except:
            await callback.answer("❌ Ошибка")

# --- Команда /clear ---
@dp.message(Command("clear"))
async def cmd_clear(message: Message):
    user_id = str(message.from_user.id)
    
    if user_id not in reminders or not reminders[user_id]:
        await message.answer("📭 Нет напоминаний.")
        return
    
    count = len(reminders[user_id])
    del reminders[user_id]
    save_reminders()
    
    await message.answer(f"✅ Удалено {count} напоминаний.")

# --- Команда /help ---
@dp.message(Command("help"))
async def cmd_help(message: Message):
    await message.answer(
        "🤖 **Помощь**\n\n"
        "Команды:\n"
        "/new - Создать напоминание\n"
        "/list - Список напоминаний\n"
        "/del [номер] - Удалить\n"
        "/clear - Очистить всё\n\n"
        "При создании просто выбери время из кнопок!\n"
        "Или введи своё время в формате DD.MM.YYYY HH:MM"
    )

# --- Запуск бота ---
async def main():
    load_reminders()
    print(f"Загружено напоминаний: {sum(len(r) for r in reminders.values())}")
    
    asyncio.create_task(check_reminders())
    
    print("Бот запущен!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
