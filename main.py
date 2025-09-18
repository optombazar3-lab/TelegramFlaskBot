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
CHANNEL_URL = os.getenv('CHANNEL_URL')  # Public channel URL for subscription button
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
        self.application.add_handler(CommandHandler("user_id", self.user_id))
        self.application.add_handler(CommandHandler("chat_id", self.chat_id))
        self.application.add_handler(CommandHandler("channel_id", self.channel_id))
        self.application.add_handler(CallbackQueryHandler(self.button_handler))
    
    async def is_subscribed(self, context, user_id):
        """Check if user is subscribed to the required channel"""
        try:
            member = await context.bot.get_chat_member(CHANNEL_ID, user_id)
            return member.status in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]
        except Exception as e:
            logger.error(f"Error checking subscription: {e}")
            return False
    
    async def start(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /start command"""
        if not update.effective_user or not update.message:
            return
            
        global user_count
        user_id = update.effective_user.id
        user_count += 1
        
        # Welcome message
        welcome_text = (
            f"👋 Salom, botimizga xush kelibsiz! Siz botdagi {user_count}-foydalanuvchi bo'ldingiz. "
            f"💬 Bu bot orqali foydalanuvchi, guruh va kanallarning ID'sini olish imkoniyatiga ega bo'lasiz. "
            f"⭐ Botga start tugmasini bosib, ish faoliyatini boshlang."
        )
        
        await update.message.reply_text(welcome_text)
        
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
        
        # Create subscription button only if we have a public channel URL
        keyboard = []
        if CHANNEL_URL:
            keyboard.append([InlineKeyboardButton("✅ Obuna bo'lish", url=CHANNEL_URL)])
        keyboard.append([InlineKeyboardButton("🔄 Tekshirish", callback_data="check_subscription")])
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if WARNING_IMAGE_URL and WARNING_IMAGE_URL != "https://example.com/warning.png":
            await update.message.reply_photo(
                photo=WARNING_IMAGE_URL,
                caption=text,
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(text, reply_markup=reply_markup)
    
    async def show_subscribed_message(self, update):
        """Show message for subscribed users"""
        if not update.message:
            return
            
        text = (
            "✅ Obuna bo'lingan! Siz botdan foydalanishingiz mumkin.\n\n"
            "📋 Mavjud buyruqlar:\n"
            "• /user_id - Foydalanuvchi ID'sini ko'rish\n"
            "• /chat_id - Guruh/Kanal ID'sini ko'rish\n"
            "• /channel_id - Kanal ID'sini ko'rish\n"
            "• /check_subscription - Obuna holatini tekshirish"
        )
        await update.message.reply_text(text)
    
    async def check_subscription(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /check_subscription command"""
        if not update.effective_user:
            return
            
        user_id = update.effective_user.id
        
        if await self.is_subscribed(context, user_id):
            await self.show_subscribed_message(update)
        else:
            await self.show_subscription_required(update)
    
    async def user_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /user_id command"""
        if not update.effective_user or not update.message:
            return
            
        user_id = update.effective_user.id
        
        if not await self.is_subscribed(context, user_id):
            await self.show_subscription_required(update)
            return
        
        text = f"Foydalanuvchi ID: `{user_id}`"
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def chat_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /chat_id command"""
        if not update.effective_user or not update.effective_chat or not update.message:
            return
            
        user_id = update.effective_user.id
        
        if not await self.is_subscribed(context, user_id):
            await self.show_subscription_required(update)
            return
        
        chat_id = update.effective_chat.id
        text = f"Guruh/Kanal ID: `{chat_id}`"
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def channel_id(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle /channel_id command"""
        if not update.effective_user or not update.effective_chat or not update.message:
            return
            
        user_id = update.effective_user.id
        
        if not await self.is_subscribed(context, user_id):
            await self.show_subscription_required(update)
            return
        
        # If used in a channel, show channel ID, otherwise show the required channel ID
        chat_id = update.effective_chat.id
        if chat_id < 0:  # Group or channel
            text = f"Kanal ID: `{chat_id}`"
        else:  # Private chat
            text = f"Kanal ID: `{CHANNEL_ID or 'Not configured'}`"
        
        await update.message.reply_text(text, parse_mode='Markdown')
    
    async def button_handler(self, update: Update, context: ContextTypes.DEFAULT_TYPE):
        """Handle inline button callbacks"""
        if not update.callback_query or not update.callback_query.from_user:
            return
            
        query = update.callback_query
        await query.answer()
        
        if query.data == "check_subscription":
            user_id = query.from_user.id
            
            if await self.is_subscribed(context, user_id):
                text = (
                    "✅ Obuna bo'lingan! Siz botdan foydalanishingiz mumkin.\n\n"
                    "📋 Mavjud buyruqlar:\n"
                    "• /user_id - Foydalanuvchi ID'sini ko'rish\n"
                    "• /chat_id - Guruh/Kanal ID'sini ko'rish\n"
                    "• /channel_id - Kanal ID'sini ko'rish\n"
                    "• /check_subscription - Obuna holatini tekshirish"
                )
                await query.edit_message_text(text)
            else:
                text = "❌ Siz hali kanalga obuna bo'lmagansiz. Iltimos, avval kanalga obuna bo'ling."
                
                # Create subscription button only if we have a public channel URL
                keyboard = []
                if CHANNEL_URL:
                    keyboard.append([InlineKeyboardButton("✅ Obuna bo'lish", url=CHANNEL_URL)])
                keyboard.append([InlineKeyboardButton("🔄 Tekshirish", callback_data="check_subscription")])
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await query.edit_message_text(text, reply_markup=reply_markup)
    
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
        logger.error("CHANNEL_ID environment variable is not set")
        exit(1)
    
    logger.info("Starting Telegram bot and Flask server...")
    
    # Start Flask server in a separate thread
    flask_thread = Thread(target=run_flask, daemon=True)
    flask_thread.start()
    
    # Run bot in main thread
    run_bot()