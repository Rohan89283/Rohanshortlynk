import io
import os
import gc
import re
import json
import time
import zipfile
import random
import shutil
import platform
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor

import psutil
import requests
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    ContextTypes,
    CallbackQueryHandler,
    MessageHandler,
    filters,
)

# =========================================================
# ENV
# =========================================================
BOT_TOKEN = os.getenv("BOT_TOKEN")
BOT_ADMIN = os.getenv("BOT_ADMIN")

if not BOT_TOKEN:
    raise RuntimeError("BOT_TOKEN is missing in environment variables.")

if not BOT_ADMIN:
    raise RuntimeError("BOT_ADMIN is missing in environment variables.")

BOT_ADMIN = int(BOT_ADMIN)

# =========================================================
# SETTINGS
# =========================================================
THREADS = 10
SAFE_THREADS_NO_PROXY = 3
REQUEST_TIMEOUT = 10
RETRY_DELAY = 1.2
START_TIME = time.time()

DATA_FILE = "users.json"
LOG_FILE = "bot.log"
PROXY_FILE = "proxies.json"

headers = {
    "User-Agent": "Mozilla/5.0"
}

# =========================================================
# INIT FILES
# =========================================================
def ensure_json_file(path: str, default_data: dict) -> None:
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(default_data, f, indent=2)

ensure_json_file(DATA_FILE, {"approved": {}, "banned": []})
ensure_json_file(PROXY_FILE, {"proxies": [], "enabled_cmds": {"chk": False}})

# =========================================================
# LOGGING
# =========================================================
def log(text: str) -> None:
    stamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
    line = f"[{stamp}] {text}"
    print(line, flush=True)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line + "\n")

