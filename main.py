import asyncio
import logging
import io
from aiogram import Bot, Dispatcher, types, F
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (
    InlineKeyboardMarkup, InlineKeyboardButton, 
    ReplyKeyboardMarkup, KeyboardButton, BufferedInputFile, LabeledPrice, PreCheckoutQuery
)
import aiosqlite

# --- SOZLAMALAR ---
BOT_TOKEN = "8943527198:AAEjUbc8hhPu0joPmbxIo4jTSWsYrOsC0qs"
PROVIDER_TOKEN = "398062629:TEST:999999999_F91D8F69C042267444B74CC0B3C747757EB0E065"  # Qo'shtirnoq yopildi
ADMIN_ID = 1316308230
KANAL_ID = -1003868075342
INSTAGRAM_LINK = "https://instagram.com/kinouzb_hub"

logging.basicConfig(level=logging.INFO)

# --- FSM STATES ---
class MovieState(StatesGroup):
    waiting_for_file = State()
    waiting_for_name = State()
    waiting_for_type = State() 
    waiting_for_price = State() 
    waiting_for_code = State()

class ReqState(StatesGroup):
    waiting_for_ad = State()

class PaymentState(StatesGroup):
    waiting_for_amount = State()

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()
DB_NAME = "kinobot_universal.db"

# --- BAZANI INIZIALIZATSIYA QILISH ---
async def init_db():
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY, 
                username TEXT, 
                balance INTEGER DEFAULT 0
            )""")
        await db.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                code TEXT PRIMARY KEY, 
                name TEXT, 
                file_id TEXT, 
                file_type TEXT, 
                is_paid INTEGER DEFAULT 0, 
                price INTEGER DEFAULT 0,
                views INTEGER DEFAULT 0
            )""")
        await db.execute("CREATE TABLE IF NOT EXISTS requests (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, text TEXT)")
        await db.execute("CREATE TABLE IF NOT EXISTS purchased (user_id INTEGER, movie_code TEXT, PRIMARY KEY(user_id, movie_code))")
        await db.commit()
# --- KLAVIATURALAR ---
def get_channel_keyboard():
    buttons = [
        [InlineKeyboardButton(text="📢 Telegram kanalga a'zo bo'lish", url="https://t.me/kinouzb_hub")],
        [InlineKeyboardButton(text="📸 Instagram sahifamiz", url=INSTAGRAM_LINK)],
        [InlineKeyboardButton(text="🔄 Tasdiqlash / Tekshirish", callback_data="check_subs")]
    ]
    return InlineKeyboardMarkup(inline_keyboard=buttons)
