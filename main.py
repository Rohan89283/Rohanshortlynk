import os
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler
from instagram_checker import check_instagram_cookie
from io import BytesIO

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    await update.message.reply_text(
        "👋 Welcome to Instagram Cookie Checker!\n\n"
        "Send me your Instagram cookie to check if it's valid.\n\n"
        "Format: Just paste your cookie string"
    )

async def handle_cookie(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle cookie input"""
    user_id = update.effective_user.id
    cookie_string = update.message.text.strip()

    if not cookie_string or len(cookie_string) < 50:
        await update.message.reply_text("❌ Invalid cookie format. Please send a valid cookie string.")
        return

    status_message = await update.message.reply_text("🔄 Checking cookie...")

    async def update_status(step, message):
        try:
            await status_message.edit_text(f"🔄 Step {step}: {message}")
        except:
            pass

    result = await check_instagram_cookie(
        cookie_string=cookie_string,
        user_id=user_id,
        update_callback=update_status
    )

    if result['valid']:
        response = (
            f"✅ Cookie is VALID!\n\n"
            f"👤 Username: {result.get('username', 'N/A')}\n"
            f"🌐 URL: {result.get('url', 'N/A')}"
        )
    else:
        response = f"❌ Cookie is INVALID\n\n{result['message']}"

    await status_message.edit_text(response)

    if result['screenshot']:
        screenshot_bio = BytesIO(result['screenshot'])
        screenshot_bio.seek(0)
        await update.message.reply_photo(
            photo=screenshot_bio,
            caption="📸 Screenshot"
        )

async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle errors"""
    logger.error(f"Error: {context.error}")
    if update and update.effective_message:
        await update.effective_message.reply_text("❌ An error occurred. Please try again.")

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not set!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_cookie))
    app.add_error_handler(error_handler)

    logger.info("Bot started!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
