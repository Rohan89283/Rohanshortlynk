import os
import requests
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 🔐 ENV
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_ADMIN = int(os.getenv("BOT_ADMIN"))

THREADS = 10

session = requests.Session()

headers = {
    "User-Agent": "Mozilla/5.0"
}

LOG_FILE = "bot.log"


# 🔥 LOG FUNCTION
def write_log(text):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")


# 🔥 SAME CHECK (WITH LOGGING)
def check(username):
    url = f"https://www.instagram.com/{username}/"

    try:
        res = session.get(url, headers=headers, timeout=10)
        html = res.text

        log_text = f"\n--- CHECKING: {username} ---\n"
        log_text += f"STATUS: {res.status_code}\n"
        log_text += f"LENGTH: {len(html)}\n"
        log_text += html[:200].replace("\n", " ") + "\n"

        if f'rel="alternate" href="https://www.instagram.com/{username}/"' in html:
            result = f"{username} → ✅ EXISTS"
        else:
            result = f"{username} → ❌ NOT EXIST"

        log_text += result

    except Exception as e:
        result = f"{username} → ⚠️ ERROR"
        log_text = f"ERROR {username}: {e}"

    print(log_text)
    write_log(log_text)

    return result


# 🔥 USERNAME PARSER
def extract_usernames(text):
    users = []
    for line in text.splitlines():
        line = line.strip().replace("@", "")
        if line:
            users.extend(line.split())
    return users


# 🚀 /chk
async def chk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != BOT_ADMIN:
        await update.message.reply_text("❌ Not allowed")
        return

    usernames = []

    if context.args:
        usernames.extend(context.args)

    if update.message.text:
        text = update.message.text.replace("/chk", "").strip()
        if text:
            usernames.extend(extract_usernames(text))

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

    with ThreadPoolExecutor(max_workers=THREADS) as executor:
        outputs = list(executor.map(check, usernames))
        results.extend(outputs)

    chunk = ""
    for r in results:
        if len(chunk) + len(r) + 1 > 4000:
            await update.message.reply_text(chunk)
            chunk = ""
        chunk += r + "\n"

    if chunk:
        await update.message.reply_text(chunk)


# 🚀 /log
async def log_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != BOT_ADMIN:
        await update.message.reply_text("❌ Not allowed")
        return

    if not os.path.exists(LOG_FILE):
        await update.message.reply_text("📭 No logs yet.")
        return

    # read last lines
    with open(LOG_FILE, "r", encoding="utf-8") as f:
        lines = f.readlines()

    last_logs = "".join(lines[-50:])  # last 50 lines

    if len(last_logs) > 4000:
        last_logs = last_logs[-4000:]

    await update.message.reply_text(f"📜 Last Logs:\n\n{last_logs}")


# 🚀 MAIN
def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    app.add_handler(CommandHandler("chk", chk))
    app.add_handler(CommandHandler("log", log_cmd))

    print("🤖 Bot started...")

    app.run_polling()


if __name__ == "__main__":
    main()
