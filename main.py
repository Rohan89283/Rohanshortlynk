import os
import logging
import asyncio
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.request import HTTPXRequest
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
🤖 Instagram Business Fix Bot

This bot automates connecting your Instagram account to Facebook Business Manager.

📋 Available Commands:
/start - Show this welcome message
/help - Detailed help and instructions
/cmds - All commands list
/ig <cookie> - Run automation (all screenshots)
/fix <cookie> - Run automation (multi-language, screenshots on failures only)
/fb <cookie> - ULTRA OPTIMIZED automation (fastest, smart detection)

⚠️ Quick Start:
1. Get your Instagram cookie (see /help for instructions)
2. Use: /fb sessionid=xxx; ds_user_id=yyy; csrftoken=zzz
3. Watch the automation with live updates
4. Receive screenshots only if errors occur

💡 Use /fb for the fastest execution with smart URL detection!

Type /help for detailed instructions.
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
   /fix sessionid=abc123; ds_user_id=456789; csrftoken=xyz789

━━━━━━━━━━━━━━━━━━━━

📸 AUTOMATION PROCESS:

PART 1: INSTAGRAM LOGIN
  → Step 1: Login to Instagram with cookie

PART 2: FACEBOOK BUSINESS
  → Step 2: Open Facebook Business and click "Log in with Instagram"
  → Step 3: Handle Instagram OAuth authorization

PART 3: FINAL WORK
  → Step 4: Click Boost button and continue
  → Step 5: Handle Facebook OAuth and complete

You'll get:
✓ Live updates for each part and step
✓ Success notification when complete
✓ Detailed logs for debugging

━━━━━━━━━━━━━━━━━━━━

⚠️ IMPORTANT NOTES:

- Cookies expire (get fresh ones if automation fails)
- Keep cookies private
- Bot runs in headless mode
- Process takes 1-3 minutes (fastest with /fb)
- Multi-language support (English, Bengali, Hindi, Spanish, Arabic, French, German, Portuguese, Russian)
- /fb command: ULTRA OPTIMIZED with smart detection (FASTEST)
- /fix command: captures screenshots only on failures
- /ig command: captures all screenshots

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

/cmds
  → Show this commands list

/ig <cookie>
  → Start automation with ALL screenshots
  → Example: /ig sessionid=xxx; ds_user_id=yyy; csrftoken=zzz
  → 📸 Captures screenshots at every step

/fix <cookie>
  → Start automation with FAILURE-ONLY screenshots
  → Example: /fix sessionid=xxx; ds_user_id=yyy; csrftoken=zzz
  → 📸 Captures screenshots only when errors occur
  → 🌍 Multi-language support (9 languages)

/fb <cookie>
  → ULTRA OPTIMIZED automation (RECOMMENDED)
  → Example: /fb sessionid=xxx; ds_user_id=yyy; csrftoken=zzz
  → ⚡ Fastest execution with smart URL detection
  → 📸 Screenshots only on failures
  → 🌍 Multi-language support (9 languages)
  → 🎯 Part 1 completes in under 6 seconds
  → 📊 Detailed timing reports for each step

━━━━━━━━━━━━━━━━━━━━

💡 WORKFLOW:

1. Type /help to learn how to get cookies
2. Copy your Instagram cookies from browser
3. Choose your command:
   - /fb (FASTEST & RECOMMENDED) - ultra optimized with smart detection
   - /fix (standard) - multi-language, minimal screenshots
   - /ig - all screenshots for debugging
4. Watch the magic happen!
5. Get screenshots (all steps or failures only)

━━━━━━━━━━━━━━━━━━━━

🌍 SUPPORTED LANGUAGES (for /fix and /fb):
English, Bengali, Hindi, Spanish, Arabic, French, German, Portuguese, Russian

━━━━━━━━━━━━━━━━━━━━

