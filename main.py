import os
import requests
import time
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 🔐 ENV
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_ADMIN = int(os.getenv("BOT_ADMIN"))

# 🔥 SESSION (important for consistency)
session = requests.Session()

headers = {
    "User-Agent": "Mozilla/5.0 (Linux; Android 10; Mobile) AppleWebKit/537.36 Chrome/120.0.0.0 Mobile Safari/537.36",
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "en-US,en;q=0.9",
    "Connection": "keep-alive"
}

# 🔥 EXACT SAME LOGIC (FIXED REQUEST)
def check_username(username):
    url = f"https://www.instagram.com/{username}/"

    try:
        res = session.get(url, headers=headers, timeout=10)
        html = res.text

        # 🔥 YOUR ORIGINAL CHECK
        if f'rel="alternate" href="https://www.instagram.com/{username}/"' in html:
            return "EXISTS"
        else:
            return "NOT_EXIST"

    except Exception as e:
        print(f"ERROR {username}: {e}")
        return "ERROR"


# 🔥 EXTRACT USERNAMES
def extract_usernames(text):
    lines = text.splitlines()
    users = []

    for line in lines:
        line = line.strip().replace("@", "")
        if line:
            users.append(line)

    return users


# 🚀 /chk COMMAND
async def chk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    # 🔒 admin only
    if user_id != BOT_ADMIN:
        await update.message.reply_text("❌ You are not authorized.")
        return

    usernames = []

    # ✅ args
    if context.args:
        usernames.extend(context.args)

    # ✅ multiline
    if update.message.text:
        text = update.message.text.replace("/chk", "").strip()
        if text:
            usernames.extend(extract_usernames(text))

    # ✅ txt file
    if update.message.reply_to_message:
        doc = update.message.reply_to_message.document

        if doc and doc.file_name.endswith(".txt"):
            file = await context.bot.get_file(doc.file_id)
            content = await file.download_as_bytearray()
            file_text = content.decode("utf-8")

            usernames.extend(extract_usernames(file_text))

    if not usernames:
        await update.message.reply_text("⚠️ Send usernames or reply to .txt file")
        return

    usernames = list(set(usernames))

    await update.message.reply_text(f"🔍 Checking {len(usernames)} usernames...")

    results = []

    for username in usernames:
        username = username.strip().replace("@", "")

        result = check_username(username)

        if result == "EXISTS":
            msg = f"@{username} → ✅"
        elif result == "NOT_EXIST":
            msg = f"@{username} → ❌"
        else:
            msg = f"@{username} → ⚠️"

        print(msg)  # Railway logs
        results.append(msg)

        time.sleep(0.3)  # 🔥 anti-ban / more accurate

    # split messages
    chunk = ""
    for r in results:
        if len(chunk) + len(r) + 1 > 4000:
            await update.message.reply_text(chunk)
            chunk = ""
        chunk += r + "\n"

    if chunk:
        await update.message.reply_text(chunk)


# 🚀 MAIN
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("chk", chk))

    print("🤖 Bot running...")

    app.run_polling()


if __name__ == "__main__":
    main()