# =========================================================
# DATA HELPERS
# =========================================================
def load_data() -> dict:
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_data(data: dict) -> None:
    with open(DATA_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

def load_proxies() -> dict:
    with open(PROXY_FILE, "r", encoding="utf-8") as f:
        return json.load(f)

def save_proxies(data: dict) -> None:
    with open(PROXY_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2)

# =========================================================
# AUTH / PERMISSIONS
# =========================================================
def is_admin(user_id: int) -> bool:
    return user_id == BOT_ADMIN

def is_banned(user_id: int) -> bool:
    data = load_data()
    return user_id in data.get("banned", [])

def is_approved(user_id: int, cmd: str) -> bool:
    if is_admin(user_id):
        return True

    data = load_data()

    if user_id in data.get("banned", []):
        return False

    approved = data.get("approved", {})
    user_cmds = approved.get(str(user_id), [])
    return cmd in user_cmds or "all" in user_cmds

# =========================================================
# INPUT HELPERS
# =========================================================
USERNAME_RE = re.compile(r"^[A-Za-z0-9._]{1,30}$")

def clean_username(username: str) -> str:
    return username.strip().replace("@", "")

def is_valid_username(username: str) -> bool:
    return bool(USERNAME_RE.fullmatch(username))

def extract_usernames(text: str) -> list[str]:
    usernames = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue

        parts = line.split()
        for part in parts:
            part = clean_username(part)
            if part and part.lower() != "chk" and is_valid_username(part):
                usernames.append(part)

    seen = set()
    final = []
    for u in usernames:
        if u not in seen:
            seen.add(u)
            final.append(u)
    return final

def reply_id(update: Update) -> int | None:
    if update.message:
        return update.message.message_id
    if update.callback_query and update.callback_query.message:
        return update.callback_query.message.message_id
    return None

# =========================================================
# PROXY HELPERS
# =========================================================
def format_proxy(proxy_line: str) -> str:
    """
    Supports:
    host:port
    host:port:user:pass
    """
    parts = proxy_line.strip().split(":")
    if len(parts) == 2:
        host, port = parts
        return f"http://{host}:{port}"
    if len(parts) == 4:
        host, port, user, password = parts
        return f"http://{user}:{password}@{host}:{port}"
    raise ValueError(f"Invalid proxy format: {proxy_line}")

def get_proxy_for_request(cmd: str) -> dict | None:
    data = load_proxies()
    enabled = data.get("enabled_cmds", {}).get(cmd, False)
    proxies = data.get("proxies", [])

    if not enabled or not proxies:
        return None

    chosen = random.choice(proxies)
    proxy_url = format_proxy(chosen)
    return {"http": proxy_url, "https": proxy_url}

def proxy_status_text() -> str:
    data = load_proxies()
    proxies = data.get("proxies", [])
    enabled_cmds = data.get("enabled_cmds", {})
    chk_enabled = enabled_cmds.get("chk", False)

    return (
        f"<b>Proxy Status</b>\n\n"
        f"• Saved proxies: <b>{len(proxies)}</b>\n"
        f"• /chk proxy: <b>{'ON' if chk_enabled else 'OFF'}</b>\n"
    )

# =========================================================
# CORE CHECK
# =========================================================
def fetch_instagram_page(username: str, proxy: dict | None) -> tuple[int, str]:
    res = requests.get(
        f"https://www.instagram.com/{username}/",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
        proxies=proxy,
    )
    return res.status_code, res.text

def classify_instagram_response(username: str, status_code: int, html: str) -> tuple[str, str]:
    html = html or ""
    html_len = len(html)

    # hard errors
    if status_code == 429:
        return "ERROR", f"{username} → ⚠️ ERROR"
    if status_code in (403, 500, 502, 503, 504):
        return "ERROR", f"{username} → ⚠️ ERROR"
    if not html.strip():
        return "ERROR", f"{username} → ⚠️ ERROR"

    # exact same mobile logic first
    if f'rel="alternate" href="https://www.instagram.com/{username}/"' in html:
        return "EXISTS", f"{username} → ✅ EXISTS"

    # explicit not-found markers
    not_found_markers = [
        "Sorry, this page isn't available.",
        "The link you followed may be broken",
        "Page isn't available",
        "Page Not Found",
    ]
    if status_code == 404 or any(marker in html for marker in not_found_markers):
        return "NOT_EXIST", f"{username} → ❌ NOT EXIST"

    # size-based fallback from your own Railway logs
    # stable exists zone
    if 900000 <= html_len <= 970000:
        return "EXISTS", f"{username} → ✅ EXISTS"

    # stable not-exist zone
    if 780000 <= html_len <= 880000:
        return "NOT_EXIST", f"{username} → ❌ NOT EXIST"

    # unstable compressed / drift zone seen in your latest logs
    # these were causing false NOT EXIST
    if 580000 <= html_len <= 700000:
        return "ERROR", f"{username} → ⚠️ ERROR"

    suspicious_markers = [
        "Please wait a few minutes before you try again",
        "/accounts/login/",
        "challenge",
        "checkpoint",
        "loginForm",
        '"viewer":null',
    ]
    if any(marker in html for marker in suspicious_markers):
        return "ERROR", f"{username} → ⚠️ ERROR"

    # safer fallback
    if status_code == 200:
        return "ERROR", f"{username} → ⚠️ ERROR"

    return "ERROR", f"{username} → ⚠️ ERROR"

def check_instagram_username(username: str, proxy: dict | None) -> dict:
    for attempt in range(2):
        try:
            status_code, html = fetch_instagram_page(username, proxy)
            preview = (html[:180] if html else "").replace("\n", " ").replace("\r", " ")
            log(f"CHECK username={username} status={status_code} html_len={len(html)} proxy={proxy} attempt={attempt+1}")
            log(f"HTML_PREVIEW username={username} preview={preview}")

            status_key, result = classify_instagram_response(username, status_code, html)

            if status_key == "ERROR" and attempt == 0:
                time.sleep(RETRY_DELAY)
                continue

            log(f"RESULT {result}")
            return {
                "username": username,
                "status": status_key,
                "result": result,
            }

        except Exception as e:
            log(f"ERROR username={username} err={e} attempt={attempt+1}")
            if attempt == 0:
                time.sleep(RETRY_DELAY)
                continue

            result = f"{username} → ⚠️ ERROR"
            log(f"RESULT {result}")
            return {
                "username": username,
                "status": "ERROR",
                "result": result,
            }

    result = f"{username} → ⚠️ ERROR"
    log(f"RESULT {result}")
    return {
        "username": username,
        "status": "ERROR",
        "result": result,
    }

# =========================================================
# UI HELPERS
# =========================================================
async def send_html_reply(update: Update, text: str, **kwargs):
    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_to_message_id=reply_id(update),
        **kwargs,
    )

def build_main_welcome(user_name: str) -> str:
    return (
        f"<b>🔥 Instagram Checker Bot</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"👋 Welcome, <b>{user_name}</b>\n\n"
        f"This bot is built for Instagram username checking, access control, "
        f"admin tools, backups, logs, and proxy management.\n\n"
        f"📌 Use <b>/cmds</b> to see all commands\n"
        f"📘 Use <b>/help</b> to learn how to use them\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"⚡ Fast • Structured • Railway Ready"
    )

