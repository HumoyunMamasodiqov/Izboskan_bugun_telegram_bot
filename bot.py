import logging
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup, WebAppInfo, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, ContextTypes, filters
import sqlite3
import datetime
import json
import os
import re

# === KONFIGURATSIYA ===
BOT_TOKEN = "8250661516:AAHNwNWH1JWFK83FDCv6juuptqUvAqPNA98"
ADMIN_CHAT_ID = 7678962106
CONFIG_FILE = "config.json"
PRICES_FILE = "prices.json"
SOCIAL_FILE = "social_links.json"

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
    return {"admin_code": "7777", "admin_phone": "+998901234567"}

def save_config(data):
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f)

config = load_config()

# === NARXLARNI YUKLASH/SAQLASH ===
def load_prices():
    if os.path.exists(PRICES_FILE):
        with open(PRICES_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "instagram": {
            "story": "500$",
            "post": "1000$",
            "combo": "800$",
            "description": "Instagramda reklama qilish narxlari"
        },
        "telegram": {
            "story": "300$",
            "post": "700$",
            "combo": "500$",
            "description": "Telegramda reklama narxlari"
        },
        "combo": {
            "story": "700$",
            "post": "1500$",
            "combo": "1200$",
            "description": "Instagram + Telegram kombo reklama narxlari"
        }
    }

def save_prices(data):
    with open(PRICES_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

# === IJTIMOIY TARMOQLARNI YUKLASH/SAQLASH ===
def load_social_links():
    if os.path.exists(SOCIAL_FILE):
        with open(SOCIAL_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {
        "telegram": "https://t.me/example",
        "instagram": "https://instagram.com/example", 
        "youtube": "https://youtube.com/example",
        "website": "https://example.com"
    }

def save_social_links(data):
    with open(SOCIAL_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

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
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        platform TEXT,
        order_type TEXT,
        price TEXT,
        full_name TEXT,
        phone_number TEXT,
        order_details TEXT,
        order_date TIMESTAMP,
        status TEXT DEFAULT 'pending',
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

def add_order(user_id, platform, order_type, price, full_name, phone_number, order_details):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO orders (user_id, platform, order_type, price, full_name, phone_number, order_details, order_date)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (user_id, platform, order_type, price, full_name, phone_number, order_details, datetime.datetime.now()))
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id

def get_all_orders():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('''
    SELECT o.id, u.first_name, u.username, o.platform, o.order_type, o.price, 
           o.full_name, o.phone_number, o.order_details, o.order_date, o.status
    FROM orders o
    JOIN users u ON o.user_id = u.id
    ORDER BY o.order_date DESC
    ''')
    orders = cursor.fetchall()
    conn.close()
    return orders

def get_order_by_id(order_id):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('''
    SELECT o.id, u.first_name, u.username, o.platform, o.order_type, o.price, 
           o.full_name, o.phone_number, o.order_details, o.order_date, o.status
    FROM orders o
    JOIN users u ON o.user_id = u.id
    WHERE o.id = ?
    ''', (order_id,))
    order = cursor.fetchone()
    conn.close()
    return order

def delete_order(order_id):
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM orders WHERE id = ?', (order_id,))
    conn.commit()
    conn.close()

def delete_all_orders():
    conn = sqlite3.connect('bot.db')
    cursor = conn.cursor()
    cursor.execute('DELETE FROM orders')
    conn.commit()
    conn.close()

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
    
    keyboard = [
        ["📞 Admin bilan bog'lanish"], 
        ["💰 Reklama narxlari"],
        ["🛒 Reklama sotib olish"],
        ["🌐 Ijtimoiy tarmoqlar"],
        ["ℹ️ Yordam"]
    ]
    
    welcome_text = (
        f"👋 Assalomu alaykum {user.mention_html()}!\n\n"
        f"🤖 <b>Reklama Botiga</b> xush kelibsiz!\n\n"
        f"📊 Bizning xizmatlarimiz:\n"
        f"• Instagram reklama\n"
        f"• Telegram reklama\n"
        f"• Kombo reklama paketlar\n\n"
        f"⬇️ Quyidagi menyulardan birini tanlang:"
    )
    
    await update.message.reply_html(
        welcome_text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True, one_time_keyboard=True)
    )

async def contact_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["✍️ Xabar yozish"], ["📞 Telefon qilish"], ["🔙 Orqaga"]]
    await update.message.reply_text(
        "👨‍💼 Admin bilan bog'lanish:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def write_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['waiting_for_message'] = True
    await update.message.reply_text(
        "📝 Xabaringizni yozing:",
        reply_markup=ReplyKeyboardRemove()
    )

async def call_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone_number = config['admin_phone'].replace(" ", "")
    text = (
        f"📞 Admin raqami: {config['admin_phone']}\n\n"
        f"<a href='tel:{phone_number}'>📱 Telefon qilish uchun shu yerga bosing</a>"
    )
    await update.message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=ReplyKeyboardMarkup([["🔙 Orqaga"]], resize_keyboard=True)
    )

