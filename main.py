import os
import requests
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 🔐 ENV
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_ADMIN = int(os.getenv("BOT_ADMIN"))

# 🔥 SETTINGS (same style)
THREADS = 10

session = requests.Session()

headers = {
    "User-Agent": "Mozilla/5.0"
}

# 🔥 SAME LOGIC (WITH DEBUG LOGS)
def check(username):
    url = f"https://www.instagram.com/{username}/"

    try:
        res = session.get(url, headers=headers, timeout=10)

        html = res.text

        # 🔍 DEBUG LOGS
        print(f"\n--- CHECKING: {username} ---")
        print(f"STATUS: {res.status_code}")
        print(f"LENGTH: {len(html)}")

        # show small part of html (important)
        print(html[:200].replace("\n", " "))

        # 🔥 YOUR EXACT LOGIC
        if f'rel="alternate" href="https://www.instagram.com/{username}/"' in html:
            result = f"{username} → ✅ EXISTS"
        else:
            result = f"{username} → ❌ NOT EXIST"

    except Exception as e:
        result = f"{username} → ⚠️ ERROR"
        print(f"ERROR: {e}")

    print(result)
    return result


# 🔥 EXTRACT USERNAMES
def extract_usernames(text):
    users = []
    for line in text.splitlines():
        line = line.strip().replace("@", "")
        if line:
            users.extend(line.split())  # supports space separated
    return users


# 🚀 /chk COMMAND
async def chk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id

    if user_id != BOT_ADMIN:
        await update.message.reply_text("❌ Not allowed")
        return

    usernames = []

    # ✅ args
    if context.args:
        usernames.extend(context.args)

    # ✅ multiline / message
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
            usernames.extend(extract_usernames(content.decode("utf-8")))

    if not usernames:
        await update.message.reply_text("⚠️ Send usernames or reply to txt")
        return

    usernames = list(set(usernames))

    await update.message.reply_text(f"🔍 Checking {len(usernames)} usernames...")

    results = []

    # 🔥 THREADING LIKE YOUR SCRIPT
    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        outputs = list(executor.map(check, usernames))
        results.extend(outputs)

    # 🔥 SEND RESULT (SAFE SPLIT)
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

    print("🤖 Bot started...")

    app.run_polling()


if __name__ == "__main__":
    main()
