import asyncio
import logging
import os
import sys

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import CommandStart, Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.storage.memory import MemoryStorage
from aiogram.types import (
    InlineKeyboardButton, InlineKeyboardMarkup,
    KeyboardButton, ReplyKeyboardMarkup, FSInputFile
)
from aiohttp import web

import config
import database
from ai_salesman import function_get_ai_response

logging.basicConfig(level=logging.INFO)

# Initialize bot & dispatcher
bot = Bot(token=config.BOT_TOKEN)
dp = Dispatcher(storage=MemoryStorage())

# --- FSM States ---
class AddBookState(StatesGroup):
    title = State()
    description = State()
    price = State()
    channel_link = State()

class EditPaymentState(StatesGroup):
    payment_info = State()

class EditChannelState(StatesGroup):
    channel_link = State()

class SelectBookForPaymentState(StatesGroup):
    book_id = State()

# --- Keyboards ---
def main_menu_keyboard(is_admin=False):
    kb = [
        [KeyboardButton(text="📚 Kitoblar katalogi"), KeyboardButton(text="💳 To'lov rekvizitlari")],
        [KeyboardButton(text="💬 AI Maslahatchi bilan suhbat"), KeyboardButton(text="💡 Yo'riqnoma")]
    ]
    if is_admin:
        kb.append([KeyboardButton(text="⚙️ Admin Panel")])
    return ReplyKeyboardMarkup(keyboard=kb, resize_keyboard=True)

def admin_menu_keyboard():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Yangi kitob qo'shish", callback_data="admin_add_book")],
        [InlineKeyboardButton(text="📚 Kitoblar va o'chirish", callback_data="admin_list_books")],
        [InlineKeyboardButton(text="💳 To'lov rekvizitlarini tahrirlash", callback_data="admin_edit_payment")],
        [InlineKeyboardButton(text="🔗 Kanal havolasini o'zgartirish", callback_data="admin_edit_channel")],
    ])
    return kb

# --- User Handlers ---
@dp.message(CommandStart())
async def cmd_start(message: types.Message):
    is_admin = (message.from_user.id == config.ADMIN_ID)
    welcome_text = (
        f"Assalomu alaykum, {message.from_user.first_name}! 📖✨\n\n"
        "**Kitob Tarjimon** rasmiy botiga xush kelibsiz!\n"
        "Bu yerda siz o'zbek tiliga tarjima qilingan eng zo'r va sara kitoblarni xarid qilishingiz mumkin.\n\n"
        "👇 Kerakli bo'limni tanlang yoki bemalol men bilan suhbat qiling!"
    )
    await message.answer(
        welcome_text,
        reply_markup=main_menu_keyboard(is_admin),
        parse_mode="Markdown"
    )

@dp.message(F.text == "📚 Kitoblar katalogi")
async def show_books_catalog(message: types.Message):
    books = database.get_all_books()
    if not books:
        await message.answer("Hozircha sotuvdagi kitoblar ro'yxati bo'sh. Admin panel orqali kitob qo'shing!")
        return

    for b in books:
        caption = (
            f"📖 *{b['title']}*\n\n"
            f"📝 {b['description']}\n\n"
            f"💰 *Narxi:* {b['price']} so'm\n"
        )
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text=f"🛒 '{b['title']}'ni sotib olish", callback_data=f"buy_book_{b['id']}")]
        ])
        await message.answer(caption, reply_markup=kb, parse_mode="Markdown")

@dp.message(F.text == "💳 To'lov rekvizitlari")
async def show_payment_info(message: types.Message):
    payment_info = database.get_setting("payment_details", "Uzcard / Humo karta raqamiga to'lov qilinadi.")
    text = (
        "💳 **To'lov ma'lumotlari:**\n\n"
        f"{payment_info}\n\n"
        "📌 **Yo'riqnoma:**\n"
        "1. Yuqoridagi karta raqamiga Payme, Click yoki Uzum orqali to'lov qiling.\n"
        "2. To'lov chekini (kvitansiya rasmini) **to'g'ridan-to'g'ri ushbu botga rasm ko'rinishida yuboring!**\n"
        "3. Admin chekni tekshirib tasdiqlagach, bot sizga kanal havolasini yuboradi! ✅"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "💡 Yo'riqnoma")