def get_admin_keyboard():
    buttons = [
        [KeyboardButton(text="📊 Statika"), KeyboardButton(text="📝 So'ralgan kinolar")],
        [KeyboardButton(text="🎬 Kino qo'shish"), KeyboardButton(text="📢 Reklama yuborish")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

def get_user_keyboard():
    buttons = [
        [KeyboardButton(text="💰 Balans / Profil"), KeyboardButton(text="🔝 Top Kinolar")],
        [KeyboardButton(text="💳 Karta orqali hisob to'ldirish"), KeyboardButton(text="🔍 Qanday qidirish?")]
    ]
    return ReplyKeyboardMarkup(keyboard=buttons, resize_keyboard=True)

# --- OBUNANI TEKSHIRISH ---
async def check_subscription(user_id: int) -> bool:
    if user_id == int(ADMIN_ID):
        return True
    try:
        member = await bot.get_chat_member(chat_id=KANAL_ID, user_id=user_id)
        return member.status in ["member", "administrator", "creator"]
    except Exception:
        return False

# --- COMMANDS ---
@dp.message(CommandStart())
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    username = f"@{message.from_user.username}" if message.from_user.username else "Noma'lum"
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("INSERT INTO users (user_id, username) VALUES (?, ?) ON CONFLICT(user_id) DO UPDATE SET username=?", (user_id, username, username))
        await db.commit()
    
    if await check_subscription(user_id):
        await message.answer("🎬 Xush kelibsiz! Kino kodini yoki nomini kiriting. Yoki quyidagi menyudan foydalaning:", reply_markup=get_user_keyboard())
    else:
        await message.answer("Botdan to'liq foydalanish uchun kanallarimizga a'zo bo'ling va tasdiqlash tugmasini bosing!", reply_markup=get_channel_keyboard())

@dp.callback_query(F.data == "check_subs")
async def check_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    if await check_subscription(user_id):
        try:
            await callback.message.delete()
        except Exception:
            pass
        await callback.message.answer("🎉 Rahmat! Obuna tasdiqlandi. Kino kodini yoki nomini yuborishingiz mumkin.", reply_markup=get_user_keyboard())
    else:
        await callback.answer("❌ Siz hali barcha kanallarga a'zo bo'lmadingiz! Tekshirib qayta urining.", show_alert=True)
@dp.message(Command("admin"))
async def admin_panel(message: types.Message):
    user_id = message.from_user.id
    if user_id == int(ADMIN_ID):
        await message.answer("👨‍✈️ Admin panelga xush kelibsiz!", reply_markup=get_admin_keyboard())
# --- USER FUNCTIONS ---
@dp.message(F.text == "💰 Balans / Profil")
async def show_profile(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (message.from_user.id,)) as cursor:
            res = await cursor.fetchone()
            balance = res[0] if res else 0
    await message.answer(f"👤 **Sizning Profilingiz:**\n\n🆔 ID: `{message.from_user.id}`\n💰 Balans: {balance} so'm", parse_mode="Markdown")

@dp.message(F.text == "🔝 Top Kinolar")
async def top_movies(message: types.Message):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT code, name, views FROM movies ORDER BY views DESC LIMIT 10") as cursor:
            rows = await cursor.fetchall()
    if not rows:
        await message.answer("Hozircha kinolar mavjud emas.")
        return
    text = "🔥 **Eng ko'p ko'rilgan top 10 ta kino:**\n\n"
    for row in rows:
        text += f"🔹 Kod: `{row[0]}` — {row[1]} ({row[2]} marta ko'rilgan)\n"
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "🔍 Qanday qidirish?")
async def how_to_search(message: types.Message):
    await message.answer("💡 **Kino qidirish juda oddiy:**\n\n1. Kino kodini raqam ko'rinishida yuboring (Masalan: `12`)\n2. Yoki kino nomini qisman yozib yuboring (Masalan: `O'rgimchak odam`)", parse_mode="Markdown")

# --- AVTOMATIK INVOICE (KARTA ORQALI) TO'LOV TIZIMI ---
@dp.message(F.text == "💳 Karta orqali hisob to'ldirish")
async def start_deposit(message: types.Message, state: FSMContext):
    await message.answer("Qancha miqdorda balansni to'ldirmoqchisiz? (Faqat raqam kiriting, masalan: 5000):")
    await state.set_state(PaymentState.waiting_for_amount)

@dp.message(PaymentState.waiting_for_amount)
async def process_amount(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Iltimos, faqat raqam kiriting:")
        return
    
    amount = int(message.text)
    if amount < 1000:
        await message.answer("Minimal to'ldirish miqdori 1000 so'm!")
        return

    await state.clear()
    
    prices = [LabeledPrice(label="Balansni to'ldirish", amount=amount * 100)]
    
    await bot.send_invoice(
        chat_id=message.chat.id,
        title="Bot balansini to'ldirish",
        description=f"Bot ichki balansiga {amount} so'm qo'shish uchun Click/Payme orqali xavfsiz to'lov qiling.",
        provider_token=PROVIDER_TOKEN,
        currency="UZS",
        prices=prices,
        payload=f"deposit_user_{message.from_user.id}_{amount}",
        start_parameter="pay"
    )

@dp.pre_checkout_query()
async def process_pre_checkout(pre_checkout_query: PreCheckoutQuery):
    await bot.answer_pre_checkout_query(pre_checkout_query.id, ok=True)

@dp.message(F.successful_payment)
async def success_payment_handler(message: types.Message):
    payload = message.successful_payment.invoice_payload
    parts = payload.split("_")
    user_id = int(parts[2])
    amount = int(parts[3])
    
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        await db.commit()
        
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as cursor:
            res = await cursor.fetchone()
            current_balance = res[0] if res else 0

    await message.answer(
        f"✅ To'lov muvaffaqiyatli amalga oshirildi!\n"
        f"💰 Balansingizga {amount} so'm qo'shildi.\n"
        f"💳 Hozirgi balansingiz: **{current_balance} so'm**.",
        parse_mode="Markdown"
    )

# --- ADMIN STATISTIKA ---
@dp.message(F.text.contains("Statika"))
async def show_stats(message: types.Message):
if message.from_user.id == int(ADMIN_ID):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT COUNT(*) FROM users") as cursor:
                u_count = (await cursor.fetchone())[0]
            async with db.execute("SELECT COUNT(*) FROM movies") as cursor:
                m_count = (await cursor.fetchone())[0]
            async with db.execute("SELECT user_id, username, balance FROM users") as cursor:
                users_list = await cursor.fetchall()
                
        file_content = "ID | USERNAME | BALANS\n" + "-"*30 + "\n"
        for u in users_list:
            file_content += f"{u[0]} | {u[1]} | {u[2]} so'm\n"
        
        file_bytes = io.BytesIO(file_content.encode('utf-8'))
        input_file = BufferedInputFile(file_bytes.getvalue(), filename="users_list.txt")
        
        await message.answer(f"📊 **Statistika:**\n\n👥 Foydalanuvchilar: {u_count} ta\n🎬 Kinolar: {m_count} ta", parse_mode="Markdown")
        await message.answer_document(document=input_file, caption="👥 Bot a'zolarining to'liq ro'yxati")
@dp.message(F.text.contains("So'ralgan kinolar"))
async def show_requests(message: types.Message):
if message.from_user.id == int(ADMIN_ID):
        async with aiosqlite.connect(DB_NAME) as db:
            async with db.execute("SELECT text, COUNT(text) FROM requests GROUP BY text ORDER BY COUNT(text) DESC LIMIT 20") as cursor:
                reqs = await cursor.fetchall()
        if not reqs:
            await message.answer("Hozircha hech narsa so'rashmagan.")
            return
        text = "📝 **Eng ko'p so'ralgan kodlar/nomlar:**\n\n"
        for r in reqs:
            text += f"🔹 {r[0]} — {r[1]} marta\n"
        await message.answer(text, parse_mode="Markdown")

# --- KINO QO'SHISH ---
@dp.message(F.text.contains("Kino qo'shish"))
    if message.from_user.id == int(ADMIN_ID):
        await message.answer("Kinoni video yoki fayl ko'rinishida yuboring:")
        await state.set_state(MovieState.waiting_for_file)

@dp.message(MovieState.waiting_for_file, F.video | F.document)
async def process_movie_file(message: types.Message, state: FSMContext):
    file_id = message.video.file_id if message.video else message.document.file_id
    file_type = "video" if message.video else "document"
    await state.update_data(file_id=file_id, file_type=file_type)
    await message.answer("Kino nomini kiriting:")
    await state.set_state(MovieState.waiting_for_name)

@dp.message(MovieState.waiting_for_name)
async def process_movie_name(message: types.Message, state: FSMContext):
    await state.update_data(name=message.text)
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🆓 Bepul", callback_data="type_free"),
         InlineKeyboardButton(text="💰 Pullik", callback_data="type_paid")]
    ])
    await message.answer("Kino turini tanlang:", reply_markup=kb)
    await state.set_state(MovieState.waiting_for_type)

