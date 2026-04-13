# =========================
# IMPORTS
# =========================
import os, re, json, time, html, random, asyncio, requests, logging, psutil, shutil, zipfile, gc
from pathlib import Path
from telegram import Update, InlineKeyboardMarkup, InlineKeyboardButton, InputFile
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler, ContextTypes
from telegram.constants import ParseMode

# =========================
# CONFIG
# =========================
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS = [int(x) for x in os.getenv("BOT_ADMIN").split(",")]

BASE = Path(".")
DATA = BASE / "data"
TMP = BASE / "tmp"
LOG = BASE / "logs"

DATA.mkdir(exist_ok=True)
TMP.mkdir(exist_ok=True)
LOG.mkdir(exist_ok=True)

USERS_FILE = DATA / "users.json"
PROXY_FILE = DATA / "proxies.json"
LOG_FILE = LOG / "bot.log"

# =========================
# JSON
# =========================
def load(p, d): return json.load(open(p)) if p.exists() else d
def save(p, d): json.dump(d, open(p,"w"), indent=2)

users = load(USERS_FILE, {})
proxies = load(PROXY_FILE, {"items": [], "chk": False})

# =========================
# USER SYSTEM
# =========================
def is_admin(uid): return uid in ADMIN_IDS

def get_user(uid):
    uid=str(uid)
    if uid not in users:
        users[uid]={"ban":False,"chk":False}
    save(USERS_FILE,users)
    return users[uid]

# =========================
# PROXY
# =========================
def build_proxy():
    if not proxies["chk"] or not proxies["items"]:
        return None
    try:
        h,p,u,pw=random.choice(proxies["items"]).split(":")
        url=f"http://{u}:{pw}@{h}:{p}"
        return {"http":url,"https":url}
    except: return None

# =========================
# IG CHECK
# =========================
def check(u):
    url=f"https://www.instagram.com/{u}/"
    for _ in range(3):
        try:
            r=requests.get(url,headers={"User-Agent":"Mozilla/5.0"},proxies=build_proxy(),timeout=10)
            if f'/{u}/' in r.text:
                return "EXISTS"
            return "NOT"
        except: pass
    return "ERR"

async def run_check(list_u):
    res=[];ex=[];no=[];er=[]
    for u in list_u:
        r=await asyncio.to_thread(check,u)
        res.append(f"{u} -> {r}")
        if r=="EXISTS": ex.append(u)
        elif r=="NOT": no.append(u)
        else: er.append(u)
    return res,ex,no,er

# =========================
# BASIC CMDS
# =========================
async def start(update,ctx):
    await update.message.reply_text("<b>IG BOT</b>\nUse /cmds",parse_mode="HTML")

async def cmds(update,ctx):
    t="🔹 Free:\n/id\n/ping\n\n💎 Premium:\n/chk\n"
    if is_admin(update.effective_user.id):
        t+="\n👑 Admin:\n/approve id\n/revoke id\n/ban id\n/unban id\n/proxy\n/ram\n/cleanram\n/log\n/backup\n"
    await update.message.reply_text(t)

async def help_cmd(update,ctx):
    await update.message.reply_text("/chk user1 user2\nor reply txt")

async def id_cmd(update,ctx):
    u=update.effective_user
    d=get_user(u.id)
    txt=(
        f"👤 {u.full_name}\n"
        f"ID: {u.id}\n"
        f"CHK: {d['chk']}\n"
        f"Banned: {d['ban']}"
    )
    await update.message.reply_text(txt)

async def ping(update,ctx):
    await update.message.reply_text("🏓 OK")

# =========================
# CHK
# =========================
async def chk(update,ctx):
    uid=update.effective_user.id
    if not get_user(uid)["chk"] and not is_admin(uid):
        return await update.message.reply_text("❌ No access")

    users_list=[]

    if ctx.args:
        users_list+=ctx.args

    if update.message.reply_to_message and update.message.reply_to_message.document:
        f=await update.message.reply_to_message.document.get_file()
        d=await f.download_as_bytearray()
        users_list+=d.decode().splitlines()

    users_list=[u.strip() for u in users_list if u.strip()]
    if not users_list:
        return await update.message.reply_text("No usernames")

    m=await update.message.reply_text("Checking...")

    res,ex,no,er=await run_check(users_list)

    open(TMP/"ex.txt","w").write("\n".join(ex))
    open(TMP/"no.txt","w").write("\n".join(no))
    open(TMP/"all.txt","w").write("\n".join(res))

    txt="\n".join(res[:20])
    txt+=f"\n\nTotal:{len(users_list)}\nEX:{len(ex)} NO:{len(no)} ER:{len(er)}"

    kb=InlineKeyboardMarkup([
        [InlineKeyboardButton("Exists",callback_data="ex")],
        [InlineKeyboardButton("Not Exists",callback_data="no")],
        [InlineKeyboardButton("All",callback_data="all")]
    ])

    await m.edit_text(txt,reply_markup=kb)

