import os, json, time, asyncio, requests, random
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler,
    CallbackQueryHandler, filters, ContextTypes
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("BOT_ADMIN").split(",")]

USERS_FILE = "users.json"
PROXY_FILE = "proxies.json"

# =========================
# LOAD / SAVE
# =========================
def load_json(f, d):
    return json.load(open(f)) if os.path.exists(f) else d

def save_json(f, d):
    json.dump(d, open(f, "w"), indent=4)

users = load_json(USERS_FILE, {})
proxies = load_json(PROXY_FILE, {"enabled": False, "list": []})

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
# IG CHECK
# =========================
def check_username(username):
    url = f"https://www.instagram.com/{username}/"
    headers = {"User-Agent": "Mozilla/5.0"}

    proxy = None
    if proxies["enabled"] and proxies["list"]:
        try:
            p = random.choice(proxies["list"])
            host, port, user, pwd = p.split(":")
            proxy_url = f"http://{user}:{pwd}@{host}:{port}"
            proxy = {"http": proxy_url, "https": proxy_url}
        except:
            proxy = None

    for _ in range(3):
        try:
            r = requests.get(url, headers=headers, proxies=proxy, timeout=8)
            if f'rel="alternate" href="https://www.instagram.com/{username}/"' in r.text:
                return "EXISTS"
            return "NOT_EXIST"
        except:
            continue
    return "ERROR"

# =========================
# BASIC CMDS
# =========================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("👋 Welcome\nUse /cmds")

async def ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start = time.time()
    msg = await update.message.reply_text("🏓...")
    await msg.edit_text(f"⚡ {round((time.time()-start)*1000,2)} ms")

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    u = update.effective_user
    data = get_user(u.id)

    await update.message.reply_text(
        f"👤 {u.full_name}\n@{u.username}\nID: {u.id}\n"
        f"Premium: {data['premium']}\nBanned: {data['banned']}"
    )

# =========================
# CMDS / HELP
# =========================
async def cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = update.effective_user.id

    txt = "📜 Commands\n\nFree:\n/id\n/ping\n\nPremium:\n/chk\n\n"

    if is_admin(uid):
        txt += "Admin:\n/approve id\n/revoke id\n/ban id\n/unban id\n/proxy"

    await update.message.reply_text(txt)

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "/chk user1 user2\nor reply txt\n\nAdmin: manage users + proxy"
    )

# =========================
# CHK (FIXED)
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
        data = await file.download_as_bytearray()
        usernames += data.decode().splitlines()

    if not usernames:
        return await update.message.reply_text("⚠️ Send usernames")

    msg = await update.message.reply_text("⏳ Checking...")

    exists, not_exist, errors = [], [], []
    start = time.time()

    for u in usernames:
        u = u.strip()
        if not u: continue

        res = await asyncio.to_thread(check_username, u)

        if res == "EXISTS": exists.append(u)
        elif res == "NOT_EXIST": not_exist.append(u)
        else: errors.append(u)

    took = round(time.time()-start,2)

    open("exists.txt","w").write("\n".join(exists))
    open("not.txt","w").write("\n".join(not_exist))

    txt = f"""
✅ Done

Total: {len(usernames)}
Exists: {len(exists)}
Not: {len(not_exist)}
Errors: {len(errors)}
Time: {took}s
"""

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("Exists", callback_data="ex")],
        [InlineKeyboardButton("Not", callback_data="no")]
    ])

    await msg.edit_text(txt, reply_markup=kb)

# =========================
# BUTTON FIX
# =========================
async def btn(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.callback_query:
        return

    q = update.callback_query
    await q.answer()

    if q.data == "ex":
        await q.message.reply_document(InputFile("exists.txt"))
    elif q.data == "no":
        await q.message.reply_document(InputFile("not.txt"))

# =========================
# ADMIN FIX
# =========================
def require_arg(update, context):
    if not context.args:
        return update.message.reply_text("⚠️ Give user ID")
    return context.args[0]

async def approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    uid = require_arg(update, context)
    if not uid: return
    get_user(uid)["premium"] = True
    save_json(USERS_FILE, users)
    await update.message.reply_text("✅ Approved")

async def revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    uid = require_arg(update, context)
    if not uid: return
    get_user(uid)["premium"] = False
    save_json(USERS_FILE, users)
    await update.message.reply_text("❌ Revoked")

async def ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    uid = require_arg(update, context)
    if not uid: return
    get_user(uid)["banned"] = True
    save_json(USERS_FILE, users)
    await update.message.reply_text("🚫 Banned")

async def unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not is_admin(update.effective_user.id): return
    uid = require_arg(update, context)
    if not uid: return
    get_user(uid)["banned"] = False
    save_json(USERS_FILE, users)
    await update.message.reply_text("✅ Unbanned")

# =========================
# ERROR HANDLER
# =========================
async def error(update, context):
    print("ERROR:", context.error)

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

app.add_handler(CallbackQueryHandler(btn))

app.add_error_handler(error)

print("🚀 Bot Running")
app.run_polling()
