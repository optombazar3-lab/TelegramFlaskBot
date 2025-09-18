import os
import asyncio
import logging
from flask import Flask
from threading import Thread
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, MessageHandler, filters, ContextTypes
from telegram.helpers import escape_markdown
from telegram.constants import ChatMemberStatus

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Suppress verbose loggers to prevent token leakage
logging.getLogger("httpx").setLevel(logging.WARNING)
logging.getLogger("telegram").setLevel(logging.WARNING)

# Configuration from environment variables
BOT_TOKEN = os.getenv('BOT_TOKEN')
CHANNEL_ID = os.getenv('CHANNEL_ID')
CHANNEL_URL = os.getenv('CHANNEL_URL')
WARNING_IMAGE_URL = os.getenv('WARNING_IMAGE_URL')

# User counter (in production, use a database)
user_count = 0

# Search states for users (keyed by (chat_id, user_id) tuple)
user_search_states = {}

class TelegramBot:
    def __init__(self):
        if not BOT_TOKEN:
            raise ValueError("BOT_TOKEN is required")
        self.application = Application.builder().token(BOT_TOKEN).build()
        self.setup_handlers()
    
    def setup_handlers(self):
        """Set up command and callback handlers"""
        self.application.add_handler(CommandHandler("start", self.start))
        self.application.add_handler(CommandHandler("check_subscription", self.check_subscription))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
        self.application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, self.handle_text_message))
    
    async def is_subscribed(self, context, user_id):
        """Check if user is subscribed to the required channel"""
        if not CHANNEL_ID:
            logger.warning("CHANNEL_ID not configured - allowing access for testing")
            return True
            
        try:
            logger.info(f"Checking subscription for user {user_id} in channel {CHANNEL_ID}")
            member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
            logger.info(f"User {user_id} status in channel: {member.status}")
            is_member = member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
            logger.info(f"User {user_id} subscription check result: {is_member}")
            return is_member
        except Exception as e:
            logger.error(f"Error checking subscription for user {user_id} in channel {CHANNEL_ID}: {e}")
            logger.error(f"Error type: {type(e).__name__}")
            # For development/testing, return False so users see the subscription prompt
            # In production with proper setup, this should return False
            return False
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if not update.effective_user or not update.message:
            return
            
        global user_count
        user_id = update.effective_user.id
        user_name = update.effective_user.first_name or "Foydalanuvchi"
        user_count += 1
        
        # Welcome message with user name and number
        welcome_text = (
            f"👋 Salom, **{user_name}** botimizga xush kelibsiz! "
            f"Siz botdagi **{user_count}**-foydalanuvchi bo'ldingiz. "
            f"💬 Bu bot orqali foydalanuvchi, guruh va kanallarning ID'sini olish imkoniyatiga ega bo'lasiz. "
            f"⭐ Botga start tugmasini bosib, ish faoliyatini boshlang."
        )
        
        await update.message.reply_text(welcome_text, parse_mode='Markdown')
        
        # Check subscription
        if await self.is_subscribed(context, user_id):
            await self.show_subscribed_message(update)
        else:
            await self.show_subscription_required(update)
    
    async def show_subscription_required(self, update):
        """Show subscription required message with inline buttons"""
        if not update.message:
            return
            
        text = "⚠️ Botdan foydalanish uchun quyidagi kanalga obuna bo'ling."
        
        # Create subscription button URL
        subscribe_url = None
        
        # Priority 1: Use CHANNEL_URL if provided
        if CHANNEL_URL:
            if CHANNEL_URL.startswith('https://') or CHANNEL_URL.startswith('http://'):
                subscribe_url = CHANNEL_URL
            elif CHANNEL_URL.startswith('@'):
                subscribe_url = f"https://t.me/{CHANNEL_URL[1:]}"
        
        # Priority 2: Derive URL from CHANNEL_ID if it starts with @
        elif CHANNEL_ID and CHANNEL_ID.startswith('@'):
            subscribe_url = f"https://t.me/{CHANNEL_ID[1:]}"
        
        # Priority 3: Show channel ID in message for numeric IDs
        elif CHANNEL_ID:
            text += f"\n\n🆔 Kanal ID: `{CHANNEL_ID}`\n📝 Admin bilan bog'laning yoki kanalning public username'ini so'rang."
        
        # Create keyboard
        keyboard = []
        if subscribe_url:
            keyboard.append([InlineKeyboardButton("✅ Obuna bo'lish", url=subscribe_url)])
        
        keyboard.append([InlineKeyboardButton("🔄 Tekshirish", callback_data="check_subscription")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        try:
            if WARNING_IMAGE_URL and WARNING_IMAGE_URL != "https://example.com/warning.png":
                await update.message.reply_photo(
                    photo=WARNING_IMAGE_URL,
                    caption=text,
                    reply_markup=reply_markup,
                    parse_mode='Markdown'
                )
            else:
                await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        except Exception as e:
            logger.error(f"Error sending subscription message: {e}")
            # Fallback to simple text message
            await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    
    async def show_subscribed_message(self, update):
        """Show message for subscribed users with search options only"""
        if not update.message:
            return
            
        text = "✅ Obuna bo'lingan! Siz botdan foydalanishingiz mumkin.\n\n🔍 Qidirish turini tanlang:"
        
        keyboard = [
            [InlineKeyboardButton("👤 Foydalanuvchi qidirish", callback_data="search_user")],
            [InlineKeyboardButton("📺 Kanal qidirish", callback_data="search_channel")],
            [InlineKeyboardButton("👥 Guruh qidirish", callback_data="search_group")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def check_subscription(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /check_subscription command"""
        if not update.effective_user:
            return
            
        user_id = update.effective_user.id
        
        if await self.is_subscribed(context, user_id):
            await self.show_subscribed_message(update)
        else:
            await self.show_subscription_required(update)
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        if not update.callback_query or not update.callback_query.from_user:
            return
            
        query = update.callback_query
        user_id = query.from_user.id
        
        try:
            if query.data == "check_subscription":
                if await self.is_subscribed(context, user_id):
                    text = "✅ Obuna bo'lingan! Siz botdan foydalanishingiz mumkin.\n\n🔍 Qidirish turini tanlang:"
                    keyboard = [
                        [InlineKeyboardButton("👤 Foydalanuvchi qidirish", callback_data="search_user")],
                        [InlineKeyboardButton("📺 Kanal qidirish", callback_data="search_channel")],
                        [InlineKeyboardButton("👥 Guruh qidirish", callback_data="search_group")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    
                    # Try to edit message, if it fails, send new message
                    try:
                        await query.edit_message_text(text, reply_markup=reply_markup)
                    except:
                        # If editing fails (maybe it was a photo message), delete and send new
                        if query.message:
                            try:
                                await query.message.delete()
                            except:
                                pass
                            await context.bot.send_message(
                                chat_id=query.message.chat_id,
                                text=text,
                                reply_markup=reply_markup
                            )
                else:
                    await query.answer("❌ Siz hali kanalga obuna bo'lmagansiz. Iltimos, avval kanalga obuna bo'ling.", show_alert=True)
                    
            elif query.data == "search_user":
                if await self.is_subscribed(context, user_id):
                    chat_id = query.message.chat.id if query.message else None
                    user_search_states[(chat_id, user_id)] = "waiting_user_search"
                    text = "👤 **Foydalanuvchi qidirish**\n\nFoydalanuvchi username'ini kiriting (masalan: @username yoki username):"
                    if query.message:
                        await query.edit_message_text(text, parse_mode='Markdown')
                else:
                    await query.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
                    
            elif query.data == "search_channel":
                if await self.is_subscribed(context, user_id):
                    chat_id = query.message.chat.id if query.message else None
                    user_search_states[(chat_id, user_id)] = "waiting_channel_search"
                    text = "🔍 **Kanal qidirish**\n\nKanal username'ini kiriting (masalan: @channelname yoki channelname):"
                    if query.message:
                        await query.edit_message_text(text, parse_mode='Markdown')
                else:
                    await query.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
                    
            elif query.data == "search_group":
                if await self.is_subscribed(context, user_id):
                    chat_id = query.message.chat.id if query.message else None
                    user_search_states[(chat_id, user_id)] = "waiting_group_search"
                    text = "🔍 **Guruh qidirish**\n\nGuruh username'ini kiriting (masalan: @groupname yoki groupname):"
                    if query.message:
                        await query.edit_message_text(text, parse_mode='Markdown')
                else:
                    await query.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
                    
            elif query.data == "search_back":
                if await self.is_subscribed(context, user_id):
                    chat_id = query.message.chat.id if query.message else None
                    user_search_states.pop((chat_id, user_id), None)
                    text = "✅ Obuna bo'lingan! Siz botdan foydalanishingiz mumkin.\n\n🔍 Qidirish turini tanlang:"
                    keyboard = [
                        [InlineKeyboardButton("👤 Foydalanuvchi qidirish", callback_data="search_user")],
                        [InlineKeyboardButton("📺 Kanal qidirish", callback_data="search_channel")],
                        [InlineKeyboardButton("👥 Guruh qidirish", callback_data="search_group")]
                    ]
                    reply_markup = InlineKeyboardMarkup(keyboard)
                    if query.message:
                        await query.edit_message_text(text, reply_markup=reply_markup)
                else:
                    await query.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
            
            await query.answer()
            
        except Exception as e:
            logger.error(f"Error in button handler: {e}")
            await query.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
    
    
    async def handle_text_message(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle text messages for search functionality"""
        if not update.effective_user or not update.message:
            return
            
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id if update.effective_chat else None
        text = update.message.text
        
        # Skip if we don't have a valid chat_id
        if not chat_id:
            return
        
        # Check if user is subscribed before processing search
        if not await self.is_subscribed(context, user_id):
            return
        
        # Check if user is in a search state
        if (chat_id, user_id) in user_search_states:
            search_state = user_search_states[(chat_id, user_id)]
            
            if search_state == "waiting_user_search":
                await self.search_user(update, context, text)
            elif search_state == "waiting_channel_search":
                await self.search_channel(update, context, text)
            elif search_state == "waiting_group_search":
                await self.search_group(update, context, text)
                
    async def search_user(self, update, context, username):
        """Search for user by username"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Clean the username
        if username.startswith('@'):
            username = username[1:]
        
        try:
            # Try to get user info by searching for them
            # Note: Telegram Bot API doesn't allow searching for users directly by username
            # We can only get user info if we have their ID or if they interact with the bot
            # So we'll provide a helpful message about this limitation
            
            # Clear search state
            user_search_states.pop((chat_id, user_id), None)
            
            # Inform user about the limitation
            clean_username = escape_markdown(username, version=2)
            text = f"⚠️ **Foydalanuvchi qidirish cheklovi**\n\n"
            text += f"Afsuski, Telegram Bot API orqali @{clean_username} foydalanuvchisini username bo\'yicha qidirish mumkin emas\.\n\n"
            text += f"**Foydalanuvchi ID\-sini olish usullari:**\n"
            text += f"• Foydalanuvchi botga yozishi va /start bosishi kerak\n"
            text += f"• Yoki foydalanuvchini guruhlarda mention qilib, bot orqali ID\-sini olish mumkin\n\n"
            text += f"**Maslahat:** Kanal yoki guruh qidirish funksiyasidan foydalaning\!"
            
        except Exception as e:
            logger.error(f"Error in user search: {e}")
            user_search_states.pop((chat_id, user_id), None)
            clean_username = escape_markdown(username, version=2)
            text = f"❌ **Xatolik yuz berdi\!**\n\n@{clean_username} foydalanuvchisini qidirishda xatolik yuz berdi\."
            
        keyboard = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="search_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='MarkdownV2')
    
    async def search_channel(self, update, context, channel_name):
        """Search for channel by username"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Clean the channel name
        if channel_name.startswith('@'):
            channel_name = channel_name[1:]
        
        try:
            # Try to get channel info
            channel = await context.bot.get_chat(f"@{channel_name}")
            
            # Clear search state only on success
            user_search_states.pop((chat_id, user_id), None)
            
            # Use proper Markdown escaping
            title = escape_markdown(channel.title, version=2) if channel.title else "N/A"
            username = escape_markdown(channel.username, version=2) if channel.username else "N/A"
            channel_id = escape_markdown(str(channel.id), version=2)
            channel_type = escape_markdown(channel.type, version=2)
            
            text = f"✅ **Kanal topildi\!**\n\n"
            text += f"📺 **Nomi:** {title}\n"
            text += f"🆔 **Username:** @{username}\n" if channel.username else ""
            text += f"🆔 **ID:** `{channel_id}`\n"
            text += f"👥 **Turi:** {channel_type}\n"
            
            if channel.description:
                desc = escape_markdown(channel.description[:100], version=2)
                text += f"📝 **Tavsif:** {desc}\.\.\."
            
        except Exception as e:
            logger.error(f"Error searching channel @{channel_name}: {e}")
            clean_channel_name = escape_markdown(channel_name, version=2)
            text = f"❌ **Kanal topilmadi\!**\n\n@{clean_channel_name} kanal topilmadi yoki bot unga kirish huquqiga ega emas\.\n\n💡 **Maslahatlar:**\n\u2022 Kanal username'i to'g'ri yozilganligini tekshiring\n\u2022 Kanal ochiq \(public\) bo'lishi kerak\n\u2022 Kanal mavjudligini tekshiring"
            
        keyboard = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="search_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='MarkdownV2')
    
    async def search_group(self, update, context, group_name):
        """Search for group by username"""
        user_id = update.effective_user.id
        chat_id = update.effective_chat.id
        
        # Clean the group name
        if group_name.startswith('@'):
            group_name = group_name[1:]
        
        try:
            # Try to get group info
            group = await context.bot.get_chat(f"@{group_name}")
            
            # Clear search state only on success
            user_search_states.pop((chat_id, user_id), None)
            
            # Use proper Markdown escaping
            title = escape_markdown(group.title, version=2) if group.title else "N/A"
            username = escape_markdown(group.username, version=2) if group.username else "N/A"
            group_id = escape_markdown(str(group.id), version=2)
            group_type = escape_markdown(group.type, version=2)
            
            text = f"✅ **Guruh topildi\!**\n\n"
            text += f"👥 **Nomi:** {title}\n"
            text += f"🆔 **Username:** @{username}\n" if group.username else ""
            text += f"🆔 **ID:** `{group_id}`\n"
            text += f"👥 **Turi:** {group_type}\n"
            
            if group.description:
                desc = escape_markdown(group.description[:100], version=2)
                text += f"📝 **Tavsif:** {desc}\.\.\."
            
        except Exception as e:
            logger.error(f"Error searching group @{group_name}: {e}")
            clean_group_name = escape_markdown(group_name, version=2)
            text = f"❌ **Guruh topilmadi\!**\n\n@{clean_group_name} guruh topilmadi yoki bot unga kirish huquqiga ega emas\.\n\n💡 **Maslahatlar:**\n\u2022 Guruh username'i to'g'ri yozilganligini tekshiring\n\u2022 Guruh ochiq \(public\) bo'lishi kerak\n\u2022 Guruh mavjudligini tekshiring"
            
        keyboard = [[InlineKeyboardButton("⬅️ Orqaga", callback_data="search_back")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='MarkdownV2')
    
    def run(self):
        """Run the bot using polling"""
        self.application.run_polling()

# Flask app for Render.com deployment
app = Flask(__name__)

@app.route('/')
def health_check():
    """Health check endpoint"""
    return "Bot is running", 200

@app.route('/health')
def health():
    """Health check endpoint"""
    return "OK", 200

def run_flask():
    """Run Flask server"""
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)

def run_bot():
    """Run Telegram bot"""
    bot = TelegramBot()
    bot.run()

if __name__ == '__main__':
    # Check if required environment variables are set
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN environment variable is not set")
        exit(1)
    
    if not CHANNEL_ID:
        logger.warning("CHANNEL_ID environment variable is not set - bot will allow all users for testing")
    
    logger.info("Starting Telegram bot and Flask server...")
    
    # Start Flask server in a separate thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Run bot in main thread
    run_bot()