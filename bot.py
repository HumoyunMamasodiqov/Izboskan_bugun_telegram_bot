import logging
import sqlite3
from datetime import datetime
from typing import Dict, List, Optional, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, ContextTypes, filters, ConversationHandler
from telegram.constants import ParseMode

# === KONFIGURATSIYA ===
BOT_TOKEN = "8250661516:AAHNwNWH1JWFK83FDCv6juuptqUvAqPNA98"  # O'z bot tokeningizni qo'ying
ADMIN_CHAT_ID = "7678962106"  # O'z chat IDingizni qo'ying
ADMIN_PHONE = "+998933320335"  # Admin telefon raqami
DEFAULT_PASSWORD = "7777"  # Default parol
SOCIAL_MEDIA_URL = "https://boskanbugunpotug.netlify.app"

# Ma'lumotlar bazasi
DB_NAME = "bot_database.db"

# Holatlar (Conversation states)
SELECTING_ACTION, TYPING_MESSAGE, ORDER_NAME, ORDER_PHONE, ORDER_PLATFORM, ORDER_PACKAGE, ORDER_COMMENT, ADMIN_LOGIN, ADMIN_MAIN, \
EDIT_PRICES, VIEW_ORDERS, VIEW_MESSAGES, ADMIN_HISTORY, CHANGE_PASSWORD, RESPOND_TO_MESSAGE, CONFIRM_ORDER = range(16)

# Narxlar (default qiymatlar)
prices = {
    "telegram": {"stories": 50000, "post": 100000, "stories_post": 120000},
    "instagram": {"stories": 60000, "post": 110000, "stories_post": 130000},
    "both": {"stories": 100000, "post": 180000, "stories_post": 200000}
}

# === LOGGING ===
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# === MA'LUMOTLAR BAZASI ===
def init_db():
    """Ma'lumotlar bazasini ishga tushirish"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # Foydalanuvchilar jadvali
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        phone TEXT,
        first_name TEXT,
        last_name TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    )
    ''')
    
    # Xabarlar jadvali
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        message_text TEXT,
        admin_response TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    # Buyurtmalar jadvali
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        customer_name TEXT,
        phone TEXT,
        platform TEXT,
        package TEXT,
        comment TEXT,
        status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    # Admin kirish tarixi jadvali
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS admin_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        success INTEGER,
        attempted_password TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (user_id) REFERENCES users (user_id)
    )
    ''')
    
    conn.commit()
    conn.close()

def save_user(user_id, username, first_name, last_name):
    """Foydalanuvchini ma'lumotlar bazasiga saqlash"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT OR IGNORE INTO users (user_id, username, first_name, last_name) VALUES (?, ?, ?, ?)',
        (user_id, username, first_name, last_name)
    )
    
    conn.commit()
    conn.close()

def update_user_phone(user_id, phone):
    """Foydalanuvchi telefon raqamini yangilash"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        'UPDATE users SET phone = ? WHERE user_id = ?',
        (phone, user_id)
    )
    
    conn.commit()
    conn.close()

def save_message(user_id, message_text):
    """Xabarni saqlash"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT INTO messages (user_id, message_text) VALUES (?, ?)',
        (user_id, message_text)
    )
    
    conn.commit()
    conn.close()
    return cursor.lastrowid

def save_order(user_id, customer_name, phone, platform, package, comment):
    """Buyurtmani saqlash"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        '''INSERT INTO orders (user_id, customer_name, phone, platform, package, comment) 
        VALUES (?, ?, ?, ?, ?, ?)''',
        (user_id, customer_name, phone, platform, package, comment)
    )
    
    conn.commit()
    conn.close()
    return cursor.lastrowid

def get_user_orders(user_id):
    """Foydalanuvchi buyurtmalarini olish"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT * FROM orders WHERE user_id = ? ORDER BY created_at DESC',
        (user_id,)
    )
    
    orders = cursor.fetchall()
    conn.close()
    return orders

def get_all_orders():
    """Barcha buyurtmalarni olish"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT o.*, u.username FROM orders o LEFT JOIN users u ON o.user_id = u.user_id ORDER BY o.created_at DESC'
    )
    
    orders = cursor.fetchall()
    conn.close()
    return orders

def get_all_messages():
    """Barcha xabarlarni olish"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        'SELECT m.*, u.username FROM messages m LEFT JOIN users u ON m.user_id = u.user_id ORDER BY m.created_at DESC'
    )
    
    messages = cursor.fetchall()
    conn.close()
    return messages

def update_order_status(order_id, status):
    """Buyurtma statusini yangilash"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        'UPDATE orders SET status = ? WHERE id = ?',
        (status, order_id)
    )
    
    conn.commit()
    conn.close()

def log_admin_access(user_id, success, attempted_password):
    """Admin kirish tarixini saqlash"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        'INSERT INTO admin_history (user_id, success, attempted_password) VALUES (?, ?, ?)',
        (user_id, success, attempted_password)
    )
    
    conn.commit()
    conn.close()