def build_cmds_text(user_id: int) -> str:
    text = (
        "<b>📜 Command Panel</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "<b>🔹 Basic Commands</b>\n"
        "• /start → welcome message\n"
        "• /cmds → command list\n"
        "• /help → usage guide\n"
        "• /id → show your Telegram info\n"
        "• /ping → uptime and bot status\n\n"
        "<b>⚡ Pro Commands</b>\n"
        "• /chk → Instagram username checker\n"
    )

    if is_admin(user_id):
        text += (
            "\n<b>👑 Admin Commands</b>\n"
            "• /approve &lt;user_id&gt; &lt;cmd|all&gt;\n"
            "• /revoke &lt;user_id&gt; [cmd|all]\n"
            "• /ban &lt;user_id&gt;\n"
            "• /unban &lt;user_id&gt;\n"
            "• /log → get full log file\n"
            "• /ram → system details\n"
            "• /cleanram → cleanup memory\n"
            "• /backup → download all project files as zip\n"
            "• /restore → reply to backup zip to restore\n"
            "• /proxy → full proxy panel\n"
        )

    text += "\n━━━━━━━━━━━━━━━━━━━\nUse <b>/help</b> for detailed usage."
    return text

def build_help_text(user_id: int) -> str:
    text = (
        "<b>📘 Help Guide</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "<b>🔹 /start</b>\n"
        "Shows the welcome message and points you to /cmds.\n\n"
        "<b>🔹 /cmds</b>\n"
        "Shows all commands grouped by category.\n\n"
        "<b>🔹 /id</b>\n"
        "Shows your Telegram ID, name, and username.\n\n"
        "<b>🔹 /ping</b>\n"
        "Shows uptime and bot health.\n\n"
        "<b>⚡ /chk usage</b>\n"
        "1) Single username:\n"
        "<code>/chk username</code>\n\n"
        "2) Multiple usernames in one message:\n"
        "<code>/chk user1 user2 user3</code>\n\n"
        "3) Multiline:\n"
        "<code>/chk\nuser1\nuser2\nuser3</code>\n\n"
        "4) TXT file:\n"
        "Upload a .txt file, then reply to that file with <code>/chk</code>\n\n"
        "📌 Notes:\n"
        "• No @ needed\n"
        "• Duplicates are removed automatically\n"
        "• One /chk request uses one proxy only\n"
        "• Next /chk may use a different proxy\n"
        "• 429 stays error, not fake not-exist\n"
        "• unstable 600k HTML pages stay error now\n"
    )

    if is_admin(user_id):
        text += (
            "\n<b>👑 Admin Tips</b>\n"
            "• Approve user for one command: <code>/approve 123456789 chk</code>\n"
            "• Approve user for all pro commands: <code>/approve 123456789 all</code>\n"
            "• Revoke full access: <code>/revoke 123456789 all</code>\n"
            "• Ban user: <code>/ban 123456789</code>\n"
            "• Unban user: <code>/unban 123456789</code>\n"
            "• Open proxy manager: <code>/proxy</code>\n"
        )

    text += "\n━━━━━━━━━━━━━━━━━━━\nBuilt for clear replies and admin control."
    return text

def build_chk_status_text(
    title: str,
    total: int,
    exist: int,
    not_exist: int,
    error: int,
    proxy_status: str,
    elapsed: int,
    progress: int | None = None,
) -> str:
    text = (
        f"<b>{title}</b>\n\n"
        f"━━━━━━━━━━━━━━━━━━━\n"
        f"📦 Total: <b>{total}</b>\n"
        f"✅ Exist: <b>{exist}</b>\n"
        f"❌ Not Exist: <b>{not_exist}</b>\n"
        f"⚠️ Error: <b>{error}</b>\n\n"
        f"🌐 Proxy: <b>{proxy_status}</b>\n"
        f"⏱ Time: <b>{elapsed}s</b>\n"
        f"━━━━━━━━━━━━━━━━━━━"
    )

    if progress is not None:
        text += f"\n\n⚡ Progress: <b>{progress}/{total}</b>"

    return text

# =========================================================
# BASIC COMMANDS
# =========================================================
async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log(f"/start by user_id={user.id}")
    await send_html_reply(update, build_main_welcome(user.first_name or "User"))

async def cmds_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log(f"/cmds by user_id={user.id}")
    await send_html_reply(update, build_cmds_text(user.id))

async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log(f"/help by user_id={user.id}")
    await send_html_reply(update, build_help_text(user.id))

