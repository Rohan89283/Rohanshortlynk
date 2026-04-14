import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 🔐 ENV VARIABLES (from Railway)
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_ADMIN = int(os.getenv("BOT_ADMIN"))

headers = {
    "User-Agent": "Mozilla/5.0"
}

# 🔥 YOUR ORIGINAL LOGIC (converted to function)
def check_username(username):
    url = f"https://www.instagram.com/{username}/"

    try:
        res = requests.get(url, headers=headers, timeout=10)
        html = res.text

        if f'rel="alternate" href="https://www.instagram.com/{username}/"' in html:
            return "EXISTS"
        else:
            return "NOT_EXIST"

    except:
        return "ERROR"


# 🚀 /chk COMMAND
async def chk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # 🔒 Only admin allowed (for now)
    if user_id != BOT_ADMIN:
        await update.message.reply_text("❌ You are not authorized.")
        return

    # ❗ No username provided
    if len(context.args) == 0:
        await update.message.reply_text("⚠️ Usage:\n/chk username")
        return

    username = context.args[0].strip().replace("@", "")

    await update.message.reply_text(f"🔍 Checking `{username}`...", parse_mode="Markdown")

    result = check_username(username)

    if result == "EXISTS":
        msg = f"@{username} → ✅ EXISTS"
    elif result == "NOT_EXIST":
        msg = f"@{username} → ❌ NOT EXIST"
    else:
        msg = f"@{username} → ⚠️ ERROR"

    await update.message.reply_text(msg)


# 🚀 MAIN BOT
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("chk", chk))

    print("🤖 Bot is running...")

    app.run_polling()


if __name__ == "__main__":
    main()
