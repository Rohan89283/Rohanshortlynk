import os
import requests
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 🔐 ENV
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_ADMIN = int(os.getenv("BOT_ADMIN"))

headers = {
    "User-Agent": "Mozilla/5.0"
}

# 🔥 IMPROVED CHECK FUNCTION
def check_username(username):
    url = f"https://www.instagram.com/{username}/"

    try:
        res = requests.get(url, headers=headers, timeout=10)
        html = res.text

        if f'"username":"{username}"' in html:
            return "EXISTS"
        elif "Page Not Found" in html:
            return "NOT_EXIST"
        else:
            return "NOT_EXIST"

    except Exception as e:
        print(f"ERROR checking {username}: {e}")
        return "ERROR"


# 🔥 EXTRACT USERNAMES FROM TEXT
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

    # ✅ Case 1: command args (/chk user1 user2)
    if context.args:
        usernames.extend(context.args)

    # ✅ Case 2: multiline message
    if update.message.text:
        text = update.message.text.replace("/chk", "").strip()
        if text:
            usernames.extend(extract_usernames(text))

    # ✅ Case 3: reply to file
    if update.message.reply_to_message:
        doc = update.message.reply_to_message.document

        if doc and doc.file_name.endswith(".txt"):
            file = await context.bot.get_file(doc.file_id)
            content = await file.download_as_bytearray()
            file_text = content.decode("utf-8")

            usernames.extend(extract_usernames(file_text))

    # ❗ no usernames found
    if not usernames:
        await update.message.reply_text("⚠️ Send usernames or reply to .txt file")
        return

    # remove duplicates
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

        print(msg)  # 👈 Railway log
        results.append(msg)

    # split long messages (telegram limit)
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