def get_admin_history():
    """Admin kirish tarixini olish"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    cursor.execute(
        '''SELECT ah.*, u.username 
        FROM admin_history ah 
        LEFT JOIN users u ON ah.user_id = u.user_id 
        ORDER BY ah.created_at DESC'''
    )
    
    history = cursor.fetchall()
    conn.close()
    return history

# === YORDAMCHI FUNKSIYALAR ===
async def send_admin_notification(context: ContextTypes.DEFAULT_TYPE, message: str):
    """Adminga bildirishnoma yuborish"""
    try:
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=message, parse_mode=ParseMode.HTML)
    except Exception as e:
        logger.error(f"Adminga xabar yuborishda xatolik: {e}")

def get_main_keyboard():
    """Asosiy keyboardni yaratish"""
    keyboard = [
        ["👤 Admin bilan bog'lanish", "📊 Reklama narxlari"],
        ["🌐 Ijtimoiy tarmoqlar", "🛒 Reklama sotib olish"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_contact_keyboard():
    """Admin bilan bog'lanish keyboardi"""
    keyboard = [
        ["📩 Xabar yuborish", "📞 Telefon qilish"],
        ["🔙 Asosiy menyu"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_admin_main_keyboard():
    """Admin asosiy keyboardi"""
    keyboard = [
        ["📊 Narxlarni boshqarish", "📜 Buyurtmalarni ko'rish"],
        ["💬 Xabarlarga javob berish", "🔔 Kirish tarixi"],
        ["🔑 Parolni o'zgartirish", "🔙 Asosiy menyu"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_back_keyboard():
    """Orqaga keyboardi"""
    keyboard = [["🔙 Orqaga"]]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_platform_keyboard():
    """Platforma tanlash keyboardi"""
    keyboard = [
        ["📱 Telegram", "📷 Instagram"],
        ["🔗 Telegram + Instagram birgalikda"],
        ["🔙 Orqaga"]
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_package_keyboard(platform: str):
    """Paket tanlash keyboardi"""
    if platform == "both":
        platform_key = "both"
    elif platform == "instagram":
        platform_key = "instagram"
    else:
        platform_key = "telegram"
    
    packages = prices[platform_key]
    keyboard = []
    
    for package_name, price in packages.items():
        if package_name == "stories":
            display_name = "Stories"
        elif package_name == "post":
            display_name = "Post"
        else:
            display_name = "Stories + Post"
        
        keyboard.append([f"{display_name} - {price:,} so'm"])
    
    keyboard.append(["🔙 Orqaga"])
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

def get_order_status_keyboard(order_id):
    """Buyurtma statusi keyboardi"""
    keyboard = [
        [
            InlineKeyboardButton("✅ Tasdiqlash", callback_data=f"confirm_{order_id}"),
            InlineKeyboardButton("❌ Rad etish", callback_data=f"reject_{order_id}")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

# === BOSHQARUV HANDLERLARI ===
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Botni ishga tushirish"""
    user = update.effective_user
    save_user(user.id, user.username, user.first_name, user.last_name)
    
    welcome_text = (
        f"Assalomu alaykum {user.first_name}! 👋\n\n"
        "Reklama xizmatlarimizdan foydalanish uchun botimizga xush kelibsiz.\n\n"
        "Quyidagi menyulardan birini tanlang:"
    )
    
    await update.message.reply_text(welcome_text, reply_markup=get_main_keyboard())
    return SELECTING_ACTION

async def admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin paneliga kirish"""
    await update.message.reply_text(
        "Admin paneliga kirish uchun parolni kiriting:",
        reply_markup=get_back_keyboard()
    )
    return ADMIN_LOGIN

async def main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Asosiy menyuga qaytish"""
    await update.message.reply_text("Asosiy menyu:", reply_markup=get_main_keyboard())
    return SELECTING_ACTION

async def admin_contact(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin bilan bog'lanish"""
    await update.message.reply_text(
        "Admin bilan bog'lanish usulini tanlang:",
        reply_markup=get_admin_contact_keyboard()
    )
    return SELECTING_ACTION

async def send_message_to_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Adminga xabar yuborish"""
    await update.message.reply_text(
        "Xabaringizni yozing va yuboring. Adminga to'g'ridan-to'g'ri yuboriladi:",
        reply_markup=get_back_keyboard()
    )
    return TYPING_MESSAGE

async def handle_user_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Foydalanuvchi xabarini qayta ishlash va adminga yuborish"""
    user_message = update.message.text
    user = update.effective_user
    
    # Xabarni ma'lumotlar bazasiga saqlash
    message_id = save_message(user.id, user_message)
    
    # Adminga bildirishnoma yuborish
    notification = (
        f"📩 <b>Yangi xabar</b>\n\n"
        f"👤 <b>Foydalanuvchi:</b> {user.first_name}\n"
        f"🔗 <b>Username:</b> @{user.username if user.username else 'Noma lum'}\n"
        f"🆔 <b>ID:</b> {user.id}\n\n"
        f"💬 <b>Xabar:</b>\n{user_message}"
    )
    
    await send_admin_notification(context, notification)
    await update.message.reply_text(
        "✅ Xabaringiz muvaffaqiyatli yuborildi! Admin tez orada sizga javob beradi.",
        reply_markup=get_admin_contact_keyboard()
    )
    
    return SELECTING_ACTION

async def show_admin_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin telefon raqamini ko'rsatish"""
    await update.message.reply_text(
        f"Admin telefon raqami: {ADMIN_PHONE}\n\n"
        "Telefon qilish uchun quyidagi tugmani bosing:",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("📞 Telefon qilish", url=f"tel:{ADMIN_PHONE}")]
        ])
    )
    return SELECTING_ACTION

async def social_media(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Ijtimoiy tarmoqlar havolasini ko'rsatish"""
    await update.message.reply_text(
        "Bizning ijtimoiy tarmoqlarimiz:\n\n"
        f"{SOCIAL_MEDIA_URL}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🌐 Veb-sahifani ko'rish", url=SOCIAL_MEDIA_URL)]
        ])
    )
    return SELECTING_ACTION

async def show_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Reklama narxlarini ko'rsatish"""
    price_text = "📊 <b>Reklama narxlari</b>\n\n"
    
    # Telegram narxlari
    price_text += "📱 <b>Telegram</b>\n"
    for package, price in prices["telegram"].items():
        package_name = "Stories" if package == "stories" else "Post" if package == "post" else "Stories + Post"
        price_text += f"   • {package_name}: {price:,} so'm\n"
    
    # Instagram narxlari
    price_text += "\n📷 <b>Instagram</b>\n"
    for package, price in prices["instagram"].items():
        package_name = "Stories" if package == "stories" else "Post" if package == "post" else "Stories + Post"
        price_text += f"   • {package_name}: {price:,} so'm\n"
    
    # Birgalikdagi narxlar
    price_text += "\n🔗 <b>Telegram + Instagram birgalikda</b>\n"
    for package, price in prices["both"].items():
        package_name = "Stories" if package == "stories" else "Post" if package == "post" else "Stories + Post"
        price_text += f"   • {package_name}: {price:,} so'm\n"
    
    price_text += "\nPlatformani tanlang:"
    
    await update.message.reply_text(price_text, parse_mode=ParseMode.HTML, reply_markup=get_platform_keyboard())
    return SELECTING_ACTION

async def start_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyurtma berishni boshlash"""
    await update.message.reply_text(
        "Ismingizni kiriting:",
        reply_markup=get_back_keyboard()
    )
    return ORDER_NAME

async def order_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyurtma uchun ismni qabul qilish"""
    context.user_data['order_name'] = update.message.text
    await update.message.reply_text(
        "Telefon raqamingizni kiriting:",
        reply_markup=get_back_keyboard()
    )
    return ORDER_PHONE

async def order_phone(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyurtma uchun telefon raqamini qabul qilish"""
    phone = update.message.text
    context.user_data['order_phone'] = phone
    
    # Foydalanuvchi telefon raqamini yangilash
    update_user_phone(update.effective_user.id, phone)
    
    await update.message.reply_text(
        "Platformani tanlang:",
        reply_markup=get_platform_keyboard()
    )
    return ORDER_PLATFORM

async def order_platform(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Platformani qabul qilish"""
    platform_text = update.message.text
    
    if "Telegram" in platform_text and "Instagram" in platform_text:
        platform = "both"
    elif "Instagram" in platform_text:
        platform = "instagram"
    else:
        platform = "telegram"
    
    context.user_data['order_platform'] = platform
    
    await update.message.reply_text(
        "Reklama paketini tanlang:",
        reply_markup=get_package_keyboard(platform)
    )
    return ORDER_PACKAGE

async def order_package(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Paketni qabul qilish va izoh so'rash"""
    package_text = update.message.text
    
    if "Stories" in package_text and "Post" in package_text:
        package = "stories_post"
    elif "Stories" in package_text:
        package = "stories"
    else:
        package = "post"
    
    context.user_data['order_package'] = package
    
    await update.message.reply_text(
        "Qo'shimcha izoh yozing (agar kerak bo'lsa):",
        reply_markup=ReplyKeyboardMarkup([["⏭ O'tkazib yuborish"], ["🔙 Orqaga"]], resize_keyboard=True)
    )
    return ORDER_COMMENT

async def order_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Izohni qabul qilish va buyurtmani tasdiqlash"""
    comment = update.message.text
    if comment == "⏭ O'tkazib yuborish":
        comment = "Yo'q"
    
    context.user_data['order_comment'] = comment
    
    # Buyurtma ma'lumotlarini yig'ish
    order_name = context.user_data['order_name']
    order_phone = context.user_data['order_phone']
    order_platform = context.user_data['order_platform']
    order_package = context.user_data['order_package']
    
    # Paket nomini formatlash
    if order_package == "stories":
        package_name = "Stories"
    elif order_package == "post":
        package_name = "Post"
    else:
        package_name = "Stories + Post"
    
    # Platforma nomini formatlash
    if order_platform == "telegram":
        platform_name = "Telegram"
    elif order_platform == "instagram":
        platform_name = "Instagram"
    else:
        platform_name = "Telegram + Instagram"
    
    # Narxni olish
    price = prices[order_platform][order_package]
    
    order_summary = (
        f"🛒 <b>Buyurtma xulosasi</b>\n\n"
        f"👤 <b>Ism:</b> {order_name}\n"
        f"📞 <b>Telefon:</b> {order_phone}\n"
        f"📱 <b>Platforma:</b> {platform_name}\n"
        f"📦 <b>Paket:</b> {package_name}\n"
        f"💵 <b>Narx:</b> {price:,} so'm\n"
        f"💬 <b>Izoh:</b> {comment}\n\n"
        "Buyurtmani tasdiqlaysizmi?"
    )
    
    await update.message.reply_text(
        order_summary,
        parse_mode=ParseMode.HTML,
        reply_markup=ReplyKeyboardMarkup([["✅ Tasdiqlash", "❌ Bekor qilish"]], resize_keyboard=True)
    )
    return CONFIRM_ORDER

async def confirm_order(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyurtmani tasdiqlash"""
    if update.message.text == "❌ Bekor qilish":
        await update.message.reply_text(
            "Buyurtma bekor qilindi.",
            reply_markup=get_main_keyboard()
        )
        return SELECTING_ACTION
    
    # Buyurtma ma'lumotlarini olish
    user = update.effective_user
    order_name = context.user_data['order_name']
    order_phone = context.user_data['order_phone']
    order_platform = context.user_data['order_platform']
    order_package = context.user_data['order_package']
    order_comment = context.user_data['order_comment']
    
    # Buyurtmani saqlash
    order_id = save_order(user.id, order_name, order_phone, order_platform, order_package, order_comment)
    
    # Paket nomini formatlash
    if order_package == "stories":
        package_name = "Stories"
    elif order_package == "post":
        package_name = "Post"
    else:
        package_name = "Stories + Post"
    
    # Platforma nomini formatlash
    if order_platform == "telegram":
        platform_name = "Telegram"
    elif order_platform == "instagram":
        platform_name = "Instagram"
    else:
        platform_name = "Telegram + Instagram"
    
    # Narxni olish
    price = prices[order_platform][order_package]
    
    # Adminga bildirishnoma yuborish
    notification = (
        f"🛒 <b>Yangi buyurtma</b> #{order_id}\n\n"
        f"👤 <b>Mijoz:</b> {order_name}\n"
        f"📞 <b>Telefon:</b> {order_phone}\n"
        f"📱 <b>Platforma:</b> {platform_name}\n"
        f"📦 <b>Paket:</b> {package_name}\n"
        f"💵 <b>Narx:</b> {price:,} so'm\n"
        f"💬 <b>Izoh:</b> {order_comment}\n\n"
        f"👤 <b>Foydalanuvchi:</b> {user.first_name}\n"
        f"🔗 <b>Username:</b> @{user.username if user.username else 'Noma lum'}\n"
        f"🆔 <b>ID:</b> {user.id}"
    )
    
    await send_admin_notification(context, notification)
    
    # Adminga buyurtma statusini o'zgartirish uchun tugma yuborish
    await context.bot.send_message(
        chat_id=ADMIN_CHAT_ID,
        text="Buyurtma statusini o'zgartiring:",
        reply_markup=get_order_status_keyboard(order_id),
        parse_mode=ParseMode.HTML
    )
    
    await update.message.reply_text(
        "✅ Buyurtmangiz qabul qilindi! Admin tez orada siz bilan bog'lanadi.",
        reply_markup=get_main_keyboard()
    )
    
    return SELECTING_ACTION

# === ADMIN HANDLERLARI ===
async def admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin paneliga kirish"""
    await update.message.reply_text(
        "Admin paneliga kirish uchun parolni kiriting:",
        reply_markup=get_back_keyboard()
    )
    return ADMIN_LOGIN

async def handle_admin_login(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin parolini tekshirish"""
    password = update.message.text
    user = update.effective_user
    
    # Parolni tekshirish
    if password == DEFAULT_PASSWORD:
        # Muvaffaqiyatli kirish
        log_admin_access(user.id, 1, password)
        await update.message.reply_text(
            "✅ Admin paneliga xush kelibsiz!",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN
    else:
        # Noto'g'ri parol
        log_admin_access(user.id, 0, password)
        
        # Noto'g'ri parol kiritilganlar sonini hisoblash
        history = get_admin_history()
        failed_attempts = sum(1 for entry in history if entry[2] == 0 and entry[1] == user.id)
        
        if failed_attempts >= 2:  # 0-indexda, shuning uchun 2 = 3 marta
            # 3 marta noto'g'ri parol kiritilganda adminga xabar
            warning_msg = (
                f"⚠️ <b>Ogohlantirish</b>\n\n"
                f"Foydalanuvchi @{user.username if user.username else 'Noma lum'} (ID: {user.id}) "
                f"3 marta noto'g'ri parol kiritdi.\n"
                f"Oxirgi kiritilgan parol: {password}"
            )
            await send_admin_notification(context, warning_msg)
            
            await update.message.reply_text(
                "❌ Parol noto'g'ri. Siz 3 marta noto'g'ri parol kiritdingiz. "
                "Admin ogohlantirildi.",
                reply_markup=get_main_keyboard()
            )
            return SELECTING_ACTION
        
        await update.message.reply_text(
            f"❌ Noto'g'ri parol. Qayta urining. "
            f"Siz {failed_attempts + 1}/3 marta noto'g'ri parol kiritdingiz.",
            reply_markup=get_back_keyboard()
        )
        return ADMIN_LOGIN

async def admin_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin asosiy menyusi"""
    await update.message.reply_text(
        "Admin paneli. Quyidagi funksiyalardan birini tanlang:",
        reply_markup=get_admin_main_keyboard()
    )
    return ADMIN_MAIN

async def manage_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Narxlarni boshqarish"""
    price_text = "📊 <b>Joriy narxlar</b>\n\n"
    
    for platform, packages in prices.items():
        platform_name = "Telegram" if platform == "telegram" else "Instagram" if platform == "instagram" else "Telegram + Instagram"
        price_text += f"<b>{platform_name}</b>\n"
        
        for package, price in packages.items():
            package_name = "Stories" if package == "stories" else "Post" if package == "post" else "Stories + Post"
            price_text += f"   • {package_name}: {price:,} so'm\n"
        
        price_text += "\n"
    
    price_text += "Narxlarni o'zgartirish uchun yangi formatda yuboring:\n" \
                  "<code>platforma:paket:yangi_narx</code>\n\n" \
                  "Masalan: <code>telegram:stories:55000</code>\n\n" \
                  "Platformalar: telegram, instagram, both\n" \
                  "Paketlar: stories, post, stories_post"
    
    await update.message.reply_text(price_text, parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard())
    return EDIT_PRICES

async def edit_prices(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Narxlarni o'zgartirish"""
    try:
        data = update.message.text.split(":")
        if len(data) != 3:
            raise ValueError("Noto'g'ri format")
        
        platform, package, new_price = data
        new_price = int(new_price)
        
        if platform not in prices or package not in prices[platform]:
            raise ValueError("Noto'g'ri platforma yoki paket")
        
        # Narxni yangilash
        prices[platform][package] = new_price
        
        await update.message.reply_text(
            f"✅ Narx muvaffaqiyatli yangilandi: {platform}:{package} = {new_price:,} so'm",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN
        
    except ValueError as e:
        await update.message.reply_text(
            f"❌ Xato: {e}\n\nIltimos, to'g'ri formatda kiriting: <code>platforma:paket:yangi_narx</code>",
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_keyboard()
        )
        return EDIT_PRICES

async def view_orders(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyurtmalarni ko'rish"""
    orders = get_all_orders()
    
    if not orders:
        await update.message.reply_text(
            "Hozircha buyurtmalar mavjud emas.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN
    
    orders_text = "📜 <b>Barcha buyurtmalar</b>\n\n"
    
    for order in orders[:10]:  # Faqat oxirgi 10 ta buyurtma
        order_id, user_id, customer_name, phone, platform, package, comment, status, created_at, username = order
        
        # Platforma nomini formatlash
        if platform == "telegram":
            platform_name = "Telegram"
        elif platform == "instagram":
            platform_name = "Instagram"
        else:
            platform_name = "Telegram + Instagram"
        
        # Paket nomini formatlash
        if package == "stories":
            package_name = "Stories"
        elif package == "post":
            package_name = "Post"
        else:
            package_name = "Stories + Post"
        
        # Statusni formatlash
        status_icon = "✅" if status == "confirmed" else "❌" if status == "rejected" else "⏳"
        
        orders_text += (
            f"🆔 <b>Buyurtma #{order_id}</b> {status_icon}\n"
            f"👤 <b>Mijoz:</b> {customer_name}\n"
            f"📞 <b>Telefon:</b> {phone}\n"
            f"📱 <b>Platforma:</b> {platform_name}\n"
            f"📦 <b>Paket:</b> {package_name}\n"
            f"💬 <b>Izoh:</b> {comment}\n"
            f"👤 <b>Foydalanuvchi:</b> @{username if username else 'Noma lum'} (ID: {user_id})\n"
            f"📅 <b>Sana:</b> {created_at}\n\n"
        )
    
    if len(orders) > 10:
        orders_text += f"...va yana {len(orders) - 10} ta buyurtma\n\n"
    
    orders_text += "Buyurtma ID sini kiriting ko'proq ma'lumot olish uchun yoki 'barcha' deb yozing hammasini ko'rish uchun:"
    
    await update.message.reply_text(orders_text, parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard())
    return VIEW_ORDERS

async def handle_order_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyurtma so'rovini qayta ishlash"""
    query = update.message.text
    
    if query.lower() == "barcha":
        orders = get_all_orders()
        orders_text = "📜 <b>Barcha buyurtmalar</b>\n\n"
        
        for order in orders:
            order_id, user_id, customer_name, phone, platform, package, comment, status, created_at, username = order
            
            # Platforma nomini formatlash
            if platform == "telegram":
                platform_name = "Telegram"
            elif platform == "instagram":
                platform_name = "Instagram"
            else:
                platform_name = "Telegram + Instagram"
            
            # Paket nomini formatlash
            if package == "stories":
                package_name = "Stories"
            elif package == "post":
                package_name = "Post"
            else:
                package_name = "Stories + Post"
            
            # Statusni formatlash
            status_icon = "✅" if status == "confirmed" else "❌" if status == "rejected" else "⏳"
            
            orders_text += (
                f"🆔 <b>Buyurtma #{order_id}</b> {status_icon}\n"
                f"👤 <b>Mijoz:</b> {customer_name}\n"
                f"📞 <b>Telefon:</b> {phone}\n"
                f"📱 <b>Platforma:</b> {platform_name}\n"
                f"📦 <b>Paket:</b> {package_name}\n"
                f"💬 <b>Izoh:</b> {comment}\n"
                f"👤 <b>Foydalanuvchi:</b> @{username if username else 'Noma lum'} (ID: {user_id})\n"
                f"📅 <b>Sana:</b> {created_at}\n\n"
            )
        
        # Xabarni qismlarga bo'lish (Telegram xabar chegarasi uchun)
        if len(orders_text) > 4000:
            for i in range(0, len(orders_text), 4000):
                await update.message.reply_text(orders_text[i:i+4000], parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(orders_text, parse_mode=ParseMode.HTML)
        
        await update.message.reply_text(
            "Buyurtma ID sini kiriting statusini o'zgartirish uchun:",
            reply_markup=get_back_keyboard()
        )
        return VIEW_ORDERS
    
    try:
        order_id = int(query)
        orders = get_all_orders()
        order = next((o for o in orders if o[0] == order_id), None)
        
        if not order:
            await update.message.reply_text(
                "❌ Buyurtma topilmadi.",
                reply_markup=get_back_keyboard()
            )
            return VIEW_ORDERS
        
        order_id, user_id, customer_name, phone, platform, package, comment, status, created_at, username = order
        
        # Platforma nomini formatlash
        if platform == "telegram":
            platform_name = "Telegram"
        elif platform == "instagram":
            platform_name = "Instagram"
        else:
            platform_name = "Telegram + Instagram"
        
        # Paket nomini formatlash
        if package == "stories":
            package_name = "Stories"
        elif package == "post":
            package_name = "Post"
        else:
            package_name = "Stories + Post"
        
        # Statusni formatlash
        status_icon = "✅" if status == "confirmed" else "❌" if status == "rejected" else "⏳"
        status_text = "Tasdiqlangan" if status == "confirmed" else "Rad etilgan" if status == "rejected" else "Kutilmoqda"
        
        order_text = (
            f"🆔 <b>Buyurtma #{order_id}</b> {status_icon} ({status_text})\n"
            f"👤 <b>Mijoz:</b> {customer_name}\n"
            f"📞 <b>Telefon:</b> {phone}\n"
            f"📱 <b>Platforma:</b> {platform_name}\n"
            f"📦 <b>Paket:</b> {package_name}\n"
            f"💬 <b>Izoh:</b> {comment}\n"
            f"👤 <b>Foydalanuvchi:</b> @{username if username else 'Noma lum'} (ID: {user_id})\n"
            f"📅 <b>Sana:</b> {created_at}\n\n"
            "Statusni o'zgartirish uchun quyidagilardan birini tanlang:"
        )
        
        await update.message.reply_text(
            order_text,
            parse_mode=ParseMode.HTML,
            reply_markup=ReplyKeyboardMarkup([
                ["✅ Tasdiqlash", "❌ Rad etish"],
                ["🔙 Orqaga"]
            ], resize_keyboard=True)
        )
        
        context.user_data['current_order_id'] = order_id
        return CONFIRM_ORDER
        
    except ValueError:
        await update.message.reply_text(
            "❌ Noto'g'ri format. Iltimos, buyurtma ID sini kiriting yoki 'barcha' deb yozing.",
            reply_markup=get_back_keyboard()
        )
        return VIEW_ORDERS

async def change_order_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Buyurtma statusini o'zgartirish"""
    order_id = context.user_data.get('current_order_id')
    action = update.message.text
    
    if not order_id:
        await update.message.reply_text(
            "❌ Xatolik: Buyurtma topilmadi.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN
    
    if action == "✅ Tasdiqlash":
        new_status = "confirmed"
        status_text = "tasdiqlandi"
    elif action == "❌ Rad etish":
        new_status = "rejected"
        status_text = "rad etildi"
    else:
        await update.message.reply_text(
            "❌ Noto'g'ri amal.",
            reply_markup=get_back_keyboard()
        )
        return VIEW_ORDERS
    
    # Buyurtma statusini yangilash
    update_order_status(order_id, new_status)
    
    await update.message.reply_text(
        f"✅ Buyurtma #{order_id} muvaffaqiyatli {status_text}.",
        reply_markup=get_admin_main_keyboard()
    )
    return ADMIN_MAIN

async def view_messages(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xabarlarni ko'rish"""
    messages = get_all_messages()
    
    if not messages:
        await update.message.reply_text(
            "Hozircha xabarlar mavjud emas.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN
    
    messages_text = "💬 <b>Barcha xabarlar</b>\n\n"
    
    for msg in messages[:10]:  # Faqat oxirgi 10 ta xabar
        msg_id, user_id, message_text, admin_response, created_at, username = msg
        
        messages_text += (
            f"🆔 <b>Xabar #{msg_id}</b>\n"
            f"👤 <b>Foydalanuvchi:</b> @{username if username else 'Noma lum'} (ID: {user_id})\n"
            f"💬 <b>Xabar:</b> {message_text[:100]}{'...' if len(message_text) > 100 else ''}\n"
            f"📅 <b>Sana:</b> {created_at}\n\n"
        )
    
    if len(messages) > 10:
        messages_text += f"...va yana {len(messages) - 10} ta xabar\n\n"
    
    messages_text += "Xabar ID sini kiriting javob berish uchun yoki 'barcha' deb yozing hammasini ko'rish uchun:"
    
    await update.message.reply_text(messages_text, parse_mode=ParseMode.HTML, reply_markup=get_back_keyboard())
    return VIEW_MESSAGES

async def handle_message_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xabar so'rovini qayta ishlash"""
    query = update.message.text
    
    if query.lower() == "barcha":
        messages = get_all_messages()
        messages_text = "💬 <b>Barcha xabarlar</b>\n\n"
        
        for msg in messages:
            msg_id, user_id, message_text, admin_response, created_at, username = msg
            
            messages_text += (
                f"🆔 <b>Xabar #{msg_id}</b>\n"
                f"👤 <b>Foydalanuvchi:</b> @{username if username else 'Noma lum'} (ID: {user_id})\n"
                f"💬 <b>Xabar:</b> {message_text}\n"
                f"📅 <b>Sana:</b> {created_at}\n"
            )
            
            if admin_response:
                messages_text += f"👤 <b>Admin javobi:</b> {admin_response}\n"
            
            messages_text += "\n"
        
        # Xabarni qismlarga bo'lish (Telegram xabar chegarasi uchun)
        if len(messages_text) > 4000:
            for i in range(0, len(messages_text), 4000):
                await update.message.reply_text(messages_text[i:i+4000], parse_mode=ParseMode.HTML)
        else:
            await update.message.reply_text(messages_text, parse_mode=ParseMode.HTML)
        
        await update.message.reply_text(
            "Xabar ID sini kiriting javob berish uchun:",
            reply_markup=get_back_keyboard()
        )
        return VIEW_MESSAGES
    
    try:
        message_id = int(query)
        messages = get_all_messages()
        message = next((m for m in messages if m[0] == message_id), None)
        
        if not message:
            await update.message.reply_text(
                "❌ Xabar topilmadi.",
            )
            return VIEW_MESSAGES
        
        msg_id, user_id, message_text, admin_response, created_at, username = message
        
        message_text_display = (
            f"🆔 <b>Xabar #{msg_id}</b>\n"
            f"👤 <b>Foydalanuvchi:</b> @{username if username else 'Noma lum'} (ID: {user_id})\n"
            f"💬 <b>Xabar:</b> {message_text}\n"
            f"📅 <b>Sana:</b> {created_at}\n"
        )
        
        if admin_response:
            message_text_display += f"👤 <b>Admin javobi:</b> {admin_response}\n"
        
        message_text_display += "\nJavobingizni yozing:"
        
        await update.message.reply_text(
            message_text_display,
            parse_mode=ParseMode.HTML,
            reply_markup=get_back_keyboard()
        )
        
        context.user_data['current_message_id'] = msg_id
        context.user_data['current_user_id'] = user_id
        return RESPOND_TO_MESSAGE
        
    except ValueError:
        await update.message.reply_text(
            "❌ Noto'g'ri format. Iltimos, xabar ID sini kiriting yoki 'barcha' deb yozing.",
            reply_markup=get_back_keyboard()
        )
        return VIEW_MESSAGES

async def respond_to_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Xabarga javob berish"""
    response = update.message.text
    message_id = context.user_data.get('current_message_id')
    user_id = context.user_data.get('current_user_id')
    
    if not message_id or not user_id:
        await update.message.reply_text(
            "❌ Xatolik: Xabar ma'lumotlari topilmadi.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN
    
    # Xabarga javobni saqlash
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        'UPDATE messages SET admin_response = ? WHERE id = ?',
        (response, message_id)
    )
    conn.commit()
    conn.close()
    
    # Foydalanuvchiga javob yuborish
    try:
        await context.bot.send_message(
            chat_id=user_id,
            text=f"👤 <b>Admin javobi:</b>\n{response}",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Foydalanuvchiga javob yuborishda xatolik: {e}")
    
    await update.message.reply_text(
        "✅ Javobingiz yuborildi.",
        reply_markup=get_admin_main_keyboard()
    )
    return ADMIN_MAIN

async def admin_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Admin kirish tarixini ko'rish"""
    history = get_admin_history()
    
    if not history:
        await update.message.reply_text(
            "Hozircha kirish tarixi mavjud emas.",
            reply_markup=get_admin_main_keyboard()
        )
        return ADMIN_MAIN
    
    history_text = "🔔 <b>Admin kirish tarixi</b>\n\n"
    
    for entry in history[:15]:  # Faqat oxirgi 15 ta kirish
        entry_id, user_id, success, attempted_password, created_at, username = entry
        
        status = "✅ Muvaffaqiyatli" if success else "❌ Muvaffaqiyatsiz"
        
        history_text += (
            f"👤 <b>Foydalanuvchi:</b> @{username if username else 'Noma lum'} (ID: {user_id})\n"
            f"📊 <b>Status:</b> {status}\n"
            f"🔐 <b>Parol:</b> {attempted_password}\n"
            f"📅 <b>Sana:</b> {created_at}\n\n"
        )
    
    if len(history) > 15:
        history_text += f"...va yana {len(history) - 15} ta kirish\n\n"
    
    await update.message.reply_text(history_text, parse_mode=ParseMode.HTML, reply_markup=get_admin_main_keyboard())
    return ADMIN_MAIN

async def change_password(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parolni o'zgartirish"""
    global DEFAULT_PASSWORD
    
    await update.message.reply_text(
        "Yangi parolni kiriting:",
        reply_markup=get_back_keyboard()
    )
    return CHANGE_PASSWORD

async def handle_password_change(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Parolni o'zgartirishni qayta ishlash"""
    global DEFAULT_PASSWORD
    new_password = update.message.text
    
    # Yangi parolni saqlash
    DEFAULT_PASSWORD = new_password
    
    await update.message.reply_text(
        "✅ Parol muvaffaqiyatli o'zgartirildi.",
        reply_markup=get_admin_main_keyboard()
    )
    return ADMIN_MAIN

async def handle_callback_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Callback querylarni qayta ishlash"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data.startswith("confirm_") or data.startswith("reject_"):
        # Buyurtma statusini o'zgartirish
        order_id = int(data.split("_")[1])
        new_status = "confirmed" if data.startswith("confirm_") else "rejected"
        
        # Buyurtma statusini yangilash
        update_order_status(order_id, new_status)
        
        # Tugmalarni olib tashlash
        await query.edit_message_reply_markup(reply_markup=None)
        
        # Xabarni yangilash
        status_text = "tasdiqlandi" if new_status == "confirmed" else "rad etildi"
        await query.edit_message_text(
            text=query.message.text + f"\n\n✅ Buyurtma statusi {status_text}.",
            parse_mode=ParseMode.HTML
        )

# === ASOSIY DASTUR ===
def main():
    """Asosiy dastur"""
    # Ma'lumotlar bazasini ishga tushirish
    init_db()
    
    # Botni yaratish
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Conversation handler
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CommandHandler('admin', admin_command)],
        states={
            SELECTING_ACTION: [
                MessageHandler(filters.Regex("^👤 Admin bilan bog'lanish$"), admin_contact),
                MessageHandler(filters.Regex("^📊 Reklama narxlari$"), show_prices),
                MessageHandler(filters.Regex("^🌐 Ijtimoiy tarmoqlar$"), social_media),
                MessageHandler(filters.Regex("^🛒 Reklama sotib olish$"), start_order),
                MessageHandler(filters.Regex("^🔙 Asosiy menyu$"), main_menu),
            ],
            TYPING_MESSAGE: [
                MessageHandler(filters.Regex("^🔙 Orqaga$"), admin_contact),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_message),
            ],
            ORDER_NAME: [
                MessageHandler(filters.Regex("^🔙 Orqaga$"), main_menu),
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_name),
            ],
            ORDER_PHONE: [
                MessageHandler(filters.Regex("^🔙 Orqaga$"), start_order),
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_phone),
            ],
            ORDER_PLATFORM: [
                MessageHandler(filters.Regex("^🔙 Orqaga$"), order_name),
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_platform),
            ],
            ORDER_PACKAGE: [
                MessageHandler(filters.Regex("^🔙 Orqaga$"), order_platform),
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_package),
            ],
            ORDER_COMMENT: [
                MessageHandler(filters.Regex("^🔙 Orqaga$"), order_package),
                MessageHandler(filters.TEXT & ~filters.COMMAND, order_comment),
            ],
            CONFIRM_ORDER: [
                MessageHandler(filters.Regex("^(✅ Tasdiqlash|❌ Bekor qilish)$"), confirm_order),
            ],
            ADMIN_LOGIN: [
                MessageHandler(filters.Regex("^🔙 Orqaga$"), main_menu),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_admin_login),
            ],
            ADMIN_MAIN: [
                MessageHandler(filters.Regex("^📊 Narxlarni boshqarish$"), manage_prices),
                MessageHandler(filters.Regex("^📜 Buyurtmalarni ko'rish$"), view_orders),
                MessageHandler(filters.Regex("^💬 Xabarlarga javob berish$"), view_messages),
                MessageHandler(filters.Regex("^🔔 Kirish tarixi$"), admin_history),
                MessageHandler(filters.Regex("^🔑 Parolni o'zgartirish$"), change_password),
                MessageHandler(filters.Regex("^🔙 Asosiy menyu$"), main_menu),
            ],
            EDIT_PRICES: [
                MessageHandler(filters.Regex("^🔙 Orqaga$"), admin_main_menu),
                MessageHandler(filters.TEXT & ~filters.COMMAND, edit_prices),
            ],
            VIEW_ORDERS: [
                MessageHandler(filters.Regex("^🔙 Orqaga$"), admin_main_menu),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_order_query),
            ],
            VIEW_MESSAGES: [
                MessageHandler(filters.Regex("^🔙 Orqaga$"), admin_main_menu),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message_query),
            ],
            ADMIN_HISTORY: [
                MessageHandler(filters.Regex("^🔙 Orqaga$"), admin_main_menu),
            ],
            CHANGE_PASSWORD: [
                MessageHandler(filters.Regex("^🔙 Orqaga$"), admin_main_menu),
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password_change),
            ],
            RESPOND_TO_MESSAGE: [
                MessageHandler(filters.Regex("^🔙 Orqaga$"), view_messages),
                MessageHandler(filters.TEXT & ~filters.COMMAND, respond_to_message),
            ],
        },
        fallbacks=[CommandHandler('start', start), CommandHandler('admin', admin_command)],
    )
    
    # Handlerlarni qo'shish
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(handle_callback_query))
    
    # Botni ishga tushirish
    application.run_polling()

if __name__ == '__main__':
    main()