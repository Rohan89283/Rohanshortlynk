import os, json, time, zipfile, random, requests, psutil
from concurrent.futures import ThreadPoolExecutor
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, ContextTypes,
    CallbackQueryHandler, MessageHandler, filters
)

# ========= ENV =========
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_ADMIN = int(os.getenv("BOT_ADMIN"))

THREADS = 10
START_TIME = time.time()

DATA_FILE = "users.json"
LOG_FILE = "bot.log"
PROXY_FILE = "proxies.json"

# ========= INIT =========
if not os.path.exists(DATA_FILE):
    json.dump({"approved": {}, "banned": []}, open(DATA_FILE, "w"))

if not os.path.exists(PROXY_FILE):
    json.dump({"proxies": [], "enabled_cmds": {}}, open(PROXY_FILE, "w"))

# ========= HELPERS =========
def load_data(): return json.load(open(DATA_FILE))
def save_data(d): json.dump(d, open(DATA_FILE, "w"), indent=2)

def load_proxies(): return json.load(open(PROXY_FILE))
def save_proxies(d): json.dump(d, open(PROXY_FILE, "w"), indent=2)

def log(t):
    print(t)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(t + "\n")

def is_admin(uid): return uid == BOT_ADMIN

def is_approved(uid, cmd):
    d = load_data()
    if uid == BOT_ADMIN: return True
    if uid in d["banned"]: return False
    return str(uid) in d["approved"] and (
        cmd in d["approved"][str(uid)] or "all" in d["approved"][str(uid)]
    )

def extract(text):
    out = []
    for l in text.splitlines():
        l = l.strip().replace("@","")
        if l: out.extend(l.split())
    return out

# ========= PROXY =========
def format_proxy(p):
    # supports ip:port OR ip:port:user:pass
    parts = p.split(":")
    if len(parts) == 4:
        host, port, user, pwd = parts
        return f"http://{user}:{pwd}@{host}:{port}"
    return f"http://{p}"

def get_proxy(cmd):
    d = load_proxies()
    if not d["enabled_cmds"].get(cmd): return None
    if not d["proxies"]: return None

    p = random.choice(d["proxies"])
    proxy_url = format_proxy(p)

    return {"http": proxy_url, "https": proxy_url}

# ========= SESSION =========
session = requests.Session()
headers = {"User-Agent": "Mozilla/5.0"}

# ========= CHECK =========
def check(username):
    url = f"https://www.instagram.com/{username}/"
    proxy = get_proxy("chk")

    try:
        res = session.get(url, headers=headers, timeout=10, proxies=proxy)
        html = res.text

        if f'rel="alternate" href="https://www.instagram.com/{username}/"' in html:
            result = f"{username} → ✅"
        else:
            result = f"{username} → ❌"

    except Exception as e:
        result = f"{username} → ⚠️"
        log(f"ERR {username}: {e}")

    log(result)
    return result

# ========= BASIC =========
async def start(u, c): await u.message.reply_text("👋 Welcome")

async def cmds(u, c):
    uid = u.effective_user.id
    msg = "📜 Commands\n\nBasic:\n/start /help /id /ping\n\nPro:\n/chk\n"
    if is_admin(uid):
        msg += "\nAdmin:\n/approve /revoke /ban /unban /log /ram /backup /restore /proxy"
    await u.message.reply_text(msg)

async def help_cmd(u,c): await u.message.reply_text("/chk username or txt")

async def id_cmd(u,c):
    user=u.effective_user
    await u.message.reply_text(f"ID:{user.id}\n@{user.username}")

async def ping(u,c):
    await u.message.reply_text(f"Uptime: {int(time.time()-START_TIME)}s")

# ========= PRO =========
async def chk(u, c):
    uid = u.effective_user.id
    if not is_approved(uid,"chk"):
        await u.message.reply_text("❌ Not approved")
        return

    users=[]
    if c.args: users.extend(c.args)
    if u.message.text: users.extend(extract(u.message.text.replace("/chk","")))

    if u.message.reply_to_message:
        doc=u.message.reply_to_message.document
        if doc and doc.file_name.endswith(".txt"):
            f=await c.bot.get_file(doc.file_id)
            users.extend(extract((await f.download_as_bytearray()).decode()))

    if not users:
        await u.message.reply_text("No users")
        return

    users=list(set(users))
    await u.message.reply_text(f"Checking {len(users)}...")

    with ThreadPoolExecutor(max_workers=THREADS) as ex:
        res=list(ex.map(check, users))

    await u.message.reply_text("\n".join(res))

# ========= ADMIN =========
async def approve(u,c):
    if not is_admin(u.effective_user.id): return
    uid,cmd=c.args
    d=load_data()
    d["approved"].setdefault(uid,[]).append(cmd)
    save_data(d)
    await u.message.reply_text("Approved")