async def id_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log(f"/id by user_id={user.id}")

    username = f"@{user.username}" if user.username else "No username"
    first_name = user.first_name or "Unknown"
    last_name = user.last_name or "None"

    text = (
        "<b>🆔 User Details</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"👤 First Name: <b>{first_name}</b>\n"
        f"👥 Last Name: <b>{last_name}</b>\n"
        f"🔗 Username: <b>{username}</b>\n"
        f"🆔 User ID: <code>{user.id}</code>\n"
        "━━━━━━━━━━━━━━━━━━━"
    )

    await send_html_reply(update, text)

async def ping_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    uptime = int(time.time() - START_TIME)
    log(f"/ping by user_id={user.id}")

    text = (
        "<b>🏓 Bot Status</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "⚡ Status: <b>ONLINE</b>\n"
        f"⏱ Uptime: <b>{uptime}</b> sec\n"
        f"🧠 Python: <b>{platform.python_version()}</b>\n"
        f"💻 Platform: <b>{platform.system()} {platform.release()}</b>\n"
        "━━━━━━━━━━━━━━━━━━━"
    )

    await send_html_reply(update, text)

# =========================================================
# PRO COMMANDS
# =========================================================
async def chk_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log(f"/chk by user_id={user.id}")

    if is_banned(user.id):
        await send_html_reply(update, "❌ <b>You are banned from using this bot.</b>")
        return

    if not is_approved(user.id, "chk"):
        await send_html_reply(
            update,
            "❌ <b>You are not approved for /chk.</b>\n\n"
            "Ask admin for access."
        )
        return

    start_time = time.time()
    usernames: list[str] = []

    if context.args:
        usernames.extend([clean_username(x) for x in context.args])

    if update.message and update.message.text:
        raw_text = update.message.text
        raw_text = raw_text.replace("/chk", "", 1).strip()
        if raw_text:
            usernames.extend(extract_usernames(raw_text))

    if update.message and update.message.reply_to_message:
        doc = update.message.reply_to_message.document
        if doc and doc.file_name and doc.file_name.lower().endswith(".txt"):
            try:
                file = await context.bot.get_file(doc.file_id)
                content = await file.download_as_bytearray()
                decoded = content.decode("utf-8", errors="ignore")
                usernames.extend(extract_usernames(decoded))
                log(f"Loaded usernames from txt file: {doc.file_name}")
            except Exception as e:
                log(f"TXT_READ_ERROR err={e}")
                await send_html_reply(update, f"⚠️ <b>Could not read txt file.</b>\n<code>{e}</code>")
                return

    cleaned = []
    seen = set()
    for u in usernames:
        u = clean_username(u)
        if not u:
            continue
        if not is_valid_username(u):
            continue
        if u not in seen:
            seen.add(u)
            cleaned.append(u)

    usernames = cleaned

    if not usernames:
        await send_html_reply(
            update,
            "<b>⚠️ No valid usernames found.</b>\n\n"
            "Examples:\n"
            "<code>/chk username</code>\n"
            "<code>/chk user1 user2</code>\n"
            "Or reply to a .txt file with <code>/chk</code>"
        )
        return

    proxy = get_proxy_for_request("chk")
    proxy_status = "ON | LIVE" if proxy else "OFF"
    worker_threads = THREADS if proxy else SAFE_THREADS_NO_PROXY

    log(
        f"NEW_CHK_REQUEST user_id={user.id} usernames={len(usernames)} "
        f"proxy={proxy} worker_threads={worker_threads}"
    )

    progress_message = await update.message.reply_text(
        build_chk_status_text(
            title="🔍 Check Started",
            total=len(usernames),
            exist=0,
            not_exist=0,
            error=0,
            proxy_status=proxy_status,
            elapsed=0,
            progress=0,
        ),
        parse_mode=ParseMode.HTML,
        reply_to_message_id=reply_id(update),
    )

    exist_count = 0
    not_exist_count = 0
    error_count = 0
    exists_list: list[str] = []

    def worker(username: str) -> dict:
        return check_instagram_username(username, proxy)

    with ThreadPoolExecutor(max_workers=worker_threads) as executor:
        for i, item in enumerate(executor.map(worker, usernames), start=1):
            status = item["status"]
            username = item["username"]

            if status == "EXISTS":
                exist_count += 1
                exists_list.append(username)
            elif status == "NOT_EXIST":
                not_exist_count += 1
            else:
                error_count += 1

            if i % 2 == 0 or i == len(usernames):
                elapsed = int(time.time() - start_time)
                try:
                    await progress_message.edit_text(
                        build_chk_status_text(
                            title="🔄 Check Running",
                            total=len(usernames),
                            exist=exist_count,
                            not_exist=not_exist_count,
                            error=error_count,
                            proxy_status=proxy_status,
                            elapsed=elapsed,
                            progress=i,
                        ),
                        parse_mode=ParseMode.HTML,
                        reply_markup=None,
                    )
                except Exception as e:
                    log(f"EDIT_TEXT_ERROR err={e}")

    elapsed_total = int(time.time() - start_time)
    context.user_data["last_exists"] = "\n".join(exists_list)

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Get Clean Exists TXT", callback_data="get_exists")]
    ])

    try:
        await progress_message.edit_text(
            build_chk_status_text(
                title="📊 Check Complete",
                total=len(usernames),
                exist=exist_count,
                not_exist=not_exist_count,
                error=error_count,
                proxy_status=proxy_status,
                elapsed=elapsed_total,
                progress=len(usernames),
            ),
            parse_mode=ParseMode.HTML,
            reply_markup=keyboard,
        )
    except Exception as e:
        log(f"FINAL_EDIT_TEXT_ERROR err={e}")