@dp.callback_query(MovieState.waiting_for_type, F.data.startswith("type_"))
async def process_movie_type(callback: types.CallbackQuery, state: FSMContext):
    movie_type = callback.data.split("_")[1]
    if movie_type == "free":
        await state.update_data(is_paid=0, price=0)
        await callback.message.answer("Kino uchun kod kiriting:")
        await state.set_state(MovieState.waiting_for_code)
    else:
        await state.update_data(is_paid=1)
        await callback.message.answer("Kino narxini kiriting (Faqat raqamda, masalan: 3000):")
        await state.set_state(MovieState.waiting_for_price)
    await callback.answer()

@dp.message(MovieState.waiting_for_price)
async def process_movie_price(message: types.Message, state: FSMContext):
    if not message.text.isdigit():
        await message.answer("Iltimos, faqat raqam kiriting:")
        return
    await state.update_data(price=int(message.text))
    await message.answer("Kino uchun yangi kod kiriting:")
    await state.set_state(MovieState.waiting_for_code)

@dp.message(MovieState.waiting_for_code)
async def process_movie_code(message: types.Message, state: FSMContext):
    code = message.text.strip()
    data = await state.get_data()
    async with aiosqlite.connect(DB_NAME) as db:
        try:
            await db.execute("""
                INSERT INTO movies (code, name, file_id, file_type, is_paid, price) 
                VALUES (?, ?, ?, ?, ?, ?)""", 
                (code, data['name'], data['file_id'], data['file_type'], data['is_paid'], data['price']))
            await db.commit()
            t_text = "Bepul" if data['is_paid'] == 0 else f"Pullik ({data['price']} so'm)"
            await message.answer(f"✅ Saqlandi!\nNom: {data['name']}\nTur: {t_text}\nKod: {code}")
            await state.clear()
        except aiosqlite.IntegrityError:
            await message.answer("❌ Bu kod band! Boshqa kod kiriting.")

# --- REKLAMA ---
@dp.message(F.text == "📢 Reklama yuborish")
async def start_ad(message: types.Message, state: FSMContext):
    if message.from_user.id == ADMIN_ID:
        await message.answer("Reklama postini yuboring:")
        await state.set_state(ReqState.waiting_for_ad)

@dp.message(ReqState.waiting_for_ad)
async def send_ad_to_all(message: types.Message, state: FSMContext):
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT user_id FROM users") as cursor:
            users = await cursor.fetchall()
    await message.answer("📢 Reklama tarqatilmoqda...")
    count = 0
    for user in users:
        try:
            await message.copy_to(chat_id=user[0])
            count += 1
            await asyncio.sleep(0.04)
        except Exception:
            pass
    await message.answer(f"📢 Reklama {count} ta odamga yuborildi!")
    await state.clear()

