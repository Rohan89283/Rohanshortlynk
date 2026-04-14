import os
import json
import time
import zipfile
import shutil
import requests
import psutil
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes

# 🔐 ENV
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_ADMIN = int(os.getenv("BOT_ADMIN"))

START_TIME = time.time()
THREADS = 10

DATA_FILE = "users.json"
LOG_FILE = "bot.log"

# 🔥 INIT FILES
if not os.path.exists(DATA_FILE):
    with open(DATA_FILE, "w") as f:
        json.dump({"approved": {}, "banned": []}, f)

# 🔥 LOAD DATA
def load_data():
    with open(DATA_FILE) as f:
        return json.load(f)

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f, indent=2)

# 🔥 LOG
def log(text):
    print(text)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(text + "\n")

# 🔥 SESSION
session = requests.Session()
headers = {"User-Agent": "Mozilla/5.0"}

# 🔥 YOUR CHECK LOGIC
def check(username):
    url = f"https://www.instagram.com/{username}/"
    try:
        res = session.get(url, headers=headers, timeout=10)
        html = res.text

        if f'rel="alternate" href="https://www.instagram.com/{username}/"' in html:
            result = f"{username} → ✅"
        else:
            result = f"{username} → ❌"

    except Exception as e:
        result = f"{username} → ⚠️"
        log(f"ERROR {username}: {e}")

    log(result)
    return result

# 🔥 HELPERS
def extract(text):
    users = []
    for line in text.splitlines():
        line = line.strip().replace("@", "")
        if line:
            users.extend(line.split())
    return users

def is_admin(user_id):
    return user_id == BOT_ADMIN

def is_approved(user_id, cmd):
    data = load_data()
    if user_id == BOT_ADMIN:
        return True
    if user_id in data["banned"]:
        return False
    return str(user_id) in data["approved"] and (
        cmd in data["approved"][str(user_id)] or "all" in data["approved"][str(user_id)]
    )

# ================= BASIC CMDS =================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome to IG Checker Bot")

async def cmds(update: Update, context):
    user_id = update.effective_user.id

    msg = "📜 Commands:\n\n"

    msg += "🔹 Basic:\n/start\n/help\n/id\n/ping\n\n"
    msg += "🔹 Pro:\n/chk\n\n"

    if is_admin(user_id):
        msg += "🔸 Admin:\n/approve /revoke /ban /unban /log /ram /cleanram /backup /restore /proxy\n"

    await update.message.reply_text(msg)

async def help_cmd(update: Update, context):
    await update.message.reply_text("Use /chk username or reply to txt file")

async def id_cmd(update: Update, context):
    u = update.effective_user
    await update.message.reply_text(f"ID: {u.id}\nUsername: @{u.username}")

async def ping(update: Update, context):
    uptime = int(time.time() - START_TIME)
    await update.message.reply_text(f"🏓 Pong!\nUptime: {uptime}s")

# ================= PRO =================

async def chk(update: Update, context):
    user_id = update.effective_user.id

    if not is_approved(user_id, "chk"):
        await update.message.reply_text("❌ Not approved")
        return

    usernames = []

    if context.args:
        usernames.extend(context.args)

    if update.message.text:
        usernames.extend(extract(update.message.text.replace("/chk", "")))

    if update.message.reply_to_message:
        doc = update.message.reply_to_message.document
        if doc and doc.file_name.endswith(".txt"):
            file = await context.bot.get_file(doc.file_id)
            content = await file.download_as_bytearray()
            usernames.extend(extract(content.decode()))

    if not usernames:
        await update.message.reply_text("⚠️ No usernames")
        return

    usernames = list(set(usernames))
    await update.message.reply_text(f"Checking {len(usernames)}...")

    with ThreadPoolExecutor(max_workers=THREADS) as ex:
        results = list(ex.map(check, usernames))

    await update.message.reply_text("\n".join(results))

# ================= ADMIN =================

async def approve(update: Update, context):
    if not is_admin(update.effective_user.id):
        return

    uid = context.args[0]
    cmd = context.args[1]

    data = load_data()
    data["approved"].setdefault(uid, []).append(cmd)
    save_data(data)

    await update.message.reply_text("✅ Approved")

async def revoke(update: Update, context):
    if not is_admin(update.effective_user.id):
        return

    uid = context.args[0]
    data = load_data()

    if uid in data["approved"]:
        del data["approved"][uid]

    save_data(data)
    await update.message.reply_text("❌ Revoked")

async def ban(update: Update, context):
    if not is_admin(update.effective_user.id):
        return

    uid = int(context.args[0])
    data = load_data()
    data["banned"].append(uid)
    save_data(data)

    await update.message.reply_text("🚫 Banned")

async def unban(update: Update, context):
    if not is_admin(update.effective_user.id):
        return

    uid = int(context.args[0])
    data = load_data()

    if uid in data["banned"]:
        data["banned"].remove(uid)

    save_data(data)
    await update.message.reply_text("✅ Unbanned")

async def log_cmd(update: Update, context):
    if not is_admin(update.effective_user.id):
        return

    if os.path.exists(LOG_FILE):
        await update.message.reply_document(open(LOG_FILE, "rb"))
    else:
        await update.message.reply_text("No logs")

async def ram(update: Update, context):
    mem = psutil.virtual_memory()
    await update.message.reply_text(f"RAM: {mem.percent}%")

async def cleanram(update: Update, context):
    await update.message.reply_text("🧹 Restarting recommended")

async def backup(update: Update, context):
    zip_name = "backup.zip"
    with zipfile.ZipFile(zip_name, "w") as z:
        for file in os.listdir():
            if file.endswith(".py") or file.endswith(".json"):
                z.write(file)
    await update.message.reply_document(open(zip_name, "rb"))

async def restore(update: Update, context):
    if update.message.reply_to_message:
        doc = update.message.reply_to_message.document
        file = await context.bot.get_file(doc.file_id)
        path = "restore.zip"
        await file.download_to_drive(path)

        with zipfile.ZipFile(path, "r") as z:
            z.extractall()

        await update.message.reply_text("✅ Restored")

async def proxy(update: Update, context):
    await update.message.reply_text("⚙️ Proxy UI coming soon")

# ================= MAIN =================

def main():
    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # basic
    app.add_handler(CommandHandler("start", start))
    app.add_handler(CommandHandler("cmds", cmds))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("ping", ping))

    # pro
    app.add_handler(CommandHandler("chk", chk))

    # admin
    app.add_handler(CommandHandler("approve", approve))
    app.add_handler(CommandHandler("revoke", revoke))
    app.add_handler(CommandHandler("ban", ban))
    app.add_handler(CommandHandler("unban", unban))
    app.add_handler(CommandHandler("log", log_cmd))
    app.add_handler(CommandHandler("ram", ram))
    app.add_handler(CommandHandler("cleanram", cleanram))
    app.add_handler(CommandHandler("backup", backup))
    app.add_handler(CommandHandler("restore", restore))
    app.add_handler(CommandHandler("proxy", proxy))

    print("🔥 BOT RUNNING")
    app.run_polling()

if __name__ == "__main__":
    main()
