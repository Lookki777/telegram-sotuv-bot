import os
import aiohttp
import json
import database

USER_CONVERSATIONS = {}

SYSTEM_PROMPT = """Siz — O'zbekistondagi eng kuchli, tajribali va ishontira oladigan AI kitob sotuvchisi (Marketing va Sales bo'yicha ekspert)siz. 
Ismingiz: "Super Sotuvchi AI".

Sizning maqsadingiz: Mijoz bilan shunday suhbat qurishki, u albatta kitob xarid qilsin!

ASOSIY SOTUV STRATEGIYALARI (MARKETING):
1. Emotsiyaga ta'sir qilish: Kitob shunchaki qog'oz emas, u muvaffaqiyat, boylik, va baxtga erishish vositasi ekanligini tushuntiring. ("Bu kitob sizning hayotingizni 180 darajaga o'zgartirishi mumkin", "O'z ustingizda ishlash uchun eng yaxshi sarmoya").
2. Qiziqish uyg'otish: Kitobning eng qiziqarli joylaridan spoylersiz qisqa faktlar ayting. Uni o'qimasa nima yo'qotishini bildiring.
3. Ishonch va Kafolat: Barcha kitoblarimiz yuqori sifatda tarjima qilingani, minglab o'quvchilar rozi ekanligini ta'kidlang.
4. FOMO (Quruq qolish qo'rquvi): "Ushbu eksklyuziv tarjimalarni faqat bizdan topasiz", "Hozir xarid qilib, darhol o'qishni boshlang".
5. Call to Action (CTA - Harakatga chorlash): Har doim suhbat oxirida mijozni harakatga undovchi aniq ko'rsatma bering (Masalan: "Qaysi kitobni tanladingiz? Hozir to'lov qilsangiz, 1 daqiqada kitobni yuboraman!").

Hozirgi mavjud kitoblar va ularning narxlari:
{books_context}

To'lov ma'lumotlari:
{payment_context}

Xulq-atvor qoidalari:
- Doimo samimiy, g'ayratli va professional O'zbek tilida (Lotin alifbosida) yozing.
- Mijoz ikkilansa, unga savollar bering ("Sizni ko'proq qaysi mavzu o'ylantiryapti? Shunga mos zo'r kitob tavsiya qilaman").
- Agar mijoz kitob tanlasa, DARDHOL to'lov qilib, chek rasmini botga yuborishini ayting.
- Qisqa, tushunarli va emoji (🔥, 🚀, 💡, 📚, 💳, ✅) lar bilan boyitilgan xabarlar yozing. Hech qachon zerikarli va uzun gapirmang.
"""

async def function_get_ai_response(user_id: int, user_message: str) -> str:
    books = database.get_all_books()
    if books:
        books_str = "\n".join([f"- Nomi: '{b['title']}' | Narxi: {b['price']} so'm | Haqida: {b['description']}" for b in books])
    else:
        books_str = "Hozircha sotuvda kitoblar mavjud emas, lekin tez orada super asarlar qo'shiladi!"

    payment_str = database.get_setting("payment_details", "Click / Payme orqali karta raqamiga to'lov qilinadi.")

    sys_prompt = SYSTEM_PROMPT.format(
        books_context=books_str,
        payment_context=payment_str
    )

    if user_id not in USER_CONVERSATIONS:
        USER_CONVERSATIONS[user_id] = []
    
    history = USER_CONVERSATIONS[user_id]
    history.append({"role": "user", "parts": [{"text": user_message}]})

    if len(history) > 10:
        history = history[-10:]

    gemini_api_key = os.environ.get("GEMINI_API_KEY", "")
    
    if not gemini_api_key:
        return get_rule_based_response(user_message, books, payment_str)

    try:
        url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent?key={gemini_api_key}"
        payload = {
            "system_instruction": {
                "parts": [{"text": sys_prompt}]
            },
            "contents": history
        }

        async with aiohttp.ClientSession() as session:
            async with session.post(url, json=payload, timeout=10) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    bot_text = data['candidates'][0]['content']['parts'][0]['text']
                    history.append({"role": "model", "parts": [{"text": bot_text}]})
                    return bot_text
                else:
                    return get_rule_based_response(user_message, books, payment_str)
    except Exception as e:
        print("Gemini API Error:", e)
        return get_rule_based_response(user_message, books, payment_str)

def get_rule_based_response(msg: str, books: list, payment_info: str) -> str:
    msg_lower = msg.lower()
    
    if "salom" in msg_lower or "assalom" in msg_lower or "start" in msg_lower:
        return "Assalomu alaykum! 🔥 Sizni ko'rib turganimdan xursandman. Hayotingizni o'zgartiruvchi eng kuchli kitoblar aynan shu yerda. Sizga ko'proq qanday yo'nalishdagi kitoblar yoqadi?"
    
    if "narx" in msg_lower or "qancha" in msg_lower or "sotib" in msg_lower or "kitob" in msg_lower:
        if books:
            book_list = "\n".join([f"🚀 *{b['title']}* — {b['price']} so'm\n_{b['description']}_\n" for b in books])
            return f"Siz uchun maxsus tayyorlangan ajoyib kitoblar:\n\n{book_list}\n💡 Bu shunchaki kitob emas, bu sizning kelajagingiz uchun eng zo'r sarmoya! Hoziroq to'lov qilib chek rasmini yuboring va darhol o'qishni boshlang! 💳✅"
        else:
            return "Hozircha kitoblar ro'yxati yangilanmoqda. Tez orada ajoyib yangiliklar bilan qaytamiz! 🚀"

    if "to'lov" in msg_lower or "tolov" in msg_lower or "karta" in msg_lower or "chek" in msg_lower:
        return f"Ajoyib tanlov! To'lov ma'lumotlari:\n\n{payment_info}\n\nTo'lov qilganingizdan so'ng, skrinshotni (chekni) shu yerga tashlang. Men darhol tasdiqlatib, kitobni sizga yetkazaman! 🚀"

    return "Tushundim! Vaqtni o'tkazmang, menyudan o'zingizga yoqqan kitobni tanlang yoki savolingiz bo'lsa bering! Eng zo'r kitoblar aynan sizni kutmoqda! 🔥📚"
