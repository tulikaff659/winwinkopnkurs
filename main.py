import os
import json
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, FSInputFile
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()

# Tokenni olish
TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = 6935090105  # Admin ID

# Bot va dispatcher sozlamalari
bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Logging
logging.basicConfig(level=logging.INFO)

# JSON fayl yordamida APK ma'lumotlarini saqlash
APK_DATA_FILE = "apk_data.json"

def load_apk_data():
    try:
        with open(APK_DATA_FILE, "r") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"text": None, "file_id": None}

def save_apk_data(data):
    with open(APK_DATA_FILE, "w") as f:
        json.dump(data, f, indent=4)

# FSM holatlari (admin APK qo'shish uchun)
class AddApkStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_file = State()

# /start komandasi
@dp.message(CommandStart())
async def start_handler(message: types.Message):
    apk_data = load_apk_data()
    text = (
        "🎰 *Winwin bukmekerida konkurs!*\n\n"
        "Konkursda gʻoliblar qatorida boʻlish uchun *win_21450* promokod orqali "
        "winwinda roʻyxatdan oʻtish talab qilinadi. Ball toʻplab imkoniyatni oshiring!\n\n"
        "🎁 *Sovrinlar:* bosh sovrin BMW va 100 dan ortiq sovgʻalar. "
        "Raisboydan keyin BMVni siz yutishingiz mumkin.\n\n"
        "Endi bloggerlar qatnashmaydi, konkurs oddiy xalq uchun."
    )
    # Inline tugmalar
    builder = InlineKeyboardBuilder()
    builder.button(text="📋 Konkurs haqida maʼlumot", callback_data="info")
    builder.button(text="📝 Roʻyxatdan oʻtish", url="https://refpa712080.pro/L?tag=d_4543807m_64485c_&site=4543807&ad=64485")
    if apk_data.get("file_id"):  # APK mavjud boʻlsa
        builder.button(text="📲 APK yuklash", callback_data="download_apk")
    builder.adjust(1)  # Har bir qatorda bitta tugma

    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

# "Konkurs haqida maʼlumot" tugmasi bosilganda
@dp.callback_query(F.data == "info")
async def info_callback(callback: types.CallbackQuery):
    text = (
        "📌 *Konkurs tafsilotlari:*\n\n"
        "• *Promokod:* win_21450 orqali winwin'da roʻyxatdan oʻting.\n"
        "• Ball toʻplab, imkoniyatingizni oshiring.\n"
        "• Bosh sovrin: *BMW* va 100+ sovgʻalar.\n"
        "• Raisboydan keyin BMW sizniki boʻlishi mumkin.\n"
        "• Endi bloggerlar qatnashmaydi – konkurs oddiy xalq uchun!"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

# "APK yuklash" tugmasi bosilganda
@dp.callback_query(F.data == "download_apk")
async def download_apk_callback(callback: types.CallbackQuery):
    apk_data = load_apk_data()
    if not apk_data.get("file_id"):
        await callback.message.answer("❌ APK hozircha mavjud emas.")
        await callback.answer()
        return

    text = apk_data.get("text", "📦 Winwin ilovasi")
    file_id = apk_data["file_id"]
    try:
        await callback.message.answer_document(document=file_id, caption=text)
    except Exception:
        await callback.message.answer("❌ APK faylini yuborishda xatolik yuz berdi.")
    await callback.answer()

# ------------------- Admin buyruqlari -------------------

# /add_apk - APK qo'shish (faqat admin)
@dp.message(Command("add_apk"))
async def add_apk_start(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Siz admin emassiz.")
        return
    await message.answer("✍️ APK uchun matn (taʼrif) yuboring:")
    await state.set_state(AddApkStates.waiting_for_text)

# Matnni qabul qilish
@dp.message(AddApkStates.waiting_for_text)
async def add_apk_text(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.clear()
        return
    text = message.text
    await state.update_data(apk_text=text)
    await message.answer("📎 Endi APK faylini yuboring (fayl sifatida).")
    await state.set_state(AddApkStates.waiting_for_file)

# Faylni qabul qilish va saqlash
@dp.message(AddApkStates.waiting_for_file)
async def add_apk_file(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        await state.clear()
        return
    if not message.document:
        await message.answer("❌ Iltimos, APK faylini yuboring.")
        return

    file_id = message.document.file_id
    data = await state.get_data()
    apk_text = data.get("apk_text", "Winwin APK")

    # JSON ga yozish
    apk_data = {"text": apk_text, "file_id": file_id}
    save_apk_data(apk_data)

    await message.answer("✅ APK muvaffaqiyatli qoʻshildi!")
    await state.clear()

# /remove_apk - APKni o'chirish
@dp.message(Command("remove_apk"))
async def remove_apk(message: types.Message):
    if message.from_user.id != ADMIN_ID:
        await message.answer("⛔ Siz admin emassiz.")
        return
    # Ma'lumotlarni o'chirish
    save_apk_data({"text": None, "file_id": None})
    await message.answer("✅ APK o'chirildi.")

# /cancel - holatni bekor qilish
@dp.message(Command("cancel"))
async def cancel_handler(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID:
        return
    current_state = await state.get_state()
    if current_state is None:
        await message.answer("❌ Hech qanday jarayon yo'q.")
        return
    await state.clear()
    await message.answer("✅ Jarayon bekor qilindi.")

# ------------------- Botni ishga tushirish -------------------
async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
