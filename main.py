import os
import json
import asyncio
import logging
import traceback
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import InlineKeyboardBuilder
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 6935090105))  # fallback

logging.basicConfig(level=logging.DEBUG)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

APK_DATA_FILE = "apk_data.json"

def load_apk_data():
    try:
        with open(APK_DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {"text": None, "file_id": None}

def save_apk_data(data):
    with open(APK_DATA_FILE, "w") as f:
        json.dump(data, f)

class AddApkStates(StatesGroup):
    waiting_for_text = State()
    waiting_for_file = State()

@dp.message(Command("ping"))
async def ping(message: types.Message):
    await message.answer("pong")

@dp.message(CommandStart())
async def start_handler(message: types.Message):
    try:
        apk_data = load_apk_data()
        text = (
            "🎰 *Winwin bukmekerida konkurs!*\n\n"
            "Konkursda gʻoliblar qatorida boʻlish uchun *win_21450* promokod orqali "
            "winwinda roʻyxatdan oʻtish talab qilinadi. Ball toʻplab imkoniyatni oshiring!\n\n"
            "🎁 *Sovrinlar:* bosh sovrin BMW va 100 dan ortiq sovgʻalar. "
            "Raisboydan keyin BMVni siz yutishingiz mumkin.\n\n"
            "Endi bloggerlar qatnashmaydi, konkurs oddiy xalq uchun."
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="📋 Konkurs haqida maʼlumot", callback_data="info")
        builder.button(text="📝 Roʻyxatdan oʻtish", url="https://refpa712080.pro/L?tag=d_4543807m_64485c_&site=4543807&ad=64485")
        if apk_data.get("file_id"):
            builder.button(text="📲 APK yuklash", callback_data="download_apk")
        builder.adjust(1)
        await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
    except Exception as e:
        logging.error(f"Start handler error: {e}")

@dp.callback_query(F.data == "info")
async def info_callback(callback: types.CallbackQuery):
    try:
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
    except Exception as e:
        logging.error(f"Info callback error: {e}\n{traceback.format_exc()}")
        await callback.answer("Xatolik yuz berdi", show_alert=True)

@dp.callback_query(F.data == "download_apk")
async def download_apk_callback(callback: types.CallbackQuery):
    try:
        apk_data = load_apk_data()
        if not apk_data.get("file_id"):
            await callback.message.answer("❌ APK hozircha mavjud emas.")
            await callback.answer()
            return
        text = apk_data.get("text", "📦 Winwin ilovasi")
        await callback.message.answer_document(document=apk_data["file_id"], caption=text)
        await callback.answer()
    except Exception as e:
        logging.error(f"Download APK error: {e}")

# Admin commands
@dp.message(Command("add_apk"))
async def add_apk_start(message: types.Message, state: FSMContext):
    try:
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔ Siz admin emassiz.")
            return
        await message.answer("✍️ APK uchun matn (taʼrif) yuboring:")
        await state.set_state(AddApkStates.waiting_for_text)
    except Exception as e:
        logging.error(f"Add_apk start error: {e}")

@dp.message(AddApkStates.waiting_for_text)
async def add_apk_text(message: types.Message, state: FSMContext):
    try:
        if message.from_user.id != ADMIN_ID:
            await state.clear()
            return
        await state.update_data(apk_text=message.text)
        await message.answer("📎 Endi APK faylini yuboring.")
        await state.set_state(AddApkStates.waiting_for_file)
    except Exception as e:
        logging.error(f"Add_apk text error: {e}")

@dp.message(AddApkStates.waiting_for_file)
async def add_apk_file(message: types.Message, state: FSMContext):
    try:
        if message.from_user.id != ADMIN_ID:
            await state.clear()
            return
        if not message.document:
            await message.answer("❌ Iltimos, APK faylini yuboring.")
            return
        file_id = message.document.file_id
        data = await state.get_data()
        apk_text = data.get("apk_text", "Winwin APK")
        save_apk_data({"text": apk_text, "file_id": file_id})
        await message.answer("✅ APK muvaffaqiyatli qoʻshildi!")
        await state.clear()
    except Exception as e:
        logging.error(f"Add_apk file error: {e}")

@dp.message(Command("remove_apk"))
async def remove_apk(message: types.Message):
    try:
        if message.from_user.id != ADMIN_ID:
            await message.answer("⛔ Siz admin emassiz.")
            return
        save_apk_data({"text": None, "file_id": None})
        await message.answer("✅ APK o'chirildi.")
    except Exception as e:
        logging.error(f"Remove_apk error: {e}")

@dp.message(Command("cancel"))
async def cancel_handler(message: types.Message, state: FSMContext):
    try:
        if message.from_user.id != ADMIN_ID:
            return
        await state.clear()
        await message.answer("✅ Jarayon bekor qilindi.")
    except Exception as e:
        logging.error(f"Cancel error: {e}")

# Universal callback handler (vaqtinchalik debug uchun)
@dp.callback_query()
async def debug_callback(callback: types.CallbackQuery):
    logging.debug(f"Unhandled callback data: {callback.data}")
    await callback.answer(f"Boshqa callback: {callback.data}", show_alert=True)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