async def download_exists_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user

    await query.answer()
    log(f"DOWNLOAD_EXISTS by user_id={user.id}")

    data = context.user_data.get("last_exists", "")
    if not data.strip():
        await query.message.reply_text(
            "❌ No exists usernames available.",
            reply_to_message_id=query.message.message_id,
        )
        return

    file_bytes = io.BytesIO(data.encode("utf-8"))
    file_bytes.seek(0)

    await query.message.reply_document(
        document=file_bytes,
        filename="exists_usernames.txt",
        caption="📥 Clean exists usernames",
        reply_to_message_id=query.message.message_id,
    )

# =========================================================
# ADMIN COMMANDS
# =========================================================
async def approve_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log(f"/approve by user_id={user.id}")

    if not is_admin(user.id):
        await send_html_reply(update, "❌ <b>Admin only.</b>")
        return

    if len(context.args) < 2:
        await send_html_reply(
            update,
            "<b>Usage:</b>\n<code>/approve user_id cmd</code>\n"
            "<code>/approve user_id all</code>"
        )
        return

    target_user_id = context.args[0]
    cmd_name = context.args[1].lower()

    data = load_data()
    data["approved"].setdefault(target_user_id, [])

    if cmd_name not in data["approved"][target_user_id]:
        data["approved"][target_user_id].append(cmd_name)

    save_data(data)
    log(f"APPROVED target={target_user_id} cmd={cmd_name}")

    await send_html_reply(
        update,
        "<b>✅ Approval Updated</b>\n\n"
        f"User: <code>{target_user_id}</code>\n"
        f"Access: <b>{cmd_name}</b>"
    )

async def revoke_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log(f"/revoke by user_id={user.id}")

    if not is_admin(user.id):
        await send_html_reply(update, "❌ <b>Admin only.</b>")
        return

    if len(context.args) < 1:
        await send_html_reply(
            update,
            "<b>Usage:</b>\n<code>/revoke user_id</code>\n"
            "<code>/revoke user_id cmd</code>\n"
            "<code>/revoke user_id all</code>"
        )
        return

    target_user_id = context.args[0]
    cmd_name = context.args[1].lower() if len(context.args) > 1 else "all"

    data = load_data()

    if target_user_id not in data["approved"]:
        await send_html_reply(update, "⚠️ <b>User has no approvals saved.</b>")
        return

    if cmd_name == "all":
        data["approved"].pop(target_user_id, None)
        save_data(data)
        log(f"REVOKED_ALL target={target_user_id}")
        await send_html_reply(
            update,
            "<b>❌ Access Revoked</b>\n\n"
            f"User: <code>{target_user_id}</code>\n"
            "Removed: <b>all approvals</b>"
        )
        return

    user_cmds = data["approved"].get(target_user_id, [])
    if cmd_name in user_cmds:
        user_cmds.remove(cmd_name)

    if not user_cmds:
        data["approved"].pop(target_user_id, None)
    else:
        data["approved"][target_user_id] = user_cmds

    save_data(data)
    log(f"REVOKED target={target_user_id} cmd={cmd_name}")

    await send_html_reply(
        update,
        "<b>❌ Access Revoked</b>\n\n"
        f"User: <code>{target_user_id}</code>\n"
        f"Removed: <b>{cmd_name}</b>"
    )

async def ban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log(f"/ban by user_id={user.id}")

    if not is_admin(user.id):
        await send_html_reply(update, "❌ <b>Admin only.</b>")
        return

    if len(context.args) < 1:
        await send_html_reply(update, "<b>Usage:</b>\n<code>/ban user_id</code>")
        return

    try:
        target = int(context.args[0])
    except ValueError:
        await send_html_reply(update, "⚠️ <b>Invalid user ID.</b>")
        return

    data = load_data()
    if target not in data["banned"]:
        data["banned"].append(target)
    save_data(data)
    log(f"BANNED target={target}")

    await send_html_reply(update, f"🚫 <b>User banned</b>\n\nUser: <code>{target}</code>")

