import os, json, time, asyncio, requests, random
from datetime import datetime
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import (
    ApplicationBuilder, CommandHandler, CallbackQueryHandler,
    ContextTypes
)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("BOT_ADMIN").split(",")]

start_time = time.time()

USERS_FILE = "users.json"

# =========================
# JSON
# =========================
def load(f, d): return json.load(open(f)) if os.path.exists(f) else d
def save(f, d): json.dump(d, open(f,"w"), indent=4)

users = load(USERS_FILE, {})

def get_user(uid):
    uid=str(uid)
    if uid not in users:
        users[uid]={"premium":False,"banned":False}
    return users[uid]

def is_admin(uid): return uid in ADMIN_IDS

# =========================
# IG CHECK
# =========================
def check_username(u):
    try:
        r = requests.get(f"https://www.instagram.com/{u}/",
                         headers={"User-Agent":"Mozilla/5.0"},timeout=8)
        if f'rel="alternate" href="https://www.instagram.com/{u}/"' in r.text:
            return "✅ EXISTS"
        return "❌ NOT EXIST"
    except:
        return "⚠️ ERROR"

# =========================
# START
# =========================
async def start(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 *Welcome to IG Checker Bot*\n\n"
        "Use /cmds to see commands",
        parse_mode="Markdown"
    )

# =========================
# CMDS LIST
# =========================
async def cmds(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id

    txt = "📜 *Command List*\n\n"

    txt += "🔹 *Free*\n"
    txt += "/id - your info\n"
    txt += "/ping - bot speed\n\n"

    txt += "💎 *Premium*\n"
    txt += "/chk - check usernames\n\n"

    if is_admin(uid):
        txt += "👑 *Admin*\n"
        txt += "/approve id\n/revoke id\n/ban id\n/unban id\n"

    await update.message.reply_text(txt, parse_mode="Markdown")

# =========================
# HELP
# =========================
async def help_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "🧠 *Help*\n\n"
        "➡ /chk username1 username2\n"
        "➡ Or reply to txt file\n\n"
        "Returns:\n"
        "- username result\n"
        "- summary\n"
        "- download buttons",
        parse_mode="Markdown"
    )

# =========================
# PING
# =========================
async def ping(update:Update,context:ContextTypes.DEFAULT_TYPE):
    latency = round((time.time()-start_time),2)
    await update.message.reply_text(
        f"🏓 *PONG*\n\n"
        f"⚡ Uptime: {latency}s",
        parse_mode="Markdown"
    )

# =========================
# ID
# =========================
async def id_cmd(update:Update,context:ContextTypes.DEFAULT_TYPE):
    u=update.effective_user
    d=get_user(u.id)

    await update.message.reply_text(
        f"👤 *User Info*\n\n"
        f"Name: {u.full_name}\n"
        f"Username: @{u.username}\n"
        f"ID: `{u.id}`\n\n"
        f"Premium: {d['premium']}\n"
        f"Banned: {d['banned']}",
        parse_mode="Markdown"
    )

# =========================
# CHK (PRO VERSION)
# =========================
async def chk(update:Update,context:ContextTypes.DEFAULT_TYPE):
    uid=update.effective_user.id
    user=get_user(uid)

    if user["banned"]:
        return await update.message.reply_text("🚫 Banned")

    if not user["premium"] and not is_admin(uid):
        return await update.message.reply_text("❌ Premium required")

    usernames = context.args

    if not usernames:
        return await update.message.reply_text("⚠️ Send usernames")

    msg = await update.message.reply_text("⏳ Checking...")

    results=[]
    exists=[]
    not_exist=[]

    start=time.time()

    for u in usernames:
        res = await asyncio.to_thread(check_username,u)
        results.append(f"{u} → {res}")

        if "EXISTS" in res: exists.append(u)
        elif "NOT" in res: not_exist.append(u)

    took=round(time.time()-start,2)

    open("exists.txt","w").write("\n".join(exists))
    open("not.txt","w").write("\n".join(not_exist))
    open("results.txt","w").write("\n".join(results))

    text = "📊 *Results*\n\n"
    text += "\n".join(results[:20])  # show first 20
    text += f"\n\nTotal: {len(usernames)}"
    text += f"\nExists: {len(exists)}"
    text += f"\nNot Exist: {len(not_exist)}"
    text += f"\nTime: {took}s"

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("📄 Exists",callback_data="ex")],
        [InlineKeyboardButton("📄 Not Exist",callback_data="no")],
        [InlineKeyboardButton("📄 All",callback_data="all")]
    ])

    await msg.edit_text(text,parse_mode="Markdown",reply_markup=kb)

# =========================
# BUTTONS
# =========================
async def btn(update:Update,context:ContextTypes.DEFAULT_TYPE):
    q=update.callback_query
    if not q: return
    await q.answer()

    if q.data=="ex":
        await q.message.reply_document(InputFile("exists.txt"))
    elif q.data=="no":
        await q.message.reply_document(InputFile("not.txt"))
    elif q.data=="all":
        await q.message.reply_document(InputFile("results.txt"))

# =========================
# ADMIN SAFE
# =========================
def arg_check(update,context):
    if not context.args:
        return update.message.reply_text("⚠️ Give user ID")
    return context.args[0]

async def approve(update,context):
    if not is_admin(update.effective_user.id): return
    uid=arg_check(update,context)
    if not uid: return
    get_user(uid)["premium"]=True
    save(USERS_FILE,users)
    await update.message.reply_text("✅ Approved")

async def revoke(update,context):
    if not is_admin(update.effective_user.id): return
    uid=arg_check(update,context)
    if not uid: return
    get_user(uid)["premium"]=False
    save(USERS_FILE,users)
    await update.message.reply_text("❌ Revoked")

async def ban(update,context):
    if not is_admin(update.effective_user.id): return
    uid=arg_check(update,context)
    if not uid: return
    get_user(uid)["banned"]=True
    save(USERS_FILE,users)
    await update.message.reply_text("🚫 Banned")

async def unban(update,context):
    if not is_admin(update.effective_user.id): return
    uid=arg_check(update,context)
    if not uid: return
    get_user(uid)["banned"]=False
    save(USERS_FILE,users)
    await update.message.reply_text("✅ Unbanned")

# =========================
# MAIN
# =========================
app=ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(CommandHandler("cmds",cmds))
app.add_handler(CommandHandler("help",help_cmd))
app.add_handler(CommandHandler("ping",ping))
app.add_handler(CommandHandler("id",id_cmd))
app.add_handler(CommandHandler("chk",chk))

app.add_handler(CommandHandler("approve",approve))
app.add_handler(CommandHandler("revoke",revoke))
app.add_handler(CommandHandler("ban",ban))
app.add_handler(CommandHandler("unban",unban))

app.add_handler(CallbackQueryHandler(btn))

print("🚀 Bot Running")
app.run_polling()
