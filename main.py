#!/usr/bin/env python3
"""
Telegram Bot for Instagram Username Checker
- Free commands: /id, /ping, /help, /cmds
- Premium command (requires admin approval): /chk
- Admin commands: /ban, /unban, /approve, /revoke, /ram, /cleanram, /log, /backup, /restore, /proxy

Environment variables:
- BOT_TOKEN: your Telegram bot token
- BOT_ADMIN: comma-separated list of admin user IDs (integers)
"""

import asyncio
import aiohttp
import json
import logging
import os
import random
import time
import gc
import psutil
import sys
import zipfile
import io
from datetime import datetime
from functools import wraps
from pathlib import Path
from typing import Dict, List, Tuple

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)

# ------------------------------
# Configuration & Constants
# ------------------------------
TOKEN = os.getenv("BOT_TOKEN")
if not TOKEN:
    raise ValueError("BOT_TOKEN environment variable not set")

ADMIN_IDS = {int(x.strip()) for x in os.getenv("BOT_ADMIN", "").split(",") if x.strip()}
if not ADMIN_IDS:
    raise ValueError("BOT_ADMIN environment variable not set or empty")

USER_DATA_FILE = "user_data.json"
PROXY_CONFIG_FILE = "proxy_config.json"
LOG_FILE = "bot.log"
BACKUP_DIR = Path("backups")
BACKUP_INTERVAL_HOURS = 48

# Default proxy config
DEFAULT_PROXY_CONFIG = {
    "proxies": [],                # list of proxy strings (http://user:pass@host:port)
    "enabled_for_chk": False,     # whether to use proxies for /chk command
}

# Instagram checker settings
MAX_CONCURRENT_CHECKS = 5
CHECK_TIMEOUT = 10
RETRY_LIMIT = 3

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
    handlers=[
        logging.FileHandler(LOG_FILE),
        logging.StreamHandler(sys.stdout),
    ],
)
logger = logging.getLogger(__name__)

# Global data
user_data: Dict[str, Dict] = {}
proxy_config: Dict = {}
start_time = datetime.now()
file_lock = asyncio.Lock()


# ------------------------------
# Persistence Helpers
# ------------------------------
async def load_user_data():
    global user_data
    async with file_lock:
        if Path(USER_DATA_FILE).exists():
            with open(USER_DATA_FILE, "r") as f:
                user_data = json.load(f)
        else:
            user_data = {}
            await save_user_data()

async def save_user_data():
    async with file_lock:
        with open(USER_DATA_FILE, "w") as f:
            json.dump(user_data, f, indent=2)

async def load_proxy_config():
    global proxy_config
    async with file_lock:
        if Path(PROXY_CONFIG_FILE).exists():
            with open(PROXY_CONFIG_FILE, "r") as f:
                proxy_config = json.load(f)
        else:
            proxy_config = DEFAULT_PROXY_CONFIG.copy()
            await save_proxy_config()

async def save_proxy_config():
    async with file_lock:
        with open(PROXY_CONFIG_FILE, "w") as f:
            json.dump(proxy_config, f, indent=2)

def get_user_record(user_id: int) -> dict:
    uid = str(user_id)
    if uid not in user_data:
        user_data[uid] = {
            "id": user_id,
            "first_name": "",
            "username": "",
            "approved_commands": [],
            "banned": False,
        }
    return user_data[uid]

def is_admin(user_id: int) -> bool:
    return user_id in ADMIN_IDS

def is_banned(user_id: int) -> bool:
    record = get_user_record(user_id)
    return record.get("banned", False)

def has_permission(user_id: int, command: str) -> bool:
    if is_admin(user_id):
        return True
    if is_banned(user_id):
        return False
    record = get_user_record(user_id)
    return command in record.get("approved_commands", [])


# ------------------------------
# Permission Decorators
# ------------------------------
def require_permission(command: str):
    def decorator(func):
        @wraps(func)
        async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
            user = update.effective_user
            if user is None:
                return
            if is_banned(user.id):
                await update.message.reply_text("❌ You are banned from using this bot.")
                return
            if has_permission(user.id, command):
                return await func(update, context)
            else:
                await update.message.reply_text(
                    "⚠️ This command requires admin approval. Contact an administrator."
                )
                return
        return wrapper
    return decorator