async def unban_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log(f"/unban by user_id={user.id}")

    if not is_admin(user.id):
        await send_html_reply(update, "❌ <b>Admin only.</b>")
        return

    if len(context.args) < 1:
        await send_html_reply(update, "<b>Usage:</b>\n<code>/unban user_id</code>")
        return

    try:
        target = int(context.args[0])
    except ValueError:
        await send_html_reply(update, "⚠️ <b>Invalid user ID.</b>")
        return

    data = load_data()
    if target in data["banned"]:
        data["banned"].remove(target)
        save_data(data)

    log(f"UNBANNED target={target}")
    await send_html_reply(update, f"✅ <b>User unbanned</b>\n\nUser: <code>{target}</code>")

async def log_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log(f"/log by user_id={user.id}")

    if not is_admin(user.id):
        await send_html_reply(update, "❌ <b>Admin only.</b>")
        return

    if not os.path.exists(LOG_FILE):
        await send_html_reply(update, "📭 <b>No log file found yet.</b>")
        return

    with open(LOG_FILE, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename=LOG_FILE,
            reply_to_message_id=reply_id(update),
            caption="📄 Full bot log file"
        )

async def ram_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log(f"/ram by user_id={user.id}")

    if not is_admin(user.id):
        await send_html_reply(update, "❌ <b>Admin only.</b>")
        return

    vm = psutil.virtual_memory()
    disk = psutil.disk_usage("/")
    proc = psutil.Process(os.getpid())

    text = (
        "<b>🖥 System Details</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        f"🧠 RAM Used: <b>{vm.percent}%</b>\n"
        f"📦 RAM Total: <b>{round(vm.total / (1024**3), 2)} GB</b>\n"
        f"📁 Disk Used: <b>{disk.percent}%</b>\n"
        f"💾 Disk Total: <b>{round(disk.total / (1024**3), 2)} GB</b>\n"
        f"⚙️ Process Memory: <b>{round(proc.memory_info().rss / (1024**2), 2)} MB</b>\n"
        f"💻 Platform: <b>{platform.system()} {platform.release()}</b>\n"
        f"🐍 Python: <b>{platform.python_version()}</b>\n"
        "━━━━━━━━━━━━━━━━━━━"
    )

    await send_html_reply(update, text)

async def cleanram_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log(f"/cleanram by user_id={user.id}")

    if not is_admin(user.id):
        await send_html_reply(update, "❌ <b>Admin only.</b>")
        return

    gc.collect()

    text = (
        "<b>🧹 Memory Cleanup</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "✅ Python garbage collector triggered.\n"
        "ℹ️ Full OS RAM release is controlled by the host system.\n"
        "━━━━━━━━━━━━━━━━━━━"
    )
    await send_html_reply(update, text)

async def backup_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log(f"/backup by user_id={user.id}")

    if not is_admin(user.id):
        await send_html_reply(update, "❌ <b>Admin only.</b>")
        return

    backup_name = "backup.zip"

    with zipfile.ZipFile(backup_name, "w", zipfile.ZIP_DEFLATED) as zf:
        for item in os.listdir("."):
            if item in {backup_name, "__pycache__"}:
                continue
            if os.path.isdir(item):
                continue
            zf.write(item)

    with open(backup_name, "rb") as f:
        await update.message.reply_document(
            document=f,
            filename=backup_name,
            reply_to_message_id=reply_id(update),
            caption="🗂 Project backup ready"
        )

    log("BACKUP_CREATED")

async def restore_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log(f"/restore by user_id={user.id}")

    if not is_admin(user.id):
        await send_html_reply(update, "❌ <b>Admin only.</b>")
        return

    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await send_html_reply(
            update,
            "<b>Usage:</b>\nReply to a backup zip file with <code>/restore</code>"
        )
        return

    doc = update.message.reply_to_message.document
    if not doc.file_name.lower().endswith(".zip"):
        await send_html_reply(update, "⚠️ <b>Reply to a valid .zip backup file.</b>")
        return

    restore_path = "restore.zip"

    try:
        tg_file = await context.bot.get_file(doc.file_id)
        await tg_file.download_to_drive(restore_path)

        with zipfile.ZipFile(restore_path, "r") as zf:
            zf.extractall(".")

        log(f"RESTORE_DONE filename={doc.file_name}")
        await send_html_reply(
            update,
            f"<b>✅ Restore Complete</b>\n\nRestored from: <code>{doc.file_name}</code>"
        )
    except Exception as e:
        log(f"RESTORE_ERROR err={e}")
        await send_html_reply(update, f"⚠️ <b>Restore failed.</b>\n<code>{e}</code>")

