import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from instagram_automation import InstagramAutomation

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.getenv('BOT_TOKEN')

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start command"""
    welcome_message = """
🤖 Welcome to Instagram Business Automation Bot!

This bot helps you automate Instagram Business Manager setup.

📋 Available Commands:
/start - Show this welcome message
/help - Show detailed help information
/cmds - List all available commands
/ig <cookie> - Start Instagram automation with your cookie

⚠️ Important: Make sure you have your Instagram cookie ready before using /ig command.
    """
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    help_message = """
📚 Detailed Help Information

🔹 /ig Command Usage:
Format: /ig <your_instagram_cookie>

Example: /ig sessionid=abc123xyz; ds_user_id=456789; csrftoken=token123

What the bot does:
1. Opens Facebook Business login page
2. Clicks "Log in with Instagram"
3. Uses your cookie to log into Instagram
4. Navigates through Business Manager setup
5. Links your Instagram account to Facebook ad account
6. Completes the ad account connection process

📸 You'll receive:
- Live updates for each step
- Screenshots of the process
- Error messages if something fails
- Final confirmation when complete

⚠️ Requirements:
- Valid Instagram cookie string
- Instagram account must be business/creator account
- Stable internet connection

🔐 Privacy:
- Your cookies are used only for automation
- No data is stored permanently
- Session ends after process completes

Need support? Contact the bot administrator.
    """
    await update.message.reply_text(help_message)

async def cmds_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commands list"""
    cmds_message = """
📋 Available Commands:

/start - Welcome message and quick start guide
/help - Detailed help and usage instructions
/cmds - Show all available commands (this message)
/ig <cookie> - Start Instagram automation process

💡 Quick Start:
1. Use /start to see the welcome message
2. Get your Instagram cookie
3. Run /ig with your cookie to start automation
4. Monitor progress and receive screenshots

For detailed instructions, use /help
    """
    await update.message.reply_text(cmds_message)

async def ig_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /ig command with Instagram cookie"""
    if not context.args:
        await update.message.reply_text(
            "❌ Error: Please provide your Instagram cookie.\n\n"
            "Usage: /ig <cookie_string>\n\n"
            "Example: /ig sessionid=abc123; ds_user_id=456789"
        )
        return

    cookie = ' '.join(context.args)
    logger.info(f"User {update.effective_user.id} started automation")

    # Send initial message
    status_message = await update.message.reply_text(
        "🚀 Starting automation process...\n"
        "Please wait, this may take a few minutes.\n\n"
        "You will receive live updates below."
    )

    updates_text = []

    async def update_callback(message):
        """Callback to send updates to user"""
        updates_text.append(message)
        full_text = '\n'.join(updates_text[-20:])  # Keep last 20 updates
        try:
            await status_message.edit_text(
                f"🔄 Automation in Progress...\n\n{full_text}"
            )
        except:
            pass  # Ignore if message hasn't changed

    # Run automation
    automation = InstagramAutomation(cookie, update_callback)

    try:
        success, screenshots = await automation.run_automation()

        # Send final status
        if success:
            await update.message.reply_text(
                "✅ Automation completed successfully!\n\n"
                f"📊 Captured {len(screenshots)} screenshots.\n"
                "Sending screenshots..."
            )
        else:
            await update.message.reply_text(
                "❌ Automation failed.\n\n"
                f"📊 Captured {len(screenshots)} screenshots for debugging.\n"
                "Sending screenshots..."
            )

        # Send screenshots
        for idx, screenshot in enumerate(screenshots, 1):
            try:
                screenshot['image'].seek(0)
                await update.message.reply_photo(
                    photo=screenshot['image'],
                    caption=f"Screenshot {idx}/{len(screenshots)}: {screenshot['name']}"
                )
                await asyncio.sleep(0.5)  # Avoid rate limiting
            except Exception as e:
                logger.error(f"Failed to send screenshot {idx}: {e}")

        if success:
            await update.message.reply_text(
                "🎉 All done! Your Instagram account should now be connected to Facebook Business Manager."
            )
        else:
            await update.message.reply_text(
                "⚠️ Process completed with errors. Please check the screenshots and logs above."
            )

    except Exception as e:
        logger.error(f"Error in automation: {e}")
        await update.message.reply_text(
            f"❌ An error occurred: {str(e)}\n\n"
            "Please try again or contact support."
        )

def main():
    """Start the bot"""
    if not BOT_TOKEN:
        logger.error("BOT_TOKEN not set!")
        return

    app = Application.builder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cmds", cmds_command))
    app.add_handler(CommandHandler("ig", ig_command))

    logger.info("Bot started successfully!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