def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user = update.effective_user
        if user is None:
            return
        if not is_admin(user.id):
            await update.message.reply_text("⛔ You are not authorized to use this command.")
            return
        return await func(update, context)
    return wrapper


# ------------------------------
# Instagram Checker Logic
# ------------------------------
async def check_single_username(
    username: str,
    use_proxy: bool,
    proxies: List[str],
    session: aiohttp.ClientSession,
) -> Tuple[str, str]:
    url = f"https://www.instagram.com/{username}/"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

    for attempt in range(1, RETRY_LIMIT + 1):
        proxy = None
        if use_proxy and proxies:
            proxy = random.choice(proxies)
        try:
            async with session.get(
                url, headers=headers, timeout=CHECK_TIMEOUT, proxy=proxy
            ) as resp:
                html = await resp.text()
                if f'rel="alternate" href="https://www.instagram.com/{username}/"' in html:
                    return username, "EXISTS"
                else:
                    if resp.status == 404:
                        return username, "NOT_EXIST"
                    return username, "NOT_EXIST"
        except Exception as e:
            logger.warning(f"Attempt {attempt} for {username} failed: {e}")
            if attempt == RETRY_LIMIT:
                return username, "ERROR"
            await asyncio.sleep(1)
    return username, "ERROR"

async def check_usernames_batch(
    usernames: List[str],
    use_proxy: bool,
    proxies: List[str],
) -> Dict[str, str]:
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_CHECKS)
    results = {}

    async def bounded_check(username):
        async with semaphore:
            async with aiohttp.ClientSession() as session:
                return await check_single_username(username, use_proxy, proxies, session)

    tasks = [bounded_check(u) for u in usernames]
    for coro in asyncio.as_completed(tasks):
        user, status = await coro
        results[user] = status
    return results


# ------------------------------
# Free Commands
# ------------------------------
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    get_user_record(user.id)
    await save_user_data()
    await update.message.reply_text(
        f"👋 Hello {user.first_name}!\n\n"
        f"🤖 *Instagram Username Checker Bot*\n"
        f"🔓 Free commands: /id , /ping , /help , /cmds\n"
        f"⭐ Premium command: /chk (requires admin approval)\n"
        f"🛠️ Admins have additional commands.\n\n"
        f"Use /help to see all available commands.",
        parse_mode="Markdown"
    )

async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    is_adm = is_admin(user_id)
    premium = has_permission(user_id, "chk")
    msg = "📖 *Bot Commands*\n\n"
    msg += "🔓 *Free for all:*\n/id - Your user info\n/ping - Bot uptime & response\n/help - Show this help\n/cmds - Same as /help\n\n"
    if premium or is_adm:
        msg += "⭐ *Premium:*\n/chk - Check Instagram usernames (supports file reply)\n\n"
    if is_adm:
        msg += "🛠️ *Admin Commands:*\n"
        msg += "/ban <id> - Ban user\n/unban <id> - Unban user\n"
        msg += "/approve <id> <cmd|all> - Grant command permission\n/revoke <id> <cmd|all> - Revoke permission\n"
        msg += "/ram - Show system resources\n/cleanram - Run garbage collection\n/log - Send bot log\n"
        msg += "/backup - Download all bot files\n/restore - Restore user data (reply to JSON)\n"
        msg += "/proxy - Manage proxies for /chk\n"
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_cmds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await cmd_help(update, context)