# =========================================================
# PROXY UI
# =========================================================
def proxy_keyboard() -> InlineKeyboardMarkup:
    kb = [
        [InlineKeyboardButton("📊 Status", callback_data="proxy_status")],
        [InlineKeyboardButton("➕ Add Proxy", callback_data="proxy_add")],
        [InlineKeyboardButton("➖ Remove Proxy", callback_data="proxy_remove")],
        [InlineKeyboardButton("📋 List Proxies", callback_data="proxy_list")],
        [InlineKeyboardButton("🧪 Test Proxies", callback_data="proxy_test")],
        [InlineKeyboardButton("⚙ Toggle /chk Proxy", callback_data="proxy_toggle_chk")],
    ]
    return InlineKeyboardMarkup(kb)

async def proxy_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    log(f"/proxy by user_id={user.id}")

    if not is_admin(user.id):
        await send_html_reply(update, "❌ <b>Admin only.</b>")
        return

    text = (
        "<b>🌐 Proxy Manager</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━\n"
        "Manage saved proxies, test them, and enable or disable proxy usage for /chk.\n\n"
        "Supported formats:\n"
        "<code>host:port</code>\n"
        "<code>host:port:user:pass</code>\n"
        "━━━━━━━━━━━━━━━━━━━"
    )

    await update.message.reply_text(
        text,
        parse_mode=ParseMode.HTML,
        reply_markup=proxy_keyboard(),
        reply_to_message_id=reply_id(update),
    )

