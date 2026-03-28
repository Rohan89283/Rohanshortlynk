import os
import logging
from dotenv import load_dotenv
from telegram import Update, InputFile
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes
from instagram_checker import check_instagram_cookie
from proxy_validator import ProxyValidator
from proxy_manager import ProxyManager
from io import BytesIO

# Load environment variables
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
        "/addproxy - Add proxies (supports domains & special chars)\n"
        "/listproxy - List all your proxies\n"
        "/deleteproxy [id] - Delete specific proxy\n"
        "/clearproxy - Delete all your proxies\n"
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
        "**/addproxy**\n"
        "Add proxies in various formats:\n"
        "• `/addproxy host:port`\n"
        "• `/addproxy host:port:user:pass`\n"
        "• `/addproxy user:pass@host:port`\n"
        "• `/addproxy http://host:port`\n"
        "• `/addproxy http://user:pass@host:port`\n"
        "• Multiple proxies (one per line)\n"
        "• Send .txt file with proxies\n"
        "Note: Host can be IP or domain (e.g., proxy.example.com)\n"
        "Note: Password can contain special characters and colons\n\n"
        "**/listproxy**\n"
        "View all your saved proxies with their status.\n\n"
        "**/deleteproxy [id]**\n"
        "Delete a specific proxy by ID.\n\n"
        "**/clearproxy**\n"
        "Remove all your proxies at once."
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
        "🌐 *Proxy:* Checking...\n"
        "📍 *Location:* N/A\n"
        "👤 *Username:* N/A\n\n"
        "🔄 Initializing browser...",
        parse_mode='Markdown'
    )

    import time
    import asyncio
    start_time = time.time()

    # Create async wrapper for status updates
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
        except:
            pass

    try:
        # Update: Starting Step 1
        await update_status(1, "Logging into Instagram...")

        result = check_instagram_cookie(cookie_string, user_id=user_id)

        elapsed = int(time.time() - start_time)
        proxy_used = result.get('proxy_used', 'Direct')
        username = result.get('username', 'N/A')
        total_posts = result.get('total_posts', 'N/A')
        location = result.get('location', 'N/A')

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
            f"🌐 *Proxy:* {proxy_used}\n"
            f"📍 *Location:* {location}\n"
            f"👤 *Username:* {username}\n"
            f"📊 *Total Posts:* {total_posts}\n\n"
        )

        if result['valid']:
            final_status += f"✅ *Status:* Cookie Valid - Login Successful!\n"
        else:
            final_status += f"❌ *Status:* {result['message']}\n"

        await status_msg.edit_text(final_status, parse_mode='Markdown')

        # Send only Step 2 and Step 3 screenshots
        if result.get('screenshot_step2'):
            await update.message.reply_photo(
                photo=BytesIO(result['screenshot_step2']),
                caption=f"📸 Step 2 - Meta Business Home"
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
            "🌐 *Proxy:* N/A\n"
            "📍 *Location:* N/A\n"
            "👤 *Username:* N/A\n"
            "📊 *Total Posts:* N/A\n\n"
            f"❌ *Error:* {str(e)[:100]}"
        )

        await status_msg.edit_text(error_status, parse_mode='Markdown')