async def show_help(message: types.Message):
    text = (
        "💡 **Botdan foydalanish yo'riqnomasi:**\n\n"
        "1. **Kitob tanlash:** Katalogdan o'zingizga yoqqan kitobni tanlang.\n"
        "2. **To'lov qilish:** Payme yoki Click orqali ko'rsatilgan karta raqamiga to'lang.\n"
        "3. **Chekni yuborish:** To'lov kvitansiyasi skrinshotini (rasmini) botga yuboring.\n"
        "4. **Kanalga kirish:** Admin 1-5 daqiqa ichida chekni tasdiqlaydi va bot sizga kitob kanalining yopiq havolasini taqdim etadi! 🚀"
    )
    await message.answer(text, parse_mode="Markdown")

@dp.message(F.text == "💬 AI Maslahatchi bilan suhbat")
async def ai_chat_info(message: types.Message):
    await message.answer("Men tayyorman! Kitoblar haqida savolingiz bo'lsa yoki qaysi birini o'qishni bilmayotgan bo'lsangiz, bemalol yozing! 🤖✨")

# --- Buying Book Callback ---
@dp.callback_query(F.data.startswith("buy_book_"))
async def process_buy_callback(callback: types.CallbackQuery, state: FSMContext):
    book_id = int(callback.data.split("_")[2])
    book = database.get_book(book_id)
    if not book:
        await callback.answer("Kitob topilmadi!", show_alert=True)
        return

    await state.update_data(selected_book_id=book_id)
    payment_info = database.get_setting("payment_details", "8600 0000 0000 0000")

    text = (
        f"🛒 **'{book['title']}' kitobini sotib olish**\n\n"
        f"💰 **To'lov summasi:** {book['price']} so'm\n\n"
        f"💳 **To'lov rekvizitlari:**\n{payment_info}\n\n"
        "📸 **To'lovni amalga oshirgach, chek (skrinshot) rasmini shu yerga yuboring!**"
    )
    await callback.message.answer(text, parse_mode="Markdown")
    await callback.answer()

# --- Receipt Photo Handler ---
@dp.message(F.photo)
async def handle_receipt_photo(message: types.Message, state: FSMContext):
    user_data = await state.get_data()
    book_id = user_data.get("selected_book_id")

    books = database.get_all_books()
    if not book_id:
        if books:
            book_id = books[0]['id']
        else:
            await message.answer("Hozircha sotuvda kitob yo'q!")
            return

    book = database.get_book(book_id)
    photo_id = message.photo[-1].file_id
    user_id = message.from_user.id
    user_name = message.from_user.full_name
    username = f"@{message.from_user.username}" if message.from_user.username else "Mavjud emas"

    order_id = database.create_order(
        user_id=user_id,
        user_name=user_name,
        username=username,
        book_id=book_id,
        receipt_photo_id=photo_id
    )

    await message.answer(
        "✅ **To'lov chekingiz qabul qilindi!**\n\n"
        "Chek administratorga tekshirish uchun yuborildi. 1-5 daqiqa ichida tasdiqlanib, kitob havolasi yuboriladi! ⏳",
        parse_mode="Markdown"
    )

    admin_caption = (
        f"🔔 **YANGI TO'LOV CHEKI! (Buyurtma #{order_id})**\n\n"
        f"👤 **Mijoz:** {user_name} ({username})\n"
        f"🆔 **User ID:** `{user_id}`\n"
        f"📖 **Kitob:** {book['title'] if book else 'Noma''lum'}\n"
        f"💰 **Narxi:** {book['price'] if book else '0'} so'm\n"
    )

    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="✅ Tasdiqlash", callback_data=f"approve_order_{order_id}"),
            InlineKeyboardButton(text="❌ Rad etish", callback_data=f"reject_order_{order_id}")
        ]
    ])

    try:
        await bot.send_photo(
            chat_id=config.ADMIN_ID,
            photo=photo_id,
            caption=admin_caption,
            reply_markup=admin_kb,
            parse_mode="Markdown"
        )
    except Exception as e:
        print("Admin notification error:", e)