async def back_to_main(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📞 Admin bilan bog'lanish"], 
        ["💰 Reklama narxlari"],
        ["🛒 Reklama sotib olish"],
        ["🌐 Ijtimoiy tarmoqlar"],
        ["ℹ️ Yordam"]
    ]
    await update.message.reply_text(
        "🏠 Asosiy menyu:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# === REKLAMA SOTIB OLISH FUNKSIYALARI ===
async def buy_advertisement(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📸 Instagram", "📨 Telegram"],
        ["📊 Instagram+Telegram Kombo", "🔙 Orqaga"]
    ]
    await update.message.reply_text(
        "📱 Reklama platformasini tanlang:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def select_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = update.message.text
    prices = load_prices()
    
    if "Instagram" in text:
        context.user_data['selected_platform'] = 'instagram'
        platform_data = prices['instagram']
    elif "Telegram" in text:
        context.user_data['selected_platform'] = 'telegram'
        platform_data = prices['telegram']
    elif "Kombo" in text:
        context.user_data['selected_platform'] = 'combo'
        platform_data = prices['combo']
    else:
        return await update.message.reply_text("❌ Noto'g'ri tanlov!")
    
    keyboard = [
        ["📱 Story", "📋 Post"],
        ["📊 Story+Post Kombo", "🔙 Orqaga"]
    ]
    
    text = (
        f"📊 {platform_data['description']}:\n\n"
        f"• 📱 Story: {platform_data['story']}\n"
        f"• 📋 Post: {platform_data['post']}\n"
        f"• 📊 Story+Post: {platform_data['combo']}\n\n"
        f"👇 Reklama turini tanlang:"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def select_order_type(update: Update, context: ContextTypes.DEFAULT_TYPE):
    platform = context.user_data.get('selected_platform')
    if not platform:
        return await update.message.reply_text("❌ Platforma tanlanmagan!")
    
    prices = load_prices()
    platform_data = prices[platform]
    
    text = update.message.text
    if "Story" in text and "Post" not in text and "Kombo" not in text:
        context.user_data['order_type'] = 'story'
        context.user_data['order_type_display'] = 'Story'
        context.user_data['price'] = platform_data['story']
    elif "Post" in text and "Story" not in text and "Kombo" not in text:
        context.user_data['order_type'] = 'post'
        context.user_data['order_type_display'] = 'Post'
        context.user_data['price'] = platform_data['post']
    elif "Kombo" in text:
        context.user_data['order_type'] = 'combo'
        context.user_data['order_type_display'] = 'Story+Post Kombo'
        context.user_data['price'] = platform_data['combo']
    else:
        return await update.message.reply_text("❌ Noto'g'ri tanlov!")
    
    context.user_data['waiting_for_full_name'] = True
    await update.message.reply_text(
        f"✅ Tanlangan: {platform.capitalize()} - {context.user_data['order_type_display']}\n💰 Narxi: {context.user_data['price']}\n\n👤 Ism va familiyangizni kiriting:",
        reply_markup=ReplyKeyboardRemove()
    )

async def process_full_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['full_name'] = update.message.text
    context.user_data['waiting_for_full_name'] = False
    context.user_data['waiting_for_phone'] = True
    await update.message.reply_text("📱 Telefon raqamingizni kiriting (format: +998901234567):")

async def process_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    phone = update.message.text
    # Telefon raqamini tekshirish
    if not re.match(r'^\+998\d{9}$', phone):
        await update.message.reply_text("❌ Noto'g'ri telefon raqami formati. Iltimos, +998901234567 formatida kiriting.")
        return
    
    context.user_data['phone'] = phone
    context.user_data['waiting_for_phone'] = False
    context.user_data['waiting_for_order_details'] = True
    await update.message.reply_text("📝 Reklama haqida qisqacha ma'lumot kiriting (nima reklama qilmoqchisiz va qaysi sohada):")

async def process_order_details(update: Update, context: ContextTypes.DEFAULT_TYPE):
    order_details = update.message.text
    context.user_data['order_details'] = order_details
    context.user_data['waiting_for_order_details'] = False
    
    # Buyurtma ma'lumotlarini ko'rsatish va tasdiqlash
    platform = context.user_data.get('selected_platform')
    order_type = context.user_data.get('order_type_display')
    price = context.user_data.get('price')
    full_name = context.user_data.get('full_name')
    phone = context.user_data.get('phone')
    
    order_summary = (
        f"🛒 <b>Buyurtma xulosasi:</b>\n\n"
        f"📊 Platforma: {platform.capitalize()}\n"
        f"📝 Tur: {order_type}\n"
        f"💰 Narx: {price}\n"
        f"👤 Ism: {full_name}\n"
        f"📱 Telefon: {phone}\n"
        f"📋 Reklama tafsilotlari: {order_details}\n\n"
        f"✅ Buyurtmani tasdiqlaysizmi?"
    )
    
    keyboard = [["✅ Ha, tasdiqlayman", "❌ Yo'q, bekor qilish"]]
    await update.message.reply_html(
        order_summary,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )
    context.user_data['waiting_for_confirmation'] = True

async def process_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('waiting_for_confirmation'):
        return
    
    if update.message.text == "✅ Ha, tasdiqlayman":
        platform = context.user_data.get('selected_platform')
        order_type = context.user_data.get('order_type')
        order_type_display = context.user_data.get('order_type_display')
        price = context.user_data.get('price')
        full_name = context.user_data.get('full_name')
        phone = context.user_data.get('phone')
        order_details = context.user_data.get('order_details')
        
        # Buyurtmani bazaga qo'shish
        user_id = get_user_id(update.effective_chat.id)
        order_id = add_order(user_id, platform, order_type, price, full_name, phone, order_details)
        
        # Adminga xabar yuborish
        user_info = get_user_info(user_id)
        user_name = user_info[1] if user_info else "Noma'lum"
        username = f"@{user_info[2]}" if user_info and user_info[2] else "Yo'q"
        
        order_msg = (
            f"🛒 <b>YANGI BUYURTMA!</b>\n\n"
            f"🆔 Buyurtma ID: {order_id}\n"
            f"👤 Mijoz: {full_name}\n"
            f"📱 Telefon: {phone}\n"
            f"👥 Foydalanuvchi: {user_name} ({username})\n"
            f"📊 Platforma: {platform.capitalize()}\n"
            f"📝 Turi: {order_type_display}\n"
            f"💰 Narxi: {price}\n"
            f"📋 Tavsif: {order_details}\n\n"
            f"⏰ Vaqt: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"
        )
        
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=order_msg, parse_mode="HTML")
        
        # Foydalanuvchiga javob
        response_text = (
            f"✅ <b>Buyurtmangiz qabul qilindi!</b>\n\n"
            f"🆔 Buyurtma ID: {order_id}\n"
            f"💰 Narx: {price}\n"
            f"📊 Platforma: {platform.capitalize()}\n"
            f"📝 Tur: {order_type_display}\n\n"
            f"📞 Admin tez orada siz bilan bog'lanadi.\n\n"
            f"☎️ Admin telefon raqami: {config['admin_phone']}\n"
            
        )
        
        await update.message.reply_html(
            response_text,
            reply_markup=ReplyKeyboardMarkup([
                ["📞 Admin bilan bog'lanish"], 
                ["💰 Reklama narxlari"],
                ["🛒 Yangi buyurtma"],
                ["🌐 Ijtimoiy tarmoqlar"]
            ], resize_keyboard=True)
        )
    else:
        await update.message.reply_text(
            "❌ Buyurtma bekor qilindi.",
            reply_markup=ReplyKeyboardMarkup([
                ["📞 Admin bilan bog'lanish"], 
                ["💰 Reklama narxlari"],
                ["🛒 Yangi buyurtma"],
                ["🌐 Ijtimoiy tarmoqlar"]
            ], resize_keyboard=True)
        )
    
    # Foydalanuvchi ma'lumotlarini tozalash
    keys_to_remove = ['selected_platform', 'order_type', 'order_type_display', 'price', 
                     'full_name', 'phone', 'order_details', 'waiting_for_confirmation']
    for key in keys_to_remove:
        context.user_data.pop(key, None)

# === FOYDALANUVCHI UCHUN REKLAMA NARXLARI FUNKSIYALARI ===
async def show_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        ["📸 Instagram", "📨 Telegram"],
        ["📊 Instagram+Telegram Kombo", "🔙 Orqaga"]
    ]
    await update.message.reply_text(
        "💰 Reklama narxlari:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def show_instagram_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prices = load_prices()
    insta = prices['instagram']
    text = (
        f"📸 {insta['description']}:\n\n"
        f"• 📱 Story: {insta['story']}\n"
        f"• 📋 Post: {insta['post']}\n"
        f"• 📊 Story + Post: {insta['combo']}\n\n"
        f"ℹ️ Batafsil ma'lumot uchun admin bilan bog'laning."
    )
    await update.message.reply_text(text)

async def show_telegram_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prices = load_prices()
    tg = prices['telegram']
    text = (
        f"📨 {tg['description']}:\n\n"
        f"• 📱 Story: {tg['story']}\n"
        f"• 📋 Post: {tg['post']}\n"
        f"• 📊 Story + Post: {tg['combo']}\n\n"
        f"ℹ️ Batafsil ma'lumot uchun admin bilan bog'laning."
    )
    await update.message.reply_text(text)

async def show_combo_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    prices = load_prices()
    combo = prices['combo']
    text = (
        f"📊 {combo['description']}:\n\n"
        f"• 📱 Story: {combo['story']}\n"
        f"• 📋 Post: {combo['post']}\n"
        f"• 📊 Story + Post: {combo['combo']}\n\n"
        f"ℹ️ Batafsil ma'lumot uchun admin bilan bog'laning."
    )
    await update.message.reply_text(text)

# === IJTIMOIY TARMOQLAR FUNKSIYALARI ===
async def show_social_networks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    social_links = load_social_links()
    
    keyboard = [
        ["📲 Telegram", "📷 Instagram"],
        ["▶️ YouTube", "🌐 Veb sayt"],
        ["🔙 Orqaga"]
    ]
    
    await update.message.reply_text(
        "🌐 Bizning ijtimoiy tarmoqlarimiz:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def open_telegram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    social_links = load_social_links()
    await update.message.reply_text(
        f"📲 Bizning Telegram kanal: {social_links['telegram']}",
        reply_markup=ReplyKeyboardMarkup([["🔙 Orqaga"]], resize_keyboard=True)
    )

async def open_instagram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    social_links = load_social_links()
    await update.message.reply_text(
        f"📷 Bizning Instagram: {social_links['instagram']}",
        reply_markup=ReplyKeyboardMarkup([["🔙 Orqaga"]], resize_keyboard=True)
    )

async def open_youtube(update: Update, context: ContextTypes.DEFAULT_TYPE):
    social_links = load_social_links()
    await update.message.reply_text(
        f"▶️ Bizning YouTube kanal: {social_links['youtube']}",
        reply_markup=ReplyKeyboardMarkup([["🔙 Orqaga"]], resize_keyboard=True)
    )

async def open_website(update: Update, context: ContextTypes.DEFAULT_TYPE):
    social_links = load_social_links()
    await update.message.reply_text(
        f"🌐 Bizning veb sayt: {social_links['website']}",
        reply_markup=ReplyKeyboardMarkup([["🔙 Orqaga"]], resize_keyboard=True)
    )

# === ADMIN PANEL FUNKSIYALARI ===
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        context.user_data['waiting_for_admin_code'] = True
        await update.message.reply_text("❌ Siz admin emassiz. Kodni kiriting:")
        return
    
    keyboard = [
        ["📨 Barcha xabarlar", "🗑️ Xabarlarni tozalash"],
        ["📬 Javob berish", "🛒 Buyurtmalarni ko'rish"],
        ["🗑️ Buyurtmani o'chirish", "🗑️ Barcha buyurtmalarni o'chirish"],
        ["⚙️ Reklama narxlarini tahrirlash"],
        ["🔗 Ijtimoiy tarmoqlarni tahrirlash"],
        ["📱 Telefon raqamini o'zgartirish", "🔑 Kod almashtirish"],
        ["🔐 Admin paneldan chiqish"]
    ]
    await update.message.reply_text(
        "🔑 Admin panel:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data['waiting_for_admin_code'] = True
    await update.message.reply_text("🔐 Admin kodini kiriting:", reply_markup=ReplyKeyboardRemove())

async def admin_prices_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reply_text("❌ Siz admin emassiz!")
    
    keyboard = [
        ["📸 Instagram narxini o'zgartirish", "📨 Telegram narxini o'zgartirish"],
        ["📊 Kombo narxini o'zgartirish", "🔙 Admin panel"]
    ]
    await update.message.reply_text(
        "💰 Reklama narxlari paneli:",
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# === BUYURTMALARNI BOSHQARISH FUNKSIYALARI ===
async def view_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reply_text("❌ Siz admin emassiz!")
    
    orders = get_all_orders()
    if not orders:
        return await update.message.reply_text("📭 Buyurtmalar yo'q.")
    
    response = "🛒 Barcha buyurtmalar:\n\n"
    for order in orders[:10]:
        order_id, first_name, username, platform, order_type, price, full_name, phone, details, date, status = order
        display_username = f"@{username}" if username else "Noma'lum"
        status_emoji = "✅" if status == "completed" else "⏳" if status == "pending" else "❌"
        
        response += (
            f"🆔 {order_id} | {status_emoji} {status}\n"
            f"👤 {full_name} ({first_name} {display_username})\n"
            f"📱 {phone}\n"
            f"📊 {platform.capitalize()} - {order_type.capitalize()}\n"
            f"💰 {price}\n"
            f"📅 {date}\n"
            f"────────────────────\n\n"
        )
    
    await update.message.reply_text(response)

async def delete_order_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reply_text("❌ Siz admin emassiz!")
    
    context.user_data['waiting_for_order_id'] = True
    await update.message.reply_text("🗑️ O'chirish uchun buyurtma ID sini kiriting:", reply_markup=ReplyKeyboardRemove())

async def delete_all_orders_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reply_text("❌ Siz admin emassiz!")
    
    context.user_data['waiting_for_confirm_delete_orders'] = True
    await update.message.reply_text("⚠️ Barcha buyurtmalarni o'chirishni tasdiqlaysizmi? (Ha/Yo'q)", reply_markup=ReplyKeyboardRemove())

async def change_instagram_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reply_text("❌ Siz admin emassiz!")
    
    prices = load_prices()
    insta = prices['instagram']
    
    text = (
        f"📸 Instagram joriy narxlari:\n\n"
        f"📝 Tavsif: {insta['description']}\n"
        f"1. 📱 Story: {insta['story']}\n"
        f"2. 📋 Post: {insta['post']}\n"
        f"3. 📊 Story + Post: {insta['combo']}\n\n"
        f"Qaysi narxni o'zgartirmoqchisiz?"
    )
    
    context.user_data['editing_platform'] = 'instagram'
    
    keyboard = [
        ["📝 Tavsifni o'zgartirish", "📱 Story narxini o'zgartirish"],
        ["📋 Post narxini o'zgartirish", "📊 Kombo narxini o'zgartirish"],
        ["🔙 Orqaga"]
    ]
    
    await update.message.reply_text(
        text, 
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def change_telegram_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reply_text("❌ Siz admin emassiz!")
    
    prices = load_prices()
    tg = prices['telegram']
    
    text = (
        f"📨 Telegram joriy narxlari:\n\n"
        f"📝 Tavsif: {tg['description']}\n"
        f"1. 📱 Story: {tg['story']}\n"
        f"2. 📋 Post: {tg['post']}\n"
        f"3. 📊 Story + Post: {tg['combo']}\n\n"
        f"Qaysi narxni o'zgartirmoqchisiz?"
    )
    
    context.user_data['editing_platform'] = 'telegram'
    
    keyboard = [
        ["📝 Tavsifni o'zgartirish", "📱 Story narxini o'zgartirish"],
        ["📋 Post narxini o'zgartirish", "📊 Kombo narxini o'zgartirish"],
        ["🔙 Orqaga"]
    ]
    
    await update.message.reply_text(
        text, 
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def change_combo_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reply_text("❌ Siz admin emassiz!")
    
    prices = load_prices()
    combo = prices['combo']
    
    text = (
        f"📊 Kombo joriy narxlari:\n\n"
        f"📝 Tavsif: {combo['description']}\n"
        f"1. 📱 Story: {combo['story']}\n"
        f"2. 📋 Post: {combo['post']}\n"
        f"3. 📊 Story + Post: {combo['combo']}\n\n"
        f"Qaysi narxni o'zgartirmoqchisiz?"
    )
    
    context.user_data['editing_platform'] = 'combo'
    
    keyboard = [
        ["📝 Tavsifni o'zgartirish", "📱 Story narxini o'zgartirish"],
        ["📋 Post narxini o'zgartirish", "📊 Kombo narxini o'zgartirish"],
        ["🔙 Orqaga"]
    ]
    
    await update.message.reply_text(
        text, 
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

# === IJTIMOIY TARMOQLARNI TAHRIRLASH FUNKSIYALARI ===
async def edit_social_links(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reppy_text("❌ Siz admin emassiz!")
    
    social_links = load_social_links()
    
    keyboard = [
        ["📲 Telegram linkini o'zgartirish", "📷 Instagram linkini o'zgartirish"],
        ["▶️ YouTube linkini o'zgartirish", "🌐 Veb sayt linkini o'zgartirish"],
        ["🔙 Admin panel"]
    ]
    
    text = (
        "🔗 Ijtimoiy tarmoqlarni tahrirlash:\n\n"
        f"📲 Telegram: {social_links['telegram']}\n"
        f"📷 Instagram: {social_links['instagram']}\n"
        f"▶️ YouTube: {social_links['youtube']}\n"
        f"🌐 Veb sayt: {social_links['website']}"
    )
    
    await update.message.reply_text(
        text,
        reply_markup=ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    )

async def change_telegram_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reply_text("❌ Siz admin emassiz!")
    
    context.user_data['editing_social'] = 'telegram'
    context.user_data['waiting_for_social_link'] = True
    
    social_links = load_social_links()
    await update.message.reply_text(
        f"📲 Joriy Telegram linki: {social_links['telegram']}\nYangi linkni kiriting:",
        reply_markup=ReplyKeyboardRemove()
    )

async def change_instagram_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reply_text("❌ Siz admin emassiz!")
    
    context.user_data['editing_social'] = 'instagram'
    context.user_data['waiting_for_social_link'] = True
    
    social_links = load_social_links()
    await update.message.reply_text(
        f"📷 Joriy Instagram linki: {social_links['instagram']}\nYangi linkni kiriting:",
        reply_markup=ReplyKeyboardRemove()
    )

async def change_youtube_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reply_text("❌ Siz admin emassiz!")
    
    context.user_data['editing_social'] = 'youtube'
    context.user_data['waiting_for_social_link'] = True
    
    social_links = load_social_links()
    await update.message.reply_text(
        f"▶️ Joriy YouTube linki: {social_links['youtube']}\nYangi linkni kiriting:",
        reply_markup=ReplyKeyboardRemove()
    )

async def change_website_link(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.user_data.get('admin'):
        return await update.message.reply_text("❌ Siz admin emassiz!")
    
    context.user_data['editing_social'] = 'website'
    context.user_data['waiting_for_social_link'] = True
    
    social_links = load_social_links()
    await update.message.reply_text(
        f"🌐 Joriy veb sayt linki: {social_links['website']}\nYangi linkni kiriting:",
        reply_markup=ReplyKeyboardRemove()
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

        await update.message.reply_text("✅ Xabaringiz yuborildi.", reply_markup=ReplyKeyboardMarkup([["📞 Admin bilan bog'lanish"], ["💰 Reklama narxlari"], ["🛒 Reklama sotib olish"], ["🌐 Ijtimoiy tarmoqlar"], ["ℹ️ Yordam"]], resize_keyboard=True))
        user_data['waiting_for_message'] = False
        return

    # Ism va familiya kiritish
    if user_data.get('waiting_for_full_name'):
        await process_full_name(update, context)
        return

    # Telefon raqam kiritish
    if user_data.get('waiting_for_phone'):
        await process_phone(update, context)
        return

    # Buyurtma tafsilotlari kiritish
    if user_data.get('waiting_for_order_details'):
        await process_order_details(update, context)
        return

    # Buyurtma tasdiqlash
    if user_data.get('waiting_for_confirmation'):
        await process_confirmation(update, context)
        return

    # Buyurtma ID sini kutish (o'chirish uchun)
    if user_data.get('waiting_for_order_id'):
        try:
            order_id = int(update.message.text)
            order = get_order_by_id(order_id)
            if order:
                delete_order(order_id)
                await update.message.reply_text(f"✅ {order_id} ID li buyurtma o'chirildi.")
            else:
                await update.message.reply_text("❌ Buyurtma topilmadi!")
        except ValueError:
            await update.message.reply_text("❌ Noto'g'ri ID format!")
        user_data.pop('waiting_for_order_id', None)
        return await admin_panel(update, context)

    # Barcha buyurtmalarni o'chirish tasdiqlash
    if user_data.get('waiting_for_confirm_delete_orders'):
        if update.message.text.lower() == 'ha':
            delete_all_orders()
            await update.message.reply_text("✅ Barcha buyurtmalar o'chirildi.")
        else:
            await update.message.reply_text("❌ Buyurtmalarni o'chirish bekor qilindi.")
        user_data.pop('waiting_for_confirm_delete_orders', None)
        return await admin_panel(update, context)

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
        if not re.match(r'^\+998\d{9}$', new_phone):
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

    # Ijtimoiy tarmoq linkini o'zgartirish
    if user_data.get('waiting_for_social_link'):
        new_link = update.message.text
        platform = user_data['editing_social']
        
        # Linkni tekshirish
        if not new_link.startswith(('http://', 'https://')):
            new_link = 'https://' + new_link
        
        # Linkni saqlash
        social_links = load_social_links()
        social_links[platform] = new_link
        save_social_links(social_links)
        
        await update.message.reply_text(
            f"✅ {platform.capitalize()} linki muvaffaqiyatli o'zgartirildi: {new_link}",
            reply_markup=ReplyKeyboardMarkup([["🔙 Admin panel"]], resize_keyboard=True)
        )
        
        # Foydalanuvchi ma'lumotlarini tozalash
        user_data.pop('editing_social', None)
        user_data.pop('waiting_for_social_link', None)
        return

    # Narx turini tanlash (keyboard orqali)
    if user_data.get('editing_platform'):
        platform = user_data['editing_platform']
        prices = load_prices()
        
        # Tavsifni o'zgartirish
        if update.message.text == "📝 Tavsifni o'zgartirish":
            user_data['editing_price_type'] = 'description'
            user_data['waiting_for_new_price'] = True
            await update.message.reply_text(
                f"Joriy tavsif: {prices[platform]['description']}\nYangi tavsifni kiriting:",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        # Story narxini o'zgartirish
        elif update.message.text == "📱 Story narxini o'zgartirish":
            user_data['editing_price_type'] = 'story'
            user_data['waiting_for_new_price'] = True
            await update.message.reply_text(
                f"Joriy story narxi: {prices[platform]['story']}\nYangi narxni kiriting:",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        # Post narxini o'zgartirish
        elif update.message.text == "📋 Post narxini o'zgartirish":
            user_data['editing_price_type'] = 'post'
            user_data['waiting_for_new_price'] = True
            await update.message.reply_text(
                f"Joriy post narxi: {prices[platform]['post']}\nYangi narxni kiriting:",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        # Kombo narxini o'zgartirish
        elif update.message.text == "📊 Kombo narxini o'zgartirish":
            user_data['editing_price_type'] = 'combo'
            user_data['waiting_for_new_price'] = True
            await update.message.reply_text(
                f"Joriy kombo narxi: {prices[platform]['combo']}\nYangi narxni kiriting:",
                reply_markup=ReplyKeyboardRemove()
            )
            return
        
        # Orqaga qaytish
        elif update.message.text == "🔙 Orqaga":
            user_data.pop('editing_platform', None)
            return await admin_prices_panel(update, context)
    
    # Yangi narxni o'qish
    if user_data.get('waiting_for_new_price'):
        new_value = update.message.text
        platform = user_data['editing_platform']
        price_type = user_data['editing_price_type']
        
        # Narxni saqlash
        prices = load_prices()
        prices[platform][price_type] = new_value
        save_prices(prices)
        
        if price_type == 'description':
            await update.message.reply_text(
                f"✅ {platform.capitalize()}ning tavsifi muvaffaqiyatli o'zgartirildi.",
                reply_markup=ReplyKeyboardMarkup([["🔙 Admin panel"]], resize_keyboard=True)
            )
        else:
            await update.message.reply_text(
                f"✅ {platform.capitalize()}ning {price_type} narxi {new_value} ga o'zgartirildi.",
                reply_markup=ReplyKeyboardMarkup([["🔙 Admin panel"]], resize_keyboard=True)
            )
        
        # Foydalanuvchi ma'lumotlarini tozalash
        user_data.pop('editing_platform', None)
        user_data.pop('editing_price_type', None)
        user_data.pop('waiting_for_new_price', None)
        return

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
    await update.message.reply_text("🔓 Admin paneldan chiqdingiz.", reply_markup=ReplyKeyboardMarkup([["📞 Admin bilan bog'lanish"], ["💰 Reklama narxlari"], ["🛒 Reklama sotib olish"], ["🌐 Ijtimoiy tarmoqlar"], ["ℹ️ Yordam"]], resize_keyboard=True))

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 <b>Yordam</b>\n\n"
        "📞 <b>Admin bilan bog'lanish</b> - Administratorga xabar yuborish yoki telefon qilish\n"
        "💰 <b>Reklama narxlari</b> - Instagram, Telegram va Kombo reklama narxlari\n"
        "🛒 <b>Reklama sotib olish</b> - Yangi reklama buyurtma berish\n"
        "🌐 <b>Ijtimoiy tarmoqlar</b> - Bizning ijtimoiy tarmoqdagi sahifalarimiz\n"
        "🔑 <b>Admin panel</b> - /admin buyrug'i orqali admin paneliga kirish\n\n"
        "ℹ️ Qo'shimcha ma'lumot olish uchun admin bilan bog'laning."
    )
    await update.message.reply_html(help_text)

def main():
    init_db()
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_login))
    application.add_handler(CommandHandler("reply", reply_command))
    application.add_handler(CommandHandler("help", help_command))

    # Foydalanuvchi handlerlari
    application.add_handler(MessageHandler(filters.Regex("^📞 Admin bilan bog'lanish$"), contact_admin))
    application.add_handler(MessageHandler(filters.Regex("^✍️ Xabar yozish$"), write_message))
    application.add_handler(MessageHandler(filters.Regex("^📞 Telefon qilish$"), call_admin))
    application.add_handler(MessageHandler(filters.Regex("^🔙 Orqaga$"), back_to_main))
    application.add_handler(MessageHandler(filters.Regex("^💰 Reklama narxlari$"), show_prices))
    application.add_handler(MessageHandler(filters.Regex("^📸 Instagram$"), select_platform))
    application.add_handler(MessageHandler(filters.Regex("^📨 Telegram$"), select_platform))
    application.add_handler(MessageHandler(filters.Regex("^📊 Instagram\+Telegram Kombo$"), select_platform))
    application.add_handler(MessageHandler(filters.Regex("^📱 Story$"), select_order_type))
    application.add_handler(MessageHandler(filters.Regex("^📋 Post$"), select_order_type))
    application.add_handler(MessageHandler(filters.Regex("^📊 Story\+Post Kombo$"), select_order_type))
    application.add_handler(MessageHandler(filters.Regex("^✅ Ha, tasdiqlayman$"), process_confirmation))
    application.add_handler(MessageHandler(filters.Regex("^❌ Yo'q, bekor qilish$"), process_confirmation))
    application.add_handler(MessageHandler(filters.Regex("^🛒 Reklama sotib olish$"), buy_advertisement))
    application.add_handler(MessageHandler(filters.Regex("^🌐 Ijtimoiy tarmoqlar$"), show_social_networks))
    application.add_handler(MessageHandler(filters.Regex("^📲 Telegram$"), open_telegram))
    application.add_handler(MessageHandler(filters.Regex("^📷 Instagram$"), open_instagram))
    application.add_handler(MessageHandler(filters.Regex("^▶️ YouTube$"), open_youtube))
    application.add_handler(MessageHandler(filters.Regex("^🌐 Veb sayt$"), open_website))

    # Admin handlerlari
    application.add_handler(MessageHandler(filters.Regex("^📨 Barcha xabarlar$"), view_messages))
    application.add_handler(MessageHandler(filters.Regex("^🗑️ Xabarlarni tozalash$"), delete_messages))
    application.add_handler(MessageHandler(filters.Regex("^📬 Javob berish$"), reply_command))
    application.add_handler(MessageHandler(filters.Regex("^🛒 Buyurtmalarni ko'rish$"), view_orders))
    application.add_handler(MessageHandler(filters.Regex("^🗑️ Buyurtmani o'chirish$"), delete_order_command))
    application.add_handler(MessageHandler(filters.Regex("^🗑️ Barcha buyurtmalarni o'chirish$"), delete_all_orders_command))
    application.add_handler(MessageHandler(filters.Regex("^⚙️ Reklama narxlarini tahrirlash$"), admin_prices_panel))
    application.add_handler(MessageHandler(filters.Regex("^🔗 Ijtimoiy tarmoqlarni tahrirlash$"), edit_social_links))
    application.add_handler(MessageHandler(filters.Regex("^📲 Telegram linkini o'zgartirish$"), change_telegram_link))
    application.add_handler(MessageHandler(filters.Regex("^📷 Instagram linkini o'zgartirish$"), change_instagram_link))
    application.add_handler(MessageHandler(filters.Regex("^▶️ YouTube linkini o'zgartirish$"), change_youtube_link))
    application.add_handler(MessageHandler(filters.Regex("^🌐 Veb sayt linkini o'zgartirish$"), change_website_link))
    application.add_handler(MessageHandler(filters.Regex("^📸 Instagram narxini o'zgartirish$"), change_instagram_prices))
    application.add_handler(MessageHandler(filters.Regex("^📨 Telegram narxini o'zgartirish$"), change_telegram_prices))
    application.add_handler(MessageHandler(filters.Regex("^📊 Kombo narxini o'zgartirish$"), change_combo_prices))
    application.add_handler(MessageHandler(filters.Regex("^📱 Telefon raqamini o'zgartirish$"), change_phone))
    application.add_handler(MessageHandler(filters.Regex("^🔑 Kod almashtirish$"), change_code))
    application.add_handler(MessageHandler(filters.Regex("^🔐 Admin paneldan chiqish$"), admin_logout))
    application.add_handler(MessageHandler(filters.Regex("^🔙 Admin panel$"), admin_panel))
    
    # Narx tahrirlash uchun yangi handlerlar
    application.add_handler(MessageHandler(filters.Regex("^📝 Tavsifni o'zgartirish$"), handle_message))
    application.add_handler(MessageHandler(filters.Regex("^📱 Story narxini o'zgartirish$"), handle_message))
    application.add_handler(MessageHandler(filters.Regex("^📋 Post narxini o'zgartirish$"), handle_message))
    application.add_handler(MessageHandler(filters.Regex("^📊 Kombo narxini o'zgartirish$"), handle_message))

    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))
    print("🤖 Bot ishga tushdi...")
    application.run_polling()

if __name__ == '__main__':
    main()