async def cmd_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    if not user:
        return
    record = get_user_record(user.id)
    record["first_name"] = user.first_name
    record["username"] = user.username or ""
    await save_user_data()

    status_text = "✅ Free"
    if is_banned(user.id):
        status_text = "❌ Banned"
    elif "chk" in record.get("approved_commands", []):
        status_text = "⭐ Premium (chk approved)"

    msg = (
        f"📌 *User Info*\n"
        f"ID: `{user.id}`\n"
        f"Name: {user.first_name}\n"
        f"Username: @{user.username if user.username else 'N/A'}\n"
        f"Status: {status_text}"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

async def cmd_ping(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uptime_sec = (datetime.now() - start_time).total_seconds()
    uptime_str = f"{int(uptime_sec // 3600)}h {int((uptime_sec % 3600) // 60)}m {int(uptime_sec % 60)}s"
    start_ts = time.time()
    await update.message.reply_text("🏓 Pong!")
    end_ts = time.time()
    ping_ms = (end_ts - start_ts) * 1000
    await update.message.reply_text(
        f"🕒 Uptime: `{uptime_str}`\n⏱️ Response: `{ping_ms:.0f}ms`",
        parse_mode="Markdown",
    )


# ------------------------------
# Premium Command: /chk
# ------------------------------
async def send_check_results(
    update: Update,
    usernames: List[str],
    results: Dict[str, str],
    start_time_check: float,
    context: ContextTypes.DEFAULT_TYPE,
):
    total = len(usernames)
    exist = sum(1 for s in results.values() if s == "EXISTS")
    not_exist = sum(1 for s in results.values() if s == "NOT_EXIST")
    errors = sum(1 for s in results.values() if s == "ERROR")
    elapsed = time.time() - start_time_check

    summary = (
        f"✅ *Instagram Username Check*\n"
        f"📊 Total: {total}\n"
        f"🟢 Exists: {exist}\n"
        f"🔴 Not exist: {not_exist}\n"
        f"⚠️ Errors: {errors}\n"
        f"⏱️ Time: {elapsed:.2f}s"
    )

    details = []
    for u in usernames:
        status = results.get(u, "UNKNOWN")
        if status == "EXISTS":
            details.append(f"✅ {u}")
        elif status == "NOT_EXIST":
            details.append(f"❌ {u}")
        else:
            details.append(f"⚠️ {u}")

    detail_text = "\n".join(details)
    if len(detail_text) > 3500:
        await update.message.reply_document(
            document=detail_text.encode(),
            filename="check_results.txt",
            caption=summary,
            parse_mode="Markdown",
        )
    else:
        await update.message.reply_text(summary + "\n\n" + detail_text, parse_mode="Markdown")

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("📥 Existing only (txt)", callback_data="dl_exist"),
         InlineKeyboardButton("📥 Non-existing only (txt)", callback_data="dl_notexist")]
    ])
    context.user_data["last_check_results"] = results
    context.user_data["last_check_usernames"] = usernames
    await update.message.reply_text("📎 *Download clean lists:*", reply_markup=keyboard, parse_mode="Markdown")

async def handle_download_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    results = context.user_data.get("last_check_results", {})
    if not results:
        await query.edit_message_text("No recent check results found. Please run /chk again.")
        return
    data_type = query.data
    if data_type == "dl_exist":
        usernames = [u for u, s in results.items() if s == "EXISTS"]
        filename = "existing_usernames.txt"
        caption = "✅ Existing usernames"
    else:
        usernames = [u for u, s in results.items() if s == "NOT_EXIST"]
        filename = "non_existing_usernames.txt"
        caption = "❌ Non-existing usernames"
    if not usernames:
        await query.edit_message_text("No usernames found for this category.")
        return
    content = "\n".join(usernames)
    await query.message.reply_document(
        document=content.encode(),
        filename=filename,
        caption=caption,
    )
    await query.delete_message()

@require_permission("chk")
async def cmd_chk(update: Update, context: ContextTypes.DEFAULT_TYPE):
    start_time_check = time.time()
    usernames = []

    # Reply to .txt file
    if update.message.reply_to_message and update.message.reply_to_message.document:
        doc = update.message.reply_to_message.document
        if doc.mime_type == "text/plain" or doc.file_name.endswith(".txt"):
            file = await context.bot.get_file(doc.file_id)
            content = await file.download_as_bytearray()
            lines = content.decode("utf-8").splitlines()
            usernames = [line.strip() for line in lines if line.strip()]
    else:
        if context.args:
            usernames = [arg.strip() for arg in context.args if arg.strip()]
        else:
            text = update.message.text.replace("/chk", "").strip()
            if text:
                usernames = [line.strip() for line in text.splitlines() if line.strip()]

    if not usernames:
        await update.message.reply_text(
            "❌ No usernames provided.\n"
            "Usage:\n"
            "/chk username1 username2 ...\n"
            "or reply to a .txt file with one username per line\n"
            "or send usernames line by line in the message."
        )
        return

    # Remove duplicates
    seen = set()
    unique_usernames = []
    for u in usernames:
        if u not in seen:
            seen.add(u)
            unique_usernames.append(u)
    usernames = unique_usernames

    progress_msg = await update.message.reply_text(f"🔍 Checking {len(usernames)} username(s) ... (this may take a while)")

    use_proxy = proxy_config.get("enabled_for_chk", False) and bool(proxy_config.get("proxies"))
    proxies = proxy_config.get("proxies", [])

    results = await check_usernames_batch(usernames, use_proxy, proxies)

    await progress_msg.delete()
    await send_check_results(update, usernames, results, start_time_check, context)


