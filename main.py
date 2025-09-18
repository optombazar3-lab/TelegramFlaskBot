import os
import asyncio
import logging
from flask import Flask
from threading import Thread
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes
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
    
    async def is_subscribed(self, context, user_id):
        """Check if user is subscribed to the required channel"""
        if not CHANNEL_ID:
            logger.warning("CHANNEL_ID not configured - allowing access for testing")
            return True
            
        try:
            member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
            return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
        except Exception as e:
            logger.error(f"Error checking subscription for channel {CHANNEL_ID}: {e}")
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
        """Show message for subscribed users with inline buttons"""
        if not update.message:
            return
            
        text = "✅ Obuna bo'lingan! Siz botdan foydalanishingiz mumkin."
        
        keyboard = [
            [InlineKeyboardButton("👤 Foydalanuvchi ID", callback_data="get_user_id")],
            [InlineKeyboardButton("👥 Guruh/Kanal ID", callback_data="get_chat_id")],
            [InlineKeyboardButton("📜 Kanal ID", callback_data="get_channel_id")]
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
                    text = "✅ Obuna bo'lingan! Siz botdan foydalanishingiz mumkin."
                    keyboard = [
                        [InlineKeyboardButton("👤 Foydalanuvchi ID", callback_data="get_user_id")],
                        [InlineKeyboardButton("👥 Guruh/Kanal ID", callback_data="get_chat_id")],
                        [InlineKeyboardButton("📜 Kanal ID", callback_data="get_channel_id")]
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
                    
            elif query.data == "get_user_id":
                if await self.is_subscribed(context, user_id):
                    text = f"Foydalanuvchi ID: `{user_id}`"
                    if query.message:
                        await context.bot.send_message(
                            chat_id=query.message.chat_id,
                            text=text,
                            parse_mode='Markdown'
                        )
                else:
                    await query.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
                    
            elif query.data == "get_chat_id":
                if await self.is_subscribed(context, user_id):
                    chat_id = update.effective_chat.id if update.effective_chat else "N/A"
                    text = f"Guruh/Kanal ID: `{chat_id}`"
                    if query.message:
                        await context.bot.send_message(
                            chat_id=query.message.chat_id,
                            text=text,
                            parse_mode='Markdown'
                        )
                else:
                    await query.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
                    
            elif query.data == "get_channel_id":
                if await self.is_subscribed(context, user_id):
                    # Show current chat ID if it's a channel/group, or required channel ID if private
                    chat_id = update.effective_chat.id if update.effective_chat else None
                    if chat_id and chat_id < 0:  # Group or channel
                        text = f"Kanal ID: `{chat_id}`"
                    else:  # Private chat
                        text = f"Kanal ID: `{CHANNEL_ID or 'Sozlanmagan'}`"
                    
                    if query.message:
                        await context.bot.send_message(
                            chat_id=query.message.chat_id,
                            text=text,
                            parse_mode='Markdown'
                        )
                else:
                    await query.answer("❌ Avval kanalga obuna bo'ling!", show_alert=True)
            
            await query.answer()
            
        except Exception as e:
            logger.error(f"Error in button handler: {e}")
            await query.answer("❌ Xatolik yuz berdi. Qaytadan urinib ko'ring.")
    
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