# =========================
# BUTTON
# =========================
async def btn(update,ctx):
    q=update.callback_query
    await q.answer()

    if q.data=="ex":
        await q.message.reply_document(InputFile(str(TMP/"ex.txt")))
    elif q.data=="no":
        await q.message.reply_document(InputFile(str(TMP/"no.txt")))
    else:
        await q.message.reply_document(InputFile(str(TMP/"all.txt")))

# =========================
# ADMIN
# =========================
async def approve(update,ctx):
    if not is_admin(update.effective_user.id): return
    if not ctx.args: return await update.message.reply_text("ID?")
    get_user(ctx.args[0])["chk"]=True
    save(USERS_FILE,users)
    await update.message.reply_text("Approved")

async def revoke(update,ctx):
    if not is_admin(update.effective_user.id): return
    if not ctx.args: return
    get_user(ctx.args[0])["chk"]=False
    save(USERS_FILE,users)
    await update.message.reply_text("Revoked")

async def ban(update,ctx):
    if not is_admin(update.effective_user.id): return
    if not ctx.args: return
    get_user(ctx.args[0])["ban"]=True
    save(USERS_FILE,users)
    await update.message.reply_text("Banned")

async def unban(update,ctx):
    if not is_admin(update.effective_user.id): return
    if not ctx.args: return
    get_user(ctx.args[0])["ban"]=False
    save(USERS_FILE,users)
    await update.message.reply_text("Unbanned")

async def proxy(update,ctx):
    if not is_admin(update.effective_user.id): return

    if not ctx.args:
        return await update.message.reply_text(f"Proxy:{proxies['chk']} Count:{len(proxies['items'])}")

    c=ctx.args[0]

    if c=="on": proxies["chk"]=True
    elif c=="off": proxies["chk"]=False
    elif c=="add": proxies["items"].append(ctx.args[1])
    elif c=="del": proxies["items"].remove(ctx.args[1])

    save(PROXY_FILE,proxies)
    await update.message.reply_text("Done")

# =========================
# SYSTEM
# =========================
async def ram(update,ctx):
    if not is_admin(update.effective_user.id): return
    m=psutil.virtual_memory()
    await update.message.reply_text(f"RAM:{m.percent}%")

async def cleanram(update,ctx):
    if not is_admin(update.effective_user.id): return
    for f in TMP.glob("*"):
        try: f.unlink()
        except: pass
    gc.collect()
    await update.message.reply_text("Cleaned")

async def log(update,ctx):
    if not is_admin(update.effective_user.id): return
    if LOG_FILE.exists():
        await update.message.reply_document(InputFile(str(LOG_FILE)))

async def backup(update,ctx):
    if not is_admin(update.effective_user.id): return
    z=TMP/"backup.zip"
    with zipfile.ZipFile(z,"w") as zipf:
        for f in [USERS_FILE,PROXY_FILE]:
            if f.exists(): zipf.write(f)
    await update.message.reply_document(InputFile(str(z)))

# =========================
# MAIN
# =========================
app=ApplicationBuilder().token(BOT_TOKEN).build()

app.add_handler(CommandHandler("start",start))
app.add_handler(CommandHandler("cmds",cmds))
app.add_handler(CommandHandler("help",help_cmd))
app.add_handler(CommandHandler("id",id_cmd))
app.add_handler(CommandHandler("ping",ping))
app.add_handler(CommandHandler("chk",chk))

app.add_handler(CommandHandler("approve",approve))
app.add_handler(CommandHandler("revoke",revoke))
app.add_handler(CommandHandler("ban",ban))
app.add_handler(CommandHandler("unban",unban))
app.add_handler(CommandHandler("proxy",proxy))
app.add_handler(CommandHandler("ram",ram))
app.add_handler(CommandHandler("cleanram",cleanram))
app.add_handler(CommandHandler("log",log))
app.add_handler(CommandHandler("backup",backup))

app.add_handler(CallbackQueryHandler(btn))

print("🚀 BOT RUNNING")
app.run_polling()