Need help getting cookies? → /help
Ready to start? → /fix <your_cookie>
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

    # Send initial message with retry logic
    status_message = None
    for attempt in range(3):
        try:
            status_message = await update.message.reply_text(
                "🚀 Starting automation process...\n"
                "Please wait, this may take a few minutes.\n\n"
                "You will receive live updates below.",
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30,
                pool_timeout=30
            )
            break
        except Exception as e:
            logger.warning(f"Failed to send initial message (attempt {attempt + 1}/3): {e}")
            if attempt == 2:
                # If all retries fail, send a simple message without waiting
                try:
                    await update.message.reply_text("�� Starting automation...")
                except:
                    pass
                # Continue without status updates
                status_message = None
            await asyncio.sleep(1)

    updates_text = []

    async def update_callback(message):
        """Callback to send updates to user"""
        if status_message is None:
            return  # Skip updates if initial message failed

        updates_text.append(message)
        full_text = '\n'.join(updates_text[-20:])  # Keep last 20 updates
        try:
            await status_message.edit_text(
                f"🔄 Automation in Progress...\n\n{full_text}",
                read_timeout=20,
                write_timeout=20
            )
        except Exception as e:
            logger.debug(f"Could not update message: {e}")
            pass  # Ignore if message hasn't changed or timeout

    # Run automation
    automation = InstagramAutomation(cookie, update_callback)

    try:
        success, screenshots = await automation.run_fix_command_v1()

        # Send final status
        if success:
            await update.message.reply_text(
                "✅ FIX COMMAND V1 - FIXED DONE!\n\n"
                f"📊 Captured {len(screenshots)} screenshots.\n"
                "Sending screenshots..."
            )
        else:
            await update.message.reply_text(
                "❌ Fix Command V1 failed.\n\n"
                f"📊 Captured {len(screenshots)} screenshots for debugging.\n"
                "Sending screenshots..."
            )

        # Send screenshots
        for idx, screenshot in enumerate(screenshots, 1):
            try:
                screenshot['image'].seek(0)
                await update.message.reply_photo(
                    photo=screenshot['image'],
                    caption=f"Screenshot {idx}/{len(screenshots)}: {screenshot['name']}",
                    read_timeout=60,
                    write_timeout=60
                )
                await asyncio.sleep(0.5)  # Avoid rate limiting
            except Exception as e:
                logger.error(f"Failed to send screenshot {idx}: {e}")

        if success:
            await update.message.reply_text(
                "🎉 FIXED DONE! Your Instagram account is now connected to Facebook Business Manager."
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

async def fix_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /fix command with Instagram cookie - Multi-language version"""
    if not context.args:
        await update.message.reply_text(
            "❌ Error: Please provide your Instagram cookie.\n\n"
            "Usage: /fix <cookie_string>\n\n"
            "Example: /fix sessionid=abc123; ds_user_id=456789"
        )
        return

    cookie = ' '.join(context.args)
    logger.info(f"User {update.effective_user.id} started /fix automation")

    status_message = None
    for attempt in range(3):
        try:
            status_message = await update.message.reply_text(
                "🚀 Starting Fix Command (Multi-language)...\n"
                "Please wait, this may take a few minutes.\n\n"
                "You will receive live updates below.\n"
                "📸 Screenshots only captured on failures.",
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30,
                pool_timeout=30
            )
            break
        except Exception as e:
            logger.warning(f"Failed to send initial message (attempt {attempt + 1}/3): {e}")
            if attempt == 2:
                try:
                    await update.message.reply_text("🚀 Starting automation...")
                except:
                    pass
                status_message = None
            await asyncio.sleep(1)

    updates_text = []

    async def update_callback(message):
        """Callback to send updates to user"""
        if status_message is None:
            return

        updates_text.append(message)
        full_text = '\n'.join(updates_text[-20:])
        try:
            await status_message.edit_text(
                f"🔄 Fix Command in Progress...\n\n{full_text}",
                read_timeout=20,
                write_timeout=20
            )
        except Exception as e:
            logger.debug(f"Could not update message: {e}")
            pass

    automation = InstagramAutomation(cookie, update_callback)

    try:
        success, screenshots = await automation.run_fix_command()

        if success:
            await update.message.reply_text(
                "✅ FIX COMMAND - FIXED DONE!\n\n"
                f"📊 Captured {len(screenshots)} screenshots (failures only).\n"
                "Sending screenshots..."
            )
        else:
            await update.message.reply_text(
                "❌ Fix Command failed.\n\n"
                f"📊 Captured {len(screenshots)} screenshots for debugging.\n"
                "Sending screenshots..."
            )

        for idx, screenshot in enumerate(screenshots, 1):
            try:
                screenshot['image'].seek(0)
                caption = f"Screenshot {idx}/{len(screenshots)}: {screenshot['name']}"
                if 'failure_reason' in screenshot:
                    caption += f"\n❌ Reason: {screenshot['failure_reason']}"

                await update.message.reply_photo(
                    photo=screenshot['image'],
                    caption=caption,
                    read_timeout=60,
                    write_timeout=60
                )
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed to send screenshot {idx}: {e}")

        if success:
            await update.message.reply_text(
                "🎉 FIXED DONE! Your Instagram account is now connected to Facebook Business Manager."
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

async def fb_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /fb command with Instagram cookie - Optimized & Fastest version"""
    if not context.args:
        await update.message.reply_text(
            "❌ Error: Please provide your Instagram cookie.\n\n"
            "Usage: /fb <cookie_string>\n\n"
            "Example: /fb sessionid=abc123; ds_user_id=456789"
        )
        return

    cookie = ' '.join(context.args)
    logger.info(f"User {update.effective_user.id} started /fb automation")

    status_message = None
    for attempt in range(3):
        try:
            status_message = await update.message.reply_text(
                "⚡ Starting FB Command (Optimized & Fastest)...\n"
                "Please wait, this will be quick!\n\n"
                "You will receive live updates below.\n"
                "📸 Screenshots only captured on failures.\n"
                "⏱️ Detailed timing report will be provided.",
                read_timeout=30,
                write_timeout=30,
                connect_timeout=30,
                pool_timeout=30
            )
            break
        except Exception as e:
            logger.warning(f"Failed to send initial message (attempt {attempt + 1}/3): {e}")
            if attempt == 2:
                try:
                    await update.message.reply_text("⚡ Starting optimized automation...")
                except:
                    pass
                status_message = None
            await asyncio.sleep(1)

    updates_text = []

    async def update_callback(message):
        """Callback to send updates to user"""
        if status_message is None:
            return

        updates_text.append(message)
        full_text = '\n'.join(updates_text[-25:])
        try:
            await status_message.edit_text(
                f"⚡ FB Command in Progress...\n\n{full_text}",
                read_timeout=20,
                write_timeout=20
            )
        except Exception as e:
            logger.debug(f"Could not update message: {e}")
            pass

    automation = InstagramAutomation(cookie, update_callback)

    try:
        success, screenshots = await automation.run_fb_command()

        if len(screenshots) > 0:
            await update.message.reply_text(
                f"📸 Captured {len(screenshots)} screenshots (failures only).\n"
                "Sending screenshots..."
            )

        for idx, screenshot in enumerate(screenshots, 1):
            try:
                screenshot['image'].seek(0)
                caption = f"Screenshot {idx}/{len(screenshots)}: {screenshot['name']}"
                if 'failure_reason' in screenshot:
                    caption += f"\n❌ Failure: {screenshot['failure_reason']}"
                if 'url' in screenshot:
                    caption += f"\n🔗 URL: {screenshot['url']}"

                await update.message.reply_photo(
                    photo=screenshot['image'],
                    caption=caption,
                    read_timeout=30,
                    write_timeout=30
                )
                await asyncio.sleep(0.5)
            except Exception as e:
                logger.error(f"Failed to send screenshot {idx}: {e}")

        if success:
            await update.message.reply_text(
                "🎉 FB COMMAND COMPLETED! Your Instagram account is now connected to Facebook Business Manager.\n\n"
                "⚡ This was the optimized & fastest automation with detailed timing reports!"
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

    # Create custom request with longer timeouts
    request = HTTPXRequest(
        connection_pool_size=8,
        read_timeout=60.0,
        write_timeout=60.0,
        connect_timeout=30.0,
        pool_timeout=30.0
    )

    app = (
        Application.builder()
        .token(BOT_TOKEN)
        .request(request)
        .build()
    )

    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("help", help_command))
    app.add_handler(CommandHandler("cmds", cmds_command))
    app.add_handler(CommandHandler("ig", ig_command))
    app.add_handler(CommandHandler("fix", fix_command))
    app.add_handler(CommandHandler("fb", fb_command))

    logger.info("Bot started successfully!")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