# --- KINO QIDIRISH VA SOTIB OLISH ---
@dp.message(F.text)
async def search_movie(message: types.Message):
    user_id = message.from_user.id
    if not await check_subscription(user_id):
        await message.answer("Botdan foydalanish uchun kanallarimizga a'zo bo'ling!", reply_markup=get_channel_keyboard())
        return
    
    search_query = message.text.strip()
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT code, name, file_id, file_type, is_paid, price FROM movies WHERE code = ?", (search_query,)) as cursor:
            movie = await cursor.fetchone()
            
        if not movie:
            async with db.execute("SELECT code, name, file_id, file_type, is_paid, price FROM movies WHERE name LIKE ?", (f"%{search_query}%",)) as cursor:
                movie = await cursor.fetchone()
                
        if movie:
            m_code, m_name, m_file_id, m_file_type, is_paid, price = movie
            
            await db.execute("UPDATE movies SET views = views + 1 WHERE code = ?", (m_code,))
            await db.commit()
            
            if is_paid == 1:
                async with db.execute("SELECT 1 FROM purchased WHERE user_id = ? AND movie_code = ?", (user_id, m_code)) as p_cursor:
                    purchased = await p_cursor.fetchone()
                
                if not purchased and user_id != ADMIN_ID:
                    kb = InlineKeyboardMarkup(inline_keyboard=[
                        [InlineKeyboardButton(text="💰 Sotib olish", callback_data=f"buy_m_{m_code}")]
                    ])
                    await message.answer(f"🔒 **Ushbu kino pullik!**\n\n🎬 Nomi: {m_name}\n💵 Narxi: {price} so'm\n\nKinoni ko'rish uchun quyidagi tugma orqali sotib oling.", reply_markup=kb, parse_mode="Markdown")
                    return
            
            caption_text = f"🎬 **Kino nomi:** {m_name}\n🔑 **Kodi:** {m_code}"
            
            if m_file_type == "video":
                await message.answer_video(video=m_file_id, caption=caption_text, protect_content=True, parse_mode="Markdown")
            else:
                await message.answer_document(document=m_file_id, caption=caption_text, protect_content=True, parse_mode="Markdown")
        else:
            try:
                await db.execute("INSERT INTO requests (user_id, text) VALUES (?, ?)", (user_id, search_query))
                await db.commit()
            except Exception:
                pass
            await message.answer("❌ Afsuski, bunday kod yoki nom bilan kino topilmadi. So'rovingiz adminga yetkazildi!")

@dp.callback_query(F.data.startswith("buy_m_"))
async def buy_movie_callback(callback: types.CallbackQuery):
    user_id = callback.from_user.id
    movie_code = callback.data.split("_")[2]
    
    async with aiosqlite.connect(DB_NAME) as db:
        async with db.execute("SELECT name, file_id, file_type, price FROM movies WHERE code = ?", (movie_code,)) as cursor:
            movie = await cursor.fetchone()
            
        if not movie:
            await callback.answer("Kino topilmadi!", show_alert=True)
            return
            
        m_name, m_file_id, m_file_type, price = movie
        
        async with db.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,)) as u_cursor:
            res = await u_cursor.fetchone()
            balance = res[0] if res else 0
            
        if balance < price:
            await callback.answer(f"❌ Mablag' yetarli emas! Sizga yana {price - balance} so'm kerak.", show_alert=True)
            return
            
        await db.execute("UPDATE users SET balance = balance - ? WHERE user_id = ?", (price, user_id))
        await db.execute("INSERT OR IGNORE INTO purchased (user_id, movie_code) VALUES (?, ?)", (user_id, movie_code))
        await db.commit()
        
    await callback.message.delete()
    await callback.answer("✅ Kino muvaffaqiyatli sotib olindi!", show_alert=True)
    
    caption_text = f"🎬 **Kino nomi:** {m_name}\n🔑 **Kodi:** {movie_code}\n\n🛍 Xaridingiz uchun rahmat!"
    if m_file_type == "video":
        await callback.message.answer_video(video=m_file_id, caption=caption_text, protect_content=True, parse_mode="Markdown")
    else:
        await callback.message.answer_document(document=m_file_id, caption=caption_text, protect_content=True, parse_mode="Markdown")
# --- START UP ---
import os
from aiohttp import web

PORT = int(os.environ.get("PORT", 8080))

async def handle(request):
    return web.Response(text="Bot active!")

async def main():
    await init_db()
    print("Bot muvaffaqiyatli ishga tushdi!")
    
    # Render Timed Out bermasligi uchun veb-server
    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    
    # Bot polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