# --- Admin Order Approval Callbacks ---
@dp.callback_query(F.data.startswith("approve_order_"))
async def approve_order_callback(callback: types.CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID:
        await callback.answer("Ruxsat yo'q!", show_alert=True)
        return

    order_id = int(callback.data.split("_")[2])
    order = database.get_order(order_id)
    if not order:
        await callback.answer("Buyurtma topilmadi!", show_alert=True)
        return

    database.update_order_status(order_id, "approved")
    book = database.get_book(order['book_id'])
    channel_link = (book.get('channel_link') if book and book.get('channel_link') else None) or database.get_setting("channel_link")

    user_msg = (
        f"🎉 **To'lovingiz muvaffaqiyatli tasdiqlandi!**\n\n"
        f"📖 **Kitob:** {book['title'] if book else ''}\n\n"
        f"🔗 **Kitob va kanalga kirish havolasi:**\n{channel_link}\n\n"
        "Xaridingiz uchun rahmat! Maroqli mutolaa tilaymiz! 📚✨"
    )

    try:
        await bot.send_message(chat_id=order['user_id'], text=user_msg, parse_mode="Markdown")
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n✅ **TASDIQLANDI! (Mijozga havola yuborildi)**",
            reply_markup=None,
            parse_mode="Markdown"
        )
    except Exception as e:
        await callback.answer(f"Mijozga xabar yuborishda xatolik: {e}", show_alert=True)

