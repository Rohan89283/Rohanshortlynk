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

This bot automates connecting your Instagram account to Facebook Business Manager for running ads.

📋 Available Commands:
/start - Show this welcome message
/help - Detailed help and instructions
/ig <cookie> - Start automation (paste your Instagram cookie)

⚠️ Quick Start:
1. Get your Instagram cookie (see /help for instructions)
2. Use: /ig sessionid=xxx; ds_user_id=yyy; csrftoken=zzz
3. Watch the automation happen with live updates
4. Receive screenshots at each step

Type /help for detailed instructions on getting your cookie.
    """
    await update.message.reply_text(welcome_message)

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Help command"""
    help_message = """
📚 HOW TO GET INSTAGRAM COOKIES

1️⃣ Open Instagram in Chrome/Firefox
   - Go to instagram.com and log in

2️⃣ Open Developer Tools
   - Press F12 (or right-click > Inspect)

3️⃣ Go to Application/Storage Tab
   - Click "Application" (Chrome) or "Storage" (Firefox)
   - Expand "Cookies" on the left
   - Click on "https://www.instagram.com"

4️⃣ Copy These Cookie Values:
   - sessionid
   - ds_user_id
   - csrftoken

5️⃣ Format Your Cookie String:
   sessionid=VALUE1; ds_user_id=VALUE2; csrftoken=VALUE3

6️⃣ Use The Command:
   /ig sessionid=abc123; ds_user_id=456789; csrftoken=xyz789

━━━━━━━━━━━━━━━━━━━━

📸 WHAT HAPPENS NEXT:

Step 1: Bot opens Facebook Business login
Step 2: Clicks "Log in with Instagram"
Step 3: Uses your cookies to authenticate
Step 4: Navigates to Business Manager home
Step 5: Clicks "Create ad" button
Step 6: Processes boosted item picker
Step 7: Authorizes Facebook connection
Step 8: Completes final setup steps

You'll get:
✓ Live updates for each step
✓ Screenshots at every stage
✓ Success/error notifications
✓ Detailed logs for debugging

━━━━━━━━━━━━━━━━━━━━

⚠️ IMPORTANT NOTES:

- Cookies expire after a while (get fresh ones if automation fails)
- Keep your cookies private (never share with others)
- Use at your own risk (automation may violate ToS)
- Bot runs in headless mode (you won't see browser)
- Process takes 2-5 minutes depending on connection

Need help? Check the screenshots if something fails!
    """
    await update.message.reply_text(help_message)

async def cmds_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Commands list"""
    cmds_message = """
📋 AVAILABLE COMMANDS

/start
  → Welcome message and quick overview

/help
  → Detailed guide on getting Instagram cookies
  → Step-by-step automation process explanation

/ig <cookie>
  → Start the automation process
  → Example: /ig sessionid=xxx; ds_user_id=yyy; csrftoken=zzz

━━━━━━━━━━━━━━━━━━━━

💡 WORKFLOW:

1. Type /help to learn how to get cookies
2. Copy your Instagram cookies from browser
3. Use /ig command with your cookies
4. Watch the magic happen!
5. Get screenshots of every step

━━━━━━━━━━━━━━━━━━━━

Need help getting cookies? → /help
Ready to start? → /ig <your_cookie>
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