# ------------------------------
# Admin Commands
# ------------------------------
@admin_only
async def cmd_ban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /ban <user_id>")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID.")
        return
    record = get_user_record(user_id)
    record["banned"] = True
    await save_user_data()
    await update.message.reply_text(f"✅ User {user_id} has been banned.")

@admin_only
async def cmd_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await update.message.reply_text("Usage: /unban <user_id>")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID.")
        return
    record = get_user_record(user_id)
    record["banned"] = False
    await save_user_data()
    await update.message.reply_text(f"✅ User {user_id} has been unbanned.")

@admin_only
async def cmd_approve(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /approve <user_id> <command|all>")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID.")
        return
    cmd_name = context.args[1].lower()
    record = get_user_record(user_id)
    if cmd_name == "all":
        if "chk" not in record["approved_commands"]:
            record["approved_commands"].append("chk")
        await save_user_data()
        await update.message.reply_text(f"✅ All premium commands approved for user {user_id}.")
    elif cmd_name == "chk":
        if cmd_name not in record["approved_commands"]:
            record["approved_commands"].append(cmd_name)
            await save_user_data()
        await update.message.reply_text(f"✅ Command '{cmd_name}' approved for user {user_id}.")
    else:
        await update.message.reply_text(f"Unknown command '{cmd_name}'. Available: chk")

