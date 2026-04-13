import os
import json
import time
import asyncio
import requests
import random
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, MessageHandler, filters, ContextTypes

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("BOT_ADMIN").split(",")]

USERS_FILE = "users.json"
PROXY_FILE = "proxies.json"

# =========================
# LOAD / SAVE
# =========================
def load_json(file, default):
    if not os.path.exists(file):
        return default
    with open(file, "r") as f:
        return json.load(f)

def save_json(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)

users = load_json(USERS_FILE, {})
proxies_data = load_json(PROXY_FILE, {"enabled": False, "list": []})

# =========================
# USER SYSTEM
# =========================
def get_user(uid):
    uid = str(uid)
    if uid not in users:
        users[uid] = {"premium": False, "banned": False}
    return users[uid]

def is_admin(uid):
    return uid in ADMIN_IDS

# =========================
# INSTAGRAM CHECK (FIXED)
# =========================
def check_username(username):
    url = f"https://www.instagram.com/{username}/"
    headers = {"User-Agent": "Mozilla/5.0"}

    proxy = None
    if proxies_data["enabled"] and proxies_data["list"]:
        try:
            p = random.choice(proxies_data["list"])
            host, port, user, pwd = p.split(":")
            proxy_url = f"http://{user}:{pwd}@{host}:{port}"
            proxy = {"http": proxy_url, "https": proxy_url}
        except:
            proxy = None

    for _ in range(3):
        try:
            r = requests.get(url, headers=headers, proxies=proxy, timeout=8)
            html = r.text

            if f'rel="alternate" href="https://www.instagram.com/{username}/"' in html:
                return "EXISTS"
            return "NOT_EXIST"

        except:
            continue

    return "ERROR"

# =========================
# BASIC CMDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome to IG Checker Bot\nUse /cmds")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start = time.time()
    msg = await update.message.reply_text("🏓 Pinging...")
    end = round((time.time() - start)*1000,2)
    await msg.edit_text(f"⚡ {end} ms")

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    data = get_user(u.id)

    await update.message.reply_text(
        f"👤 {u.full_name}\n"
        f"🔗 @{u.username}\n"
        f"🆔 {u.id}\n"
        f"⭐ Premium: {data['premium']}\n"
        f"🚫 Banned: {data['banned']}"
    )

# =========================
# CMD LIST
# =========================
async def cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    text = "📜 Commands:\n\n"

    text += "🔹 Free:\n/id\n/ping\n\n"
    text += "💎 Premium:\n/chk\n\n"

    if is_admin(uid):
        text += "👑 Admin:\n/approve\n/revoke\n/ban\n/unban\n/proxy\n"

    await update.message.reply_text(text)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 Usage:\n\n"
        "/chk username1 username2\n"
        "or reply to txt file\n\n"
        "Admin cmds manage users & proxy"
    )

# =========================
# /CHK FIXED
# =========================
async def chk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id
    user = get_user(uid)

    if user["banned"]:
        return await update.message.reply_text("🚫 Banned")

    if not user["premium"] and not is_admin(uid):
        return await update.message.reply_text("❌ Premium only")

    usernames = []

    if context.args:
        usernames += context.args

    if update.message.reply_to_message and update.message.reply_to_message.document:
        file = await update.message.reply_to_message.document.get_file()
        content = await file.download_as_bytearray()
        usernames += content.decode().splitlines()

    if not usernames:
        return await update.message.reply_text("⚠️ Send usernames")

    msg = await update.message.reply_text("⏳ Checking...")

    start = time.time()

    exists, not_exist, errors = [], [], []

    for u in usernames:
        u = u.strip()
        if not u:
            continue

        res = await asyncio.to_thread(check_username, u)

        if res == "EXISTS":
            exists.append(u)
        elif res == "NOT_EXIST":
            not_exist.append(u)
        else:
            errors.append(u)

    took = round(time.time() - start, 2)

    # save files
    open("exists.txt","w").write("\n".join(exists))
    open("not.txt","w").write("\n".join(not_exist))

    text = (
        f"✅ Done\n\n"
        f"Total: {len(usernames)}\n"
        f"Exists: {len(exists)}\n"
        f"Not Exist: {len(not_exist)}\n"
        f"Errors: {len(errors)}\n"
        f"Time: {took}s"
    )

    buttons = InlineKeyboardMarkup([
        [InlineKeyboardButton("Exists", callback_data="ex")],
        [InlineKeyboardButton("Not Exist", callback_data="no")]
    ])

    await msg.edit_text(text, reply_markup=buttons)

# =========================
# BUTTON
# =========================
async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    q = update.callback_query
    await q.answer()

    if q.data == "ex":
        await q.message.reply_document(InputFile("exists.txt"))
    elif q.data == "no":
        await q.message.reply_document(InputFile("not.txt"))

# =========================
# ADMIN
# =========================
async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    uid = context.args[0]
    get_user(uid)["premium"] = True
    save_json(USERS_FILE, users)
    await update.message.reply_text("✅ Approved")

async def revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    uid = context.args[0]
    get_user(uid)["premium"] = False
    save_json(USERS_FILE, users)
    await update.message.reply_text("❌ Revoked")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    uid = context.args[0]
    get_user(uid)["banned"] = True
    save_json(USERS_FILE, users)
    await update.message.reply_text("🚫 Banned")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    uid = context.args[0]
    get_user(uid)["banned"] = False
    save_json(USERS_FILE, users)
    await update.message.reply_text("✅ Unbanned")

# =========================
# MAIN
# =========================
app = ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start", start))
app.add_handler(CommandHandler("ping", ping))
app.add_handler(CommandHandler("id", id_cmd))
app.add_handler(CommandHandler("cmds", cmds))
app.add_handler(CommandHandler("help", help_cmd))
app.add_handler(CommandHandler("chk", chk))

app.add_handler(CommandHandler("approve", approve))
app.add_handler(CommandHandler("revoke", revoke))
app.add_handler(CommandHandler("ban", ban))
app.add_handler(CommandHandler("unban", unban))

app.add_handler(MessageHandler(filters.Document.ALL, chk))
app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, chk))

app.add_handler(MessageHandler(filters.ALL, btn))

print("🚀 Bot Running")
app.run_polling()
