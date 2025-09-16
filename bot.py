import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import sqlite3
import datetime
import json
import os

# === KONFIGURATSIYA ===
BOT_TOKEN = "8250661516:AAHNwNWH1JWFK83FDCv6juuptqUvAqPNA98"
ADMIN_CHAT_ID = 7678962106
CONFIG_FILE = "config.json"

# Log konfiguratsiyasi
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === PAROLNI YUKLASH/SAQLASH ===
def load_config():
    if os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"admin_code": "7777", "admin_phone": "+998901234567"}  # default

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

config = load_config()

# === MA'LUMOTLAR BAZASI ===
def init_db():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        id INTEGER PRIMARY KEY,
        chat_id INTEGER UNIQUE,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        joined_date TIMESTAMP
    )
    ''')
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message_text TEXT,
        message_date TIMESTAMP,
        admin_replied BOOLEAN DEFAULT FALSE,
        FOREIGN KEY (user_id) REFERENCES users (id)
    )
    ''')
    conn.commit()
    conn.close()

def add_user(chat_id, username, first_name, last_name):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR IGNORE INTO users (chat_id, username, first_name, last_name, joined_date)
    VALUES (?, ?, ?, ?, ?)
    ''', (chat_id, username, first_name, last_name, datetime.datetime.now()))
    conn.commit()
    conn.close()

def add_message(user_id, message_text):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO messages (user_id, message_text, message_date)
    VALUES (?, ?, ?)
    ''', (user_id, message_text, datetime.datetime.now()))
    message_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return message_id

