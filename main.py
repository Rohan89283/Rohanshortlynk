import os
import logging
from dotenv import load_dotenv
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from instagram_checker import check_instagram_cookie
from io import BytesIO
import time

load_dotenv()

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
        "/start - Start the bot\n"
        "/cmds - Show all commands\n"
        "/help - Get detailed help\n"
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
        "The bot will test the cookies and send you a screenshot."
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

    user_id = update.effective_user.id
    cookie_string = ' '.join(context.args)

    status_msg = await update.message.reply_text(
        "━━━━━━━━━━━━━━━━━━━━━━\n"
        "🔍 *INSTAGRAM COOKIE CHECKER*\n"
        "━━━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 *Step 1:* Instagram Login ⏳\n"
        "📋 *Step 2:* Meta Business Suite ⏸️\n\n"
        "⏱️ *Time:* 0s\n"
        "👤 *Username:* N/A\n\n"
        "🔄 Initializing browser...",
        parse_mode='Markdown'
    )

    start_time = time.time()

    async def update_status(step, status_text):
        try:
            elapsed = int(time.time() - start_time)
            await status_msg.edit_text(
                "━━━━━━━━━━━━━━━━━━━━━━\n"
                "🔍 *INSTAGRAM COOKIE CHECKER*\n"
                "━━━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📋 *Step 1:* Instagram Login {'✅' if step > 1 else '⏳' if step == 1 else '⏸️'}\n"
                f"📋 *Step 2:* Profile Data {'✅' if step > 2 else '⏳' if step == 2 else '⏸️'}\n\n"
                f"⏱️ *Time:* {elapsed}s\n\n"
                f"🔄 {status_text}",
                parse_mode='Markdown'
            )
        except Exception as e:
            logger.warning(f"Failed to update status: {e}")

    try:
        result = await check_instagram_cookie(cookie_string, user_id=user_id, update_callback=update_status)

        elapsed = int(time.time() - start_time)
        username = result.get('username', 'N/A')

        step1_status = "✅" if result.get('step1_complete', False) else "❌"
        step1_text = "Completed" if result.get('step1_complete', False) else "Failed"

        step2_status = "✅" if result.get('step2_complete', False) else "❌"
        step2_text = "Completed" if result.get('step2_complete', False) else "Failed"

        step3_status = "✅" if result.get('step3_complete', False) else "❌"
        step3_text = "Completed" if result.get('step3_complete', False) else "Failed"

        # Get Step 2 details
        step2_clicked = result.get('step2_instagram_clicked', False)
        step2_new_tab = result.get('step2_new_tab_info', {}).get('new_tab_opened', False)
        step2_total_windows = result.get('step2_new_tab_info', {}).get('total_windows', 1)
        step2_login_clicked = result.get('step2_login_button_clicked', False)

        # Get Step 3 details
        step3_get_started_clicked = result.get('step3_get_started_clicked', False)
        step3_continue_clicked = result.get('step3_continue_clicked', False)
        step3_continue_clicked_2 = result.get('step3_continue_clicked_2', False)

        final_status = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔍 *INSTAGRAM COOKIE CHECKER*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📋 *Step 1:* Instagram Login {step1_status} {step1_text}\n"
            f"📋 *Step 2:* Meta Business Suite {step2_status} {step2_text}\n"
            f"📋 *Step 3:* Ad Center {step3_status} {step3_text}\n\n"
            f"⏱️ *Time:* {elapsed}s\n"
            f"👤 *Username:* {username}\n"
            f"🔘 *IG Button Clicked:* {'Yes' if step2_clicked else 'No'}\n"
            f"🪟 *New Tab/Popup:* {'Yes' if step2_new_tab else 'No'}\n"
            f"🔑 *Login Button Clicked:* {'Yes' if step2_login_clicked else 'No'}\n"
            f"📱 *Total Windows:* {step2_total_windows}\n"
            f"🚀 *Get Started Clicked:* {'Yes' if step3_get_started_clicked else 'No'}\n"
            f"▶️ *Continue Clicked (1st):* {'Yes' if step3_continue_clicked else 'No'}\n"
            f"▶️ *Continue Clicked (2nd):* {'Yes' if step3_continue_clicked_2 else 'No'}\n\n"
        )

        if result['valid']:
            final_status += f"✅ *Status:* Cookie Valid - Login Successful!\n"
        else:
            final_status += f"❌ *Status:* {result['message']}\n"

        await status_msg.edit_text(final_status, parse_mode='Markdown')

        # Send screenshot for Step 1
        if result.get('screenshot'):
            await update.message.reply_photo(
                photo=BytesIO(result['screenshot']),
                caption=f"📸 Step 1 - Instagram Login"
            )

        # Send screenshot for Step 2 (main window)
        if result.get('screenshot_step2'):
            step2_url = result.get('step2_current_url', 'N/A')
            await update.message.reply_photo(
                photo=BytesIO(result['screenshot_step2']),
                caption=f"📸 Step 2 - Meta Business Suite (Main Window)\n🔗 URL: {step2_url[:80]}"
            )

        # Send screenshot for Step 3 (Ad Center)
        if result.get('screenshot_step3'):
            step3_url = result.get('step3_current_url', 'N/A')
            await update.message.reply_photo(
                photo=BytesIO(result['screenshot_step3']),
                caption=f"📸 Step 3 - Ad Center\n🔗 URL: {step3_url[:80]}"
            )

    except Exception as e:
        elapsed = int(time.time() - start_time)
        logger.error(f"Error in ig_command: {e}")

        error_status = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔍 *INSTAGRAM COOKIE CHECKER*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📋 *Step 1:* Instagram Login ❌ Error\n"
            "📋 *Step 2:* Meta Business Suite ⏸️ Skipped\n"
            "📋 *Step 3:* Ad Center ⏸️ Skipped\n\n"
            f"⏱️ *Time:* {elapsed}s\n"
            "👤 *Username:* N/A\n\n"
            f"❌ *Error:* {str(e)[:100]}"
        )

        await status_msg.edit_text(error_status, parse_mode='Markdown')

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