async def addproxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Add proxies from text or file"""
    user_id = update.effective_user.id
    proxy_text = None

    if update.message.document:
        file = await context.bot.get_file(update.message.document.file_id)
        file_content = await file.download_as_bytearray()
        proxy_text = file_content.decode('utf-8', errors='ignore')
    elif context.args:
        proxy_text = ' '.join(context.args).replace(' ', '\n')
    else:
        await update.message.reply_text(
            "📝 *How to add proxies:*\n\n"
            "Send proxies in any of these formats:\n\n"
            "• `/addproxy host:port`\n"
            "• `/addproxy host:port:user:pass`\n"
            "• `/addproxy user:pass@host:port`\n"
            "• `/addproxy http://host:port`\n"
            "• `/addproxy http://user:pass@host:port`\n\n"
            "Examples:\n"
            "• `1.2.3.4:8080`\n"
            "• `proxy.example.com:8000:user:pass`\n"
            "• `user:complex-pass@proxy.com:8080`\n\n"
            "Or send multiple proxies (one per line)\n"
            "Or upload a .txt file with proxies!\n\n"
            "*Note:* Password can contain special characters and colons\n"
            "*Note:* Fast validation checks proxy connectivity only",
            parse_mode='Markdown'
        )
        return

    status_msg = await update.message.reply_text("🔄 Processing proxies...")

    try:
        proxies = ProxyValidator.parse_proxy_list(proxy_text)

        if not proxies:
            await status_msg.edit_text(
                "❌ No valid proxy format found!\n\n"
                "Use /help to see supported formats."
            )
            return

        await status_msg.edit_text(
            f"🔍 Found {len(proxies)} proxies\n"
            f"⚡ Fast validating proxies..."
        )

        valid_proxies = ProxyValidator.validate_proxies_batch(proxies, max_workers=50, fast_mode=True)

        if not valid_proxies:
            await status_msg.edit_text(
                f"❌ None of the {len(proxies)} proxies are working!\n\n"
                "Please check your proxies and try again."
            )
            return

        await status_msg.edit_text(
            f"💾 Saving {len(valid_proxies)} working proxies..."
        )

        proxy_manager = ProxyManager()
        result = proxy_manager.add_proxies(user_id, valid_proxies)

        summary = (
            f"✅ *Proxy Import Complete*\n\n"
            f"📊 Total provided: {len(proxies)}\n"
            f"✅ Valid & working: {len(valid_proxies)}\n"
            f"💾 Added to database: {result['added']}\n"
            f"🔄 Already exists: {result['duplicates']}\n"
            f"❌ Failed to save: {result['failed']}\n\n"
            f"Use /listproxy to view all your proxies"
        )

        await status_msg.edit_text(summary, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in addproxy_command: {e}")
        await status_msg.edit_text(
            f"❌ Error processing proxies: {str(e)[:150]}"
        )

async def listproxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """List all user proxies"""
    user_id = update.effective_user.id

    try:
        proxy_manager = ProxyManager()
        proxies = proxy_manager.get_all_proxies(user_id)

        if not proxies:
            await update.message.reply_text(
                "📭 You don't have any proxies saved.\n\n"
                "Use /addproxy to add proxies!"
            )
            return

        active_count = sum(1 for p in proxies if p['is_active'])
        inactive_count = len(proxies) - active_count

        message = (
            f"🔐 *Your Proxies ({len(proxies)} total)*\n"
            f"✅ Active: {active_count}\n"
            f"❌ Inactive: {inactive_count}\n\n"
        )

        for idx, proxy in enumerate(proxies[:50], 1):
            status = "✅" if proxy['is_active'] else "❌"
            auth = "🔒" if proxy.get('username') else "🔓"

            message += (
                f"{idx}. {status} {auth} `{proxy['host']}:{proxy['port']}`\n"
                f"   Type: {proxy['proxy_type']} | "
                f"Success: {proxy['success_count']} | "
                f"Fails: {proxy['fail_count']}\n"
                f"   ID: `{proxy['id'][:8]}...`\n\n"
            )

        if len(proxies) > 50:
            message += f"\n_Showing first 50 of {len(proxies)} proxies_"

        message += "\n\nUse `/deleteproxy [id]` to remove a proxy"

        await update.message.reply_text(message, parse_mode='Markdown')

    except Exception as e:
        logger.error(f"Error in listproxy_command: {e}")
        await update.message.reply_text(
            f"❌ Error fetching proxies: {str(e)[:150]}"
        )

async def deleteproxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete a specific proxy"""
    user_id = update.effective_user.id

    if not context.args:
        await update.message.reply_text(
            "❌ Please provide proxy ID!\n\n"
            "Usage: `/deleteproxy [id]`\n"
            "Use /listproxy to see proxy IDs",
            parse_mode='Markdown'
        )
        return

    proxy_id = context.args[0]

    try:
        proxy_manager = ProxyManager()
        success = proxy_manager.delete_proxy(user_id, proxy_id)

        if success:
            await update.message.reply_text(
                "✅ Proxy deleted successfully!"
            )
        else:
            await update.message.reply_text(
                "❌ Failed to delete proxy. Make sure the ID is correct."
            )

    except Exception as e:
        logger.error(f"Error in deleteproxy_command: {e}")
        await update.message.reply_text(
            f"❌ Error: {str(e)[:150]}"
        )

async def clearproxy_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Delete all proxies for user"""
    user_id = update.effective_user.id

    try:
        proxy_manager = ProxyManager()
        proxies = proxy_manager.get_all_proxies(user_id)

        if not proxies:
            await update.message.reply_text(
                "📭 You don't have any proxies to clear."
            )
            return

        success = proxy_manager.delete_all_proxies(user_id)

        if success:
            await update.message.reply_text(
                f"✅ Successfully deleted all {len(proxies)} proxies!"
            )
        else:
            await update.message.reply_text(
                "❌ Failed to delete proxies."
            )

    except Exception as e:
        logger.error(f"Error in clearproxy_command: {e}")
        await update.message.reply_text(
            f"❌ Error: {str(e)[:150]}"
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
    application.add_handler(CommandHandler("addproxy", addproxy_command))
    application.add_handler(CommandHandler("listproxy", listproxy_command))
    application.add_handler(CommandHandler("deleteproxy", deleteproxy_command))
    application.add_handler(CommandHandler("clearproxy", clearproxy_command))
    application.add_handler(MessageHandler(filters.Document.ALL, addproxy_command))

    logger.info("Bot started successfully")
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == '__main__':
    main()
