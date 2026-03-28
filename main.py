import os
import logging
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, ContextTypes
from instagram_checker import check_instagram_cookie
from io import BytesIO

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Hello! I'm your bot.\n\n"
        "Use /cmds to see all available commands\n"
        "Use /help to learn how to use each command"
    )

async def cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    commands_list = (
        "📋 *Available Commands:*\n\n"
        "/start - Start the bot and see welcome message\n"
        "/cmds - Show all available commands\n"
        "/help - Get detailed help for each command\n"
        "/ig [cookies] - Check Instagram cookie validity\n"
    )
    await update.message.reply_text(commands_list, parse_mode='Markdown')

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    help_text = (
        "📖 *How to Use Each Command:*\n\n"
        "**/start**\n"
        "Simply type /start to initialize the bot and see the welcome message.\n\n"
        "**/cmds**\n"
        "Type /cmds to get a quick list of all available commands and their basic descriptions.\n\n"
        "**/help**\n"
        "Type /help (this command) to get detailed instructions on how to use each command.\n\n"
        "**/ig [cookies]**\n"
        "Check if Instagram cookies are valid. Usage:\n"
        "`/ig datr=xxx; sessionid=yyy; csrftoken=zzz`\n"
        "The bot will test the cookies and send you a screenshot.\n\n"
        "More commands coming soon!"
    )
    await update.message.reply_text(help_text, parse_mode='Markdown')

async def ig_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Check Instagram cookie validity"""
    if not context.args:
        await update.message.reply_text(
            "❌ Please provide cookies!\n\n"
            "Usage: `/ig datr=xxx; sessionid=yyy; csrftoken=zzz`\n\n"
            "Example:\n"
            "`/ig datr=abc123; sessionid=xyz789; csrftoken=token123`",
            parse_mode='Markdown'
        )
        return

    # Join all arguments as cookie string
    cookie_string = ' '.join(context.args)

    # Send processing message
    status_msg = await update.message.reply_text(
        "🔄 Checking Instagram cookies...\n"
        "This may take 10-15 seconds..."
    )

    try:
        # Check the cookie
        result = check_instagram_cookie(cookie_string)

        # Update status message
        if result['valid']:
            status_text = f"✅ {result['message']}\n\nURL: {result['url']}"
        else:
            status_text = f"❌ {result['message']}\n\nURL: {result.get('url', 'N/A')}"

        await status_msg.edit_text(status_text)

        # Send screenshot if available
        if result['screenshot']:
            await update.message.reply_photo(
                photo=BytesIO(result['screenshot']),
                caption="📸 Instagram page screenshot"
            )
        else:
            await update.message.reply_text(
                "⚠️ Could not capture screenshot. Check logs for details."
            )

    except Exception as e:
        logger.error(f"Error in ig_command: {e}")
        await status_msg.edit_text(
            f"❌ An error occurred: {str(e)[:200]}"
        )
        await update.message.reply_text(
            "Please check if your cookie format is correct and try again."
        )

def main():
    bot_token = os.getenv('BOT_TOKEN')

    if not bot_token:
        raise ValueError("BOT_TOKEN environment variable is not set")

    application = Application.builder().token(bot_token).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cmds", cmds))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("ig", ig_command))

    logger.info("Bot started successfully")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