@admin_only
async def cmd_revoke(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if len(context.args) < 2:
        await update.message.reply_text("Usage: /revoke <user_id> <command|all>")
        return
    try:
        user_id = int(context.args[0])
    except ValueError:
        await update.message.reply_text("Invalid user ID.")
        return
    cmd_name = context.args[1].lower()
    record = get_user_record(user_id)
    if cmd_name == "all":
        record["approved_commands"] = []
        await save_user_data()
        await update.message.reply_text(f"✅ All premium commands revoked for user {user_id}.")
    elif cmd_name == "chk":
        if cmd_name in record["approved_commands"]:
            record["approved_commands"].remove(cmd_name)
            await save_user_data()
        await update.message.reply_text(f"✅ Command '{cmd_name}' revoked for user {user_id}.")
    else:
        await update.message.reply_text(f"Unknown command '{cmd_name}'. Available: chk")

@admin_only
async def cmd_ram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    mem = psutil.virtual_memory()
    cpu_percent = psutil.cpu_percent(interval=1)
    disk = psutil.disk_usage("/")
    msg = (
        f"🖥️ *System Resources*\n"
        f"RAM: {mem.used / (1024**3):.2f} GB / {mem.total / (1024**3):.2f} GB ({mem.percent}%)\n"
        f"CPU: {cpu_percent}%\n"
        f"Disk: {disk.used / (1024**3):.2f} GB / {disk.total / (1024**3):.2f} GB ({disk.percent}%)"
    )
    await update.message.reply_text(msg, parse_mode="Markdown")

@admin_only
async def cmd_cleanram(update: Update, context: ContextTypes.DEFAULT_TYPE):
    before = psutil.virtual_memory().used
    gc.collect()
    after = psutil.virtual_memory().used
    freed = (before - after) / (1024**2)
    await update.message.reply_text(f"🧹 Garbage collector run. Freed approx {freed:.2f} MB of memory.")

@admin_only
async def cmd_log(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if Path(LOG_FILE).exists():
        with open(LOG_FILE, "rb") as f:
            await update.message.reply_document(document=f, filename="bot.log")
    else:
        await update.message.reply_text("No log file found.")

@admin_only
async def cmd_backup(update: Update, context: ContextTypes.DEFAULT_TYPE):
    files_to_backup = ["main.py", "requirements.txt", "Dockerfile", USER_DATA_FILE, PROXY_CONFIG_FILE, LOG_FILE]
    zip_buffer = io.BytesIO()
    with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zipf:
        for fname in files_to_backup:
            if Path(fname).exists():
                zipf.write(fname, fname)
    zip_buffer.seek(0)
    await update.message.reply_document(
        document=zip_buffer,
        filename=f"backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.zip",
        caption="📦 Full bot backup"
    )

@admin_only
async def cmd_restore(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not update.message.reply_to_message or not update.message.reply_to_message.document:
        await update.message.reply_text("Please reply to a JSON file with /restore")
        return
    doc = update.message.reply_to_message.document
    if not doc.file_name.endswith(".json"):
        await update.message.reply_text("Only JSON files are accepted.")
        return
    file = await context.bot.get_file(doc.file_id)
    content = await file.download_as_bytearray()
    try:
        restored_data = json.loads(content.decode("utf-8"))
    except Exception as e:
        await update.message.reply_text(f"Invalid JSON: {e}")
        return
    if not isinstance(restored_data, dict):
        await update.message.reply_text("Invalid format: root must be an object.")
        return
    global user_data
    async with file_lock:
        user_data = restored_data
        await save_user_data()
    await update.message.reply_text(f"✅ User data restored. Total users: {len(user_data)}")


# ------------------------------
# Proxy Management (Admin)
# ------------------------------
def build_proxy_keyboard() -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton("📋 List Proxies", callback_data="proxy_list")],
        [InlineKeyboardButton("➕ Add Proxy", callback_data="proxy_add")],
        [InlineKeyboardButton("🗑️ Delete Proxy", callback_data="proxy_del")],
        [InlineKeyboardButton("🔌 Toggle Proxy for /chk", callback_data="proxy_toggle")],
        [InlineKeyboardButton("❌ Close", callback_data="proxy_close")],
    ]
    return InlineKeyboardMarkup(buttons)

@admin_only
async def cmd_proxy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    status = "✅ ENABLED" if proxy_config.get("enabled_for_chk") else "❌ DISABLED"
    proxy_count = len(proxy_config.get("proxies", []))
    await update.message.reply_text(
        f"🌐 *Proxy Manager*\n"
        f"Proxy count: {proxy_count}\n"
        f"/chk proxy usage: {status}\n\n"
        f"Use the buttons below to manage proxies.",
        reply_markup=build_proxy_keyboard(),
        parse_mode="Markdown",
    )

async def proxy_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data

    if data == "proxy_list":
        proxies = proxy_config.get("proxies", [])
        if not proxies:
            await query.edit_message_text("No proxies configured.", reply_markup=build_proxy_keyboard())
        else:
            text = "📋 *Current Proxies:*\n" + "\n".join(f"`{p}`" for p in proxies)
            await query.edit_message_text(text, parse_mode="Markdown", reply_markup=build_proxy_keyboard())
    elif data == "proxy_add":
        context.user_data["waiting_for_proxy"] = True
        await query.edit_message_text(
            "Send me a proxy in the format:\n`http://user:pass@host:port`\nOr `http://host:port`\n"
            "Send /cancel to abort.",
            parse_mode="Markdown",
        )
    elif data == "proxy_del":
        proxies = proxy_config.get("proxies", [])
        if not proxies:
            await query.edit_message_text("No proxies to delete.", reply_markup=build_proxy_keyboard())
            return
        buttons = []
        for idx, proxy in enumerate(proxies):
            short = proxy[:50] + "..." if len(proxy) > 50 else proxy
            buttons.append([InlineKeyboardButton(f"❌ {short}", callback_data=f"proxy_del_{idx}")])
        buttons.append([InlineKeyboardButton("🔙 Back", callback_data="proxy_back")])
        await query.edit_message_text("Select proxy to delete:", reply_markup=InlineKeyboardMarkup(buttons))
    elif data == "proxy_toggle":
        current = proxy_config.get("enabled_for_chk", False)
        proxy_config["enabled_for_chk"] = not current
        await save_proxy_config()
        new_status = "ENABLED" if not current else "DISABLED"
        await query.edit_message_text(f"Proxy for /chk has been {new_status}.", reply_markup=build_proxy_keyboard())
    elif data == "proxy_close":
        await query.delete_message()
    elif data == "proxy_back":
        await query.edit_message_text("Proxy Manager", reply_markup=build_proxy_keyboard())
    elif data.startswith("proxy_del_"):
        idx = int(data.split("_")[-1])
        proxies = proxy_config.get("proxies", [])
        if 0 <= idx < len(proxies):
            deleted = proxies.pop(idx)
            await save_proxy_config()
            await query.edit_message_text(f"Deleted: `{deleted}`", parse_mode="Markdown", reply_markup=build_proxy_keyboard())
        else:
            await query.edit_message_text("Invalid index.", reply_markup=build_proxy_keyboard())

async def handle_proxy_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if context.user_data.get("waiting_for_proxy"):
        proxy_str = update.message.text.strip()
        if proxy_str.lower() == "/cancel":
            context.user_data.pop("waiting_for_proxy", None)
            await update.message.reply_text("Cancelled.")
            return
        if not (proxy_str.startswith("http://") or proxy_str.startswith("https://") or proxy_str.startswith("socks5://")):
            await update.message.reply_text("Invalid proxy format. Must start with http://, https://, or socks5://")
            return
        proxies = proxy_config.get("proxies", [])
        proxies.append(proxy_str)
        proxy_config["proxies"] = proxies
        await save_proxy_config()
        context.user_data.pop("waiting_for_proxy", None)
        await update.message.reply_text(f"✅ Proxy added: `{proxy_str}`", parse_mode="Markdown")
        await cmd_proxy(update, context)


# ------------------------------
# Automatic Backup Task (every 48h)
# ------------------------------
async def auto_backup(app: Application):
    while True:
        await asyncio.sleep(BACKUP_INTERVAL_HOURS * 3600)
        backup_data = {
            "user_data": user_data,
            "proxy_config": proxy_config,
            "timestamp": datetime.now().isoformat(),
        }
        backup_json = json.dumps(backup_data, indent=2)
        for admin_id in ADMIN_IDS:
            try:
                await app.bot.send_document(
                    chat_id=admin_id,
                    document=backup_json.encode(),
                    filename=f"auto_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                    caption="📦 Automatic 48h backup of user data and proxy config.",
                )
            except Exception as e:
                logger.error(f"Failed to send backup to admin {admin_id}: {e}")


# ------------------------------
# Main
# ------------------------------
async def post_init(app: Application):
    """Start auto backup after app is initialized."""
    asyncio.create_task(auto_backup(app))

def main():
    # Load data
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(load_user_data())
    loop.run_until_complete(load_proxy_config())
    loop.close()

    # Build application
    app = Application.builder().token(TOKEN).post_init(post_init).build()

    # Free commands
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(CommandHandler("cmds", cmd_cmds))
    app.add_handler(CommandHandler("id", cmd_id))
    app.add_handler(CommandHandler("ping", cmd_ping))

    # Premium command
    app.add_handler(CommandHandler("chk", cmd_chk))

    # Admin commands
    app.add_handler(CommandHandler("ban", cmd_ban))
    app.add_handler(CommandHandler("unban", cmd_unban))
    app.add_handler(CommandHandler("approve", cmd_approve))
    app.add_handler(CommandHandler("revoke", cmd_revoke))
    app.add_handler(CommandHandler("ram", cmd_ram))
    app.add_handler(CommandHandler("cleanram", cmd_cleanram))
    app.add_handler(CommandHandler("log", cmd_log))
    app.add_handler(CommandHandler("backup", cmd_backup))
    app.add_handler(CommandHandler("restore", cmd_restore))
    app.add_handler(CommandHandler("proxy", cmd_proxy))

    # Callback handlers
    app.add_handler(CallbackQueryHandler(handle_download_callback, pattern="^(dl_exist|dl_notexist)$"))
    app.add_handler(CallbackQueryHandler(proxy_callback_handler, pattern="^proxy_"))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_proxy_text_input))

    # Start bot
    logger.info("Bot is starting...")
    app.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()