async def revoke(u,c):
    if not is_admin(u.effective_user.id): return
    uid=c.args[0]
    d=load_data()
    d["approved"].pop(uid,None)
    save_data(d)
    await u.message.reply_text("Revoked")

async def ban(u,c):
    if not is_admin(u.effective_user.id): return
    uid=int(c.args[0])
    d=load_data(); d["banned"].append(uid)
    save_data(d)
    await u.message.reply_text("Banned")

async def unban(u,c):
    if not is_admin(u.effective_user.id): return
    uid=int(c.args[0])
    d=load_data()
    if uid in d["banned"]: d["banned"].remove(uid)
    save_data(d)
    await u.message.reply_text("Unbanned")

async def log_cmd(u,c):
    if not is_admin(u.effective_user.id): return
    if os.path.exists(LOG_FILE):
        await u.message.reply_document(open(LOG_FILE,"rb"))

async def ram(u,c):
    mem=psutil.virtual_memory()
    await u.message.reply_text(f"RAM {mem.percent}%")

async def backup(u,c):
    z="backup.zip"
    with zipfile.ZipFile(z,"w") as zz:
        for f in os.listdir():
            zz.write(f)
    await u.message.reply_document(open(z,"rb"))

async def restore(u,c):
    if u.message.reply_to_message:
        doc=u.message.reply_to_message.document
        f=await c.bot.get_file(doc.file_id)
        await f.download_to_drive("restore.zip")
        with zipfile.ZipFile("restore.zip") as z:
            z.extractall()
        await u.message.reply_text("Restored")

# ========= PROXY UI =========
async def proxy(u,c):
    if not is_admin(u.effective_user.id): return
    kb=[
        [InlineKeyboardButton("➕ Add",callback_data="p_add")],
        [InlineKeyboardButton("➖ Remove",callback_data="p_del")],
        [InlineKeyboardButton("🧪 Test",callback_data="p_test")],
        [InlineKeyboardButton("⚙ Toggle /chk",callback_data="p_toggle")]
    ]
    await u.message.reply_text("Proxy Panel",reply_markup=InlineKeyboardMarkup(kb))

async def proxy_btn(u,c):
    q=u.callback_query
    await q.answer()
    d=load_proxies()

    if q.data=="p_add":
        c.user_data["pm"]="add"
        await q.message.reply_text("Send proxies")

    elif q.data=="p_del":
        c.user_data["pm"]="del"
        await q.message.reply_text("Send proxy to remove")

    elif q.data=="p_test":
        out=[]
        for p in d["proxies"]:
            try:
                requests.get("https://httpbin.org/ip",
                    proxies={"http":format_proxy(p),"https":format_proxy(p)},
                    timeout=5)
                out.append(p+" → ✅")
            except:
                out.append(p+" → ❌")
        await q.message.reply_text("\n".join(out))

    elif q.data=="p_toggle":
        st=d["enabled_cmds"].get("chk",False)
        d["enabled_cmds"]["chk"]=not st
        save_proxies(d)
        await q.message.reply_text(f"/chk proxy {'ON' if not st else 'OFF'}")

async def proxy_input(u,c):
    if not is_admin(u.effective_user.id): return
    if "pm" not in c.user_data: return

    d=load_proxies()
    txt=u.message.text.splitlines()

    if c.user_data["pm"]=="add":
        d["proxies"].extend(txt)
        d["proxies"]=list(set(d["proxies"]))
        save_proxies(d)
        await u.message.reply_text("Added")

    elif c.user_data["pm"]=="del":
        for t in txt:
            if t in d["proxies"]: d["proxies"].remove(t)
        save_proxies(d)
        await u.message.reply_text("Removed")

    c.user_data.pop("pm")

# ========= MAIN =========
def main():
    app=ApplicationBuilder().token(BOT_TOKEN).build()

    # basic
    app.add_handler(CommandHandler("start",start))
    app.add_handler(CommandHandler("cmds",cmds))
    app.add_handler(CommandHandler("help",help_cmd))
    app.add_handler(CommandHandler("id",id_cmd))
    app.add_handler(CommandHandler("ping",ping))

    # pro
    app.add_handler(CommandHandler("chk",chk))

    # admin
    app.add_handler(CommandHandler("approve",approve))
    app.add_handler(CommandHandler("revoke",revoke))
    app.add_handler(CommandHandler("ban",ban))
    app.add_handler(CommandHandler("unban",unban))
    app.add_handler(CommandHandler("log",log_cmd))
    app.add_handler(CommandHandler("ram",ram))
    app.add_handler(CommandHandler("backup",backup))
    app.add_handler(CommandHandler("restore",restore))
    app.add_handler(CommandHandler("proxy",proxy))

    app.add_handler(CallbackQueryHandler(proxy_btn))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, proxy_input))

    print("🔥 BOT RUNNING")
    app.run_polling()

if __name__=="__main__":
    main()
