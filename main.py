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
        "📋 *Step 2:* Meta Business Home ⏸️\n"
        "📋 *Step 3:* Ad Center Summary ⏸️\n\n"
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
                f"📋 *Step 2:* Meta Business Home {'✅' if step > 2 else '⏳' if step == 2 else '⏸️'}\n"
                f"📋 *Step 3:* Ad Center Summary {'✅' if step > 3 else '⏳' if step == 3 else '⏸️'}\n\n"
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
        total_posts = result.get('total_posts', 'N/A')

        step1_status = "✅" if result.get('step1_complete', False) else "❌"
        step1_text = "Completed" if result.get('step1_complete', False) else "Failed"

        step2_status = "✅" if result.get('step2_complete', False) else "❌"
        step2_text = "Completed" if result.get('step2_complete', False) else "Failed" if result.get('step1_complete', False) else "Pending"

        step3_status = "✅" if result.get('step3_complete', False) else "❌"
        step3_text = "Completed" if result.get('step3_complete', False) else "Failed" if result.get('step2_complete', False) else "Pending"

        final_status = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔍 *INSTAGRAM COOKIE CHECKER*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            f"📋 *Step 1:* Instagram Login {step1_status} {step1_text}\n"
            f"📋 *Step 2:* Meta Business Home {step2_status} {step2_text}\n"
            f"📋 *Step 3:* Ad Center Summary {step3_status} {step3_text}\n\n"
            f"⏱️ *Time:* {elapsed}s\n"
            f"👤 *Username:* {username}\n"
            f"📊 *Total Posts:* {total_posts}\n\n"
        )

        if result['valid']:
            final_status += f"✅ *Status:* Cookie Valid - Login Successful!\n"
        else:
            final_status += f"❌ *Status:* {result['message']}\n"

        await status_msg.edit_text(final_status, parse_mode='Markdown')

        # Send detailed Step 2 information if available
        if result.get('step2_method') or result.get('step2_click_technique'):
            step2_info = "━━━━━━━━━━━━━━━━━━━━━━\n"
            step2_info += "🔧 *STEP 2 DEBUG INFO*\n"
            step2_info += "━━━━━━━━━━━━━━━━━━━━━━\n\n"

            if result.get('step2_method'):
                step2_info += f"✅ *Detection Method:* {result['step2_method']}\n"

            if result.get('step2_click_technique'):
                step2_info += f"✅ *Click Technique:* {result['step2_click_technique']}\n"

            if result.get('step2_urls_visited'):
                urls = result['step2_urls_visited']
                step2_info += f"\n📍 *URLs Visited ({len(urls)}):*\n"
                for i, url in enumerate(urls[:5], 1):  # Limit to 5 URLs
                    step2_info += f"{i}. {url[:60]}...\n"

            if result.get('step2_button_html'):
                button_html = result['step2_button_html']
                step2_info += f"\n🔍 *Button HTML:*\n`{button_html[:200]}...`\n"

            await update.message.reply_text(step2_info, parse_mode='Markdown')

        # Send all screenshots in order
        if result.get('screenshot'):
            await update.message.reply_photo(
                photo=BytesIO(result['screenshot']),
                caption=f"📸 Step 1 - Instagram Login"
            )

        if result.get('screenshot_step2_before'):
            method_used = result.get('step2_method', 'Unknown')
            technique_used = result.get('step2_click_technique', 'Unknown')
            await update.message.reply_photo(
                photo=BytesIO(result['screenshot_step2_before']),
                caption=f"📸 Step 2 (Before)\n🔧 Method: {method_used}\n🖱️ Click: {technique_used}"
            )

        if result.get('screenshot_step2_after_click'):
            await update.message.reply_photo(
                photo=BytesIO(result['screenshot_step2_after_click']),
                caption=f"📸 Step 2 (After Click) - Right after clicking Instagram login button"
            )

        if result.get('screenshot_oauth_before'):
            await update.message.reply_photo(
                photo=BytesIO(result['screenshot_oauth_before']),
                caption=f"📸 OAuth Page (BEFORE) - Instagram OAuth page before clicking 'Log in as'"
            )

        if result.get('screenshot_oauth_after'):
            await update.message.reply_photo(
                photo=BytesIO(result['screenshot_oauth_after']),
                caption=f"📸 OAuth Page (AFTER) - After clicking 'Log in as' button"
            )

        # Keep old screenshot_oauth for compatibility
        if result.get('screenshot_oauth') and not result.get('screenshot_oauth_before'):
            await update.message.reply_photo(
                photo=BytesIO(result['screenshot_oauth']),
                caption=f"📸 OAuth Confirmation Page"
            )

        if result.get('screenshot_step2'):
            await update.message.reply_photo(
                photo=BytesIO(result['screenshot_step2']),
                caption=f"📸 Step 2 (Final) - Meta Business Home"
            )

        if result.get('screenshot_step3'):
            await update.message.reply_photo(
                photo=BytesIO(result['screenshot_step3']),
                caption=f"📸 Step 3 - Ad Center Summary"
            )

    except Exception as e:
        elapsed = int(time.time() - start_time)
        logger.error(f"Error in ig_command: {e}")

        error_status = (
            "━━━━━━━━━━━━━━━━━━━━━━\n"
            "🔍 *INSTAGRAM COOKIE CHECKER*\n"
            "━━━━━━━━━━━━━━━━━━━━━━\n\n"
            "📋 *Step 1:* Instagram Login ❌ Error\n"
            "📋 *Step 2:* Meta Business Home ⏸️ Pending\n"
            "📋 *Step 3:* Ad Center Summary ⏸️ Pending\n\n"
            f"⏱️ *Time:* {elapsed}s\n"
            "👤 *Username:* N/A\n"
            "📊 *Total Posts:* N/A\n\n"
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
