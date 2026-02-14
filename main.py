import os
import json
import asyncio
import logging
import traceback
from urllib.parse import quote
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import Command, CommandStart
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.utils.keyboard import InlineKeyboardBuilder
from dotenv import load_dotenv
import asyncpg

load_dotenv()

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", 6935090105))
DATABASE_URL = os.getenv("DATABASE_URL")

logging.basicConfig(level=logging.DEBUG)

bot = Bot(token=TOKEN)
storage = MemoryStorage()
dp = Dispatcher(storage=storage)

# Ma'lumotlar bazasi pooli
db_pool = None

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

# ------------------- Ma'lumotlar bazasi funksiyalari -------------------
async def init_db():
    global db_pool
    db_pool = await asyncpg.create_pool(DATABASE_URL)
    async with db_pool.acquire() as conn:
        await conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id BIGINT PRIMARY KEY,
                balance INTEGER DEFAULT 0,
                referrer_id BIGINT,
                registered BOOLEAN DEFAULT FALSE,
                created_at TIMESTAMP DEFAULT NOW()
            )
        """)

async def get_user(conn, user_id):
    return await conn.fetchrow("SELECT * FROM users WHERE user_id = $1", user_id)

async def create_user(conn, user_id, referrer_id=None):
    await conn.execute("""
        INSERT INTO users (user_id, referrer_id)
        VALUES ($1, $2)
        ON CONFLICT (user_id) DO NOTHING
    """, user_id, referrer_id)

async def add_balance(conn, user_id, amount):
    await conn.execute("UPDATE users SET balance = balance + $1 WHERE user_id = $2", amount, user_id)

async def get_balance(conn, user_id):
    row = await conn.fetchrow("SELECT balance FROM users WHERE user_id = $1", user_id)
    return row['balance'] if row else 0

async def is_registered(conn, user_id):
    row = await conn.fetchrow("SELECT registered FROM users WHERE user_id = $1", user_id)
    return row['registered'] if row else False

async def set_registered(conn, user_id):
    await conn.execute("UPDATE users SET registered = TRUE WHERE user_id = $1", user_id)

# ------------------- Bot username olish -------------------
bot_username = None

async def get_bot_username():
    global bot_username
    if bot_username is None:
        me = await bot.get_me()
        bot_username = me.username
    return bot_username

# ------------------- Start va tugmalar -------------------
@dp.message(CommandStart())
async def start_handler(message: types.Message, command: CommandStart):
    try:
        user_id = message.from_user.id
        args = command.args  # start parametri
        referrer_id = None
        if args and args.startswith("ref_"):
            try:
                referrer_id = int(args.split("_")[1])
            except:
                pass

        async with db_pool.acquire() as conn:
            # Foydalanuvchi mavjudmi?
            user = await get_user(conn, user_id)
            if not user:
                # Yangi foydalanuvchi
                await create_user(conn, user_id, referrer_id)
                await add_balance(conn, user_id, 8000)  # start bonusi

                # Referalga 500 ball va xabar
                if referrer_id and referrer_id != user_id:
                    # Referal mavjudligini tekshirish
                    ref_user = await get_user(conn, referrer_id)
                    if ref_user:
                        await add_balance(conn, referrer_id, 500)
                        try:
                            await bot.send_message(
                                referrer_id,
                                f"🎉 Sizning taklifingiz orqali {message.from_user.full_name} (@{message.from_user.username}) qoʻshildi!\n+500 ball hisobingizga qoʻshildi."
                            )
                        except:
                            pass
            else:
                # Eski foydalanuvchi, ball qo'shmaymiz, faqat referrer_id ni saqlaymiz (agar birinchi marta kelayotgan bo'lsa?)
                # Agar referrer_id bo'lsa va userda referrer_id yo'q bo'lsa, uni saqlash mumkin, lekin ball bermaymiz
                if referrer_id and not user['referrer_id'] and referrer_id != user_id:
                    await conn.execute("UPDATE users SET referrer_id = $1 WHERE user_id = $2", referrer_id, user_id)

        # Asosiy menyu
        await show_main_menu(message)
    except Exception as e:
        logging.error(f"Start handler error: {e}\n{traceback.format_exc()}")

async def show_main_menu(message: types.Message):
    apk_data = load_apk_data()
    text = (
        "🎉 *D I Q Q A T! Winwin’da super konkurs!* 🎉\n\n"
        "🏆 *Bosh sovrin – BMW!* 100+ qimmatbaho sovgʻalar!\n"
        "📢 Endi bloggerlar qatnashmaydi – bu konkurs *oddiy xalq uchun*! Sizda ajoyib imkoniyat bor!\n\n"
        "✅ *Qatnashish uchun:*\n"
        "1. Roʻyxatdan oʻtish tugmasini bosing va *win_21450* promokodini kiriting.\n"
        "2. Ball toʻplab, imkoniyatingizni oshiring.\n"
        "3. Doʻstlaringizni taklif qiling va qoʻshimcha ball oling!\n\n"
        "🚀 *Omad! BMW sizniki boʻlishi mumkin!*"
    )
    builder = InlineKeyboardBuilder()
    builder.button(text="💰 Mening ballarim", callback_data="my_balance")
    builder.button(text="🎁 Ball ishlash", callback_data="earn_points")
    builder.button(text="📝 Roʻyxatdan oʻtish (20000 ball)", callback_data="register_bonus")
    if apk_data.get("file_id"):
        builder.button(text="📲 APK yuklash", callback_data="download_apk")
    builder.adjust(1)
    await message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")

# ------------------- Mening ballarim -------------------
@dp.callback_query(F.data == "my_balance")
async def my_balance_callback(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        async with db_pool.acquire() as conn:
            balance = await get_balance(conn, user_id)
        await callback.message.answer(f"💰 Sizning balansingiz: *{balance} ball*", parse_mode="Markdown")
        await callback.answer()
    except Exception as e:
        logging.error(f"my_balance error: {e}")
        await callback.answer("Xatolik yuz berdi", show_alert=True)

# ------------------- Ball ishlash (referal) -------------------
@dp.callback_query(F.data == "earn_points")
async def earn_points_callback(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        bot_username = await get_bot_username()
        referral_link = f"https://t.me/{bot_username}?start=ref_{user_id}"
        share_text = quote("🎯 Winwin konkursida qatnash! BMW yutib olish imkoniyati. Roʻyxatdan oʻt va ball toʻpla! Quyidagi havola orqali:")
        share_url = f"https://t.me/share/url?url={referral_link}&text={share_text}"
        text = (
            "🔗 *Doʻstlaringizni taklif qiling va ball ishlang!*\n\n"
            "Har bir taklif qilgan doʻstingiz uchun *+500 ball* olasiz.\n"
            "Quyidagi havolani nusxalab, doʻstlaringizga yuboring yoki \"Ulashish\" tugmasini bosing:\n\n"
            f"`{referral_link}`"
        )
        builder = InlineKeyboardBuilder()
        builder.button(text="👥 Doʻstlarga yuborish", url=share_url)
        await callback.message.answer(text, reply_markup=builder.as_markup(), parse_mode="Markdown")
        await callback.answer()
    except Exception as e:
        logging.error(f"earn_points error: {e}")
        await callback.answer("Xatolik yuz berdi", show_alert=True)

# ------------------- Ro'yxatdan o'tish bonusi -------------------
@dp.callback_query(F.data == "register_bonus")
async def register_bonus_callback(callback: types.CallbackQuery):
    try:
        user_id = callback.from_user.id
        async with db_pool.acquire() as conn:
            registered = await is_registered(conn, user_id)
            if not registered:
                await add_balance(conn, user_id, 20000)
                await set_registered(conn, user_id)
                text = (
                    "✅ Siz roʻyxatdan oʻtish bonusini oldingiz! *+20000 ball* hisobingizga qoʻshildi.\n\n"
                    "🔗 Endi quyidagi havola orqali winwin'da roʻyxatdan oʻting va *win_21450* promokodini kiriting:\n"
                    "https://refpa712080.pro/L?tag=d_4543807m_64485c_&site=4543807&ad=64485"
                )
                await callback.message.answer(text, parse_mode="Markdown")
            else:
                await callback.message.answer("❌ Siz allaqachon roʻyxatdan oʻtish bonusini olgansiz.")
        await callback.answer()
    except Exception as e:
        logging.error(f"register_bonus error: {e}")
        await callback.answer("Xatolik yuz berdi", show_alert=True)

# ------------------- APK yuklash -------------------
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

# ------------------- Admin buyruqlari -------------------
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

# ------------------- Ping test -------------------
@dp.message(Command("ping"))
async def ping(message: types.Message):
    await message.answer("pong")

# ------------------- Universal callback (debug) -------------------
@dp.callback_query()
async def debug_callback(callback: types.CallbackQuery):
    logging.debug(f"Unhandled callback data: {callback.data}")
    await callback.answer(f"Boshqa callback: {callback.data}", show_alert=True)

# ------------------- Startup / Shutdown -------------------
async def on_startup():
    await init_db()
    logging.info("Bot started and database initialized.")

async def on_shutdown():
    if db_pool:
        await db_pool.close()
    logging.info("Bot stopped.")

async def main():
    dp.startup.register(on_startup)
    dp.shutdown.register(on_shutdown)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