@dp.callback_query(F.data.startswith("reject_order_"))
async def reject_order_callback(callback: types.CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID:
        return

    order_id = int(callback.data.split("_")[2])
    order = database.get_order(order_id)
    if not order:
        return

    database.update_order_status(order_id, "rejected")

    try:
        await bot.send_message(
            chat_id=order['user_id'],
            text="❌ **To'lov chekingiz tasdiqlanmadi.**\nIltimos, qayta to'lov qiling yoki haqiqiy chek rasmini yuboring.",
            parse_mode="Markdown"
        )
        await callback.message.edit_caption(
            caption=callback.message.caption + "\n\n❌ **RAD ETILDI.**",
            reply_markup=None,
            parse_mode="Markdown"
        )
    except Exception as e:
        pass

# --- Admin Panel Handlers ---
@dp.message(F.text == "⚙️ Admin Panel")
@dp.message(Command("admin"))
async def cmd_admin(message: types.Message):
    if message.from_user.id != config.ADMIN_ID:
        return
    await message.answer("⚙️ **ADMIN PANEL**\nKerakli bo'limni tanlang:", reply_markup=admin_menu_keyboard(), parse_mode="Markdown")

@dp.callback_query(F.data == "admin_add_book")
async def start_add_book(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_ID: return
    await state.set_state(AddBookState.title)
    await callback.message.answer("📝 **Yangi kitob nomini kiriting:**")
    await callback.answer()

@dp.message(AddBookState.title)
async def process_book_title(message: types.Message, state: FSMContext):
    await state.update_data(title=message.text.strip())
    await state.set_state(AddBookState.description)
    await message.answer("📄 **Kitob tavsifini (batafsil ma'lumot) kiriting:**")

@dp.message(AddBookState.description)
async def process_book_desc(message: types.Message, state: FSMContext):
    await state.update_data(description=message.text.strip())
    await state.set_state(AddBookState.price)
    await message.answer("💰 **Kitob narxini kiriting (masalan: 35000):**")

@dp.message(AddBookState.price)
async def process_book_price(message: types.Message, state: FSMContext):
    await state.update_data(price=message.text.strip())
    await state.set_state(AddBookState.channel_link)
    await message.answer("🔗 **Ushbu kitob uchun telegram kanal / fayl havolasini kiriting:**\n(masalan: https://t.me/+AbCdEfGhIjKl)")

@dp.message(AddBookState.channel_link)
async def process_book_link(message: types.Message, state: FSMContext):
    data = await state.get_data()
    channel_link = message.text.strip()
    
    book_id = database.add_book(
        title=data['title'],
        description=data['description'],
        price=data['price'],
        channel_link=channel_link
    )
    await state.clear()
    await message.answer(f"✅ **'{data['title']}' kitobi muvaffaqiyatli qo'shildi!** (ID: {book_id})", parse_mode="Markdown")

@dp.callback_query(F.data == "admin_list_books")
async def list_admin_books(callback: types.CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID: return
    books = database.get_all_books(active_only=True)
    if not books:
        await callback.message.answer("Hozircha kitoblar yo'q.")
        await callback.answer()
        return

    for b in books:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🗑 O'chirish", callback_data=f"admin_del_book_{b['id']}")]
        ])
        await callback.message.answer(f"📖 *{b['title']}* — {b['price']} so'm\n_{b['description']}_", reply_markup=kb, parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data.startswith("admin_del_book_"))
async def del_admin_book(callback: types.CallbackQuery):
    if callback.from_user.id != config.ADMIN_ID: return
    book_id = int(callback.data.split("_")[3])
    database.delete_book(book_id)
    await callback.message.edit_text("❌ **Kitob o'chirildi!**", parse_mode="Markdown")
    await callback.answer()

@dp.callback_query(F.data == "admin_edit_payment")
async def start_edit_payment(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_ID: return
    await state.set_state(EditPaymentState.payment_info)
    current = database.get_setting("payment_details")
    await callback.message.answer(f"💳 **Hozirgi to'lov rekviziti:**\n\n`{current}`\n\n**Yangi to'lov rekvizitlarini va karta raqamingizni kiriting:**", parse_mode="Markdown")
    await callback.answer()

@dp.message(EditPaymentState.payment_info)
async def save_edit_payment(message: types.Message, state: FSMContext):
    new_info = message.text.strip()
    database.set_setting("payment_details", new_info)
    await state.clear()
    await message.answer("✅ **To'lov rekvizitlari yangilandi!**")

@dp.callback_query(F.data == "admin_edit_channel")
async def start_edit_channel(callback: types.CallbackQuery, state: FSMContext):
    if callback.from_user.id != config.ADMIN_ID: return
    await state.set_state(EditChannelState.channel_link)
    current = database.get_setting("channel_link")
    await callback.message.answer(f"🔗 **Hozirgi standart kanal havolasi:**\n\n`{current}`\n\n**Yangi havola kiriting:**", parse_mode="Markdown")
    await callback.answer()

@dp.message(EditChannelState.channel_link)
async def save_edit_channel(message: types.Message, state: FSMContext):
    new_link = message.text.strip()
    database.set_setting("channel_link", new_link)
    await state.clear()
    await message.answer("✅ **Kanal havolasi yangilandi!**")

# --- AI Fallback Text Chat Handler ---
@dp.message(F.text)
async def handle_user_text(message: types.Message):
    user_id = message.from_user.id
    user_text = message.text.strip()

    ai_response = await function_get_ai_response(user_id, user_text)
    await message.answer(ai_response)

# --- DUMMY WEB SERVER FOR CLOUD HOSTING (Render, Koyeb) ---
async def health_check(request):
    return web.Response(text="Telegram Sales Bot is Running 24/7!")

async def start_web_server():
    app = web.Application()
    app.router.add_get('/', health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    port = int(os.environ.get("PORT", 10000))
    site = web.TCPSite(runner, '0.0.0.0', port)
    await site.start()
    print(f"Web server started on port {port}")

# --- Main Runner ---
async def main():
    database.init_db()
    print("Telegram Sotuv Boti ishga tushdi...")
    # Start web server first so Cloud providers don't kill the app
    await start_web_server()
    # Start telegram bot polling
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