async def proxy_buttons(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = update.effective_user

    await query.answer()
    log(f"PROXY_BUTTON user_id={user.id} data={query.data}")

    if not is_admin(user.id):
        await query.message.reply_text("❌ Admin only.")
        return

    data = load_proxies()

    if query.data == "proxy_status":
        await query.message.reply_text(
            proxy_status_text(),
            parse_mode=ParseMode.HTML,
            reply_to_message_id=query.message.message_id,
        )

    elif query.data == "proxy_add":
        context.user_data["proxy_mode"] = "add"
        await query.message.reply_text(
            "<b>➕ Add Proxy Mode</b>\n\n"
            "Send one or more proxies now.\n\n"
            "Formats:\n"
            "<code>host:port</code>\n"
            "<code>host:port:user:pass</code>",
            parse_mode=ParseMode.HTML,
            reply_to_message_id=query.message.message_id,
        )

    elif query.data == "proxy_remove":
        context.user_data["proxy_mode"] = "remove"
        await query.message.reply_text(
            "<b>➖ Remove Proxy Mode</b>\n\n"
            "Send one or more exact proxy lines to remove.",
            parse_mode=ParseMode.HTML,
            reply_to_message_id=query.message.message_id,
        )

    elif query.data == "proxy_list":
        proxies = data.get("proxies", [])
        if not proxies:
            await query.message.reply_text(
                "📭 <b>No proxies saved.</b>",
                parse_mode=ParseMode.HTML,
                reply_to_message_id=query.message.message_id,
            )
        else:
            text = "<b>📋 Saved Proxies</b>\n\n" + "\n".join(
                f"{i+1}. <code>{p}</code>" for i, p in enumerate(proxies[:100])
            )
            await query.message.reply_text(
                text,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=query.message.message_id,
            )

    elif query.data == "proxy_test":
        proxies = data.get("proxies", [])
        if not proxies:
            await query.message.reply_text(
                "📭 <b>No proxies to test.</b>",
                parse_mode=ParseMode.HTML,
                reply_to_message_id=query.message.message_id,
            )
            return

        await query.message.reply_text(
            f"🧪 <b>Testing {len(proxies)} proxies...</b>",
            parse_mode=ParseMode.HTML,
            reply_to_message_id=query.message.message_id,
        )

        results = []
        for p in proxies:
            try:
                proxy_url = format_proxy(p)
                requests.get(
                    "https://httpbin.org/ip",
                    proxies={"http": proxy_url, "https": proxy_url},
                    timeout=8,
                )
                results.append(f"{p} → ✅ LIVE")
                log(f"PROXY_TEST {p} LIVE")
            except Exception as e:
                results.append(f"{p} → ❌ DEAD")
                log(f"PROXY_TEST {p} DEAD err={e}")

        chunk = "<b>🧪 Proxy Test Result</b>\n\n"
        for line in results:
            if len(chunk) + len(line) + 1 > 3500:
                await query.message.reply_text(
                    chunk,
                    parse_mode=ParseMode.HTML,
                    reply_to_message_id=query.message.message_id,
                )
                chunk = ""
            chunk += line + "\n"

        if chunk.strip():
            await query.message.reply_text(
                chunk,
                parse_mode=ParseMode.HTML,
                reply_to_message_id=query.message.message_id,
            )

    elif query.data == "proxy_toggle_chk":
        current = data.get("enabled_cmds", {}).get("chk", False)
        data.setdefault("enabled_cmds", {})["chk"] = not current
        save_proxies(data)
        log(f"PROXY_TOGGLE chk={not current}")

        await query.message.reply_text(
            f"⚙️ <b>/chk proxy is now {'ON' if not current else 'OFF'}</b>",
            parse_mode=ParseMode.HTML,
            reply_to_message_id=query.message.message_id,
        )

async def proxy_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message:
        return

    user = update.effective_user
    if not is_admin(user.id):
        return

    mode = context.user_data.get("proxy_mode")
    if not mode:
        return

    lines = [x.strip() for x in update.message.text.splitlines() if x.strip()]
    if not lines:
        await send_html_reply(update, "⚠️ <b>No proxy lines received.</b>")
        return

    data = load_proxies()
    proxies = data.get("proxies", [])

    valid_lines = []
    invalid_lines = []

    for line in lines:
        try:
            format_proxy(line)
            valid_lines.append(line)
        except Exception:
            invalid_lines.append(line)

    if mode == "add":
        new_count = 0
        for line in valid_lines:
            if line not in proxies:
                proxies.append(line)
                new_count += 1

        data["proxies"] = proxies
        save_proxies(data)
        log(f"PROXY_ADD added={new_count}")

        text = (
            "<b>✅ Proxy Add Result</b>\n\n"
            f"Added: <b>{new_count}</b>\n"
            f"Invalid: <b>{len(invalid_lines)}</b>"
        )
        if invalid_lines:
            text += "\n\nInvalid lines:\n" + "\n".join(f"<code>{x}</code>" for x in invalid_lines[:20])

        await send_html_reply(update, text)

    elif mode == "remove":
        removed = 0
        for line in valid_lines:
            if line in proxies:
                proxies.remove(line)
                removed += 1

        data["proxies"] = proxies
        save_proxies(data)
        log(f"PROXY_REMOVE removed={removed}")

        text = (
            "<b>❌ Proxy Remove Result</b>\n\n"
            f"Removed: <b>{removed}</b>\n"
            f"Invalid: <b>{len(invalid_lines)}</b>"
        )
        if invalid_lines:
            text += "\n\nInvalid lines:\n" + "\n".join(f"<code>{x}</code>" for x in invalid_lines[:20])

        await send_html_reply(update, text)

    context.user_data.pop("proxy_mode", None)

# =========================================================
# MAIN
# =========================================================
def main():
    log("BOT_STARTING")

    app = ApplicationBuilder().token(BOT_TOKEN).build()

    # basic
    app.add_handler(CommandHandler("start", start_cmd))
    app.add_handler(CommandHandler("cmds", cmds_cmd))
    app.add_handler(CommandHandler("help", help_cmd))
    app.add_handler(CommandHandler("id", id_cmd))
    app.add_handler(CommandHandler("ping", ping_cmd))

    # pro
    app.add_handler(CommandHandler("chk", chk_cmd))

    # admin
    app.add_handler(CommandHandler("approve", approve_cmd))
    app.add_handler(CommandHandler("revoke", revoke_cmd))
    app.add_handler(CommandHandler("ban", ban_cmd))
    app.add_handler(CommandHandler("unban", unban_cmd))
    app.add_handler(CommandHandler("log", log_cmd))
    app.add_handler(CommandHandler("ram", ram_cmd))
    app.add_handler(CommandHandler("cleanram", cleanram_cmd))
    app.add_handler(CommandHandler("backup", backup_cmd))
    app.add_handler(CommandHandler("restore", restore_cmd))
    app.add_handler(CommandHandler("proxy", proxy_cmd))

    # callback ui
    app.add_handler(CallbackQueryHandler(download_exists_callback, pattern="^get_exists$"))
    app.add_handler(CallbackQueryHandler(proxy_buttons, pattern="^proxy_"))

    # proxy text input mode
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, proxy_input_handler))

    log("BOT_RUNNING")
    app.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