def get_user_id(chat_id):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT id FROM users WHERE chat_id = ?', (chat_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_all_messages():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('''
    SELECT m.id, u.first_name, u.username, m.message_text, m.message_date
    FROM messages m
    JOIN users u ON m.user_id = u.id
    ORDER BY m.message_date DESC
    ''')
    messages = cursor.fetchall()
    conn.close()
    return messages

def get_user_id_by_message(message_id):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT user_id FROM messages WHERE id = ?', (message_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def get_user_info(user_id):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('SELECT chat_id, first_name, username FROM users WHERE id = ?', (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result if result else None

def delete_all_messages():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM messages')
    conn.commit()
    conn.close()

# === BOT FUNKSIYALARI ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    chat_id = update.effective_chat.id
    add_user(chat_id, user.username, user.first_name, user.last_name)
    keyboard = [["📞 Admin bilan bog'lanish"], ["ℹ️ Yordam"]]
    await update.message.reply_html(
        f"Assalomu alaykum {user.mention_html()}!\n\nBotga xush kelibsiz.",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["✍️ Xabar yozish"], ["📞 Telefon qilish"], ["🔙 Orqaga"]]
    await update.message.reply_text("Admin bilan bog'lanish:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def write_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['waiting_for_message'] = True
    await update.message.reply_text("Xabaringizni yozing:", reply_markup=ReplyKeyboardRemove())

async def call_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [[InlineKeyboardButton("📞 Telefon qilish", url=f"tel:{config['admin_phone']}")]]
    await update.message.reply_text("Telefon orqali bog'lanish:", reply_markup=InlineKeyboardMarkup(keyboard))

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["📞 Admin bilan bog'lanish"], ["ℹ️ Yordam"]]
    await update.message.reply_text("Asosiy menyu:", reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True))

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # Admin huquqi tekshiruvi
    if not context.user_data.get('admin'):
        context.user_data['waiting_for_admin_code'] = True
        await update.message.reply_text("❌ Siz admin emassiz. Kodni kiriting:")
        return
    
    keyboard = [
        ["📨 Barcha xabarlar", "🗑️ Xabarlarni tozalash"],
        ["📬 Javob berish", "📱 Telefon raqamini o'zgartirish"],
        ["🔑 Kod almashtirish", "🔐 Admin paneldan chiqish"]
    ]
    await update.message.reply_text(
        "🔑 Admin panel:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_data = context.user_data

    # Xabar yuborish
    if user_data.get('waiting_for_message'):
        user_message = update.message.text
        user_id = get_user_id(update.effective_chat.id)
        message_id = add_message(user_id, user_message)

        user_info = get_user_info(user_id)
        user_name = user_info[1] if user_info else "Noma'lum"
        username = f"@{user_info[2]}" if user_info and user_info[2] else "Yo'q"

        msg = (f"📩 Yangi xabar!\n\n👤 {user_name}\n📱 {username}\n🆔 ID: {message_id}\n📝 {user_message}")
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=msg)

        await update.message.reply_text("✅ Xabaringiz yuborildi.", reply_markup=ReplyKeyboardMarkup([["📞 Admin bilan bog'lanish"], ["ℹ️ Yordam"]], resize_keyboard=True))
        user_data['waiting_for_message'] = False
        return

    # Admin javob berish jarayoni
    if user_data.get('waiting_for_reply_id'):
        try:
            user_data['reply_message_id'] = int(update.message.text)
            user_data['waiting_for_reply_id'] = False
            user_data['waiting_for_reply_text'] = True
            await update.message.reply_text("Javob matnini kiriting:")
        except:
            await update.message.reply_text("Noto'g'ri ID. Raqam kiriting.")
        return

    if user_data.get('waiting_for_reply_text'):
        reply_text = update.message.text
        message_id = user_data.get('reply_message_id')
        user_id = get_user_id_by_message(message_id)
        if not user_id:
            await update.message.reply_text("❌ Xabar topilmadi!")
            return await admin_panel(update, context)

        user_info = get_user_info(user_id)
        if not user_info:
            await update.message.reply_text("❌ Foydalanuvchi topilmadi!")
            return await admin_panel(update, context)

        chat_id, first_name, username = user_info
        await context.bot.send_message(chat_id=chat_id, text=f"📬 Admin javobi:\n\n{reply_text}")
        await update.message.reply_text("✅ Javob yuborildi.")
        user_data.clear()
        return await admin_panel(update, context)

    # Kod almashtirish jarayoni
    if user_data.get('waiting_for_old_code'):
        if update.message.text == config['admin_code']:
            user_data.pop('waiting_for_old_code')
            user_data['waiting_for_new_code'] = True
            await update.message.reply_text("Yangi kodni kiriting:")
        else:
            await update.message.reply_text("❌ Eski kod noto'g'ri!")
        return

    if user_data.get('waiting_for_new_code'):
        user_data['temp_new_code'] = update.message.text
        user_data['waiting_for_new_code'] = False
        user_data['waiting_for_confirm_code'] = True
        await update.message.reply_text("Tasdiqlash uchun yangi kodni qayta kiriting:")
        return

    if user_data.get('waiting_for_confirm_code'):
        if update.message.text == user_data['temp_new_code']:
            config['admin_code'] = user_data['temp_new_code']
            save_config(config)
            await update.message.reply_text("✅ Kod muvaffaqiyatli o'zgartirildi.")
            user_data.clear()
            return await admin_panel(update, context)
        else:
            await update.message.reply_text("❌ Kod mos kelmadi. Qaytadan urinib ko'ring.")
            user_data.clear()
            return await admin_panel(update, context)

    # Telefon raqamini o'zgartirish jarayoni
    if user_data.get('waiting_for_new_phone'):
        new_phone = update.message.text
        # Telefon raqamini tekshirish
        if not new_phone.startswith('+') or not new_phone[1:].isdigit():
            await update.message.reply_text("❌ Noto'g'ri telefon raqami formati. Iltimos, +998901234567 formatida kiriting.")
            return
        
        config['admin_phone'] = new_phone
        save_config(config)
        await update.message.reply_text("✅ Telefon raqami muvaffaqiyatli o'zgartirildi.")
        user_data.clear()
        return await admin_panel(update, context)

    # Barcha xabarlarni o'chirish tasdiqlash
    if user_data.get('waiting_for_confirm_delete'):
        if update.message.text.lower() == 'ha':
            delete_all_messages()
            await update.message.reply_text("✅ Barcha xabarlar o'chirildi.")
        else:
            await update.message.reply_text("❌ Xabarlarni o'chirish bekor qilindi.")
        user_data.clear()
        return await admin_panel(update, context)

    if user_data.get('waiting_for_admin_code'):
        if update.message.text == config['admin_code']:
            user_data['admin'] = True
            user_data.pop('waiting_for_admin_code')
            await admin_panel(update, context)
        else:
            await update.message.reply_text("❌ Kod noto'g'ri!")
            user = update.effective_user
            now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            alert = (f"⚠️ Noto'g'ri kod urinish!\n👤 {user.first_name}\n@{user.username}\n🆔 {user.id}\n⏰ {now}")
            await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=alert)
        return

    await update.message.reply_text("Menyudan foydalaning.")

async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['waiting_for_admin_code'] = True
    await update.message.reply_text("Admin kodini kiriting:", reply_markup=ReplyKeyboardRemove())

async def reply_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reply_text("❌ Avval admin paneliga kiring.")
    context.user_data['waiting_for_reply_id'] = True
    await update.message.reply_text("Javob berish uchun xabar ID sini kiriting:", reply_markup=ReplyKeyboardRemove())

async def view_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reply_text("Sizga ruxsat yo'q!")
    messages = get_all_messages()
    if not messages:
        return await update.message.reply_text("📭 Xabarlar yo'q.")
    response = "📨 Oxirgi xabarlar:\n\n"
    for msg_id, first_name, username, message_text, message_date in messages[:10]:
        display_username = f"@{username}" if username else "Noma'lum"
        response += f"🆔 {msg_id} | 👤 {first_name} ({display_username})\n📝 {message_text[:50]}...\n⏰ {message_date}\n\n"
    await update.message.reply_text(response)

async def delete_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reply_text("Sizga ruxsat yo'q!")
    
    context.user_data['waiting_for_confirm_delete'] = True
    await update.message.reply_text("⚠️ Barcha xabarlarni o'chirishni tasdiqlaysizmi? (Ha/Yo'q)", reply_markup=ReplyKeyboardRemove())

async def change_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reply_text("Siz admin emassiz!")
    context.user_data['waiting_for_new_phone'] = True
    await update.message.reply_text("Yangi telefon raqamini kiriting (format: +998901234567):", reply_markup=ReplyKeyboardRemove())

async def change_code(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reply_text("Siz admin emassiz!")
    context.user_data['waiting_for_old_code'] = True
    await update.message.reply_text("Eski kodni kiriting:", reply_markup=ReplyKeyboardRemove())

async def admin_logout(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await update.message.reply_text("🔓 Admin paneldan chiqdingiz.", reply_markup=ReplyKeyboardMarkup([["📞 Admin bilan bog'lanish"], ["ℹ️ Yordam"]], resize_keyboard=True))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("📖 Yordam:\n📞 Admin bilan bog'lanish\nℹ️ Yordam\n🔑 Admin panel: /admin")

def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_login))
    application.add_handler(CommandHandler("reply", reply_command))
    application.add_handler(CommandHandler("help", help_command))

    application.add_handler(MessageHandler(filters.Regex("^📞 Admin bilan bog'lanish$"), contact_admin))
    application.add_handler(MessageHandler(filters.Regex("^✍️ Xabar yozish$"), write_message))
    application.add_handler(MessageHandler(filters.Regex("^📞 Telefon qilish$"), call_admin))
    application.add_handler(MessageHandler(filters.Regex("^🔙 Orqaga$"), back_to_main))
    application.add_handler(MessageHandler(filters.Regex("^📨 Barcha xabarlar$"), view_messages))
    application.add_handler(MessageHandler(filters.Regex("^🗑️ Xabarlarni tozalash$"), delete_messages))
    application.add_handler(MessageHandler(filters.Regex("^📬 Javob berish$"), reply_command))
    application.add_handler(MessageHandler(filters.Regex("^📱 Telefon raqamini o'zgartirish$"), change_phone))
    application.add_handler(MessageHandler(filters.Regex("^🔑 Kod almashtirish$"), change_code))
    application.add_handler(MessageHandler(filters.Regex("^🔐 Admin paneldan chiqish$"), admin_logout))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("Bot ishga tushdi...")
    application.run_polling()

if __name__ == '__main__':
    main()